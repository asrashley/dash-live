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

import re
import webapp2

class Route(object):
    def __init__(self, template, handler, title, parent=None):
        self.template = template
        self.handler = handler
        self.title = title
        self.parent = parent
        # convert App Engine's template syntax in to the Python string.format() syntax
        self.formatTemplate = re.sub(
            r':[^>]*>', '}', template.replace('<', '{'))

        # convert App Engine's template syntax in to the Python regex format
        reTemplate = re.sub(r'<(\w+):([^>]+)>', r'(?P<\1>\2)', template)
        self.reTemplate = re.compile(reTemplate)


routes = {
    "del-key": Route(
        r'/key/<kid:\w+>',
        handler='server.requesthandler.keypairs.KeyHandler',
        title='delete key pairs'),
    "key": Route(
        r'/key',
        handler='server.requesthandler.keypairs.KeyHandler',
        title='Add key pairs'),
    "clearkey": Route(
        r'/clearkey',
        handler='server.requesthandler.clearkey.ClearkeyHandler',
        title='W3C clearkey support'),
    "dash-mpd-v1": Route(
        r'/dash/<manifest:[\w\-_]+\.mpd>',
        handler='server.requesthandler.manifest_requests.LegacyManifestUrl',
        title='DASH test stream (v1 URL)'),
    "dash-mpd-v2": Route(
        r'/dash/<stream:\w+>/<manifest:[\w\-_]+\.mpd>',
        handler='server.requesthandler.manifest_requests.LegacyManifestUrl',
        title='DASH test stream (v2 URL)'),
    "dash-mpd-v3": Route(
        r'/dash/<mode:(live|vod|odvod)>/<stream:\w+>/<manifest:[\w\-_]+\.mpd>',
        handler='server.requesthandler.manifest_requests.ServeManifest',
        title='DASH test stream'),
    "dash-media": Route(
        r'/dash/<mode:(live|vod)>/<filename:\w+>/<segment_num:(\d+|init)>.<ext:(mp4|m4v|m4a|m4s)>',
        handler='server.requesthandler.media_requests.LiveMedia',
        title="DASH fragment"),
    "dash-od-media": Route(
        r'/dash/vod/<filename:\w+>.<ext:(mp4|m4v|m4a|m4s)>',
        handler='server.requesthandler.media_requests.OnDemandMedia',
        title="DASH media file"),
    "media-info": Route(
        r'/media/<mfid:[\w_+=-]+>',
        handler='server.requesthandler.media_management.MediaHandler',
        title='Media information'),
    "media-index": Route(
        r'/media',
        handler='server.requesthandler.media_management.MediaHandler',
        title='Media file management'),
    "time": Route(
        r'/time/<format:(xsd|iso|ntp)>',
        handler='server.requesthandler.utctime.UTCTimeHandler',
        title='Current time of day'),
    "del-stream": Route(
        r'/stream/<id:[\w_+=-]+>',
        handler='server.requesthandler.streams.StreamHandler',
        title='Delete stream'),
    "stream": Route(
        r'/stream',
        handler='server.requesthandler.streams.StreamHandler',
        title='Add stream'),
    "uploadBlob": Route(
        r'/blob',
        handler='server.requesthandler.media_management.MediaHandler',
        title='Upload blob'),
    "video": Route(
        r'/video',
        handler='server.requesthandler.htmlpage.VideoPlayer',
        title='DASH test stream player'),
    "cgi-options": Route(
        r'/options',
        handler='server.requesthandler.htmlpage.CgiOptionsPage',
        title='Manifest and Media CGI options'),
    "home": Route(
        r'/',
        handler='server.requesthandler.htmlpage.MainPage',
        title='DASH test streams'),
}

for name, r in routes.iteritems():
    r.name = name

webapp_routes = []
for name, route in routes.iteritems():
    webapp_routes.append(
        webapp2.Route(template=route.template,
                      handler=route.handler,
                      name=name))
