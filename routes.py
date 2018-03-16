import webapp2

class Route(object):
    def __init__(self,template,handler,title,parent=None):
        self.template=template
        self.handler=handler
        self.title=title
        self.parent=parent

routes = {
    "dash-mpd":Route(r'/dash/<manifest:[\w\-_]+\.mpd>', handler='views.LiveManifest', title='DASH test stream'),
    "dash-media":Route(r'/dash/<mode:(live|vod)>/<filename:(A[1-2]|V[1-3]|V3ENC)>/<segment:(\d+|init)>.<ext:(mp4|m4v|m4a|m4s)>', handler='views.LiveMedia', title="DASH fragment"),
    "dash-od-media":Route(r'/dash/vod/<filename:(A[1-2]|V[1-3]|V3ENC)>.<ext:(mp4|m4v|m4a|m4s)>', handler='views.OnDemandMedia', title="DASH media file"),
    "video":Route(r'/video/<testcase:[\w\-_]+>', handler='views.VideoPlayer', title='DASH test stream player'),
    "home":Route(r'/', handler='views.MainPage', title='DASH test streams'),
    "time":Route(r'/time/<format:(xsd|iso|ntp)>', handler='views.UTCTimeHandler', title='Current time of day'),
    "uploadBlob":Route(r'/blob', handler='views.UploadHandler', title='Upload blob'),
    "upload":Route(r'/upload', handler='views.UploadHandler', title='Upload media file'),
}

for name,r in routes.iteritems():
    r.name = name

webapp_routes = []
for name,route in routes.iteritems():
    webapp_routes.append(webapp2.Route(template=route.template, handler=route.handler, name=name))
