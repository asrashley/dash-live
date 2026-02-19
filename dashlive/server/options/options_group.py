import dataclasses
from typing import AbstractSet

from dashlive.utils.json_object import JsonObject

class OptionsGroup:
    @classmethod
    def classname(cls) -> str:
        if cls.__module__.startswith('__'):
            return cls.__name__
        return cls.__module__ + '.' + cls.__name__

    def toJSON(self, exclude: AbstractSet[str] | None = None) -> JsonObject:
        rv: JsonObject = dataclasses.asdict(self)
        if exclude is None:
            exclude = set()
        for k in list(rv.keys()):
            if k in exclude or k[0] == '_':
                del rv[k]
        return rv
