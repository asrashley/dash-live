#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .with_children import BoxWithChildren, BoxWithChildrenFactory


class SampleTableBox(BoxWithChildren):
    ATOM_FOURCC = 'stbl'


class SampleTableBoxFactory(BoxWithChildrenFactory[SampleTableBox]):
    def atom_type(self) -> type[SampleTableBox]:
        return SampleTableBox
