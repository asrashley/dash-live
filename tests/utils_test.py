
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

import os
import sys
import unittest

_src = os.path.join(os.path.dirname(__file__),"..", "src")
if not _src in sys.path:
    sys.path.append(_src)

import utils

class DateTimeTests(unittest.TestCase):
    def test_isoformat(self):
        date_str = "2013-07-25T09:57:31Z"
        date_val = utils.from_isodatetime(date_str)
        self.assertEqual(date_val.year,2013)
        self.assertEqual(date_val.month, 7)
        self.assertEqual(date_val.day, 25)
        self.assertEqual(date_val.hour, 9)
        self.assertEqual(date_val.minute, 57)
        self.assertEqual(date_val.second, 31)
        # Don't check for the 'Z' because Python doesn't put the timezone in the isoformat string
        isoformat = date_val.isoformat().replace('+00:00','Z')
        self.assertEqual(isoformat,date_str)
        date_str = "2013-07-25T09:57:31.123Z"
        date_val = utils.from_isodatetime(date_str)
        self.assertEqual(date_val.microsecond, 123000)
        # Don't check for the 'Z' because Python doesn't put the timezone in the isoformat string
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
