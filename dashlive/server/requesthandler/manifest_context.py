#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import datetime
import math
from typing import AbstractSet, Set, cast
import urllib.parse

import flask  # type: ignore

from dashlive.drm.keymaterial import KeyMaterial
from dashlive.mpeg.dash.adaptation_set import AdaptationSet
from dashlive.mpeg.dash.patch_location import PatchLocation
from dashlive.mpeg.dash.period import Period
from dashlive.mpeg.dash.profiles import primary_profiles, additional_profiles
from dashlive.mpeg.dash.reference import StreamTimingReference
from dashlive.mpeg.dash.representation import Representation
from dashlive.mpeg.dash.timing import (
    DashTiming,
    DynamicManifestTimingContext,
    StaticManifestTimingContext,
)
from dashlive.server import models
from dashlive.server.events.factory import EventFactory
from dashlive.server.manifests import DashManifest
from dashlive.server.options.container import OptionsContainer
from dashlive.server.options.types import OptionUsage
from dashlive.utils import objects
from dashlive.utils.date_time import scale_timedelta
from dashlive.utils.json_object import JsonObject
from dashlive.utils.timezone import UTC

from .cgi_parameter_collection import CgiParameterCollection
from .decorators import current_stream
from .drm_context import DrmContext
from .time_source_context import TimeSourceContext
from .utils import is_https_request

class ManifestContext:
    baseURL: str | None = None
    cgi_params: CgiParameterCollection
    locationURL: str
    manifest: DashManifest | None
    maxSegmentDuration: int
    mediaDuration: int
    minBufferTime: datetime.timedelta
    mpd_name: str
    mpd_id: str
    now: datetime.datetime
    options: OptionsContainer
    patch: PatchLocation | None = None
    periods: list[Period]
    profiles: list[str]
    startNumber: int
    stream: models.Stream
    suggestedPresentationDelay: int
    timeSource: TimeSourceContext | None = None
    timing_ref: StreamTimingReference | None = None
    title: str

    def __init__(self,
                 options: OptionsContainer,
                 manifest: DashManifest | None = None,
                 stream: models.Stream | None = None) -> None:
        if stream is None:
            stream = current_stream
        if not bool(stream):
            raise ValueError('Stream model is not available')

        now = datetime.datetime.now(tz=UTC())
        if options.clockDrift:
            now -= datetime.timedelta(seconds=options.clockDrift)
        self.minBufferTime = datetime.timedelta(seconds=1.5)
        self.manifest = manifest
        self.mpd_id = stream.directory
        self.now = now
        self.options = options
        self.maxSegmentDuration = 0
        self.periods = []
        self.profiles = [primary_profiles[options.mode]]
        self.startNumber = 1
        self.stream = stream  # .to_dict(exclude={'media_files'}),
        self.suggestedPresentationDelay = 30
        self.timing_ref = stream.timing_reference
        self.title = stream.title

        if options.mode != 'odvod':
            self.profiles.append(additional_profiles['dvb'])

        timing: DashTiming | None = None
        if self.timing_ref is not None:
            timing = DashTiming(self.now, self.timing_ref, options)
            self.mediaDuration = self.timing_ref.media_duration_timedelta().total_seconds()

        self.periods.append(self.create_period(timing))
        self.timeSource = None
        if self.options.mode == 'live' and self.options.utcMethod is not None:
            self.timeSource = TimeSourceContext(self.options, self.cgi_params, now)
        self.finish_periods_setup(timing)

        if (
                self.options.mode == 'live' and
                options.patch and
                self.manifest is not None and
                timing is not None):
            patch_loc = flask.url_for(
                'mpd-patch',
                stream=self.stream.directory,
                manifest=self.manifest.name,
                publish=int(timing.publishTime.timestamp()))
            ttl = max(
                timing.timeShiftBufferDepth,
                int(math.ceil(timing.minimumUpdatePeriod)))
            if self.cgi_params.patch:
                patch_loc += objects.dict_to_cgi_params(self.cgi_params.patch)
            self.patch = PatchLocation(location=patch_loc, ttl=ttl)

    def to_dict(self,
                exclude: AbstractSet[str] | None = None,
                only: AbstractSet[str] | None = None
                ) -> JsonObject:
        retval: JsonObject = {}
        if exclude is None:
            exclude = set()
        for key, value in self.__dict__.items():
            if only is not None and key not in only:
                continue
            if key in exclude:
                continue
            retval[key] = value
        return retval

    @property
    def period(self) -> Period:
        if self.periods:
            return self.periods[0]
        raise IndexError('periods list is empty')

    @property
    def video(self) -> AdaptationSet:
        if not self.periods:
            raise IndexError('periods list is empty')
        for adp in self.periods[0].adaptationSets:
            if adp.content_type == 'video':
                return adp
        raise AttributeError('Failed to find a video AdaptationSet')

    @property
    def audio_sets(self) -> list[AdaptationSet]:
        rv: list[AdaptationSet] = []
        if not self.periods:
            return rv
        for adp in self.periods[0].adaptationSets:
            if adp.content_type == 'audio':
                rv.append(adp)
        return rv

    @property
    def text_sets(self) -> list[AdaptationSet]:
        rv: list[AdaptationSet] = []
        if not self.periods:
            return rv
        for adp in self.periods[0].adaptationSets:
            if adp.content_type == 'text':
                rv.append(adp)
        return rv

    def create_period(self, timing: DashTiming | None) -> Period:
        opts = self.options

        period = Period(start=datetime.timedelta(0), id="p0")
        audio_adps = self.calculate_audio_adaptation_sets()
        text_adps = self.calculate_text_adaptation_sets()
        max_items = None
        if opts.abr is False:
            max_items = 1
        video = self.calculate_video_adaptation_set(max_items=max_items)

        if timing:
            opts.availabilityStartTime = timing.availabilityStartTime
            opts.timeShiftBufferDepth = timing.timeShiftBufferDepth
            self.update_timing(timing)

        self.cgi_params = self.calculate_cgi_parameters(
            audio=audio_adps, video=video)
        video.append_cgi_params(self.cgi_params.video)
        for audio in audio_adps:
            audio.append_cgi_params(self.cgi_params.audio)
        for text in text_adps:
            text.append_cgi_params(self.cgi_params.text)
        if self.cgi_params.manifest:
            locationURL = flask.request.url
            if '?' in locationURL:
                locationURL = locationURL[:flask.request.url.index('?')]
            locationURL = locationURL + objects.dict_to_cgi_params(self.cgi_params.manifest)
            self.locationURL = locationURL
        event_generators = EventFactory.create_event_generators(opts)
        for evgen in event_generators:
            ev_stream = evgen.create_manifest_context(context=vars(self))
            if evgen.inband:
                # TODO: allow AdaptationSet for inband events to be
                # configurable
                video.event_streams.append(ev_stream)
            else:
                period.event_streams.append(ev_stream)
        period.adaptationSets.append(video)
        period.adaptationSets += audio_adps
        period.adaptationSets += text_adps
        return period

    def calculate_video_adaptation_set(
            self, max_items: int | None = None) -> AdaptationSet:
        video = AdaptationSet(
            mode=self.options.mode, content_type='video', id=1,
            segment_timeline=self.options.segmentTimeline)
        media_files = models.MediaFile.search(
            content_type='video', encrypted=self.options.encrypted,
            stream=self.stream, max_items=max_items)
        for mf in media_files:
            if mf.representation is None:
                mf.parse_media_file()
            if mf.representation is None:
                continue
            assert mf.content_type == 'video'
            assert mf.representation.content_type == 'video'
            video.representations.append(mf.representation)
            assert video.representations[0].track_id == mf.representation.track_id
        video.compute_av_values()
        assert isinstance(video.representations, list)
        return video

    def calculate_audio_adaptation_sets(
            self, max_items: int | None = None) -> list[AdaptationSet]:
        opts = self.options
        adap_sets: dict[int, AdaptationSet] = {}
        media_files = models.MediaFile.search(
            content_type='audio', stream=self.stream, max_items=max_items)
        audio_files: list[Representation] = []
        acodec = opts.audioCodec
        for mf in media_files:
            if mf.representation is None:
                continue
            r = mf.representation
            if r.encrypted != opts.encrypted:
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
                    mode=opts.mode, content_type='audio',
                    id=(100 + r.track_id),
                    segment_timeline=opts.segmentTimeline,
                    numChannels=r.numChannels)
                adap_sets[r.track_id] = audio
            if len(audio_files) == 1 or opts.mainAudio == r.id:
                audio.role = 'main'
            else:
                audio.role = 'alternate'
                if opts.audioDescription == r.id:
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

    def calculate_text_adaptation_sets(
            self, max_items: int | None = None) -> list[AdaptationSet]:
        opts = self.options

        media_files = models.MediaFile.search(
            content_type='text', stream=self.stream, max_items=max_items)
        text_tracks: list[Representation] = []
        for mf in media_files:
            if mf.representation is None:
                continue
            r = mf.representation
            if r.encrypted == opts.encrypted:
                if opts.textCodec is None or r.codecs.startswith(
                        opts.textCodec):
                    text_tracks.append(r)
        if not text_tracks:
            # if stream is encrypted but there is no encrypted version of the text track, fall back
            # to a clear version
            for mf in media_files:
                r = mf.representation
                if opts.textCodec is None or r.codecs.startswith(
                        opts.textCodec):
                    text_tracks.append(r)
        result: list[AdaptationSet] = []
        for r in text_tracks:
            text = AdaptationSet(
                mode=opts.mode, content_type='text',
                id=(200 + r.track_id),
                segment_timeline=opts.segmentTimeline)
            lang_match = (opts.textLanguage is None or
                          text.lang in {'und', opts.textLanguage})
            if len(text_tracks) == 1 or lang_match:
                text.role = 'main'
                # Subtitles for the hard of hearing in the same language as
                # the programme
                text.accessibility = {
                    'schemeIdUri': "urn:tva:metadata:cs:AudioPurposeCS:2007",
                    'value': 2,
                }
            elif opts.mainText == r.id:
                text.role = 'main'
            else:
                text.role = 'alternate'
            text.compute_av_values()
            result.append(text)
        return result

    def calculate_cgi_parameters(
            self,
            audio: list[AdaptationSet],
            video: AdaptationSet) -> CgiParameterCollection:
        exclude = {'encrypted', 'mode'}
        options = self.options

        vid_cgi_params = options.generate_cgi_parameters(
            use=OptionUsage.VIDEO, exclude=exclude)
        aud_cgi_params = options.generate_cgi_parameters(
            use=OptionUsage.AUDIO, exclude=exclude)
        txt_cgi_params = options.generate_cgi_parameters(
            use=OptionUsage.TEXT, exclude=exclude)
        mft_cgi_params = options.generate_cgi_parameters(exclude=exclude)
        patch_cgi_params = options.generate_cgi_parameters(
            exclude=exclude.union({'timeline', 'patch'}))
        clk_cgi_params = options.generate_cgi_parameters(
            use=OptionUsage.TIME, exclude=exclude)

        if options.videoErrors:
            times = self.calculate_injected_error_segments(
                options.videoErrors,
                self.now,
                options.availabilityStartTime,
                options.timeShiftBufferDepth,
                video.representations[0])
            vid_cgi_params['verr'] = times

        if options.audioErrors and audio:
            if audio[0].representations:
                times = self.calculate_injected_error_segments(
                    options.audioErrors,
                    self.now,
                    options.availabilityStartTime,
                    options.timeShiftBufferDepth,
                    audio[0].representations[0])
                aud_cgi_params['aerr'] = times

        if options.videoCorruption:
            errs = [(None, tc) for tc in options.videoCorruption]
            segs = self.calculate_injected_error_segments(
                errs,
                self.now,
                options.availabilityStartTime,
                options.timeShiftBufferDepth,
                video.representations[0])
            vid_cgi_params['vcorrupt'] = segs

        if options.updateCount is not None:
            mft_cgi_params['update'] = str(options.updateCount + 1)

        return CgiParameterCollection(
            audio=aud_cgi_params,
            video=vid_cgi_params,
            text=txt_cgi_params,
            manifest=mft_cgi_params,
            patch=patch_cgi_params,
            time=clk_cgi_params)

    def finish_periods_setup(self, timing: DashTiming | None) -> None:
        prefix: str = ''
        base: str
        if self.options.mode == 'odvod':
            base = flask.url_for(
                'dash-od-media',
                stream=self.stream.directory,
                filename='RepresentationID',
                ext='m4v')
            base = base.replace('RepresentationID.m4v', '')
        else:
            base = flask.url_for(
                'dash-media',
                mode=self.options.mode,
                stream=self.stream.directory,
                filename='RepresentationID',
                segment_num='init',
                ext='m4v')
            base = base.replace('RepresentationID/init.m4v', '')
        if self.options.useBaseUrls:
            self.baseURL = urllib.parse.urljoin(flask.request.host_url, base)
            if is_https_request():
                self.baseURL = self.baseURL.replace('http://', 'https://')
        else:
            # convert every initURL and mediaURL to be an absolute URL
            prefix = base

        for period in self.periods:
            for idx, adp in enumerate(period.adaptationSets):
                kids: Set[KeyMaterial] = set()
                adp.id = idx + 1  # is this needed?
                if prefix:
                    if self.options.mode != 'odvod':
                        adp.initURL = prefix + adp.initURL
                    adp.mediaURL = prefix + adp.mediaURL
                if timing:
                    adp.set_dash_timing(timing)
                self.maxSegmentDuration = max(
                    self.maxSegmentDuration, adp.maxSegmentDuration)
                for rep in adp.representations:
                    if rep.encrypted:
                        kids.update(rep.kids)
                if adp.encrypted:
                    keys = models.Key.get_kids(kids)
                    dc = DrmContext(self.stream, keys, self.options)
                    adp.drm = dc.manifest_context
                    adp.default_kid = list(keys.keys())[0]

    @staticmethod
    def calculate_injected_error_segments(
            errors: list[tuple[int, str]],
            now: datetime.datetime,
            availabilityStartTime: datetime.datetime,
            timeShiftBufferDepth: int,
            representation: Representation) -> str:
        """
        Calculate a list of segment numbers for injecting errors
        :param errors: a list of error definitions. Each definition is a
            tuple of an HTTP error code and either a segment number or
            an ISO8601 time.
        :param availabilityStartTime: datetime.datetime containing
            availability start time
        :param representation: the Representation to use when calculating
            segment numbering
        """
        drops = []
        earliest_available = now - datetime.timedelta(
            seconds=timeShiftBufferDepth)
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
                    drop_delta, representation.timescale,
                    representation.segment_duration))
            if code is None:
                drops.append(f'{drop_seg}')
            else:
                drops.append(f'{code}={drop_seg}')
        return urllib.parse.quote_plus(','.join(drops))

    def update_timing(self, timing: DashTiming) -> None:
        tc = timing.generate_manifest_context()
        self.now = tc.now
        self.publishTime = tc.publishTime
        if self.options.mode != 'live':
            stc = cast(StaticManifestTimingContext, tc)
            self.mediaDuration = stc.mediaDuration
            return
        ltc = cast(DynamicManifestTimingContext, tc)
        self.availabilityStartTime = ltc.availabilityStartTime
        self.elapsedTime = ltc.elapsedTime
        self.minimumUpdatePeriod = ltc.minimumUpdatePeriod
        self.timeShiftBufferDepth = ltc.timeShiftBufferDepth
