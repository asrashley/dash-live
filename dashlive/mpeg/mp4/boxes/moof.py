#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .with_children import BoxWithChildren, BoxWithChildrenFactory

class MovieFragmentBox(BoxWithChildren):
    ATOM_FOURCC = 'moof'


class MovieFragmentBoxFactory(BoxWithChildrenFactory[MovieFragmentBox]):
    def atom_type(self) -> type[MovieFragmentBox]:
        return MovieFragmentBox
