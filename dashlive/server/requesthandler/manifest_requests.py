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

from builtins import str
import datetime
import logging
from typing import Optional

import flask

from dashlive.mpeg.dash.profiles import primary_profiles
from dashlive.server import manifests
from dashlive.server.models import Stream
from dashlive.server.options.container import OptionsContainer
from dashlive.utils.objects import dict_to_cgi_params

from .base import RequestHandlerBase
from .decorators import uses_stream

class ServeManifest(RequestHandlerBase):
    """handler for generating MPD files"""

    decorators = [uses_stream]

    def head(self, **kwargs):
        return self.get(**kwargs)

    def get(self, mode: str, stream: str, manifest: str, **kwargs) -> flask.Response:
        logging.debug('ServeManifest: mode=%s stream=%s manifest=%s', mode, stream, manifest)
        try:
            mft = manifests.manifest[manifest]
        except KeyError as err:
            logging.debug('Unknown manifest: %s (%s)', manifest, err)
            return flask.make_response(f'{manifest} not found', 404)
        try:
            modes = mft.restrictions['mode']
        except KeyError:
            modes = primary_profiles.keys()
        if mode not in modes:
            logging.debug(
                'Mode %s not supported with manifest %s', mode, manifest)
            return flask.make_response(f'{manifest} not found', 404)
        context = self.create_context(**kwargs)
        try:
            options = self.calculate_options(mode)
        except ValueError as e:
            return flask.make_response(f'Invalid CGI parameters: {e}', 400)
        options.mode = mode
        options.remove_unused_parameters(mode)
        dash = self.calculate_dash_params(mpd_url=manifest, options=options)
        context.update(dash)
        response = self.check_for_synthetic_manifest_error(options, context)
        if response is not None:
            return response
        body = flask.render_template(f'manifests/{manifest}', **context)
        headers = {
            'Content-Type': 'application/dash+xml',
            'Accept-Ranges': 'none',
        }
        self.add_allowed_origins(headers)
        return flask.make_response((body, 200, headers))

    def check_for_synthetic_manifest_error(self, options: OptionsContainer,
                                           context: dict) -> Optional[flask.Response]:
        for item in options.manifestErrors:
            code, pos = item
            if isinstance(pos, int):
                if pos != options.updateCount:
                    continue
            else:
                tm = options.availabilityStartTime.replace(
                    hour=pos.hour, minute=pos.minute, second=pos.second)
                tm2 = tm + datetime.timedelta(seconds=options.minimumUpdatePeriod)
                if context['now'] < tm or context['now'] > tm2:
                    continue
            if (
                    code >= 500 and
                    options.failureCount is not None and
                    self.increment_error_counter('manifest', code) > options.failureCount
            ):
                self.reset_error_counter('manifest', code)
                continue
            return flask.make_response(f'Synthetic {code} for manifest', code)
        return None


class LegacyManifestUrl(ServeManifest):
    legacy_manifest_names = {
        'hand_made.mpd': ('hand_made.mpd', {}),
        'enc.mpd': ('hand_made.mpd', {'drm': 'all'}),
        'manifest_vod.mpd': ('hand_made.mpd', {'mode': 'vod'}),
    }

    decorators = []

    def head(self, manifest, **kwargs):
        return self.get(manifest, **kwargs)

    def get(self, manifest, **kwargs):
        try:
            name, init_params = self.legacy_manifest_names[manifest]
            directory = kwargs.get("stream", "bbb")
            stream = Stream.get(directory=directory)
            if stream is None:
                search = Stream.search(max_items=1)
                if search:
                    stream = search[0]
            if stream is None:
                return flask.make_response('Not found', 404)
            mode = flask.request.args.get("mode", "vod")
            url = flask.url_for(
                'dash-mpd-v3', manifest=name,
                stream=stream.directory, mode=mode)
            params = dict(**init_params)
            params.update(flask.request.args)
            url += dict_to_cgi_params(params)
            return flask.redirect(url)
        except KeyError:
            logging.debug('Unknown manifest: %s', manifest)
            return flask.make_response(f'{manifest} not found', 404)
