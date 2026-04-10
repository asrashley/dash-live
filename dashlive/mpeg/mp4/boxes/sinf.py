#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .with_children import BoxWithChildren, BoxWithChildrenFactory


class ProtectionSchemeInformationBox(BoxWithChildren):
    ATOM_FOURCC = 'sinf'


class ProtectionSchemeInformationBoxFactory(BoxWithChildrenFactory[ProtectionSchemeInformationBox]):
    def atom_type(self) -> type[ProtectionSchemeInformationBox]:
        return ProtectionSchemeInformationBox
