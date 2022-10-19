try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

import datetime
import os
import sys
import unittest

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src not in sys.path:
    sys.path.append(_src)

from utils.date_time import from_isodatetime, toIsoDuration, UTC
from utils.buffered_reader import BufferedReader
from utils import objects


class DateTimeTests(unittest.TestCase):
    def test_from_isodatetime(self):
        tests = [
            ('2009-02-27T10:00:00Z', datetime.datetime(2009,
             2, 27, 10, 0, 0, tzinfo=UTC())),
            ('2013-07-25T09:57:31Z', datetime.datetime(2013,
             7, 25, 9, 57, 31, tzinfo=UTC())),
            ('2022-09-21T15:35:31.541000+00:00', datetime.datetime(
                2022, 9, 21, 15, 35, 31, 541000, tzinfo=UTC())),
            ('PT14H00M00S', datetime.timedelta(hours=14)),
            ('PT26H00M00S', datetime.timedelta(hours=26)),
            ('PT14H', datetime.timedelta(hours=14)),
            ('PT1M00S', datetime.timedelta(minutes=1)),
            ('PT2M', datetime.timedelta(minutes=2)),
            ('PT1M0.00S', datetime.timedelta(minutes=1)),
            ('PT45S', datetime.timedelta(seconds=45)),
            ('PT4.5S', datetime.timedelta(seconds=4.5)),
            ('PT01:45:19', datetime.timedelta(hours=1, minutes=45, seconds=19)),
            ('P0Y0M0DT0H0M20S', datetime.timedelta(seconds=20)),
            ('P0Y0M0DT0H18M28.976S', datetime.timedelta(minutes=18, seconds=28.976)),
            ('2022-10-18T14:22:24',
             datetime.datetime(2022, 10, 18, 14, 22, 24, tzinfo=None)),
        ]
        for test in tests:
            tc = from_isodatetime(test[0])
            self.failUnlessEqual(tc, test[1])
        date_str = "2013-07-25T09:57:31Z"
        date_val = from_isodatetime(date_str)
        # Don't check for the 'Z' because Python doesn't put the timezone in
        # the isoformat string
        isoformat = date_val.isoformat().replace('+00:00', 'Z')
        self.assertEqual(isoformat, date_str)
        date_str = "2013-07-25T09:57:31.123Z"
        date_val = from_isodatetime(date_str)
        self.assertEqual(date_val.microsecond, 123000)
        self.assertTrue(date_val.isoformat().startswith(date_str[:-1]))

    def test_to_isoduration(self):
        tests = [
            ('PT14H0M0S', datetime.timedelta(hours=14)),
            ('PT26H0M0S', datetime.timedelta(hours=26)),
            ('PT14H0M0S', datetime.timedelta(hours=14)),
            ('PT1M0S', datetime.timedelta(minutes=1)),
            ('PT2M0S', datetime.timedelta(minutes=2)),
            ('PT1M0S', datetime.timedelta(minutes=1)),
            ('PT45S', datetime.timedelta(seconds=45)),
            ('PT4.5S', datetime.timedelta(seconds=4.5)),
            ('PT4.56S', datetime.timedelta(seconds=4, microseconds=560000)),
            ('PT4.067S', datetime.timedelta(seconds=4.067)),
            ('PT4.008S', datetime.timedelta(seconds=4, microseconds=7800)),
            ('PT4.007S', datetime.timedelta(seconds=4, microseconds=7300)),
            ('PT4.001S', datetime.timedelta(seconds=4, microseconds=1000)),
            ('PT2.001S', datetime.timedelta(seconds=2, microseconds=500)),
            ('PT3S', datetime.timedelta(seconds=3, microseconds=499)),
            ('PT1H45M19S', datetime.timedelta(hours=1, minutes=45, seconds=19)),
        ]
        for expected, src in tests:
            self.assertEqual(expected, toIsoDuration(src))


class BufferedReaderTests(unittest.TestCase):
    def test_buffer_reader(self):
        r = bytearray('t' * 65536)
        for i in range(len(r)):
            r[i] = i & 0xFF
        br = BufferedReader(StringIO.StringIO(r), buffersize=1024)
        p = br.peek(8)
        self.assertTrue(len(p) >= 8)
        for i in range(8):
            self.assertEqual(ord(p[i]), i)
        self.assertEqual(br.tell(), 0)
        p = br.read(8)
        self.assertEqual(br.tell(), 8)
        self.assertEqual(len(p), 8)
        for i in range(8):
            self.assertEqual(ord(p[i]), i)
        p = br.read(8)
        self.assertEqual(br.tell(), 16)
        self.assertEqual(len(p), 8)
        for i in range(8):
            self.assertEqual(ord(p[i]), i + 8)

class HasTwoJson(object):
    def __init__(self, result, pure):
        self.pure = pure
        self.result = result

    def toJSON(self, pure):
        if pure != self.pure:
            raise AssertionError(
                "Wrong pure argument. Got {0} expected {1}".format(pure, self.pure))
        return self.result

class ObjectTests(unittest.TestCase):
    def test_flatten(self):
        list_input = [
            'string', datetime.datetime(2019, 2, 1, 4, 5, 6, tzinfo=UTC()),
            HasTwoJson("has_json", True),
            datetime.timedelta(minutes=1, seconds=30),
        ]
        list_expected = [
            "string", "2019-02-01T04:05:06Z", "has_json", "PT1M30S",
        ]
        dict_input = {
            'hello': 'world',
            'datetime': datetime.datetime(2019, 2, 1, 4, 5, 6, tzinfo=UTC()),
            'timedelta': datetime.timedelta(minutes=2, seconds=30),
        }
        dict_expected = {
            'hello': 'world',
            'datetime': "2019-02-01T04:05:06Z",
            'timedelta': "PT2M30S",
        }

        test_cases = [
            (None, False, None),
            (None, True, None),
            ('string', False, 'string'),
            ("'string'", True, "\'string\'"),
            (HasTwoJson("json", False), False, "json"),
            (HasTwoJson("json", True), True, "json"),
            (datetime.datetime(2019, 2, 1, 4, 5, 6, tzinfo=UTC()),
             False, "2019-02-01T04:05:06Z"),
            (datetime.timedelta(minutes=1, seconds=30),
             False, "PT1M30S"),
            (list_input, True, list_expected),
            (dict_input, True, dict_expected),
            (tuple(list_input), True, tuple(list_expected)),
        ]
        for value, pure, expected in test_cases:
            actual = objects.flatten(value, pure=pure)
            self.assertEqual(expected, actual)

    def test_pick_item(self):
        src = {
            1: 'one',
            2: 'two',
            'three': 'three',
            4: 'four',
            'five': 5,
        }
        expected = {
            1: 'one',
            2: 'two',
            'five': 5,
        }
        self.assertEqual(expected, objects.pick_items(src, [1, 2, 'five', 7]))


if __name__ == "__main__":
    unittest.main()
