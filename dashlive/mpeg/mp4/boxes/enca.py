#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .mp4a import MP4AudioSampleEntry, MP4AudioSampleEntryFactory


class EncryptedMP4A(MP4AudioSampleEntry):
    ATOM_FOURCC = 'enca'


class EncryptedMP4AFactory(MP4AudioSampleEntryFactory):
    def atom_type(self) -> type[EncryptedMP4A]:
        return EncryptedMP4A
