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

import datetime
import html
import logging
import math
from typing import cast

import flask

from dashlive.mpeg.dash.profiles import primary_profiles
from dashlive.server.models import Stream
from dashlive.server.options.container import OptionsContainer
from dashlive.utils.objects import dict_to_cgi_params
from dashlive.utils.timezone import UTC

from .base import RequestHandlerBase, TemplateContext
from .decorators import (
    uses_stream,
    current_stream,
    uses_manifest,
    current_manifest,
    uses_multi_period_stream,
    current_mps,
)
from .manifest_context import ManifestContext
from .utils import add_allowed_origins

class ManifestTemplateContext(TemplateContext):
    mode: str
    mpd: ManifestContext
    options: OptionsContainer
    stream: Stream

class PatchTemplateContext(TemplateContext):
    mpd: ManifestContext
    options: OptionsContainer
    stream: Stream
    original_publish_time: datetime.datetime

class ServeManifest(RequestHandlerBase):
    """handler for generating MPD files"""

    decorators = [uses_stream, uses_manifest]

    def head(self, **kwargs):
        return self.get(**kwargs)

    def get(self, mode: str, stream: str, manifest: str) -> flask.Response:
        logging.debug('ServeManifest: mode=%s stream=%s manifest=%s', mode, stream, manifest)
        mft = current_manifest
        try:
            options = self.calculate_options(
                mode=mode,
                args=flask.request.args,
                stream=current_stream,
                restrictions=mft.restrictions,
                features=mft.features)
        except ValueError as e:
            logging.info('Invalid CGI parameters: %s', e)
            return flask.make_response('Invalid CGI parameters', 400)
        if mode != 'live':
            # Patch elements are ignored if MPD@type == 'static'
            options.update(patch=False)
        if options.patch and 'segmentTimeline' not in mft.features:
            return flask.make_response(
                f'manifest {html.escape(manifest)} does not SegmentTimeline',
                400)
        if 'segmentTimeline' not in mft.features:
            options.update(segmentTimeline=False)
        elif mft.segment_timeline or options.patch:
            options.update(segmentTimeline=True)
        options.remove_unused_parameters(mode)
        dash = ManifestContext(
            manifest=mft, options=options, stream=current_stream,
            multi_period=None)
        context = cast(ManifestTemplateContext, self.create_context(
            title=current_stream.title, mpd=dash, options=options,
            mode=mode, stream=current_stream))
        response = self.check_for_synthetic_manifest_error(options, context)
        if response is not None:
            return response
        body = flask.render_template(f'manifests/{manifest}', **context)
        try:
            max_age = int(math.floor(context["minimumUpdatePeriod"]))
        except KeyError:
            max_age = 60
        headers = {
            'Content-Type': 'application/dash+xml',
            'Cache-Control': f'max-age={max_age}',
            'Accept-Ranges': 'none',
        }
        add_allowed_origins(headers, methods={'HEAD', 'GET'})
        return flask.make_response((body, 200, headers))

    def check_for_synthetic_manifest_error(
            self,
            options: OptionsContainer,
            context: ManifestTemplateContext) -> flask.Response | None:
        for item in options.manifestErrors:
            code, pos = item
            if isinstance(pos, int):
                if pos != options.updateCount:
                    continue
            else:
                tm = options.availabilityStartTime.replace(
                    hour=pos.hour, minute=pos.minute, second=pos.second)
                tm2 = tm + datetime.timedelta(seconds=options.minimumUpdatePeriod)
                if context['mpd'].now < tm or context['mpd'].now > tm2:
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


class ServeMultiPeriodManifest(RequestHandlerBase):
    decorators = [uses_multi_period_stream, uses_manifest]

    def get(self, mode: str, mps_name: str, manifest: str) -> flask.Response:
        logging.debug(
            'ServeMultiPeriodManifest: mode=%s mps=%s manifest=%s',
            mode, mps_name, manifest)
        try:
            options = self.calculate_options(
                mode=mode,
                args=flask.request.args,
                stream=None,
                restrictions=current_manifest.restrictions,
                features=current_manifest.features)
        except ValueError as e:
            logging.info('Invalid CGI parameters: %s', e)
            return flask.make_response('Invalid CGI parameters', 400)
        dash = ManifestContext(
            manifest=current_manifest, options=options, stream=None,
            multi_period=current_mps)
        context = cast(ManifestTemplateContext, self.create_context(
            title=current_mps.title, mpd=dash, options=options,
            mode=mode))
        body = flask.render_template(f'manifests/{manifest}', **context)
        try:
            max_age = int(math.floor(context["minimumUpdatePeriod"]))
        except KeyError:
            max_age = 60
        headers = {
            'Content-Type': 'application/dash+xml',
            'Cache-Control': f'max-age={max_age}',
            'Accept-Ranges': 'none',
        }
        add_allowed_origins(headers, methods={'GET', 'HEAD'})
        return flask.make_response((body, 200, headers))


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
            return flask.make_response(f'{html.escape(manifest)} not found', 404)

class ServePatch(RequestHandlerBase):
    """
    handler for generating MPD patch files
    """

    decorators = [uses_stream, uses_manifest]

    def get(self,
            stream: str,
            manifest: str,
            publish: int,  # publishTime from Unix epoch
            **kwargs):

        logging.debug(
            'ServePatch: stream=%s manifest=%s', stream, manifest)
        mft = current_manifest

        if 'patch' not in mft.features:
            logging.warning(
                'MPD patches are not supported with manifest %s',
                manifest)
            return flask.make_response(
                f'{html.escape(manifest)} does not support patches', 400)

        if 'segmentTimeline' not in mft.features:
            logging.warning(
                'SegmentTimeline are not supported with manifest %s',
                manifest)
            return flask.make_response(
                f'{html.escape(manifest)} does not support SegmentTimeline',
                400)
        try:
            modes = mft.restrictions['mode']
        except KeyError:
            modes = primary_profiles.keys()
        if 'live' not in modes:
            logging.warning(
                'Live mode not supported with manifest %s (supported=%s)',
                manifest, modes)
            return flask.make_response(
                f'{html.escape(manifest)} live mode not supported',
                400)

        try:
            options = self.calculate_options(
                mode='live', args=flask.request.args, stream=current_stream,
                restrictions=mft.restrictions,
                features=mft.features)
        except ValueError as e:
            logging.info('Invalid CGI parameters: %s', e)
            return flask.make_response('Invalid CGI parameters', 400)

        options.update(patch=True, segmentTimeline=True)
        options.remove_unused_parameters('live')
        original_publish_time = datetime.datetime.fromtimestamp(
            publish, tz=UTC())
        dash = ManifestContext(
            manifest=mft, options=options, stream=current_stream,
            multi_period=None)
        context = cast(PatchTemplateContext, self.create_context(
            title=current_stream.title, mpd=dash, options=options,
            stream=current_stream,
            original_publish_time=original_publish_time))

        body = flask.render_template(f'patches/{manifest}.xml', **context)
        try:
            max_age = int(math.floor(context["minimumUpdatePeriod"]))
        except KeyError:
            max_age = 60
        # MIME type is defined in clause C.5 of DASH specification
        headers = {
            'Content-Type': 'application/dash-patch+xml',
            'Cache-Control': f'max-age={max_age}',
            'Accept-Ranges': 'none',
        }
        add_allowed_origins(headers)
        return flask.make_response((body, 200, headers))
