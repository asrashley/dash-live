#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
import traceback
from typing import AbstractSet, Any, NamedTuple

from dashlive.utils.json_object import JsonObject

class ErrorSource(IntEnum):
    ATTRIBUTE = 1
    ELEMENT = 2
    OTHER = 3


class LineRange(NamedTuple):
    start: int
    end: int

    def __str__(self) -> str:
        return f'{self.start}->{self.end}'

class StackFrame:
    __slots__ = ('filename', 'lineno', 'qualname')

    def __init__(self, item: tuple) -> None:
        frame = item[0]
        self.lineno = frame.f_lineno
        self.filename = Path(frame.f_code.co_filename).name
        self.qualname = frame.f_code.co_qualname

    def __repr__(self):
        return f'StackFrame({self.qualname}, {self.lineno}, {self.filename})'

    def to_dict(self) -> dict:
        return {
            'filename': self.filename,
            'line': self.lineno,
            'module': self.qualname,
        }

@dataclass(slots=True, kw_only=True)
class ValidationError:
    """
    Container for one validation error
    """
    assertion: StackFrame
    source: ErrorSource
    location: LineRange
    msg: str
    clause: str | None = None

    def to_dict(self) -> JsonObject:
        return {
            'assertion': self.assertion.to_dict(),
            'clause': self.clause,
            'location': list(self.location),
            'msg': self.msg,
            'source': self.source.name,
        }

    def __str__(self) -> str:
        if self.clause:
            msg = f'{self.clause}: {self.msg}'
        else:
            msg = self.msg
        return f'{self.location}: {msg} [{self.assertion.filename}:{self.assertion.lineno}]'


class ValidationChecks:
    __slots__ = ('errors', 'source', 'location', 'prefix')

    def __init__(self, source: ErrorSource, location: LineRange) -> None:
        self.errors: list[ValidationError] = []
        self.source = source
        self.location = location
        self.prefix = ''

    def has_errors(self) -> bool:
        return bool(self.errors)

    def find_caller(self, limit: int = 5) -> StackFrame:
        for item in traceback.walk_stack(None):
            sf = StackFrame(item)
            if sf.filename != 'errors.py':
                break
            limit -= 1
            if limit == 0:
                break
        return sf

    def add_error(self, msg: str, clause: str | None = None) -> None:
        frame = self.find_caller()
        self.errors.append(
            ValidationError(source=self.source, location=self.location, assertion=frame,
                            msg=f'{self.prefix}{msg}', clause=clause))

    def check_true(self, result: bool,
                   a: Any = None,
                   b: Any = None,
                   msg: str | None = None,
                   template: str | None = None,
                   clause: str | None = None) -> bool:
        if not result:
            if msg is None:
                msg = template.format(a, b)
            self.add_error(msg, clause)
        return result

    def check_none(self, item: Any, **kwargs) -> bool:
        result = item is None
        return self.check_true(result, item, item, **kwargs)

    def check_not_none(self, item: Any, template: str | None = None, **kwargs) -> bool:
        result = item is not None
        if template is None:
            template = 'Expected item not to be None'
        return self.check_true(result, item, item, template=template, **kwargs)

    def check_equal(self, a: Any, b: Any, template: str | None = None, **kwargs) -> bool:
        result = a == b
        if template is None:
            template = r'{0} != {1}'
        return self.check_true(result, a, b, template=template, **kwargs)

    def check_not_equal(self, a: Any, b: Any, **kwargs) -> bool:
        result = a != b
        return self.check_true(result, a, b, **kwargs)

    def check_includes(self, container: AbstractSet, item: Any,
                       template: str | None = None, **kwargs) -> bool:
        result = item in container
        if template is None:
            template = r'Expected {1} to be in {0}'
        return self.check_true(
            result, container, item, template=template, **kwargs)

    def check_not_in(self, item: Any, container: AbstractSet, **kwargs) -> bool:
        result = item not in container
        return self.check_true(result, container, item, **kwargs)

    def check_less_than(self, a: Any, b: Any,
                        msg: str | None = None,
                        template: str | None = None) -> bool:
        result = a < b
        return self.check_true(
            result, a, b, msg=msg, template=template)

    def check_less_than_or_equal(self, a: Any, b: Any, **kwargs) -> bool:
        result = a <= b
        return self.check_true(result, a, b, **kwargs)

    def check_greater_than(self, a: Any, b: Any,
                           template: str | None = None, **kwargs) -> bool:
        result = a > b
        if template is None:
            template = f'{0} should be greater than  {1}'
        return self.check_true(result, a, b, template=template, **kwargs)

    def check_greater_or_equal(self, a: Any, b: Any,
                               template: str | None = None, **kwargs) -> bool:
        result = a >= b
        if template is None:
            template = f'{0} should be >=  {1}'
        return self.check_true(result, a, b, **kwargs)

    def check_starts_with(self, text: str, prefix: str, template: str | None = None,
                          **kwargs) -> bool:
        result = text.startswith(prefix)
        if template is None:
            template = r'{0} should start with {1}'
        return self.check_true(result, text, prefix, template=template, **kwargs)

    def check_almost_equal(self, a, b, places=7, delta=None,
                           template: str | None = None, **kwargs) -> bool:
        if template is None:
            template = r'{} !~= {}'
        if delta is not None:
            d = abs(a - b)
            return self.check_true(d <= delta, a, b, template=template, **kwargs)
        ar = round(a, places)
        br = round(b, places)
        return self.check_true(ar == br, a, b, template=template, **kwargs)

    def check_is_instance(self, item: Any, types: type | tuple, **kwargs) -> bool:
        result = isinstance(item, types)
        return self.check_true(result, item, types, **kwargs)
