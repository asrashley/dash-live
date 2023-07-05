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

from builtins import object
import re

class Route(object):
    def __init__(self, template: str, handler: str, title: str,
                 parent: str = None) -> None:
        self.name = ''
        self.template = template
        self.handler = handler
        self.title = title
        self.parent = parent
        # convert Flask's template syntax in to the Python string.format() syntax
        self.formatTemplate = re.sub(
            r'<([^:>]+:)?(?P<name>[^>]+)>', r'{\g<name>}', template)

        # convert Flask's template syntax in to the Python regex format
        def matchfn(match) -> str:
            name = match.group(2)
            ptype = match.group('ptype')
            # print(f'ptype "{ptype}"')
            if ptype is None:
                return f'(?P<{name}>\\w+)'
            if ptype == 'int':
                return f'(?P<{name}>\\d+)'
            if ptype.startswith('regex'):
                regex = ptype[7:-2]
                return f'(?P<{name}>{regex})'
            return f'(?P<{name}>\\w+)'
        reTemplate = re.sub(r'<(?:(?P<ptype>[^:>]+):)?([^>]+?)>', matchfn, template)
        # print('reTemplate', self.title, reTemplate)
        self.reTemplate = re.compile(reTemplate)

    def __str__(self) -> str:
        rv = f'Route(name="{self.name}", title="{self.title}"'
        rv += f', template="{self.template}"'
        rv += f', re_template="{self.reTemplate.pattern}"'
        if self.parent:
            rv += f', parent="{self.parent}"'
        rv += ')'
        return rv


routes = {
    "key-delete": Route(
        r'/key/<int:kpk>/delete',
        handler='keypairs.DeleteKeyHandler',
        title='delete key pairs'),
    "key-edit": Route(
        r'/key/<int:kpk>',
        handler='keypairs.KeyHandler',
        title='Edit key pairs'),
    "key": Route(
        r'/key',
        handler='keypairs.KeyHandler',
        title='Add key pairs'),
    "clearkey": Route(
        r'/clearkey',
        handler='clearkey.ClearkeyHandler',
        title='W3C clearkey support'),
    "dash-mpd-v1": Route(
        r'/dash/<regex("[\w\-_]+\.mpd"):manifest>',
        handler='manifest_requests.LegacyManifestUrl',
        title='DASH test stream (v1 URL)'),
    "dash-mpd-v2": Route(
        r'/dash/<stream>/<regex("[\w\-_]+\.mpd"):manifest>',
        handler='manifest_requests.LegacyManifestUrl',
        title='DASH test stream (v2 URL)'),
    "dash-mpd-v3": Route(
        r'/dash/<regex("(live|vod|odvod)"):mode>/<stream>/<manifest>',
        handler='manifest_requests.ServeManifest',
        title='DASH test stream'),
    "dash-media": Route(
        r'/dash/<regex("(live|vod)"):mode>/<stream>/<filename>/' +
        r'<regex("(\d+|init)"):segment_num>.<regex("(mp4|m4v|m4a|m4s)"):ext>',
        handler='media_requests.LiveMedia',
        title="DASH fragment"),
    "dash-od-media": Route(
        r'/dash/vod/<stream>/<regex("[\w-]+"):filename>.<regex("(mp4|m4v|m4a|m4s)"):ext>',
        handler='media_requests.OnDemandMedia',
        title="DASH media file"),
    "media-index": Route(
        r'/media/index/<mfid>',
        handler='media_management.MediaIndex',
        title='Media information'),
    "media-info": Route(
        r'/media/<int:mfid>',
        handler='media_management.MediaInfo',
        title='Media information'),
    "media-list": Route(
        r'/media',
        handler='media_management.MediaList',
        title='Media file management'),
    "time": Route(
        r'/time/<regex("(head|xsd|iso|http-ntp)"):format>',
        handler='utctime.UTCTimeHandler',
        title='Current time of day'),
    "del-stream": Route(
        r'/stream/<int:spk>',
        handler='streams.StreamHandler',
        title='Delete stream'),
    "stream-add": Route(
        r'/stream',
        handler='streams.StreamHandler',
        title='Add stream'),
    "stream-edit": Route(
        r'/media/edit/<int:spk>',
        handler='streams.EditStreamHandler',
        title='Edit Stream',
        parent='media-list'),
    "stream-delete": Route(
        r'/media/delete/<int:spk>',
        handler='streams.DeleteStreamHandler',
        title='Delete Stream',
        parent='media-list'),
    "upload-blob": Route(
        r'/media/<int:spk>/blob',
        handler='media_management.UploadHandler',
        title='Upload blob',
        parent='media-list'),
    "video": Route(
        r'/play/<regex("(live|vod|odvod)"):mode>/<stream>/<manifest>/index.html',
        handler='htmlpage.VideoPlayer',
        title='DASH test stream player'),
    "cgi-options": Route(
        r'/options',
        handler='htmlpage.CgiOptionsPage',
        title='Manifest and Media CGI options'),
    "login": Route(
        r'/login',
        handler='htmlpage.LoginPage',
        title='Log into site'),
    "logout": Route(
        r'/logout',
        handler='htmlpage.LogoutPage',
        title='Log out of site'),
    "home": Route(
        r'/',
        handler='htmlpage.MainPage',
        title='DASH test streams'),
}

for name in routes.keys():
    routes[name].name = name
