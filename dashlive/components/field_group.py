#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from dataclasses import dataclass
from typing import AbstractSet

from dashlive.utils.json_object import JsonObject

@dataclass(slots=True)
class InputFieldGroup:
    name: str
    title: str
    fields: list[JsonObject]
    show: bool = False
    className: str = ''

    def toJSON(self, pure: bool = False, exclude: AbstractSet | None = None) -> JsonObject:
        js = {
            'name': self.name,
            'title': self.title,
            'show': self.show,
            'className': self.className,
            'fields': self.fields,
        }
        if exclude is not None:
            for field in exclude:
                del js[field]
        return js
