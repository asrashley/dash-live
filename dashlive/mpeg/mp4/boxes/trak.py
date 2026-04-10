#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .with_children import BoxWithChildren, BoxWithChildrenFactory


class TrackBox(BoxWithChildren):
    ATOM_FOURCC = 'trak'
    include_atom_type = False


class TrackBoxFactory(BoxWithChildrenFactory[TrackBox]):
    def atom_type(self) -> type[TrackBox]:
        return TrackBox
