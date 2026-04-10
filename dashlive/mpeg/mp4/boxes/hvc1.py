#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .visual_sample_entry import VisualSampleEntry, VisualSampleEntryFactory


class HVC1SampleEntry(VisualSampleEntry):
    ATOM_FOURCC = 'hvc1'


class HVC1SampleEntryFactory(VisualSampleEntryFactory[HVC1SampleEntry]):
    def atom_type(self) -> type[HVC1SampleEntry]:
        return HVC1SampleEntry
