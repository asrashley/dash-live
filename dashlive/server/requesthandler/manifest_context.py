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
from dashlive.utils.lang import lang_is_equal
from dashlive.utils.timezone import UTC

from .cgi_parameter_collection import CgiParameterCollection
from .drm_context import DrmContext
from .time_source_context import TimeSourceContext
from .utils import is_https_request

class ManifestContext:
    baseURL: str | None = None
    cgi_params: CgiParameterCollection
    locationURL: str
    manifest: DashManifest | None
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

    def __init__(
            self,
            options: OptionsContainer,
            manifest: DashManifest | None,
            stream: models.Stream | None,
            multi_period: models.MultiPeriodStream | None) -> None:
        if multi_period is None and stream is None:
            raise ValueError('Either Stream or MultiPeriodStream must be provided')

        now = datetime.datetime.now(tz=UTC())
        if options.clockDrift:
            now -= datetime.timedelta(seconds=options.clockDrift)
        self.minBufferTime = datetime.timedelta(seconds=1.5)
        self.manifest = manifest
        if multi_period:
            self.mpd_id = multi_period.name
            self.title = multi_period.title
        else:
            self.mpd_id = stream.directory
            self.title = stream.title
            self.timing_ref = stream.timing_reference
        self.now = now
        self.options = options
        self.periods = []
        self.profiles = [primary_profiles[options.mode]]
        self.startNumber = 1
        self.suggestedPresentationDelay = 30

        if options.mode != 'odvod':
            self.profiles.append(additional_profiles['dvb'])

        timing: DashTiming | None = None
        if self.timing_ref is not None:
            timing = DashTiming(self.now, self.timing_ref, options)
            self.mediaDuration = self.timing_ref.media_duration_timedelta().total_seconds()

        if multi_period:
            self.create_all_periods(multi_period)
        else:
            self.periods.append(
                self.create_period(stream, timing, db_period=None))
        self.timeSource = None
        if self.options.mode == 'live' and self.options.utcMethod is not None:
            self.timeSource = TimeSourceContext(self.options, self.cgi_params, now)

        if (
                self.options.mode == 'live' and
                options.patch and
                self.manifest is not None and
                timing is not None):
            patch_loc = flask.url_for(
                'mpd-patch',
                stream=stream.directory,
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

    @property
    def maxSegmentDuration(self) -> float:
        if not self.periods:
            return 1
        return max([p.maxSegmentDuration for p in self.periods])

    def create_all_periods(self,
                           multi_period: models.MultiPeriodStream) -> None:
        start: datetime.timedelta = datetime.timedelta(0)
        for prd in multi_period.periods:
            timing = DashTiming(
                self.now, prd.stream.timing_reference, self.options)
            period = self.create_period(
                stream=prd.stream, timing=timing, db_period=prd)
            period.start = start
            self.periods.append(period)
            start += period.duration

    def create_period(self,
                      stream: models.Stream,
                      timing: DashTiming | None,
                      db_period: models.Period | None) -> Period:
        opts = self.options

        if db_period:
            period: Period = Period(
                start=datetime.timedelta(0), id=db_period.pid,
                duration=db_period.duration)
        else:
            period = Period(start=datetime.timedelta(0), id="p0")
        max_items = None
        if opts.abr is False:
            max_items = 1

        video: AdaptationSet | None = None
        audio_adps: list[AdaptationSet] = []
        text_adps: list[AdaptationSet] = []
        if db_period:
            for adp in db_period.adaptation_sets:
                adp_set = AdaptationSet(
                    mode=self.options.mode,
                    content_type=adp.content_type.name,
                    id=adp.track_id,
                    role=adp.role.name.lower(),
                    segment_timeline=self.options.segmentTimeline)
                for mf in adp.media_files(encrypted=self.options.encrypted):
                    if mf.representation is None:
                        mf.parse_media_file()
                    if mf.representation is None:
                        continue
                    adp_set.representations.append(mf.representation)
                adp_set.compute_av_values()
                period.adaptationSets.append(adp_set)
                if adp_set.content_type == 'video':
                    video = adp_set
                elif adp_set.content_type == 'audio':
                    audio_adps.append(adp_set)
                elif adp_set.content_type == 'text':
                    text_adps.append(adp_set)
        else:
            video = self.calculate_video_adaptation_set(
                stream, max_items=max_items)
            audio_adps = self.calculate_audio_adaptation_sets(stream)
            text_adps = self.calculate_text_adaptation_sets(
                stream, video.lang)
        assert video is not None
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
        if db_period is None:
            period.adaptationSets.append(video)
            period.adaptationSets += audio_adps
            period.adaptationSets += text_adps
        if db_period:
            base_url: str = flask.url_for(
                "mps-base-url", mode=opts.mode, mps_name=db_period.parent.name,
                ppk=db_period.pk)
        elif opts.mode == "odvod":
            base_url = flask.url_for(
                'dash-od-media-base-url', stream=stream.directory)
        else:
            base_url = flask.url_for(
                'dash-media-base-url', mode=opts.mode, stream=stream.directory)

        period.finish_setup(
            mode=opts.mode, timing=timing, base_url=base_url,
            use_base_urls=opts.useBaseUrls)
        if is_https_request():
            period.baseURL = period.baseURL.replace('http://', 'https://')
        for adp in period.adaptationSets:
            if not adp.encrypted:
                continue
            kids: Set[KeyMaterial] = adp.key_ids()
            keys = models.Key.get_kids(kids)
            dc = DrmContext(stream, keys, self.options)
            adp.drm = dc.manifest_context
            adp.default_kid = list(keys.keys())[0]
        return period

    def calculate_video_adaptation_set(
            self,
            stream: models.Stream,
            max_items: int | None = None) -> AdaptationSet:
        video = AdaptationSet(
            mode=self.options.mode, content_type='video', id=1,
            segment_timeline=self.options.segmentTimeline)
        media_files = models.MediaFile.search(
            content_type='video', encrypted=self.options.encrypted,
            stream=stream, max_items=max_items)
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
            self,
            stream: models.Stream,
            max_items: int | None = None) -> list[AdaptationSet]:
        opts = self.options
        adap_sets: dict[int, AdaptationSet] = {}
        media_files = models.MediaFile.search(
            content_type='audio', stream=stream, max_items=max_items)
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
                    id=r.track_id,
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
            self,
            stream: models.Stream,
            video_lang: str | None,
            max_items: int | None = None) -> list[AdaptationSet]:
        opts = self.options

        media_files = models.MediaFile.search(
            content_type='text', stream=stream, max_items=max_items)
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
            # if stream is encrypted but there is no encrypted version of the
            # text track, fall back to a clear version
            for mf in media_files:
                r = mf.representation
                if opts.textCodec is None or r.codecs.startswith(
                        opts.textCodec):
                    text_tracks.append(r)
        result: list[AdaptationSet] = []
        main_text: int | None = None
        for index, r in enumerate(text_tracks):
            text = AdaptationSet(
                mode=opts.mode, content_type='text',
                id=r.track_id,
                segment_timeline=opts.segmentTimeline)
            if lang_is_equal(text.lang, video_lang, True):
                # Subtitles in the same language as the programme
                text.accessibility = {
                    'schemeIdUri': "urn:tva:metadata:cs:AudioPurposeCS:2007",
                    'value': 2,
                }
                if main_text is None:
                    main_text = index
            elif opts.mainText == r.id:
                main_text = index
            text.representations.append(r)
            text.compute_av_values()
            result.append(text)
        if main_text is None:
            main_text = 0
        for index, adp in enumerate(result):
            if main_text == index:
                adp.role = 'main'
            else:
                adp.role = 'alternate'
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
