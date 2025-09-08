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

import binascii
import logging
import os
import sys
from typing import Any

from dashlive.utils.hexdump import hexdump_buffer

class TestCaseMixin:
    @classmethod
    def classname(cls) -> str:
        if cls.__module__.startswith('__'):
            return cls.__name__
        return cls.__module__ + '.' + cls.__name__

    def update_recursively(self, lower: dict, upper: dict) -> dict[str, Any]:
        rv: dict[str, Any] = {**lower}
        rv.update(upper)
        for key, value in upper.items():
            if key not in lower:
                continue
            if isinstance(value, list):
                items: list[Any] = []
                for exp, act in zip(value, lower[key]):
                    if isinstance(exp, dict):
                        merged: dict = {**act}
                        merged.update(exp)
                        items.append(merged)
                    else:
                        items.append(exp)
                rv[key] = items
            elif isinstance(value, dict):
                rv[key] = {**lower[key]}
                rv[key].update(value)
        return rv

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

    def assertObjectEqual(self, expected, actual, msg=None, strict=False, list_key=None) -> None:
        if expected is None:
            self.assertEqual(expected, actual)
            return
        if isinstance(expected, (str, int)):
            self.assertEqual(expected, actual)
            return
        if strict:
            self.asssertDictEqual(expected, actual)
            return
        for key, value in expected.items():
            if msg is None:
                key_name: str = key
            else:
                key_name = f'{msg}.{key}'
            self.assertIn(key, actual, f'{key_name}: key "{key}" missing')
            act: Any = actual[key]
            if value is None:
                self.assertIsNone(act, f'{key_name}: {act} should be None')
            else:
                self.assertIsNotNone(act, f'{key_name}: {act} should not be None')
            if isinstance(value, dict):
                self.assertObjectEqual(value, actual[key], msg=key_name, strict=strict)
            elif isinstance(value, list):
                if strict:
                    self.assertListEqual(value, actual[key], msg=key_name)
                else:
                    for e, a in zip(value, act):
                        self.assertObjectEqual(e, a)
            else:
                assert_msg = r'{}: expected "{}" got "{}"'.format(
                    key_name, value, actual[key])
                self.assertEqual(value, actual[key], msg=assert_msg)

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

    def _check_true(self, result: bool, a: Any, b: Any,
                    msg: str | None, template: str) -> bool:
        if not result:
            if msg is None:
                msg = template.format(a, b)
            log = getattr(self, "log", None)
            if log is None:
                log = logging.getLogger(self.classname())
            log.warning('%s', msg)
        return result

    def checkTrue(self, result: bool, msg: str | None = None) -> bool:
        return self._check_true(result, result, None, msg, r'{} not True')

    def checkFalse(self, result: bool, msg: str | None = None) -> bool:
        return self._check_true(not result, result, None, msg, r'{} not False')

    def checkEqual(self, a: Any, b: Any, msg: str | None = None) -> bool:
        return self._check_true(a == b, a, b, msg, r'{} != {}')

    def checkNotEqual(self, a, b, msg=None) -> bool:
        return self._check_true(a != b, a, b, msg, r'{} == {}')

    def checkAlmostEqual(self, a, b, places=7, msg=None, delta=None) -> bool:
        if delta is not None:
            d = abs(a - b)
            return self._check_true(
                d <= delta,
                a,
                b,
                msg,
                '{} !~= {} (delta %f)' %
                (delta))
        ar = round(a, places)
        br = round(b, places)
        return self._check_true(ar == br, a, b, msg, '{} !~= {}')

    def checkGreaterThan(self, a, b, msg=None) -> bool:
        return self._check_true(a > b, a, b, msg, r'{} <= {}')

    def checkGreaterThanOrEqual(self, a, b, msg=None) -> bool:
        return self._check_true(a >= b, a, b, msg, r'{} < {}')

    def checkLessThan(self, a, b, msg=None) -> bool:
        return self._check_true(a < b, a, b, msg, r'{} >= {}')

    def checkLessThanOrEqual(self, a, b, msg=None) -> bool:
        return self._check_true(a <= b, a, b, msg, r'{} > {}')

    def checkIn(self, a, b, msg=None) -> bool:
        return self._check_true(a in b, a, b, msg, r'{} not in {}')

    def checkNotIn(self, a, b, msg=None) -> bool:
        return self._check_true(a not in b, a, b, msg, r'{} in {}')

    def checkIsNone(self, a, msg=None) -> bool:
        return self._check_true(a is None, a, None, msg, r'{} is not None')

    def checkIsNotNone(self, a, msg=None) -> bool:
        return self._check_true(a is not None, a, None, msg, r'{} is None')

    def checkEndsWith(self, a, b, msg=None) -> bool:
        return self._check_true(a.endswith(b), a, b, msg, r'{} does not end with {}')

    def checkIsInstance(self, a, types, msg=None) -> bool:
        return self._check_true(
            isinstance(a, types), a, types, msg, r'{} is not instance of {}')

    def checkStartsWith(self, a, b, msg=None) -> bool:
        return self._check_true(a.startswith(b), a, b, msg,
                                r'{} does not start with {}')

    def checkGreaterOrEqual(self, a, b, msg=None) -> bool:
        return self._check_true(a >= b, a, b, msg, r'{} < {}')

    def assertBuffersEqual(self, a, b, name=None, max_length=256, dump=True, width=16):
        lmsg = r'Expected length {expected:d} does not match {actual:d}'
        dmsg = r'Expected 0x{expected:02x} got 0x{actual:02x} at byte position {position:d} (bit {bitpos:d})'
        if name is not None:
            lmsg = ': '.join([name, lmsg])
            dmsg = ': '.join([name, dmsg])
        if len(a) != len(b):
            hexdump_buffer(f'expected {name}', a, width=width)
            hexdump_buffer(f'actual {name}', b, width=width)
        self.assertEqual(
            len(a), len(b), lmsg.format(
                expected=len(a), actual=len(b)))
        if a == b:
            return
        for idx in range(len(a)):
            exp = a[idx]
            act = b[idx]
            bitpos = idx * 8
            mask = 0x80
            for bit in range(8):
                if (exp & mask) != (act & mask):
                    break
                mask = mask >> 1
                bitpos += 1
            if dump and exp != act:
                start = max(0, idx - max_length // 2)
                hexdump_buffer(
                    f'expected {name}', a, max_length=max_length, offset=start, width=width)
                hexdump_buffer(
                    f'actual {name}', b, max_length=max_length, offset=start, width=width)
            self.assertEqual(
                exp, act,
                dmsg.format(
                    expected=a[idx],
                    actual=b[idx],
                    position=idx,
                    bitpos=bitpos))

    def assertBuffersNotEqual(self, a, b, name=None, max_length=256):
        with self.assertRaises(AssertionError):
            self.assertBuffersEqual(a, b, name=name, dump=False)

    def progress(self, pos: int, total: int) -> None:
        if os.environ.get('CI') is not None:
            return
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

    @staticmethod
    def to_hex(data: bytes) -> str:
        return str(binascii.b2a_hex(data), 'ascii')

    @staticmethod
    def to_base64(data: bytes) -> str:
        return str(binascii.b2a_base64(data, newline=False), 'ascii')

    @staticmethod
    def list_key_fn(item: Any, index: int) -> str:
        if isinstance(item, dict):
            if '_type' in item:
                item_type = item["_type"].split('.')[-1]
                return f'{index}={item_type}'
            print(item.keys())
            return f'{index}={item["atom_type"]}'
        return f'{index}'

class HideMixinsFilter(logging.Filter):
    """A logging.Filter that hides mixin.py in log messages.
    Using the HideMixinsFilter in a logging adapter will cause the filename and line numbers
    in log messages to be set to the caller of mixins functions, rather than just seeing
    the line number in mixings.py that calls logger.error
    """

    def filter(self, record):
        if record.filename.endswith('mixin.py'):
            # Replace the log record with the function & line number that called
            # mixin.py
            record.filename, record.lineno, record.funcName = self.find_caller()
        return True

    def find_caller(self):
        n_frames_upper = 3
        f = logging.currentframe()
        for _ in range(2 + n_frames_upper):
            if f is not None:
                f = f.f_back
        rv = "(unknown file)", 0, "(unknown function)"
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            basename = os.path.basename(co.co_filename)
            if filename == logging._srcfile or basename == 'mixin.py':
                f = f.f_back
                continue
            rv = (basename, f.f_lineno, co.co_name)
            break
        return rv
