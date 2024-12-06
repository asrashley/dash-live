#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from dataclasses import dataclass
from typing import AbstractSet, TypedDict

from dashlive.server.options.form_input_field import FormInputContext

class InputFieldGroupJson(TypedDict):
    name: str
    title: str
    fields: list[FormInputContext]
    show: bool
    className: str

@dataclass(slots=True)
class InputFieldGroup:
    name: str
    title: str
    fields: list[FormInputContext]
    show: bool = False
    className: str = ''

    def toJSON(self, pure: bool = False, exclude: AbstractSet | None = None) -> InputFieldGroupJson:
        js: InputFieldGroupJson = {
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
