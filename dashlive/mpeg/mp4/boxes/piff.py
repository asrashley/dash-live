#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .senc import CencSampleEncryptionBox, CencSampleEncryptionBoxFactory

# Protected Interoperable File Format (PIFF) SampleEncryptionBox uses the
# same format as the CencSampleEncryptionBox, but using a UUID box

PIFF_ATOM_FOURCC = 'UUID(a2394f525a9b4f14a2446c427c648df4)'


class PiffSampleEncryptionBox(CencSampleEncryptionBox):
    ATOM_FOURCC = PIFF_ATOM_FOURCC
    DEFAULT_VALUES = {
        'atom_type': PIFF_ATOM_FOURCC
    }

    @classmethod
    def clone_from_senc(cls, senc):
        """
        Create a PiffSampleEncryptionBox from a CencSampleEncryptionBox
        """
        samples = []
        for samp in senc.samples:
            samples.append(samp.clone())
        kwargs = {
            'atom_type': cls.DEFAULT_VALUES['atom_type'],
            'version': senc.version,
            'flags': senc.flags,
            'iv_size': senc.iv_size,
            'samples': samples,
            'position': 0,
        }
        if senc.flags & 0x01:
            kwargs['algorithm_id'] = senc.algorithm_id
            kwargs['kid'] = senc.kid
        return cls(**kwargs)


class PiffSampleEncryptionBoxFactory(CencSampleEncryptionBoxFactory):
    def atom_type(self) -> type[PiffSampleEncryptionBox]:
        return PiffSampleEncryptionBox
