import logging
import os


class TestCaseMixin(object):
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
