import datetime
import logging
import unittest

from dashlive.mpeg.dash.reference import StreamTimingReference
from dashlive.mpeg.dash.representation import Representation
from dashlive.mpeg.dash.segment import Segment
from dashlive.mpeg.dash.timing import DashTiming
from dashlive.server.options.repository import OptionsRepository

from .mixins.mixin import TestCaseMixin

class TestDashTiming(TestCaseMixin, unittest.TestCase):
    def create_representation(self, mode: str, **kwargs) -> tuple[StreamTimingReference, Representation]:
        stream_ref = StreamTimingReference(
            media_name='bbb_v1',
            media_duration=142080,
            num_media_segments=148,
            segment_duration=960,
            timescale=240)
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
            # duration = num * stream_ref.segment_duration
            segments.append(Segment(
                pos=(42 + num * 123),
                size=123,
                duration=stream_ref.segment_duration))
        rp = Representation(
            content_type='video',
            segments=segments,
            timescale=stream_ref.timescale,
            segment_duration=stream_ref.segment_duration)
        rp.set_dash_timing(timing)
        return (stream_ref, rp,)

    def test_generate_segment_timeline_vod(self) -> None:
        stream_ref, rep = self.create_representation('vod')
        timeline = rep.generateSegmentTimeline()
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0].start, 0)
        self.assertEqual(timeline[0].count, stream_ref.num_media_segments)
        self.assertEqual(timeline[0].duration, stream_ref.segment_duration)

    def test_generate_segment_timeline_live(self) -> None:
        stream_ref, rep = self.create_representation('live')
        self.assertEqual(rep._timing.elapsedTime, datetime.timedelta(seconds=3600))
        # 3540 = 3600 - 60 (the timeShiftBufferDepth)
        self.assertEqual(rep._timing.firstAvailableTime, datetime.timedelta(seconds=3540))
        timeline_start = 3540 * 240
        mod_segment_num, origin_time = rep.calculate_segment_from_timecode(timeline_start)
        self.assertGreaterThan(mod_segment_num, 0)
        self.assertLessThanOrEqual(mod_segment_num, stream_ref.num_media_segments)
        tc = origin_time + (mod_segment_num - 1)* stream_ref.segment_duration
        self.assertEqual(tc, timeline_start)
        timeline = rep.generateSegmentTimeline()
        self.assertEqual(len(timeline), 1)
        num_segments = 60 // 4 # 60 seconds, 4 second fragments
        self.assertEqual(timeline[0].count, num_segments)
        end_time = 3600 * 240
        start_time = 3540 * 240
        self.assertEqual(timeline[0].start, start_time)
        self.assertEqual(timeline[0].duration, stream_ref.segment_duration)
        total_dur = timeline[0].count * stream_ref.segment_duration
        self.assertEqual(total_dur, 60 * 240)

    def test_calculate_segment_number_and_time_vod(self) -> None:
        stream_ref, rep = self.create_representation('vod')
        segment_time = 123 * 4 * 240
        segment_num, mod_segment, origin_time = rep.calculate_segment_number_and_time(
            segment_time, None)
        self.assertEqual(segment_num, 124)
        self.assertEqual(mod_segment, 124)
        self.assertEqual(origin_time, 0)

    def test_calculate_segment_number_and_time_live(self) -> None:
        stream_ref, rep = self.create_representation('live')
        start_time = 3556 * 240
        segment_num, mod_segment, origin_time = rep.calculate_segment_number_and_time(
            start_time, None)
        tc = origin_time + (mod_segment - 1) * 960
        self.assertEqual(tc, start_time)
        sn = int(start_time // 960)
        self.assertEqual(segment_num, sn)
        while sn > stream_ref.num_media_segments:
            sn -= stream_ref.num_media_segments
        self.assertEqual(mod_segment, sn + 1)

    def test_calculate_segment_number_and_time_leeway(self) -> None:
        stream_ref, rep = self.create_representation('live')
        with self.assertRaises(ValueError):
            rep.calculate_segment_number_and_time(0, None)
        start_time = 3520 * 240 # 20 seconds beyond start of timeshift buffer
        with self.assertRaises(ValueError):
            rep.calculate_segment_number_and_time(start_time, None)
        stream_ref, rep = self.create_representation('live', leeway='30')
        segment_num, mod_segment, origin_time = rep.calculate_segment_number_and_time(
            start_time, None)
        start_time = 3500 * 240 # 40 seconds beyond start of timeshift buffer
        with self.assertRaises(ValueError):
            rep.calculate_segment_number_and_time(start_time, None)

if __name__ == "__main__":
    # logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
