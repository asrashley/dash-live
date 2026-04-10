#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .visual_sample_entry import VisualSampleEntry, VisualSampleEntryFactory


class AVC1SampleEntry(VisualSampleEntry):
    ATOM_FOURCC = 'avc1'


class AVC1SampleEntryFactory(VisualSampleEntryFactory[AVC1SampleEntry]):
    def atom_type(self) -> type[AVC1SampleEntry]:
        return AVC1SampleEntry
