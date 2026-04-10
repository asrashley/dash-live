#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .visual_sample_entry import VisualSampleEntry, VisualSampleEntryFactory


class AVC3SampleEntry(VisualSampleEntry):
    ATOM_FOURCC = 'avc3'


class AVC3SampleEntryFactory(VisualSampleEntryFactory[AVC3SampleEntry]):
    def atom_type(self) -> type[AVC3SampleEntry]:
        return AVC3SampleEntry
