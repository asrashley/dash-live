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
from flask.views import MethodView  # type: ignore
from flask_login import current_user

from dashlive.server import manifests, models
from dashlive.server.options.drm_options import DrmLocation, DrmSelection
from dashlive.server.options.repository import OptionsRepository
from dashlive.server.options.player_options import ShakaVersion, DashjsVersion
from dashlive.server.options.types import OptionUsage
from dashlive.drm.playready import PlayReady

from .base import HTMLHandlerBase
from .decorators import uses_stream, current_stream

class MainPage(HTMLHandlerBase):
    """
    handler for main index page
    """

    def get(self, **kwargs):
        context = self.create_context(**kwargs)
        context.update({
            'rows': [],
            'streams': list(models.Stream.all()),
            'exclude_buttons': True,
        })
        if context['streams']:
            context.update({
                'default_stream': context['streams'][0],
                'default_url': flask.url_for(
                    'dash-mpd-v3', mode='vod', manifest='hand_made.mpd',
                    stream=context['streams'][0].directory),
            })
        defaults = OptionsRepository.get_default_options()
        field_choices = {
            'representation': [
                dict(value=mf.name, title=mf.name) for mf in models.MediaFile.all()],
            'audio_representation': [
                dict(value=mf.name, title=mf.name) for mf in models.MediaFile.search(
                    content_type='audio')],
            'text_representation': [
                dict(value=mf.name, title=mf.name) for mf in models.MediaFile.search(
                    content_type='text')],
        }
        for name in ['representation', 'audio_representation', 'text_representation']:
            field_choices[name].insert(0, {
                'title': '--',
                'value': '',
            })
        context['field_groups'] = defaults.generate_input_field_groups(
            field_choices,
            exclude={'mode', 'dashjsVersion', 'marlin.licenseUrl',
                     'audioErrors', 'manifestErrors', 'textErrors', 'videoErrors',
                     'numPeriods', 'playready.licenseUrl', 'shakaVersion', 'failureCount',
                     'videoCorruption', 'videoCorruptionFrameCount',
                     'updateCount', 'utcValue'})
        dash_options = OptionsRepository.get_cgi_map()
        for idx, group in enumerate(context['field_groups']):
            if idx > 0:
                group.className = 'advanced hidden'
            for field in group.fields:
                field['rowClass'] = 'row advanced hidden'
                try:
                    if dash_options[field['name']].featured:
                        field['rowClass'] = 'row featured'
                except KeyError:
                    pass
        filenames = list(manifests.manifest.keys())
        filenames.sort(key=lambda name: manifests.manifest[name].title)
        context['field_groups'][0].fields.insert(0, {
            "name": "manifest",
            "title": "Manifest",
            "text": "Manifest template to use",
            "type": "select",
            "options": [{
                "title": f'{name}: {manifests.manifest[name].title}',
                "value": name,
                "selected": name == "hand_made.mpd",
            } for name in filenames],
        })
        context['field_groups'][0].fields.insert(0, {
            "name": "stream",
            "title": "Stream",
            "type": "radio",
            "options": [{
                "title": stream.title,
                "value": stream.directory,
                "selected": stream.directory == context['streams'][0].directory,
            } for stream in context['streams']],
        })
        context['field_groups'][0].fields.insert(0, {
            "name": "mode",
            "title": "Playback Mode",
            "type": "radio",
            "options": [{
                "title": 'Video On Demand (using live profile)',
                "value": 'vod',
                "selected": True,
            }, {
                "title": 'Live stream (using live profile)',
                "value": 'live',
                "selected": False,
            }, {
                "title": 'Video On Demand (using on-demand profile)',
                "value": 'odvod',
                "selected": False,
            }],
        })
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
        url = flask.url_for(
            'dash-mpd-v3',
            manifest='manifest',
            stream='directory',
            mode='mode').replace('/manifest', '/{manifest}')
        url = url.replace('/directory/', '/{directory}/')
        url = url.replace('/mode/', '/{mode}/')
        context['url_template'] = url
        extras = [DrmLocation]
        cgi_options = OptionsRepository.get_cgi_options(
            featured=True, omit_empty=False, extras=extras)
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
        if current_stream.timing_reference is None:
            flask.flash(
                f'The timing reference needs to be set for stream "{current_stream.title}"',
                'error')
            return flask.redirect(flask.url_for('home'))
        app_cfg = flask.current_app.config['DASH']
        manifest += '.mpd'
        context = self.create_context(**kwargs)
        try:
            options = self.calculate_options(mode, flask.request.args)
        except ValueError as err:
            logging.error('Invalid CGI parameters: %s', err)
            return flask.make_response(f'Invalid CGI parameters: {err}', 400)
        dash_parms = self.calculate_manifest_params(mpd_url=manifest, options=options)
        for item in {'periods', 'period', 'ref_representation', 'audio', 'video'}:
            try:
                del dash_parms[item]
            except KeyError:
                pass
        if options.encrypted:
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
        mpd_url += options.generate_cgi_parameters_string(use=~OptionUsage.HTML)
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


class ViewManifest(HTMLHandlerBase):
    """
    Responds with an HTML page that shows the contents of a manifest
    """

    decorators = [uses_stream]

    def get(self, mode, stream, manifest, **kwargs):
        context = self.create_context(**kwargs)
        try:
            options = self.calculate_options(mode, flask.request.args)
        except ValueError as err:
            logging.error('Invalid CGI parameters: %s', err)
            return flask.make_response(f'Invalid CGI parameters: {err}', 400)
        mpd_url = flask.url_for(
            'dash-mpd-v3', stream=stream, manifest=manifest, mode=mode)
        options.remove_unused_parameters(mode, use=~OptionUsage.HTML)
        mpd_url += options.generate_cgi_parameters_string()
        context.update({
            'mpd_url': mpd_url,
        })
        return flask.render_template('manifest.html', **context)


class DashValidator(HTMLHandlerBase):
    """
    Responds with an HTML page that allows a manifest to be validated
    """

    def get(self):
        context = self.create_context()
        context['form'] = [{
            "name": "manifest",
            "title": "Manifest to check",
            "type": "url",
            "required": True,
            "placeholder": "... manifest URL ...",
        }, {
            'name': 'duration',
            'title': 'Maximum duration',
            'type': 'number',
            'text': 'seconds',
            'value': 30,
            'min': 1,
            'max': 3600,
        }]
        if current_user.has_permission(models.Group.MEDIA):
            context['form'] += [{
                "name": "prefix",
                "title": "Destination directory",
                "type": "text",
                "disabled": True,
                "pattern": r'[A-Za-z0-9]{3,31}',
                "text": "3 to 31 characters without any special characters",
                "minlength": 3,
                "maxlength": 31,
            }, {
                "name": "title",
                "title": "Stream title",
                "type": "text",
                "disabled": True,
                "minlength": 3,
                "maxlength": 119,
            }]
        context['form'] += [{
            'name': 'encrypted',
            'title': 'Stream is encrypted?',
            'type': 'checkbox',
            'inline': True
        }, {
            'name': 'media',
            'title': 'Check media segments',
            'type': 'checkbox',
            'inline': True,
            'value': True,
        }, {
            'name': 'verbose',
            'title': 'Verbose output',
            'type': 'checkbox',
            'inline': True
        }, {
            'name': 'pretty',
            'title': 'Pretty print XML before validation',
            'type': 'checkbox',
            'inline': True,
            'newRow': True,
        }]
        if current_user.has_permission(models.Group.MEDIA):
            context['form'].append({
                'name': 'save',
                'title': 'Add stream to this server?',
                'type': 'checkbox',
                'inline': True,
            })
        return flask.render_template('validator.html', **context)


class ModuleWrapper(MethodView):
    """
    Handler that is used to wrap conventional JS libraries into ESM modules
    """

    def get(self, filename: str) -> flask.Response:
        headers = {
            'Content-Type': 'application/javascript',
        }
        context = {}
        if 'default' in filename:
            context['defaults'] = OptionsRepository.get_default_options().generate_cgi_parameters(
                exclude={'_type'})
        body = flask.render_template(f'esm/{filename}', **context)
        return flask.make_response((body, 200, headers))

def favicon() -> flask.Response:
    return flask.send_from_directory(
        flask.current_app.static_folder,
        'favicon.ico', mimetype='image/vnd.microsoft.icon', conditional=True)
