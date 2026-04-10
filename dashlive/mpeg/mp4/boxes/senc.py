#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import AbstractSet, Any, BinaryIO, ClassVar, override

from dashlive.utils.binary import HexBinary
from dashlive.utils.fio import FieldReader, FieldWriter
from dashlive.utils.json_object import JsonObject
from dashlive.utils.list_of import ListOf
from dashlive.utils.object_with_fields import ObjectWithFields

from ..atom import MODULE_PREFIX_RE, Mp4Atom
from ..options import Options

from .full import FullBox, FullBoxFactory

# See 2.2.4 of Common File Format & Media Formats Specification Version 2.1
class CencSubSample(ObjectWithFields):
    REQUIRED_FIELDS = {
        'clear': int,
        'encrypted': int,
    }

    @classmethod
    def parse(cls, src):
        rv = {}
        r = FieldReader(cls.classname(), src, rv)
        r.read('H', 'clear')
        r.read('I', 'encrypted')
        return rv

    def encode(self, dest):
        d = FieldWriter(self, dest)
        d.write('H', 'clear')
        d.write('I', 'encrypted')

    @override
    def _to_json(self, exclude: AbstractSet) -> JsonObject:
        rv = super()._to_json(exclude)
        if '_type' in rv:
            rv['_type'] = MODULE_PREFIX_RE.sub(r'\g<box_name>', rv['_type'])
        return rv

class CencSampleAuxiliaryData(ObjectWithFields):
    UseSubsampleEncryption: ClassVar[int] = 2

    OBJECT_FIELDS = {
        "initialization_vector": HexBinary,
        "subsamples": ListOf(CencSubSample),
    }

    @classmethod
    def parse(cls, src, size, iv_size, flags, parent):
        subsample_encryption = (flags & cls.UseSubsampleEncryption) == cls.UseSubsampleEncryption
        if iv_size is None:
            if not subsample_encryption:
                iv_size = size
            else:
                raise ValueError("Unable to determine IV size")
        rv = {
            "iv_size": iv_size,
            "offset": src.tell() - parent['position'],
            "size": size,
        }
        r = FieldReader(cls.classname(), src, rv)
        r.read(iv_size, "initialization_vector", encoder=HexBinary)
        rv["subsamples"] = []
        if subsample_encryption and size >= (iv_size + 2):
            subsample_count = r.get('H', 'subsample_count')
            if size < (subsample_count * 6):
                raise ValueError(f'Invalid subsample_count {subsample_count}')
            for i in range(subsample_count):
                rv["subsamples"].append(CencSubSample.parse(src))
        return rv

    def encode(self, dest, parent):
        assert len(self.initialization_vector) == self.iv_size
        self.position = dest.tell()
        d = FieldWriter(self, dest)
        d.write(None, 'initialization_vector')
        if ((parent.flags & self.UseSubsampleEncryption) == self.UseSubsampleEncryption and
                self.subsamples):
            d.write('H', 'subsample_count', value=len(self.subsamples))
            for samp in self.subsamples:
                samp.encode(dest)

    @override
    def _to_json(self, exclude: AbstractSet) -> JsonObject:
        rv = super()._to_json(exclude)
        if '_type' in rv:
            rv['_type'] = MODULE_PREFIX_RE.sub(r'\g<box_name>', rv['_type'])
        return rv


class CencSampleEncryptionBox(FullBox):
    ATOM_FOURCC = 'senc'
    OBJECT_FIELDS = {
        "kid": HexBinary,
        "samples": ListOf(CencSampleAuxiliaryData),
        **FullBox.OBJECT_FIELDS,
    }

    def encode_fields(self, dest):
        if len(self.samples) > 0:
            self.flags |= 0x02
        super().encode_fields(dest)

    def encode_box_fields(self, dest):
        d = FieldWriter(self, dest)
        if self.flags & 0x01:
            alg = __import__('struct').pack('>I', self.algorithm_id)
            d.write(3, 'algorithm_id', value=alg[1:])
            d.write('B', 'iv_size')
            d.write(16, 'kid')
        d.write('I', 'sample_count', value=len(self.samples))
        for s in self.samples:
            s.encode(dest, self)


class CencSampleEncryptionBoxFactory(FullBoxFactory[CencSampleEncryptionBox]):
    REQUIRED_PEERS = ['saiz']

    def atom_type(self) -> type[CencSampleEncryptionBox]:
        return CencSampleEncryptionBox

    @override
    def depends_upon(self):
        return {'moov', 'tenc'}

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        if rv["flags"] & 0x01:
            r.read('3I', 'algorithm_id')
            r.read('B', 'iv_size')
            if rv["iv_size"] == 0:
                rv["iv_size"] = 8
            r.read(16, 'kid')
        else:
            try:
                moov = parent.find_atom("moov")
                tenc = moov.find_child("tenc")
                rv["iv_size"] = tenc.iv_size
            except AttributeError:
                rv["iv_size"] = options.iv_size if options is not None else None
        num_entries = r.get('I', 'num_entries')
        assert rv['iv_size'] in {8, 16}
        rv["samples"] = []
        saiz = parent.find_child('saiz')
        if saiz is None:
            if options is not None:
                options.log.warning('Failed to find saiz box')
            rv['error'] = 'Failed to find required saiz box'
            return rv
        samples: list[CencSampleAuxiliaryData] = []
        for i in range(num_entries):
            if saiz.sample_info_sizes:
                size = saiz.sample_info_sizes[i]
            else:
                size = saiz.default_sample_info_size
            if size:
                s = CencSampleAuxiliaryData.parse(
                    src, size, rv["iv_size"], rv["flags"], rv)
                samples.append(s)
        rv["samples"] = samples
        return rv
