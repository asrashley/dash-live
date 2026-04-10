#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .with_children import BoxWithChildren, BoxWithChildrenFactory


class UserDataBox(BoxWithChildren):
    ATOM_FOURCC = 'udta'


class UserDataBoxFactory(BoxWithChildrenFactory[UserDataBox]):
    def atom_type(self) -> type[UserDataBox]:
        return UserDataBox
