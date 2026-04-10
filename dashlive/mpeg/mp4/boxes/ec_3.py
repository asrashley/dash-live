#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .audio_sample_entry import AudioSampleEntry, AudioSampleEntryFactory


class EC3SampleEntry(AudioSampleEntry):
    ATOM_FOURCC = 'ec-3'


class EC3SampleEntryFactory(AudioSampleEntryFactory[EC3SampleEntry]):
    def atom_type(self) -> type[EC3SampleEntry]:
        return EC3SampleEntry
