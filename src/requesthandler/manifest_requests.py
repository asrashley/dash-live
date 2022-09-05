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
import logging
import re

import manifests
import options
import utils

from .base import RequestHandlerBase
from .templates import templates

from events import EventFactory
from routes import routes

class ServeManifest(RequestHandlerBase):
    """handler for generating MPD files"""

    def head(self, mode, stream, manifest, **kwargs):
        self.get(mode, stream, manifest, **kwargs)

    def get(self, mode, stream, manifest, **kwargs):
        if manifest in self.legacy_manifest_names:
            manifest = self.legacy_manifest_names[manifest]
        try:
            mft = manifests.manifest[manifest]
        except KeyError:
            logging.debug('Unknown manifest: %s', manifest)
            self.response.write('%s not found' % (manifest))
            self.response.set_status(404)
            return
        modes = mft.restrictions.get('mode', options.supported_modes)
        if mode not in modes:
            logging.debug(
                'Mode %s not supported with manifest %s', mode, manifest)
            self.response.write('%s not found' % (manifest))
            self.response.set_status(404)
            return
        context = self.create_context(**kwargs)
        context["headers"] = []
        context['routes'] = routes
        self.response.content_type = 'application/dash+xml'
        try:
            dash = self.calculate_dash_params(
                mpd_url=manifest, stream=stream, mode=mode, **kwargs)
        except ValueError as e:
            self.response.write('Invalid CGI parameters: %s' % (str(e)))
            self.response.set_status(400)
            return
        context.update(dash)
        context['abr'] = self.request.params.get('abr', "True")
        context['abr'] = re.search(r'(True|0)', context['abr'], re.I)
        # context['availabilityStartTime'] = datetime.datetime.utcfromtimestamp(dash['availabilityStartTime'])
        if re.search(r'(True|0)', self.request.params.get(
                'base', 'False'), re.I) is not None:
            del context['baseURL']
            if mode == 'odvod':
                prefix = self.uri_for(
                    'dash-od-media', filename='RepresentationID', ext='m4v')
                prefix = prefix.replace('RepresentationID.m4v', '')
            else:
                prefix = self.uri_for('dash-media', mode=mode, filename='RepresentationID',
                                      segment_num='init', ext='m4v')
                prefix = prefix.replace('RepresentationID/init.m4v', '')
                context['video']['initURL'] = prefix + \
                    context['video']['initURL']
                context['audio']['initURL'] = prefix + \
                    context['audio']['initURL']
            context['video']['mediaURL'] = prefix + \
                context['video']['mediaURL']
            context['audio']['mediaURL'] = prefix + \
                context['audio']['mediaURL']
        if context['abr'] is False:
            context['video']['representations'] = context['video']['representations'][-1:]
        if mode == 'live':
            try:
                context['minimumUpdatePeriod'] = float(self.request.params.get(
                    'mup', 2.0 * context['video'].get('maxSegmentDuration', 1)))
            except ValueError:
                context['minimumUpdatePeriod'] = 2.0 * \
                    context['video'].get('maxSegmentDuration', 1)
            if context['minimumUpdatePeriod'] <= 0:
                del context['minimumUpdatePeriod']
        for code in self.INJECTED_ERROR_CODES:
            if self.request.params.get('m%03d' % code) is not None:
                try:
                    num_failures = int(
                        self.request.params.get('failures', '1'), 10)
                    for d in self.request.params.get(
                            'm%03d' % code).split(','):
                        tm = utils.from_isodatetime(d)
                        tm = dash['availabilityStartTime'].replace(
                            hour=tm.hour, minute=tm.minute, second=tm.second)
                        try:
                            tm2 = tm + \
                                datetime.timedelta(
                                    seconds=context['minimumUpdatePeriod'])
                        except KeyError:
                            tm2 = tm + \
                                datetime.timedelta(
                                    seconds=context['minimumUpdatePeriod'])
                        if dash['now'] >= tm and dash['now'] <= tm2:
                            if code < 500 or self.increment_memcache_counter(
                                    0, code) <= num_failures:
                                self.response.write(
                                    'Synthetic %d for manifest' % (code))
                                self.response.set_status(code)
                                return
                except ValueError as e:
                    self.response.write(
                        'Invalid CGI parameters: %s' % (str(e)))
                    self.response.set_status(400)
                    return
        event_generators = EventFactory.create_event_generators(self.request)
        if event_generators:
            for evgen in event_generators:
                stream = evgen.create_manifest_context(
                    context=context, templates=templates)
                if evgen.inband:
                    # TODO: allow AdaptationSet for inband events to be
                    # configurable
                    if 'video' in context:
                        try:
                            context['video']['event_streams'].append(stream)
                        except KeyError:
                            context['video']['event_streams'] = [stream]
                else:
                    try:
                        context['period']['event_streams'].append(stream)
                    except KeyError:
                        context['period']['event_streams'] = [stream]
        template = templates.get_template(manifest)
        self.add_allowed_origins()
        self.response.headers.add_header('Accept-Ranges', 'none')
        self.response.write(template.render(context))


class LegacyManifestUrl(ServeManifest):
    def head(self, manifest, **kwargs):
        stream = kwargs.get("stream", "bbb")
        mode = self.request.params.get("mode", "live")
        return super(LegacyManifestUrl, self).head(mode=mode, stream=stream,
                                                   manifest=manifest, **kwargs)

    def get(self, manifest, **kwargs):
        try:
            stream = kwargs["stream"]
            del kwargs["stream"]
        except KeyError:
            stream = "bbb"
        mode = self.request.params.get("mode", "live")
        return super(LegacyManifestUrl, self).get(mode=mode, stream=stream,
                                                  manifest=manifest, **kwargs)
