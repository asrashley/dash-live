#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import base64
import binascii
import copy
import datetime
import decimal
import hashlib
import hmac
import io
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
import drm, mp4, utils, models, settings, manifests, options, segment
from webob import exc

templates = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__), '..', 'templates')
    ),
    extensions=['jinja2.ext.autoescape'],
    trim_blocks=False,
)
templates.filters['base64'] = utils.toBase64
templates.filters['dateTimeFormat'] = utils.dateTimeFormat
templates.filters['isoDuration'] = utils.toIsoDuration
templates.filters['isoDateTime'] = utils.toIsoDateTime
templates.filters['sizeFormat'] = utils.sizeFormat
templates.filters['toHtmlString'] = utils.toHtmlString
templates.filters['toJson'] = utils.toJson
templates.filters['uuid'] = utils.toUuid
templates.filters['xmlSafe'] = utils.xmlSafe
templates.filters['default'] = utils.default

legacy_manifest_names = {
    'enc.mpd': 'hand_made.mpd',
    'manifest_vod.mpd': 'hand_made.mpd',
}

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
    CSRF_EXPIRY=1200
    CSRF_KEY_LENGTH=32
    CSRF_SALT_LENGTH=8
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

    def generate_csrf_cookie(self):
        """generate a secure cookie if not already present"""
        sc = securecookie.SecureCookieSerializer(settings.cookie_secret)
        try:
            cookie = self.request.cookies[self.CSRF_COOKIE_NAME]
            csrf_key = sc.deserialize(self.CSRF_COOKIE_NAME, cookie)
        except KeyError:
            csrf_key = None
        if csrf_key is None:
            csrf_key = security.generate_random_string(length=self.CSRF_KEY_LENGTH)
            cookie = sc.serialize(self.CSRF_COOKIE_NAME, csrf_key)
            self.response.set_cookie(self.CSRF_COOKIE_NAME, cookie, httponly=True,
                                     max_age=self.CSRF_EXPIRY)
        return csrf_key

    def generate_csrf_token(self, service, csrf_key):
        """generate a CSRF token that can be used as a hidden form field"""
        logging.debug('generate_csrf URI: {}'.format(self.request.uri))
        logging.debug('generate_csrf User-Agent: {}'.format(self.request.headers['User-Agent']))
        sig = hmac.new(settings.csrf_secret, csrf_key, hashlib.sha1)
        cur_url = urlparse.urlparse(self.request.uri, 'http')
        salt = security.generate_random_string(length=self.CSRF_SALT_LENGTH)
        origin = '%s://%s'%(cur_url.scheme, cur_url.netloc)
        logging.debug('generate_csrf origin: {}'.format(origin))
        #print('generate', service, csrf_key, origin, self.request.headers['User-Agent'], salt)
        sig.update(service)
        sig.update(origin)
        #sig.update(self.request.uri)
        sig.update(self.request.headers['User-Agent'])
        sig.update(salt)
        sig = sig.digest()
        rv =  urllib.quote(salt + base64.b64encode(sig))
        #print('csrf', service, rv)
        return rv

    def check_csrf(self, service):
        """check that the CSRF token from the cookie and the submitted form match"""
        sc = securecookie.SecureCookieSerializer(settings.cookie_secret)
        try:
            cookie = self.request.cookies[self.CSRF_COOKIE_NAME]
        except KeyError:
            logging.debug("csrf cookie not present")
            logging.debug(str(self.request.cookies))
            raise CsrfFailureException("{} cookie not present".format(self.CSRF_COOKIE_NAME))
        csrf_key = sc.deserialize(self.CSRF_COOKIE_NAME, cookie)
        if not csrf_key:
            logging.debug("csrf deserialize failed")
            self.response.delete_cookie(self.CSRF_COOKIE_NAME)
            raise CsrfFailureException("csrf cookie not valid")
        try:
            token = str(urllib.unquote(self.request.params['csrf_token']))
        except KeyError:
            raise CsrfFailureException("csrf_token not present")
        try:
            origin = self.request.headers['Origin']
        except KeyError:
            logging.debug("No origin in request, using: {}".format(self.request.uri))
            cur_url = urlparse.urlparse(self.request.uri, 'http')
            origin = '%s://%s'%(cur_url.scheme, cur_url.netloc)
        logging.debug("check_csrf origin: {}".format(origin))
        #print("check_csrf origin: {}".format(origin))
        if not memcache.add(key=token, value=origin, time=self.CSRF_EXPIRY, namespace=service):
            raise CsrfFailureException("Re-use of csrf_token")
        salt = token[:self.CSRF_SALT_LENGTH]
        token = token[self.CSRF_SALT_LENGTH:]
        #print('check', service, csrf_key, origin, self.request.headers['User-Agent'], salt, token)
        sig = hmac.new(settings.csrf_secret, csrf_key, hashlib.sha1)
        sig.update(service)
        sig.update(origin)
        #logging.debug("check_csrf Referer: {}".format(self.request.headers['Referer']))
        #sig.update(self.request.headers['Referer'])
        sig.update(self.request.headers['User-Agent'])
        sig.update(salt)
        sig_hex = sig.hexdigest()
        tk_hex = binascii.b2a_hex(base64.b64decode(token))
        #print(sig_hex, tk_hex)
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

    def generate_drm_dict(self, stream):
        if isinstance(stream, basestring):
            stream = models.Stream.query(models.Stream.prefix==stream).get()
        marlin_la_url = None
        playready_la_url = None
        if stream is not None:
            marlin_la_url = stream.marlin_la_url
            playready_la_url = stream.playready_la_url
        mspr = drm.PlayReady(templates, la_url=playready_la_url)
        ck = drm.ClearKey(templates)
        rv = {
            'playready': {
                'laurl': playready_la_url,
                'pro': mspr.generate_pro,
                'cenc': mspr.generate_pssh,
                'moov': mspr.generate_pssh,
            },
            'marlin': {
                "MarlinContentIds": True,
                'laurl': marlin_la_url,
            },
            'clearkey': {
                'laurl': self.generate_clearkey_license_url(),
                'cenc': ck.generate_pssh,
                'moov': ck.generate_pssh,
            }
        }
        drms = self.request.params.get('drm')
        if drms is None or drms == 'all':
            return rv
        d = {}
        for name in drms.split(','):
            try:
                if '-' in name:
                    parts = name.split('-')
                    name = parts[0]
                    d[name] = {}
                    try:
                        d[name]['laurl'] = rv[name]['laurl']
                    except KeyError:
                        pass
                    for p in parts[1:]:
                        d[name][p] = rv[name][p]
                else:
                    d[name] = rv[name]
            except KeyError:
                pass
        return d

    def generateSegmentList(self, representation):
        #TODO: support live profile
        rv = ['<SegmentList timescale="%d" duration="%d">'%(representation.timescale,representation.mediaDuration)]
        first=True
        for seg in representation.segments:
            if first:
                rv.append('<Initialization range="{start:d}-{end:d}"/>'.format(start=seg.pos, end=seg.pos+seg.size-1))
                first=False
            else:
                rv.append('<SegmentURL mediaRange="{start:d}-{end:d}"/>'.format(start=seg.pos,end=seg.pos+seg.size-1))
        rv.append('</SegmentList>')
        return '\n'.join(rv)

    def generateSegmentDurations(self, representation):
        #TODO: support live profile
        def output_s_node(sn):
            if sn["duration"] is None:
                return
            c = ' r="{:d}"'.format(sn["count"]-1) if sn["count"]>1 else ''
            rv.append('<S {} d="{:d}"/>'.format(c, sn["duration"]))
        rv = ['<SegmentDurations timescale="%d">'%(representation.timescale)]
        s_node = {
            "duration": None,
            "count": 0,
        }
        for seg in representation.segments:
            try:
                if seg.duration != s_node["duration"]:
                    output_s_node(s_node)
                    s_node["count"] = 0
                s_node["duration"] = seg.duration
                s_node["count"] += 1
            except AttributeError:
                # init segment does not have a duration
                pass
        output_s_node(s_node)
        rv.append('</SegmentDurations>')
        return '\n'.join(rv)

    def generateSegmentTimeline(self, context, representation):
        def output_s_node(sn):
            if sn["duration"] is None:
                return
            r = ' r="{0:d}"'.format(sn["count"]-1) if sn["count"]>1 else ''
            t = ' t="{0:d}"'.format(sn["start"]) if sn["start"] is not None else ''
            rv.append('<S {r} {t} d="{d:d}"/>'.format(r=r, t=t, d=sn["duration"]))
        
        rv = []
        timeline_start = context["elapsedTime"] - datetime.timedelta(seconds=context["timeShiftBufferDepth"])
        first=True
        segment_num, origin_time = self.calculate_segment_from_timecode(utils.scale_timedelta(timeline_start,1,1), representation, context["ref_representation"])
        assert representation.num_segments == (len(representation.segments)-1)
        assert segment_num < len(representation.segments)
        # seg_start_time is the time (in representation timescale units) when the segment_num
        # segment started, relative to availabilityStartTime
        seg_start_time = long(origin_time * representation.timescale + (segment_num-1) * representation.segment_duration)
        dur=0
        s_node = {
            'duration': None,
            'count': 0,
            'start': None,
        }
        if context["mode"] == 'live':
            end = context["timeShiftBufferDepth"] * representation.timescale
        else:
            end = context["mediaDuration"] * representation.timescale
        while dur <= end:
            seg = representation.segments[segment_num]
            if first:
                rv.append('<SegmentTimeline>')
                s_node['start'] = seg_start_time
                first=False
            elif seg.duration != s_node["duration"]:
                output_s_node(s_node)
                s_node["start"] = None
                s_node["count"] = 0
            s_node["duration"] = seg.duration
            s_node["count"] += 1
            dur += seg.duration
            segment_num += 1
            if segment_num > representation.num_segments:
                segment_num = 1
        output_s_node(s_node)
        rv.append('</SegmentTimeline>')
        return '\n'.join(rv)

    def calculate_dash_params(self, stream, mode, **kwargs):
        st = models.Stream.query(models.Stream.prefix==stream).get()
        if st is None:
            raise ValueError("Invalid stream prefix {0}".format(stream))
        stream = st
        mpd_url = kwargs.get("mpd_url")
        if mpd_url is None:
            mpd_url = self.request.uri
            for k, v in legacy_manifest_names.iteritems():
                if v in mpd_url:
                    mpd_url = mpd_url.replace(k,v)
                    break
        if mpd_url is None:
            raise ValueError("Unable to determin MPD URL")
        encrypted = self.request.params.get('drm','none').lower() != 'none'
        now = datetime.datetime.now(tz=utils.UTC())
        clockDrift=0
        try:
            clockDrift = int(self.request.params.get('drift','0'),10)
            if clockDrift:
                now -= datetime.timedelta(seconds=clockDrift)
        except ValueError:
            pass
        timeShiftBufferDepth=0
        if mode=='live':
            try:
                timeShiftBufferDepth = int(self.request.params.get('depth',str(self.DEFAULT_TIMESHIFT_BUFFER_DEPTH)),10)
            except ValueError:
                timeShiftBufferDepth = self.DEFAULT_TIMESHIFT_BUFFER_DEPTH # in seconds
        rv = {
            "DRM": {},
            "clockDrift": clockDrift,
            "encrypted": encrypted,
            "generateSegmentList": self.generateSegmentList,
            "generateSegmentDurations": self.generateSegmentDurations,
            "generateSegmentTimeline": lambda r: self.generateSegmentTimeline(rv, r),
            "mode": mode,
            "mpd_url": mpd_url,
            "now": now,
            "publishTime": now.replace(microsecond=0),
            "startNumber": 1,
            "stream": stream,
            "suggestedPresentationDelay": 30,
            "timeShiftBufferDepth": timeShiftBufferDepth,
        }
        elapsedTime = datetime.timedelta(seconds=0)
        if mode=='live':
            startParam = self.request.params.get('start', 'today')
            if startParam == 'today':
                availabilityStartTime = now.replace(hour=0, minute=0, second=0, microsecond=0)
                if now.hour == 0 and now.minute == 0:
                    availabilityStartTime -= datetime.timedelta(days=1)
            elif startParam == 'now':
                availabilityStartTime = rv["publishTime"] - \
                    datetime.timedelta(seconds=self.DEFAULT_TIMESHIFT_BUFFER_DEPTH)
            elif startParam == 'epoch':
                availabilityStartTime = datetime.datetime(1970, 1, 1, 0, 0, tzinfo=utils.UTC())
            else:
                try:
                    availabilityStartTime = utils.from_isodatetime(startParam)
                except ValueError:
                    availabilityStartTime = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elapsedTime = now - availabilityStartTime
            if elapsedTime.total_seconds() < rv["timeShiftBufferDepth"]:
                timeShiftBufferDepth = rv["timeShiftBufferDepth"] = elapsedTime.total_seconds()
        else:
            availabilityStartTime = now
        rv["availabilityStartTime"] = availabilityStartTime
        rv["elapsedTime"] = elapsedTime
        if mode=='odvod':
            rv["baseURL"] = urlparse.urljoin(self.request.host_url, '/dash/vod')+'/'
        else:
            rv["baseURL"] = urlparse.urljoin(self.request.host_url,'/dash/'+mode)+'/'
        if self.is_https_request():
            rv["baseURL"] = rv["baseURL"].replace('http://','https://')
        video = { 
            'representations' : [],
            'initURL': '$RepresentationID$/init.m4v',
            'mediaURL':'$RepresentationID$/$Number$.m4v',
        }
        audio = {
            'representations': [],
            'initURL': '$RepresentationID$/init.m4a',
            'mediaURL':'$RepresentationID$/$Number$.m4a'
        }
        if mode=='odvod':
            del video['initURL']
            video['mediaURL'] = '$RepresentationID$.m4v'
            del audio['initURL']
            audio['mediaURL'] = '$RepresentationID$.m4a'
        acodec = self.request.params.get('acodec')
        media_files = models.MediaFile.all()
        for mf in media_files:
            r = mf.representation
            if r is None:
                continue
            if r.contentType=="video" and r.encrypted==encrypted and \
               r.filename.startswith(stream.prefix):
                video['representations'].append(r)
            elif r.contentType=="audio" and r.encrypted==encrypted and \
                 r.filename.startswith(stream.prefix):
                if acodec is None or r.codecs.startswith(acodec):
                    audio['representations'].append(r)
        # if stream is encrypted but there is no encrypted version of the audio track, fall back
        # to a clear version
        if not audio['representations'] and acodec:
            for mf in media_files:
                r = mf.representation
                if r is None:
                    continue
                if r.contentType=="audio" and r.filename.startswith(stream.prefix) and r.codecs.startswith(acodec):
                    audio['representations'].append(r)
        if mode=='vod' or mode=='odvod':
            if video['representations']:
                elapsedTime = datetime.timedelta(seconds = video['representations'][0].mediaDuration / video['representations'][0].timescale)
            elif audio['representations']:
                elapsedTime = datetime.timedelta(seconds = audio['representations'][0].mediaDuration / audio['representations'][0].timescale)
            timeShiftBufferDepth = elapsedTime.seconds
        if video['representations']:
            self.compute_av_values(video, rv["startNumber"])
            video['minWidth'] = min([ a.width for a in video['representations']])
            video['minHeight'] = min([ a.height for a in video['representations']])
            video['maxWidth'] = max([ a.width for a in video['representations']])
            video['maxHeight'] = max([ a.height for a in video['representations']])
            video['maxFrameRate'] = max([ a.frameRate for a in video['representations']])
        rv["video"] = video

        if len(audio['representations'])==1:
            audio['representations'][0].role='main'
        else:
            for rep in audio['representations']:
                if rep.codecs.startswith(self.request.params.get('main_audio','mp4a')):
                    rep.role='main'
                else:
                    rep.role='alternate'
        if audio['representations']:
            self.compute_av_values(audio, rv["startNumber"])
        rv["audio"] = audio

        ref_representation=None
        kids = set()
        for rep in video['representations']+audio['representations']:
            if rep.encrypted:
                kids.update(rep.kids)
        rv["kids"] = kids
        if video['representations']:
            rv["ref_representation"] = video['representations'][0]
        else:
            rv["ref_representation"] = audio['representations'][0]
        rv["mediaDuration"] = rv["ref_representation"].mediaDuration / rv["ref_representation"].timescale
        rv["maxSegmentDuration"] = max(video.get('maxSegmentDuration', 0),
                                       audio.get('maxSegmentDuration', 0))
        if encrypted:
            rv["DRM"] = self.generate_drm_dict(stream)
            if not kids:
                rv["keys"] = models.Key.all_as_dict()
            else:
                rv["keys"] = models.Key.get_kids(kids)
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
            timeSource['url']= urlparse.urljoin(self.request.host_url,
                                                self.uri_for('time',format=timeSource['format']))
        rv["timeSource"] = timeSource
        v_cgi_params = []
        a_cgi_params = []
        m_cgi_params = copy.deepcopy(dict(self.request.params))
        if self.request.params.get('drm', 'none') != 'none':
            v_cgi_params.append('drm={}'.format(self.request.params.get('drm')))
            a_cgi_params.append('drm={}'.format(self.request.params.get('drm')))
        if self.request.params.get('start'):
            v_cgi_params.append('start=%s'%utils.toIsoDateTime(availabilityStartTime))
            a_cgi_params.append('start=%s'%utils.toIsoDateTime(availabilityStartTime))
            m_cgi_params['start'] = utils.toIsoDateTime(availabilityStartTime)
        if clockDrift:
            rv["timeSource"]['url'] += '?drift=%d'%clockDrift
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
            if self.request.params.get('a%03d'%code) is not None:
                times = self.calculate_injected_error_segments(self.request.params.get('a%03d'%code), \
                                                               now, availabilityStartTime, \
                                                               timeShiftBufferDepth, \
                                                               audio['representations'][0])
                if times:
                    a_cgi_params.append('%03d=%s'%(code,times))
        if self.request.params.get('vcorrupt') is not None:
            segs = self.calculate_injected_error_segments(self.request.params.get('vcorrupt'), \
                                                          now, availabilityStartTime, \
                                                          timeShiftBufferDepth, \
                                                          video['representations'][0])
            if segs:
                v_cgi_params.append('corrupt=%s'%(segs))
        try:
            updateCount = int(self.request.params.get('update','0'),10)
            m_cgi_params['update']=str(updateCount+1)
        except ValueError:
            pass
        if v_cgi_params:
            rv["video"]['mediaURL'] += '?' + '&'.join(v_cgi_params)
            if mode != 'odvod':
                rv["video"]['initURL'] += '?' + '&'.join(v_cgi_params)
        if a_cgi_params:
            rv["audio"]['mediaURL'] += '?' + '&'.join(a_cgi_params)
            if mode != 'odvod':
                rv["audio"]['initURL'] += '?' + '&'.join(a_cgi_params)
        if m_cgi_params:
            lst = []
            for k,v in m_cgi_params.iteritems():
                lst.append('%s=%s'%(k,v))
            locationURL = self.request.uri
            if '?' in locationURL:
                locationURL = locationURL[:self.request.uri.index('?')]
            locationURL = locationURL + '?' + '&'.join(lst)
            rv["locationURL"] = locationURL
        return rv

    def add_allowed_origins(self):
        try:
            if self.ALLOWED_DOMAINS.search(self.request.headers['Origin']):
                self.response.headers.add_header("Access-Control-Allow-Origin", self.request.headers['Origin'])
                self.response.headers.add_header("Access-Control-Allow-Methods", "HEAD, GET, POST")
        except KeyError:
            pass

    def calculate_segment_from_timecode(self, timecode, representation, ref_representation):
        """find the correct segment for the given timecode.

        :param timecode: the time (in seconds) since availabilityStartTime
            for the requested fragment.
        :param representation: the Representation to use
        :param ref_representation: the Representation that is used as a stream's reference
        returns the segment number and the time when the stream last looped
        """
        if timecode < 0:
            raise ValueError("Invalid timecode: %d"%timecode)
        # nominal_duration is the duration (in timescale units) of the reference
        # representation. This is used to decide how many times the stream has looped
        # since availabilityStartTime.
        nominal_duration = ref_representation.segment_duration * \
                           ref_representation.num_segments
        tc_scaled = long(timecode * ref_representation.timescale)
        num_loops = tc_scaled / nominal_duration

        # origin time is the time (in timescale units) that maps to segment 1 for
        # all adaptation sets. It represents the most recent time of day when the
        # content started from the beginning, relative to availabilityStartTime
        origin_time = num_loops * nominal_duration

        # the difference between timecode and origin_time now needs
        # to be mapped to the segment index of this representation
        segment_num = (tc_scaled - origin_time) * representation.timescale
        segment_num /= ref_representation.timescale
        segment_num /= representation.segment_duration
        segment_num += 1
        # the difference between the segment durations of the reference
        # representation and this representation can mean that this representation
        # has already looped
        if segment_num > representation.num_segments:
            segment_num = 1
            origin_time += nominal_duration
        origin_time /= ref_representation.timescale
        if segment_num<1 or segment_num>representation.num_segments:
            raise ValueError('Invalid segment number %d'%(segment_num))
        return (segment_num, origin_time)

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
        context["headers"]=[]
        context['routes'] = routes
        context['video_fields'] = [ 'id', 'codecs', 'bitrate', 'width', 'height', 'encrypted' ]
        context['video_representations'] = []
        context['audio_representations'] = []
        for mf in models.MediaFile.all():
            r = mf.representation
            if r is None:
                continue
            if r.contentType=="video":
                context['video_representations'].append(r)
            elif r.contentType=="audio":
                context['audio_representations'].append(r)
        context['video_representations'].sort(key=lambda r: r.filename)
        context['audio_representations'].sort(key=lambda r: r.filename)
        context['audio_fields'] = [ 'id', 'codecs', 'bitrate', 'sampleRate', 'numChannels', 'language', 'encrypted' ]
        context['streams'] = models.Stream.all()
        context['keys'] = models.Key.all_as_dict()
        context['rows'] = []
        filenames = manifests.manifest.keys()
        filenames.sort(key=lambda name: manifests.manifest[name]['title'])
        for name in filenames:
            url = self.uri_for('dash-mpd-v3', manifest=name, stream='placeholder', mode='live')
            url = url.replace('/placeholder/','/{directory}/')
            url = url.replace('/live/','/{mode}/')
            context['rows'].append({
                'filename': name,
                'url': url,
                'manifest': manifests.manifest[name],
                'option': [],
            })
        for idx, opt in enumerate(options.options):
            try:
                row = context['rows'][idx]
                row['option'] = opt
            except IndexError:
                row = {
                    'manifest': { 'title':None },
                    'option': opt
                }
                context['rows'].append(row)
        template = templates.get_template('index.html')
        self.response.write(template.render(context))

class ServeManifest(RequestHandler):
    """handler for generating MPD files"""
    def head(self, mode, stream, manifest, **kwargs):
        self.get(mode, stream, manifest, **kwargs)

    def get(self, mode, stream, manifest, **kwargs):
        if manifest in legacy_manifest_names:
            manifest = legacy_manifest_names[manifest]
        if not manifests.manifest.has_key(manifest):
            logging.debug('Unknown manifest: %s', manifest)
            self.response.write('%s not found'%(manifest))
            self.response.set_status(404)
            return
        if mode not in manifests.manifest[manifest]['modes']:
            logging.debug('Mode %s not supported with manifest %s', mode, manifest)
            self.response.write('%s not found'%(manifest))
            self.response.set_status(404)
            return
        context = self.create_context(**kwargs)
        context["headers"]=[]
        context['routes'] = routes
        self.response.content_type='application/dash+xml'
        context['title'] = 'Big Buck Bunny DASH test stream'
        try:
            dash = self.calculate_dash_params(mpd_url=manifest, stream=stream, mode=mode, **kwargs)
        except ValueError, e:
            self.response.write('Invalid CGI parameters: %s'%(str(e)))
            self.response.set_status(400)
            return
        context.update(dash)
        context['abr'] = self.request.params.get('abr', "True")
        context['abr'] = re.search(r'(True|0)', context['abr'], re.I)
        #context['availabilityStartTime'] = datetime.datetime.utcfromtimestamp(dash['availabilityStartTime'])
        if re.search(r'(True|0)',self.request.params.get('base','False'),re.I) is not None:
            del context['baseURL']
            if mode == 'odvod':
                prefix = self.uri_for('dash-od-media', filename='RepresentationID', ext='m4v')
                prefix = prefix.replace('RepresentationID.m4v','')
            else:
                prefix = self.uri_for('dash-media', mode=mode, filename='RepresentationID',
                                      segment_num='init', ext='m4v')
                prefix = prefix.replace('RepresentationID/init.m4v','')
                context['video']['initURL'] = prefix + context['video']['initURL']
                context['audio']['initURL'] = prefix + context['audio']['initURL']
            context['video']['mediaURL'] = prefix + context['video']['mediaURL']
            context['audio']['mediaURL'] = prefix + context['audio']['mediaURL']
        if context['abr'] is False:
            context['video']['representations'] = context['video']['representations'][-1:]
        if mode == 'live':
            try:
                context['minimumUpdatePeriod'] = float(self.request.params.get('mup', 2.0 * context['video'].get('maxSegmentDuration', 1)))
            except ValueError:
                context['minimumUpdatePeriod'] = 2.0* context['video'].get('maxSegmentDuration', 1)
            if context['minimumUpdatePeriod'] <= 0:
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


class LegacyManifestUrl(ServeManifest):
    def head(self, manifest, **kwargs):
        stream = kwargs.get("stream", "bbb")
        mode = self.request.params.get("mode", "live")
        return super(LegacyManifestUrl, self).head(mode=mode, stream=stream,
                                                   manifest=manifest, **kwargs)

    def get(self, manifest, **kwargs):
        try:
            stream = kwargs["stream"]
            del kwargs["stream"]
        except KeyError:
            stream = "bbb"
        mode = self.request.params.get("mode", "live")
        return super(LegacyManifestUrl, self).get(mode=mode, stream=stream,
                                                  manifest=manifest, **kwargs)


class OnDemandMedia(RequestHandler): #blobstore_handlers.BlobstoreDownloadHandler):
    """Handler that returns media fragments for the on-demand profile"""
    def get(self, filename, ext):
        name = filename+'.mp4'
        name = name.lower()
        mf = models.MediaFile.query(models.MediaFile.name==name).get()
        if mf is None:
            self.response.write('%s not found'%(name))
            self.response.set_status(404)
            return
        stream = filename.split('_')[0]
        try:
            dash = self.calculate_dash_params(mode='odvod', stream=stream)
        except ValueError, e:
            self.response.write('Invalid CGI parameters: %s'%(str(e)))
            self.response.set_status(400)
            return
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
        name = filename.lower()+'.mp4'
        mf = models.MediaFile.query(models.MediaFile.name==name).get()
        if mf is None:
            self.response.write('%s not found'%filename)
            self.response.set_status(404)
            return
        stream = filename.split('_')[0]
        try:
            dash = self.calculate_dash_params(mode=mode, stream=stream)
        except ValueError, e:
            self.response.write('Invalid CGI parameters: %s'%(str(e)))
            self.response.set_status(400)
            return
        representation = mf.representation
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
                lastFragment = dash['startNumber'] + int(utils.scale_timedelta(dash['elapsedTime'], representation.timescale, representation.segment_duration))
                firstFragment = lastFragment - int(representation.timescale*dash['timeShiftBufferDepth'] / representation.segment_duration) - 1
                firstFragment = max(dash['startNumber'], firstFragment)
            else:
                firstFragment = dash['startNumber']
                lastFragment = firstFragment + representation.num_segments - 1
            if segment_num<firstFragment or segment_num>lastFragment:
                self.response.write('Segment %d not found (valid range= %d->%d)'%(segment_num,firstFragment,lastFragment))
                self.response.set_status(404)
                return
            if dash['mode']=='live':
                # elapsed_time is the time (in seconds) since availabilityStartTime
                # for the requested fragment
                ref = dash["ref_representation"]
                #elapsed_time = (segment_num - dash['startNumber']) * representation.segment_duration / float(representation.timescale)
                elapsed_time = (segment_num - dash['startNumber']) * ref.segment_duration / float(ref.timescale)
                try:
                    mod_segment, origin_time = self.calculate_segment_from_timecode(elapsed_time,
                                                                  representation,
                                                                  dash['ref_representation'])
                except ValueError:
                    raise
                    self.response.write('Segment %d not found (valid range= %d->%d)'%(segment_num,firstFragment,lastFragment))
                    self.response.set_status(404)
                    return
            else:
                mod_segment = 1 + segment_num - dash['startNumber']
        #blob_info = blobstore.BlobInfo.get(mf.blob)
        if ext=='m4a':
            self.response.content_type='audio/mp4'
        elif ext=='m4v':
            self.response.content_type='video/mp4'
        else:
            self.response.content_type='application/mp4'
        assert mod_segment>=0 and mod_segment<=representation.num_segments
        frag = representation.segments[mod_segment]
        blob_reader = blobstore.BlobReader(mf.blob, position=frag.pos, buffer_size=16384)
        src = utils.BufferedReader(blob_reader, offset=frag.pos, size=frag.size, buffersize=16384)
        options = mp4.Options(cache_encoded=True)
        if representation.encrypted:
            options.iv_size = representation.iv_size
        atom = mp4.Wrapper(atom_type='wrap', children=mp4.Mp4Atom.create(src, options=options))
        if self.request.params.get('corrupt') is not None:
            atom.moof.traf.trun.parse_samples(src, representation.nalLengthFieldFength)
        if segment_num==0 and representation.encrypted:
            keys = models.Key.get_kids(representation.kids)
            drms = self.generate_drm_dict(stream)
            for drm in drms.values():
                try:
                    pssh = drm["moov"](representation, keys)
                    atom.moov.append_child(pssh)
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
                delta = long(origin_time*representation.timescale)
                if delta < 0L:
                    raise IOError("Failure in calculating delta %s %d %d %d"%(str(delta),segment_num,mod_segment,dash['startNumber']))
                atom.moof.traf.tfdt.base_media_decode_time += delta

                # Update the sequenceNumber field in the MovieFragmentHeader box
                atom.moof.mfhd.sequence_number = segment_num
            try:
                # remove any sidx box as it has a baseMediaDecodeTime and it's an optional index
                del atom.sidx
            except AttributeError:
                pass
        self.add_allowed_origins()
        data = io.BytesIO()
        atom.encode(data)
        if self.request.params.get('corrupt') is not None:
            try:
                self.apply_corruption(representation, segment_num, atom, data)
            except ValueError, e:
                self.response.write('Invalid CGI parameter %s: %s'%(self.request.params.get('corrupt'),str(e)))
                self.response.set_status(400)
                return
        data = data.getvalue()[8:] # [8:] is to skip the fake "wrap" box
        try:
            start,end = self.get_http_range(frag.size)
            if start is not None:
                data = data[start:end+1]
        except (ValueError) as ve:
            self.response.write(str(ve))
            self.response.set_status(400)
            return
        self.response.headers.add_header('Accept-Ranges','bytes')
        self.response.out.write(data)

    def apply_corruption(self, representation, segment_num, atom, dest):
        try:
            corrupt_frames = int(self.request.params.get('frames','4'),10)
        except ValueError:
            corrupt_frames = 4
        for d in self.request.params.get('corrupt').split(','):
            try:
                d = int(d, 10)
            except ValueError:
                continue
            if d != segment_num:
                continue
            for sample in atom.moof.traf.trun.samples:
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
                            dest.seek(offset)
                            dest.write(junk_count*junk)
                            corrupt_frames -= 1
                            if corrupt_frames<=0:
                                break


class VideoPlayer(RequestHandler):
    """Responds with an HTML page that contains a video element to play the specified MPD"""
    def get(self, **kwargs):
        def gen_errors(cgiparam):
            err_time = context['now'].replace(microsecond=0) + datetime.timedelta(seconds=20)
            times=[]
            for i in range(12):
                err_time += datetime.timedelta(seconds=10)
                times.append(err_time.time().isoformat()+'Z')
            params.append('%s=%s'%(cgiparam,urllib.quote_plus(','.join(times))))
        context = self.create_context(**kwargs)
        try:
            filename = self.request.params["mpd"]
        except KeyError:
            self.response.write('Missing CGI parameter: mpd')
            self.response.set_status(400)
            return
        stream=''
        if '/' in filename:
            stream, filename = filename.split('/')
            stream = stream.lower()
        mode = self.request.params.get("mode", "live")
        context['dash'] = self.calculate_dash_params(mpd_url=filename, mode=mode, stream=stream)
        for idx in range(len(context['dash']['video']['representations'])):
            context['dash']['video']['representations'][idx] = context['dash']['video']['representations'][idx].toJSON()
            del context['dash']['video']['representations'][idx]["segments"]
        for idx in range(len(context['dash']['audio']['representations'])):
            context['dash']['audio']['representations'][idx] = context['dash']['audio']['representations'][idx].toJSON()
            del context['dash']['audio']['representations'][idx]["segments"]
        del context['dash']['ref_representation']
        if context['dash']['encrypted']:
            keys = context['dash']['keys']
            for kid in keys.keys():
                item = keys[kid].toJSON()
                item['guidKid'] = drm.PlayReady.hex_to_le_guid(keys[kid].hkid, raw=False)
                item['b64Key'] = keys[kid].KEY.b64
                keys[kid] = item
        params=[]
        for k,v in self.request.params.iteritems():
            if k in ['mpd', 'mse']:
                continue
            if isinstance(v,(int,long)):
                params.append('%s=%d'%(k,v))
            else:
                params.append('%s=%s'%(k,urllib.quote_plus(v)))
        if self.request.params.get('corruption',False)==True:
            gen_errors('vcorrupt')
        for code in self.INJECTED_ERROR_CODES:
            p = 'v%03d'%code
            if self.request.params.get(p,False)==True:
                gen_errors(p)
            p = 'a%03d'%code
            if self.request.params.get(p,False)==True:
                gen_errors(p)
        if stream:
            mpd_url = self.uri_for('dash-mpd-v2', stream=stream, manifest=filename)
        else:
            mpd_url = self.uri_for('dash-mpd-v2', stream="bbb", manifest=filename)
        if params:
            mpd_url += '?' + '&'.join(params)
        context['source'] = urlparse.urljoin(self.request.host_url, mpd_url)
        context['drm'] = self.request.get("drm", "none")
        if self.is_https_request():
            context['source'] = context['source'].replace('http://','https://')
        else:
            if "marlin" in context["drm"] and context['dash']['DRM']['marlin']['laurl']:
                context['source'] = '#'.join([
                    context['dash']['DRM']['marlin']['laurl'],
                    context['source']
                ])
        context['mimeType'] = 'application/dash+xml'
        context['title'] = manifests.manifest[filename]['title']
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
            is_ajax = self.request.get("ajax", "0") == "1"
            upload_files = self.get_uploads()
            logging.debug("uploaded file count: %d"%len(upload_files))
            if not users.is_current_user_admin():
                self.response.write('User is not an administrator')
                self.response.set_status(401)
                return
            result = {"error":"Unknown"}
            if is_ajax:
                self.response.content_type='application/json'
            if len(upload_files)==0:
                if is_ajax:
                    result["error"] = "No files uploaded"
                    self.response.write(json.dumps(result))
                    return 
                self.outer.get()
                return
            blob_info = upload_files[0]
            #infos = self.get_file_infos()[0]
            logging.debug("Filename: "+blob_info.filename)
            result["filename"] = blob_info.filename
            media_id, ext = os.path.splitext(blob_info.filename)
            try:
                self.outer.check_csrf('upload')
            except (CsrfFailureException) as cfe:
                logging.debug("csrf check failed")
                logging.debug(cfe)
                if is_ajax:
                    result["error"] = '{}: {:s}'.format(cfe.__class__.__name__, cfe)
                    self.response.write(json.dumps(result))
                self.response.set_status(401)
                blob_info.delete()
                return
            try:
                context = self.outer.create_context(title='File %s uploaded'%(blob_info.filename),
                                                    blob=blob_info.key())
                mf = models.MediaFile.query(models.MediaFile.name==blob_info.filename).get()
                if mf:
                    mf.delete()
                mf = models.MediaFile(name=blob_info.filename, blob=blob_info.key())
                mf.put()
                context["mfid"] = mf.key.urlsafe()
                result = mf.toJSON()
                logging.debug("upload done "+context["mfid"])
                if is_ajax:
                    csrf_key = self.outer.generate_csrf_cookie()
                    result['upload_url'] = blobstore.create_upload_url(self.outer.uri_for('uploadBlob'))
                    result['csrf'] = self.outer.generate_csrf_token("upload", csrf_key)
                    template = templates.get_template('media_row.html')
                    context["media"] = mf
                    result["file_html"] = template.render(context)
                    self.response.write(json.dumps(result))
                else:
                    template = templates.get_template('upload-done.html')
                    self.response.write(template.render(context))
                return
            except (KeyError) as e:
                if is_ajax:
                    result["error"] = '{:s} not found: {:s}'.format(media_id,e)
                    self.response.write(json.dumps(result))
                else:
                    self.response.write('{:s} not found: {:s}'.format(media_id,e))
                self.response.set_status(404)
                blob_info.delete()

    #def __init__(self, request, response):
    def __init__(self, *args, **kwargs):
        super(MediaHandler, self).__init__(*args, **kwargs)
        #self.initialize(request, response)
        self.upload_handler = self.UploadHandler()
        self.upload_handler.initialize(self.request, self.response)
        self.upload_handler.outer = self
        self.post = self.upload_handler.post

    def get(self, **kwargs):
        if not users.is_current_user_admin():
            self.response.write('User is not an administrator')
            self.response.set_status(401)
            return
        context = self.create_context(**kwargs)
        if kwargs.has_key("mfid"):
            return self.media_info(**kwargs)
        context['upload_url'] = blobstore.create_upload_url(self.uri_for('uploadBlob'))
        if self.is_https_request():
            context['upload_url'] = context['upload_url'].replace('http://','https://')
        context['files'] = models.MediaFile.all()
        context['files'].sort(key=lambda i: i.name)
        context['keys'] = models.Key.all()
        context['keys'].sort(key=lambda i: i.hkid)
        context['streams'] = models.Stream.all()
        csrf_key = self.generate_csrf_cookie()
        context['csrf_tokens'] = {
            'files': self.generate_csrf_token('files', csrf_key),
            'kids': self.generate_csrf_token('keys', csrf_key),
            'streams': self.generate_csrf_token('streams', csrf_key),
            'upload': self.generate_csrf_token('upload', csrf_key),
        }
        context['drm'] = {
            'playready': {
                'laurl': drm.PlayReady.TEST_LA_URL
            },
            'marlin': {
                'laurl': ''
            }
        }
        is_ajax = self.request.get("ajax", "0") == "1"
        if is_ajax:
            result = {}
            for item in ['csrf_tokens', 'files', 'streams', 'keys', 'upload_url']:
                result[item] = context[item]
            result = utils.flatten(result)
            self.response.content_type='application/json'
            self.response.write(json.dumps(result))
        else:
            template = templates.get_template('media.html')
            self.response.write(template.render(context))

    def media_info(self, mfid, **kwargs):
        result= { "error": "unknown error" }
        try:
            mf = models.MediaFile.query(models.Key.key==Key(urlsafe=mfid)).get()
            if not mf:
                self.response.write('{} not found'.format(mfid))
                self.response.set_status(404)
                return
            bi = blobstore.BlobInfo.get(mf.blob)
            info = {
                'size': bi.size,
                'creation': utils.dateTimeFormat(bi.creation, "%H:%M:%S %d/%m/%Y"),
                'md5': bi.md5_hash,
            }
            result = {
                "representation": mf.rep,
                "name": mf.name,
                "key": mf.key.urlsafe(),
                "blob": info,
            }
            if self.request.params.get('index'):
                self.check_csrf('files')
                blob_reader = utils.BufferedReader(blobstore.BlobReader(mf.blob))
                atom = mp4.Wrapper(atom_type='wrap', position=0, size = mf.info.size, parent=None,
                                   children=mp4.Mp4Atom.create(blob_reader))
                rep = segment.Representation.create(filename=mf.name, atoms=atom.children)
                mf.representation = rep
                mf.put()
                result = {
                    "indexed":mfid,
                    "representation": mf.rep,
                }
        except (ValueError, CsrfFailureException) as err:
            result= { "error": str(err) }
        finally:
            csrf_key = self.generate_csrf_cookie()
            result["csrf"] = self.generate_csrf_token('files', csrf_key)
            self.response.content_type='application/json'
            self.response.write(json.dumps(result))
        
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
        result= { "error": "unknown error" }
        try:
            self.check_csrf('files')
            mf = models.MediaFile.query(models.Key.key==Key(urlsafe=mfid)).get()
            if not mf:
                self.response.write('{} not found'.format(mfid))
                self.response.set_status(404)
                return
            mf.delete()
            result = {"deleted":mfid}
        except (ValueError, CsrfFailureException) as err:
            result= { "error": str(err) }
        finally:
            csrf_key = self.generate_csrf_cookie()
            result["csrf"] = self.generate_csrf_token('files', csrf_key)
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
        result= { "error": "unknown error" }
        try:
            self.check_csrf('keys')
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
            result = {
                "key": key.hex,
                "kid": kid.hex,
                "computed": computed
            }
        except (ValueError, CsrfFailureException) as err:
            result= {
                "error": '{}: {:s}'.format(err.__class__.__name__, err)
            }
        finally:
            csrf_key = self.generate_csrf_cookie()
            result["csrf"] = self.generate_csrf_token('keys', csrf_key)
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
            self.check_csrf('keys')
            kid = models.KeyMaterial(hex=kid)
            keypair = models.Key.query(models.Key.hkid==kid.hex).get()
            if keypair:
                keypair.key.delete()
                result = {
                    "deleted": kid.hex,
                }
            else:
                result["error"] = 'KID {:s} not found'.format(kid)
        except (TypeError, ValueError, CsrfFailureException) as err:
            result= {
                "error": '{}: {:s}'.format(err.__class__.__name__, err)
            }
        finally:
            csrf_key = self.generate_csrf_cookie()
            result["csrf"] = self.generate_csrf_token('keys', csrf_key)
            self.response.content_type='application/json'
            self.response.write(json.dumps(result))

class StreamHandler(RequestHandler):
    FIELDS=['title', 'prefix', 'marlin_la_url', 'playready_la_url']

    """handler for adding or removing a stream"""
    def put(self, **kwargs):
        if not users.is_current_user_admin():
            self.response.write('User is not an administrator')
            self.response.set_status(401)
            return
        data = {}
        for f in self.FIELDS:
            data[f] = self.request.get(f)
            if data[f]=='':
                data[f] = None
        result= { "error": "unknown error" }
        try:
            self.check_csrf('streams')
            st = models.Stream.query(models.Stream.prefix==data['prefix']).get()
            if st:
                raise ValueError("Duplicate prefix {prefix}".format(**data))
            st = models.Stream(**data)
            st.put()
            result = {
                "id": st.key.urlsafe()
            }
            result.update(data)
        except (ValueError, CsrfFailureException) as err:
            result= {
                "error": '{}: {:s}'.format(err.__class__.__name__, err)
            }
        finally:
            csrf_key = self.generate_csrf_cookie()
            result["csrf"] = self.generate_csrf_token('streams', csrf_key)
            self.response.content_type='application/json'
            self.response.write(json.dumps(result))

    """handler for deleting a stream"""
    def delete(self, id, **kwargs):
        if not users.is_current_user_admin():
            self.response.write('User is not an administrator')
            self.response.set_status(401)
            return
        if not id:
            self.response.write('Stream ID missing')
            self.response.set_status(400)
            return
        result= { "error": "unknown error" }
        try:
            self.check_csrf('streams')
            key = Key(urlsafe=id)
            st = key.get()
            if not st:
                self.response.write('Stream {:s} not found'.format(id))
                self.response.set_status(404)
                return
            key.delete()
            result = {
                "deleted":id,
                "title":st.title,
                "prefix":st.prefix
            }
        except (TypeError, ValueError, CsrfFailureException) as err:
            result= {
                "error": '{}: {:s}'.format(err.__class__.__name__, err)
            }
        finally:
            csrf_key = self.generate_csrf_cookie()
            result["csrf"] = self.generate_csrf_token('streams', csrf_key)
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
        except (TypeError, ValueError, KeyError) as err:
            result= {
                "error": '{}: {:s}'.format(err.__class__.__name__, err)
            }
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

