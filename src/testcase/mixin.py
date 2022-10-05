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

import datetime
import logging
import os
import sys
try:
    from unittest import mock
except ImportError:
    # use Python 2 back-port
    import mock

class TestCaseMixin(object):
    real_datetime_class = datetime.datetime

    @property
    def classname(self):
        clz = type(self)
        if clz.__module__.startswith('__'):
            return clz.__name__
        return clz.__module__ + '.' + clz.__name__

    def _assert_true(self, result, a, b, msg, template):
        if not result:
            if msg is not None:
                raise AssertionError(msg)
            raise AssertionError(template.format(a, b))

    def assertTrue(self, result, msg=None):
        self._assert_true(result, result, None, msg, r'{} not True')

    def assertFalse(self, result, msg=None):
        self._assert_true(not result, result, None, msg, r'{} not False')

    def assertEqual(self, a, b, msg=None):
        self._assert_true(a == b, a, b, msg, r'{} != {}')

    def assertNotEqual(self, a, b, msg=None):
        self._assert_true(a != b, a, b, msg, r'{} == {}')

    def assertAlmostEqual(self, a, b, places=7, msg=None, delta=None):
        if delta is not None:
            d = abs(a - b)
            self._assert_true(
                d <= delta,
                a,
                b,
                msg,
                '{} !~= {} (delta %f)' %
                (delta))
        else:
            ar = round(a, places)
            br = round(b, places)
            self._assert_true(ar == br, a, b, msg, '{} !~= {}')

    def assertGreaterOrEqual(self, a, b, msg=None):
        self._assert_true(a >= b, a, b, msg, r'{} < {}')

    def assertObjectEqual(self, expected, actual, msg=None, strict=False):
        for key, value in expected.iteritems():
            if msg is None:
                key_name = key
            else:
                key_name = '{0}.{1}'.format(msg, key)
            if expected is None:
                self.assertIsNone(
                    actual, '{0}: {1} should be None'.format(key_name, actual))
            else:
                self.assertIsNotNone(
                    actual, '{0}: {1} should not be None'.format(key_name, actual))
            if isinstance(value, dict):
                self.assertObjectEqual(value, actual[key], key_name, strict=strict)
            elif isinstance(value, list):
                self.assertListEqual(value, actual[key], key_name)
            else:
                self.assertIn(key, actual,
                              '{0}: missing key {1}'.format(key_name, key))
                assert_msg = r'{0}: expected "{1}" got "{2}"'.format(
                    key_name, value, actual[key])
                self.assertEqual(value, actual[key], msg=assert_msg)
        if strict:
            for key in actual.keys():
                self.assertIn(key, expected)

    def assertListEqual(self, expected, actual, msg=None):
        if msg is None:
            msg = ''
        assert_msg = '{0}: expected length {1} got {2}'.format(
            msg, len(expected), len(actual))
        self.assertEqual(len(expected), len(actual), assert_msg)
        idx = 0
        for exp, act in zip(expected, actual):
            if isinstance(exp, list):
                self.assertListEqual(exp, act, '{0:s}[{1:d}]'.format(msg, idx))
            elif isinstance(exp, dict):
                self.assertObjectEqual(exp, act, '{0:s}[{1:d}]'.format(msg, idx))
            else:
                assert_msg = '{0:s}[{1:d}] expected "{2}" got "{3}"'.format(
                    msg, idx, exp, act)
                self.assertEqual(exp, act, assert_msg)
            idx += 1

    def assertGreaterThan(self, a, b, msg=None):
        self._assert_true(a > b, a, b, msg, r'{} <= {}')

    def assertGreaterThanOrEqual(self, a, b, msg=None):
        self._assert_true(a >= b, a, b, msg, r'{} < {}')

    def assertLessThan(self, a, b, msg=None):
        self._assert_true(a < b, a, b, msg, r'{} >= {}')

    def assertLessThanOrEqual(self, a, b, msg=None):
        self._assert_true(a <= b, a, b, msg, r'{} > {}')

    def assertIn(self, a, b, msg=None):
        self._assert_true(a in b, a, b, msg, r'{} not in {}')

    def assertNotIn(self, a, b, msg=None):
        self._assert_true(a not in b, a, b, msg, r'{} in {}')

    def assertIsNone(self, a, msg=None):
        self._assert_true(a is None, a, None, msg, r'{} is not None')

    def assertIsNotNone(self, a, msg=None):
        self._assert_true(a is not None, a, None, msg, r'{} is None')

    def assertStartsWith(self, a, b, msg=None):
        self._assert_true(a.startswith(b), a, b, msg,
                          r'{} does not start with {}')

    def assertEndsWith(self, a, b, msg=None):
        self._assert_true(a.endswith(b), a, b, msg, r'{} does not end with {}')

    def assertIsInstance(self, a, types, msg=None):
        self._assert_true(isinstance(a, types), a, types,
                          msg, r'{} is not instance of {}')

    def _check_true(self, result, a, b, msg, template):
        if not result:
            if msg is None:
                msg = template.format(a, b)
            log = getattr(self, "log", None)
            if log is None:
                log = logging.getLogger(self.classname)
            log.warning('%s', msg)

    def checkTrue(self, result, msg=None):
        self._check_true(result, result, None, msg, r'{} not True')

    def checkFalse(self, result, msg=None):
        self._check_true(not result, result, None, msg, r'{} not False')

    def checkEqual(self, a, b, msg=None):
        self._check_true(a == b, a, b, msg, r'{} != {}')

    def checkNotEqual(self, a, b, msg=None):
        self._check_true(a != b, a, b, msg, r'{} == {}')

    def checkAlmostEqual(self, a, b, places=7, msg=None, delta=None):
        if delta is not None:
            d = abs(a - b)
            self._check_true(
                d <= delta,
                a,
                b,
                msg,
                '{} !~= {} (delta %f)' %
                (delta))
        else:
            ar = round(a, places)
            br = round(b, places)
            self._check_true(ar == br, a, b, msg, '{} !~= {}')

    def checkGreaterThan(self, a, b, msg=None):
        self._check_true(a > b, a, b, msg, r'{} <= {}')

    def checkGreaterThanOrEqual(self, a, b, msg=None):
        self._check_true(a >= b, a, b, msg, r'{} < {}')

    def checkLessThan(self, a, b, msg=None):
        self._check_true(a < b, a, b, msg, r'{} >= {}')

    def checkLessThanOrEqual(self, a, b, msg=None):
        self._check_true(a <= b, a, b, msg, r'{} > {}')

    def checkIn(self, a, b, msg=None):
        self._check_true(a in b, a, b, msg, r'{} not in {}')

    def checkNotIn(self, a, b, msg=None):
        self._check_true(a not in b, a, b, msg, r'{} in {}')

    def checkIsNone(self, a, msg=None):
        self._check_true(a is None, a, None, msg, r'{} is not None')

    def checkIsNotNone(self, a, msg=None):
        self._check_true(a is not None, a, None, msg, r'{} is None')

    def checkEndsWith(self, a, b, msg=None):
        self._check_true(a.endswith(b), a, b, msg, r'{} does not end with {}')

    def checkIsInstance(self, a, types, msg=None):
        self._check_true(isinstance(a, types), a, types,
                         msg, r'{} is not instance of {}')

    @staticmethod
    def _print_line(start, hex_line, ascii_line):
        if len(hex_line) < 8:
            hex_line += ['   '] * (8 - len(hex_line))
        print('{0:04d}: {1}   {2}'.format(
            start,
            ' '.join(hex_line),
            ' '.join(ascii_line)))

    def hexdumpBuffer(self, label, data, max_length=256):
        print('==={0}==='.format(label))
        hex_line = []
        ascii_line = []
        for idx, d in enumerate(data):
            asc = d if d >= ' ' and d <= 'z' else ' '
            hex_line.append('{0:02x} '.format(ord(d)))
            ascii_line.append('{0} '.format(asc))
            if len(hex_line) == 8:
                self._print_line(idx - 7, hex_line, ascii_line)
                hex_line = []
                ascii_line = []
            if idx == max_length:
                break
        if hex_line:
            self._print_line(idx - 7, hex_line, ascii_line)
        if idx < len(data):
            print('.......')
        print('==={0}==='.format('=' * len(label)))

    def assertBuffersEqual(self, a, b, name=None, max_length=256, dump=True):
        lmsg = r'Expected length {expected:d} does not match {actual:d}'
        dmsg = r'Expected 0x{expected:02x} got 0x{actual:02x} at byte position {position:d} (bit {bitpos:d})'
        if name is not None:
            lmsg = ': '.join([name, lmsg])
            dmsg = ': '.join([name, dmsg])
        if len(a) != len(b):
            self.hexdumpBuffer('expected', a)
            self.hexdumpBuffer('actual', b)
        self.assertEqual(
            len(a), len(b), lmsg.format(
                expected=len(a), actual=len(b)))
        if a == b:
            return
        if dump:
            self.hexdumpBuffer('expected', a, max_length=max_length)
            self.hexdumpBuffer('actual', b, max_length=max_length)
        for idx in range(len(a)):
            exp = ord(a[idx])
            act = ord(b[idx])
            bitpos = idx * 8
            mask = 0x80
            for bit in range(8):
                if (exp & mask) != (act & mask):
                    break
                mask = mask >> 1
                bitpos += 1
            self.assertEqual(
                exp, act,
                dmsg.format(
                    expected=ord(a[idx]),
                    actual=ord(b[idx]),
                    position=idx,
                    bitpos=bitpos))

    def assertBuffersNotEqual(self, a, b, name=None, max_length=256):
        with self.assertRaises(AssertionError):
            self.assertBuffersEqual(a, b, name=name, dump=False)

    def progress(self, pos, total):
        if pos == 0:
            sys.stdout.write('\n')
        sys.stdout.write(
            '\r {:05.1f}%'.format(
                100.0 *
                float(pos) /
                float(total)))
        if pos == total:
            sys.stdout.write('\n')
        sys.stdout.flush()

    @classmethod
    def mock_datetime_now(cls, target):
        """
        Override ``datetime.datetime.now()`` with a custom target value.
        This creates a new datetime.datetime class, and alters its now()/utcnow()
        methods.
        Returns:
        A mock.patch context, can be used as a decorator or in a with.
        """
        # See http://bugs.python.org/msg68532
        # And
        # http://docs.python.org/reference/datamodel.html#customizing-instance-and-subclass-checks
        class DatetimeSubclassMeta(type):
            """
            We need to customize the __instancecheck__ method for isinstance().
            This must be performed at a metaclass level.
            """
            @classmethod
            def __instancecheck__(mcs, obj):
                return isinstance(obj, cls.real_datetime_class)

        class BaseMockedDatetime(cls.real_datetime_class):
            @classmethod
            def now(cls, tz=None):
                return target.replace(tzinfo=tz)

            @classmethod
            def utcnow(cls):
                return target

        # Python2 & Python3-compatible metaclass
        MockedDatetime = DatetimeSubclassMeta(
            'datetime', (BaseMockedDatetime,), {})
        return mock.patch.object(datetime, 'datetime', MockedDatetime)


class HideMixinsFilter(logging.Filter):
    """A logging.Filter that hides mixins.py in log messages.
    Using the HideMixinsFilter in a logging adapter will cause the filename and line numbers
    in log messages to be set to the caller of mixins functions, rather than just seeing
    the line number in mixings.py that calls logger.error
    """

    def filter(self, record):
        if record.filename.endswith('mixins.py'):
            # Replace the log record with the function & line number that called
            # mixins.py
            record.filename, record.lineno, record.funcName = self.find_caller()
        return True

    def find_caller(self):
        n_frames_upper = 2
        f = logging.currentframe()
        for _ in range(2 + n_frames_upper):
            if f is not None:
                f = f.f_back
        rv = "(unknown file)", 0, "(unknown function)"
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            basename = os.path.basename(co.co_filename)
            if filename == logging._srcfile or basename == 'mixins.py':
                f = f.f_back
                continue
            rv = (basename, f.f_lineno, co.co_name)
            break
        return rv