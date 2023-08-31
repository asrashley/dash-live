class DescriptorElement:
    def __init__(self, elt):
        self.attributes = elt.attrib
        self.tag = elt.tag
        self.children = []
        self.text = elt.text
        for child in elt:
            self.children.append(DescriptorElement(child))
