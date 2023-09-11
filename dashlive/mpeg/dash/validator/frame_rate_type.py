#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import re

from dashlive.testcase.mixin import TestCaseMixin

class FrameRateType(TestCaseMixin):
    pattern = re.compile(r"([0-9]*[0-9])(/[0-9]*[0-9])?$")

    def __init__(self, num, denom=1):
        if isinstance(num, str):
            match = self.pattern.match(num)
            self.assertIsNotNone(match, 'Invalid frame rate "{}", pattern is "{}"'.format(
                num, self.pattern.pattern))
            num = int(match.group(1), 10)
            if match.group(2):
                denom = int(match.group(2)[1:])
        self.num = num
        self.denom = denom
        if denom == 1:
            self.value = num
        else:
            self.value = float(num) / float(denom)

    def __float__(self):
        return self.value

    def __repr__(self):
        if self.denom == 1:
            return str(self.value)
        return f'{self.num:d}/{self.denom:d}'

    def validate(self, depth: int = -1) -> None:
        pass
