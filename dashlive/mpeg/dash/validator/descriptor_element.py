from typing import Union

from .dash_element import DashElement
from .errors import ErrorSource, ValidationChecks, ValidationError

class DescriptorElement:
    def __init__(self, elt, parent: Union["DescriptorElement", DashElement]) -> None:
        self.parent = parent
        self.attributes = elt.attrib
        self.tag = elt.tag
        self.children = []
        self.text = elt.text
        line_range = parent.elt.location
        self.elt = ValidationChecks(ErrorSource.ELEMENT, line_range)
        for child in elt:
            self.children.append(DescriptorElement(child, self))

    def has_errors(self) -> bool:
        result = self.elt.has_errors()
        if result:
            return True
        for child in self.children:
            if child.has_errors():
                return True
        return False

    def get_errors(self) -> list[ValidationError]:
        result = self.elt.errors
        for child in self.children:
            result += child.get_errors()
        return result
