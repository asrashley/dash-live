#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .audio_sample_entry import AudioSampleEntry, AudioSampleEntryFactory


class AC3SampleEntry(AudioSampleEntry):
    ATOM_FOURCC = 'ac-3'


class AC3SampleEntryFactory(AudioSampleEntryFactory[AC3SampleEntry]):
    def atom_type(self) -> type[AC3SampleEntry]:
        return AC3SampleEntry
