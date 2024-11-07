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

class Route:
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

    def page_title(self) -> str:
        parts = self.name.split('-')
        return ' '.join(parts).title()

    def __str__(self) -> str:
        rv = f'Route(name="{self.name}", title="{self.title}"'
        rv += f', template="{self.template}"'
        rv += f', re_template="{self.reTemplate.pattern}"'
        if self.parent:
            rv += f', parent="{self.parent}"'
        rv += ')'
        return rv


routes = {
    "delete-key": Route(
        r'/key/<int:kpk>/delete',
        handler='keypairs.DeleteKeyHandler',
        title='delete key pairs'),
    "edit-key": Route(
        r'/key/<int:kpk>',
        handler='keypairs.KeyHandler',
        title='Edit key pairs',
        parent='list-streams'),
    "add-key": Route(
        r'/key',
        handler='keypairs.KeyHandler',
        title='Add key pairs',
        parent='list-streams'),
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
    "mpd-patch": Route(
        r'/patch/<stream>/<manifest>/<int:publish>',
        handler='manifest_requests.ServePatch',
        title='DASH manifest patch'),
    "dash-media-base-url": Route(
        r'/dash/<regex("(live|vod)"):mode>/<stream>/',
        handler='generic.NotFound',
        title="Used for generating BaseURL values"),
    "dash-media": Route(
        r'/dash/<regex("(live|vod)"):mode>/<stream>/<filename>/' +
        r'<regex("(\d+|init)"):segment_num>.<regex("(mp4|m4v|m4a|m4s)"):ext>',
        handler='media_requests.LiveMedia',
        title="DASH fragment"),
    "dash-media-by-time": Route(
        r'/dash/<regex("(live|vod)"):mode>/<stream>/<filename>/time/' +
        r'<int:segment_time>.<regex("(mp4|m4v|m4a|m4s)"):ext>',
        handler='media_requests.LiveMedia',
        title="DASH fragment"),
    "dash-od-media-base-url": Route(
        r'/dash/odvod/<stream>/',
        handler='generic.NotFound',
        title="BaseURL for on-demand media"),
    "dash-od-media": Route(
        r'/dash/odvod/<stream>/<regex("[\w-]+"):filename>.<regex("(mp4|m4v|m4a|m4s)"):ext>',
        handler='media_requests.OnDemandMedia',
        title="DASH media file"),
    "index-media-file": Route(
        r'/media/index/<int:mfid>',
        handler='media_management.IndexMediaFile',
        title='Media information'),
    "view-media-segment": Route(
        r'/stream/<int:spk>/<int:mfid>/segment/<int:segnum>',
        handler='media_management.MediaSegmentInfo',
        title='Media Segment',
        parent='list-streams'),
    "list-media-segments": Route(
        r'/stream/<int:spk>/<int:mfid>/segments',
        handler='media_management.MediaSegmentList',
        title='Media Segments',
        parent='list-streams'),
    "media-info": Route(
        r'/stream/<int:spk>/<int:mfid>',
        handler='media_management.MediaInfo',
        title='Media information',
        parent='list-streams'),
    "edit-media": Route(
        r'/stream/<int:spk>/<int:mfid>/edit',
        handler='media_management.EditMedia',
        title='Edit Media',
        parent='list-streams'),
    "inspect-media": Route(
        r'/media/inspect',
        handler='media_management.InspectMediaFile',
        title='Inspect MP4 file',
        parent='home',
    ),
    "check-media-changes": Route(
        r'/stream/<int:spk>/<int:mfid>/validate',
        handler='media_management.ValidateMediaChanges',
        title='Edit Media',
        parent='list-streams'),
    "delete-media": Route(
        r'/stream/<int:spk>/<int:mfid>/delete',
        handler='media_management.DeleteMedia',
        title='Delete Media',
        parent='list-streams'),
    'list-streams': Route(
        r'/streams',
        handler='streams.ListStreams',
        title='Available DASH streams'),
    "time": Route(
        r'/time/<regex("(head|xsd|iso|http-ntp)"):method>',
        handler='utctime.UTCTimeHandler',
        title='Current time of day'),
    "delete-stream": Route(
        r'/stream/<int:spk>/delete',
        handler='streams.DeleteStream',
        title='Delete stream',
        parent='list-streams'),
    "add-stream": Route(
        r'/streams/add',
        handler='streams.AddStream',
        title='Add stream'),
    "validate-stream": Route(
        r'/validate/',
        handler='htmlpage.DashValidator',
        title='DASH Validator'),
    "view-stream": Route(
        r'/stream/<int:spk>',
        handler='streams.EditStream',
        title='Edit Stream',
        parent='list-streams'),
    "edit-stream-defaults": Route(
        r'/stream/<int:spk>/defaults',
        handler='streams.EditStreamDefaults',
        title='Edit Stream Defaults',
        parent='list-streams'),
    "upload-blob": Route(
        r'/media/<int:spk>/blob',
        handler='media_management.UploadHandler',
        title='Upload blob',
        parent='list-streams'),
    "video": Route(
        r'/play/<regex("(live|vod|odvod)"):mode>/<stream>/<manifest>/index.html',
        handler='htmlpage.VideoPlayer',
        title='DASH test stream player'),
    "video-mps": Route(
        r'/play/mps/<regex("(live|vod)"):mode>/<mps_name>/<manifest>/index.html',
        handler='htmlpage.VideoPlayer',
        title='DASH test stream player'),
    "view-manifest": Route(
        r'/view/dash/<regex("(live|vod|odvod)"):mode>/<stream>/<manifest>',
        handler='htmlpage.ViewManifest',
        title='DASH manifest'),
    "view-mps-manifest": Route(
        r'/view/mps/<regex("(live|vod)"):mode>/<mps_name>/<manifest>',
        handler='htmlpage.ViewMpsManifest',
        title='DASH manifest'),
    "cgi-options": Route(
        r'/options',
        handler='htmlpage.CgiOptionsPage',
        title='Manifest and Media CGI options'),
    "login": Route(
        r'/login',
        handler='user_management.LoginPage',
        title='Log into site'),
    "logout": Route(
        r'/logout',
        handler='user_management.LogoutPage',
        title='Log out of site'),
    "list-users": Route(
        r'/users',
        handler='user_management.ListUsers',
        title='Users'),
    "add-user": Route(
        r'/users/',
        handler='user_management.AddUser',
        title='Add User'),
    "edit-user": Route(
        r'/users/<int:upk>',
        handler='user_management.EditUser',
        title='Edit User'),
    "change-password": Route(
        r'/users/me',
        handler='user_management.EditSelf',
        title='Account Settings'),
    "delete-user": Route(
        r'/users/<int:upk>/delete',
        handler='user_management.DeleteUser',
        title='Delete User'),
    "refresh-access-token": Route(
        r'/user/refresh/access',
        handler='user_management.RefreshAccessToken',
        title='Refresh access token'),
    "refresh-csrf-tokens": Route(
        r'/user/refresh/csrf',
        handler='user_management.RefreshCsrfTokens',
        title='Refresh access token'),
    'list-mps': Route(
        r'/multi-period-streams',
        handler='multi_period_streams.ListStreams',
        title='Available DASH multi-period streams'),
    'add-mps': Route(
        r'/multi-period-streams/.add',
        handler='multi_period_streams.AddStream',
        title='Add new multi-period stream',
        parent='list-mps'),
    'edit-mps': Route(
        r'/multi-period-streams/<mps_name>',
        handler='multi_period_streams.EditStream',
        title='Edit multi-period stream',
        parent='list-mps'),
    "validate-mps": Route(
        r'/multi-period-streams.validate',
        handler='multi_period_streams.ValidateStream',
        title='Check MPS settings are valid',
        parent='list-mps'),
    "mps-manifest": Route(
        r'/mps/<regex("(live|vod)"):mode>/<mps_name>/<manifest>',
        handler='manifest_requests.ServeMultiPeriodManifest',
        title='DASH multi-period manifests'),
    "mps-base-url": Route(
        r'/mps/<regex("(live|vod)"):mode>/<mps_name>/<int:ppk>/',
        handler='generic.NotFound',
        title='Used for generating BaseURL values'),
    "mps-init-seg": Route(
        r'/mps/<regex("(live|vod)"):mode>/<mps_name>/<int:ppk>/<filename>/' +
        r'init.<regex("(mp4|m4v|m4a|m4s)"):ext>',
        handler='media_requests.ServeMpsInitSeg',
        title='Init segments for multi-period streams'),
    "mps-media-seg-by-number": Route(
        r'/mps/<regex("(live|vod)"):mode>/<mps_name>/<int:ppk>/<filename>/' +
        r'<int:segment_num>.<regex("(mp4|m4v|m4a|m4s)"):ext>',
        handler='media_requests.ServeMpsMedia',
        title='media segments for multi-period streams'),
    "mps-media-seg-by-time": Route(
        r'/mps/<regex("(live|vod)"):mode>/<mps_name>/<int:ppk>/<filename>/' +
        r'time/<int:segment_time>.<regex("(mp4|m4v|m4a|m4s)"):ext>',
        handler='media_requests.ServeMpsMedia',
        title='media segments for multi-period streams using timelines'),
    "route-map": Route(
        r'/libs/routemap.js',
        handler='esm.RouteMap',
        title='URL routing data'),
    "content-roles": Route(
        r'/libs/content_roles.js',
        handler='esm.ContentRoles',
        title='MPEG content roles'),
    "spa-bundle": Route(
        r'/libs/bundle/<directory>.js',
        handler='esm.BundleDirectory',
        title='Bundle of JS files'),
    "esm-wrapper": Route(
        r'/libs/<filename>',
        handler='esm.ModuleWrapper',
        title='ESM JavaScript wrapper'),
    "favicon": Route(
        r'/favicon.ico',
        handler='htmlpage.favicon',
        title='favicon'),
    "es5-home": Route(
        r'/es5/',
        handler='htmlpage.ES5MainPage',
        title='DASH test streams'),
    "home": Route(
        r'/',
        handler='htmlpage.MainPage',
        title='DASH test streams'),
}

for name in routes.keys():
    routes[name].name = name
    if name != 'home' and routes[name].parent is None:
        routes[name].parent = 'home'
