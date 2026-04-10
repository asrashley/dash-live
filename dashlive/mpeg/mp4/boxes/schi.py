#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .with_children import BoxWithChildren, BoxWithChildrenFactory


class SchemaInformationBox(BoxWithChildren):
    ATOM_FOURCC = 'schi'


class SchemaInformationBoxFactory(BoxWithChildrenFactory[SchemaInformationBox]):
    def atom_type(self) -> type[SchemaInformationBox]:
        return SchemaInformationBox
