
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

import datetime
import os
import sys
import unittest

_src = os.path.join(os.path.dirname(__file__),"..", "src")
if not _src in sys.path:
    sys.path.append(_src)

import utils

class DateTimeTests(unittest.TestCase):
    def test_isoformat(self):
        tests = [
            ('2009-02-27T10:00:00Z', datetime.datetime(2009,2,27,10,0,0, tzinfo=utils.UTC()) ),
            ('2013-07-25T09:57:31Z', datetime.datetime(2013,7,25,9,57,31, tzinfo=utils.UTC()) ),
            ('PT14H00M00S', datetime.timedelta(hours=14) ),
            ('PT26H00M00S', datetime.timedelta(hours=26) ),
            ('PT14H', datetime.timedelta(hours=14) ),
            ('PT1M00S', datetime.timedelta(minutes=1) ),
            ('PT2M', datetime.timedelta(minutes=2) ),
            ('PT1M0.00S', datetime.timedelta(minutes=1) ),
            ('PT45S', datetime.timedelta(seconds=45) ),
            ('PT4.5S', datetime.timedelta(seconds=4.5) ),
            ('PT01:45:19', datetime.timedelta(hours=1,minutes=45,seconds=19) ),
        ]
        for test in tests:
            tc = utils.from_isodatetime(test[0])
            self.failUnlessEqual(tc,test[1])
        date_str = "2013-07-25T09:57:31Z"
        date_val = utils.from_isodatetime(date_str)
        # Don't check for the 'Z' because Python doesn't put the timezone in the isoformat string
        isoformat = date_val.isoformat().replace('+00:00','Z')
        self.assertEqual(isoformat,date_str)
        date_str = "2013-07-25T09:57:31.123Z"
        date_val = utils.from_isodatetime(date_str)
        self.assertEqual(date_val.microsecond, 123000)
        self.assertTrue(date_val.isoformat().startswith(date_str[:-1]))

class BufferedReaderTests(unittest.TestCase):
    def test_buffer_reader(self):
        r = bytearray('t'*65536)
        #mem = memoryview(r)
        for i in range(len(r)):
            r[i] = i & 0xFF
        br = utils.BufferedReader(StringIO.StringIO(r), buffersize=1024)
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
            self.assertEqual(ord(p[i]), i+8)

        
if __name__ == "__main__":
    unittest.main()
