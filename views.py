#!/usr/bin/env python
#
import base64
import binascii
import copy
import datetime
import decimal
import hashlib
import hmac
import logging
import json
import math
import os
import re
import struct
import sys
import time
import urllib
import urlparse
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import webapp2, jinja2
from google.appengine.api import users, memcache
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext.ndb.model import Key
#from google.appengine.api.datastore_types import BlobKey
from webapp2_extras import securecookie
from webapp2_extras import security
from webapp2_extras.appengine.users import login_required, admin_required

from routes import routes
import drm, media, mp4, utils, models, settings, testcases
from webob import exc

templates = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__),'templates')
    ),
    extensions=['jinja2.ext.autoescape'],
    trim_blocks=False,
)
templates.filters['isoDuration'] = utils.toIsoDuration
templates.filters['isoDateTime'] = utils.toIsoDateTime
templates.filters['toHtmlString'] = utils.toHtmlString
templates.filters['xmlSafe'] = utils.xmlSafe
templates.filters['base64'] = utils.toBase64
templates.filters['uuid'] = utils.toUuid

SCRIPT_TEMPLATE=r'<script src="/js/{mode}/{filename}{min}.js" type="text/javascript"></script>'
def import_script(filename):
    mode = 'dev' if settings.DEBUG else 'prod'
    min = '' if settings.DEBUG else '.min'
    return SCRIPT_TEMPLATE.format(mode=mode, filename=filename, min=min)

class CsrfFailureException(Exception):
    pass

class RequestHandler(webapp2.RequestHandler):
    CLIENT_COOKIE_NAME='dash'
    CSRF_COOKIE_NAME='csrf'
    ALLOWED_DOMAINS = re.compile(r'^http://(dashif\.org)|(shaka-player-demo\.appspot\.com)|(mediapm\.edgesuite\.net)')
    DEFAULT_TIMESHIFT_BUFFER_DEPTH=60
    INJECTED_ERROR_CODES=[404, 410, 503, 504]

    def create_context(self, **kwargs):
        route = routes[self.request.route.name]
        context = {
                   "title": kwargs.get('title', route.title),
                   "uri_for":self.uri_for,
                   "on_production_server":utils.on_production_server,
                   "import_script":import_script,
                   "http_protocol":self.request.host_url.split(':')[0]
                   }
        #parent = app.router.match()
        #(route, args, kwargs)
        for k,v in kwargs.iteritems():
            context[k] = v
        p = route.parent
        context["breadcrumbs"]=[]
        while p:
            p = routes[p]
            context["breadcrumbs"].insert(0,{"title":p.title,
                                           "href":self.uri_for(p.name)})
            p = p.parent
        context['user'] = self.user = users.get_current_user()
        if self.user:
            context['logout'] = users.create_logout_url(self.uri_for('home'))
            context["is_current_user_admin"]=users.is_current_user_admin()
        else:
            context['login'] = users.create_login_url(self.uri_for('home'))
        context['remote_addr'] = self.request.remote_addr
        context['request_uri'] = self.request.uri
        if self.is_https_request():
            context['request_uri'] = context['request_uri'].replace('http://','https://')
        return context

    def generate_csrf(self,context):
        """generate a CSRF token as a hidden form field and a secure cookie"""
        csrf = security.generate_random_string(length=32)
        sig = hmac.new(settings.csrf_secret,csrf,hashlib.sha1)
        #logging.debug('X-AppEngine-country = %s'%self.request.headers['X-AppEngine-country'])
        logging.debug('User-Agent = %s'%self.request.headers['User-Agent'])
        #logging.debug('remote_addr = %s'%self.request.remote_addr)
        cur_url = urlparse.urlparse(self.request.uri, 'http')
        origin = '%s://%s'%(cur_url.scheme, cur_url.netloc)
        logging.debug('origin = %s'%origin)
        #sig.update(self.request.headers['X-AppEngine-country'])
        sig.update(origin)
        sig.update(self.request.uri)
        #sig.update(self.request.remote_addr)
        sig.update(self.request.headers['User-Agent'])
        sig = sig.digest()
        context['csrf_token'] ='<input type="hidden" name="csrf_token" value="%s" />'%urllib.quote(binascii.b2a_base64(sig))
        sc = securecookie.SecureCookieSerializer(settings.cookie_secret)
        cookie = sc.serialize(self.CSRF_COOKIE_NAME, csrf)
        self.response.set_cookie(self.CSRF_COOKIE_NAME, cookie, httponly=True, max_age=7200)

    def check_csrf(self):
        """check that the CSRF token from the cookie and the submitted form match"""
        sc = securecookie.SecureCookieSerializer(settings.cookie_secret)
        csrf = sc.deserialize(self.CSRF_COOKIE_NAME, self.request.cookies[self.CSRF_COOKIE_NAME])
        self.response.delete_cookie(self.CSRF_COOKIE_NAME)
        if not csrf:
            logging.debug("csrf cookie not present")
            raise CsrfFailureException("csrf cookie not present")
        token = urllib.unquote(self.request.params['csrf_token'])
        sig = hmac.new(settings.csrf_secret,csrf,hashlib.sha1)
        try:
            origin = self.request.headers['Origin']
        except KeyError:
            cur_url = urlparse.urlparse(self.request.uri, 'http')
            origin = '%s://%s'%(cur_url.scheme, cur_url.netloc)
        sig.update(origin)
        sig.update(self.request.headers['Referer'])
        sig.update(self.request.headers['User-Agent'])
        sig_hex = sig.hexdigest()
        tk_hex = binascii.b2a_hex(binascii.a2b_base64(token))
        if sig_hex!=tk_hex:
            raise CsrfFailureException("signatures do not match")
        return True

    def compute_av_values(self, av, startNumber):
        av['timescale'] = av['representations'][0].timescale
        av['presentationTimeOffset'] = int((startNumber-1) * av['representations'][0].segment_duration)
        av['minBitrate'] = min([ a.bitrate for a in av['representations']])
        av['maxBitrate'] = max([ a.bitrate for a in av['representations']])
        av['maxSegmentDuration'] = max([ a.segment_duration for a in av['representations']]) / av['timescale']

    def generate_clearkey_license_url(self):
        laurl = urlparse.urljoin(self.request.host_url, self.uri_for('clearkey'))
        if self.is_https_request():
            laurl = laurl.replace('http://','https://')
        return laurl

    def generate_drm_dict(self):
        mspr = drm.PlayReady(templates)
        ck = drm.ClearKey(templates)
        rv = {
            'playready': {
                'pro': mspr.generate_pro,
                'cenc': mspr.generate_pssh,
                'moov': mspr.generate_pssh,
            },
            'marlin': {
                "MarlinContentIds": True
            },
            'clearkey': {
                'laurl': self.generate_clearkey_license_url,
                'cenc': ck.generate_pssh,
                'moov': ck.generate_pssh,
            }
        }
        drms = self.request.params.get('drm')
        if drms is None:
            return rv
        d = {}
        for name in drms.split(','):
            try:
                if '-' in name:
                    parts = name.split('-')
                    name = parts[0]
                    d[name] = {}
                    for p in parts[1:]:
                        d[name][p] = rv[name][p]
                else:
                    d[name] = rv[name]
            except KeyError:
                pass
        return d

    def calculate_dash_params(self, mode=None, mpd_url=None):
        def generateSegmentTimeline(repr):
            rv = ['<SegmentTemplate timescale="%d" '%repr.timescale,
                  'initialization="$RepresentationID$/init.mp4" ',
                  'media="$RepresentationID$/$Number$.mp4" ' ]
            timeline_start = elapsedTime - datetime.timedelta(seconds=timeShiftBufferDepth)
            first=True
            first_seg = self.calculate_segment_from_timecode(utils.scale_timedelta(timeline_start,1,1), repr, shortest_representation)
            dur=0
            while dur<=(timeShiftBufferDepth*repr.timescale):
                seg = repr.segments[first_seg['segment_num']]
                if first:
                    rv.append('startNumber="%d">'%(startNumber+long(first_seg['seg_start_time']/repr.segment_duration)))
                    rv.append('<SegmentTimeline>')
                    t = 't="%d" '%first_seg['seg_start_time']
                    first=False
                else:
                    t=''
                rv.append('<S %sd="%d"/>'%(t,seg.seg.duration))
                dur += seg.seg.duration
                first_seg['segment_num'] += 1
                if first_seg['segment_num']>repr.num_segments:
                    first_seg['segment_num']=1
            rv.append('</SegmentTimeline></SegmentTemplate>')
            return '\n'.join(rv)

        def generateSegmentList(repr):
            #TODO: support live profile
            rv = ['<SegmentList timescale="%d" duration="%d">'%(repr.timescale,repr.media_duration)]
            first=True
            for seg in repr.segments:
                if first:
                    rv.append('<Initialization range="{start:d}-{end:d}"/>'.format(start=seg.seg.pos, end=seg.seg.pos+seg.seg.size-1))
                    first=False
                else:
                    rv.append('<SegmentURL mediaRange="{start:d}-{end:d}"/>'.format(start=seg.seg.pos,end=seg.seg.pos+seg.seg.size-1))
            rv.append('</SegmentList>')
            return '\n'.join(rv)

        def generateSegmentDurations(repr):
            #TODO: support live profile
            rv = ['<SegmentDurations timescale="%d">'%(repr.timescale)]
            for seg in repr.segments:
                try:
                    rv.append('<S d="%d"/>'%(seg.seg.duration))
                except AttributeError:
                    # init segment does not have a duration
                    pass
            rv.append('</SegmentDurations>')
            return '\n'.join(rv)

        if mpd_url is None:
            mpd_url = self.request.uri
        try:
            encrypted = int(self.request.params.get('enc',''),10)
            encrypted = encrypted>0
        except ValueError:
            encrypted = re.search('enc.mpd',mpd_url) is not None
            encrypted = re.search('true',self.request.params.get('enc',str(encrypted)),re.I) is not None
        if mode is None:
            mode = self.request.params.get('mode',None)
        if mode is None:
            if re.search('vod',mpd_url) or encrypted:
                mode='vod'
            else:
                mode='live'
        if mode=='live':
            try:
                timeShiftBufferDepth = int(self.request.params.get('depth',str(self.DEFAULT_TIMESHIFT_BUFFER_DEPTH)),10)
            except ValueError:
                timeShiftBufferDepth = self.DEFAULT_TIMESHIFT_BUFFER_DEPTH # in seconds
        #media_duration = 9*60 + 32.52 #"PT0H9M32.52S"
        startNumber = 1
        now = datetime.datetime.now(tz=utils.UTC())
        clockDrift=0
        try:
            clockDrift = int(self.request.params.get('drift','0'),10)
            if clockDrift:
                now -= datetime.timedelta(seconds=clockDrift)
        except ValueError:
            pass
        publishTime = now.replace(microsecond=0)
        suggestedPresentationDelay = 30
        if mode=='live':
            if now.hour>=5:
                availabilityStartTime = now.replace(hour=5, minute=0, second=0, microsecond=0)
            else:
                availabilityStartTime = now.replace(hour=0, minute=0, second=0, microsecond=0)
            startParam = self.request.params.get('start')
            if startParam:
                if startParam == 'now':
                    availabilityStartTime = publishTime - datetime.timedelta(seconds=self.DEFAULT_TIMESHIFT_BUFFER_DEPTH)
                else:
                    try:
                        availabilityStartTime = utils.from_isodatetime(startParam)
                    except ValueError:
                        availabilityStartTime = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elapsedTime = now - availabilityStartTime
            if elapsedTime.seconds<timeShiftBufferDepth:
                timeShiftBufferDepth = elapsedTime.seconds
        else:
            availabilityStartTime = now
        baseURL = urlparse.urljoin(self.request.host_url,'/dash/'+mode)+'/'
        if self.is_https_request():
            baseURL = baseURL.replace('http://','https://')
        video = { 
                 'representations' : [ r for r in media.representations.values() if r.contentType=="video" and r.encrypted==encrypted],
                 'mediaURL':'$RepresentationID$/$Number$.m4v'
        }
        if self.request.params.get('drm'):
            video["mediaURL"] += '?drm={}'.format(self.request.params.get('drm'))
        if mode=='vod':
            elapsedTime = datetime.timedelta(seconds = video['representations'][0].media_duration / video['representations'][0].timescale)
            timeShiftBufferDepth = elapsedTime.seconds
        self.compute_av_values(video, startNumber)
        video['minWidth'] = min([ a.width for a in video['representations']])
        video['minHeight'] = min([ a.height for a in video['representations']])
        video['maxWidth'] = max([ a.width for a in video['representations']])
        video['maxHeight'] = max([ a.height for a in video['representations']])
        video['maxFrameRate'] = max([ a.frameRate for a in video['representations']])
        audio = {'representations':[ r for r in media.representations.values() if r.contentType=="audio"],
                 'mediaURL':'$RepresentationID$/$Number$.m4a'
        }
        if self.request.params.get('acodec'):
            audio['representations'] = [r for r in audio['representations'] if r.codecs.startswith(self.request.params.get('acodec'))]
        if len(audio['representations'])==1:
            audio['representations'][0].role='main'
        else:
            for rep in audio['representations']:
                if rep.codecs.startswith(self.request.params.get('main_audio','mp4a')):
                    rep.role='main'
                else:
                    rep.role='alternate'
        self.compute_av_values(audio, startNumber)
        shortest_representation=None
        media_duration = 0
        kids = set()
        for rep in video['representations']+audio['representations']:
            dur = rep.media_duration / rep.timescale
            if shortest_representation is None or dur<media_duration:
                shortest_representation = rep
                media_duration = dur
            if rep.encrypted:
                kids.update(rep.kids)
        del dur
        del rep
        maxSegmentDuration = max(video['maxSegmentDuration'],audio['maxSegmentDuration'])
        if encrypted:
            DRM = self.generate_drm_dict()
            if not kids:
                keys = models.Key.all_as_dict()
            else:
                keys = models.Key.get_kids(kids)
        del kids
        try:
            timeSource = { 'format':self.request.params['time'] }
            if timeSource['format']=='xsd':
                timeSource['method']='urn:mpeg:dash:utc:http-xsdate:2014'
            elif timeSource['format']=='iso':
                timeSource['method']='urn:mpeg:dash:utc:http-iso:2014'
            elif timeSource['format']=='ntp':
                timeSource['method']='urn:mpeg:dash:utc:http-ntp:2014'
            elif timeSource['format']=='head':
                timeSource['method']='urn:mpeg:dash:utc:http-head:2014'
                timeSource['format']='ntp'
            else:
                raise KeyError('Unknown time format')
        except KeyError:
            timeSource = {
                          'method':'urn:mpeg:dash:utc:http-xsdate:2014',
                          'format':'xsd'
            }
        if not timeSource.has_key('url'):
            timeSource['url']= urlparse.urljoin(self.request.host_url, self.uri_for('time',format=timeSource['format']))
        v_cgi_params = []
        a_cgi_params = []
        m_cgi_params = copy.deepcopy(dict(self.request.params))
        if self.request.params.get('start'):
            v_cgi_params.append('start=%s'%utils.toIsoDateTime(availabilityStartTime))
            a_cgi_params.append('start=%s'%utils.toIsoDateTime(availabilityStartTime))
        if clockDrift:
            timeSource['url'] += '?drift=%d'%clockDrift
            v_cgi_params.append('drift=%d'%clockDrift)
            a_cgi_params.append('drift=%d'%clockDrift)
        if mode=='live' and timeShiftBufferDepth != self.DEFAULT_TIMESHIFT_BUFFER_DEPTH:
            v_cgi_params.append('depth=%d'%timeShiftBufferDepth)
            a_cgi_params.append('depth=%d'%timeShiftBufferDepth)
        for code in self.INJECTED_ERROR_CODES:
            if self.request.params.get('v%03d'%code) is not None:
                times = self.calculate_injected_error_segments(self.request.params.get('v%03d'%code), \
                                                               now, availabilityStartTime, \
                                                               timeShiftBufferDepth, \
                                                               video['representations'][0])
                if times:
                    v_cgi_params.append('%03d=%s'%(code,times))
                del times
            if self.request.params.get('a%03d'%code) is not None:
                times = self.calculate_injected_error_segments(self.request.params.get('a%03d'%code), \
                                                               now, availabilityStartTime, \
                                                               timeShiftBufferDepth, \
                                                               audio['representations'][0])
                if times:
                    a_cgi_params.append('%03d=%s'%(code,times))
                del times
        if self.request.params.get('vcorrupt') is not None:
            segs = self.calculate_injected_error_segments(self.request.params.get('vcorrupt'), \
                                                          now, availabilityStartTime, \
                                                          timeShiftBufferDepth, \
                                                          video['representations'][0])
            if segs:
                v_cgi_params.append('corrupt=%s'%(segs))
            del segs
        try:
            updateCount = int(self.request.params.get('update','0'),10)
            m_cgi_params['update']=str(updateCount+1)
        except ValueError:
            pass
        if v_cgi_params:
            video['mediaURL'] += '?' + '&'.join(v_cgi_params)
        del v_cgi_params
        if a_cgi_params:
            audio['mediaURL'] += '?' + '&'.join(a_cgi_params)
        del a_cgi_params
        if m_cgi_params:
            lst = []
            for k,v in m_cgi_params.iteritems():
                lst.append('%s=%s'%(k,v))
            locationURL = self.request.uri
            if '?' in locationURL:
                locationURL = locationURL[:self.request.uri.index('?')]
            locationURL = locationURL + '?' + '&'.join(lst)
            del lst
        del m_cgi_params
        return locals()

    def add_allowed_origins(self):
        try:
            if self.ALLOWED_DOMAINS.search(self.request.headers['Origin']):
                self.response.headers.add_header("Access-Control-Allow-Origin", self.request.headers['Origin'])
                self.response.headers.add_header("Access-Control-Allow-Methods", "HEAD, GET, POST")
        except KeyError:
            pass

    def calculate_segment_from_timecode(self, timecode, repr, shortest_representation):
        """find the correct segment for the given timecode.

        :param timecode: the time (in seconds) since availabilityStartTime
            for the requested fragment.
        :param repr: the Representation to use
        :param shortest_representation: the Representation with the shortest total duration
        """
        # nominal_duration is the duration (in seconds) of the shortest representation.
        # This is used to decide how many times the stream has looped since
        # availabilityStartTime.
        nominal_duration = shortest_representation.segment_duration * shortest_representation.num_segments / float(shortest_representation.timescale)
        num_loops = long(timecode / nominal_duration)
        # origin time is the time (in seconds) that maps to segment 1 for
        # all adaptation sets. It represents the time of day when the
        # content started from the beginning, relative to availabilityStartTime
        origin_time = num_loops * nominal_duration
        assert timecode >= origin_time
        # the difference between timecode and origin_time now needs
        # to be mapped to the segment index of this representation
        segment_num = 1 + long((timecode - origin_time) * repr.timescale / repr.segment_duration)
        assert segment_num>0 and segment_num<=repr.num_segments
        # seg_start_time is the time (in repr timescale units) when this
        # segment started, relative to availabilityStartTime
        seg_start_time = origin_time * repr.timescale + (segment_num-1) * repr.segment_duration
        return locals()

    def calculate_injected_error_segments(self, times, now, availabilityStartTime, timeshiftBufferDepth, representation):
        """Calculate a list of segment numbers for injecting errors

        :param times: a string of comma separated ISO8601 times
        :param availabilityStartTime: datetime.datetime containing availability start time
        :param representation: the Representation to use when calculating segment numbering
        """
        drops=[]
        if not times:
            raise ValueError('Time must be a comma separated list of ISO times')
        earliest_available = now - datetime.timedelta(seconds=timeshiftBufferDepth)
        for d in times.split(','):
            tm = utils.from_isodatetime(d)
            tm = availabilityStartTime.replace(hour=tm.hour, minute=tm.minute, second=tm.second)
            if tm < earliest_available:
                continue
            drop_delta = tm - availabilityStartTime
            drop_seg = long(utils.scale_timedelta(drop_delta, representation.timescale, representation.segment_duration))
            drops.append('%d'%drop_seg)
        return urllib.quote_plus(','.join(drops))

    def increment_memcache_counter(self, segment, code):
        try:
            key = 'inject-%06d-%03d-%s'%(segment,code,self.request.headers['Referer'])
        except KeyError:
            key = 'inject-%06d-%03d-%s'%(segment,code,self.request.headers['Host'])
        client = memcache.Client()
        timeout = 10
        while timeout:
            counter = client.gets(key)
            if counter is None:
                client.add(key,1,time=60)
                return 1
            if client.cas(key, counter+1, time=60):
                return counter+1
            timeout -= 1
        return -1

    def get_http_range(self, content_length):
        try:
            http_range = self.request.headers['range'].lower().strip()
        except KeyError:
            return (None, None)
        if not http_range.startswith('bytes='):
            raise ValueError('Only byte based ranges are supported')
        if ',' in http_range:
            raise ValueError('Multiple ranges not supported')
        start,end = http_range[6:].split('-')
        if start=='':
            amount = int(end,10)
            start = content_length - amount
            end = content_length - 1
        elif end=='':
            end = content_length - 1
        if isinstance(start,(str,unicode)):
            start = int(start,10)
        if isinstance(end,(str,unicode)):
            end = int(end,10)
        if end>=content_length or end<start:
            self.response.set_status(416)
            self.response.headers.add_header('Content-Range','bytes */{length}'.format(length=content_length))
            raise ValueError('Invalid content range')
        self.response.set_status(206)
        self.response.headers.add_header('Content-Range','bytes {start}-{end}/{length}'.format(start=start, end=end, length=content_length))
        return (start,end)
    
    def is_https_request(self):
        if self.request.scheme == 'https':
            return True
        if self.request.environ.get('HTTPS', 'off')=='on':
            return True
        return self.request.headers.get('X-HTTP-Scheme', 'http') == 'https'

class MainPage(RequestHandler):
    """handler for main index page"""
    def get(self, **kwargs):
        context = self.create_context(**kwargs)
        try:
            context['page'] = int(self.request.params.get('page','1'),10)
        except ValueError:
            context['page'] = 1
        context['num_pages']=len(testcases.test_cases)
        context["headers"]=[]
        context['routes'] = routes
        context['video_fields'] = [ 'id', 'codecs', 'bitrate', 'height', 'width', 'encrypted' ]
        context['video_representations'] = [ r for r in media.representations.values() if r.contentType=="video"]
        context['audio_fields'] = [ 'id', 'codecs', 'bitrate', 'sampleRate', 'numChannels', 'language' ]
        context['audio_representations'] = [ r for r in media.representations.values() if r.contentType=="audio"]
        context['keys'] = models.Key.all_as_dict()
        context['rows'] = []
        key_number=1
        manifest=None
        prev_item=None
        row={ 'buttons':[], "kids":[] }
        for tst in testcases.test_cases[context['page']-1]:
            tst_manifest = testcases.manifests[tst['manifest']]
            new_row = tst_manifest!=manifest or len(row['buttons'])==3
            for field in ['title', 'details', 'static']:
                try:
                    new_row = new_row or (prev_item and prev_item[field]!=tst[field])
                except KeyError:
                    pass
            if new_row:
                if row['buttons']:
                    context['rows'].append(row)
                row={ 'buttons':[], "kids":[] }
                manifest = tst_manifest
                row.update(manifest)
            item = { 'key':key_number, 'encrypted':False }
            item.update(manifest)
            item.update(tst)
            for field in ['title', 'details']:
                try:
                    row[field] = item[field]
                except KeyError:
                    pass
            item['url'] = self.uri_for('dash-mpd', manifest=tst['manifest'])
            params=[]
            try:
                for k,v in tst['params'].iteritems():
                    if isinstance(v,(int,long)):
                        params.append('%s=%d'%(k,v))
                    else:
                        params.append('%s=%s'%(k,urllib.quote_plus(v)))
                item['url'] += '?' + '&'.join(params)
            except KeyError:
                pass
            item['abr'] = not tst['params'].has_key('repr')
            try:
                item['BaseURL'] = tst['params']['base']!=0
            except KeyError:
                item['BaseURL'] = True
            try:
                item['mup'] = tst['params']['mup']<0
            except KeyError:
                item['mup'] = True
            if item["encrypted"]:
                kids = set()
                for rep in context['video_representations']+context['audio_representations']:
                    if rep.encrypted:
                        kids.update(rep.kids)
                row["kids"] = list(kids)
            row['buttons'].append(item)
            key_number += 1
            prev_item = item
        if row['buttons']:
            context['rows'].append(row)
        template = templates.get_template('index.html')
        self.response.write(template.render(context))

class LiveManifest(RequestHandler):
    """handler for generating MPD files"""
    def head(self, manifest, **kwargs):
        self.get(manifest, **kwargs)

    def get(self, manifest, **kwargs):
        context = self.create_context(**kwargs)
        context["headers"]=[]
        context['routes'] = routes
        self.response.content_type='application/dash+xml'
        context['title'] = 'Big Buck Bunny DASH test stream'
        try:
            dash = self.calculate_dash_params()
        except ValueError, e:
            self.response.write('Invalid CGI parameters: %s'%(str(e)))
            self.response.set_status(400)
            return
        context.update(dash)
        context['repr'] = self.request.params.get('repr')
        #context['availabilityStartTime'] = datetime.datetime.utcfromtimestamp(dash['availabilityStartTime'])
        if re.search(r'(True|0)',self.request.params.get('base','False'),re.I) is not None:
            del context['baseURL']
        if context['repr'] is not None:
            context['video']['representations'] = [r for r in context['video']['representations'] if r.id==context['repr']]
        try:
            context['minimumUpdatePeriod'] = float(self.request.params.get('mup',2.0*context['video']['maxSegmentDuration']))
        except ValueError:
            context['minimumUpdatePeriod'] = 2.0*context['video']['maxSegmentDuration']
        if context['minimumUpdatePeriod']<=0:
            del context['minimumUpdatePeriod']
        for code in self.INJECTED_ERROR_CODES:
            if self.request.params.get('m%03d'%code) is not None:
                try:
                    num_failures = int(self.request.params.get('failures','1'),10)
                    for d in self.request.params.get('m%03d'%code).split(','):
                        tm = utils.from_isodatetime(d)
                        tm = dash['availabilityStartTime'].replace(hour=tm.hour, minute=tm.minute, second=tm.second)
                        try:
                            tm2 = tm + datetime.timedelta(seconds=context['minimumUpdatePeriod'])
                        except KeyError:
                            tm2 = tm + datetime.timedelta(seconds=context['minimumUpdatePeriod'])
                        if dash['now']>=tm and dash['now']<=tm2:
                            if code<500 or self.increment_memcache_counter(0,code)<=num_failures:
                                self.response.write('Synthetic %d for manifest'%(code))
                                self.response.set_status(code)
                                return
                except ValueError,e:
                    self.response.write('Invalid CGI parameters: %s'%(str(e)))
                    self.response.set_status(400)
                    return
        template = templates.get_template(manifest)
        self.add_allowed_origins()
        self.response.headers.add_header('Accept-Ranges','none')
        self.response.write(template.render(context))

class OnDemandMedia(RequestHandler): #blobstore_handlers.BlobstoreDownloadHandler):
    """Handler that returns media fragments for the on-demand profile"""
    def get(self, filename, ext):
        try:
            repr = media.representations[filename.upper()]
        except KeyError,e:
            self.response.write('%s not found: %s'%(filename,str(e)))
            self.response.set_status(404)
            return
        try:
            dash = self.calculate_dash_params('vod')
        except ValueError, e:
            self.response.write('Invalid CGI parameters: %s'%(str(e)))
            self.response.set_status(400)
            return
        mf = models.MediaFile.query(models.MediaFile.name==repr.filename).get()
        if ext=='m4a':
            self.response.content_type='audio/mp4'
        elif ext=='m4v':
            self.response.content_type='video/mp4'
        else:
            self.response.content_type='application/mp4'
        blob_info = blobstore.BlobInfo.get(mf.blob)
        try:
            start,end = self.get_http_range(blob_info.size)
        except ValueError, ve:
            self.response.write(str(ve))
            return
        if start is None:
            self.response.write('HTTP range must be specified')
            self.response.set_status(400)
            return
        blob_reader = blobstore.BlobReader(mf.blob, position=start, buffer_size=1+end-start)
        data = blob_reader.read(1+end-start)
        self.response.headers.add_header('Accept-Ranges','bytes')
        self.response.write(data)

class LiveMedia(RequestHandler): #blobstore_handlers.BlobstoreDownloadHandler):
    """Handler that returns media fragments"""
    def get(self,mode,filename,segment_num,ext):
        try:
            repr = media.representations[filename.upper()]
        except KeyError,e:
            self.response.write('%s not found: %s'%(filename,str(e)))
            self.response.set_status(404)
            return
        try:
            dash = self.calculate_dash_params(mode)
        except ValueError, e:
            self.response.write('Invalid CGI parameters: %s'%(str(e)))
            self.response.set_status(400)
            return
        if segment_num=='init':
            mod_segment = segment_num = 0
        else:
            try:
                segment_num = int(segment_num,10)
            except ValueError:
                segment_num=-1
            for code in self.INJECTED_ERROR_CODES:
                if self.request.params.get('%03d'%code) is not None:
                    try:
                        num_failures = int(self.request.params.get('failures','1'),10)
                        for d in self.request.params.get('%03d'%code).split(','):
                            if int(d,10)==segment_num:
                                # Only fail 5xx errors "num_failures" times
                                if code<500 or self.increment_memcache_counter(segment_num,code)<=num_failures:
                                    self.response.write('Synthetic %d for segment %d'%(code,segment_num))
                                    self.response.set_status(code)
                                    return
                    except ValueError, e:
                        self.response.write('Invalid CGI parameter %s: %s'%(self.request.params.get(str(code)),str(e)))
                        self.response.set_status(400)
                        return
            avInfo = dash['video'] if filename[0]=='V' else dash['audio']
            if dash['mode']=='live':
                #5.3.9.5.3 Media Segment information
                # For services with MPD@type='dynamic', the Segment availability
                # start time of a Media Segment is the sum of:
                #    the value of the MPD@availabilityStartTime,
                #    the PeriodStart time of the containing Period as defined in 5.3.2.1,
                #    the MPD start time of the Media Segment, and
                #    the MPD duration of the Media Segment.
                #
                # The Segment availability end time of a Media Segment is the sum of
                # the Segment availability start time, the MPD duration of the
                # Media Segment and the value of the attribute @timeShiftBufferDepth
                # for this Representation
                lastFragment = dash['startNumber'] + int(utils.scale_timedelta(dash['elapsedTime'], repr.timescale, repr.segment_duration))
                firstFragment = lastFragment - int(repr.timescale*dash['timeShiftBufferDepth'] / repr.segment_duration) - 1
            else:
                firstFragment = dash['startNumber']
                lastFragment = firstFragment + repr.num_segments
            if segment_num<firstFragment or segment_num>lastFragment:
                self.response.write('Segment not found (valid range= %d->%d)'%(firstFragment,lastFragment))
                self.response.set_status(404)
                return
            if dash['mode']=='live':
                # elapsed_time is the time (in seconds) since availabilityStartTime
                # for the requested fragment
                elapsed_time = (segment_num - dash['startNumber']) * repr.segment_duration / float(repr.timescale)
                segpos = self.calculate_segment_from_timecode(elapsed_time, repr, dash['shortest_representation'])
                mod_segment = segpos['segment_num']
                origin_time = segpos['origin_time']
            else:
                mod_segment = segment_num
        mf = models.MediaFile.query(models.MediaFile.name==repr.filename).get()
        if mf is None:
            self.response.write('%s not found'%(repr.filename))
            self.response.set_status(404)
            return
        #blob_info = blobstore.BlobInfo.get(mf.blob)
        if ext=='m4a':
            self.response.content_type='audio/mp4'
        elif ext=='m4v':
            self.response.content_type='video/mp4'
        else:
            self.response.content_type='application/mp4'
        assert mod_segment>=0 and mod_segment<=repr.num_segments
        frag = repr.segments[mod_segment]
        blob_reader = blobstore.BlobReader(mf.blob, position=frag.seg.pos, buffer_size=frag.seg.size)
        data = StringIO.StringIO(blob_reader.read(frag.seg.size))
        atom = mp4.Mp4Atom(atom_type='wrap', position=0, size = frag.seg.size, parent=None,
                       children=mp4.Mp4Atom.create(data))
        #atom = mp4.Mp4Atom(atom_type='wrap', position=0, size = frag.seg.size, parent=None,
        #               children=mp4.Mp4Atom.create(blob_reader))
        if segment_num==0 and repr.encrypted:
            keys = models.Key.get_kids(repr.kids)
            drms = self.generate_drm_dict()
            for drm in drms.values():
                try:
                    pssh = drm["moov"](repr, keys)
                    # insert the PSSH before the trak box
                    atom.moov.insert_child(atom.moov.index('trak'), pssh)
                except KeyError:
                    pass
        if dash['mode']=='live':
            if segment_num==0:
                try:
                    # remove the mehd box as this stream is not supposed to have a fixed duration
                    del atom.moov.mehd
                except AttributeError:
                    pass
            else:
                # Update the baseMediaDecodeTime to take account of the number of times the
                # stream would have looped since availabilityStartTime
                delta = long(origin_time*repr.timescale)
                if delta < 0L:
                    raise IOError("Failure in calculating delta %s %d %d %d"%(str(delta),segment_num,mod_segment,dash['startNumber']))
                atom.moof.traf.tfdt.base_media_decode_time += delta

                # Update the sequenceNumber field in the MovieFragmentHeader box
                atom.moof.mfhd.sequence_number = segment_num
            try:
                # remove any sidx box as it has a baseMediaDecodeTime and it's an optional index
                del data.sidx
            except AttributeError:
                pass
        self.add_allowed_origins()
        data = atom.encode()
        if self.request.params.get('corrupt') is not None:
            try:
                self.apply_corruption(repr, segment_num, atom, data)
            except ValueError, e:
                self.response.write('Invalid CGI parameter %s: %s'%(self.request.params.get('corrupt'),str(e)))
                self.response.set_status(400)
                return
        data = data[8:] # [8:] is to skip the fake "wrap" box
        try:
            start,end = self.get_http_range(frag.seg.size)
            if start is not None:
                data = data[start:end+1]
        except ValueError, ve:
            self.response.write(str(ve))
            return
        self.response.headers.add_header('Accept-Ranges','bytes')
        self.response.write(data)

    def apply_corruption(self, repr, segment_num, atom, data):
        mem = memoryview(data)
        try:
            corrupt_frames = int(self.request.params.get('frames','4'),10)
        except ValueError:
            corrupt_frames = 4
        for d in self.request.params.get('corrupt').split(','):
            if int(d,10) != segment_num:
                continue
            # put junk data in the last 2% of the segment
            #junk_count = frag.seg.size//(50*len(filling))
            #junk_size = junk_count*len(filling)
            atom.moof.traf.trun.parse_samples(data, repr.nalLengthFieldFength)
            #hdr = mp4.Mp4Atom.parse_atom_header(src)
            #while hdr and hdr['type']!='mdat':
            #    src.seek(hdr['position']+hdr['size'])
            #    hdr = mp4.Mp4Atom.parse_atom_header(src)
            #del src
            for sample in seg.moof.traf.trun.samples:
                if corrupt_frames<=0:
                    break
                for nal in sample.nals:
                    if nal.is_ref_frame and not nal.is_idr_frame:
                        junk = 'junk'
                        # put junk data in the last 20% of the NAL
                        junk_count = nal.size // (5*len(junk))
                        if junk_count:
                            junk_size = len(junk)*junk_count
                            offset =  nal.position + nal.size - junk_size
                            mem[offset:offset+junk_size] = junk_count*junk
                            #data = ''.join([data[:offset], junk_count*junk, data[offset+junk_size:]])
                            corrupt_frames -= 1
                            if corrupt_frames<=0:
                                break


class VideoPlayer(RequestHandler):
    """Responds with an HTML page that contains a video element to play the specified MPD"""
    def get(self, testcase, **kwargs):
        def gen_errors(cgiparam):
            err_time = context['now'].replace(microsecond=0) + datetime.timedelta(seconds=20)
            times=[]
            for i in range(12):
                err_time += datetime.timedelta(seconds=10)
                times.append(err_time.time().isoformat()+'Z')
            params.append('%s=%s'%(cgiparam,urllib.quote_plus(','.join(times))))

        try:
            testcase = testcases.testcase_map[testcase]
            manifest = testcases.manifests[testcase['manifest']]
        except KeyError:
            self.response.write('Unknown test case')
            self.response.set_status(404)
            return
        context = self.create_context(**kwargs)
        mpd_url = self.uri_for('dash-mpd', manifest=testcase['manifest'])
        try:
            mode = testcase['mode']
        except KeyError:
            try:
                mode = manifest['mode']
            except KeyError:
                mode = None
        context.update(self.calculate_dash_params(mpd_url=mpd_url, mode=mode))
        params=[]
        try:
            for k,v in testcase['params'].iteritems():
                if isinstance(v,(int,long)):
                    params.append('%s=%d'%(k,v))
                else:
                    params.append('%s=%s'%(k,urllib.quote_plus(v)))
        except KeyError:
            pass
        if testcase.get('corruption',False)==True:
            gen_errors('vcorrupt')
        for code in self.INJECTED_ERROR_CODES:
            p = 'v%03d'%code
            if testcase.get(p,False)==True:
                gen_errors(p)
            p = 'a%03d'%code
            if testcase.get(p,False)==True:
                gen_errors(p)
        if params:
            mpd_url += '?' + '&'.join(params)
        context['source'] = urlparse.urljoin(self.request.host_url,mpd_url)
        if self.is_https_request():
            context['source'] = context['source'].replace('http://','https://')
        else:
            try:
                if encrypted:
                    context['source'] = '#'.join([settings.sas_url,urllib.quote(context['source'])])
            except AttributeError:
                pass
        context['mimeType'] = 'application/dash+xml'
        try:
            context['title'] = testcase['title']
        except KeyError:
            context['title'] = manifest['title']
        template = templates.get_template('video.html')
        self.response.write(template.render(context))

class UTCTimeHandler(RequestHandler):
    def head(self, format, **kwargs):
        self.get(format, **kwargs)

    def get(self, format, **kwargs):
        #context = self.create_context(**kwargs)
        now = datetime.datetime.now(tz=utils.UTC())
        try:
            drift = int(self.request.params.get('drift','0'),10)
            if drift:
                now -= datetime.timedelta(seconds=drift)
        except ValueError:
            pass
        self.response.content_type='text/plain'
        rv = ''
        if format=='xsd':
            rv = utils.toIsoDateTime(now)
        elif format=='iso':
            # This code picks an obscure option from ISO 8601, so that a simple parser
            # will fail
            isocal = now.isocalendar()
            rv = '%04d-W%02d-%dT%02d:%02d:%02dZ'%(isocal[0],isocal[1],isocal[2],now.hour, now.minute, now.second)
        elif format=='ntp':
            # NTP epoch is 1st Jan 1900
            epoch = datetime.datetime(year=1900, month=1, day=1, tzinfo=utils.UTC())
            seconds = (now - epoch).total_seconds()
            fraction = seconds - int(seconds)
            seconds = int(seconds) % (1<<32)
            fraction = int(fraction*(1<<32))
            #rv = '%f   %d , %d\n'%((now - epoch).total_seconds(), seconds,fraction)
            # See RFC5905 for "NTP Timestamp format"
            rv = struct.pack('>II',seconds,fraction)
            self.response.content_type='application/octet-stream'
        self.response.write(rv)

class MediaHandler(RequestHandler):
    class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
        def post(self, *args, **kwargs):
            upload_files = self.get_uploads('file')
            logging.debug("uploaded file count: %d"%len(upload_files))
            if not users.is_current_user_admin():
                self.response.write('User is not an administrator')
                self.response.set_status(401)
                return
            if len(upload_files)==0:
                self.outer.get()
                return
            blob_info = upload_files[0]
            media_id = 'Unknown media ID'
            try:
                self.outer.check_csrf()
                media_id = self.request.get('media')
                repr = media.representations[media_id.upper()]
                context = self.outer.create_context(title='File %s uploaded'%(media_id), blob=blob_info.key())
                mf = models.MediaFile.query(models.MediaFile.name==repr.filename).get()
                if mf:
                    mf.delete()
                mf = models.MediaFile(name=repr.filename, blob=blob_info.key())
                mf.put()
                template = templates.get_template('upload-done.html')
                self.response.write(template.render(context))
            except CsrfFailureException,cfe:
                logging.debug("csrf check failed")
                logging.debug(cfe)
                self.response.write('CSRF check failed')
                self.response.write(cfe)
                self.response.set_status(401)
                blob_info.delete()
            except KeyError,e:
                self.response.write('%s not found: %s'%(media_id,str(e)))
                self.response.set_status(404)
                blob_info.delete()

    def __init__(self, request, response):
        self.initialize(request, response)
        self.upload_handler = self.UploadHandler()
        self.upload_handler.initialize(request, response)
        self.upload_handler.outer = self
        self.post = self.upload_handler.post

    def get(self, **kwargs):
        if not users.is_current_user_admin():
            self.response.write('User is not an administrator')
            self.response.set_status(401)
            return
        context = self.create_context(**kwargs)
        context['media_ids'] = media.representations.keys()
        context['media_ids'].sort()
        context['upload_url'] = blobstore.create_upload_url(self.uri_for('uploadBlob'))
        if self.is_https_request():
            context['upload_url'] = context['upload_url'].replace('http://','https://')
        context['media'] = models.MediaFile.all()
        context['media'].sort(key=lambda i: i['name'])
        context['keys'] = models.Key.all()
        context['keys'].sort(key=lambda i: i.hkid)
        self.generate_csrf(context)
        template = templates.get_template('upload.html')
        self.response.write(template.render(context))

    """handler for deleting a media blob"""
    def delete(self, mfid, **kwargs):
        if not users.is_current_user_admin():
            self.response.write('User is not an administrator')
            self.response.set_status(401)
            return
        if not mfid:
            self.response.write('MediaFile ID missing')
            self.response.set_status(400)
            return
        print('delete', mfid)
        result= { "error": "unknown error" }
        try:
            mf = models.MediaFile.query(models.Key.key==Key(urlsafe=mfid)).get()
            if not mf:
                self.response.write('{} not found'.format(blob))
                self.response.set_status(404)
                return
            mf.delete()
            result = {"deleted":mfid}
        except (ValueError) as err:
            result= { "error": str(err) }
        finally:
            self.response.content_type='application/json'
            self.response.write(json.dumps(result))

class KeyHandler(RequestHandler):
    """handler for adding a key pair"""
    def put(self, **kwargs):
        if not users.is_current_user_admin():
            self.response.write('User is not an administrator')
            self.response.set_status(401)
            return
        kid = self.request.get('kid')
        key = self.request.get('key')
        print(kid,key)
        result= { "error": "unknown error" }
        try:
            kid = models.KeyMaterial(kid)
            computed = False
            if key:
                key = models.KeyMaterial(key)
            else:
                key = models.KeyMaterial(raw=drm.PlayReady.generate_content_key(kid.raw))
                computed = True
            keypair = models.Key.query(models.Key.hkid==kid.hex).get()
            if keypair:
                raise ValueError("Duplicate KID {}".format(kid.hex))
            keypair = models.Key(hkid = kid.hex, hkey=key.hex, computed=computed)
            keypair.put()
            result = {"key":key.hex, "kid": kid.hex, "computed": computed}
        except (ValueError) as err:
            result= { "error": str(err) }
        finally:
            self.response.content_type='application/json'
            self.response.write(json.dumps(result))

    """handler for deleting a key pair"""
    def delete(self, kid, **kwargs):
        if not users.is_current_user_admin():
            self.response.write('User is not an administrator')
            self.response.set_status(401)
            return
        if not kid:
            self.response.write('KID missing')
            self.response.set_status(400)
            return
        result= { "error": "unknown error" }
        try:
            kid = models.KeyMaterial(hex=kid)
            keypair = models.Key.query(models.Key.hkid==kid.hex).get()
            if not keypair:
                self.response.write('KID {:s} not found'.format(kid))
                self.response.set_status(404)
                return
            keypair.key.delete()
            result = {"deleted":kid.hex}
        except (TypeError, ValueError) as err:
            result= { "error": str(err) }
        finally:
            self.response.content_type='application/json'
            self.response.write(json.dumps(result))
            

class ClearkeyHandler(RequestHandler):
    def post(self):
        result= { "error": "unknown error" }
        try:
            req = json.loads(self.request.body)
            kids = req["kids"]
            kids = map(self.base64url_decode, kids)
            kids = map(lambda k: k.encode('hex'), kids)
            keys = []
            for kid, key in models.Key.get_kids(kids).iteritems():
                item = {
                    "kty": "oct",
                    "kid": self.base64url_encode(key.KID.raw),
                    "k": self.base64url_encode(key.KEY.raw)
                }
                keys.append(item)
            result = {
                "keys": keys,
                "type": req["type"]
            }
        except (ValueError, KeyError) as err:
            result= { "error": str(err) }
        finally:
            self.add_allowed_origins()
            self.response.content_type = 'application/json'
            self.response.write(json.dumps(result))

    def base64url_encode(self, b):
        b = base64.b64encode(b)
        b = b.replace('+', '-')
        b = b.replace('/', '_')
        return b.replace('=', '')

    def base64url_decode(self, b):
        b = b.replace('-', '+')
        b = b.replace('_', '/')
        padding = len(b) % 4
        if padding == 2:
            b += '=='
        elif padding == 3:
            b += '='
        return base64.b64decode(b)
