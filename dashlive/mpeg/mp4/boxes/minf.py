#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from .with_children import BoxWithChildren, BoxWithChildrenFactory

class MediaInformationBox(BoxWithChildren):
    ATOM_FOURCC = 'minf'


class MediaInformationBoxFactory(BoxWithChildrenFactory[MediaInformationBox]):
    def atom_type(self) -> type[MediaInformationBox]:
        return MediaInformationBox
