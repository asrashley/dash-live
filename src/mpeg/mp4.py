#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from abc import ABCMeta, abstractmethod
import argparse
import copy
import io
import json
import logging
import os
import re
import struct
import sys

try:
    import bitstring
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
    import bitstring

from utils.bitio import FieldReader, BitsFieldReader, FieldWriter
from utils.binary import Binary
from utils.date_time import DateTimeField, from_iso_epoch, to_iso_epoch
from utils.object_with_fields import ObjectWithFields
from utils.list_of import ListOf
from mpeg.nal import Nal

MP4_BOXES = {}
MP4_DESCRIPTORS = {}

class Options(ObjectWithFields):
    DEFAULT_VALUES = {
        "cache_encoded": False,
        "iv_size": None,
    }

    def __init__(self, **kwargs):
        super(Options, self).__init__(**kwargs)
        self.log = logging.getLogger('mp4')


class Mp4Atom(ObjectWithFields):
    __metaclass__ = ABCMeta
    parse_children = False
    include_atom_type = False

    OBJECT_FIELDS = {
        'children': ListOf(ObjectWithFields),
        'options': Options,
        'parent': ObjectWithFields,
    }
    DEFAULT_EXCLUDE = {'options', 'parent'}

    def __init__(self, **kwargs):
        self._encoded = None
        super(Mp4Atom, self).__init__(**kwargs)
        self.apply_defaults({
            'children': [],
            'options': Options(),
            'parent': None,
            'size': 0,
        })
        try:
            atom_type = kwargs["atom_type"]
        except KeyError:
            atom_type = None
            for k, v in MP4_BOXES.iteritems():
                if v == type(self):
                    atom_type = k
                    break
            if atom_type is None:
                raise KeyError("atom_type")
        self._fields.add('atom_type')
        self.atom_type = atom_type
        if self.parent:
            self._fullname = r'{0}.{1}'.format(self.parent._fullname, self.atom_type)
        else:
            self._fullname = self.atom_type
        for ch in self.children:
            ch.parent = self

    def __getattr__(self, name):
        if name in self.__dict__:
            return self.__dict__[name]
        if name[0] == "_":
            # __getattribute__ should have responded before __getattr__ called
            raise AttributeError(name)
        if name in self._fields:
            # __getattribute__ should have responded before __getattr__ called
            raise AttributeError(name)
        for c in self.children:
            if c.atom_type == name:
                return c
            if '-' in c.atom_type:
                if c.atom_type.replace('-', '_') == name:
                    return c
        raise AttributeError(name)

    def _invalidate(self):
        if self._encoded is not None:
            self._encoded = None
            if self.parent:
                self.parent._invalidate()

    def __setattr__(self, name, value):
        if name[0] != '_' and name in self._fields:
            self._invalidate()
        object.__setattr__(self, name, value)

    def __delattr__(self, name):
        if name in self._fields:
            raise AttributeError('Unable to delete field {} '.format(name))
        for idx, c in enumerate(self.children):
            if c.atom_type == name:
                self.remove_child(idx)
                return
            if '-' in c.atom_type and c.atom_type.replace('-', '_') == name:
                self.remove_child(idx)
                return
        raise AttributeError(name)

    def _field_repr(self, exclude):
        if not self.include_atom_type:
            exclude = exclude.union({'atom_type', 'options'})
        return super(Mp4Atom, self)._field_repr(exclude)

    def _int_field_repr(self, fields, names):
        for name in names:
            fields.append('%s=%d' % (name, self.__getattribute__(name)))
        return fields

    def find_atom(self, atom_type, check_parent=True):
        if self.atom_type == atom_type:
            return self
        for ch in self.children:
            if ch.atom_type == atom_type:
                return ch
        if check_parent and self.parent:
            return self.parent.find_atom(atom_type, True)
        raise AttributeError(atom_type)

    def find_child(self, atom_type):
        for child in self.children:
            if child.atom_type == atom_type:
                return child
            child = child.find_child(atom_type)
            if child:
                return child
        return None

    def index(self, atom_type):
        for idx, c in enumerate(self.children):
            if c.atom_type == atom_type:
                return idx
        raise ValueError(atom_type)

    def append_child(self, child):
        self.options.log.debug(
            '%s: append_child "%s"', self._fullname, child.atom_type)
        self.children.append(child)
        if child.size:
            self.size += child.size
        else:
            self.size = 0
        self._invalidate()

    def insert_child(self, index, child):
        self.children.insert(index, child)
        if child.size:
            self.size += child.size
        self._invalidate()

    def remove_child(self, idx):
        child = self.children[idx]
        del self.children[idx]
        if child.size:
            self.size += child.size
        else:
            self.size = 0
        self._invalidate()

    @classmethod
    def create(cls, src, parent=None, options=None):
        assert src is not None
        if options is None:
            options = Options()
        elif isinstance(options, dict):
            options = Options(**options)
        if parent is not None:
            cursor = parent.payload_start
            end = parent.position + parent.size
            prefix = r'{0}: '.format(parent._fullname)
        else:
            parent = Wrapper(position=src.tell(), atom_type='wrap')
            end = None
            cursor = 0
            prefix = ''
        rv = parent.children
        if end is None:
            options.log.debug('%sCreate start=%d end=None', prefix, cursor)
        else:
            options.log.debug('%sCreate start=%d end=%d (%d)', prefix,
                              cursor, end, end - cursor)
        while end is None or cursor < end:
            assert cursor is not None
            if src.tell() != cursor:
                # options.log.debug('Move cursor from %d to %d', src.tell(), cursor)
                src.seek(cursor)
            hdr = Mp4Atom.parse(src, parent, options=options)
            if hdr is None:
                break
            try:
                Box = MP4_BOXES[hdr['atom_type']]
            except KeyError:
                Box = UnknownBox
            options.log.debug('%sfound atom "%s" type=%s pos=%d size=%d',
                              prefix,
                              hdr['atom_type'], Box.__name__,
                              hdr['position'], hdr['size'])
            encoded = None
            if options.cache_encoded and not Box.parse_children:
                sz = hdr["size"] - hdr["header_size"]
                if sz == 0:
                    encoded = ''
                else:
                    encoded = src.peek(sz)[:sz]
                    if len(encoded) < sz:
                        p = src.tell()
                        encoded = src.read(sz)
                        src.seek(p)
            kwargs = Box.parse(src, parent, options=options, initial_data=hdr)
            kwargs['parent'] = parent
            kwargs['options'] = options
            atom = Box(**kwargs)
            atom.payload_start = src.tell()
            rv.append(atom)
            if atom.parse_children:
                # options.log.debug('Parse %s children', hdr['atom_type'])
                Mp4Atom.create(src, atom, options)
            if encoded:
                atom._encoded = encoded
            if (src.tell() - atom.position) != atom.size:
                options.log.warning(
                    '%s: expected %s to contain %d bytes but parsed %d bytes',
                    prefix, atom.atom_type, atom.size, src.tell() - atom.position)
            cursor += atom.size
        return rv

    @classmethod
    def fromJSON(cls, src, parent=None, options=None):
        assert src is not None
        if options is None:
            options = Options()
        elif isinstance(options, dict):
            options = Options(**options)
        if isinstance(src, list):
            return map(lambda atom: cls.fromJSON(atom), src)

        if '_type' in src:
            name = src['_type']
            if name.startswith('mpeg.mp4.'):
                name = name[9:]
            # TODO: remove the use of eval()
            Box = eval(name)
        elif 'atom_type' in src:
            Box = MP4_BOXES[src['atom_type']]
        else:
            Box = UnknownBox
        src['parent'] = parent
        src['options'] = options
        if 'children' not in src:
            return Box(**src)

        children = src['children']
        src['children'] = []
        rv = Box(**src)
        for child in children:
            if isinstance(child, dict):
                child['parent'] = rv
                child['options'] = options
                rv.children.append(cls.fromJSON(child))
            else:
                rv.children.append(child)
        return rv

    @classmethod
    def parse(cls, src, parent, options=None, **kwargs):
        try:
            return kwargs['initial_data']
        except KeyError:
            pass
        position = src.tell()
        size = src.read(4)
        if not size or len(size) != 4:
            if options:
                if len(size) == 0:
                    options.log.debug("EOS at %d", position)
                else:
                    options.log.debug(
                        'Failed to read box length. pos=%d', position)
            return None
        size = struct.unpack('>I', size)[0]
        atom_type = src.read(4)
        if not atom_type or len(atom_type) != 4:
            if options:
                options.log.debug('Failed to read atom type. pos=%d', position)
            return None
        if size == 0:
            pos = src.tell()
            src.seek(0, 2)  # seek to end
            size = src.tell() - pos
            src.seek(pos)
        elif size == 1:
            size = struct.unpack('>Q', src.read(8))[0]
            if not size:
                if options:
                    options.log.debug(
                        'Failed to read atom size. pos=%d', position)
                return None
        if atom_type == 'uuid':
            atom_type = src.read(16)
        return {
            "atom_type": atom_type,
            "position": position,
            "size": size,
            "header_size": src.tell() - position,
        }

    def encode(self, dest=None):
        out = dest
        if out is None:
            out = io.BytesIO()
        self.position = out.tell()
        if len(self.atom_type) > 4:
            assert len(self.atom_type) == 16
            fourcc = 'uuid' + self.atom_type
        else:
            assert len(self.atom_type) == 4
            fourcc = self.atom_type
        self.options.log.debug('%s: encode %s pos=%d', self._fullname,
                               self.classname, self.position)
        if self._encoded is not None:
            self.options.log.debug('%s: Using pre-encoded data length=%d',
                                   self._fullname, len(self._encoded))
            if self.size != (4 + len(fourcc) + len(self._encoded)):
                self.options.log.warning(
                    "%s: Expected size %d, actual size %d", self.size,
                    self._fullname, 4 + len(fourcc) + len(self._encoded))
            out.write(struct.pack('>I', self.size))
            out.write(fourcc)
            out.write(self._encoded)
            if dest is None:
                return out.getvalue()
            return dest
        out.write(struct.pack('>I', 0))
        out.write(fourcc)
        self.encode_fields(dest=out)
        for child in self.children:
            child.encode(dest=out)
        self.size = out.tell() - self.position
        # replace the length field
        out.seek(self.position)
        out.write(struct.pack('>I', self.size))
        out.seek(0, 2)  # seek to end
        self.options.log.debug('%s: produced %d bytes pos=(%d .. %d)',
                               self._fullname, self.size,
                               self.position, out.tell())
        if dest is None:
            return out.getvalue()
        return dest

    @abstractmethod
    def encode_fields(self, dest):
        pass

    def dump(self, indent=''):
        atom_type = self.atom_type
        if len(atom_type) != 4:
            atom_type = 'UUID(' + atom_type.encode('hex') + ')'
        print('{}{}: {:d} -> {:d} [{:d} bytes]'.format(
            indent, atom_type, self.position,
            self.position + self.size, self.size))
        if 'descriptors' in self._fields:
            for d in self.descriptors:
                d.dump(indent + '  ')
        for c in self.children:
            c.dump(indent + '  ')


Mp4Atom.OBJECT_FIELDS['children'] = ListOf(Mp4Atom)

class WrapperIterator:
    def __init__(self, wrapper):
        self._wrapper = wrapper
        self._current = 0

    def next(self):
        if self._current < len(self._wrapper.children):
            rv = self._wrapper.children[self._current]
            self._current += 1
            return rv
        raise StopIteration


class Wrapper(Mp4Atom):
    def encode_fields(self, dest):
        pass

    def __iter__(self):
        return WrapperIterator(self)


class UnknownBox(Mp4Atom):
    include_atom_type = True
    OBJECT_FIELDS = {
        'data': Binary,
    }
    OBJECT_FIELDS.update(Mp4Atom.OBJECT_FIELDS)

    @classmethod
    def parse(clz, src, *args, **kwargs):
        rv = Mp4Atom.parse(src, *args, **kwargs)
        size = rv["size"] - rv["header_size"]
        if size > 0:
            rv["data"] = src.read(size)
        else:
            rv["data"] = None
        return rv

    def encode_fields(self, dest):
        if self.data is not None:
            try:
                dest.write(self.data.data)
            except AttributeError:
                # self.data is not wrapped in a Binary() object
                dest.write(self.data)

class FileTypeBox(Mp4Atom):
    OBJECT_FIELDS = {
        "compatible_brands": ListOf(str),
    }

    @classmethod
    def parse(clz, src, *args, **kwargs):
        rv = Mp4Atom.parse(src, *args, **kwargs)
        r = FieldReader(clz.classname, src, rv)
        r.read(4, 'major_brand')
        r.read('I', 'minor_version')
        size = rv["size"] - rv["header_size"] - 8
        rv['compatible_brands'] = []
        while size > 3:
            cb = r.get(4, 'compatible_brand')
            if len(cb) != 4:
                break
            rv['compatible_brands'].append(cb)
            size -= 4
        return rv

    def encode_fields(self, dest):
        d = FieldWriter(self, dest)
        d.write(4, 'major_brand')
        d.write('I', 'minor_version')
        for cb in self.compatible_brands:
            d.write(4, 'compatible_brand', cb)


MP4_BOXES['ftyp'] = FileTypeBox

class Descriptor(ObjectWithFields):
    __metaclass__ = ABCMeta

    OBJECT_FIELDS = {
        'children': ListOf(ObjectWithFields),
        'data': Binary,
        'parent': ObjectWithFields,
    }

    REQUIRED_FIELDS = {
        'tag': int,
    }

    def __init__(self, **kwargs):
        super(Descriptor, self).__init__(**kwargs)
        self.apply_defaults({
            "children": [],
            "options": Options(),
            "_encoded": None,
            "parent": None,
        })
        if self.parent:
            self._fullname = r'{0}.{1}'.format(self.parent._fullname, self.classname)
        else:
            self._fullname = self.classname

    @classmethod
    def create(clz, src, parent, options=None, **kwargs):
        if options is None:
            options = Options()
        kw = Descriptor.parse_header(src)
        try:
            Desc = MP4_DESCRIPTORS[kw["tag"]]
        except KeyError:
            Desc = UnknownDescriptor
        total_size = kw["size"] + kw["header_size"]
        options.log.debug(
            'create descriptor: tag=%s type=%s pos=%d size=%d',
            kw["tag"], Desc.__name__, kw["position"], total_size)
        encoded = src.peek(kw["size"])[:kw["size"]]
        if len(encoded) < kw["size"]:
            p = src.tell()
            encoded = src.read(kw["size"])
            src.seek(p)
        Desc.parse_payload(src, kw, parent=parent, options=options)
        rv = Desc(parent=parent, options=options, **kw)
        rv._encoded = encoded
        end = rv.position + rv.size + rv.header_size
        while src.tell() < end:
            options.log.debug(
                'Descriptor: parse descriptor pos=%d end=%d',
                src.tell(), end)
            dc = Descriptor.create(src, parent=rv, options=options)
            rv.children.append(dc)
            if (src.tell() - dc.position) != (dc.size + dc.header_size):
                options.log.warning(
                    'expected tag %d to contain %d bytes but parsed %d bytes',
                    dc.tag, dc.size, src.tell() - dc.position)
                src.seek(dc.position + dc.size + dc.header_size)
        return rv

    @classmethod
    def from_kwargs(clz, tag, **kwargs):
        assert isinstance(tag, int)
        try:
            Desc = MP4_DESCRIPTORS[tag]
        except KeyError:
            Desc = UnknownDescriptor
        if Desc.DEFAULT_VALUES is None:
            args = kwargs
        else:
            args = copy.deepcopy(Desc.DEFAULT_VALUES)
            args.update(**kwargs)
        args['tag'] = tag
        return Desc(**args)

    @classmethod
    def parse_header(clz, src):
        position = src.tell()
        b = src.read(1)
        if len(b) == 0:
            raise ValueError(
                "Failed to read tag byte: pos={}".format(position))
        tag = struct.unpack('B', b)[0]
        header_size = 1
        more_bytes = True
        size = 0
        while more_bytes and header_size < 5:
            header_size += 1
            b = struct.unpack('B', src.read(1))[0]
            more_bytes = (b & 0x80) == 0x80
            size = (size << 7) + (b & 0x7f)
        return {
            "position": position,
            "tag": tag,
            "header_size": header_size,
            "size": size,
        }

    def encode(self, dest):
        start = dest.tell()
        d = FieldWriter(self, dest, debug=self.options.debug)
        self.options.log.debug(
            r'%s: encode descriptor pos=%d', self._fullname, start)
        if self._encoded is not None:
            if self.options.log.isEnabledFor(logging.DEBUG):
                self.options.log.debug(
                    r'%s: using pre-encoded data size=%d', self.classname, len(self._encoded))
                for child in self.children:
                    self.options.log.debug(
                        r'%s: skipping descriptor %s size=%d',
                        self.classname, child._fullname, child.size)
            payload = self._encoded
        else:
            payload = io.BytesIO()
            self.encode_fields(payload)
            self.options.log.debug(
                r'%s: fields produced %d bytes', self._fullname, payload.tell())
            for ch in self.children:
                ch.encode(payload)
            self.options.log.debug(
                r'%s: Total payload size %d bytes', self._fullname, payload.tell())
            payload = payload.getvalue()
        if self.size == 0:
            self.size = len(payload)
        elif self.size != len(payload):
            self.options.log.warning("Descriptor %s should be %d bytes but encoded %d",
                                     self.classname, self.size, len(payload))
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
            self.classname, len(payload), start, dest.tell())

    @abstractmethod
    def encode_fields(self, dest):
        pass

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

    def _to_json(self, exclude):
        exclude = exclude.union({'parent', 'options'})
        return super(Descriptor, self)._to_json(exclude)

    def dump(self, indent=''):
        f = '{}{}: {:d} -> {:d} [header {:d} bytes] [{:d} bytes]'
        print(f.format(indent,
                       self.classname,
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

    @classmethod
    def parse_payload(clz, src, fields, parent, options):
        if fields["size"] > 0:
            fields["data"] = src.read(fields["size"])
        else:
            fields["data"] = None
        return fields

    def encode_fields(self, dest):
        if self.data is not None:
            assert isinstance(self.data, Binary)
            dest.write(self.data.data)

class ESDescriptor(Descriptor):

    @classmethod
    def parse_payload(clz, src, rv, options, **kwargs):
        r = FieldReader(clz.classname, src, rv, debug=options.debug)
        r.read('H', 'es_id')
        b = r.get('B', 'flags')
        rv["stream_dependence_flag"] = (b & 0x80) == 0x80
        url_flag = (b & 0x40) == 0x40
        ocr_stream_flag = (b & 0x20) == 0x20
        rv["stream_priority"] = b & 0x1f
        if rv["stream_dependence_flag"]:
            r.read('H', "depends_on_es_id")
        if url_flag:
            leng = r.get('B', 'url_length')
            r.read(leng, 'url')
        else:
            rv["url"] = None
        if ocr_stream_flag:
            r.read('H', 'ocr_es_id')
        else:
            rv['ocr_es_id'] = None
        return rv

    def encode_fields(self, dest):
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


MP4_DESCRIPTORS[0x03] = ESDescriptor

class DecoderConfigDescriptor(Descriptor):
    @classmethod
    def parse_payload(clz, src, rv, **kwargs):
        r = FieldReader(clz.classname, src, rv)
        r.read('B', "object_type")
        b = r.get('B', "stream_type")
        rv["stream_type"] = (b >> 2)
        rv["unknown_flag"] = (b & 0x01) == 0x01
        rv["upstream"] = (b & 0x02) == 0x02
        r.read('0I', "buffer_size")
        r.read('I', "max_bitrate")
        r.read('I', "avg_bitrate")
        return rv

    def encode_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('B', "object_type")
        b = self.stream_type << 2
        if self.unknown_flag:
            b |= 0x01
        if self.upstream:
            b |= 0x02
        w.write('B', 'stream_type', b)
        w.write('0I', 'buffer_size')
        w.write('I', "max_bitrate")
        w.write('I', "avg_bitrate")


MP4_DESCRIPTORS[0x04] = DecoderConfigDescriptor

class DecoderSpecificInfo(Descriptor):
    SAMPLE_RATES = [96000, 88200, 64000, 48000, 44100, 32000,
                    24000, 22050, 16000, 12000, 11025, 8000, 7350]

    OBJECT_FIELDS = {
        'data': Binary,
    }
    OBJECT_FIELDS.update(Descriptor.OBJECT_FIELDS)

    @classmethod
    def parse_payload(clz, src, rv, parent, **kwargs):
        rv["object_type"] = parent.object_type
        r = BitsFieldReader(clz.classname, src, rv, rv["size"])
        if rv["object_type"] == 0x40:  # Audio ISO/IEC 14496-3 subpart 1
            r.read(5, "audio_object_type")
            r.read(4, "sampling_frequency_index")
            if rv["sampling_frequency_index"] == 0xf:
                r.read(24, "sampling_frequency")
            else:
                rv["sampling_frequency"] = clz.SAMPLE_RATES[rv["sampling_frequency_index"]]
            r.read(4, "channel_configuration")
            r.read(1, "frame_length_flag")
            r.read(1, "depends_on_core_coder")
            if rv["depends_on_core_coder"]:
                r.read(14, "core_coder_delay")
            r.read(1, "extension_flag")
            # if not rv["channel_configuration"]:
            #    rv["channel_configuration"] = clz.parse_config_element(src, parent)
            if rv["audio_object_type"] == 6 or rv["audio_object_type"] == 20:
                r.read(3, "layer_nr")
            if rv["extension_flag"]:
                if rv["audio_object_type"] == 22:
                    r.read(5, "num_sub_frame")
                    r.read(11, "layer_length")
                if rv["audio_object_type"] in [17, 19, 20, 23]:
                    r.read(1, "aac_section_data_resilience_flag")
                    r.read(1, "aac_scalefactor_data_resilience_flag")
                    r.read(1, "aac_spectral_data_resilience_flag")
                r.read(1, "extension_flag_3")
        rv["data"] = None
        if r.bitpos() != (8 * rv["size"]):
            rv["data"] = r.data[r.bytepos():]
        return rv

    def encode_fields(self, dest):
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


MP4_DESCRIPTORS[0x05] = DecoderSpecificInfo

class FullBox(Mp4Atom):
    @classmethod
    def parse(clz, src, parent, options, **kwargs):
        rv = Mp4Atom.parse(src, parent, options=options, **kwargs)
        r = FieldReader(clz.classname, src, rv, debug=options.debug)
        r.read("B", "version")
        f = '\000' + r.get(3, "flags")
        rv["flags"] = struct.unpack('>I', f)[0]
        return rv

    def encode_fields(self, dest, payload=None):
        d = FieldWriter(self, dest)
        d.write('B', 'version')
        d.write(3, 'flags', value=struct.pack('>I', self.flags)[1:])
        if payload is not None:
            d.write(None, 'payload', value=payload)


class BoxWithChildren(Mp4Atom):
    parse_children = True
    include_atom_type = True

    def encode_fields(self, dest):
        pass


class MovieBox(BoxWithChildren):
    include_atom_type = False
    pass


MP4_BOXES['moov'] = MovieBox

class TrackBox(BoxWithChildren):
    include_atom_type = False
    pass


MP4_BOXES['trak'] = TrackBox

for box in ['mdia', 'minf', 'mvex', 'moof', 'schi', 'sinf', 'stbl', 'traf']:
    MP4_BOXES[box] = BoxWithChildren

class SampleEntry(Mp4Atom):
    @classmethod
    def parse(clz, src, parent, options, **kwargs):
        rv = Mp4Atom.parse(src, parent, **kwargs)
        r = FieldReader(clz.classname, src, rv, debug=options.debug)
        r.skip(6)  # reserved
        # src.read(6)  # reserved
        r.read('H', 'data_reference_index')
        # rv["data_reference_index"] = struct.unpack('>H', src.read(2))[0]
        return rv

    def encode_fields(self, dest):
        dest.write('\0' * 6)  # reserved
        dest.write(struct.pack('>H', self.data_reference_index))

class VisualSampleEntry(SampleEntry):
    parse_children = True

    @classmethod
    def parse(clz, src, parent, options, **kwargs):
        rv = SampleEntry.parse(src, parent, options, **kwargs)
        r = FieldReader(clz.classname, src, rv, debug=options.debug)
        r.read('H', "version")
        r.read('H', "revision")
        r.read('I', "vendor")
        r.read('I', "temporal_quality")
        r.read('I', "spatial_quality")
        r.read('H', "width")
        r.read('H', "height")
        r.read('I', "horizresolution")
        rv["horizresolution"] /= 65536.0
        r.read('I', "vertresolution")
        rv["vertresolution"] /= 65536.0
        r.read('I', "entry_data_size")
        r.read('H', "frame_count")
        r.read('S32', "compressorname")
        r.read('H', "bit_depth")
        r.read('H', "colour_table")
        return rv

    def encode_fields(self, dest):
        super(VisualSampleEntry, self).encode_fields(dest)
        dest.write(struct.pack('>H', self.version))
        dest.write(struct.pack('>H', self.revision))
        dest.write(struct.pack('>I', self.vendor))
        dest.write(struct.pack('>I', self.temporal_quality))
        dest.write(struct.pack('>I', self.spatial_quality))
        dest.write(struct.pack('>H', self.width))
        dest.write(struct.pack('>H', self.height))
        dest.write(struct.pack('>I', long(self.horizresolution * 65536.0)))
        dest.write(struct.pack('>I', long(self.vertresolution * 65536.0)))
        dest.write(struct.pack('>I', self.entry_data_size))
        dest.write(struct.pack('>H', self.frame_count))
        c = self.compressorname + '\0' * 32
        dest.write(c[:32])
        dest.write(struct.pack('>H', self.bit_depth))
        dest.write(struct.pack('>H', self.colour_table))

class AVC1SampleEntry(VisualSampleEntry):
    pass


MP4_BOXES['avc1'] = AVC1SampleEntry

class AVC3SampleEntry(VisualSampleEntry):
    pass


MP4_BOXES['avc3'] = AVC3SampleEntry

class EncryptedSampleEntry(VisualSampleEntry):
    pass


MP4_BOXES['encv'] = EncryptedSampleEntry

class AVCConfigurationBox(Mp4Atom):
    OBJECT_FIELDS = {
        'sps': ListOf(Binary),
        'sps_ext': ListOf(Binary),
        'pps': ListOf(Binary),
    }

    @classmethod
    def parse(clz, src, parent, options, **kwargs):
        rv = Mp4Atom.parse(src, parent, options=options, **kwargs)
        r = FieldReader(clz.classname, src, rv, debug=options.debug)
        r.read('B', "configurationVersion")
        r.read('B', "AVCProfileIndication")
        r.read('B', "profile_compatibility")
        r.read('B', "AVCLevelIndication")
        r.read('B', "lengthSizeMinusOne", mask=0x03)
        numOfSequenceParameterSets = r.get('B', "numOfSequenceParameterSets",
                                           mask=0x1F)
        rv["sps"] = []
        for i in range(numOfSequenceParameterSets):
            sequenceParameterSetLength = struct.unpack('>H', src.read(2))[0]
            sequenceParameterSetNALUnit = src.read(sequenceParameterSetLength)
            rv["sps"].append(sequenceParameterSetNALUnit)
        numOfPictureParameterSets = r.get('B', 'numOfPictureParameterSets')
        rv["pps"] = []
        for i in range(numOfPictureParameterSets):
            pictureParameterSetLength = struct.unpack('>H', src.read(2))[0]
            pictureParameterSetNALUnit = src.read(pictureParameterSetLength)
            rv["pps"].append(pictureParameterSetNALUnit)
        end = rv["position"] + rv["size"]
        if clz.is_ext_profile(rv["AVCProfileIndication"]) and (end - src.tell()) > 3:
            r.read('B', 'chroma_format', mask=0x03)
            r.read('B', 'luma_bit_depth', mask=0x03)
            rv["luma_bit_depth"] += 8
            r.read('B', 'chroma_bit_depth', mask=0x03)
            rv["chroma_bit_depth"] += 8
            numOfSequenceParameterSetExtensions = r.get(
                'B', 'numOfSequenceParameterSetExtensions')
            rv["sps_ext"] = []
            for i in range(numOfSequenceParameterSetExtensions):
                length = r.get('H', 'sps_ext_length')
                NALUnit = src.read(length)
                rv["sps_ext"].append(NALUnit)
        return rv

    def encode_fields(self, dest):
        d = FieldWriter(self, dest, debug=self.options.debug)
        d.write('B', 'configurationVersion')
        d.write('B', 'AVCProfileIndication')
        d.write('B', 'profile_compatibility')
        d.write('B', 'AVCLevelIndication')
        d.write('B', 'lengthSizeMinusOne',
                0xFC + (self.lengthSizeMinusOne & 0x03))
        d.write('B', 'sps_count', 0xE0 + (len(self.sps) & 0x1F))
        for sps in self.sps:
            d.write('H', 'sps_size', len(sps))
            d.write(None, 'sps', sps)
        d.write('B', 'pps_count', len(self.pps) & 0x1F)
        for pps in self.pps:
            d.write('H', 'pps_size', len(pps))
            d.write(None, 'pps', pps)
        if AVCConfigurationBox.is_ext_profile(self.AVCProfileIndication) and 'chroma_format' in self._fields:
            d.write('B', 'chroma_format', self.chroma_format + 0xFC)
            d.write('B', 'luma_bit_depth', self.luma_bit_depth - 8 + 0xF8)
            d.write('B', 'chroma_bit_depth', self.chroma_bit_depth - 8 + 0xF8)
            d.write('B', 'sps_ext_count', len(self.sps_ext))
            for s in self.sps_ext:
                d.write('H', 'sps_ext_size', len(s))
                d.write(None, 'sps_ext', s)

    @classmethod
    def is_ext_profile(clz, profile_idc):
        return profile_idc in [100, 110, 122, 244, 44, 83, 86, 118,
                               128, 134, 135, 138, 139]


MP4_BOXES['avcC'] = AVCConfigurationBox

class AudioSampleEntry(SampleEntry):
    parse_children = True

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = SampleEntry.parse(src, parent, **kwargs)
        src.read(8)  # reserved
        rv["channel_count"] = struct.unpack('>H', src.read(2))[0]
        rv["sample_size"] = struct.unpack('>H', src.read(2))[0]
        src.read(4)  # reserved
        rv["sampling_frequency"] = struct.unpack('>H', src.read(2))[0]
        src.read(2)  # reserved
        return rv

    def encode_fields(self, dest):
        super(AudioSampleEntry, self).encode_fields(dest)
        dest.write('\0' * 8)  # reserved
        dest.write(struct.pack('>H', self.channel_count))
        dest.write(struct.pack('>H', self.sample_size))
        dest.write('\0' * 4)  # reserved
        dest.write(struct.pack('>H', self.sampling_frequency))
        dest.write('\0' * 2)  # reserved

class EC3SampleEntry(AudioSampleEntry):
    pass


MP4_BOXES['ec-3'] = EC3SampleEntry

class EC3SubStream(ObjectWithFields):
    DEFAULT_EXCLUDE = {'src'}

    @classmethod
    def parse(clz, r):
        r.read(2, 'fscod')
        r.read(5, 'bsid')
        r.read(5, 'bsmod')
        r.read(3, 'acmod')
        r.kwargs['channel_count'] = EC3SpecificBox.ACMOD_NUM_CHANS[r.kwargs['acmod']]
        r.read(1, 'lfeon')
        r.get(3, 'reserved')
        r.read(4, 'num_dep_sub')
        if r.kwargs["num_dep_sub"] > 0:
            r.read(9, 'chan_loc')
        else:
            r.get(1, 'reserved')

    def encode_fields(self, ba):
        ba.append(bitstring.pack('uint:2, uint:5, uint:5, uint:3, bool',
                                 self.fscod, self.bsid, self.bsmod, self.acmod,
                                 self.lfeon))
        ba.append(bitstring.Bits(uint=0, length=3))  # reserved
        ba.append(bitstring.Bits(uint=self.num_dep_sub, length=4))
        if self.num_dep_sub > 0:
            ba.append(bitstring.Bits(uint=self.chan_loc, length=9))
        else:
            ba.append(bitstring.Bits(uint=0, length=1))  # reserved


# See section C.3.1 of ETSI TS 103 420 V1.2.1
class EC3SpecificBox(Mp4Atom):
    ACMOD_NUM_CHANS = [2, 1, 2, 3, 3, 4, 4, 5]

    OBJECT_FIELDS = {
        "substreams": ListOf(EC3SubStream),
    }
    OBJECT_FIELDS.update(Mp4Atom.OBJECT_FIELDS)

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = Mp4Atom.parse(src, parent, **kwargs)
        r = BitsFieldReader(clz.classname, src, rv, size=None)
        r.read(13, "data_rate")
        num_ind_sub = r.get(3, "num_ind_sub") + 1
        rv["substreams"] = []
        for i in range(num_ind_sub):
            r2 = r.duplicate("EC3SubStream", {})
            EC3SubStream.parse(r2)
            rv["substreams"].append(EC3SubStream(**r2.kwargs))
        if (r.bitpos() + 16) <= r.bitsize:
            r.get(7, 'reserved')
            r.read(1, 'flag_ec3_extension_type_a')
            r.read(8, 'complexity_index_type_a')
        return rv

    def encode_fields(self, dest):
        ba = bitstring.BitArray()
        num_ind_sub = len(self.substreams)
        ba.append(bitstring.pack('uint:13, uint:3', self.data_rate,
                                 num_ind_sub - 1))
        for s in self.substreams:
            s.encode_fields(ba)
        if 'flag_ec3_extension_type_a' in self._fields:
            ba.append(bitstring.pack('uint:7, bool, uint:8', 0,
                                     self.flag_ec3_extension_type_a,
                                     self.complexity_index_type_a))
        dest.write(ba.bytes)


MP4_BOXES['dec3'] = EC3SpecificBox

class OriginalFormatBox(Mp4Atom):
    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = Mp4Atom.parse(src, parent, **kwargs)
        rv["data_format"] = src.read(4)
        return rv

    def encode_fields(self, dest):
        dest.write(self.data_format)


MP4_BOXES['frma'] = OriginalFormatBox

# see table 6.3 of 3GPP TS 26.244 V12.3.0
class MP4AudioSampleEntry(Mp4Atom):
    parse_children = True

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = Mp4Atom.parse(src, parent, **kwargs)
        r = FieldReader(clz.classname, src, rv)
        r.get(6, 'reserved')  # (8)[6] reserved
        r.read('H', "data_reference_index")
        r.get(8 + 4 + 4, 'reserved')  # (8)[6] reserved
        r.read('H', "timescale")
        r.get(2, 'reserved')  # (16) reserved
        return rv

    def encode_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write(6, 'reserved', '')
        w.write('H', 'data_reference_index')
        w.write(8, 'reserved_8', '')
        w.write('H', 'reserved_2', 2)
        w.write('H', 'reserved_2', 16)
        w.write(4, 'reserved_4', '')
        w.write('H', 'timescale')
        w.write(2, 'reserved', '')


MP4_BOXES['mp4a'] = MP4AudioSampleEntry

class EncryptedMP4A(MP4AudioSampleEntry):
    pass


MP4_BOXES['enca'] = EncryptedMP4A

class ESDescriptorBox(FullBox):
    OBJECT_FIELDS = {
        'descriptors': ListOf(Descriptor)
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    def __init__(self, **kwargs):
        super(ESDescriptorBox, self).__init__(**kwargs)
        self.apply_defaults({"descriptors": []})
        for d in self.descriptors:
            d.parent = self
            d.options = self.options

    @classmethod
    def parse(clz, src, parent, options, **kwargs):
        rv = FullBox.parse(src, parent=parent, options=options, **kwargs)
        descriptors = []
        end = rv["position"] + rv["size"]
        while src.tell() < end:
            options.log.debug(
                'ESDescriptorBox: parse descriptor pos=%d end=%d', src.tell(), end)
            d = Descriptor.create(src, parent=parent, options=options)
            descriptors.append(d)
            if src.tell() != (d.position + d.size + d.header_size):
                options.log.warning(
                    "Expected descriptor %s to be %d bytes, but read %d bytes",
                    d.classname, d.size + d.header_size,
                    src.tell() - d.position)
                src.seek(d.position + d.size + d.header_size)
        rv["descriptors"] = descriptors
        return rv

    def descriptor(self, name):
        for d in self.descriptors:
            if type(d).__name__ == name:
                return d
            v = getattr(d, name)
            if v is not None:
                return v
        return None

    def remove_descriptor(self, name):
        for idx, d in enumerate(self._fields['descriptors']):
            if type(d).__name__ == name:
                del self._fields['descriptors'][idx]
                if d.size:
                    self.size -= d.size
                self._invalidate()
                return
        raise AttributeError(name)

    def encode_fields(self, dest):
        super(ESDescriptorBox, self).encode_fields(dest)
        for d in self.descriptors:
            d.encode(dest)


MP4_BOXES['esds'] = ESDescriptorBox

class SampleDescriptionBox(FullBox):
    parse_children = True

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        rv["entry_count"] = struct.unpack('>I', src.read(4))[0]
        return rv

    def encode_fields(self, dest):
        super(SampleDescriptionBox, self).encode_fields(dest)
        dest.write(struct.pack('>I', self.entry_count))


MP4_BOXES['stsd'] = SampleDescriptionBox

class TrackFragmentHeaderBox(FullBox):
    base_data_offset_present = 0x000001
    sample_description_index_present = 0x000002
    default_sample_duration_present = 0x000008
    default_sample_size_present = 0x000010
    default_sample_flags_present = 0x000020
    duration_is_empty = 0x010000
    default_base_is_moof = 0x020000

    def __init__(self, **kwargs):
        super(TrackFragmentHeaderBox, self).__init__(**kwargs)
        # default base offset = first byte of moof
        if self.base_data_offset is None:
            self.base_data_offset = self.find_atom('moof').position

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        rv["base_data_offset"] = None
        rv["sample_description_index"] = 0
        rv["default_sample_duration"] = 0
        rv["default_sample_size"] = 0
        rv["default_sample_flags"] = 0
        r = FieldReader(clz.classname, src, rv)
        r.read('I', 'track_id')
        if rv["flags"] & clz.base_data_offset_present:
            r.read('Q', 'base_data_offset')
        elif rv["flags"] & clz.default_base_is_moof:
            rv["base_data_offset"] = parent.find_atom('moof').position
        if rv["flags"] & clz.sample_description_index_present:
            r.read('I', 'sample_description_index')
        if rv["flags"] & clz.default_sample_duration_present:
            r.read('I', 'default_sample_duration')
        if rv["flags"] & clz.default_sample_size_present:
            r.read('I', 'default_sample_size')
        if rv["flags"] & clz.default_sample_flags_present:
            r.read('I', 'default_sample_flags')
        return rv

    def encode_fields(self, dest):
        super(TrackFragmentHeaderBox, self).encode_fields(dest)
        dest.write(struct.pack('>I', self.track_id))
        if self.flags & self.base_data_offset_present:
            dest.write(struct.pack('>Q', self.base_data_offset))
        if self.flags & self.sample_description_index_present:
            dest.write(struct.pack('>I', self.sample_description_index))
        if self.flags & self.default_sample_duration_present:
            dest.write(struct.pack('>I', self.default_sample_duration))
        if self.flags & self.default_sample_size_present:
            dest.write(struct.pack('>I', self.default_sample_size))
        if self.flags & self.default_sample_flags_present:
            dest.write(struct.pack('>I', self.default_sample_flags))


MP4_BOXES['tfhd'] = TrackFragmentHeaderBox

class TrackHeaderBox(FullBox):
    Track_enabled = 0x000001
    Track_in_movie = 0x000002
    Track_in_preview = 0x000004

    OBJECT_FIELDS = {
        "creation_time": DateTimeField,
        "modification_time": DateTimeField,
        "matrix": ListOf(int),
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        r = FieldReader(clz.classname, src, rv)
        rv["is_enabled"] = (rv["flags"] & clz.Track_enabled) == clz.Track_enabled
        rv["in_movie"] = (rv["flags"] & clz.Track_in_movie) == clz.Track_in_movie
        rv["in_preview"] = (rv["flags"] & clz.Track_in_preview) == clz.Track_in_preview
        if rv["version"] == 1:
            sz = 'Q'
        else:
            sz = 'I'
        r.read(sz, "creation_time")
        r.read(sz, "modification_time")
        r.read('I', "track_id")
        r.skip(4)  # reserved
        r.read(sz, "duration")
        rv["creation_time"] = from_iso_epoch(rv["creation_time"])
        rv["modification_time"] = from_iso_epoch(rv["modification_time"])
        r.get(8, 'reserved')  # 2 x 32 bits reserved
        r.read('H', "layer")
        r.read('H', "alternate_group")
        rv["volume"] = r.get('D8.8', 'volume')  # value is fixed point 8.8
        r.get(2, 'reserved')  # reserved
        rv["matrix"] = []
        for i in range(9):
            rv["matrix"].append(r.get('I', 'matrix'))
        rv["width"] = r.get('D16.16', 'width')  # value is fixed point 16.16
        rv["height"] = r.get('D16.16', 'height')  # value is fixed point 16.16
        return rv

    def encode_fields(self, dest):
        self.flags = 0
        if self.is_enabled:
            self.flags |= self.Track_enabled
        if self.in_movie:
            self.flags |= self.Track_in_movie
        if self.in_preview:
            self.flags |= self.Track_in_preview
        super(TrackHeaderBox, self).encode_fields(dest)
        d = FieldWriter(self, dest)
        if self.version == 1:
            sz = 'Q'
        else:
            sz = 'I'
        d.write(sz, 'creation_time', to_iso_epoch(self.creation_time))
        d.write(sz, 'modification_time', to_iso_epoch(self.modification_time))
        d.write('I', 'track_id')
        d.write(4, 'reserved', '\0' * 4)  # reserved
        d.write(sz, 'duration')
        d.write(8, 'reserved', '\0' * 8)  # reserved
        d.write('H', 'layer')
        d.write('H', 'alternate_group')
        d.write('D8.8', 'volume')  # int(self.volume * 256.0))
        d.write(2, 'reserved', '\0' * 2)  # reserved
        for m in self.matrix:
            d.write('I', 'matrix', m)
        d.write('D16.16', 'width')  # long(self.width * 65536.0))
        d.write('D16.16', 'height')  # long(self.height * 65536.0))


MP4_BOXES['tkhd'] = TrackHeaderBox

class TrackFragmentDecodeTimeBox(FullBox):
    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        if rv["version"] == 1:
            rv["base_media_decode_time"] = struct.unpack('>Q', src.read(8))[0]
        else:
            rv["base_media_decode_time"] = struct.unpack('>I', src.read(4))[0]
        return rv

    def encode_fields(self, dest):
        payload = io.BytesIO()
        if self.base_media_decode_time > long(1 << 32):
            self.version = 1
        else:
            self.version = 0
        if self.version == 1:
            payload.write(struct.pack('>Q', self.base_media_decode_time))
        else:
            payload.write(struct.pack('>I', self.base_media_decode_time))
        return super(TrackFragmentDecodeTimeBox, self).encode_fields(
            dest=dest, payload=payload.getvalue())


MP4_BOXES['tfdt'] = TrackFragmentDecodeTimeBox

class TrackExtendsBox(FullBox):
    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        rv["track_id"] = struct.unpack('>I', src.read(4))[0]
        rv["default_sample_description_index"] = struct.unpack('>I', src.read(4))[0]
        rv["default_sample_duration"] = struct.unpack('>I', src.read(4))[0]
        rv["default_sample_size"] = struct.unpack('>I', src.read(4))[0]
        rv["default_sample_flags"] = struct.unpack('>I', src.read(4))[0]
        return rv

    def encode_fields(self, dest):
        super(TrackExtendsBox, self).encode_fields(dest)
        dest.write(struct.pack('>I', self.track_id))
        dest.write(struct.pack('>I', self.default_sample_description_index))
        dest.write(struct.pack('>I', self.default_sample_duration))
        dest.write(struct.pack('>I', self.default_sample_size))
        dest.write(struct.pack('>I', self.default_sample_flags))


MP4_BOXES['trex'] = TrackExtendsBox

class MediaHeaderBox(FullBox):
    OBJECT_FIELDS = {
        "creation_time": DateTimeField,
        "modification_time": DateTimeField,
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        if rv["version"] == 1:
            rv["creation_time"] = struct.unpack('>Q', src.read(8))[0]
            rv["modification_time"] = struct.unpack('>Q', src.read(8))[0]
            rv["timescale"] = struct.unpack('>I', src.read(4))[0]
            rv["duration"] = struct.unpack('>Q', src.read(8))[0]
        else:
            rv["creation_time"] = struct.unpack('>I', src.read(4))[0]
            rv["modification_time"] = struct.unpack('>I', src.read(4))[0]
            rv["timescale"] = struct.unpack('>I', src.read(4))[0]
            rv["duration"] = struct.unpack('>I', src.read(4))[0]
        rv["creation_time"] = from_iso_epoch(rv["creation_time"])
        rv["modification_time"] = from_iso_epoch(rv["modification_time"])
        tmp = struct.unpack('>H', src.read(2))[0]
        rv["language"] = ''.join([
            chr(0x60 + ((tmp >> 10) & 0x1F)),
            chr(0x60 + ((tmp >> 5) & 0x1F)),
            chr(0x60 + (tmp & 0x1F))
        ])
        src.read(2)  # unsigned int(16) pre_defined = 0
        return rv

    def encode_fields(self, dest):
        super(MediaHeaderBox, self).encode_fields(dest)
        if self.version == 1:
            sz = '>Q'
        else:
            sz = '>I'
        dest.write(struct.pack(sz, to_iso_epoch(self.creation_time)))
        dest.write(struct.pack(sz, to_iso_epoch(self.modification_time)))
        dest.write(struct.pack('>I', self.timescale))
        dest.write(struct.pack(sz, self.duration))
        chars = map(lambda c: ord(c) - 0x60, list(self.language))
        lang = (chars[0] << 10) + (chars[1] << 5) + chars[2]
        dest.write(struct.pack('>H', lang))
        dest.write(struct.pack('>H', 0))  # pre_defined


MP4_BOXES['mdhd'] = MediaHeaderBox

class MovieFragmentHeaderBox(FullBox):
    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        rv["sequence_number"] = struct.unpack('>I', src.read(4))[0]
        return rv

    def encode_fields(self, dest):
        super(MovieFragmentHeaderBox, self).encode_fields(dest)
        dest.write(struct.pack('>I', self.sequence_number))


MP4_BOXES['mfhd'] = MovieFragmentHeaderBox

class HandlerBox(FullBox):
    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        src.read(4)  # unsigned int(32) pre_defined = 0
        rv["handler_type"] = src.read(4)
        src.read(12)  # const unsigned int(32)[3] reserved = 0;
        name_len = rv["position"] + rv["size"] - src.tell()
        rv["name"] = src.read(name_len)
        if '\0' in rv["name"]:
            rv["name"] = rv["name"].split('\0')[0]
        return rv

    def encode_fields(self, dest):
        super(HandlerBox, self).encode_fields(dest)
        dest.write('\0' * 4)  # pre_defined = 0
        dest.write(self.handler_type)
        dest.write('\0' * 12)  # reserved = 0
        dest.write(self.name)
        dest.write(chr(0))  # string is null terminated


MP4_BOXES['hdlr'] = HandlerBox

class MovieExtendsHeaderBox(FullBox):
    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        if rv["version"] == 1:
            rv["fragment_duration"] = struct.unpack('>Q', src.read(8))[0]
        else:
            rv["fragment_duration"] = struct.unpack('>I', src.read(4))[0]
        return rv

    def encode_fields(self, dest):
        super(MovieExtendsHeaderBox, self).encode_fields(dest)
        if self.version == 1:
            dest.write(struct.pack('>Q', self.fragment_duration))
        else:
            dest.write(struct.pack('>I', self.fragment_duration))


MP4_BOXES['mehd'] = MovieExtendsHeaderBox

class SampleAuxiliaryInformationSizesBox(FullBox):
    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        if rv["flags"] & 1:
            rv["aux_info_type"] = clz.check_info_type(
                struct.unpack('>I', src.read(4))[0])
            rv["aux_info_type_parameter"] = struct.unpack('>I', src.read(4))[0]
        rv["default_sample_info_size"] = struct.unpack('B', src.read(1))[0]
        rv["sample_info_sizes"] = []
        sample_count = struct.unpack('>I', src.read(4))[0]
        if rv["default_sample_info_size"] == 0:
            for i in range(sample_count):
                rv["sample_info_sizes"].append(
                    struct.unpack('B', src.read(1))[0])
        return rv

    @classmethod
    def check_info_type(clz, info_type):
        s = ''.join([
            chr((info_type >> 24) & 0xFF),
            chr((info_type >> 16) & 0xFF),
            chr((info_type >> 8) & 0xFF),
            chr((info_type) & 0xFF)
        ])
        if s.isalpha():
            return s
        return info_type

    def encode_fields(self, dest):
        payload = io.BytesIO()
        if self.flags & 1:
            if isinstance(self.aux_info_type, basestring):
                payload.write(self.aux_info_type)
            else:
                payload.write(struct.pack('>I', self.aux_info_type))
            payload.write(struct.pack('>I', self.aux_info_type_parameter))
        payload.write(struct.pack('B', self.default_sample_info_size))
        payload.write(struct.pack('>I', len(self.sample_info_sizes)))
        if self.default_sample_info_size == 0:
            for sz in self.sample_info_sizes:
                payload.write(struct.pack('B', sz))
        super(SampleAuxiliaryInformationSizesBox, self).encode_fields(
            dest=dest, payload=payload.getvalue())

    def _to_json(self, exclude):
        exclude.append('aux_info_type')
        fields = super(FullBox, self)._to_json(exclude)
        if "aux_info_type" in self._fields:
            if isinstance(self.aux_info_type, basestring):
                fields['aux_info_type'] = '"%s"' % self.aux_info_type
            else:
                fields['aux_info_type'] = '0x%x' % self.aux_info_type
        return fields


MP4_BOXES['saiz'] = SampleAuxiliaryInformationSizesBox

class CencSubSample(ObjectWithFields):
    REQUIRED_FIELDS = {
        'clear': int,
        'encrypted': int,
    }

    @classmethod
    def parse(clz, src):
        rv = {
            'clear': struct.unpack('>H', src.read(2))[0],
            'encrypted': struct.unpack('>I', src.read(4))[0],
        }
        return rv

    def encode_fields(self, dest):
        dest.write(struct.pack('>H', self.clear))
        dest.write(struct.pack('>I', self.encrypted))


class CencSampleAuxiliaryData(ObjectWithFields):
    OBJECT_FIELDS = {
        "initialization_vector": Binary,
        "subsamples": ListOf(CencSubSample),
    }

    @classmethod
    def parse(clz, src, size, iv_size, flags, parent):
        if iv_size is None:
            if (flags & 0x02) == 0x00:
                iv_size = size
            else:
                raise ValueError("Unable to determine IV size")
        rv = {
            "iv_size": iv_size,
        }
        rv["initialization_vector"] = src.read(iv_size)
        rv["subsamples"] = []
        if (flags & 0x02) == 0x02 and size >= (iv_size + 2):
            subsample_count = struct.unpack('>H', src.read(2))[0]
            if size < (subsample_count * 6):
                raise ValueError('Invalid subsample_count %d' % subsample_count)
            for i in range(subsample_count):
                rv["subsamples"].append(CencSubSample.parse(src))
        return rv

    def encode_fields(self, dest, parent):
        assert isinstance(self.initialization_vector, Binary)
        assert len(self.initialization_vector) == self.iv_size
        dest.write(self.initialization_vector.data)
        if (parent.flags & 0x02) == 0x02:
            dest.write(struct.pack('>H', len(self.subsamples)))
            for samp in self.subsamples:
                samp.encode_fields(dest)


class CencSampleEncryptionBox(FullBox):
    OBJECT_FIELDS = {
        "kid": Binary,
        "samples": ListOf(CencSampleAuxiliaryData),
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        if rv["flags"] & 0x01:
            f = '\000' + src.read(3)
            rv["algorithm_id"] = struct.unpack('>I', f)[0]
            rv["iv_size"] = struct.unpack('B', src.read(1))[0]
            if rv["iv_size"] == 0:
                rv["iv_size"] = 8
            rv["kid"] = src.read(16)
        else:
            try:
                moov = parent.find_atom("moov")
                tenc = moov.find_child("tenc")
                rv["iv_size"] = tenc.iv_size
            except AttributeError:
                rv["iv_size"] = kwargs["options"].iv_size
        num_entries = struct.unpack('>I', src.read(4))[0]
        rv["subsample_count"] = num_entries
        rv["samples"] = []
        saiz = parent.saiz
        for i in range(num_entries):
            size = saiz.sample_info_sizes[i] if saiz.sample_info_sizes else saiz.default_sample_info_size
            if size:
                s = CencSampleAuxiliaryData.parse(
                    src, size, rv["iv_size"], rv["flags"], parent)
                rv["samples"].append(s)
        return rv

    def encode_fields(self, dest):
        if len(self.samples) > 0:
            self.flags |= 0x02
        payload = io.BytesIO()
        if self.flags & 0x01:
            payload.write(struct.pack('>I', self.algorithm_id))
            payload.write(struct.pack('B', self.iv_size))
            payload.write(self.kid)
        payload.write(struct.pack('>I', len(self.samples)))
        for s in self.samples:
            s.encode_fields(payload, self)
        return super(CencSampleEncryptionBox, self).encode_fields(
            dest=dest, payload=payload.getvalue())


MP4_BOXES["senc"] = CencSampleEncryptionBox

class SampleAuxiliaryInformationOffsetsBox(FullBox):
    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        if rv["flags"] & 0x01:
            rv["aux_info_type"] = clz.check_info_type(
                struct.unpack('>I', src.read(4))[0])
            rv["aux_info_type_parameter"] = struct.unpack('>I', src.read(4))[0]
        entry_count = struct.unpack('>I', src.read(4))[0]
        rv["offsets"] = []
        for i in range(entry_count):
            if rv["version"] == 0:
                o = struct.unpack('>I', src.read(4))[0]
            else:
                o = struct.unpack('>Q', src.read(8))[0]
            rv["offsets"].append(o)
        return rv

    def encode_fields(self, dest):
        payload = io.BytesIO()
        if self.flags & 0x01:
            if isinstance(self.aux_info_type, basestring):
                payload.write(self.aux_info_type)
            else:
                payload.write(struct.pack('>I', self.aux_info_type))
            payload.write(struct.pack('>I', self.aux_info_type_parameter))
        payload.write(struct.pack('>I', len(self.offsets)))
        for off in self.offsets:
            if self.version == 0:
                payload.write(struct.pack('>I', off))
            else:
                payload.write(struct.pack('>Q', off))
        super(SampleAuxiliaryInformationOffsetsBox, self).encode_fields(
            dest=dest, payload=payload.getvalue())

    def _to_json(self, exclude):
        exclude.add('aux_info_type')
        fields = super(FullBox, self)._to_json(exclude)
        if "aux_info_type" in self._fields:
            if isinstance(self.aux_info_type, basestring):
                fields['aux_info_type'] = '"%s"' % self.aux_info_type
            else:
                fields['aux_info_type'] = '0x%x' % self.aux_info_type
        return fields


SampleAuxiliaryInformationOffsetsBox.check_info_type = SampleAuxiliaryInformationSizesBox.check_info_type

MP4_BOXES['saio'] = SampleAuxiliaryInformationOffsetsBox

class TrackSample(ObjectWithFields):
    REQUIRED_FIELDS = {
        'index': int,
        'offset': int,
    }

    @classmethod
    def parse(clz, src, index, offset, trun, tfhd):
        rv = {
            'index': index,
            'offset': offset,
            'duration': None
        }
        flags = trun["flags"]
        if flags & TrackFragmentRunBox.sample_duration_present:
            rv['duration'] = struct.unpack('>I', src.read(4))[0]
        elif tfhd.default_sample_duration:
            rv['duration'] = tfhd.default_sample_duration
        if flags & TrackFragmentRunBox.sample_size_present:
            rv['size'] = struct.unpack('>I', src.read(4))[0]
        else:
            rv['size'] = tfhd.default_sample_size
        if flags & TrackFragmentRunBox.sample_flags_present:
            rv['flags'] = struct.unpack('>I', src.read(4))[0]
        else:
            rv['flags'] = tfhd.default_sample_flags
        if index == 0 and (flags & TrackFragmentRunBox.first_sample_flags_present):
            rv['flags'] = trun["first_sample_flags"]
        if flags & TrackFragmentRunBox.sample_composition_time_offsets_present:
            rv["composition_time_offset"] = struct.unpack('>i', src.read(4))[0]
        return rv

    def encode_fields(self, dest):
        flags = self.parent.flags
        d = FieldWriter(self, dest)
        if flags & TrackFragmentRunBox.sample_duration_present:
            d.write('I', 'duration')
        if flags & TrackFragmentRunBox.sample_size_present:
            d.write('I', 'size')
        if flags & TrackFragmentRunBox.sample_flags_present:
            d.write('I', 'flags')
        if flags & TrackFragmentRunBox.sample_composition_time_offsets_present:
            d.write('I', 'composition_time_offset')


class TrackFragmentRunBox(FullBox):
    data_offset_present = 0x000001
    first_sample_flags_present = 0x000004
    sample_duration_present = 0x000100  # each sample has its own duration?
    sample_size_present = 0x000200  # each sample has its own size, otherwise the default is used.
    sample_flags_present = 0x000400  # each sample has its own flags, otherwise the default is used.
    sample_composition_time_offsets_present = 0x000800

    OBJECT_FIELDS = {
        'samples': ListOf(TrackSample),
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    def __init__(self, **kwargs):
        super(TrackFragmentRunBox, self).__init__(**kwargs)
        for s in self.samples:
            object.__setattr__(s, 'parent', self)

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        tfhd = parent.tfhd
        sample_count = struct.unpack('>I', src.read(4))[0]
        rv["sample_count"] = sample_count
        if rv["flags"] & clz.data_offset_present:
            rv["data_offset"] = struct.unpack('>i', src.read(4))[0]
        else:
            rv["data_offset"] = 0
        if rv["flags"] & clz.first_sample_flags_present:
            rv["first_sample_flags"] = struct.unpack('>I', src.read(4))[0]
        else:
            rv["first_sample_flags"] = 0
        # print('Trun: count=%d offset=%d flags=%x'%(rv["sample_count,rv["data_offset,rv["first_sample_flags))
        rv["samples"] = []
        offset = rv["data_offset"]
        for i in range(sample_count):
            ts = TrackSample.parse(src, i, offset, rv, tfhd)
            ts = TrackSample(**ts)
            rv["samples"].append(ts)
            offset += ts.size
        return rv

    def parse_samples(self, src, nal_length_field_length):
        tfhd = self.parent.tfhd
        for sample in self.samples:
            pos = sample.offset + tfhd.base_data_offset
            end = pos + sample.size
            sample.nals = []
            while pos < end:
                src.seek(pos)
                nal = Nal(src, nal_length_field_length)
                pos += nal.size + nal_length_field_length
                sample.nals.append(nal)

    def encode_fields(self, dest):
        super(TrackFragmentRunBox, self).encode_fields(dest)
        dest.write(struct.pack('>I', self.sample_count))
        if self.flags & self.data_offset_present:
            dest.write(struct.pack('>i', self.data_offset))
        if self.flags & self.first_sample_flags_present:
            dest.write(struct.pack('>I', self.first_sample_flags))
        for sample in self.samples:
            sample.encode_fields(dest)


MP4_BOXES['trun'] = TrackFragmentRunBox

class TrackEncryptionBox(FullBox):
    OBJECT_FIELDS = {
        "default_kid": Binary,
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        r = FieldReader(clz.classname, src, rv)
        r.read('0I', "is_encrypted")
        r.read('B', "iv_size")
        r.read(16, "default_kid")
        return rv

    def encode_fields(self, dest):
        super(TrackEncryptionBox, self).encode_fields(dest)
        w = FieldWriter(self, dest)
        w.write('0I', "is_encrypted")
        w.write('B', "iv_size")
        w.write(16, "default_kid")


MP4_BOXES['tenc'] = TrackEncryptionBox

class ContentProtectionSpecificBox(FullBox):
    OBJECT_FIELDS = {
        "data": Binary,
        "key_ids": ListOf(Binary),
        "system_id": Binary,
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    def __init__(self, **kwargs):
        super(ContentProtectionSpecificBox, self).__init__(**kwargs)
        self.system_id = self._fixup_binary_field(self.system_id)
        kids = []
        for kid in self.key_ids:
            kids.append(self._fixup_binary_field(kid))
        self.key_ids = kids
        if self.data and not isinstance(self.data, Binary):
            self.data = Binary(self.data, encoding=Binary.BASE64)

    @staticmethod
    def _fixup_binary_field(value):
        if value is None:
            return None
        if isinstance(value, Binary):
            return value
        if len(value) != 16:
            if re.match(r'^(0x)?[0-9a-f-]+$', value, re.IGNORECASE):
                if value.startswith('0x'):
                    value = value[2:]
                value = value.replace('-', '').decode('hex')
        if len(value) != 16:
            raise ValueError(r"Invalid length: {0}".format(len(value)))
        return Binary(value, encoding=Binary.HEX)

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        r = FieldReader(clz.classname, src, rv)
        r.read(16, "system_id")
        rv["key_ids"] = []
        if rv["version"] > 0:
            kid_count = r.get('I', 'kid_count')
            for i in range(kid_count):
                rv["key_ids"].append(r.read(16, 'kid'))
        data_size = r.get('I', 'data_size')
        if data_size > 0:
            r.read(data_size, "data")
        else:
            rv["data"] = None
        return rv

    def encode_fields(self, dest):
        super(ContentProtectionSpecificBox, self).encode_fields(dest)
        w = FieldWriter(self, dest)
        w.write(16, 'system_id')
        if self.version > 0:
            w.write('I', 'num_keys', len(self.key_ids))
            for kid in self.key_ids:
                w.write(16, 'kid', kid)
        if self.data is None:
            w.write('I', 'data_len', 0)
        else:
            w.write('I', 'data_len', len(self.data))
            w.write(None, 'data')


MP4_BOXES['pssh'] = ContentProtectionSpecificBox

class SegmentReference(ObjectWithFields):
    def __init__(self, **kwargs):
        for key, value in kwargs.iteritems():
            assert "src" != key
            if key not in self.__dict__:
                setattr(self, key, value)

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = {}
        r = BitsFieldReader(clz.classname, src, rv, size=12)
        r.read(1, 'reference_type')
        r.read(31, 'referenced_size')
        r.read(32, 'subsegment_duration')
        r.read(1, 'starts_with_SAP')
        r.read(3, 'SAP_type')
        r.read(28, 'SAP_delta_time')
        return rv

    def _to_json(self, exclude):
        fields = {
            '_type': self.classname
        }
        exclude.add('parent')
        for k, v in self.__dict__.iteritems():
            if k not in exclude:
                fields[k] = v
        return fields

    def encode_fields(self, dest):
        w = FieldWriter(self, dest)
        w.writebits(1, 'reference_type')
        w.writebits(31, 'referenced_size')
        w.writebits(32, 'subsegment_duration')
        w.writebits(1, 'starts_with_SAP')
        w.writebits(3, 'SAP_type')
        w.writebits(28, 'SAP_delta_time')
        w.done()


class SegmentIndexBox(FullBox):
    OBJECT_FIELDS = {
        'references': ListOf(SegmentReference),
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        r = FieldReader(clz.classname, src, rv)
        r.read('I', 'reference_id')
        r.read('I', 'timescale')
        sz = 'I' if rv['version'] == 0 else 'Q'
        r.read(sz, 'earliest_presentation_time')
        r.read(sz, 'first_offset')
        r.skip(2)  # reserved
        ref_count = r.get('H', 'reference_count')
        rv["references"] = []
        for i in range(ref_count):
            rv["references"].append(
                SegmentReference(**SegmentReference.parse(src, parent)))
        return rv

    def encode_fields(self, dest):
        super(SegmentIndexBox, self).encode_fields(dest)
        w = FieldWriter(self, dest)
        w.write('I', 'reference_id')
        w.write('I', 'timescale')
        sz = 'I' if self.version == 0 else 'Q'
        w.write(sz, 'earliest_presentation_time')
        w.write(sz, 'first_offset')
        w.write('H', 'reserved', 0)
        w.write('H', 'reference_count', len(self.references))
        for ref in self.references:
            ref.encode_fields(dest)


MP4_BOXES['sidx'] = SegmentIndexBox

class EventMessageBox(FullBox):
    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        r = FieldReader(clz.classname, src, rv)
        if rv['version'] == 0:
            r.read('S0', 'scheme_id_uri')
            r.read('S0', 'value')
            r.read('I', 'timescale')
            r.read('I', 'presentation_time_delta')
            r.read('I', 'event_duration')
            r.read('I', 'event_id')
        elif rv['version'] == 1:
            r.read('I', 'timescale')
            r.read('Q', 'presentation_time')
            r.read('I', 'event_duration')
            r.read('I', 'event_id')
            r.read('S0', 'scheme_id_uri')
            r.read('S0', 'value')
        rv["data"] = None
        end = rv["position"] + rv["size"]
        if src.tell() < end:
            r.read(end - src.tell(), 'data')
        return rv

    def encode_fields(self, dest):
        super(EventMessageBox, self).encode_fields(dest)
        d = FieldWriter(self, dest)
        if self.version == 0:
            d.write('S0', 'scheme_id_uri')
            d.write('S0', 'value')
            d.write('I', 'timescale')
            d.write('I', 'presentation_time_delta')
            d.write('I', 'event_duration')
            d.write('I', 'event_id')
        elif self.version == 1:
            d.write('I', 'timescale')
            d.write('Q', 'presentation_time')
            d.write('I', 'event_duration')
            d.write('I', 'event_id')
            d.write('S0', 'scheme_id_uri')
            d.write('S0', 'value')
        if self.data is not None:
            d.write(len(self.data), 'data')


MP4_BOXES['emsg'] = EventMessageBox

class IsoParser(object):
    @staticmethod
    def walk_atoms(filename, atom=None, options=None):
        atoms = None
        src = None
        try:
            if options is not None:
                options.log.debug('Parse %s', filename)
            if isinstance(filename, basestring):
                src = io.open(filename, mode="rb", buffering=16384)
            else:
                src = filename
            atoms = Mp4Atom.create(src, options=options)
        finally:
            if src and isinstance(filename, (str, unicode)):
                src.close()
        return atoms

    @staticmethod
    def show_atom(atom_types, as_json, atom):
        if atom.atom_type in atom_types:
            if as_json:
                print(json.dumps(atom.toJSON(pure=True),
                                 sort_keys=True, indent=2))
            else:
                print(atom)
        else:
            for child in atom.children:
                IsoParser.show_atom(atom_types, as_json, child)

    @classmethod
    def main(cls):
        logging.basicConfig()
        ap = argparse.ArgumentParser(description='MP4 parser')
        ap.add_argument('-d', '--debug', action="store_true")
        ap.add_argument('--json', action="store_true")
        ap.add_argument(
            '-s', '--show', help='Show contents of specified atom')
        ap.add_argument(
            '-t', '--tree', action="store_true", help='Show atom tree')
        ap.add_argument(
            '--ivsize', type=int, help='IV size (in bits or bytes)')
        ap.add_argument(
            'mp4file', help='Filename of MP4 file', nargs='+', default=None)
        args = ap.parse_args()
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
        options = Options()
        if args.ivsize:
            if args.ivsize > 16:
                # user has provided IV size in bits
                options.iv_size = args.ivsize // 8
            else:
                options.iv_size = args.ivsize
        for filename in args.mp4file:
            atoms = IsoParser.walk_atoms(filename, options=options)
            for atom in atoms:
                if args.tree:
                    atom.dump()
                if args.show:
                    IsoParser.show_atom(args.show, args.json, atom)


if __name__ == "__main__":
    IsoParser.main()
