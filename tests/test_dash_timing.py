#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import datetime
# import logging
import unittest

from dashlive.mpeg.dash.reference import StreamTimingReference
from dashlive.mpeg.dash.representation import Representation
from dashlive.mpeg.dash.segment import Segment
from dashlive.mpeg.dash.timing import DashTiming
from dashlive.server.options.repository import OptionsRepository
from dashlive.utils.date_time import timecode_to_timedelta

from .mixins.mixin import TestCaseMixin

class TestDashTiming(TestCaseMixin, unittest.TestCase):
    def create_representation(self,
                              mode: str,
                              now: datetime.datetime | None = None,
                              **kwargs) -> tuple[StreamTimingReference, Representation]:
        stream_ref = StreamTimingReference(
            media_name='bbb_v1',
            content_type='video',
            media_duration=142080,
            num_media_segments=148,
            segment_duration=960,
            timescale=240)
        if now is None:
            now = datetime.datetime.fromisoformat('2020-01-01T01:00:00Z')
        defaults = OptionsRepository.get_default_options()
        args = {
            'leeway': '0',
            'depth': '60',
            'start': '2020-01-01T00:00:00Z',
            **kwargs,
        }
        options = OptionsRepository.convert_cgi_options(args, defaults)
        options.add_field('mode', mode)
        timing = DashTiming(now, stream_ref, options)
        segments: list[Segment] = [Segment(pos=0, duration=0, size=42)]
        for num in range(stream_ref.num_media_segments):
            segments.append(Segment(
                pos=(42 + num * 123),
                size=123,
                duration=stream_ref.segment_duration))
        vid = Representation(
            content_type='video',
            segments=segments,
            timescale=stream_ref.timescale,
            segment_duration=stream_ref.segment_duration)
        vid.set_dash_timing(timing)
        # 591996ms
        # 6526756
        segments: list[Segment] = [Segment(pos=0, duration=0, size=12)]
        total_dur = 0
        for num in range(stream_ref.num_media_segments):
            if (num % 3) == 0:
                duration = 177152
            else:
                duration = 176128
            segments.append(Segment(
                pos=(12 + num * 123),
                size=123,
                duration=duration))
            total_dur += duration
        aud = Representation(
            content_type='audio',
            segments=segments,
            timescale=44100,
            segment_duration=int(total_dur // stream_ref.num_media_segments))
        aud.set_dash_timing(timing)
        return (stream_ref, vid, aud,)

    def test_generate_segment_timeline_vod(self) -> None:
        stream_ref, rep, _ = self.create_representation('vod')
        timeline = rep.generateSegmentTimeline()
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0].start, 0)
        self.assertEqual(timeline[0].count, stream_ref.num_media_segments)
        self.assertEqual(timeline[0].duration, stream_ref.segment_duration)

    def test_generate_segment_timeline_live(self) -> None:
        stream_ref, rep, _ = self.create_representation('live')
        self.assertEqual(rep._timing.elapsedTime, datetime.timedelta(seconds=3600))
        # 3540 = 3600 - 60 (the timeShiftBufferDepth)
        self.assertEqual(rep._timing.firstAvailableTime, datetime.timedelta(seconds=3540))
        timeline_start = 3540 * 240
        mod_segment_num, origin_time, seg_start = rep.calculate_segment_from_timecode(
            timeline_start, False)
        self.assertGreaterThan(mod_segment_num, 0)
        self.assertLessThanOrEqual(mod_segment_num, stream_ref.num_media_segments)
        tc = origin_time + (mod_segment_num - 1) * stream_ref.segment_duration
        self.assertEqual(tc, timeline_start)
        self.assertEqual(seg_start, timeline_start)
        timeline = rep.generateSegmentTimeline()
        self.assertEqual(len(timeline), 1)
        num_segments = 60 // 4  # 60 seconds, 4 second fragments
        self.assertEqual(timeline[0].count, num_segments)
        start_time = 3540 * 240
        self.assertEqual(timeline[0].start, start_time)
        self.assertEqual(timeline[0].duration, stream_ref.segment_duration)
        total_dur = timeline[0].count * stream_ref.segment_duration
        self.assertEqual(total_dur, 60 * 240)

    def test_calculate_segment_number_and_time_vod(self) -> None:
        stream_ref, vid, aud = self.create_representation('vod')
        segment_time = 123 * 4 * 240
        segment_num, mod_segment, origin_time = vid.calculate_segment_number_and_time(
            segment_time, None)
        self.assertEqual(segment_num, 124)
        self.assertEqual(mod_segment, 124)
        self.assertEqual(origin_time, 0)
        segment_time = 123 * 4 * 44100
        segment_num, mod_segment, origin_time = aud.calculate_segment_number_and_time(
            segment_time, None)
        self.assertEqual(segment_num, 124)
        self.assertEqual(mod_segment, 124)
        self.assertEqual(origin_time, 0)

    def test_calculate_segment_number_and_time_live(self) -> None:
        def check_rep(rep):
            start_time = 3556 * rep.timescale
            segment_num, mod_segment, origin_time = rep.calculate_segment_number_and_time(
                start_time, None)
            tc = origin_time + (mod_segment - 1) * 4 * rep.timescale
            self.assertEqual(tc, start_time)
            sn = int(start_time // rep.timescale // 4)
            if rep.timescale == rep._timing.stream_reference.timescale:
                self.assertEqual(segment_num, sn)
            else:
                self.assertGreaterThanOrEqual(segment_num, sn - 1)
                self.assertLessThanOrEqual(segment_num, sn + 1)
            while sn > stream_ref.num_media_segments:
                sn -= stream_ref.num_media_segments
            self.assertEqual(mod_segment, sn + 1)

        stream_ref, vid, aud = self.create_representation('live')
        check_rep(vid)
        check_rep(aud)

        now = datetime.datetime.fromisoformat('2023-10-25T07:54:16Z')
        stream_ref, vid, aud = self.create_representation(
            'live', now=now, start='2023-10-01T00:00:00Z')
        mod_segment, origin_time, seg_start_tc = vid.calculate_segment_from_timecode(
            503603210, True)
        self.assertLessThanOrEqual(origin_time, 503603210)

    def test_calculate_segment_number_and_time_leeway(self) -> None:
        stream_ref, rep, _ = self.create_representation('live')
        with self.assertRaises(ValueError):
            rep.calculate_segment_number_and_time(0, None)
        start_time = 3520 * 240  # 20 seconds beyond start of timeshift buffer
        with self.assertRaises(ValueError):
            rep.calculate_segment_number_and_time(start_time, None)
        stream_ref, rep, _ = self.create_representation('live', leeway='30')
        segment_num, mod_segment, origin_time = rep.calculate_segment_number_and_time(
            start_time, None)
        start_time = 3500 * 240  # 40 seconds beyond start of timeshift buffer
        with self.assertRaises(ValueError):
            rep.calculate_segment_number_and_time(start_time, None)

    def test_segment_timeline_drift(self) -> None:
        now = datetime.datetime.fromisoformat('2020-01-01T00:20:00Z')
        for _ in range(20):
            now = self.check_segment_timeline_drift(now=now)

        now = datetime.datetime.fromisoformat("2023-10-25T07:56:58Z")
        start = "2023-10-01T00:00:00Z"
        for _ in range(20):
            now = self.check_segment_timeline_drift(now=now, start=start)

    def check_segment_timeline_drift(self, now: datetime.datetime, **kwargs) -> datetime.datetime:
        # print('======')
        stream_ref, vid, aud = self.create_representation('live', depth='1200', now=now, **kwargs)
        timeline = vid.generateSegmentTimeline()
        vid_segs = []
        num = 1
        tc = None
        dur = 0
        for seg in timeline:
            if seg.start is not None:
                tc = seg.start
            for i in range(seg.repeat + 1):
                vid_segs.append(tc)
                mod_seg, origin, seg_tc = vid.calculate_segment_from_timecode(tc, True)
                self.assertLessThan(
                    origin, tc + vid.timescale,
                    msg=f'{num}: Expected origin {origin} to be less than {tc}')
                self.assertEqual(seg_tc, tc)
                tc += seg.duration
                dur += seg.duration
        next_now = now + timecode_to_timedelta(dur, vid.timescale)
        timeline = aud.generateSegmentTimeline()
        num = 1
        tc = None
        for seg in timeline:
            if seg.start is not None:
                tc = seg.start
            if num == (1 + len(vid_segs)):
                self.assertLessThanOrEqual(num, 1 + len(vid_segs))
                break
            a_delta = timecode_to_timedelta(tc, aud.timescale)
            v_delta = timecode_to_timedelta(vid_segs[num - 1], vid.timescale)
            if num == 1 and a_delta < v_delta:
                tc += seg.duration * (seg.repeat + 1)
                num += seg.repeat
                continue
            # print(num, vid_segs[num - 1], v_delta, tc, a_delta, seg.mod_segment, seg)
            diff = abs(v_delta.total_seconds() - a_delta.total_seconds())
            msg = f'Expected audio {num} segment {a_delta} to almost equal {v_delta} '
            msg += f'now={now}'
            self.assertLessThanOrEqual(diff, 0.25, msg=msg)
            num += seg.repeat + 1
            tc += seg.duration * (seg.repeat + 1)
        return next_now

    def test_live_segment_number(self) -> None:
        now = datetime.datetime.fromisoformat("2022-10-04T12:00:00Z")
        start = "2022-10-04T11:58:00Z"
        stream_ref, vid, aud = self.create_representation('live', depth='1800', now=now, start=start)
        first_fragment, last_fragment = vid.calculate_first_and_last_segment_number()
        self.assertEqual(first_fragment, 1)
        # 30 fragments == 2 minutes
        self.assertEqual(last_fragment, 31)
        aud_first, aud_last = aud.calculate_first_and_last_segment_number()
        self.assertEqual(first_fragment, aud_first)
        # self.assertEqual(last_fragment, aud_last)
        for idx in range(first_fragment, last_fragment):
            seg_num, mod_seg, origin = vid.calculate_segment_number_and_time(None, idx)
            self.assertEqual(idx, seg_num)
            seg_time = origin + (mod_seg - 1) * vid.segment_duration
            self.assertEqual((idx - 1) * vid.segment_duration, seg_time)
            seg_num, mod_seg, origin = aud.calculate_segment_number_and_time(None, idx)
            self.assertEqual(idx, seg_num)
            seg_time = origin + (mod_seg - 1) * aud.segment_duration
            exp = (idx - 1) * aud.segment_duration
            self.assertEqual(
                exp, seg_time,
                msg=f'segment {idx} expected time {exp} got {seg_time}')


if __name__ == "__main__":
    # logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
