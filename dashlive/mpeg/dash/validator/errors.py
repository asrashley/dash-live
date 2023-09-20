#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from dataclasses import dataclass
from enum import IntEnum
from typing import AbstractSet, Any, NamedTuple

from dashlive.utils.json_object import JsonObject

class ErrorSource(IntEnum):
    ATTRIBUTE = 1
    ELEMENT = 2
    OTHER = 3


class LineRange(NamedTuple):
    start: int
    end: int


@dataclass(slots=True, kw_only=True)
class ValidationError:
    """
    Container for one validation error
    """
    source: ErrorSource
    location: LineRange
    msg: str
    clause: str | None = None

    def to_dict(self) -> JsonObject:
        if self.clause:
            msg = f'{self.clause}: {self.msg}'
        else:
            msg = self.msg
        return {
            'location': list(self.location),
            'text': msg,
        }


class ValidationChecks:
    __slots__ = ('errors', 'source', 'location')

    def __init__(self, source: ErrorSource, location: LineRange) -> None:
        self.errors: list[ValidationError] = []
        self.source = source
        self.location = location

    def has_errors(self) -> bool:
        return bool(self.errors)

    def add_error(self, msg: str, clause: str | None = None) -> None:
        self.errors.append(
            ValidationError(source=self.source, location=self.location, msg=msg,
                            clause=clause))

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

    def check_greater_than(self, a: Any, b: Any, **kwargs) -> bool:
        result = a > b
        return self.check_true(result, a, b, **kwargs)

    def check_greater_or_equal(self, a: Any, b: Any, **kwargs) -> bool:
        result = a >= b
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
