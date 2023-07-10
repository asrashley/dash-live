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

from __future__ import division
from future import standard_library
standard_library.install_aliases()
from abc import abstractmethod
from builtins import str
from past.builtins import basestring
from past.utils import old_div
from typing import Any, Dict, List, Optional

import base64
import copy
import datetime
import hashlib
import hmac
import logging
import os
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
from dashlive.drm.clearkey import ClearKey
from dashlive.drm.playready import PlayReady
from dashlive.drm.marlin import Marlin
from dashlive.server import manifests
from dashlive.server import models
from dashlive.server import settings
from dashlive.server.gae import on_production_server
from dashlive.server.events.factory import EventFactory
from dashlive.server.routes import routes, Route
from dashlive.utils import objects
from dashlive.utils.date_time import scale_timedelta, from_isodatetime, toIsoDateTime
from dashlive.utils.json_object import JsonObject
from dashlive.utils.timezone import UTC

from .dash_timing import DashTiming
from .decorators import current_stream, is_ajax
from .exceptions import CsrfFailureException

class RequestHandlerBase(MethodView):
    CLIENT_COOKIE_NAME = 'dash'
    CSRF_COOKIE_NAME = 'csrf'
    CSRF_EXPIRY = 1200
    DEFAULT_ALLOWED_DOMAINS = re.compile(
        r'^http://(dashif\.org)|(shaka-player-demo\.appspot\.com)|(mediapm\.edgesuite\.net)')
    INJECTED_ERROR_CODES = [404, 410, 503, 504]

    def create_context(self, **kwargs):
        route = routes[flask.request.endpoint]
        context = {
            "title": kwargs.get('title', route.title),
            "on_production_server": on_production_server,
            "http_protocol": flask.request.scheme,
            "breadcrumbs": self.get_breadcrumbs(route),
        }
        context.update(kwargs)
        if current_user.is_authenticated:
            context['logout'] = flask.url_for('logout')
            context["is_current_user_admin"] = current_user.is_admin
        else:
            context['login'] = flask.url_for('login')
        context['remote_addr'] = flask.request.remote_addr
        context['request_uri'] = flask.request.url
        if self.is_https_request():
            context['request_uri'] = context['request_uri'].replace(
                'http://', 'https://')
        return context

    def get_breadcrumbs(self, route: Route) -> List[Dict[str, str]]:
        breadcrumbs = [{
            'title': route.page_title(),
            'active': 'active'
        }]
        p: Optional[str] = route.parent
        while p:
            rt: Route = routes[p]
            breadcrumbs.insert(0, {
                "title": rt.page_title(),
                "href": flask.url_for(rt.name)
            })
            p = rt.parent
        return breadcrumbs

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
        sig = hmac.new(
            bytes(settings.csrf_secret, 'utf-8'),
            bytes(csrf_key, 'utf-8'),
            hashlib.sha1)
        cur_url = urllib.parse.urlparse(flask.request.url, 'http')
        origin = '%s://%s' % (cur_url.scheme, cur_url.netloc)
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
                "No origin in request, using: {}".format(flask.request.url))
            cur_url = urllib.parse.urlparse(flask.request.url, 'http')
            origin = '%s://%s' % (cur_url.scheme, cur_url.netloc)
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
        sig = hmac.new(
            bytes(settings.csrf_secret, 'utf-8'),
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

    def get_bool_param(self, param: str, default: Optional[bool] = False) -> bool:
        value = flask.request.args.get(param)
        if value is None:
            value = flask.request.form.get(param)
        if value is None:
            return default
        return value.lower() in {"1", "true", "on"}

    def generate_drm_location_tuples(self):
        """
        Returns list of tuples, where each entry is:
          * DRM name,
          * DRM implementation, and
          * DRM data locations
        """
        drms = flask.request.args.get('drm', 'all')
        rv = []
        for name in drms.split(','):
            if '-' in name:
                parts = name.split('-')
                drm_name = parts[0]
                locations = set(parts[1:])
            else:
                drm_name = name
                locations = None
            if drm_name in {'all', 'playready'}:
                drm = PlayReady()
                rv.append(('playready', drm, locations,))
            if drm_name in {'all', 'marlin'}:
                drm = Marlin()
                rv.append(('marlin', drm, locations,))
            if drm_name in {'all', 'clearkey'}:
                drm = ClearKey()
                rv.append(('clearkey', drm, locations,))
        return rv

    def generate_drm_dict(self, stream, keys):
        """
        Generate contexts for all enabled DRM systems. It returns a
        dictionary with an entry for each DRM system.
        """
        if isinstance(stream, basestring):
            stream = models.Stream.get(directory=stream)
        rv = {}
        for drm_name, drm, locations in self.generate_drm_location_tuples():
            if drm_name == 'clearkey':
                ck_laurl = urllib.parse.urljoin(
                    flask.request.host_url, flask.url_for('clearkey'))
                if self.is_https_request():
                    ck_laurl = ck_laurl.replace('http://', 'https://')
                rv[drm_name] = drm.generate_manifest_context(
                    stream, keys, flask.request.args, la_url=ck_laurl, locations=locations)
            else:
                rv[drm_name] = drm.generate_manifest_context(
                    stream, keys, flask.request.args, locations=locations)
        return rv

    def calculate_dash_params(self, mode: str, mpd_url: str,
                              stream: Optional[models.Stream] = None):
        if mpd_url is None:
            raise ValueError("Unable to determin MPD URL")
        if stream is None:
            stream = current_stream
        if not bool(stream):
            raise ValueError('Stream model is not available')
        manifest_info = manifests.manifest[mpd_url]
        encrypted = flask.request.args.get('drm', 'none').lower() != 'none'
        now = datetime.datetime.now(tz=UTC())
        clockDrift = 0
        try:
            clockDrift = int(flask.request.args.get('drift', '0'), 10)
            if clockDrift:
                now -= datetime.timedelta(seconds=clockDrift)
        except ValueError as err:
            logging.warning('Invalid clock drift CGI parameter: %s', err)

        rv = {
            "DRM": {},
            "abr": self.get_bool_param('abr', default=True),
            "clockDrift": clockDrift,
            "encrypted": encrypted,
            "minBufferTime": datetime.timedelta(seconds=1.5),
            "mode": mode,
            "mpd_url": mpd_url,
            "now": now,
            "periods": [],
            "startNumber": 1,
            "stream": stream.to_dict(exclude={'media_files'}),
            "suggestedPresentationDelay": 30,
        }
        period = Period(start=datetime.timedelta(0), id="p0")
        audio = self.calculate_audio_context(stream, mode, encrypted)
        text = self.calculate_text_context(stream, mode, encrypted)
        max_items = None
        if rv['abr'] is False:
            max_items = 1
        video = self.calculate_video_context(stream, mode, encrypted, max_items=max_items)
        if video.representations:
            rv["ref_representation"] = video.representations[0]
        else:
            rv["ref_representation"] = audio.representations[0]
        timing = DashTiming(mode, now, rv["ref_representation"], flask.request.args)
        rv.update(timing.generate_manifest_context())
        cgi_params = self.calculate_cgi_parameters(
            mode=mode, now=now, avail_start=timing.availabilityStartTime,
            clockDrift=clockDrift, ts_buffer_depth=timing.timeShiftBufferDepth,
            audio=audio, video=video)
        video.append_cgi_params(cgi_params['video'])
        audio.append_cgi_params(cgi_params['audio'])
        text.append_cgi_params(cgi_params['text'])
        if cgi_params['manifest']:
            locationURL = flask.request.url
            if '?' in locationURL:
                locationURL = locationURL[:flask.request.url.index('?')]
            locationURL = locationURL + objects.dict_to_cgi_params(cgi_params['manifest'])
            rv["locationURL"] = locationURL
        use_base_url = self.get_bool_param('base', True)
        if use_base_url:
            if mode == 'odvod':
                rv["baseURL"] = urllib.parse.urljoin(
                    flask.request.host_url, f'/dash/vod/{stream.directory}') + '/'
            else:
                rv["baseURL"] = urllib.parse.urljoin(
                    flask.request.host_url, f'/dash/{mode}/{stream.directory}') + '/'
            if self.is_https_request():
                rv["baseURL"] = rv["baseURL"].replace('http://', 'https://')
        else:
            if mode == 'odvod':
                prefix = flask.url_for(
                    'dash-od-media',
                    stream=stream.directory,
                    filename='RepresentationID',
                    ext='m4v')
                prefix = prefix.replace('RepresentationID.m4v', '')
            else:
                prefix = flask.url_for(
                    'dash-media',
                    mode=mode,
                    stream=stream.directory,
                    filename='RepresentationID',
                    segment_num='init',
                    ext='m4v')
                prefix = prefix.replace('RepresentationID/init.m4v', '')
                video.initURL = prefix + video.initURL
                audio.initURL = prefix + audio.initURL
                text.initURL = prefix + text.initURL
            video.mediaURL = prefix + video.mediaURL
            audio.mediaURL = prefix + audio.mediaURL
            text.mediaURL = prefix + text.mediaURL
        event_generators = EventFactory.create_event_generators(flask.request)
        for evgen in event_generators:
            ev_stream = evgen.create_manifest_context(context=rv)
            if evgen.inband:
                # TODO: allow AdaptationSet for inband events to be
                # configurable
                video.event_streams.append(ev_stream)
            else:
                period.event_streams.append(ev_stream)
        video.set_reference_representation(rv["ref_representation"])
        video.set_dash_timing(timing)
        period.adaptationSets.append(video)

        for idx, rep in enumerate(audio.representations):
            audio_adp = audio.clone(
                id=(idx + 2), lang=rep.lang, representations=[rep])
            rep.set_reference_representation(rv["ref_representation"])
            rep.set_dash_timing(timing)
            if len(audio.representations) == 1:
                audio_adp.role = 'main'
            elif flask.request.args.get('main_audio', None) == rep.id:
                audio_adp.role = 'main'
            elif rep.codecs.startswith(flask.request.args.get('main_audio', 'mp4a')):
                audio_adp.role = 'main'
            else:
                audio_adp.role = 'alternate'
            if flask.request.args.get('ad_audio', None) == rep.id:
                audio_adp.role = 'alternate'
                audio_adp.accessibility = {
                    'schemeIdUri': "urn:tva:metadata:cs:AudioPurposeCS:2007",
                    'value': 1,  # Audio description for the visually impaired
                }
            period.adaptationSets.append(audio_adp)

        for rep in text.representations:
            text_adp = text.clone(
                id=(888 + len(period.adaptationSets)),
                lang=rep.lang, representations=[rep])
            rep.set_reference_representation(rv["ref_representation"])
            rep.set_dash_timing(timing)
            lang_match = (text.lang == audio.lang or
                          text.lang == 'und' or audio.lang == 'und')
            if len(text.representations) == 1 and lang_match:
                text_adp.role = 'main'
                # Subtitles for the hard of hearing in the same language as
                # the programme
                text_adp.accessibility = {
                    'schemeIdUri': "urn:tva:metadata:cs:AudioPurposeCS:2007",
                    'value': 2,
                }
            elif flask.request.args.get('main_text', None) == rep.id:
                text_adp.role = 'main'
            else:
                text_adp.role = 'alternate'
            period.adaptationSets.append(text_adp)

        rv["periods"].append(period)
        kids = set()
        for rep in video.representations + audio.representations:
            if rep.encrypted:
                kids.update(rep.kids)
        rv["kids"] = kids
        rv["mediaDuration"] = old_div(rv["ref_representation"].mediaDuration,
                                      rv["ref_representation"].timescale)
        rv["maxSegmentDuration"] = max(video.maxSegmentDuration,
                                       audio.maxSegmentDuration)
        if encrypted:
            if not kids:
                rv["keys"] = models.Key.all_as_dict()
            else:
                rv["keys"] = models.Key.get_kids(kids)
            rv["DRM"] = self.generate_drm_dict(stream, rv["keys"])
        rv["timeSource"] = self.choose_time_source_method(cgi_params, now)
        if 'periods' not in manifest_info.features:
            rv["video"] = video
            rv["audio"] = audio
            rv["period"] = rv["periods"][0]
        return rv

    def calculate_audio_context(self, stream, mode, encrypted, max_items=None):
        audio = AdaptationSet(mode=mode, content_type='audio', id=2)
        acodec = flask.request.args.get('acodec')
        media_files = models.MediaFile.search(
            content_type='audio', stream=stream, max_items=max_items)
        for mf in media_files:
            r = mf.representation
            assert r.content_type == 'audio'
            assert mf.content_type == 'audio'
            if r.encrypted == encrypted:
                if acodec is None or r.codecs.startswith(acodec):
                    audio.representations.append(r)
                elif acodec == 'ec-3' and r.codecs == 'ac-3':
                    # special case as CGI paramaters doesn't distinguish between
                    # AC-3 and EAC-3
                    audio.representations.append(r)
        # if stream is encrypted but there is no encrypted version of the audio track, fall back
        # to a clear version
        if not audio.representations and acodec:
            for mf in media_files:
                r = mf.representation
                if r.codecs.startswith(acodec):
                    audio.representations.append(r)
        audio.compute_av_values()
        assert isinstance(audio.representations, list)
        return audio

    def calculate_video_context(self, stream: models.Stream, mode: str,
                                encrypted: bool, max_items=None) -> List[AdaptationSet]:
        video = AdaptationSet(mode=mode, content_type='video', id=1)
        media_files = models.MediaFile.search(
            content_type='video', encrypted=encrypted, stream=stream,
            max_items=max_items)
        for mf in media_files:
            assert mf.content_type == 'video'
            assert mf.representation.content_type == 'video'
            video.representations.append(mf.representation)
        video.compute_av_values()
        assert isinstance(video.representations, list)
        return video

    def calculate_text_context(self, stream, mode, encrypted, max_items=None):
        text = AdaptationSet(mode=mode, content_type='text', id=888)
        tcodec = flask.request.args.get('tcodec')
        media_files = models.MediaFile.search(
            content_type='text', stream=stream, max_items=max_items)
        for mf in media_files:
            r = mf.representation
            if r.encrypted == encrypted:
                if tcodec is None or r.codecs.startswith(tcodec):
                    text.representations.append(r)
        # if stream is encrypted but there is no encrypted version of the text track, fall back
        # to a clear version
        if not text.representations:
            for mf in media_files:
                r = mf.representation
                if tcodec is None or r.codecs.startswith(tcodec):
                    text.representations.append(r)
        text.compute_av_values()
        return text

    def calculate_cgi_parameters(self, mode, now, avail_start, clockDrift,
                                 ts_buffer_depth, audio, video):
        vid_cgi_params = {}
        aud_cgi_params = {}
        txt_cgi_params = {}
        mft_cgi_params = copy.deepcopy(dict(flask.request.args))
        clk_cgi_params = {}
        param_includes = {'bugs', 'drm', 'start'}
        param_prefixes = ['playready_', 'marlin_']
        if flask.request.args.get('events', None) is not None:
            param_includes.add('events')
            event_generators = EventFactory.create_event_generators(flask.request)
            for evg in event_generators:
                param_prefixes.append(evg.prefix)
        for name, value in flask.request.args.items():
            if value is None or (name == 'drm' and value == 'none'):
                continue
            include = (name in param_includes)
            for prefix in param_prefixes:
                if name.startswith(prefix):
                    include = True
            if not include:
                continue
            if name == 'start':
                value = toIsoDateTime(avail_start)
            vid_cgi_params[name] = value
            aud_cgi_params[name] = value
            txt_cgi_params[name] = value
            mft_cgi_params[name] = value
        if clockDrift:
            clk_cgi_params['drift'] = str(clockDrift)
            vid_cgi_params['drift'] = str(clockDrift)
            aud_cgi_params['drift'] = str(clockDrift)
            txt_cgi_params['drift'] = str(clockDrift)
        if mode == 'live' and ts_buffer_depth != DashTiming.DEFAULT_TIMESHIFT_BUFFER_DEPTH:
            vid_cgi_params['depth'] = str(ts_buffer_depth)
            aud_cgi_params['depth'] = str(ts_buffer_depth)
            txt_cgi_params['depth'] = str(ts_buffer_depth)
        for code in self.INJECTED_ERROR_CODES:
            if flask.request.args.get('v%03d' % code) is not None:
                times = self.calculate_injected_error_segments(
                    flask.request.args.get('v%03d' % code),
                    now,
                    avail_start,
                    ts_buffer_depth,
                    video.representations[0])
                if times:
                    vid_cgi_params['%03d' % (code)] = times
            if flask.request.args.get('a%03d' % code) is not None:
                times = self.calculate_injected_error_segments(
                    flask.request.args.get('a%03d' % code),
                    now,
                    avail_start,
                    ts_buffer_depth,
                    audio.representations[0])
                if times:
                    aud_cgi_params['%03d' % (code)] = times
        if flask.request.args.get('vcorrupt') is not None:
            segs = self.calculate_injected_error_segments(
                flask.request.args.get('vcorrupt'),
                now,
                avail_start,
                ts_buffer_depth,
                video.representations[0])
            if segs:
                vid_cgi_params['corrupt'] = segs
        try:
            updateCount = int(flask.request.args.get('update', '0'), 10)
            mft_cgi_params['update'] = str(updateCount + 1)
        except ValueError as err:
            logging.warning('Invalid update CGI parameter: %s', err)

        return {
            'audio': aud_cgi_params,
            'video': vid_cgi_params,
            'text': txt_cgi_params,
            'manifest': mft_cgi_params,
            'time': clk_cgi_params,
        }

    def choose_time_source_method(self, cgi_params, now):
        timeSource = {
            'format': flask.request.args.get('time', 'xsd')
        }
        if timeSource['format'] == 'direct':
            timeSource['method'] = 'urn:mpeg:dash:utc:direct:2014'
            timeSource['value'] = toIsoDateTime(now)
        elif timeSource['format'] == 'head':
            timeSource['method'] = 'urn:mpeg:dash:utc:http-head:2014'
        elif timeSource['format'] == 'http-ntp':
            timeSource['method'] = 'urn:mpeg:dash:utc:http-ntp:2014'
        elif timeSource['format'] == 'iso':
            timeSource['method'] = 'urn:mpeg:dash:utc:http-iso:2014'
        elif timeSource['format'] == 'ntp':
            timeSource['method'] = 'urn:mpeg:dash:utc:ntp:2014'
            timeSource['value'] = 'time1.google.com time2.google.com time3.google.com time4.google.com'
        elif timeSource['format'] == 'sntp':
            timeSource['method'] = 'urn:mpeg:dash:utc:sntp:2014'
            timeSource['value'] = 'time1.google.com time2.google.com time3.google.com time4.google.com'
        elif timeSource['format'] == 'xsd':
            timeSource['method'] = 'urn:mpeg:dash:utc:http-xsdate:2014'
        else:
            raise ValueError(r'Unknown time format: "{0}"'.format(timeSource['format']))
        try:
            timeSource['value'] = flask.request.args['time_value']
        except KeyError:
            pass
        if 'value' not in timeSource:
            timeSource['value'] = urllib.parse.urljoin(
                flask.request.host_url,
                flask.url_for('time', format=timeSource['format']))
            timeSource['value'] += objects.dict_to_cgi_params(cgi_params['time'])
        return timeSource

    def add_allowed_origins(self, headers):
        allowed_domains = getattr(settings, 'allowed_domains', self.DEFAULT_ALLOWED_DOMAINS)
        if allowed_domains == "*":
            headers["Access-Control-Allow-Origin"] = "*"
            headers["Access-Control-Allow-Methods"] = ["HEAD, GET, POST"]
            return
        try:
            if isinstance(allowed_domains, str):
                allowed_domains = re.compile(allowed_domains)
            if allowed_domains.search(flask.request.headers['Origin']):
                headers["Access-Control-Allow-Origin"] = flask.request.headers['Origin']
                headers["Access-Control-Allow-Methods"] = ["HEAD, GET, POST"]
        except KeyError:
            pass

    def calculate_injected_error_segments(
            self, times, now, availabilityStartTime, timeshiftBufferDepth, representation):
        """Calculate a list of segment numbers for injecting errors

        :param times: a string of comma separated ISO8601 times
        :param availabilityStartTime: datetime.datetime containing availability start time
        :param representation: the Representation to use when calculating segment numbering
        """
        drops = []
        if not times:
            raise ValueError(
                'Time must be a comma separated list of ISO times')
        earliest_available = now - \
            datetime.timedelta(seconds=timeshiftBufferDepth)
        for d in times.split(','):
            tm = from_isodatetime(d)
            tm = availabilityStartTime.replace(
                hour=tm.hour, minute=tm.minute, second=tm.second)
            if tm < earliest_available:
                continue
            drop_delta = tm - availabilityStartTime
            drop_seg = int(scale_timedelta(
                drop_delta, representation.timescale, representation.segment_duration))
            drops.append('%d' % drop_seg)
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
        if isinstance(start, basestring):
            start = int(start, 10)
        if isinstance(end, basestring):
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

    def is_https_request(self):
        if flask.request.scheme == 'https':
            return True
        if os.environ.get('HTTPS', 'off') == 'on':
            return True
        return flask.request.headers.get('X-HTTP-Scheme', 'http') == 'https'

    def is_ajax(self) -> bool:
        return is_ajax()

    def get_next_url(self) -> Optional[str]:
        """
        Returns unquoted "next" URL if present in the request
        """
        next: Optional[str] = None
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

    def jsonify(self, data: Any, status: Optional[int] = None,
                headers: Optional[Dict] = None) -> flask.Response:
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
        context = super(HTMLHandlerBase, self).create_context(**kwargs)
        context.update({
            'routes': routes,
        })
        return context


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
