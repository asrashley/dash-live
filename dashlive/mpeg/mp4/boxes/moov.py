#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .with_children import BoxWithChildren, BoxWithChildrenFactory

class MovieBox(BoxWithChildren):
    ATOM_FOURCC = 'moov'
    include_atom_type = False


class MovieBoxFactory(BoxWithChildrenFactory[MovieBox]):
    def atom_type(self) -> type[MovieBox]:
        return MovieBox
