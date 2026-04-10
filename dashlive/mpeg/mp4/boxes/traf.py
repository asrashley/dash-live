#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .with_children import BoxWithChildren, BoxWithChildrenFactory


class TrackFragmentBox(BoxWithChildren):
    ATOM_FOURCC = 'traf'


class TrackFragmentBoxFactory(BoxWithChildrenFactory[TrackFragmentBox]):
    def atom_type(self) -> type[TrackFragmentBox]:
        return TrackFragmentBox
