#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .descriptor_element import DescriptorElement
from .dash_element import DashElement

class Descriptor(DashElement):
    attributes = [
        ('schemeIdUri', str, None),
        ('value', str, ""),
    ]

    def __init__(self, elt, parent: DashElement) -> None:
        super().__init__(elt, parent)
        self._children = []
        for child in elt:
            self._children.append(DescriptorElement(child, self))

    def validate(self) -> None:
        self.attrs.check_not_none(
            self.schemeIdUri, msg='schemeIdUri is mandatory')

    def children(self) -> list[DashElement]:
        return self._children
