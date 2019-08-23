import unittest

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

if __name__ == "__main__":
    unittest.main()
