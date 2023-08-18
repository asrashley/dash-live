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

import logging
import urllib.request
import urllib.parse
import urllib.error
import urllib.parse

import flask

from dashlive.server import manifests, models
from dashlive.server.options.drm_options import DrmLocation, DrmSelection
from dashlive.server.options.repository import OptionsRepository
from dashlive.server.options.player_options import ShakaVersion, DashjsVersion
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
        extras = [DrmLocation]
        cgi_options = OptionsRepository.get_cgi_options(
            hidden=False, omit_empty=False, extras=extras)
        for idx, opt in enumerate(cgi_options):
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
        def sort_fn(item) -> str:
            value = getattr(item, sort_key)
            if isinstance(value, list):
                return value[0]
            return value

        context = self.create_context(**kwargs)
        context['cgi_options'] = OptionsRepository.get_cgi_options()
        if flask.request.args.get('json'):
            sort_key = flask.request.args.get('sort', 'short_name')
            sort_order = self.get_bool_param('order')
            context['json'] = []
            for opt in OptionsRepository.get_dash_options():
                context['json'].append(opt)
            context['json'].sort(key=sort_fn, reverse=sort_order)
            context['sort_key'] = sort_key
            context['sort_order'] = sort_order
            context['reverse_order'] = '0' if sort_order else '1'
        return flask.render_template('cgi_options.html', **context)


class VideoPlayer(HTMLHandlerBase):
    """
    Responds with an HTML page that contains a video element to play the specified MPD
    """

    SHAKA_CDN_TEMPLATE = r'https://ajax.googleapis.com/ajax/libs/shaka-player/{shakaVersion}/shaka-player.compiled.js'
    DASHJS_CDN_TEMPLATE = r'https://cdn.dashjs.org/{dashjsVersion}/dash.all.min.js'

    decorators = [uses_stream]

    def get(self, mode, stream, manifest, **kwargs):
        app_cfg = flask.current_app.config['DASH']
        manifest += '.mpd'
        context = self.create_context(**kwargs)
        try:
            options = self.calculate_options(mode)
        except ValueError as err:
            logging.error('Invalid CGI parameters: %s', err)
            return flask.make_response(f'Invalid CGI parameters: {err}', 400)
        dash_parms = self.calculate_dash_params(mpd_url=manifest, options=options)
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
        mpd_url = flask.url_for(
            'dash-mpd-v3', stream=stream, manifest=manifest, mode=mode)
        options.remove_unused_parameters(mode)
        mpd_url += options.generate_cgi_parameters_string()
        context.update({
            'dashjsUrl': None,
            'drm': None,
            'mimeType': 'application/dash+xml',
            'source': urllib.parse.urljoin(flask.request.host_url, mpd_url),
            'shakaUrl': None,
            'title': manifests.manifest[manifest].title,
            'videoPlayer': options.videoPlayer,
        })
        if options.drmSelection:
            context['drm'] = DrmSelection.to_string(options.drmSelection)
        if options.videoPlayer == 'dashjs':
            if options.dashjsVersion is None:
                options.dashjsVersion = DashjsVersion.cgi_choices[1]
            if options.dashjsVersion in set(DashjsVersion.cgi_choices):
                context['dashjsUrl'] = flask.url_for(
                    'static', filename=f'js/prod/dashjs-{options.dashjsVersion}.js')
            else:
                cdn_template = app_cfg.get('DASHJS_CDN_TEMPLATE', VideoPlayer.DASHJS_CDN_TEMPLATE)
                context['dashjsUrl'] = cdn_template.format(dashjsVersion=options.dashjsVersion)
        else:
            if options.shakaVersion is None:
                options.shakaVersion = ShakaVersion.cgi_choices[1]
            if options.shakaVersion in set(ShakaVersion.cgi_choices):
                context['shakaUrl'] = flask.url_for(
                    'static', filename=f'js/prod/shaka-player.{options.shakaVersion}.js')
            else:
                cdn_template = app_cfg.get('SHAKA_CDN_TEMPLATE', VideoPlayer.SHAKA_CDN_TEMPLATE)
                context['shakaUrl'] = cdn_template.format(shakaVersion=options.shakaVersion)
        if self.is_https_request():
            context['source'] = context['source'].replace(
                'http://', 'https://')
        else:
            if (
                    context["drm"] and
                    "marlin" in context["drm"] and
                    context['dash']['DRM']['marlin']['laurl']
            ):
                context['source'] = '#'.join([
                    context['dash']['DRM']['marlin']['laurl'],
                    context['source']
                ])
        return flask.render_template('video.html', **context)
