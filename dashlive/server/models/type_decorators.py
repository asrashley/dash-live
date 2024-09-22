from enum import IntEnum
from typing import Type

from sqlalchemy import Integer, TypeDecorator

# based upon https://gist.github.com/hasansezertasan/691a7ef67cc79ea669ff76d168503235
class IntEnumType(TypeDecorator):
    """
    Enables passing in a Python enum and storing the enum's *value* in the db.
    The default would have stored the enum's *name* (ie the string).
    """

    impl = Integer

    def __init__(self, enumtype: Type[IntEnum], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._enumtype = enumtype

    def process_bind_param(self, value: int | IntEnum, dialect) -> int:
        if isinstance(value, int):
            return value
        return value.value

    def process_result_value(self, value: int, dialect) -> IntEnum:
        return self._enumtype(value)
