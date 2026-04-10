#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .visual_sample_entry import VisualSampleEntry, VisualSampleEntryFactory


class HEV1SampleEntry(VisualSampleEntry):
    ATOM_FOURCC = 'hev1'


class HEV1SampleEntryFactory(VisualSampleEntryFactory[HEV1SampleEntry]):
    def atom_type(self) -> type[HEV1SampleEntry]:
        return HEV1SampleEntry
