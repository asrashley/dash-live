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

import base64
import binascii
import copy
import datetime
import hashlib
import hmac
import logging
import re
import urllib
import urlparse
import webapp2

from google.appengine.api import users, memcache
from webapp2_extras import securecookie
from webapp2_extras import security

from mpeg.dash.adaptation_set import AdaptationSet
from mpeg.dash.period import Period
from drm.clearkey import ClearKey
from drm.playready import PlayReady
from drm.marlin import Marlin
from server import manifests
from server import models
from server import settings
from server.gae import on_production_server
from server.events.factory import EventFactory
from server.routes import routes
from templates.factory import TemplateFactory
import utils.objects
from utils.date_time import scale_timedelta, from_isodatetime, toIsoDateTime
from utils.timezone import UTC

from .dash_timing import DashTiming
from .exceptions import CsrfFailureException

class RequestHandlerBase(webapp2.RequestHandler):
    CLIENT_COOKIE_NAME = 'dash'
    CSRF_COOKIE_NAME = 'csrf'
    CSRF_EXPIRY = 1200
    CSRF_KEY_LENGTH = 32
    CSRF_SALT_LENGTH = 8
    DEFAULT_ALLOWED_DOMAINS = re.compile(
        r'^http://(dashif\.org)|(shaka-player-demo\.appspot\.com)|(mediapm\.edgesuite\.net)')
    INJECTED_ERROR_CODES = [404, 410, 503, 504]

    def create_context(self, **kwargs):
        route = routes[self.request.route.name]
        context = {
            "title": kwargs.get('title', route.title),
            "uri_for": self.uri_for,
            "on_production_server": on_production_server,
            "http_protocol": self.request.host_url.split(':')[0]
        }
        context.update(kwargs)
        p = route.parent
        context["breadcrumbs"] = []
        while p:
            p = routes[p]
            context["breadcrumbs"].insert(0, {"title": p.title,
                                              "href": self.uri_for(p.name)})
            p = p.parent
        context['user'] = self.user = users.get_current_user()
        if self.user:
            context['logout'] = users.create_logout_url(self.uri_for('home'))
            context["is_current_user_admin"] = users.is_current_user_admin()
        else:
            context['login'] = users.create_login_url(self.uri_for('home'))
        context['remote_addr'] = self.request.remote_addr
        context['request_uri'] = self.request.uri
        if self.is_https_request():
            context['request_uri'] = context['request_uri'].replace(
                'http://', 'https://')
        return context

    def generate_csrf_cookie(self):
        """generate a secure cookie if not already present"""
        sc = securecookie.SecureCookieSerializer(settings.cookie_secret)
        try:
            cookie = self.request.cookies[self.CSRF_COOKIE_NAME]
            csrf_key = sc.deserialize(self.CSRF_COOKIE_NAME, cookie)
        except KeyError:
            csrf_key = None
        if csrf_key is None:
            csrf_key = security.generate_random_string(
                length=self.CSRF_KEY_LENGTH)
            cookie = sc.serialize(self.CSRF_COOKIE_NAME, csrf_key)
            self.response.set_cookie(self.CSRF_COOKIE_NAME, cookie, httponly=True,
                                     max_age=self.CSRF_EXPIRY)
        return csrf_key

    def generate_csrf_token(self, service, csrf_key):
        """generate a CSRF token that can be used as a hidden form field"""
        logging.debug('generate_csrf URI: {}'.format(self.request.uri))
        logging.debug(
            'generate_csrf User-Agent: {}'.format(self.request.headers['User-Agent']))
        sig = hmac.new(settings.csrf_secret, csrf_key, hashlib.sha1)
        cur_url = urlparse.urlparse(self.request.uri, 'http')
        salt = security.generate_random_string(length=self.CSRF_SALT_LENGTH)
        origin = '%s://%s' % (cur_url.scheme, cur_url.netloc)
        logging.debug('generate_csrf origin: {}'.format(origin))
        # print('generate', service, csrf_key, origin, self.request.headers['User-Agent'], salt)
        sig.update(service)
        sig.update(origin)
        # sig.update(self.request.uri)
        sig.update(self.request.headers['User-Agent'])
        sig.update(salt)
        sig = sig.digest()
        rv = urllib.quote(salt + base64.b64encode(sig))
        # print('csrf', service, rv)
        return rv

    def check_csrf(self, service):
        """
        check that the CSRF token from the cookie and the submitted form match
        """
        sc = securecookie.SecureCookieSerializer(settings.cookie_secret)
        try:
            cookie = self.request.cookies[self.CSRF_COOKIE_NAME]
        except KeyError:
            logging.debug("csrf cookie not present")
            logging.debug(str(self.request.cookies))
            raise CsrfFailureException(
                "{} cookie not present".format(self.CSRF_COOKIE_NAME))
        csrf_key = sc.deserialize(self.CSRF_COOKIE_NAME, cookie)
        if not csrf_key:
            logging.debug("csrf deserialize failed")
            self.response.delete_cookie(self.CSRF_COOKIE_NAME)
            raise CsrfFailureException("csrf cookie not valid")
        try:
            token = str(urllib.unquote(self.request.params['csrf_token']))
        except KeyError:
            raise CsrfFailureException("csrf_token not present")
        try:
            origin = self.request.headers['Origin']
        except KeyError:
            logging.debug(
                "No origin in request, using: {}".format(self.request.uri))
            cur_url = urlparse.urlparse(self.request.uri, 'http')
            origin = '%s://%s' % (cur_url.scheme, cur_url.netloc)
        logging.debug("check_csrf origin: {}".format(origin))
        if not memcache.add(key=token, value=origin,
                            time=self.CSRF_EXPIRY, namespace=service):
            raise CsrfFailureException("Re-use of csrf_token")
        salt = token[:self.CSRF_SALT_LENGTH]
        token = token[self.CSRF_SALT_LENGTH:]
        sig = hmac.new(settings.csrf_secret, csrf_key, hashlib.sha1)
        sig.update(service)
        sig.update(origin)
        # logging.debug("check_csrf Referer: {}".format(self.request.headers['Referer']))
        # sig.update(self.request.headers['Referer'])
        sig.update(self.request.headers['User-Agent'])
        sig.update(salt)
        sig_hex = sig.hexdigest()
        tk_hex = binascii.b2a_hex(base64.b64decode(token))
        if sig_hex != tk_hex:
            logging.debug("signatures do not match: %s %s", sig_hex, tk_hex)
            raise CsrfFailureException("signatures do not match")
        return True

    def get_bool_param(self, param, default=False):
        value = self.request.params.get(param, str(default)).lower()
        return value in ["1", "true"]

    def generate_drm_dict(self, stream, keys):
        if isinstance(stream, basestring):
            stream = models.Stream.query(models.Stream.prefix == stream).get()
        templates = TemplateFactory.get_singleton()
        drms = self.request.params.get('drm', 'all')
        rv = {}
        for name in drms.split(','):
            if '-' in name:
                parts = name.split('-')
                drm_name = parts[0]
                locations = set(parts[1:])
            else:
                drm_name = name
                locations = None
            if drm_name in {'all', 'playready'}:
                mspr = PlayReady(templates)
                rv['playready'] = mspr.generate_manifest_context(
                    stream, keys, self.request.params, locations=locations)
            if drm_name in {'all', 'marlin'}:
                marlin = Marlin(templates)
                rv['marlin'] = marlin.generate_manifest_context(
                    stream, keys, self.request.params, locations=locations)
            if drm_name in {'all', 'clearkey'}:
                ck = ClearKey(templates)
                ck_laurl = urlparse.urljoin(
                    self.request.host_url, self.uri_for('clearkey'))
                if self.is_https_request():
                    ck_laurl = ck_laurl.replace('http://', 'https://')
                rv['clearkey'] = ck.generate_manifest_context(
                    stream, keys, self.request.params, la_url=ck_laurl, locations=locations)
        return rv

    def calculate_dash_params(self, prefix, mode, mpd_url):
        stream = models.Stream.query(models.Stream.prefix == prefix).get()
        if stream is None:
            raise ValueError("Invalid stream prefix {0}".format(prefix))
        if mpd_url is None:
            raise ValueError("Unable to determin MPD URL")
        manifest_info = manifests.manifest[mpd_url]
        encrypted = self.request.params.get('drm', 'none').lower() != 'none'
        now = datetime.datetime.now(tz=UTC())
        clockDrift = 0
        try:
            clockDrift = int(self.request.params.get('drift', '0'), 10)
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
            "stream": stream,
            "suggestedPresentationDelay": 30,
        }
        period = Period(start=datetime.timedelta(0), id="p0")
        audio = self.calculate_audio_context(stream, mode, encrypted)
        max_items = None
        if rv['abr'] is False:
            max_items = 1
        video = self.calculate_video_context(stream, mode, encrypted, max_items=max_items)
        if video.representations:
            rv["ref_representation"] = video.representations[0]
        else:
            rv["ref_representation"] = audio.representations[0]
        timing = DashTiming(mode, now, rv["ref_representation"], self.request.params)
        rv.update(timing.generate_manifest_context())
        cgi_params = self.calculate_cgi_parameters(
            mode=mode, now=now, avail_start=timing.availabilityStartTime,
            clockDrift=clockDrift, ts_buffer_depth=timing.timeShiftBufferDepth,
            audio=audio, video=video)
        video.append_cgi_params(cgi_params['video'])
        audio.append_cgi_params(cgi_params['audio'])
        if cgi_params['manifest']:
            locationURL = self.request.uri
            if '?' in locationURL:
                locationURL = locationURL[:self.request.uri.index('?')]
            locationURL = locationURL + utils.objects.dict_to_cgi_params(cgi_params['manifest'])
            rv["locationURL"] = locationURL
        use_base_url = self.get_bool_param('base', True)
        if use_base_url:
            if mode == 'odvod':
                rv["baseURL"] = urlparse.urljoin(
                    self.request.host_url, '/dash/vod') + '/'
            else:
                rv["baseURL"] = urlparse.urljoin(
                    self.request.host_url, '/dash/' + mode) + '/'
            if self.is_https_request():
                rv["baseURL"] = rv["baseURL"].replace('http://', 'https://')
        else:
            if mode == 'odvod':
                prefix = self.uri_for(
                    'dash-od-media', filename='RepresentationID', ext='m4v')
                prefix = prefix.replace('RepresentationID.m4v', '')
            else:
                prefix = self.uri_for('dash-media', mode=mode, filename='RepresentationID',
                                      segment_num='init', ext='m4v')
                prefix = prefix.replace('RepresentationID/init.m4v', '')
                video.initURL = prefix + video.initURL
                audio.initURL = prefix + audio.initURL
            video.mediaURL = prefix + video.mediaURL
            audio.mediaURL = prefix + audio.mediaURL
        event_generators = EventFactory.create_event_generators(self.request)
        for evgen in event_generators:
            ev_stream = evgen.create_manifest_context(
                context=rv, templates=TemplateFactory.get_singleton())
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
                id=(idx + 2), lang=rep.language, representations=[rep])
            rep.set_reference_representation(rv["ref_representation"])
            rep.set_dash_timing(timing)
            if len(audio.representations) == 1:
                audio_adp.role = 'main'
            elif self.request.params.get('main_audio', None) == rep.id:
                audio_adp.role = 'main'
            elif rep.codecs.startswith(self.request.params.get('main_audio', 'mp4a')):
                audio_adp.role = 'main'
            else:
                audio_adp.role = 'alternate'
            period.adaptationSets.append(audio_adp)

        rv["periods"].append(period)
        kids = set()
        for rep in video.representations + audio.representations:
            if rep.encrypted:
                kids.update(rep.kids)
        rv["kids"] = kids
        rv["mediaDuration"] = rv["ref_representation"].mediaDuration / \
            rv["ref_representation"].timescale
        rv["maxSegmentDuration"] = max(video.maxSegmentDuration,
                                       audio.maxSegmentDuration)
        if encrypted:
            if not kids:
                rv["keys"] = models.Key.all_as_dict()
            else:
                rv["keys"] = models.Key.get_kids(kids)
            rv["DRM"] = self.generate_drm_dict(stream, rv["keys"])
        try:
            timeSource = {'format': self.request.params['time']}
            if timeSource['format'] == 'xsd':
                timeSource['method'] = 'urn:mpeg:dash:utc:http-xsdate:2014'
            elif timeSource['format'] == 'iso':
                timeSource['method'] = 'urn:mpeg:dash:utc:http-iso:2014'
            elif timeSource['format'] == 'ntp':
                timeSource['method'] = 'urn:mpeg:dash:utc:http-ntp:2014'
            elif timeSource['format'] == 'head':
                timeSource['method'] = 'urn:mpeg:dash:utc:http-head:2014'
                timeSource['format'] = 'ntp'
            else:
                raise KeyError('Unknown time format')
        except KeyError:
            timeSource = {
                'method': 'urn:mpeg:dash:utc:http-xsdate:2014',
                          'format': 'xsd'
            }
        if 'url' not in timeSource:
            timeSource['url'] = urlparse.urljoin(
                self.request.host_url,
                self.uri_for('time', format=timeSource['format']))
            timeSource['url'] += utils.objects.dict_to_cgi_params(cgi_params['time'])
        rv["timeSource"] = timeSource
        if 'periods' not in manifest_info.features:
            rv["video"] = video
            rv["audio"] = audio
            rv["period"] = rv["periods"][0]
        return rv

    def calculate_audio_context(self, stream, mode, encrypted, max_items=None):
        audio = AdaptationSet(mode=mode, contentType='audio', id=2)
        acodec = self.request.params.get('acodec')
        media_files = models.MediaFile.search(contentType='audio', prefix=stream.prefix,
                                              maxItems=max_items)
        for mf in media_files:
            r = mf.representation
            assert r.contentType == 'audio'
            assert mf.contentType == 'audio'
            if r.encrypted == encrypted:
                if acodec is None or r.codecs.startswith(acodec):
                    audio.representations.append(r)
        # if stream is encrypted but there is no encrypted version of the audio track, fall back
        # to a clear version
        if not audio.representations and acodec:
            for mf in media_files:
                r = mf.representation
                if r.codecs.startswith(acodec):
                    audio.representations.append(r)
        audio.compute_av_values()
        assert(isinstance(audio.representations, list))
        return audio

    def calculate_video_context(self, stream, mode, encrypted, max_items=None):
        video = AdaptationSet(mode=mode, contentType='video', id=1)
        media_files = models.MediaFile.search(
            contentType='video', encrypted=encrypted, prefix=stream.prefix,
            maxItems=max_items)
        for mf in media_files:
            assert mf.contentType == 'video'
            assert mf.representation.contentType == 'video'
            video.representations.append(mf.representation)
        video.compute_av_values()
        assert(isinstance(video.representations, list))
        return video

    def calculate_cgi_parameters(self, mode, now, avail_start, clockDrift,
                                 ts_buffer_depth, audio, video):
        v_cgi_params = {}
        a_cgi_params = {}
        m_cgi_params = copy.deepcopy(dict(self.request.params))
        t_cgi_params = {}
        param_list = ['drm', 'marlin_la_url', 'playready_la_url', 'start']
        if self.request.params.get('events', None) is not None:
            param_list.append('events')
            event_generators = EventFactory.create_event_generators(self.request)
            for evg in event_generators:
                param_list += evg.cgi_parameters().keys()
        for param in param_list:
            value = self.request.params.get(param)
            if value is None or (param == 'drm' and value == 'none'):
                continue
            if param == 'start':
                value = toIsoDateTime(avail_start)
            v_cgi_params[param] = value
            a_cgi_params[param] = value
            m_cgi_params[param] = value
        if clockDrift:
            t_cgi_params['drift'] = str(clockDrift)
            v_cgi_params['drift'] = str(clockDrift)
            a_cgi_params['drift'] = str(clockDrift)
        if mode == 'live' and ts_buffer_depth != DashTiming.DEFAULT_TIMESHIFT_BUFFER_DEPTH:
            v_cgi_params['depth'] = str(ts_buffer_depth)
            a_cgi_params['depth'] = str(ts_buffer_depth)
        for code in self.INJECTED_ERROR_CODES:
            if self.request.params.get('v%03d' % code) is not None:
                times = self.calculate_injected_error_segments(
                    self.request.params.get('v%03d' % code),
                    now,
                    avail_start,
                    ts_buffer_depth,
                    video.representations[0])
                if times:
                    v_cgi_params['%03d' % (code)] = times
            if self.request.params.get('a%03d' % code) is not None:
                times = self.calculate_injected_error_segments(
                    self.request.params.get('a%03d' % code),
                    now,
                    avail_start,
                    ts_buffer_depth,
                    audio.representations[0])
                if times:
                    a_cgi_params['%03d' % (code)] = times
        if self.request.params.get('vcorrupt') is not None:
            segs = self.calculate_injected_error_segments(
                self.request.params.get('vcorrupt'),
                now,
                avail_start,
                ts_buffer_depth,
                video.representations[0])
            if segs:
                v_cgi_params['corrupt'] = segs
        try:
            updateCount = int(self.request.params.get('update', '0'), 10)
            m_cgi_params['update'] = str(updateCount + 1)
        except ValueError as err:
            logging.warning('Invalid update CGI parameter: %s', err)

        return {
            'audio': a_cgi_params,
            'video': v_cgi_params,
            'manifest': m_cgi_params,
            'time': t_cgi_params,
        }

    def add_allowed_origins(self):
        allowed_domains = getattr(settings, 'allowed_domains', self.DEFAULT_ALLOWED_DOMAINS)
        if allowed_domains == "*":
            self.response.headers.add_header("Access-Control-Allow-Origin", "*")
            self.response.headers.add_header("Access-Control-Allow-Methods", "HEAD, GET, POST")
            return
        try:
            if isinstance(allowed_domains, str):
                allowed_domains = re.compile(allowed_domains)
            if allowed_domains.search(self.request.headers['Origin']):
                self.response.headers.add_header("Access-Control-Allow-Origin",
                                                 self.request.headers['Origin'])
                self.response.headers.add_header("Access-Control-Allow-Methods", "HEAD, GET, POST")
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
            drop_seg = long(scale_timedelta(
                drop_delta, representation.timescale, representation.segment_duration))
            drops.append('%d' % drop_seg)
        return urllib.quote_plus(','.join(drops))

    def increment_memcache_counter(self, segment, code):
        try:
            key = 'inject-%06d-%03d-%s' % (segment,
                                           code, self.request.headers['Referer'])
        except KeyError:
            key = 'inject-%06d-%03d-%s' % (segment,
                                           code, self.request.headers['Host'])
        client = memcache.Client()
        timeout = 10
        while timeout:
            counter = client.gets(key)
            if counter is None:
                client.add(key, 1, time=60)
                return 1
            if client.cas(key, counter + 1, time=60):
                return counter + 1
            timeout -= 1
        return -1

    def get_http_range(self, content_length):
        try:
            http_range = self.request.headers['range'].lower().strip()
        except KeyError:
            return (None, None)
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
        if isinstance(start, (str, unicode)):
            start = int(start, 10)
        if isinstance(end, (str, unicode)):
            end = int(end, 10)
        if end >= content_length or end < start:
            self.response.set_status(416)
            self.response.headers.add_header(
                'Content-Range', 'bytes */{length}'.format(length=content_length))
            raise ValueError('Invalid content range')
        self.response.set_status(206)
        self.response.headers.add_header(
            'Content-Range', 'bytes {start}-{end}/{length}'.format(start=start, end=end, length=content_length))
        return (start, end)

    def is_https_request(self):
        if self.request.scheme == 'https':
            return True
        if self.request.environ.get('HTTPS', 'off') == 'on':
            return True
        return self.request.headers.get('X-HTTP-Scheme', 'http') == 'https'


class HTMLHandlerBase(RequestHandlerBase):
    """
    Base class for all HTML pages
    """

    SCRIPT_TEMPLATE = r'<script src="/js/{mode}/{filename}{minify}.js" type="text/javascript"></script>'

    def create_context(self, **kwargs):
        context = super(HTMLHandlerBase, self).create_context(**kwargs)
        context.update({
            'routes': routes,
            'import_script': self.import_script,
        })
        return context

    def import_script(self, filename):
        mode = 'dev' if settings.DEBUG else 'prod'
        minify = '' if settings.DEBUG else '.min'
        return self.SCRIPT_TEMPLATE.format(mode=mode, filename=filename, minify=minify)
