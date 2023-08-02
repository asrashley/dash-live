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

from future import standard_library
standard_library.install_aliases()
from builtins import range
import datetime
import urllib.request
import urllib.parse
import urllib.error
import urllib.parse

import flask

from dashlive.server import manifests, models
from dashlive.server.options.cgi_options import get_cgi_options, get_dash_options
from dashlive.drm.playready import PlayReady

from .base import HTMLHandlerBase
from .decorators import uses_stream

class MainPage(HTMLHandlerBase):
    """
    handler for main index page
    """

    def get(self, **kwargs):
        context = self.create_context(**kwargs)
        context.update({
            'rows': [],
            'streams': models.Stream.all(),
        })
        filenames = list(manifests.manifest.keys())
        filenames.sort(key=lambda name: manifests.manifest[name].title)
        for name in filenames:
            url = flask.url_for(
                'dash-mpd-v3',
                manifest=name,
                stream='placeholder',
                mode='live')
            url = url.replace('/placeholder/', '/{directory}/')
            url = url.replace('/live/', '/{mode}/')
            context['rows'].append({
                'filename': name,
                'url': url,
                'manifest': manifests.manifest[name],
                'option': [],
            })
        for idx, opt in enumerate(get_cgi_options(hidden=False, omit_empty=False)):
            try:
                row = context['rows'][idx]
                row['option'] = opt
            except IndexError:
                row = {
                    'manifest': None,
                    'option': opt
                }
                context['rows'].append(row)
        return flask.render_template('index.html', **context)


class CgiOptionsPage(HTMLHandlerBase):
    """
    handler for page that describes each CGI option
    """

    def get(self, **kwargs):
        context = self.create_context(**kwargs)
        context['cgi_options'] = get_cgi_options()
        if flask.request.args.get('json'):
            names: list[str] = []
            option_map = {}
            for opt in get_dash_options():
                names.append(opt.name)
                option_map[opt.name] = opt
            names.sort()
            context['json'] = []
            for name in names:
                context['json'].append(option_map[name])
        return flask.render_template('cgi_options.html', **context)


class VideoPlayer(HTMLHandlerBase):
    """Responds with an HTML page that contains a video element to play the specified MPD"""

    decorators = [uses_stream]

    def get(self, mode, stream, manifest, **kwargs):
        def gen_errors(cgiparam):
            err_time = context['now'].replace(
                microsecond=0) + datetime.timedelta(seconds=20)
            times = []
            for i in range(12):
                err_time += datetime.timedelta(seconds=10)
                times.append(err_time.time().isoformat() + 'Z')
            params.append('%s=%s' %
                          (cgiparam, urllib.parse.quote_plus(','.join(times))))
        manifest += '.mpd'
        context = self.create_context(**kwargs)
        try:
            dash_parms = self.calculate_dash_params(mpd_url=manifest, mode=mode)
        except (KeyError, ValueError) as err:
            return flask.make_response(f'{err}', 404)
        for item in {'periods', 'period', 'ref_representation', 'audio', 'video'}:
            try:
                del dash_parms[item]
            except KeyError:
                pass
        if dash_parms['encrypted']:
            keys = dash_parms['keys']
            for kid in list(keys.keys()):
                item = keys[kid].toJSON()
                item['guidKid'] = PlayReady.hex_to_le_guid(
                    keys[kid].hkid, raw=False)
                item['b64Key'] = keys[kid].KEY.b64
                keys[kid] = item
        context['dash'] = dash_parms
        params = []
        for k, v in flask.request.args.items():
            if k in ['mpd', 'mse']:
                continue
            if isinstance(v, int):
                params.append(f'{k}={v:d}')
            else:
                params.append('{0:s}={1:s}'.format(k, urllib.parse.quote_plus(v)))
        if self.get_bool_param('corruption'):
            gen_errors('vcorrupt')
        for code in self.INJECTED_ERROR_CODES:
            p = 'v{0:03d}'.format(code)
            if self.get_bool_param(p):
                gen_errors(p)
            p = 'a{0:03d}'.format(code)
            if self.get_bool_param(p):
                gen_errors(p)
        mpd_url = flask.url_for(
            'dash-mpd-v3', stream=stream, manifest=manifest, mode=mode)
        if params:
            mpd_url += '?' + '&'.join(params)
        context['source'] = urllib.parse.urljoin(flask.request.host_url, mpd_url)
        context['drm'] = flask.request.args.get("drm", "none")
        if self.is_https_request():
            context['source'] = context['source'].replace(
                'http://', 'https://')
        else:
            if "marlin" in context["drm"] and context['dash']['DRM']['marlin']['laurl']:
                context['source'] = '#'.join([
                    context['dash']['DRM']['marlin']['laurl'],
                    context['source']
                ])
        context['mimeType'] = 'application/dash+xml'
        context['title'] = manifests.manifest[manifest].title
        return flask.render_template('video.html', **context)
