#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .visual_sample_entry import VisualSampleEntry, VisualSampleEntryFactory


class EncryptedSampleEntry(VisualSampleEntry):
    ATOM_FOURCC = 'encv'


class EncryptedSampleEntryFactory(VisualSampleEntryFactory[EncryptedSampleEntry]):
    def atom_type(self) -> type[EncryptedSampleEntry]:
        return EncryptedSampleEntry
