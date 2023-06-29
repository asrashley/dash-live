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
import importlib
import re
from typing import Optional

from flask import Flask, request  # type: ignore
from werkzeug.routing import BaseConverter  # type: ignore

class RegexConverter(BaseConverter):
    """
    Utility class to allow a regex to be used in a route path
    """
    def __init__(self, url_map, *items):
        super().__init__(url_map)
        self.regex = items[0]

class Route(object):
    def __init__(self, template: str, handler: str, title: str,
                 parent: Optional["Route"] = None) -> None:
        self.template = template
        self.handler = handler
        self.title = title
        self.parent = parent
        # convert Flask's template syntax in to the Python string.format() syntax
        self.formatTemplate = re.sub(
            r':[^>]*>', '}', template.replace('<', '{'))

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


routes = {
    "del-key": Route(
        r'/key/<kid>',
        handler='keypairs.KeyHandler',
        title='delete key pairs'),
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
    "stream": Route(
        r'/stream',
        handler='streams.StreamHandler',
        title='Add stream'),
    "stream-edit": Route(
        r'/media/edit/<int:spk>',
        handler='streams.EditStreamHandler',
        title='Media information'),
    "uploadBlob": Route(
        r'/blob',
        handler='media_management.UploadHandler',
        title='Upload blob'),
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

def no_api_cache(response):
    """
    Make sure all API calls return no caching directives
    """
    if request.path.startswith('/api/'):
        response.cache_control.max_age = 0
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.cache_control.must_revalidate = True
    return response


def add_routes(app: Flask) -> None:
    app.url_map.converters['regex'] = RegexConverter
    app.after_request(no_api_cache)
    for name, route in routes.items():
        route.name = name
        full_path = f'dashlive.server.requesthandler.{route.handler}'
        pos = full_path.rindex('.')
        module_name = full_path[:pos]
        handler_name = full_path[pos + 1:]
        module = importlib.import_module(module_name)
        view_func = getattr(module, handler_name).as_view(name)
        app.add_url_rule(route.template, endpoint=name,
                         view_func=view_func)
