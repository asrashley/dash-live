#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import cast
from .descriptor_element import DescriptorElement
from .dash_element import DashElement

class Descriptor(DashElement):
    attributes = [
        ('schemeIdUri', str, None),
        ('value', str, ""),
    ]

    schemeIdUri: str | None
    value: str
    _children: list[DescriptorElement]

    def __init__(self, elt, parent: DashElement) -> None:
        super().__init__(elt, parent)
        self._children = []
        for child in elt:
            self._children.append(DescriptorElement(child, self))

    async def validate(self) -> None:
        self.attrs.check_not_none(
            self.schemeIdUri, msg='schemeIdUri is mandatory')

    def children(self) -> list[DashElement]:
        return cast(list[DashElement], self._children)
