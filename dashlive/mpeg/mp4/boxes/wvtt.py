#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .sample_entry import SampleEntry, SampleEntryFactory

class PlainTextSampleEntry(SampleEntry):
    pass


class WVTTSampleEntry(PlainTextSampleEntry):
    ATOM_FOURCC = 'wvtt'


class WVTTSampleEntryFactory(SampleEntryFactory[WVTTSampleEntry]):
    parse_children = True

    def atom_type(self) -> type[WVTTSampleEntry]:
        return WVTTSampleEntry
