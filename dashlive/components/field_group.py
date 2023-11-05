#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from dataclasses import dataclass

from dashlive.utils.json_object import JsonObject

@dataclass(slots=True)
class InputFieldGroup:
    title: str
    fields: list[JsonObject]
    show: bool = False
    className: str = ''
