#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .with_children import BoxWithChildren, BoxWithChildrenFactory


class MovieExtendsBox(BoxWithChildren):
    ATOM_FOURCC = 'mvex'


class MovieExtendsBoxFactory(BoxWithChildrenFactory[MovieExtendsBox]):
    def atom_type(self) -> type[MovieExtendsBox]:
        return MovieExtendsBox
