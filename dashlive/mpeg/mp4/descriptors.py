#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from abc import abstractmethod
import copy
import io
import struct
from typing import Any, BinaryIO, ClassVar, Union, TYPE_CHECKING, cast

from dashlive.utils.binary import Binary
from dashlive.utils.fio import FieldReader, BitsFieldReader, FieldWriter
from dashlive.utils.json_object import JsonObject
from dashlive.utils.list_of import ListOf
from dashlive.utils.object_with_fields import ObjectWithFields

from .options import Options

MP4_DESCRIPTORS: dict[int, type["Descriptor"]] = {}  # map from descriptor tag to class

if TYPE_CHECKING:
    from .atom import Mp4Atom

def mp4descriptor(tag: int):
    def func(cls: type["Descriptor"]) -> type["Descriptor"]:
        MP4_DESCRIPTORS[tag] = cls
        return cls
    return func

class Descriptor(ObjectWithFields):
    OBJECT_FIELDS: ClassVar[dict[str, Any]] = {
        'children': ListOf(ObjectWithFields),
        'data': Binary,
    }

    REQUIRED_FIELDS = {
        'tag': int,
    }

    _fullname: str
    _encoded: bytes | None = None
    children: list["Descriptor"]
    header_size: int
    options: Options
    position: int
    size: int
    tag: int

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.apply_defaults({
            "children": [],
            "options": Options(),
        })
        parent: Mp4Atom | Descriptor | None = kwargs.get("parent", None)
        if parent:
            self._fullname = fr'{parent._fullname}.{self.classname()}'
        else:
            self._fullname = self.classname()

    @classmethod
    def load(cls,
             src: BinaryIO,
             parent: Union["Descriptor", "Mp4Atom", None],
             options: Options,
             **kwargs) -> "Descriptor":
        position: int = src.tell()
        kw = Descriptor.parse_header(src)
        try:
            Desc: type[Descriptor] = MP4_DESCRIPTORS[kw["tag"]]
        except KeyError:
            Desc = UnknownDescriptor
        total_size = kw["size"] + kw["header_size"]
        options.log.debug(
            'load descriptor: tag=%s type=%s pos=%d size=%d',
            kw["tag"], Desc.__name__, position, total_size)
        Desc.parse_payload(src, kw, parent=parent, options=options)
        rv: Descriptor = Desc(
            parent=parent, options=options, position=position, **kw)
        end: int = position + rv.size + rv.header_size
        while src.tell() < end:
            options.log.debug(
                'Descriptor: parse descriptor pos=%d end=%d',
                src.tell(), end)
            dc: Descriptor = Descriptor.load(src, parent=rv, options=options)
            rv.children.append(dc)
        return rv

    @classmethod
    def from_kwargs(cls, tag: int, **kwargs) -> "Descriptor":
        assert isinstance(tag, int)
        try:
            Desc = MP4_DESCRIPTORS[tag]
        except KeyError:
            Desc = UnknownDescriptor
        if Desc.DEFAULT_VALUES is None:
            args: dict[str, Any] = kwargs
        else:
            args = copy.deepcopy(Desc.DEFAULT_VALUES)
            args.update(**kwargs)
        args['tag'] = tag
        return Desc(**args)

    @classmethod
    def parse_header(cls, src: BinaryIO) -> dict[str, Any]:
        b: bytes = src.read(1)
        if len(b) == 0:
            position: int = src.tell()
            raise ValueError(
                f"Failed to read tag byte: pos={position}")
        tag: int = struct.unpack('B', b)[0]
        header_size: int = 1
        more_bytes: bool = True
        size: int = 0
        while more_bytes and header_size < 5:
            header_size += 1
            d: int = struct.unpack('B', src.read(1))[0]
            more_bytes = (d & 0x80) == 0x80
            size = (size << 7) + (d & 0x7f)
        return {
            "tag": tag,
            "header_size": header_size,
            "size": size,
        }

    def encode(self, dest: BinaryIO) -> None:
        start: int = dest.tell()
        d: FieldWriter = FieldWriter(self, dest, debug=self.options.debug)
        self.options.log.debug(
            r'%s: encode descriptor pos=%d', self._fullname, start)
        payload = io.BytesIO()
        self.encode_fields(payload)
        self.options.log.debug(
            r'%s: fields produced %d bytes', self._fullname, payload.tell())
        for ch in self.children:
            cast(Descriptor, ch).encode(payload)
        self.options.log.debug(
            r'%s: Total payload size %d bytes', self._fullname, payload.tell())
        payload = payload.getvalue()
        if self.size == 0:
            self.size = len(payload)
        elif self.size != len(payload):
            self.options.log.warning("Descriptor %s should be %d bytes but encoded %d",
                                     self.classname(), self.size, len(payload))
            self.size = len(payload)
        d.write('B', 'tag')
        sizes = []
        size = self.size
        while size > 0x7f:
            sizes.append(size & 0x7f)
            size = size >> 7
        sizes.append(size & 0x7f)
        while sizes:
            a = sizes.pop(0)
            flag = 0x80 if sizes else 0x00
            d.write('B', 'size', a + flag)
        if payload:
            d.write(None, 'payload', payload)
        self.options.log.debug(
            'descriptor "%s" produced %d bytes (%d .. %d)',
            self.classname(), len(payload), start, dest.tell())

    @abstractmethod
    def encode_fields(self, dest: BinaryIO) -> None:
        pass

    @classmethod
    def parse_payload(cls,
                      src: BinaryIO,
                      fields: dict[str, Any],
                      parent: Union["Descriptor", "Mp4Atom", None],
                      options: Options) -> dict[str, Any]:
        raise RuntimeError("parse_payload must be implemented for each Descriptor class")

    def __getattr__(self, name):
        if type(self).__name__ == name:
            return self
        for d in self.children:
            if type(d).__name__ == name:
                return d
            v = getattr(d, name, None)
            if v is not None:
                return v
        raise AttributeError(name)

    def _to_json(self, exclude: set[str]) -> JsonObject:
        exclude = exclude.union({'parent', 'options'})
        return super()._to_json(exclude)

    def dump(self, indent: str = '') -> None:
        f = r'{}{}: {:d} -> {:d} [header {:d} bytes] [{:d} bytes]'
        print(f.format(indent,
                       self.classname(),
                       self.position,
                       self.position + self.size + self.header_size,
                       self.header_size,
                       self.size))
        for c in self.children:
            c.dump(indent + '  ')


Descriptor.OBJECT_FIELDS['children'] = ListOf(Descriptor)

class UnknownDescriptor(Descriptor):
    OBJECT_FIELDS = {
        'data': Binary,
    }
    OBJECT_FIELDS.update(Descriptor.OBJECT_FIELDS)

    include_atom_type = True
    data: Binary

    @classmethod
    def parse_payload(cls,
                      src: BinaryIO,
                      fields: dict[str, Any],
                      parent: Union["Descriptor", "Mp4Atom", None],
                      options: Options) -> dict[str, Any]:
        if fields["size"] > 0:
            fields["data"] = src.read(fields["size"])
        else:
            fields["data"] = None
        return fields

    def encode_fields(self, dest: BinaryIO) -> None:
        if self.data is not None:
            assert isinstance(self.data, Binary)
            dest.write(self.data.data)


@mp4descriptor(0x03)
class ESDescriptor(Descriptor):
    @classmethod
    def parse_payload(cls,
                      src: BinaryIO,
                      fields: dict[str, Any],
                      parent: Union["Descriptor", "Mp4Atom", None],
                      options: Options) -> dict[str, Any]:
        r = FieldReader(cls.classname(), src, fields, debug=options.debug if options else False)
        r.read('H', 'es_id')
        b = r.get('B', 'flags')
        fields["stream_dependence_flag"] = (b & 0x80) == 0x80
        url_flag = (b & 0x40) == 0x40
        ocr_stream_flag = (b & 0x20) == 0x20
        fields["stream_priority"] = b & 0x1f
        if fields["stream_dependence_flag"]:
            r.read('H', "depends_on_es_id")
        if url_flag:
            leng = r.get('B', 'url_length')
            r.read(leng, 'url')
        else:
            fields["url"] = None
        if ocr_stream_flag:
            r.read('H', 'ocr_es_id')
        else:
            fields['ocr_es_id'] = None
        return fields

    def encode_fields(self, dest: BinaryIO) -> None:
        w = FieldWriter(self, dest, debug=self.options.debug)
        w.write('H', 'es_id')
        b = self.stream_priority & 0x1f
        if self.stream_dependence_flag:
            b += 0x80
        if self.url is not None:
            b += 0x40
        if self.ocr_es_id is not None:
            b += 0x20
        w.write('B', 'flags', b)
        if self.stream_dependence_flag:
            w.write('H', "depends_on_es_id")
        if self.url is not None:
            w.write('B', 'url_length', len(self.url))
            w.write(None, 'url')
        if self.ocr_es_id is not None:
            w.write('H', 'ocr_es_id')


@mp4descriptor(0x04)
class DecoderConfigDescriptor(Descriptor):
    @classmethod
    def parse_payload(cls,
                      src: BinaryIO,
                      fields: dict[str, Any],
                      parent: Union["Descriptor", "Mp4Atom", None],
                      options: Options) -> dict[str, Any]:
        r = FieldReader(cls.classname(), src, fields, debug=options.debug if options else False)
        r.read('B', "object_type")
        b = r.get('B', "stream_type")
        fields["stream_type"] = (b >> 2)
        fields["unknown_flag"] = (b & 0x01) == 0x01
        fields["upstream"] = (b & 0x02) == 0x02
        r.read('3I', "buffer_size")
        r.read('I', "max_bitrate")
        r.read('I', "avg_bitrate")
        return fields

    def encode_fields(self, dest: BinaryIO) -> None:
        w = FieldWriter(self, dest)
        w.write('B', "object_type")
        b = self.stream_type << 2
        if self.unknown_flag:
            b |= 0x01
        if self.upstream:
            b |= 0x02
        w.write('B', 'stream_type', b)
        w.write('3I', 'buffer_size')
        w.write('I', "max_bitrate")
        w.write('I', "avg_bitrate")


@mp4descriptor(0x05)
class DecoderSpecificInfo(Descriptor):
    SAMPLE_RATES = [96000, 88200, 64000, 48000, 44100, 32000,
                    24000, 22050, 16000, 12000, 11025, 8000, 7350]

    OBJECT_FIELDS = {
        'data': Binary,
    }
    OBJECT_FIELDS.update(Descriptor.OBJECT_FIELDS)

    @classmethod
    def parse_payload(cls,
                      src: BinaryIO,
                      fields: dict[str, Any],
                      parent: Union["Descriptor", "Mp4Atom", None],
                      options: Options) -> dict[str, Any]:
        if parent is not None:
            fields["object_type"] = parent.object_type
        r = BitsFieldReader(cls.classname(), src, fields, fields["size"])
        if fields["object_type"] == 0x40:  # Audio ISO/IEC 14496-3 subpart 1
            r.read(5, "audio_object_type")
            r.read(4, "sampling_frequency_index")
            if fields["sampling_frequency_index"] == 0xf:
                r.read(24, "sampling_frequency")
            else:
                fields["sampling_frequency"] = cls.SAMPLE_RATES[fields["sampling_frequency_index"]]
            r.read(4, "channel_configuration")
            r.read(1, "frame_length_flag")
            r.read(1, "depends_on_core_coder")
            if fields["depends_on_core_coder"]:
                r.read(14, "core_coder_delay")
            r.read(1, "extension_flag")
            # if not fields["channel_configuration"]:
            #    fields["channel_configuration"] = clz.parse_config_element(src, parent)
            if fields["audio_object_type"] == 6 or fields["audio_object_type"] == 20:
                r.read(3, "layer_nr")
            if fields["extension_flag"]:
                if fields["audio_object_type"] == 22:
                    r.read(5, "num_sub_frame")
                    r.read(11, "layer_length")
                if fields["audio_object_type"] in [17, 19, 20, 23]:
                    r.read(1, "aac_section_data_resilience_flag")
                    r.read(1, "aac_scalefactor_data_resilience_flag")
                    r.read(1, "aac_spectral_data_resilience_flag")
                r.read(1, "extension_flag_3")
        fields["data"] = None
        if r.bitpos() != (8 * fields["size"]):
            skip = 8 - r.bitpos() & 7
            if skip:
                r.read(skip, 'reserved')
            if r.bytepos() != fields["size"]:
                fields["data"] = r.data[r.bytepos():]
        return fields

    def encode_fields(self, dest: BinaryIO) -> None:
        w = FieldWriter(self, dest)
        if self.object_type == 0x40:  # Audio ISO/IEC 14496-3 subpart 1
            w.writebits(5, "audio_object_type")
            w.writebits(4, "sampling_frequency_index")
            if self.sampling_frequency_index == 0xf:
                w.writebits(24, "sampling_frequency")
            w.writebits(4, "channel_configuration")
            w.writebits(1, 'frame_length_flag')
            w.writebits(1, "depends_on_core_coder")
            if self.depends_on_core_coder:
                w.writebits(14, "core_coder_delay")
            w.writebits(1, "extension_flag")
            if self.audio_object_type == 6 or self.audio_object_type == 20:
                w.writebits(3, "layer_nr")
            if self.extension_flag:
                if self.audio_object_type == 22:
                    w.writebits(5, "num_sub_frame")
                    w.writebits(11, "layer_length")
                if self.audio_object_type in [17, 19, 20, 23]:
                    w.writebits(1, "aac_section_data_resilience_flag")
                    w.writebits(1, "aac_scalefactor_data_resilience_flag")
                    w.writebits(1, "aac_spectral_data_resilience_flag")
                w.writebits(1, "extension_flag_3")
        w.done()
        if self.data is not None:
            w.write(None, "data")
