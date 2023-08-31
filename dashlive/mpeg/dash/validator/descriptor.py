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

    def __init__(self, elt, parent):
        super().__init__(elt, parent)
        self.children = []
        for child in elt:
            self.children.append(DescriptorElement(child))

    def validate(self, depth=-1):
        self.checkIsNotNone(self.schemeIdUri)
