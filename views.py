#!/usr/bin/env python
#
import binascii, copy, datetime, decimal, hashlib, hmac, logging, math, time, os, re, struct, sys, urllib, urlparse

import webapp2, jinja2
from google.appengine.api import users
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

    def calculate_dash_params(self, mode=None, mpd_url=None):
        def scale_timedelta(delta, num, denom):
            secs = num * delta.seconds
            msecs = num* delta.microseconds
            secs += msecs / 1000000.0
            return secs / denom

        def compute_values(av):
            av['timescale'] = av['representations'][0].timescale
            av['lastFragment'] = startNumber + int(scale_timedelta(elapsedTime, av['timescale'], av['representations'][0].segment_duration))
            av['firstFragment'] = av['lastFragment'] - int(av['timescale']*timeShiftBufferDepth / av['representations'][0].segment_duration)
            av['presentationTimeOffset'] = int((startNumber-1) * av['representations'][0].segment_duration)
            av['minBitrate'] = min([ a.bitrate for a in av['representations']])
            av['maxBitrate'] = max([ a.bitrate for a in av['representations']])
            av['maxSegmentDuration'] = max([ a.segment_duration for a in av['representations']]) / av['timescale']

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
                timeShiftBufferDepth = int(self.request.params.get('depth','60'),10)
            except ValueError:
                timeShiftBufferDepth = 60 # in seconds
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
        compute_values(video)
        media_duration = video['representations'][0].media_duration / video['representations'][0].timescale
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
        compute_values(audio)
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
        cgiParams = []
        if clockDrift:
            timeSource['url'] += '?drift=%d'%clockDrift
            cgiParams.append('drift=%d'%clockDrift)
        if timeShiftBufferDepth != 60:
            cgiParams.append('depth=%d'%timeShiftBufferDepth)
        if cgiParams:
            video['mediaURL'] += '?' + '&'.join(cgiParams)
            audio['mediaURL'] += '?' + '&'.join(cgiParams)
        return locals()

    def add_allowed_origins(self):
        try:
            if self.ALLOWED_DOMAINS.search(self.request.headers['Origin']):
                self.response.headers.add_header("Access-Control-Allow-Origin", self.request.headers['Origin'])
                self.response.headers.add_header("Access-Control-Allow-Methods", "GET")
        except KeyError:
            pass

class MainPage(RequestHandler):
    """handler for main index page"""
    def get(self, **kwargs):
        context = self.create_context(**kwargs)
        try:
            context['page'] = int(self.request.params.get('page','1'),10)
        except ValueError:
            context['page'] = 1
        context["headers"]=[]
        context['routes'] = routes
        context['video_fields'] = [ 'id', 'codecs', 'bitrate', 'height', 'width', 'encrypted' ]
        context['video_representations'] = [ r for r in media.representations.values() if r.contentType=="video"]
        # [ media.representations['V1'], media.representations['V2'], media.representations['V3'] ]
        context['audio_fields'] = [ 'id', 'codecs', 'bitrate', 'sampleRate', 'numChannels', 'language', 'encrypted' ]
        context['audio_representations'] = [ r for r in media.representations.values() if r.contentType=="audio"]
        #[ media.representations['A1'] ]
        context['rows'] = [
                           { 'title':'Hand-made on demand profile', 'buttons':[
                                                                               {
                                                                                'key':0,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_vod.mpd')+'?repr=V3',
                                                                                'abr':False, 'BaseURL':True, 'static':True, 'encrypted':False
                                                                                },
                                                                               {
                                                                                'key':1,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_vod.mpd')+'?repr=V3&base=0',
                                                                                'abr':False, 'BaseURL':False, 'static':True, 'encrypted':False
                                                                                },
                                                                               {
                                                                                'key':2,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_vod.mpd'),
                                                                                'abr':True, 'BaseURL':True, 'static':True, 'encrypted':False
                                                                                }
                                                                               ]
                            },
                           { 'title':'Vendor B live profile', 'buttons':[
                                                                               {
                                                                                'key':3,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_b.mpd')+'?repr=V3&mup=-1',
                                                                                'abr':False, 'BaseURL':True, 'static':False, 'mup':False, 'encrypted':False
                                                                                },
                                                                               {
                                                                                'key':4,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_b.mpd')+'?repr=V3',
                                                                                'abr':False, 'BaseURL':True, 'static':False, 'mup':True, 'encrypted':False
                                                                                },
                                                                               {
                                                                                'key':5,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_b.mpd')+'?mup=-1',
                                                                                'abr':True, 'BaseURL':True, 'static':False, 'mup':False, 'encrypted':False
                                                                                }
                                                                               ]
                            },
                           { 'title':'Vendor E live profile', 'buttons':[
                                                                               {
                                                                                'key':6,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_e.mpd')+'?repr=V3&mup=-1',
                                                                                'abr':False, 'BaseURL':True, 'static':False, 'mup':False, 'encrypted':False
                                                                                },
                                                                               {
                                                                                'key':7,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_e.mpd')+'?repr=V3',
                                                                                'abr':False, 'BaseURL':True, 'static':False, 'mup':True, 'encrypted':False
                                                                                },
                                                                               {
                                                                                'key':8,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_e.mpd')+'?mup=-1',
                                                                                'abr':True, 'BaseURL':True, 'static':False, 'mup':False, 'encrypted':False
                                                                                }
                                                                               ]
                            }
                           ]
        if context['page']==2:
            context['rows'] = [
                               { 'title':'Vendor I live profile', 'buttons':[
                                                                                   {
                                                                                    'key':1,
                                                                                    'url':self.uri_for('dash-mpd', manifest='manifest_i.mpd')+'?repr=V3&mup=-1',
                                                                                    'abr':False, 'BaseURL':True, 'static':False, 'mup':False, 'encrypted':False
                                                                                    },
                                                                                   {
                                                                                    'key':2,
                                                                                    'url':self.uri_for('dash-mpd', manifest='manifest_i.mpd')+'?repr=V3',
                                                                                    'abr':False, 'BaseURL':True, 'static':False, 'mup':True, 'encrypted':False
                                                                                    },
                                                                                   {
                                                                                    'key':3,
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
                                             'key':4,
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
                                             'key':5,
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
        dash = self.calculate_dash_params(mode)
        if segment=='init':
            mod_segment = segment = 0
        else:
            try:
                segment = int(segment,10)
            except ValueError:
                segment=-1
            avInfo = dash['video'] if filename[0]=='V' else dash['audio']
            if segment<avInfo['firstFragment'] or segment>avInfo['lastFragment']:
                #raise IOError("incorrect fragment request %s %d %d->%d\n"%(filename, segment, avInfo['firstFragment'],avInfo['lastFragment']))
                self.response.write('Segment not found (valid range= %d->%d)'%(avInfo['firstFragment'],avInfo['lastFragment']))
                self.response.set_status(404)
                return
            mod_segment = 1+((segment-1)%repr.num_segments)
        mf = models.MediaFile.query(models.MediaFile.name==repr.filename).get()
        #blob_info = blobstore.BlobInfo.get(mf.blob)
        if ext=='m4a':
            self.response.content_type='audio/mp4'
        elif ext=='m4v':
            self.response.content_type='video/mp4'
        else:
            self.response.content_type='application/mp4'
        frag = repr.segments[mod_segment]
        blob_reader = blobstore.BlobReader(mf.blob, position=frag.seg.pos, buffer_size=frag.seg.size)
        data = blob_reader.read(frag.seg.size)
        #arr = bytearray(data)
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
            #segment * repr.segment_duration
            #num_loops = (segment-1) // repr.num_segments
            #delta = dash['media_duration'] * num_loops
            delta = (segment - mod_segment) * repr.segment_duration
            base_media_decode_time += long(delta)
            if base_media_decode_time > (1<<(8*dec_time_sz)):
                raise IOError("base_media_time overflow: %d does not fit in %d bytes"%(base_media_decode_time,dec_time_sz))
            base_media_decode_time = struct.pack(fmt,base_media_decode_time)
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
        #self.send_blob(blob_info, start=repr.segments[segment][0], end=(repr.segments[segment][0]+repr.segments[segment][1]))
        #src = open(repr.filename,'rb')
        #try:
        #    src.seek(repr.segments[segment][0])
        #    data = src.read(repr.segments[segment][1])
        #    if ext=='m4a':
        #        self.response.content_type='audio/mp4'
        #    elif ext=='m4v':
        #        self.response.content_type='video/mp4'
        #    else:
        #        self.response.content_type='application/mp4'
        #    self.response.write(data)
        #finally:
        #    src.close()

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
