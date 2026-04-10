#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .with_children import BoxWithChildren, BoxWithChildrenFactory


class MediaDataBox(BoxWithChildren):
    ATOM_FOURCC = 'mdia'


class MediaDataBoxFactory(BoxWithChildrenFactory[MediaDataBox]):
    def atom_type(self) -> type[MediaDataBox]:
        return MediaDataBox
