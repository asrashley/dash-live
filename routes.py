import webapp2

class Route(object):
    def __init__(self,template,handler,title,parent=None):
        self.template=template
        self.handler=handler
        self.title=title
        self.parent=parent

routes = {
    "del-key":Route(r'/key/<kid:\w+>', handler='views.KeyHandler', title='delete key pairs'),
    "key":Route(r'/key', handler='views.KeyHandler', title='Add key pairs'),
    "clearkey":Route(r'/clearkey', handler='views.ClearkeyHandler', title='W3C clearkey support'),
    "dash-mpd":Route(r'/dash/<manifest:[\w\-_]+\.mpd>', handler='views.LiveManifest', title='DASH test stream'),
    "dash-media":Route(r'/dash/<mode:(live|vod)>/<filename:\w+>/<segment_num:(\d+|init)>.<ext:(mp4|m4v|m4a|m4s)>', handler='views.LiveMedia', title="DASH fragment"),
    "dash-od-media":Route(r'/dash/vod/<filename:(A[1-2]|V[1-3]|V3ENC)>.<ext:(mp4|m4v|m4a|m4s)>', handler='views.OnDemandMedia', title="DASH media file"),
    "del-media":Route(r'/media/<mfid:[\w_+=-]+>', handler='views.MediaHandler', title='Delete media'),
    "media":Route(r'/media', handler='views.MediaHandler', title='Media file management'),
    "time":Route(r'/time/<format:(xsd|iso|ntp)>', handler='views.UTCTimeHandler', title='Current time of day'),
    "uploadBlob":Route(r'/blob', handler='views.MediaHandler', title='Upload blob'),
    "video":Route(r'/video', handler='views.VideoPlayer', title='DASH test stream player'),
    "home":Route(r'/', handler='views.MainPage', title='DASH test streams'),
}

for name,r in routes.iteritems():
    r.name = name

webapp_routes = []
for name,route in routes.iteritems():
    webapp_routes.append(webapp2.Route(template=route.template, handler=route.handler, name=name))
