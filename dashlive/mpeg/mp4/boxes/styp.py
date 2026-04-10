#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .ftyp import FileTypeBox, FileTypeBoxFactory


class SegmentTypeBox(FileTypeBox):
    ATOM_FOURCC = 'styp'


class SegmentTypeBoxFactory(FileTypeBoxFactory):
    def atom_type(self) -> type[SegmentTypeBox]:
        return SegmentTypeBox
