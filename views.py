#!/usr/bin/env python
#
import datetime, decimal, math, time, os, sys, urllib, urlparse

import webapp2, jinja2
from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from webapp2_extras import securecookie
from webapp2_extras import security

from settings import cookie_secret, csrf_secret, DEBUG
from routes import routes
import media, utils, models

templates = jinja2.Environment(
                               loader=jinja2.FileSystemLoader(
                                                              os.path.join(os.path.dirname(__file__),'templates')
                                                              ),
                               extensions=['jinja2.ext.autoescape'])

templates.filters['isoDuration'] = utils.toIsoDuration
templates.filters['isoDateTime'] = utils.toIsoDateTime

SCRIPT_TEMPLATE=r'<script src="/js/{mode}/{filename}{min}.js" type="text/javascript"></script>'
def import_script(filename):
    mode = 'dev' if DEBUG else 'prod'
    min = '' if DEBUG else '.min'
    return SCRIPT_TEMPLATE.format(mode=mode, filename=filename, min=min)

class RequestHandler(webapp2.RequestHandler):
    CLIENT_COOKIE_NAME='discovery'
    CSRF_COOKIE_NAME='csrf'
    
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
        context['video_fields'] = [ 'id', 'codecs', 'bandwidth', 'height', 'width', 'frameRate' ]
        context['video_representations'] = [ media.representations['V1'], media.representations['V2'], media.representations['V3'] ]
        context['audio_fields'] = [ 'id', 'codecs', 'bandwidth', 'sampleRate', 'numChannels', 'lang' ]
        context['audio_representations'] = [ media.representations['A1'] ]
        context['rows'] = [
                           { 'title':'Hand-made on demand profile', 'buttons':[
                                                                               {
                                                                                'key':0,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_vod.mpd')+'?rep=0',
                                                                                'abr':False, 'BaseURL':True, 'static':True
                                                                                },
                                                                               {
                                                                                'key':1,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_vod.mpd')+'?rep=0&base=0',
                                                                                'abr':False, 'BaseURL':False, 'static':True
                                                                                },
                                                                               {
                                                                                'key':2,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_vod.mpd'),
                                                                                'abr':True, 'BaseURL':True, 'static':True
                                                                                }
                                                                               ] 
                            },
                           { 'title':'Vendor B live profile', 'buttons':[
                                                                               {
                                                                                'key':3,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_b.mpd')+'?rep=0&mup=-1',
                                                                                'abr':False, 'BaseURL':True, 'static':False, 'mup':False
                                                                                },
                                                                               {
                                                                                'key':4,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_b.mpd')+'?rep=0',
                                                                                'abr':False, 'BaseURL':True, 'static':False, 'mup':True
                                                                                },
                                                                               {
                                                                                'key':5,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_b.mpd')+'?mup=-1',
                                                                                'abr':True, 'BaseURL':True, 'static':False, 'mup':False
                                                                                }
                                                                               ] 
                            },
                           { 'title':'Vendor E live profile', 'buttons':[
                                                                               {
                                                                                'key':6,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_e.mpd')+'?rep=0&mup=-1',
                                                                                'abr':False, 'BaseURL':True, 'static':False, 'mup':False
                                                                                },
                                                                               {
                                                                                'key':7,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_e.mpd')+'?rep=0',
                                                                                'abr':False, 'BaseURL':True, 'static':False, 'mup':True
                                                                                },
                                                                               {
                                                                                'key':8,
                                                                                'url':self.uri_for('dash-mpd', manifest='manifest_e.mpd')+'?mup=-1',
                                                                                'abr':True, 'BaseURL':True, 'static':False, 'mup':False
                                                                                }
                                                                               ] 
                            }
                           ]
        if context['page']==2:
            context['rows'] = [
                               { 'title':'Vendor I live profile', 'buttons':[
                                                                                   {
                                                                                    'key':1,
                                                                                    'url':self.uri_for('dash-mpd', manifest='manifest_i.mpd')+'?rep=0&mup=-1',
                                                                                    'abr':False, 'BaseURL':True, 'static':False, 'mup':False
                                                                                    },
                                                                                   {
                                                                                    'key':2,
                                                                                    'url':self.uri_for('dash-mpd', manifest='manifest_i.mpd')+'?rep=0',
                                                                                    'abr':False, 'BaseURL':False, 'static':False, 'mup':True
                                                                                    },
                                                                                   {
                                                                                    'key':3,
                                                                                    'url':self.uri_for('dash-mpd', manifest='manifest_i.mpd'),
                                                                                    'abr':True, 'BaseURL':True, 'static':False, 'mup':True
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
        now = math.floor(time.time())
        self.response.content_type='application/dash+xml'
        try:
            start = int(self.request.params['start'], 10)
        except (KeyError,ValueError):
            cur_url = urlparse.urlparse(self.request.uri, 'http')
            cur_qs = urlparse.parse_qs(cur_url.query)
            cur_qs['start'] = ['%d'%int(now)]
            new_url = urlparse.urlunparse(( cur_url.scheme, cur_url.netloc, cur_url.path, cur_url.params, urllib.urlencode(cur_qs,True), cur_url.fragment ))
            self.response.headers.add_header("Access-Control-Allow-Origin", "*")
            self.redirect(new_url)
            return
        if not start:
            start = now
        timeShiftBufferDepth = 20
        availabilityStartTime = datetime.datetime.utcfromtimestamp(start - timeShiftBufferDepth)
        if (1+now-start)>timeShiftBufferDepth:
            timeShiftBufferDepth = 1+now-start
        context['title'] = 'Big Buck Bunny DASH test stream'
        context['now'] = datetime.datetime.fromtimestamp(now)
        try:
            context['repr'] = int(self.request.params.get('rep','-1'),10)
        except ValueError:
            context['repr'] = -1
        context['timeShiftBufferDepth'] = timeShiftBufferDepth
        context['availabilityStartTime'] = datetime.datetime.utcfromtimestamp(start - timeShiftBufferDepth)
        context['baseURL'] = urlparse.urljoin(self.request.host_url,'/dash')+'/'
        try:
            if not int(self.request.params.get('base','1'),10):
                del context['baseURL']
        except ValueError:
            pass
        context['timescale'] = 1000
        context['media_duration'] = 9*60 + 32.52 #"PT0H9M32.52S"
        context['video_representations'] = [ media.representations['V1'], media.representations['V2'], media.representations['V3'] ]
        context['audio_representations'] = [ media.representations['A1'] ]
        #{'id':'V1', 'codecs':"avc1.4D001E", 'width':352, 'height':288, 'duration':5120, 'startWithSAP':1, 'bandwidth':683133, 'frameRate':25, 'sar':"22:17", 'scanType':"progressive", 'segments':media.atoms['V1'].fragments },
        #{'id':'V2', 'codecs':"avc1.640028", 'width':1024, 'height':576, 'duration':5120, 'startWithSAP':1, 'bandwidth':1005158, 'frameRate':25, 'sar':"22:17", 'scanType':"progressive", 'segments':media.atoms['V2'].fragments},
        #{'id':'V3', 'codecs':"avc1.640028", 'width':1024, 'height':576, 'duration':5120, 'startWithSAP':1, 'bandwidth':1289886, 'frameRate':25, 'sar':"22:17", 'scanType':"progressive", 'segments':media.atoms['V3'].fragments},
        #{'id':'V4', 'codecs':"avc1.640028", 'width':1024, 'height':576, 'duration':5120, 'startWithSAP':1, 'bandwidth':1552841, 'frameRate':25, 'sar':"22:17", 'scanType':"progressive", 'segments':media.atoms['V4'].fragments}
        #{'id':'A1', 'codecs':"mp4a.40.02", 'sampleRate':48000, 'duration':3989, 'numChannels':2, 'lang':'eng', 'startWithSAP':1, 'bandwidth':95170 },
        if context['repr']>=0 and context['repr']<len(context['video_representations']):
            context['video_representations'] = [context['video_representations'][context['repr']]]
        context['minWidth'] = min([ a.width for a in context['video_representations']])
        context['minHeight'] = min([ a.height for a in context['video_representations']])
        context['minBandwidth'] = min([ a.bandwidth for a in context['video_representations']])
        context['maxWidth'] = max([ a.width for a in context['video_representations']])
        context['maxHeight'] = max([ a.height for a in context['video_representations']])
        context['maxBandwidth'] = max([ a.bandwidth for a in context['video_representations']])
        context['maxFrameRate'] = max([ a.frameRate for a in context['video_representations']])
        context['maxSegmentDuration'] = max([ a.duration for a in context['video_representations']]) / float(context['timescale'])
        try:
            context['minimumUpdatePeriod'] = float(self.request.params.get('mup',2.0*context['maxSegmentDuration']))
        except ValueError:
            context['minimumUpdatePeriod'] = 2.0*context['maxSegmentDuration']
        if context['minimumUpdatePeriod']<=0:
            del context['minimumUpdatePeriod']
        template = templates.get_template(manifest)
        try:
            if self.request.headers['Origin']=='http://dashif.org':
                self.response.headers.add_header("Access-Control-Allow-Origin", "http://dashif.org")
                self.response.headers.add_header("Access-Control-Allow-Methods", "GET")
        except KeyError:
            pass
        self.response.write(template.render(context))

class LiveMedia(RequestHandler): #blobstore_handlers.BlobstoreDownloadHandler):
    """Handler that returns media fragments"""
    def get(self,filename,segment,ext):
        try:
            repr = media.representations[filename.upper()]
        except KeyError,e:
            self.response.write('%s not found: %s'%(filename,str(e)))
            self.response.set_status(404)
            return
        if segment=='init':
            segment = 0
        else:
            try:
                segment = int(segment,10)
            except ValueError:
                segment=-1
            if segment<0:
                self.response.write('Segment not found')
                self.response.set_status(404)
                return
            segment = 1+((segment-1)%(len(repr.segments)-1))
        mf = models.MediaFile.query(models.MediaFile.name==repr.filename).get()
        #blob_info = blobstore.BlobInfo.get(mf.blob)
        if ext=='m4a':
            self.response.content_type='audio/mp4'
        elif ext=='m4v':
            self.response.content_type='video/mp4'
        else:
            self.response.content_type='application/mp4'
        blob_reader = blobstore.BlobReader(mf.blob, position=repr.segments[segment][0], buffer_size=repr.segments[segment][1])
        data = blob_reader.read(repr.segments[segment][1])
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
    """Responds with a HTML page that contains a video element to play the specified MPD"""
    def get(self, **kwargs):
        try:
            mpd_url = self.request.params['url']
        except KeyError:
            self.response.write('URL not specified')
            self.response.set_status(404)
            return
        context = self.create_context(**kwargs)
        context['source'] = mpd_url 
        context['mimeType'] = 'application/dash+xml'
        if self.request.params.has_key('title'):
            context['title'] = self.request.params['title']
        template = templates.get_template('video.html')
        self.response.write(template.render(context))

class UploadFormHandler(RequestHandler):
    def get(self, **kwargs):
        context = self.create_context(**kwargs)
        context['upload_url'] = blobstore.create_upload_url(self.uri_for('uploadBlob'))
        context['representations'] = media.representations
        template = templates.get_template('upload.html')
        self.response.write(template.render(context))
    
class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        upload_files = self.get_uploads('file')
        blob_info = upload_files[0]
        try:
            media_id = self.request.get('media')
            repr = media.representations[media_id.upper()]
        except KeyError,e:
            self.response.write('%s not found: %s'%(media_id,str(e)))
            self.response.set_status(404)
            blob_info.delete()
            return
        mf = models.MediaFile(name=repr.filename, blob=blob_info.key())
        mf.put()
        template = templates.get_template('upload-done.html')
        context={'title':'File %s uploaded'%(media_id), 'blob':blob_info.key()}
        self.response.write(template.render(context))
