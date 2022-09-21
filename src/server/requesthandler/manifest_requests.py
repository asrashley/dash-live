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


from .base import RequestHandlerBase
from server import manifests, cgi_options
from server.routes import routes
from templates.factory import TemplateFactory
from utils.date_time import from_isodatetime

class ServeManifest(RequestHandlerBase):
    """handler for generating MPD files"""

    def head(self, **kwargs):
        self.get(**kwargs)

    def get(self, mode, stream, manifest, **kwargs):
        try:
            mft = manifests.manifest[manifest]
        except KeyError:
            logging.debug('Unknown manifest: %s', manifest)
            self.response.write('%s not found' % (manifest))
            self.response.set_status(404)
            return
        modes = mft.restrictions.get('mode', cgi_options.supported_modes)
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
                mpd_url=manifest, prefix=stream, mode=mode)
        except ValueError as e:
            self.response.write('Invalid CGI parameters: %s' % (str(e)))
            self.response.set_status(400)
            return
        context.update(dash)
        if mode == 'live' and self.check_for_synthetic_manifest_error(context):
            return
        template = TemplateFactory.get_template(manifest)
        self.add_allowed_origins()
        self.response.headers.add_header('Accept-Ranges', 'none')
        self.response.write(template.render(context))

    def check_for_synthetic_manifest_error(self, context):
        try:
            num_failures = int(self.request.params.get('failures', '1'), 10)
        except ValueError as err:
            self.response.write('Invalid CGI parameters: %s' % (str(err)))
            self.response.set_status(400)
            return True
        for code in self.INJECTED_ERROR_CODES:
            if self.request.params.get('m%03d' % code) is None:
                continue
            dates = self.request.params.get('m%03d' % code, "").split(',')
            for d in dates:
                try:
                    tm = from_isodatetime(d)
                except ValueError as e:
                    self.response.write(
                        'Invalid CGI parameters: %s' % (str(e)))
                    self.response.set_status(400)
                    return True
                tm = context['availabilityStartTime'].replace(
                    hour=tm.hour, minute=tm.minute, second=tm.second)
                try:
                    tm2 = (tm + datetime.timedelta(
                        seconds=context['minimumUpdatePeriod']))
                except KeyError:
                    tm2 = (tm + datetime.timedelta(
                        seconds=context['minimumUpdatePeriod']))
                if context['now'] >= tm and context['now'] <= tm2:
                    if code < 500 or self.increment_memcache_counter(0, code) <= num_failures:
                        self.response.write(
                            'Synthetic %d for manifest' % (code))
                        self.response.set_status(code)
                        return True
        return False


class LegacyManifestUrl(ServeManifest):
    legacy_manifest_names = {
        'hand_made.mpd': ('hand_made.mpd', {}),
        'enc.mpd': ('hand_made.mpd', {'drm': 'all'}),
        'manifest_vod.mpd': ('hand_made.mpd', {'mode': 'vod'}),
    }

    def head(self, manifest, **kwargs):
        return self.get(manifest, **kwargs)

    def get(self, manifest, **kwargs):
        try:
            name, params = self.legacy_manifest_names[manifest]
            stream = kwargs.get("stream", "bbb")
            mode = self.request.params.get("mode", "vod")
            url = self.uri_for('dash-mpd-v3', manifest=name,
                               stream=stream, mode=mode)
            params.update(self.request.params)
            url += dict_to_cgi_params(params)
            self.redirect(url)
        except KeyError:
            logging.debug('Unknown manifest: %s', manifest)
            self.response.write('%s not found' % (manifest))
            self.response.set_status(404)
