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
import urllib
import urlparse

from server import manifests, models, cgi_options
from drm.playready import PlayReady
from templates.factory import TemplateFactory

from .base import HTMLHandlerBase

class MainPage(HTMLHandlerBase):
    """
    handler for main index page
    """

    def get(self, **kwargs):
        context = self.create_context(**kwargs)
        context.update({
            'audio_fields': [
                'id', 'mimeType', 'codecs', 'bitrate', 'sampleRate', 'numChannels',
                'lang', 'encrypted'
            ],
            'audio_representations': [],
            'keys': models.Key.all_as_dict(),
            'rows': [],
            'streams': models.Stream.all(),
            'video_fields': [
                'id', 'mimeType', 'codecs', 'bitrate', 'width', 'height', 'encrypted'
            ],
            'video_representations': [],
            'text_fields': [
                'id', 'mimeType', 'codecs', 'bitrate', 'lang', 'encrypted'
            ],
            'text_representations': [],
        })
        for mf in models.MediaFile.all():
            r = mf.representation
            if r is None:
                continue
            if r.contentType == "video":
                context['video_representations'].append(r)
            elif r.contentType == "audio":
                context['audio_representations'].append(r)
            elif r.contentType == "text":
                context['text_representations'].append(r)
        context['video_representations'].sort(key=lambda r: r.filename)
        context['audio_representations'].sort(key=lambda r: r.filename)
        context['text_representations'].sort(key=lambda r: r.filename)
        filenames = manifests.manifest.keys()
        filenames.sort(key=lambda name: manifests.manifest[name].title)
        for name in filenames:
            url = self.uri_for('dash-mpd-v3', manifest=name,
                               stream='placeholder', mode='live')
            url = url.replace('/placeholder/', '/{directory}/')
            url = url.replace('/live/', '/{mode}/')
            context['rows'].append({
                'filename': name,
                'url': url,
                'manifest': manifests.manifest[name],
                'option': [],
            })
        for idx, opt in enumerate(cgi_options.cgi_options):
            try:
                row = context['rows'][idx]
                row['option'] = opt
            except IndexError:
                row = {
                    'manifest': None,
                    'option': opt
                }
                context['rows'].append(row)
        template = TemplateFactory.get_template('index.html')
        self.response.write(template.render(context))


class CgiOptionsPage(HTMLHandlerBase):
    """
    handler for page that describes each CGI option
    """

    def get(self, **kwargs):
        context = self.create_context(**kwargs)
        template = TemplateFactory.get_template('cgi_options.html')
        self.response.write(template.render(context))


class VideoPlayer(HTMLHandlerBase):
    """Responds with an HTML page that contains a video element to play the specified MPD"""

    def get(self, mode, stream, manifest, **kwargs):
        def gen_errors(cgiparam):
            err_time = context['now'].replace(
                microsecond=0) + datetime.timedelta(seconds=20)
            times = []
            for i in range(12):
                err_time += datetime.timedelta(seconds=10)
                times.append(err_time.time().isoformat() + 'Z')
            params.append('%s=%s' %
                          (cgiparam, urllib.quote_plus(','.join(times))))
        manifest += '.mpd'
        context = self.create_context(**kwargs)
        try:
            dash_parms = self.calculate_dash_params(
                mpd_url=manifest, mode=mode, prefix=stream)
        except (KeyError, ValueError) as err:
            self.response.write(err)
            self.response.set_status(404)
            return
        for item in {'periods', 'period', 'ref_representation', 'audio', 'video'}:
            try:
                del dash_parms[item]
            except KeyError:
                pass
        if dash_parms['encrypted']:
            keys = dash_parms['keys']
            for kid in keys.keys():
                item = keys[kid].toJSON()
                item['guidKid'] = PlayReady.hex_to_le_guid(
                    keys[kid].hkid, raw=False)
                item['b64Key'] = keys[kid].KEY.b64
                keys[kid] = item
        context['dash'] = dash_parms
        params = []
        for k, v in self.request.params.iteritems():
            if k in ['mpd', 'mse']:
                continue
            if isinstance(v, (int, long)):
                params.append('%s=%d' % (k, v))
            else:
                params.append('%s=%s' % (k, urllib.quote_plus(v)))
        if self.get_bool_param('corruption'):
            gen_errors('vcorrupt')
        for code in self.INJECTED_ERROR_CODES:
            p = 'v%03d' % code
            if self.get_bool_param(p):
                gen_errors(p)
            p = 'a%03d' % code
            if self.get_bool_param(p):
                gen_errors(p)
        mpd_url = self.uri_for('dash-mpd-v3', stream=stream, manifest=manifest,
                               mode=mode)
        if params:
            mpd_url += '?' + '&'.join(params)
        context['source'] = urlparse.urljoin(self.request.host_url, mpd_url)
        context['drm'] = self.request.get("drm", "none")
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
        template = TemplateFactory.get_template('video.html')
        self.response.write(template.render(context))
