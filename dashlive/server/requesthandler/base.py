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

from abc import abstractmethod
from typing import AbstractSet, Any, TypeAlias

import base64
import datetime
import hashlib
import hmac
import logging
from os import environ
import re
import secrets
import urllib.request
import urllib.parse
import urllib.error
import urllib.parse

import flask  # type: ignore
from flask.views import MethodView  # type: ignore
from flask_login import current_user

from dashlive.mpeg.dash.adaptation_set import AdaptationSet
from dashlive.mpeg.dash.period import Period
from dashlive.mpeg.dash.profiles import primary_profiles, additional_profiles
from dashlive.mpeg.dash.representation import Representation
from dashlive.mpeg.dash.timing import DashTiming
from dashlive.drm.base import DrmBase
from dashlive.drm.clearkey import ClearKey
from dashlive.drm.playready import PlayReady
from dashlive.drm.marlin import Marlin
from dashlive.server import manifests, models
from dashlive.server.events.factory import EventFactory
from dashlive.server.routes import routes, Route
from dashlive.server.options.container import OptionsContainer
from dashlive.server.options.repository import OptionsRepository
from dashlive.server.options.types import OptionUsage
from dashlive.utils import objects
from dashlive.utils.date_time import scale_timedelta, to_iso_datetime
from dashlive.utils.json_object import JsonObject
from dashlive.utils.timezone import UTC

from .decorators import current_stream, is_ajax
from .exceptions import CsrfFailureException

DrmLocationTuple: TypeAlias = tuple[str, DrmBase, set[str]]

class RequestHandlerBase(MethodView):
    CLIENT_COOKIE_NAME = 'dash'
    CSRF_COOKIE_NAME = 'csrf'
    CSRF_EXPIRY = 1200
    DEFAULT_ALLOWED_DOMAINS = re.compile(
        r'^http://(dashif\.org)|(shaka-player-demo\.appspot\.com)|(mediapm\.edgesuite\.net)')
    INJECTED_ERROR_CODES = [404, 410, 503, 504]

    def create_context(self, **kwargs):
        context = {
            "http_protocol": flask.request.scheme,
        }
        context.update(kwargs)
        if current_user.is_authenticated:
            context["is_current_user_admin"] = current_user.is_admin
        context['remote_addr'] = flask.request.remote_addr
        context['request_uri'] = flask.request.url
        if self.is_https_request():
            context['request_uri'] = context['request_uri'].replace(
                'http://', 'https://')
        return context

    def generate_csrf_cookie(self) -> str:
        """
        generate a secure cookie if not already present
        """
        try:
            csrf_key = flask.request.cookies[self.CSRF_COOKIE_NAME]
        except KeyError:
            csrf_key = None
        if csrf_key is None:
            csrf_key = secrets.token_urlsafe(models.Token.CSRF_KEY_LENGTH)

            @flask.after_this_request
            def set_csrf_cookie(response):
                response.set_cookie(
                    self.CSRF_COOKIE_NAME, csrf_key, httponly=True,
                    max_age=self.CSRF_EXPIRY)
                return response

        return csrf_key

    def generate_csrf_token(self, service: str, csrf_key: str) -> str:
        """
        generate a CSRF token that can be used as a hidden form field
        """
        logging.debug(f'generate_csrf service: "{service}"')
        logging.debug(f'generate_csrf csrf_key: "{csrf_key}"')
        # logging.debug(f'generate_csrf URL: {url}')
        # logging.debug(
        # 'generate_csrf User-Agent: "{}"'.format(flask.request.headers['User-Agent']))
        cfg = flask.current_app.config['DASH']
        sig = hmac.new(
            bytes(cfg['CSRF_SECRET'], 'utf-8'),
            bytes(csrf_key, 'utf-8'),
            hashlib.sha1)
        cur_url = urllib.parse.urlparse(flask.request.url, 'http')
        origin = '{}://{}'.format(cur_url.scheme, cur_url.netloc)
        logging.debug(f'generate_csrf origin: "{origin}"')
        salt = secrets.token_urlsafe(models.Token.CSRF_SALT_LENGTH)
        salt = salt[:models.Token.CSRF_SALT_LENGTH]
        logging.debug(f'generate_csrf salt: "{salt}"')
        # print('generate', service, csrf_key, origin, flask.request.headers['User-Agent'], salt)
        sig.update(bytes(service, 'utf-8'))
        sig.update(bytes(origin, 'utf-8'))
        # sig.update(flask.request.url)
        # sig.update(bytes(flask.request.headers['User-Agent'], 'utf-8'))
        sig.update(bytes(salt, 'utf-8'))
        rv = urllib.parse.quote(salt + str(base64.b64encode(sig.digest())))
        # print('csrf', service, rv)
        return rv

    def check_csrf(self, service, params):
        """
        check that the CSRF token from the cookie and the submitted form match
        """
        logging.debug(f'check_csrf service: "{service}"')
        try:
            csrf_key = flask.request.cookies[self.CSRF_COOKIE_NAME]
        except KeyError:
            logging.debug("csrf cookie not present")
            logging.debug(str(flask.request.cookies))
            raise CsrfFailureException(
                f"{self.CSRF_COOKIE_NAME} cookie not present")
        if not csrf_key:
            logging.debug("csrf deserialize failed")

            @flask.after_this_request
            def clear_csrf_cookie(response):
                response.delete_cookie(self.CSRF_COOKIE_NAME)
                return response

            raise CsrfFailureException("csrf cookie not valid")
        logging.debug(f'check_csrf csrf_key: "{csrf_key}"')
        try:
            token = str(urllib.parse.unquote(params['csrf_token']))
        except KeyError:
            raise CsrfFailureException("csrf_token not present")
        try:
            origin = flask.request.headers['Origin']
        except KeyError:
            logging.debug(
                f"No origin in request, using: {flask.request.url}")
            cur_url = urllib.parse.urlparse(flask.request.url, 'http')
            origin = '{}://{}'.format(cur_url.scheme, cur_url.netloc)
        logging.debug(f'check_csrf origin: "{origin}"')
        existing_key = models.Token.get(jti=token,
                                        token_type=models.TokenType.CSRF)
        if existing_key is not None:
            raise CsrfFailureException("Re-use of csrf_token")
        expires = datetime.datetime.now() + datetime.timedelta(seconds=self.CSRF_EXPIRY)
        existing_key = models.Token(
            jti=token, token_type=models.TokenType.CSRF,
            expires=expires, revoked=False)
        models.db.session.add(existing_key)
        salt = token[:models.Token.CSRF_SALT_LENGTH]
        logging.debug(f'check_csrf salt: "{salt}"')
        token = token[models.Token.CSRF_SALT_LENGTH:]
        cfg = flask.current_app.config['DASH']
        sig = hmac.new(
            bytes(cfg['CSRF_SECRET'], 'utf-8'),
            bytes(csrf_key, 'utf-8'),
            hashlib.sha1)
        sig.update(bytes(service, 'utf-8'))
        sig.update(bytes(origin, 'utf-8'))
        # logging.debug("check_csrf Referer: {}".format(flask.request.headers['Referer']))
        # sig.update(flask.request.headers['Referer'])
        # sig.update(bytes(flask.request.headers['User-Agent'], 'utf-8'))
        sig.update(bytes(salt, 'utf-8'))
        b64_sig = str(base64.b64encode(sig.digest()))
        # sig_hex = sig.hexdigest()
        # tk_hex = binascii.b2a_hex(base64.b64decode(token))
        if token != b64_sig:
            logging.debug("signatures do not match: %s %s", token, b64_sig)
            raise CsrfFailureException("signatures do not match")
        return True

    def get_bool_param(self, param: str, default: bool | None = False) -> bool:
        value = flask.request.args.get(param)
        if value is None:
            value = flask.request.form.get(param)
        if value is None:
            return default
        return value.lower() in {"1", "true", "on"}

    @staticmethod
    def drm_locations_for_drm(drm: str) -> set[str]:
        if drm == 'playready':
            return {'pro', 'cenc', 'moov'}
        if drm == 'clearkey':
            return {'cenc', 'moov'}
        return {'cenc'}

    def generate_drm_location_tuples(self, options: OptionsContainer) -> list[DrmLocationTuple]:
        """
        Returns list of tuples, where each entry is:
          * DRM name,
          * DRM implementation, and
          * DRM data locations
        """
        rv = []
        for drm_name, locations in options.drmSelection:
            assert drm_name in {'playready', 'marlin', 'clearkey'}
            if drm_name == 'playready':
                drm = PlayReady()
            elif drm_name == 'marlin':
                drm = Marlin()
            elif drm_name == 'clearkey':
                drm = ClearKey()
            rv.append((drm_name, drm, locations,))
        return rv

    def generate_drm_dict(self, stream: str | models.Stream,
                          keys: dict | list, options: OptionsContainer) -> dict:
        """
        Generate contexts for all enabled DRM systems. It returns a
        dictionary with an entry for each DRM system.
        """
        if isinstance(stream, str):
            stream = models.Stream.get(directory=stream)
            assert stream is not None
        rv = {}
        drm_tuples = self.generate_drm_location_tuples(options)
        for drm_name, drm, locations in drm_tuples:
            la_url = flask.request.args.get(f'{drm_name}_la_url')
            rv[drm_name] = drm.generate_manifest_context(
                stream, keys, getattr(options, drm_name),
                https_request=self.is_https_request(),
                la_url=la_url, locations=locations)
        return rv

    def calculate_options(self,
                          mode: str,
                          args: dict[str, str],
                          stream: models.Stream | None = None,
                          features: AbstractSet[str] | None = None,
                          restrictions: dict[str, tuple] | None = None) -> OptionsContainer:
        defaults = OptionsRepository.get_default_options()
        if stream is not None:
            if stream.defaults is not None:
                defaults = defaults.clone(**stream.defaults)
        if restrictions is not None:
            args = {**args}
            for key, allowed_values in restrictions.items():
                try:
                    value = args[key]
                    if value not in allowed_values:
                        if len(allowed_values) == 1:
                            args[key] = list(allowed_values)[0]
                        else:
                            del args[key]
                except KeyError:
                    pass
        options = OptionsRepository.convert_cgi_options(args, defaults=defaults)
        if features is not None:
            options.remove_unsupported_features(features)
        options.add_field('mode', mode)
        return options

    def calculate_manifest_params(self, mpd_url: str,
                                  options: OptionsContainer,
                                  stream: models.Stream | None = None) -> dict:
        if mpd_url is None:
            raise ValueError("Unable to determin MPD URL")
        if stream is None:
            stream = current_stream
        if not bool(stream):
            raise ValueError('Stream model is not available')
        manifest_info = manifests.manifest[mpd_url]
        now = datetime.datetime.now(tz=UTC())
        if options.clockDrift:
            now -= datetime.timedelta(seconds=options.clockDrift)
        rv = {
            "DRM": {},
            "minBufferTime": datetime.timedelta(seconds=1.5),
            "mode": options.mode,
            "mpd_url": mpd_url,
            "now": now,
            "options": options,
            "periods": [],
            'profiles': [primary_profiles[options.mode]],
            "startNumber": 1,
            "stream": stream.to_dict(exclude={'media_files'}),
            "suggestedPresentationDelay": 30,
            "timing_ref": stream.timing_reference,
        }
        if options.mode != 'odvod':
            rv['profiles'].append(additional_profiles['dvb'])
        encrypted = options.encrypted
        period = Period(start=datetime.timedelta(0), id="p0")
        audio_adps = self.calculate_audio_adaptation_sets(stream, options)
        text_adps = self.calculate_text_adaptation_sets(stream, options)
        max_items = None
        if options.abr is False:
            max_items = 1
        video = self.calculate_video_adaptation_set(stream, options, max_items=max_items)

        timing = DashTiming(now, rv["timing_ref"], options)
        options.availabilityStartTime = timing.availabilityStartTime
        options.timeShiftBufferDepth = timing.timeShiftBufferDepth
        rv.update(timing.generate_manifest_context())
        cgi_params = self.calculate_cgi_parameters(
            options=options, now=now, audio=audio_adps, video=video)
        video.append_cgi_params(cgi_params['video'])
        for audio in audio_adps:
            audio.append_cgi_params(cgi_params['audio'])
        for text in text_adps:
            text.append_cgi_params(cgi_params['text'])
        if cgi_params['manifest']:
            locationURL = flask.request.url
            if '?' in locationURL:
                locationURL = locationURL[:flask.request.url.index('?')]
            locationURL = locationURL + objects.dict_to_cgi_params(cgi_params['manifest'])
            rv["locationURL"] = locationURL
        event_generators = EventFactory.create_event_generators(options)
        for evgen in event_generators:
            ev_stream = evgen.create_manifest_context(context=rv)
            if evgen.inband:
                # TODO: allow AdaptationSet for inband events to be
                # configurable
                video.event_streams.append(ev_stream)
            else:
                period.event_streams.append(ev_stream)
        period.adaptationSets.append(video)
        period.adaptationSets += audio_adps
        period.adaptationSets += text_adps
        prefix = ''
        if options.useBaseUrls:
            if options.mode == 'odvod':
                rv["baseURL"] = urllib.parse.urljoin(
                    flask.request.host_url, f'/dash/vod/{stream.directory}') + '/'
            else:
                rv["baseURL"] = urllib.parse.urljoin(
                    flask.request.host_url, f'/dash/{options.mode}/{stream.directory}') + '/'
            if self.is_https_request():
                rv["baseURL"] = rv["baseURL"].replace('http://', 'https://')
        else:
            # convert every initURL and mediaURL to be an absolute URL
            if options.mode == 'odvod':
                prefix = flask.url_for(
                    'dash-od-media',
                    stream=stream.directory,
                    filename='RepresentationID',
                    ext='m4v')
                prefix = prefix.replace('RepresentationID.m4v', '')
            else:
                prefix = flask.url_for(
                    'dash-media',
                    mode=options.mode,
                    stream=stream.directory,
                    filename='RepresentationID',
                    segment_num='init',
                    ext='m4v')
                prefix = prefix.replace('RepresentationID/init.m4v', '')
        kids = set()
        rv["maxSegmentDuration"] = 0
        for idx, adp in enumerate(period.adaptationSets):
            adp.id = idx + 1
            if options.mode != 'odvod':
                adp.initURL = prefix + adp.initURL
            adp.mediaURL = prefix + adp.mediaURL
            adp.set_dash_timing(timing)
            rv["maxSegmentDuration"] = max(
                rv["maxSegmentDuration"], adp.maxSegmentDuration)
            for rep in adp.representations:
                if rep.encrypted:
                    kids.update(rep.kids)

        rv["periods"].append(period)
        rv["kids"] = kids
        rv["mediaDuration"] = rv["timing_ref"].media_duration_timedelta().total_seconds()
        if encrypted:
            if not kids:
                rv["keys"] = models.Key.all_as_dict()
            else:
                rv["keys"] = models.Key.get_kids(kids)
            rv["DRM"] = self.generate_drm_dict(stream, rv["keys"], options)
        rv["timeSource"] = self.choose_time_source_method(options, cgi_params, now)
        if 'numPeriods' not in manifest_info.features:
            rv["video"] = video  # TODO: support multiple video tracks
            rv["audio_sets"] = audio_adps
            rv["text_sets"] = text_adps
            rv["period"] = rv["periods"][0]
        return rv

    def calculate_audio_adaptation_sets(
            self,
            stream: models.Stream,
            options: OptionsContainer,
            max_items: int | None = None) -> list[AdaptationSet]:
        adap_sets: dict[int, AdaptationSet] = {}
        media_files = models.MediaFile.search(
            content_type='audio', stream=stream, max_items=max_items)
        audio_files: list[Representation] = []
        acodec = options.audioCodec
        for mf in media_files:
            if mf.representation is None:
                continue
            r = mf.representation
            if r.encrypted != options.encrypted:
                continue
            if acodec in {None, 'any'} or r.codecs.startswith(acodec):
                audio_files.append(r)
            elif acodec == 'ec-3' and r.codecs == 'ac-3':
                # special case as CGI paramaters doesn't distinguish between
                # AC-3 and EAC-3
                audio_files.append(r)
        if not audio_files and acodec:
            # if stream is encrypted but there is no encrypted version of the audio track, fall back
            # to a clear version
            for mf in media_files:
                if mf.representation is None:
                    continue
                r = mf.representation
                if acodec in {None, 'any'} or r.codecs.startswith(acodec):
                    audio_files.append(r)
                elif acodec == 'ec-3' and r.codecs == 'ac-3':
                    # special case as CGI paramaters doesn't distinguish between
                    # AC-3 and EAC-3
                    audio_files.append(r)

        for r in audio_files:
            try:
                audio = adap_sets[r.track_id]
            except KeyError:
                audio = AdaptationSet(
                    mode=options.mode, content_type='audio', id=(100 + r.track_id),
                    segment_timeline=options.segmentTimeline, numChannels=r.numChannels)
                adap_sets[r.track_id] = audio
            if len(audio_files) == 1 or options.mainAudio == r.id:
                audio.role = 'main'
            else:
                audio.role = 'alternate'
                if options.audioDescription == r.id:
                    audio.accessibility = {
                        'schemeIdUri': "urn:tva:metadata:cs:AudioPurposeCS:2007",
                        'value': 1,  # Audio description for the visually impaired
                    }
            audio.representations.append(r)
        result: list[AdaptationSet] = []
        for audio in adap_sets.values():
            audio.compute_av_values()
            result.append(audio)
        return result

    def calculate_video_adaptation_set(
            self, stream: models.Stream, options: OptionsContainer,
            max_items: int | None = None) -> AdaptationSet:
        video = AdaptationSet(
            mode=options.mode, content_type='video', id=1,
            segment_timeline=options.segmentTimeline)
        media_files = models.MediaFile.search(
            content_type='video', encrypted=options.encrypted, stream=stream,
            max_items=max_items)
        for mf in media_files:
            if mf.representation is None:
                continue
            assert mf.content_type == 'video'
            assert mf.representation.content_type == 'video'
            video.representations.append(mf.representation)
        video.compute_av_values()
        assert isinstance(video.representations, list)
        return video

    def calculate_text_adaptation_sets(
            self, stream: models.Stream, options: OptionsContainer,
            max_items: int | None = None) -> list[AdaptationSet]:
        media_files = models.MediaFile.search(
            content_type='text', stream=stream, max_items=max_items)
        text_tracks: list[Representation] = []
        for mf in media_files:
            if mf.representation is None:
                continue
            r = mf.representation
            if r.encrypted == options.encrypted:
                if options.textCodec is None or r.codecs.startswith(options.textCodec):
                    text_tracks.append(r)
        if not text_tracks:
            # if stream is encrypted but there is no encrypted version of the text track, fall back
            # to a clear version
            for mf in media_files:
                r = mf.representation
                if options.textCodec is None or r.codecs.startswith(options.textCodec):
                    text_tracks.append(r)
        result: list[AdaptationSet] = []
        for r in text_tracks:
            text = AdaptationSet(
                mode=options.mode, content_type='text', id=(200 + r.track_id),
                segment_timeline=options.segmentTimeline)
            lang_match = (options.textLanguage is None or
                          text.lang in {'und', options.textLanguage})
            if len(text_tracks) == 1 or lang_match:
                text.role = 'main'
                # Subtitles for the hard of hearing in the same language as
                # the programme
                text.accessibility = {
                    'schemeIdUri': "urn:tva:metadata:cs:AudioPurposeCS:2007",
                    'value': 2,
                }
            elif options.mainText == r.id:
                text.role = 'main'
            else:
                text.role = 'alternate'
            text.compute_av_values()
            result.append(text)
        return result

    def calculate_cgi_parameters(self, options: OptionsContainer,
                                 now: datetime.datetime,
                                 audio: list[AdaptationSet],
                                 video: AdaptationSet) -> dict[str, dict]:
        exclude = {'encrypted', 'mode'}
        vid_cgi_params = options.generate_cgi_parameters(use=OptionUsage.VIDEO, exclude=exclude)
        aud_cgi_params = options.generate_cgi_parameters(use=OptionUsage.AUDIO, exclude=exclude)
        txt_cgi_params = options.generate_cgi_parameters(use=OptionUsage.TEXT, exclude=exclude)
        mft_cgi_params = options.generate_cgi_parameters(exclude=exclude)
        clk_cgi_params = options.generate_cgi_parameters(use=OptionUsage.TIME, exclude=exclude)
        if options.videoErrors:
            times = self.calculate_injected_error_segments(
                options.videoErrors,
                now,
                options.availabilityStartTime,
                options.timeShiftBufferDepth,
                video.representations[0])
            vid_cgi_params['verr'] = times
        if options.audioErrors and audio:
            if audio[0].representations:
                times = self.calculate_injected_error_segments(
                    options.audioErrors,
                    now,
                    options.availabilityStartTime,
                    options.timeShiftBufferDepth,
                    audio[0].representations[0])
                aud_cgi_params['aerr'] = times
        if options.videoCorruption:
            errs = [(None, tc) for tc in options.videoCorruption]
            segs = self.calculate_injected_error_segments(
                errs,
                now,
                options.availabilityStartTime,
                options.timeShiftBufferDepth,
                video.representations[0])
            vid_cgi_params['vcorrupt'] = segs
        if options.updateCount is not None:
            mft_cgi_params['update'] = str(options.updateCount + 1)

        return {
            'audio': aud_cgi_params,
            'video': vid_cgi_params,
            'text': txt_cgi_params,
            'manifest': mft_cgi_params,
            'time': clk_cgi_params,
        }

    def choose_time_source_method(self, options: OptionsContainer, cgi_params: dict,
                                  now: datetime.datetime) -> dict | None:
        if options.mode != 'live' or options.utcMethod is None:
            return None
        format = options.utcMethod
        value = None
        if format == 'direct':
            method = 'urn:mpeg:dash:utc:direct:2014'
            value = to_iso_datetime(now)
        elif format == 'head':
            method = 'urn:mpeg:dash:utc:http-head:2014'
        elif format == 'http-ntp':
            method = 'urn:mpeg:dash:utc:http-ntp:2014'
        elif format == 'iso':
            method = 'urn:mpeg:dash:utc:http-iso:2014'
        elif format == 'ntp':
            method = 'urn:mpeg:dash:utc:ntp:2014'
            value = 'time1.google.com time2.google.com time3.google.com time4.google.com'
        elif format == 'sntp':
            method = 'urn:mpeg:dash:utc:sntp:2014'
            value = 'time1.google.com time2.google.com time3.google.com time4.google.com'
        elif format == 'xsd':
            method = 'urn:mpeg:dash:utc:http-xsdate:2014'
        else:
            raise ValueError(fr'Unknown time format: "{format}"')
        timeSource = {
            'format': format,
            'method': method,
            'value': options.utcValue if options.utcValue is not None else value
        }
        if value is None:
            timeSource['value'] = urllib.parse.urljoin(
                flask.request.host_url,
                flask.url_for('time', format=format))
            timeSource['value'] += objects.dict_to_cgi_params(cgi_params['time'])
        return timeSource

    def add_allowed_origins(self, headers):
        cfg = flask.current_app.config['DASH']
        allowed_domains = cfg.get('ALLOWED_DOMAINS', self.DEFAULT_ALLOWED_DOMAINS)
        if allowed_domains == "*":
            headers["Access-Control-Allow-Origin"] = "*"
            headers["Access-Control-Allow-Methods"] = "HEAD, GET, POST"
            return
        try:
            if isinstance(allowed_domains, str):
                allowed_domains = re.compile(allowed_domains)
            if allowed_domains.search(flask.request.headers['Origin']):
                headers["Access-Control-Allow-Origin"] = flask.request.headers['Origin']
                headers["Access-Control-Allow-Methods"] = "HEAD, GET, POST"
        except KeyError:
            pass

    def calculate_injected_error_segments(
            self,
            errors: list[tuple[int, str]],
            now: datetime.datetime,
            availabilityStartTime: datetime.datetime,
            timeShiftBufferDepth,
            representation) -> str:
        """
        Calculate a list of segment numbers for injecting errors
        :param errors: a list of error definitions. Each definition is a tuple of an HTTP error
                       code and either a segment number of an ISO8601 time.
        :param availabilityStartTime: datetime.datetime containing availability start time
        :param representation: the Representation to use when calculating segment numbering
        """
        drops = []
        earliest_available = now - \
            datetime.timedelta(seconds=timeShiftBufferDepth)
        for item in errors:
            code, pos = item
            if isinstance(pos, int):
                drop_seg = int(pos, 10)
            else:
                tm = availabilityStartTime.replace(
                    hour=pos.hour, minute=pos.minute, second=pos.second)
                if tm < earliest_available:
                    continue
                drop_delta = tm - availabilityStartTime
                drop_seg = int(scale_timedelta(
                    drop_delta, representation.timescale, representation.segment_duration))
            if code is None:
                drops.append(f'{drop_seg}')
            else:
                drops.append(f'{code}={drop_seg}')
        return urllib.parse.quote_plus(','.join(drops))

    def has_http_range(self):
        return 'range' in flask.request.headers

    def get_http_range(self, content_length):
        try:
            http_range = flask.request.headers['range'].lower().strip()
        except KeyError:
            return (None, None, 200, {})
        if not http_range.startswith('bytes='):
            raise ValueError('Only byte based ranges are supported')
        if ',' in http_range:
            raise ValueError('Multiple ranges not supported')
        start, end = http_range[6:].split('-')
        if start == '':
            amount = int(end, 10)
            start = content_length - amount
            end = content_length - 1
        elif end == '':
            end = content_length - 1
        if isinstance(start, str):
            start = int(start, 10)
        if isinstance(end, str):
            end = int(end, 10)
        status = 206
        headers = {
            'Accept-Ranges': 'bytes',
            'Content-Range': f'bytes {start}-{end}/{content_length}'
        }
        if end >= content_length or end < start:
            headers['Content-Range'] = f'bytes */{content_length}'
            status = 416
        return (start, end, status, headers,)

    @staticmethod
    def is_https_request():
        if flask.request.scheme == 'https':
            return True
        if environ.get('HTTPS', 'off') == 'on':
            return True
        return flask.request.headers.get('X-HTTP-Scheme', 'http') == 'https'

    def is_ajax(self) -> bool:
        return is_ajax()

    def get_next_url(self) -> str | None:
        """
        Returns unquoted "next" URL if present in the request
        """
        next: str | None = None
        # TODO: check "next" is a URL within this app
        try:
            next = flask.request.args['next']
            if next is not None:
                next = urllib.parse.unquote_plus(next)
            if next == "":
                next = None
        except KeyError:
            pass
        return next

    def get_next_url_with_fallback(self, route_name: str, **kwargs) -> str:
        """
        Checks for a "next" parameter in the request
        """
        next = self.get_next_url()
        if next is None:
            next = flask.url_for(route_name, **kwargs)
        return next

    def jsonify(self, data: Any, status: int | None = None,
                headers: dict | None = None) -> flask.Response:
        """
        Replacement for Flask jsonify that uses flatten to convert non-json objects
        """
        if status is None:
            status = 200
        if isinstance(data, dict):
            response = flask.json.jsonify(**objects.flatten(data))
        elif isinstance(data, list):
            response = flask.json.jsonify(objects.flatten(data))
        else:
            response = flask.json.jsonify(data)
        response.status = status
        if headers is None:
            headers = {}
            self.add_allowed_origins(headers)
        response.headers.update(headers)
        return response

    def jsonify_no_content(self, status: int) -> flask.Response:
        """
        Used to return a JSON response with no body
        """
        response = flask.json.jsonify('')
        response.status = status
        return response

    def increment_error_counter(self, usage: str, code: int) -> int:
        key = f'error-{usage}-{code:06d}'
        value = flask.session.get(key, 0) + 1
        flask.session[key] = value
        return value

    def reset_error_counter(self, usage: str, code: int) -> None:
        key = f'error-{usage}-{code:06d}'
        flask.session[key] = None


class HTMLHandlerBase(RequestHandlerBase):
    """
    Base class for all HTML pages
    """

    def create_context(self, **kwargs):
        context = super().create_context(**kwargs)
        if 'nomodule' not in flask.request.args:
            context['nomodule'] = 'nomodule'
        route = routes[flask.request.endpoint]
        navbar = [{
            'title': 'Home', 'href': flask.url_for('home')
        }, {
            'title': 'Streams', 'href': flask.url_for('list-streams')
        }, {
            'title': 'Validate', 'href': flask.url_for('validate-stream')
        }]
        if current_user.is_authenticated:
            if current_user.is_admin:
                navbar.append({
                    'title': 'Users', 'href': flask.url_for('list-users')
                })
            else:
                navbar.append({
                    'title': 'My Account', 'href': flask.url_for('change-password')
                })
            navbar.append({
                'title': 'Log Out',
                'class': 'user-login',
                'href': flask.url_for('logout')
            })
        else:
            navbar.append({
                'title': 'Log In',
                'class': 'user-login',
                'href': flask.url_for('login')
            })
        found_active = False
        for nav in navbar[1:]:
            if flask.request.path.startswith(nav['href']):
                nav['active'] = True
                found_active = True
                break
        if not found_active:
            navbar[0]['active'] = True
        context.update({
            "title": kwargs.get('title', route.title),
            "breadcrumbs": self.get_breadcrumbs(route),
            "navbar": navbar,
            'routes': routes,
        })
        return context

    def get_breadcrumbs(self, route: Route) -> list[dict[str, str]]:
        breadcrumbs = [{
            'title': route.page_title(),
            'active': 'active'
        }]
        p: str | None = route.parent
        while p:
            rt: Route = routes[p]
            breadcrumbs.insert(0, {
                "title": rt.page_title(),
                "href": flask.url_for(rt.name)
            })
            p = rt.parent
        return breadcrumbs


class DeleteModelBase(HTMLHandlerBase):
    """
    Base class for deleting a model from the database
    """

    MODEL_NAME: str = ''

    def get(self, **kwargs) -> flask.Response:
        """
        Returns HTML form to confirm if stream should be deleted
        """
        context = self.create_context()
        csrf_key = self.generate_csrf_cookie()
        context.update({
            'model': self.get_model_dict(),
            'model_name': self.MODEL_NAME,
            'cancel_url': self.get_cancel_url(),
            'submit_url': flask.request.url,
            'csrf_token': self.generate_csrf_token(self.CSRF_TOKEN_NAME, csrf_key),
        })
        return flask.render_template('delete_model_confirm.html', **context)

    def post(self, **kwargs) -> flask.Response:
        """
        Deletes a model, in response to a submitted confirm form
        """
        try:
            self.check_csrf(self.CSRF_TOKEN_NAME, flask.request.form)
        except (ValueError, CsrfFailureException) as err:
            return flask.make_response(f'CSRF failure: {err}', 400)
        model = self.get_model_dict()
        result = self.delete_model()
        if not result.get('error'):
            flask.flash(f'Deleted {self.MODEL_NAME.lower()} {model["title"]}', 'success')
        return flask.redirect(self.get_next_url())

    def delete(self, **kwargs) -> flask.Response:
        """
        handler for deleting a stream
        """
        result = {"error": None}
        try:
            self.check_csrf(self.CSRF_TOKEN_NAME, flask.request.args)
        except (ValueError, CsrfFailureException) as err:
            result = {
                "error": f'CSRF failure: {err}'
            }
        if result['error'] is None:
            result = self.delete_model()
        csrf_key = self.generate_csrf_cookie()
        result["csrf"] = self.generate_csrf_token(self.CSRF_TOKEN_NAME, csrf_key)
        return self.jsonify(result)

    @abstractmethod
    def get_model_dict(self) -> JsonObject:
        pass

    @abstractmethod
    def get_next_url(self) -> str:
        pass

    @abstractmethod
    def get_cancel_url(self) -> str:
        pass

    @abstractmethod
    def delete_model(self) -> JsonObject:
        pass
