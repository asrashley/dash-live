#!/usr/bin/env python
#
import binascii, copy, datetime, decimal, hashlib, hmac, logging, math, time, os, re, struct, sys, urllib, urlparse

import webapp2, jinja2
from google.appengine.api import users, memcache
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from webapp2_extras import securecookie
from webapp2_extras import security
from webapp2_extras.appengine.users import login_required, admin_required

from routes import routes
import media, utils, models, settings
from webob import exc

templates = jinja2.Environment(
                               loader=jinja2.FileSystemLoader(
                                                              os.path.join(os.path.dirname(__file__),'templates')
                                                              ),
                               extensions=['jinja2.ext.autoescape'])

templates.filters['isoDuration'] = utils.toIsoDuration
templates.filters['isoDateTime'] = utils.toIsoDateTime
templates.filters['toHtmlString'] = utils.toHtmlString
templates.filters['xmlSafe'] = utils.xmlSafe

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
            elapsedTime = now - availabilityStartTime
            if elapsedTime.seconds<timeShiftBufferDepth:
                timeShiftBufferDepth = elapsedTime.seconds
        else:
            availabilityStartTime = now
        request_uri=self.request.uri
        baseURL = urlparse.urljoin(self.request.host_url,'/dash/'+mode)+'/'
        video = { 'representations' : [ r for r in media.representations.values() if r.contentType=="video" and r.encrypted==encrypted],
                 'mediaURL':'$RepresentationID$/$Number$.m4v'
        }
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
        for rep in video['representations']+audio['representations']:
            dur = rep.media_duration / rep.timescale
            if shortest_representation is None or dur<media_duration:
                shortest_representation = rep
                media_duration = dur
        del dur
        maxSegmentDuration = max(video['maxSegmentDuration'],audio['maxSegmentDuration'])
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
        if clockDrift:
            timeSource['url'] += '?drift=%d'%clockDrift
            v_cgi_params.append('drift=%d'%clockDrift)
            a_cgi_params.append('drift=%d'%clockDrift)
        if mode=='live' and timeShiftBufferDepth != self.DEFAULT_TIMESHIFT_BUFFER_DEPTH:
            v_cgi_params.append('depth=%d'%timeShiftBufferDepth)
            a_cgi_params.append('depth=%d'%timeShiftBufferDepth)
        for code in self.INJECTED_ERROR_CODES:
            if self.request.params.get('v%03d'%code) is not None:
                v_cgi_params.append('%03d=%s'%(code,self.calculate_injected_error_segments(self.request.params.get('v%03d'%code), availabilityStartTime, video['representations'][0])))
            if self.request.params.get('a%03d'%code) is not None:
                a_cgi_params.append('%03d=%s'%(code,self.calculate_injected_error_segments(self.request.params.get('a%03d'%code), availabilityStartTime, audio['representations'][0])))
        if v_cgi_params:
            video['mediaURL'] += '?' + '&'.join(v_cgi_params)
        del v_cgi_params
        if a_cgi_params:
            audio['mediaURL'] += '?' + '&'.join(a_cgi_params)
        del a_cgi_params
        return locals()

    def add_allowed_origins(self):
        try:
            if self.ALLOWED_DOMAINS.search(self.request.headers['Origin']):
                self.response.headers.add_header("Access-Control-Allow-Origin", self.request.headers['Origin'])
                self.response.headers.add_header("Access-Control-Allow-Methods", "GET")
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

    def calculate_injected_error_segments(self, times, availabilityStartTime, representation):
        """Calculate a list of segment numbers for injecting errors

        :param times: a string of comma separated ISO8601 times
        :param availabilityStartTime: datetime.datetime containing availability start time
        :param representation: the Representation to use when calculating segment numbering
        """
        drops=[]
        for d in times.split(','):
            tm = utils.from_isodatetime(d)
            tm = availabilityStartTime.replace(hour=tm.hour, minute=tm.minute, second=tm.second)
            if tm < availabilityStartTime:
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

class MainPage(RequestHandler):
    """handler for main index page"""
    def get(self, **kwargs):
        context = self.create_context(**kwargs)
        try:
            context['page'] = int(self.request.params.get('page','1'),10)
        except ValueError:
            context['page'] = 1
        context['num_pages']=3
        context["headers"]=[]
        context['routes'] = routes
        context['video_fields'] = [ 'id', 'codecs', 'bitrate', 'height', 'width', 'encrypted' ]
        context['video_representations'] = [ r for r in media.representations.values() if r.contentType=="video"]
        # [ media.representations['V1'], media.representations['V2'], media.representations['V3'] ]
        context['audio_fields'] = [ 'id', 'codecs', 'bitrate', 'sampleRate', 'numChannels', 'language', 'encrypted' ]
        context['audio_representations'] = [ r for r in media.representations.values() if r.contentType=="audio"]
        #[ media.representations['A1'] ]
        context['rows'] = [
                           { 'title':'Hand-made on demand profile',
                            'details':['AAC audio'],
                            'buttons':[
                                                                               {
                                                                                'key':0,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_vod.mpd')+'?repr=V3&acodec=mp4a',
                                                                                'abr':False, 'BaseURL':True, 'static':True, 'encrypted':False
                                                                                },
                                                                               {
                                                                                'key':1,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_vod.mpd')+'?repr=V3&base=0&acodec=mp4a',
                                                                                'abr':False, 'BaseURL':False, 'static':True, 'encrypted':False
                                                                                },
                                                                               {
                                                                                'key':2,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_vod.mpd')+'?acodec=mp4a',
                                                                                'abr':True, 'BaseURL':True, 'static':True, 'encrypted':False
                                                                                }
                                                                               ]
                            },
                           { 'title':'Hand-made on demand profile',
                            'details':['E-AC3 audio'],
                            'buttons':[
                                                                               {
                                                                                'key':3,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_vod.mpd')+'?repr=V3&acodec=ec-3',
                                                                                'abr':False, 'BaseURL':True, 'static':True, 'encrypted':False
                                                                                },
                                                                               {
                                                                                'key':4,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_vod.mpd')+'?repr=V3&base=0&acodec=ec-3',
                                                                                'abr':False, 'BaseURL':False, 'static':True, 'encrypted':False
                                                                                },
                                                                               {
                                                                                'key':5,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_vod.mpd')+'?acodec=ec-3',
                                                                                'abr':True, 'BaseURL':True, 'static':True, 'encrypted':False
                                                                                }
                                                                               ]
                            },
                           { 'title':'Hand-made on demand profile',
                            'details':['AAC and E-AC3 audio'],
                            'buttons':[
                                                                               {
                                                                                'key':6,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_vod.mpd')+'?repr=V3',
                                                                                'abr':False, 'BaseURL':True, 'static':True, 'encrypted':False
                                                                                },
                                                                               {
                                                                                'key':7,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_vod.mpd')+'?repr=V3&base=0',
                                                                                'abr':False, 'BaseURL':False, 'static':True, 'encrypted':False
                                                                                },
                                                                               {
                                                                                'key':8,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_vod.mpd'),
                                                                                'abr':True, 'BaseURL':True, 'static':True, 'encrypted':False
                                                                                }
                                                                               ]
                            }
                           ]
        if context['page']==2:
            context['rows'] = [
                           { 'title':'Vendor A live profile',
                            'details':['AAC audio'], 'buttons':[
                                                                               {
                                                                                'key':1,
                                                                                'url':self.uri_for('dash-mpd', manifest='vod_manifest_a.mpd')+'?repr=V3',
                                                                                'abr':False, 'BaseURL':True, 'static':False, 'encrypted':False, 'mup':True
                                                                                },
                                                                               {
                                                                                'key':2,
                                                                                'url':self.uri_for('dash-mpd', manifest='vod_manifest_a.mpd'),
                                                                                'abr':True, 'BaseURL':True, 'static':False, 'encrypted':False, 'mup':True
                                                                                }
                                                                               ]
                            },
                           { 'title':'Vendor B live profile',
                            'details':['type="static"','AAC audio'], 'buttons':[
                                                                               {
                                                                                'key':3,
                                                                                'url':self.uri_for('dash-mpd', manifest='vod_manifest_b.mpd')+'?repr=V3',
                                                                                'abr':False, 'BaseURL':True, 'static':True, 'encrypted':False
                                                                                },
                                                                               {
                                                                                'key':4,
                                                                                'url':self.uri_for('dash-mpd', manifest='vod_manifest_b.mpd'),
                                                                                'abr':True, 'BaseURL':True, 'static':True, 'encrypted':False
                                                                                }
                                                                               ]
                            },
                           { 'title':'Vendor E live profile', 'buttons':[
                                                                               {
                                                                                'key':5,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_e.mpd')+'?repr=V3&mup=-1',
                                                                                'abr':False, 'BaseURL':True, 'static':False, 'mup':False, 'encrypted':False
                                                                                },
                                                                               {
                                                                                'key':6,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_e.mpd')+'?repr=V3',
                                                                                'abr':False, 'BaseURL':True, 'static':False, 'mup':True, 'encrypted':False
                                                                                },
                                                                               {
                                                                                'key':7,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_e.mpd'),
                                                                                'abr':True, 'BaseURL':True, 'static':False, 'mup':True, 'encrypted':False
                                                                                }
                                                                               ]
                            }
                               ]
        if context['page']==3:
            context['rows'] = [
                               { 'title':'Vendor H live profile',
                                'details':['utc:ntp UTCTiming element'],
                                 'buttons':[
                                                                                   {
                                                                                    'key':1,
                                                                                    'url':self.uri_for('dash-mpd', manifest='manifest_h.mpd')+'?repr=V3&mup=-1',
                                                                                    'abr':False, 'BaseURL':True, 'static':False, 'mup':False, 'encrypted':False
                                                                                    },
                                                                                   {
                                                                                    'key':2,
                                                                                    'url':self.uri_for('dash-mpd', manifest='manifest_h.mpd')+'?repr=V3',
                                                                                    'abr':False, 'BaseURL':True, 'static':False, 'mup':True, 'encrypted':False
                                                                                    },
                                                                                   {
                                                                                    'key':3,
                                                                                    'url':self.uri_for('dash-mpd', manifest='manifest_h.mpd'),
                                                                                    'abr':True, 'BaseURL':True, 'static':False, 'mup':True, 'encrypted':False
                                                                                    }
                                                                                   ]
                                },
                               { 'title':'Vendor I live profile',
                                'details':['utc:direct UTCTiming element'],
                                 'buttons':[
                                                                                   {
                                                                                    'key':4,
                                                                                    'url':self.uri_for('dash-mpd', manifest='manifest_i.mpd')+'?repr=V3&mup=-1',
                                                                                    'abr':False, 'BaseURL':True, 'static':False, 'mup':False, 'encrypted':False
                                                                                    },
                                                                                   {
                                                                                    'key':5,
                                                                                    'url':self.uri_for('dash-mpd', manifest='manifest_i.mpd')+'?repr=V3',
                                                                                    'abr':False, 'BaseURL':True, 'static':False, 'mup':True, 'encrypted':False
                                                                                    },
                                                                                   {
                                                                                    'key':6,
                                                                                    'url':self.uri_for('dash-mpd', manifest='manifest_i.mpd'),
                                                                                    'abr':True, 'BaseURL':True, 'static':False, 'mup':True, 'encrypted':False
                                                                                    }
                                                                                   ]
                                },
                                { 'title':'CENC VOD profile',
                                 'details':['DASH on demand profile',
                                            'kid=00000000000000000000000000000000',
                                            'key=0123456789ABCDEF0123456789ABCDEF'],
                                 'buttons':[
                                            {
                                             'key':7,
                                             'url':self.uri_for('dash-mpd', manifest='enc.mpd'),
                                             'abr':False, 'BaseURL':True, 'static':True, 'mup':False, 'encrypted':True
                                             }
                                            ]
                                },
                                { 'title':'CENC live profile',
                                 'details':['DASH live profile',
                                            'kid=00000000000000000000000000000000',
                                            'key=0123456789ABCDEF0123456789ABCDEF'],
                                 'buttons':[
                                            {
                                             'key':8,
                                             'url':self.uri_for('dash-mpd', manifest='enc.mpd')+'?mode=live',
                                             'abr':False, 'BaseURL':True, 'static':False, 'mup':True, 'encrypted':True
                                             }
                                            ]
                                }
                               ]
        template = templates.get_template('index.html')
        self.response.write(template.render(context))

class LiveManifest(RequestHandler):
    """handler for generating MPD files"""
    def get(self, manifest, **kwargs):
        context = self.create_context(**kwargs)
        context["headers"]=[]
        context['routes'] = routes
        self.response.content_type='application/dash+xml'
        context['title'] = 'Big Buck Bunny DASH test stream'
        dash = self.calculate_dash_params()
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
        template = templates.get_template(manifest)
        self.add_allowed_origins()
        self.response.write(template.render(context))

class LiveMedia(RequestHandler): #blobstore_handlers.BlobstoreDownloadHandler):
    """Handler that returns media fragments"""
    def get(self,mode,filename,segment,ext):
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
        if segment=='init':
            mod_segment = segment = 0
        else:
            try:
                segment = int(segment,10)
            except ValueError:
                segment=-1
            for code in self.INJECTED_ERROR_CODES:
                if self.request.params.get('%03d'%code) is not None:
                    try:
                        num_failures = int(self.request.params.get('failures','1'),10)
                        for d in self.request.params.get('%03d'%code).split(','):
                            if int(d,10)==segment:
                                # Only fail 5xx errors "num_failures" times
                                if code<500 or self.increment_memcache_counter(segment,code)<=num_failures:
                                    self.response.write('Synthetic %d for segment %d'%(code,segment))
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
            if segment<firstFragment or segment>lastFragment:
                #raise IOError("Incorrect fragment request %s %d %d->%d\n"%(filename, segment, firstFragment,lastFragment))
                self.response.write('Segment not found (valid range= %d->%d)'%(firstFragment,lastFragment))
                self.response.set_status(404)
                return
            if dash['mode']=='live':
                # elapsed_time is the time (in seconds) since availabilityStartTime
                # for the requested fragment
                elapsed_time = (segment - dash['startNumber']) * repr.segment_duration / float(repr.timescale)
                segpos = self.calculate_segment_from_timecode(elapsed_time, repr, dash['shortest_representation'])
                mod_segment = segpos['segment_num']
                origin_time = segpos['origin_time']
            else:
                mod_segment = segment
        mf = models.MediaFile.query(models.MediaFile.name==repr.filename).get()
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
        data = blob_reader.read(frag.seg.size)
        #arr = bytearray(data)
        if dash['mode']=='live':
            if segment==0:
                try:
                    # remove the mehd box as this stream is not supposed to have a fixed duration
                    offset = frag.mehd.pos + 4 # keep the length field of the old mehd box
                    #arr[offset:offset+4] = b'skip'
                    data = ''.join([data[:offset], 'skip', data[offset+4:]]) # convert it to a skip box
                except AttributeError:
                    pass
            else:
                # Update the baseMediaDecodeTime to take account of the number of times the
                # stream would have looped since availabilityStartTime
                dec_time_sz = frag.tfdt.size-12
                if dec_time_sz==8:
                    fmt='>Q'
                else:
                    fmt='>I'
                offset = frag.tfdt.pos + 12 #dec_time_pos - frag_pos
                base_media_decode_time = struct.unpack(fmt, data[offset:offset+dec_time_sz])[0]
                delta = long(origin_time*repr.timescale)
                if delta < 0L:
                    raise IOError("Failure in calculating delta %s %d %d %d"%(str(delta),segment,mod_segment,dash['startNumber']))
                base_media_decode_time += delta
                if base_media_decode_time > (1<<(8*dec_time_sz)):
                    raise IOError("base_media_time overflow: %s does not fit in %d bytes"%(str(base_media_decode_time),dec_time_sz))
                try:
                    base_media_decode_time = struct.pack(fmt,base_media_decode_time)
                except:
                    raise IOError("struct.pack failure %s"%str(base_media_decode_time))
                data = ''.join([data[:offset], base_media_decode_time, data[offset+dec_time_sz:]])
                #arr[offset:offset+dec_time_sz] = base_media_decode_time
                # Update the sequenceNumber field in the MovieFragmentHeader box
                offset = frag.mfhd.pos + 12
                #arr[offset:offset+4] = struct.pack('>I',segment)
                data = ''.join([data[:offset], struct.pack('>I',segment), data[offset+4:]])
            try:
                # remove any sidx box as it has a baseMediaDecodeTime and it's an optional index
                offset = frag.sidx.pos + 4 # keep the length field of the old sidx box
                data = ''.join([data[:offset], 'skip', data[offset+4:]]) # convert it to a skip box
                #arr[offset:offset+4] = b'skip'
            except AttributeError:
                pass
        self.add_allowed_origins()
        self.response.write(data)

class VideoPlayer(RequestHandler):
    """Responds with an HTML page that contains a video element to play the specified MPD"""
    def get(self, **kwargs):
        try:
            mpd_url = self.request.params['url']
        except KeyError:
            self.response.write('URL not specified')
            self.response.set_status(404)
            return
        context = self.create_context(**kwargs)
        context.update(self.calculate_dash_params(mpd_url=mpd_url))
        context['source'] = urlparse.urljoin(self.request.host_url,mpd_url)
        if context['encrypted']:
            try:
                context['source'] = '#'.join([settings.sas_url,urllib.quote(context['source'])])
            except AttributeError:
                pass
        context['mimeType'] = 'application/dash+xml'
        if self.request.params.has_key('title'):
            context['title'] = self.request.params['title']
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

class UploadFormHandler(RequestHandler):
    @admin_required
    def get(self, **kwargs):
        context = self.create_context(**kwargs)
        context['upload_url'] = blobstore.create_upload_url(self.uri_for('uploadBlob'))
        context['representations'] = media.representations
        self.generate_csrf(context)
        template = templates.get_template('upload.html')
        self.response.write(template.render(context))

class UploadHandler(RequestHandler):
    class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
        def post(self, *args, **kwargs):
            upload_files = self.get_uploads('file')
            logging.debug("uploaded file count: %d"%len(upload_files))
            if len(upload_files)==0:
                self.outer.get()
                return
            blob_info = upload_files[0]
            try:
                self.outer.check_csrf()
                media_id = self.request.get('media')
                repr = media.representations[media_id.upper()]
                context = self.outer.create_context(title='File %s uploaded'%(media_id), blob=blob_info.key())
                mf = models.MediaFile.query(models.MediaFile.name==repr.filename).get()
                if mf:
                    mf.key.delete()
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
    @admin_required
    def get(self, **kwargs):
        context = self.create_context(**kwargs)
        context['upload_url'] = blobstore.create_upload_url(self.uri_for('uploadBlob'))
        context['representations'] = media.representations
        self.generate_csrf(context)
        template = templates.get_template('upload.html')
        self.response.write(template.render(context))
