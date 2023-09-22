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

from abc import abstractmethod
import argparse
import binascii
import copy
from dataclasses import dataclass, field
import io
import json
import logging
import os
import re
import struct
import sys
from typing import Optional

try:
    import bitstring
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
    import bitstring

from dashlive.utils.fio import FieldReader, BitsFieldReader, FieldWriter, BitsFieldWriter
from dashlive.utils.binary import Binary, HexBinary
from dashlive.utils.date_time import DateTimeField, from_iso_epoch, to_iso_epoch
from dashlive.utils.object_with_fields import ObjectWithFields
from dashlive.utils.list_of import ListOf
from .nal import Nal

@dataclass(slots=True, kw_only=True)
class Options:
    cache_encoded: bool = False
    debug: bool = False
    iv_size: int | None = None
    strict: bool = False
    bug_compatibility: str | set | None = None
    log: logging = field(init=False)

    def __post_init__(self):
        self.log = logging.getLogger('mp4')

    def has_bug(self, name):
        if self.bug_compatibility is None:
            return False
        if isinstance(self.bug_compatibility, str):
            self.bug_compatibility = {
                s.strip() for s in self.bug_compatibility.split(',')}
        return name in self.bug_compatibility


def fourcc(box_name: str):
    def func(cls):
        fourcc.BOXES[box_name] = cls
        fourcc.BOX_TYPES[cls.__name__] = cls
        return cls
    return func


fourcc.BOXES = {}  # map from fourcc code to Mp4Atom class
fourcc.BOX_TYPES = {}

def mp4descriptor(tag: int):
    def func(cls: "Descriptor") -> "Descriptor":
        mp4descriptor.DESCRIPTORS[tag] = cls
        return cls
    return func


mp4descriptor.DESCRIPTORS: dict[int, "Descriptor"] = {}  # map from descriptor tag to class

class Mp4Atom(ObjectWithFields):
    parse_children = False
    include_atom_type = False

    OBJECT_FIELDS = {
        'children': ListOf(ObjectWithFields),
        'options': Options,
        'parent': ObjectWithFields,
    }
    DEFAULT_EXCLUDE = {'options', 'parent'}

    # list of box names required for parsing
    REQUIRED_PEERS = None

    MODULE_PREFIX = 'dashlive.mpeg.mp4.'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        children_default = [] if self.parse_children else None
        self.apply_defaults({
            '_encoded': None,
            'children': children_default,
            'options': Options(),
            'parent': None,
            'size': 0,
        })
        try:
            atom_type = kwargs["atom_type"]
        except KeyError:
            # TODO: try using BOX_TYPES dictionary
            atom_type = None
            for k, v in fourcc.BOXES.items():
                if v == type(self):
                    atom_type = k
                    break
        if atom_type is None and self.DEFAULT_VALUES is not None:
            atom_type = self.DEFAULT_VALUES.get('atom_type')
        if atom_type is None:
            raise KeyError(kwargs.get("atom_type", 'Missing atom_type'))
        self._fields.add('atom_type')
        if not isinstance(atom_type, str):
            atom_type = str(atom_type, 'ascii')
        self.atom_type = atom_type
        if self.parent:
            self._fullname = fr'{self.parent._fullname}.{self.atom_type}'
        else:
            self._fullname = self.atom_type
        if self.children:
            for ch in self.children:
                ch.parent = self

    def __getattr__(self, name: str) -> "Mp4Atom":
        if name in self._fields:
            # __getattribute__ should have responded before __getattr__ called
            raise AttributeError(name)
        if not self.children:
            raise AttributeError(name)
        for c in self.children:
            if c.atom_type == name:
                return c
            if isinstance(c.atom_type, bytes):
                print('c.atom_type', c.atom_type)
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

    def __delattr__(self, name: str) -> None:
        if name in self._fields:
            raise AttributeError(f'Unable to delete field {name} ')
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
        return super()._field_repr(exclude)

    def _int_field_repr(self, fields, names):
        for name in names:
            fields.append('%s=%d' % (name, self.__getattribute__(name)))
        return fields

    def find_atom(self, atom_type: bytes | str,
                  check_parent: bool = True) -> Optional["Mp4Atom"]:
        if isinstance(atom_type, bytes):
            atom_type = str(atom_type, 'ascii')
        if self.atom_type == atom_type:
            return self
        if self.children is not None:
            for ch in self.children:
                if ch.atom_type == atom_type:
                    return ch
        if check_parent and self.parent:
            return self.parent.find_atom(atom_type, True)
        raise AttributeError(atom_type)

    def find_child(self, atom_type: str | bytes) -> Optional["Mp4Atom"]:
        if self.children is None:
            return None
        if isinstance(atom_type, bytes):
            atom_type = str(atom_type, 'ascii')
        for child in self.children:
            if child.atom_type == atom_type:
                return child
            child = child.find_child(atom_type)
            if child:
                return child
        return None

    def index(self, atom_type: str | bytes) -> "Mp4Atom":
        if isinstance(atom_type, bytes):
            atom_type = str(atom_type, 'ascii')
        for idx, c in enumerate(self.children):
            if c.atom_type == atom_type:
                return idx
        raise ValueError(atom_type)

    def append_child(self, child: "Mp4Atom") -> None:
        self.options.log.debug(
            '%s: append_child "%s"', self._fullname, child.atom_type)
        if self.children is None:
            self.children = [child]
        else:
            self.children.append(child)
        if child.size:
            self.size += child.size
        else:
            self.size = 0
        self._invalidate()

    def insert_child(self, index: int, child: "Mp4Atom") -> None:
        self.children.insert(index, child)
        if child.size:
            self.size += child.size
        self._invalidate()

    def remove_child(self, idx: int) -> None:
        child = self.children[idx]
        del self.children[idx]
        if child.size:
            self.size += child.size
        else:
            self.size = 0
        self._invalidate()

    @classmethod
    def load(cls, src, parent=None, options=None):
        """
        Parse the given source to create MP4 atoms.
        :src: a readable (file) source
        :parent: the parent MP4Atom
        :options: the mp4.Options to use, or a dictionary of option values
        """
        assert src is not None
        if options is None:
            options = Options()
        elif isinstance(options, dict):
            options = Options(**options)
        if parent is not None:
            cursor = parent.payload_start
            end = parent.position + parent.size
            prefix = fr'{parent._fullname}: '
        else:
            parent = Wrapper(position=src.tell())
            end = None
            cursor = 0
            prefix = ''
        if options.iv_size and options.iv_size > 16:
            # assume user has provided IV size in bits rather than bytes
            options.iv_size = options.iv_size // 8
            assert options.iv_size in {8, 16}
        rv = parent.children
        if end is None:
            options.log.debug('%sLoad start=%d end=None', prefix, cursor)
        else:
            options.log.debug('%sLoad start=%d end=%d (%d)', prefix,
                              cursor, end, end - cursor)
        deferred_boxes = []
        while end is None or cursor < end:
            assert cursor is not None
            if src.tell() != cursor:
                # options.log.debug('Move cursor from %d to %d', src.tell(), cursor)
                src.seek(cursor)
            hdr = Mp4Atom.parse(src, parent, options=options)
            if hdr is None:
                break
            try:
                Box = fourcc.BOXES[hdr['atom_type']]
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
            if Box.REQUIRED_PEERS is not None:
                required = set(Box.REQUIRED_PEERS)
                for atom_name in Box.REQUIRED_PEERS:
                    if parent.find_child(atom_name) is not None:
                        required.remove(atom_name)
                if required:
                    options.log.debug(
                        'Defer parsing of "%s" as %s needs to be parsed',
                        hdr['atom_type'], list(required))
                    deferred_boxes.append(dict(Box=Box, initial_data=hdr,
                                               index=len(rv)))
                    cursor += hdr['size']
                    continue
            kwargs = Box.parse(src, parent, options=options, initial_data=hdr)
            kwargs['parent'] = parent
            kwargs['options'] = options
            try:
                atom = Box(**kwargs)
            except TypeError:
                print(kwargs)
                raise
            atom.payload_start = src.tell()
            rv.append(atom)
            if atom.parse_children:
                # options.log.debug('Parse %s children', hdr['atom_type'])
                Mp4Atom.load(src, atom, options)
            else:
                atom._encoded = encoded
            if (src.tell() - atom.position) != atom.size:
                msg = r'{}: expected "{}" to contain {:d} bytes but parsed {:d} bytes'.format(
                    prefix, atom.atom_type, atom.size, src.tell() - atom.position)
                options.log.warning(msg)
                if options.strict:
                    raise ValueError(msg)
            cursor += atom.size
        if not deferred_boxes:
            return rv
        cur_pos = src.tell()
        for item in deferred_boxes:
            options.log.debug('Parsing deferred box: "%s"',
                              item['initial_data']['atom_type'])
            hdr = item['initial_data']
            Box = item['Box']
            src.seek(hdr['position'] + hdr['header_size'])
            kwargs = Box.parse(
                src, parent, options=options, initial_data=hdr)
            kwargs['parent'] = parent
            kwargs['options'] = options
            new_atom = Box(**kwargs)
            new_atom.payload_start = src.tell()
            if atom.parse_children:
                options.log.debug('Parse %s children', new_atom.atom_type)
                Mp4Atom.load(src, new_atom, options)
            options.log.debug('finished parsing of deferred "%s"',
                              new_atom.atom_type)
            rv.insert(item['index'], new_atom)
        src.seek(cur_pos)
        return rv

    @classmethod
    def fromJSON(cls, src, parent=None, options=None):
        assert src is not None
        if options is None:
            options = Options()
        elif isinstance(options, dict):
            options = Options(**options)
        if isinstance(src, list):
            return [cls.fromJSON(atom) for atom in src]

        if '_type' in src:
            name = src['_type']
            if name.startswith(cls.MODULE_PREFIX):
                name = name[len(cls.MODULE_PREFIX):]
            Box = fourcc.BOX_TYPES[name]
        elif 'atom_type' in src:
            Box = fourcc.BOXES[src['atom_type']]
        else:
            Box = UnknownBox
        src['parent'] = parent
        src['options'] = options
        if 'children' not in src:
            return Box(**src)

        children = src['children']
        if children is not None:
            src['children'] = []
        rv = Box(**src)
        if children is None:
            return rv
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
        if atom_type == b'uuid':
            uuid = str(binascii.b2a_hex(src.read(16)), 'ascii')
            atom_type = f'UUID({uuid})'
        else:
            atom_type = str(atom_type, 'ascii')
        return {
            "atom_type": atom_type,
            "position": position,
            "size": size,
            "header_size": src.tell() - position,
        }

    def encode(self, dest=None, depth=0):
        out = dest
        if out is None:
            out = io.BytesIO()
        self.position = out.tell()
        if len(self.atom_type) > 4:
            # 16 hex chars + 'UUID()' == 38
            if len(self.atom_type) != 38:
                print(len(self.atom_type), self.atom_type)
            assert len(self.atom_type) == 38
            fourcc = b'uuid' + binascii.a2b_hex(self.atom_type[5:-1])
        else:
            assert len(self.atom_type) == 4
            fourcc = bytes(self.atom_type, 'ascii')
        self.options.log.debug('%s: encode %s pos=%d', self._fullname,
                               self.classname(), self.position)
        if self._encoded is not None:
            self.options.log.debug('%s: Using pre-encoded data length=%d',
                                   self._fullname, len(self._encoded))
            expected_size = 4 + len(fourcc) + len(self._encoded)
            if self.size != expected_size:
                msg = r'{}: Expected size {:d}, actual size {:d}'.format(
                    self._fullname, self.size, expected_size)
                self.options.log.warning(msg)
                if self.options.strict:
                    raise ValueError(msg)
            out.write(struct.pack('>I', self.size))
            out.write(fourcc)
            out.write(self._encoded)
            if dest is None:
                return out.getvalue()
            return dest
        out.write(struct.pack('>I', 0))
        out.write(fourcc)
        self.encode_fields(dest=out)
        if self.children:
            for child in self.children:
                child.encode(dest=out, depth=(depth + 1))
        self.size = out.tell() - self.position
        # replace the length field
        out.seek(self.position)
        out.write(struct.pack('>I', self.size))
        out.seek(0, 2)  # seek to end
        if depth == 0:
            self.post_encode_all(dest=out)
        self.options.log.debug('%s: produced %d bytes pos=(%d .. %d)',
                               self._fullname, self.size,
                               self.position, out.tell())
        if dest is None:
            return out.getvalue()
        return dest

    @abstractmethod
    def encode_fields(self, dest):
        pass

    def post_encode_all(self, dest):
        if self.children is not None:
            for child in self.children:
                child.post_encode_all(dest)
        self.post_encode(dest)

    def post_encode(self, dest):
        return

    def atom_name(self) -> str:
        return self.atom_type

    def dump(self, indent=''):
        atom_type = self.atom_name()
        print('{}{}: {:d} -> {:d} [{:d} bytes]'.format(
            indent, atom_type, self.position,
            self.position + self.size, self.size))
        if 'descriptors' in self._fields:
            for d in self.descriptors:
                d.dump(indent + '  ')
        if self.children is not None:
            for c in self.children:
                c.dump(indent + '  ')


Mp4Atom.OBJECT_FIELDS['children'] = ListOf(Mp4Atom)

class WrapperIterator:
    def __init__(self, wrapper):
        self._wrapper = wrapper
        self._current = 0

    def __next__(self):
        if self._current < len(self._wrapper.children):
            rv = self._wrapper.children[self._current]
            self._current += 1
            return rv
        raise StopIteration


class Wrapper(Mp4Atom):
    DEFAULT_VALUES = {
        'atom_type': 'wrap',
        'position': 0,
        'parent': None,
    }

    parse_children = True

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


fourcc.BOX_TYPES['UnknownBox'] = UnknownBox

@fourcc('ftyp')
class FileTypeBox(Mp4Atom):
    OBJECT_FIELDS = {
        "compatible_brands": ListOf(str),
    }

    @classmethod
    def parse(clz, src, *args, **kwargs):
        rv = Mp4Atom.parse(src, *args, **kwargs)
        r = FieldReader(clz.classname(), src, rv)
        rv['major_brand'] = str(r.get(4, 'major_brand'), 'ascii')
        r.read('I', 'minor_version')
        size = rv["size"] - rv["header_size"] - 8
        rv['compatible_brands'] = []
        while size > 3:
            cb = r.get(4, 'compatible_brand')
            if len(cb) != 4:
                break
            rv['compatible_brands'].append(str(cb, 'ascii'))
            size -= 4
        return rv

    def encode_fields(self, dest):
        d = FieldWriter(self, dest)
        d.write(4, 'major_brand')
        d.write('I', 'minor_version')
        for cb in self.compatible_brands:
            d.write(4, 'compatible_brand', value=bytes(cb, 'ascii'))


@fourcc('styp')
class SegmentTypeBox(FileTypeBox):
    pass


class Descriptor(ObjectWithFields):
    OBJECT_FIELDS = {
        'children': ListOf(ObjectWithFields),
        'data': Binary,
        'parent': ObjectWithFields,
    }

    REQUIRED_FIELDS = {
        'tag': int,
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.apply_defaults({
            "children": [],
            "options": Options(),
            "_encoded": None,
            "parent": None,
        })
        if self.parent:
            self._fullname = fr'{self.parent._fullname}.{self.classname()}'
        else:
            self._fullname = self.classname()

    @classmethod
    def load(clz, src, parent, options=None, **kwargs):
        if options is None:
            options = Options()
        kw = Descriptor.parse_header(src)
        try:
            Desc = mp4descriptor.DESCRIPTORS[kw["tag"]]
        except KeyError:
            Desc = UnknownDescriptor
        total_size = kw["size"] + kw["header_size"]
        options.log.debug(
            'load descriptor: tag=%s type=%s pos=%d size=%d',
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
            dc = Descriptor.load(src, parent=rv, options=options)
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
            Desc = mp4descriptor.DESCRIPTORS[tag]
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
                f"Failed to read tag byte: pos={position}")
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
                    r'%s: using pre-encoded data size=%d', self.classname(), len(self._encoded))
                for child in self.children:
                    self.options.log.debug(
                        r'%s: skipping descriptor %s size=%d',
                        self.classname(), child._fullname, child.size)
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
        return super()._to_json(exclude)

    def dump(self, indent=''):
        f = '{}{}: {:d} -> {:d} [header {:d} bytes] [{:d} bytes]'
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


@mp4descriptor(0x03)
class ESDescriptor(Descriptor):
    @classmethod
    def parse_payload(clz, src, rv, options, **kwargs):
        r = FieldReader(clz.classname(), src, rv, debug=options.debug)
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


@mp4descriptor(0x04)
class DecoderConfigDescriptor(Descriptor):
    @classmethod
    def parse_payload(clz, src, rv, **kwargs):
        r = FieldReader(clz.classname(), src, rv)
        r.read('B', "object_type")
        b = r.get('B', "stream_type")
        rv["stream_type"] = (b >> 2)
        rv["unknown_flag"] = (b & 0x01) == 0x01
        rv["upstream"] = (b & 0x02) == 0x02
        r.read('3I', "buffer_size")
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
    def parse_payload(clz, src, rv, parent, **kwargs):
        rv["object_type"] = parent.object_type
        r = BitsFieldReader(clz.classname(), src, rv, rv["size"])
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
            skip = 8 - r.bitpos() & 7
            if skip:
                r.read(skip, 'reserved')
            if r.bytepos() != rv["size"]:
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


class FullBox(Mp4Atom):
    @classmethod
    def parse(clz, src, parent, options, **kwargs):
        rv = Mp4Atom.parse(src, parent, options=options, **kwargs)
        r = FieldReader(clz.classname(), src, rv, debug=options.debug)
        r.read("B", "version")
        r.read('3I', "flags")
        return rv

    def encode_fields(self, dest):
        d = FieldWriter(self, dest)
        d.write('B', 'version')
        d.write(3, 'flags', value=struct.pack('>I', self.flags)[1:])
        self.encode_box_fields(dest)

    @abstractmethod
    def encode_box_fields(self, dest):
        pass

class BoxWithChildren(Mp4Atom):
    parse_children = True
    include_atom_type = True

    def encode_fields(self, dest):
        pass


fourcc.BOX_TYPES['BoxWithChildren'] = BoxWithChildren

@fourcc('moov')
class MovieBox(BoxWithChildren):
    include_atom_type = False
    pass


@fourcc('trak')
class TrackBox(BoxWithChildren):
    include_atom_type = False
    pass


@fourcc('traf')
class TrackFragmentBox(BoxWithChildren):
    pass


@fourcc('moof')
class MovieFragmentBox(BoxWithChildren):
    pass


@fourcc('minf')
class MediaInformationBox(BoxWithChildren):
    pass

@fourcc('mvex')
class MovieExtendsBox(BoxWithChildren):
    pass


@fourcc('mdia')
class MediaDataBox(BoxWithChildren):
    pass


@fourcc('schi')
class SchemaInformationBox(BoxWithChildren):
    pass


@fourcc('sinf')
class ProtectionSchemeInformationBox(BoxWithChildren):
    pass


@fourcc('stbl')
class SampleTableBox(BoxWithChildren):
    pass


@fourcc('udta')
class UserDataBox(BoxWithChildren):
    pass

@fourcc('mvhd')
class MovieHeaderBox(FullBox):
    OBJECT_FIELDS = {
        "creation_time": DateTimeField,
        "modification_time": DateTimeField,
        "matrix": ListOf(int),
    }

    @classmethod
    def parse(clz, src, parent, options, **kwargs):
        rv = FullBox.parse(src, parent, options=options, **kwargs)
        r = FieldReader(clz.classname(), src, rv, debug=options.debug)
        if rv['version'] == 1:
            sz = 'Q'
        else:
            sz = 'I'
        r.read(sz, 'creation_time')
        r.read(sz, 'modification_time')
        r.read('I', 'timescale')
        r.read(sz, 'duration')
        rv["creation_time"] = from_iso_epoch(rv["creation_time"])
        rv["modification_time"] = from_iso_epoch(rv["modification_time"])
        r.read('D16.16', 'rate')
        r.read('D8.8', 'volume')
        r.skip(10)  # reserved
        rv["matrix"] = []
        for i in range(9):
            rv["matrix"].append(r.get('I', 'matrix'))
        r.skip(6 * 4)  # pre_defined = 0
        r.read('I', 'next_track_id')
        return rv

    def encode_box_fields(self, dest):
        d = FieldWriter(self, dest)
        if self.version == 1:
            sz = 'Q'
        else:
            sz = 'I'
        d.write(sz, 'creation_time',
                value=to_iso_epoch(self.creation_time))
        d.write(sz, 'modification_time',
                value=to_iso_epoch(self.modification_time))
        d.write('I', 'timescale')
        d.write(sz, 'duration')
        d.write('D16.16', 'rate')
        d.write('D8.8', 'volume')
        d.write(10, 'reserved', value=(b'\0' * 10))  # reserved
        for value in self.matrix:
            d.write('I', 'matrix', value=value)
        d.write(6 * 4, 'reserved', value=(b'\0' * 6 * 4))  # reserved
        d.write('I', 'next_track_id')


class SampleEntry(Mp4Atom):
    @classmethod
    def parse(clz, src, parent, options, **kwargs):
        rv = Mp4Atom.parse(src, parent, **kwargs)
        r = FieldReader(clz.classname(), src, rv, debug=options.debug)
        r.skip(6)  # reserved
        r.read('H', 'data_reference_index')
        return rv

    def encode_fields(self, dest):
        dest.write(b'\0' * 6)  # reserved
        dest.write(struct.pack('>H', self.data_reference_index))

class VisualSampleEntry(SampleEntry):
    parse_children = True

    @classmethod
    def parse(clz, src, parent, options, **kwargs):
        rv = SampleEntry.parse(src, parent, options, **kwargs)
        r = FieldReader(clz.classname(), src, rv, debug=options.debug)
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
        super().encode_fields(dest)
        dest.write(struct.pack('>H', self.version))
        dest.write(struct.pack('>H', self.revision))
        dest.write(struct.pack('>I', self.vendor))
        dest.write(struct.pack('>I', self.temporal_quality))
        dest.write(struct.pack('>I', self.spatial_quality))
        dest.write(struct.pack('>H', self.width))
        dest.write(struct.pack('>H', self.height))
        dest.write(struct.pack('>I', int(self.horizresolution * 65536.0)))
        dest.write(struct.pack('>I', int(self.vertresolution * 65536.0)))
        dest.write(struct.pack('>I', self.entry_data_size))
        dest.write(struct.pack('>H', self.frame_count))
        c = self.compressorname + '\0' * 32
        dest.write(c[:32].encode('ascii'))
        dest.write(struct.pack('>H', self.bit_depth))
        dest.write(struct.pack('>H', self.colour_table))

@fourcc('avc1')
class AVC1SampleEntry(VisualSampleEntry):
    pass


@fourcc('avc3')
class AVC3SampleEntry(VisualSampleEntry):
    pass


@fourcc('hev1')
class HEV1SampleEntry(VisualSampleEntry):
    pass


@fourcc('hvc1')
class HVC1SampleEntry(VisualSampleEntry):
    pass


@fourcc('encv')
class EncryptedSampleEntry(VisualSampleEntry):
    pass


@fourcc('vttC')
class WebVTTConfigurationBox(Mp4Atom):
    @classmethod
    def parse(clz, src, parent, options, **kwargs):
        rv = Mp4Atom.parse(src, parent, options, **kwargs)
        rv['config'] = str(src.read(rv['size'] - rv['header_size']), 'utf-8')
        return rv

    def encode_fields(self, dest):
        super().encode_fields(dest)
        dest.write(bytes(self.config, 'utf-8'))


@fourcc('btrt')
class BitRateBox(Mp4Atom):
    @classmethod
    def parse(clz, src, parent, options, **kwargs):
        rv = Mp4Atom.parse(src, parent, options, **kwargs)
        r = FieldReader(clz.classname(), src, rv, debug=options.debug)
        r.read('I', 'bufferSizeDB')
        r.read('I', 'maxBitrate')
        r.read('I', 'avgBitrate')
        return rv

    def encode_fields(self, dest):
        d = FieldWriter(self, dest, debug=self.options.debug)
        d.write('I', 'bufferSizeDB')
        d.write('I', 'maxBitrate')
        d.write('I', 'avgBitrate')


class PlainTextSampleEntry(SampleEntry):
    pass


@fourcc('wvtt')
class WVTTSampleEntry(PlainTextSampleEntry):
    parse_children = True


@fourcc('stpp')
class XMLSubtitleSampleEntry(SampleEntry):
    parse_children = True

    @classmethod
    def parse(clz, src, parent, options, **kwargs):
        rv = SampleEntry.parse(src, parent, options, **kwargs)
        r = FieldReader(clz.classname(), src, rv, debug=options.debug)
        r.read('S0', 'namespace')
        r.read('S0', 'schema_location')
        r.read('S0', 'mime_types')
        return rv

    def encode_fields(self, dest):
        super().encode_fields(dest)
        d = FieldWriter(self, dest, debug=self.options.debug)
        d.write('S0', 'namespace')
        d.write('S0', 'schema_location')
        d.write('S0', 'mime_types')


@fourcc('mime')
class MimeBox(FullBox):
    @classmethod
    def parse(clz, src, parent, options, **kwargs):
        rv = FullBox.parse(src, parent=parent, options=options, **kwargs)
        rv['content_type'] = src.read(rv['size'] - rv['header_size'] - 4)
        while rv['content_type'][-1] == 0:
            rv['content_type'] = rv['content_type'][:-1]
        rv['content_type'] = str(rv['content_type'], 'ascii')
        return rv

    def encode_box_fields(self, dest):
        d = FieldWriter(self, dest, debug=self.options.debug)
        d.write('S0', 'content_type')


@fourcc('avcC')
class AVCConfigurationBox(Mp4Atom):
    OBJECT_FIELDS = {
        'sps': ListOf(Binary),
        'sps_ext': ListOf(Binary),
        'pps': ListOf(Binary),
    }

    @classmethod
    def parse(clz, src, parent, options, **kwargs):
        rv = Mp4Atom.parse(src, parent, options=options, **kwargs)
        r = FieldReader(clz.classname(), src, rv, debug=options.debug)
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


class HevcNalArray(ObjectWithFields):
    OBJECT_FIELDS = {
        'nal_units': ListOf(Binary),
    }

    @classmethod
    def parse(clz, reader):
        rv = {}
        # r = BitsFieldReader(clz.classname(), src, rv)
        r = reader.duplicate('HEVC NAL array', rv)
        r.read(1, 'array_completeness')
        r.get(1, 'reserved')
        r.read(6, 'nal_unit_type')
        num_nalus = r.get(16, 'num_nalus')
        rv['nal_units'] = []
        for i in range(num_nalus):
            unit_length = r.get(16, 'nalUnitLength')
            nal_unit = r.get_bytes(unit_length, f'NAL unit {i}')
            rv['nal_units'].append(Binary(nal_unit, encoding=Binary.BASE64))
        return rv

    def encode(self, dest):
        w = BitsFieldWriter(self, dest)
        w.write(1, 'array_completeness')
        w.write(1, 'reserved', value=0)
        w.write(6, 'nal_unit_type')
        w.write(16, 'num_nalus', value=len(self.nal_units))
        for nalu in self.nal_units:
            w.write(16, 'nalUnitLength', value=len(nalu.data))
            w.write_bytes('NAL unit', value=nalu.data)


# see FFMPEG libavformat/hevc.c for HEVCDecoderConfigurationRecord
@fourcc('hvcC')
class HEVCConfigurationBox(Mp4Atom):
    VPS_NAL_UNIT_TYPE = 32
    SPS_NAL_UNIT_TYPE = 33
    PPS_NAL_UNIT_TYPE = 34

    # general_profile_compatibility_flags
    HEVCPROFILE_MAIN = 0x0002
    HEVCPROFILE_MAIN10 = 0x0004
    HEVCPROFILE_MAIN_STILL_PICTURE = 0x0008
    HEVCPROFILE_REXT = 0x0010
    HEVCPROFILE_HIGH_THROUGHPUT = 0x0020
    HEVCPROFILE_MULTIVIEW_MAIN = 0x0040
    HEVCPROFILE_SCALABLE_MAIN = 0x0080
    HEVCPROFILE_3D_MAIN = 0x0100
    HEVCPROFILE_SCREEN_EXTENDED = 0x0200
    HEVCPROFILE_SCALABLE_REXT = 0x0400
    HEVCPROFILE_HIGH_THROUGHPUT_SCREEN_EXTENDED = 0x0800

    OBJECT_FIELDS = {
        'arrays': ListOf(HevcNalArray),
    }
    OBJECT_FIELDS.update(Mp4Atom.OBJECT_FIELDS)

    @classmethod
    def parse(clz, src, parent, options, **kwargs):
        rv = Mp4Atom.parse(src, parent, options=options, **kwargs)
        r = BitsFieldReader(clz.classname(), src, rv, rv["size"] - rv["header_size"])
        r.read(8, 'configuration_version')
        if rv['configuration_version'] != 1:
            return rv
        r.read(2, 'general_profile_space')
        r.read(1, 'general_tier_flag')
        r.read(5, 'general_profile_idc')
        r.read(32, 'general_profile_compatibility_flags')
        r.read(48, 'general_constraint_indicator_flags')
        r.read(8, 'general_level_idc')
        r.get(4, 'reserved')
        r.read(12, 'min_spatial_segmentation_idc')
        r.get(6, 'reserved')
        r.read(2, 'parallelismType')
        r.get(6, 'reserved')
        r.read(2, 'chroma_format_idc')
        r.get(5, 'reserved')
        rv['luma_bit_depth'] = 8 + r.get(3, 'luma_bit_depth_minus8')
        r.get(5, 'reserved')
        rv['chroma_bit_depth'] = 8 + r.get(3, 'chroma_bit_depth_minus8')
        r.read(16, 'avg_framerate')
        r.read(2, 'constant_framerate')
        r.read(3, 'num_temporal_layers')
        r.read(1, 'temporal_id_nested')
        r.read(2, 'length_size_minus_one')
        num_arrays = r.get(8, 'num_arrays')
        rv['arrays'] = []
        # the 'arrays' list should contain the VPS, SPS and PPS
        for i in range(num_arrays):
            rv['arrays'].append(HevcNalArray.parse(r))
        return rv

    def encode_fields(self, dest):
        w = BitsFieldWriter(self)
        w.write(8, 'configuration_version')
        w.write(2, 'general_profile_space')
        w.write(1, 'general_tier_flag')
        w.write(5, 'general_profile_idc')
        w.write(32, 'general_profile_compatibility_flags')
        w.write(48, 'general_constraint_indicator_flags')
        w.write(8, 'general_level_idc')
        w.write(4, 'reserved', value=0x0F)
        w.write(12, 'min_spatial_segmentation_idc')
        w.write(6, 'reserved', value=0x3F)
        w.write(2, 'parallelismType')
        w.write(6, 'reserved', value=0x3F)
        w.write(2, 'chroma_format_idc')
        w.write(5, 'reserved', value=0x1F)
        w.write(3, 'luma_bit_depth', value=(self.luma_bit_depth - 8))
        w.write(5, 'reserved', value=0x1F)
        w.write(3, 'chroma_bit_depth', value=(self.chroma_bit_depth - 8))
        w.write(16, 'avg_framerate')
        w.write(2, 'constant_framerate')
        w.write(3, 'num_temporal_layers')
        w.write(1, 'temporal_id_nested')
        w.write(2, 'length_size_minus_one')
        w.write(8, 'num_arrays', value=len(self.arrays))
        for nal_arr in self.arrays:
            nal_arr.encode(w)
        dest.write(w.toBytes())

    def get_vps(self):
        """
        Returns the VPS NAL units in this configuration box
        """
        return self._get_nal_unit(self.VPS_NAL_UNIT_TYPE)

    def get_sps(self):
        """
        Returns the SPS NAL units in this configuration box
        """
        return self._get_nal_unit(self.SPS_NAL_UNIT_TYPE)

    def _get_nal_unit(self, nal_type):
        for nal_arr in self.arrays:
            if nal_arr.nal_unit_type == nal_type:
                return nal_arr.nal_units
        return []


@fourcc('pasp')
class PixelAspectRatioBox(Mp4Atom):
    @classmethod
    def parse(clz, src, parent, options, **kwargs):
        rv = Mp4Atom.parse(src, parent, options=options, **kwargs)
        r = FieldReader(clz.classname(), src, rv)
        r.read('I', 'h_spacing')
        r.read('I', 'v_spacing')
        return rv

    def encode_fields(self, dest):
        d = FieldWriter(self, dest)
        d.write('I', 'h_spacing')
        d.write('I', 'v_spacing')


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
        super().encode_fields(dest)
        dest.write(b'\0' * 8)  # reserved
        dest.write(struct.pack('>H', self.channel_count))
        dest.write(struct.pack('>H', self.sample_size))
        dest.write(b'\0' * 4)  # reserved
        dest.write(struct.pack('>H', self.sampling_frequency))
        dest.write(b'\0' * 2)  # reserved

@fourcc('ec-3')
class EC3SampleEntry(AudioSampleEntry):
    pass


@fourcc('ac-3')
class AC3SampleEntry(AudioSampleEntry):
    pass


class EAC3SubStream(ObjectWithFields):
    DEFAULT_EXCLUDE = {'src'}

    @classmethod
    def parse(clz, r):
        r.read(2, 'fscod')
        r.read(5, 'bsid')
        r.read(5, 'bsmod')
        r.read(3, 'acmod')
        r.kwargs['channel_count'] = EAC3SpecificBox.ACMOD_NUM_CHANS[r.kwargs['acmod']]
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
@fourcc('dec3')
class EAC3SpecificBox(Mp4Atom):
    ACMOD_NUM_CHANS = [2, 1, 2, 3, 3, 4, 4, 5]

    OBJECT_FIELDS = {
        "substreams": ListOf(EAC3SubStream),
    }
    OBJECT_FIELDS.update(Mp4Atom.OBJECT_FIELDS)

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = Mp4Atom.parse(src, parent, **kwargs)
        r = BitsFieldReader(clz.classname(), src, rv, size=None)
        r.read(13, "data_rate")
        num_ind_sub = r.get(3, "num_ind_sub") + 1
        rv["substreams"] = []
        for i in range(num_ind_sub):
            r2 = r.duplicate("EAC3SubStream", {})
            EAC3SubStream.parse(r2)
            rv["substreams"].append(EAC3SubStream(**r2.kwargs))
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


@fourcc('dac3')
class AC3SpecificBox(Mp4Atom):
    SAMPLE_RATES = [48000, 44100, 32000, 0]
    CHANNEL_CONFIGURATIONS = [
        (2, "1 + 1 (Ch1, Ch2)"),
        (1, "1/0 (C)"),
        (2, "2/0 (L, R)"),
        (3, "3/0 (L, C, R)"),
        (3, "2/1 (L, R, S)"),
        (4, "3/1 (L, C, R, S)"),
        (4, "2/2 (L, R, SL, SR)"),
        (5, "3/2 (L, C, R, SL, SR)"),
    ]

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = Mp4Atom.parse(src, parent, **kwargs)
        r = BitsFieldReader(clz.classname(), src, rv, rv["size"] - rv["header_size"])
        r.read(2, 'fscod')
        r.read(5, 'bsid')
        r.read(3, 'bsmod')
        r.read(3, 'acmod')
        r.read(1, 'lfe')
        r.read(5, 'bitrate_code')
        r.get(5, 'reserved')
        rv['sampling_frequency'] = clz.SAMPLE_RATES[rv["fscod"]]
        rv['channel_count'], rv['channel_configuration'] = clz.CHANNEL_CONFIGURATIONS[rv['acmod']]
        if rv['lfe']:
            rv['channel_count'] += 1
        return rv

    def encode_fields(self, dest):
        w = BitsFieldWriter(self)
        w.write(2, 'fscod')
        w.write(5, 'bsid')
        w.write(3, 'bsmod')
        w.write(3, 'acmod')
        w.write(1, 'lfe')
        w.write(5, 'bitrate_code')
        w.write(5, 'reserved', value=0x00)
        dest.write(w.toBytes())


@fourcc('frma')
class OriginalFormatBox(Mp4Atom):
    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = Mp4Atom.parse(src, parent, **kwargs)
        rv["data_format"] = str(src.read(4), 'ascii')
        return rv

    def encode_fields(self, dest):
        dest.write(bytes(self.data_format, 'ascii'))


# see table 6.3 of 3GPP TS 26.244 V12.3.0
@fourcc('mp4a')
class MP4AudioSampleEntry(Mp4Atom):
    parse_children = True

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = Mp4Atom.parse(src, parent, **kwargs)
        r = FieldReader(clz.classname(), src, rv)
        r.get(6, 'reserved')  # (8)[6] reserved
        r.read('H', "data_reference_index")
        r.get(8 + 4 + 4, 'reserved')  # (8)[6] reserved
        r.read('H', "timescale")
        r.get(2, 'reserved')  # (16) reserved
        return rv

    def encode_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write(6, 'reserved', b'')
        w.write('H', 'data_reference_index')
        w.write(8, 'reserved_8', b'')
        w.write('H', 'reserved_2', 2)
        w.write('H', 'reserved_2', 16)
        w.write(4, 'reserved_4', b'')
        w.write('H', 'timescale')
        w.write(2, 'reserved', b'')


@fourcc('enca')
class EncryptedMP4A(MP4AudioSampleEntry):
    pass


@fourcc('esds')
class ESDescriptorBox(FullBox):
    OBJECT_FIELDS = {
        'descriptors': ListOf(Descriptor)
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
            d = Descriptor.load(src, parent=parent, options=options)
            descriptors.append(d)
            if src.tell() != (d.position + d.size + d.header_size):
                options.log.warning(
                    "Expected descriptor %s to be %d bytes, but read %d bytes",
                    d.classname(), d.size + d.header_size,
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

    def encode_box_fields(self, dest):
        for d in self.descriptors:
            d.encode(dest)


@fourcc('stsd')
class SampleDescriptionBox(FullBox):
    parse_children = True

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        rv["entry_count"] = struct.unpack('>I', src.read(4))[0]
        return rv

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('I', 'entry_count')


@fourcc('tfhd')
class TrackFragmentHeaderBox(FullBox):
    base_data_offset_present = 0x000001
    sample_description_index_present = 0x000002
    default_sample_duration_present = 0x000008
    default_sample_size_present = 0x000010
    default_sample_flags_present = 0x000020
    duration_is_empty = 0x010000
    default_base_is_moof = 0x020000

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
        r = FieldReader(clz.classname(), src, rv)
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

    def encode_box_fields(self, dest):
        if self.base_data_offset is None:
            self.base_data_offset = self.find_atom('moof').position
        w = FieldWriter(self, dest)
        w.write('I', 'track_id')
        if self.flags & self.base_data_offset_present:
            w.write('Q', 'base_data_offset')
        if self.flags & self.sample_description_index_present:
            w.write('I', 'sample_description_index')
        if self.flags & self.default_sample_duration_present:
            w.write('I', 'default_sample_duration')
        if self.flags & self.default_sample_size_present:
            w.write('I', 'default_sample_size')
        if self.flags & self.default_sample_flags_present:
            w.write('I', 'default_sample_flags')


@fourcc('tkhd')
class TrackHeaderBox(FullBox):
    Track_enabled = 0x000001
    Track_in_movie = 0x000002
    Track_in_preview = 0x000004
    Track_size_is_aspect_ratio = 0x000008

    OBJECT_FIELDS = {
        "creation_time": DateTimeField,
        "modification_time": DateTimeField,
        "matrix": ListOf(int),
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        r = FieldReader(clz.classname(), src, rv)
        rv["is_enabled"] = (rv["flags"] & clz.Track_enabled) == clz.Track_enabled
        rv["in_movie"] = (rv["flags"] & clz.Track_in_movie) == clz.Track_in_movie
        rv["in_preview"] = (rv["flags"] & clz.Track_in_preview) == clz.Track_in_preview
        rv["size_is_aspect_ratio"] = (
            (rv["flags"] & clz.Track_size_is_aspect_ratio) == clz.Track_size_is_aspect_ratio)
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
        if self.size_is_aspect_ratio:
            self.flags |= self.Track_size_is_aspect_ratio
        super().encode_fields(dest)

    def encode_box_fields(self, dest):
        d = FieldWriter(self, dest)
        if self.version == 1:
            sz = 'Q'
        else:
            sz = 'I'
        d.write(sz, 'creation_time', to_iso_epoch(self.creation_time))
        d.write(sz, 'modification_time', to_iso_epoch(self.modification_time))
        d.write('I', 'track_id')
        d.write(4, 'reserved', b'\0' * 4)  # reserved
        d.write(sz, 'duration')
        d.write(8, 'reserved', b'\0' * 8)  # reserved
        d.write('H', 'layer')
        d.write('H', 'alternate_group')
        d.write('D8.8', 'volume')  # int(self.volume * 256.0))
        d.write(2, 'reserved', b'\0' * 2)  # reserved
        for m in self.matrix:
            d.write('I', 'matrix', m)
        d.write('D16.16', 'width')  # long(self.width * 65536.0))
        d.write('D16.16', 'height')  # long(self.height * 65536.0))


@fourcc('tfdt')
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
        if self.base_media_decode_time > int(1 << 32):
            self.version = 1
        else:
            self.version = 0
        super().encode_fields(dest)

    def encode_box_fields(self, dest):
        d = FieldWriter(self, dest)
        if self.version == 1:
            d.write('Q', 'base_media_decode_time')
        else:
            d.write('I', 'base_media_decode_time')


@fourcc('trex')
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

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('I', 'track_id')
        w.write('I', 'default_sample_description_index')
        w.write('I', 'default_sample_duration')
        w.write('I', 'default_sample_size')
        w.write('I', 'default_sample_flags')


@fourcc('mdhd')
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

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        if self.version == 1:
            sz = 'Q'
        else:
            sz = 'I'
        w.write(sz, 'creation_time', value=to_iso_epoch(self.creation_time))
        w.write(sz, 'modification_time', value=to_iso_epoch(self.modification_time))
        w.write('I', 'timescale')
        w.write(sz, 'duration')
        chars = [ord(c) - 0x60 for c in list(self.language)]
        lang = (chars[0] << 10) + (chars[1] << 5) + chars[2]
        w.write('H', 'lang', value=lang)
        w.write('H', 'pre_defined', value=0)


@fourcc('mfhd')
class MovieFragmentHeaderBox(FullBox):
    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        rv["sequence_number"] = struct.unpack('>I', src.read(4))[0]
        return rv

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('I', 'sequence_number')


@fourcc('hdlr')
class HandlerBox(FullBox):
    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        src.read(4)  # unsigned int(32) pre_defined = 0
        rv["handler_type"] = str(src.read(4), 'utf-8')
        src.read(12)  # const unsigned int(32)[3] reserved = 0;
        name_len = rv["position"] + rv["size"] - src.tell()
        name_bytes = src.read(name_len)
        while name_len and name_bytes[-1] == 0:
            name_bytes = name_bytes[:-1]
            name_len -= 1
        rv["name"] = str(name_bytes, 'utf-8')
        return rv

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('I', 'pre_defined', value=0)
        w.write('S4', 'handler_type')
        w.write(None, 'reserved', value=(b'\0' * 12))  # reserved = 0
        w.write('S0', 'name')


@fourcc('mehd')
class MovieExtendsHeaderBox(FullBox):
    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        if rv["version"] == 1:
            rv["fragment_duration"] = struct.unpack('>Q', src.read(8))[0]
        else:
            rv["fragment_duration"] = struct.unpack('>I', src.read(4))[0]
        return rv

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        if self.version == 1:
            w.write('Q', 'fragment_duration')
        else:
            w.write('I', 'fragment_duration')


@fourcc('saiz')
class SampleAuxiliaryInformationSizesBox(FullBox):
    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        if rv["flags"] & 1:
            rv["aux_info_type"] = struct.unpack('>I', src.read(4))[0]
            rv["aux_info_type_parameter"] = struct.unpack('>I', src.read(4))[0]
        rv["default_sample_info_size"] = struct.unpack('B', src.read(1))[0]
        rv["sample_info_sizes"] = []
        rv["sample_count"] = struct.unpack('>I', src.read(4))[0]
        if rv["default_sample_info_size"] == 0:
            for i in range(rv["sample_count"]):
                rv["sample_info_sizes"].append(
                    struct.unpack('B', src.read(1))[0])
        return rv

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        if self.flags & 1:
            w.write('I', 'aux_info_type')
            w.write('I', 'aux_info_type_parameter')
        w.write('B', 'default_sample_info_size')
        if self.default_sample_info_size == 0:
            self.sample_count = len(self.sample_info_sizes)
        w.write('I', 'sample_count')
        if self.default_sample_info_size == 0:
            for sz in self.sample_info_sizes:
                w.write('B', 'size', value=sz)

    def _to_json(self, exclude):
        exclude.add('aux_info_type')
        fields = super(FullBox, self)._to_json(exclude)
        if "aux_info_type" in self._fields:
            fields['aux_info_type'] = '0x%x' % self.aux_info_type
        return fields


# See 2.2.4 of Common File Format & Media Formats Specification Version 2.1
class CencSubSample(ObjectWithFields):
    REQUIRED_FIELDS = {
        'clear': int,
        'encrypted': int,
    }

    @classmethod
    def parse(clz, src):
        rv = {}
        r = FieldReader(clz.classname(), src, rv)
        r.read('H', 'clear')
        r.read('I', 'encrypted')
        return rv

    def encode(self, dest):
        d = FieldWriter(self, dest)
        d.write('H', 'clear')
        d.write('I', 'encrypted')


class CencSampleAuxiliaryData(ObjectWithFields):
    UseSubsampleEncryption = 2

    OBJECT_FIELDS = {
        "initialization_vector": HexBinary,
        "subsamples": ListOf(CencSubSample),
    }

    @classmethod
    def parse(clz, src, size, iv_size, flags, parent):
        subsample_encryption = (flags & clz.UseSubsampleEncryption) == clz.UseSubsampleEncryption
        if iv_size is None:
            if not subsample_encryption:
                iv_size = size
            else:
                raise ValueError("Unable to determine IV size")
        rv = {
            "position": src.tell(),
            "iv_size": iv_size,
            "size": size,
        }
        r = FieldReader(clz.classname(), src, rv)
        r.read(iv_size, "initialization_vector", encoder=HexBinary)
        rv["subsamples"] = []
        if subsample_encryption and size >= (iv_size + 2):
            # subsample_count = struct.unpack('>H', src.read(2))[0]
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


@fourcc('senc')
class CencSampleEncryptionBox(FullBox):
    OBJECT_FIELDS = {
        "kid": HexBinary,
        "samples": ListOf(CencSampleAuxiliaryData),
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)
    REQUIRED_PEERS = ['saiz']

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        r = FieldReader(clz.classname(), src, rv)
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
                rv["iv_size"] = kwargs["options"].iv_size
        num_entries = r.get('I', 'num_entries')
        assert rv['iv_size'] in {8, 16}
        rv["samples"] = []
        saiz = parent.find_child('saiz')
        if saiz is None:
            kwargs['options'].log.error('Failed to find saiz box')
            kwargs['error'] = 'Failed to find required saiz box'
            return rv
        for i in range(num_entries):
            if saiz.sample_info_sizes:
                size = saiz.sample_info_sizes[i]
            else:
                size = saiz.default_sample_info_size
            if size:
                s = CencSampleAuxiliaryData.parse(
                    src, size, rv["iv_size"], rv["flags"], parent)
                rv["samples"].append(s)
        return rv

    def encode_fields(self, dest):
        if len(self.samples) > 0:
            self.flags |= 0x02
        super().encode_fields(dest)

    def encode_box_fields(self, dest):
        d = FieldWriter(self, dest)
        if self.flags & 0x01:
            alg = struct.pack('>I', self.algorithm_id)
            d.write(3, 'algorithm_id', value=alg[1:])
            d.write('B', 'iv_size')
            d.write(16, 'kid')
        d.write('I', 'sample_count', value=len(self.samples))
        for s in self.samples:
            s.encode(dest, self)


# Protected Interoperable File Format (PIFF) SampleEncryptionBox uses the
# same format as the CencSampleEncryptionBox, but using a UUID box

PIFF_ATOM_TYPE = 'UUID(a2394f525a9b4f14a2446c427c648df4)'

@fourcc(PIFF_ATOM_TYPE)
class PiffSampleEncryptionBox(CencSampleEncryptionBox):
    DEFAULT_VALUES = {
        'atom_type': PIFF_ATOM_TYPE
    }

    @classmethod
    def clone_from_senc(clz, senc):
        """
        Create a PiffSampleEncryptionBox from a CencSampleEncryptionBox
        """
        samples = []
        for samp in senc.samples:
            samples.append(samp.clone())
        kwargs = {
            'atom_type': clz.DEFAULT_VALUES['atom_type'],
            'version': senc.version,
            'flags': senc.flags,
            'iv_size': senc.iv_size,
            'samples': samples,
            'position': 0,
        }
        if senc.flags & 0x01:
            kwargs['algorithm_id'] = senc.algorithm_id
            kwargs['kid'] = senc.kid
        return clz(**kwargs)


@fourcc('schm')
class ProtectionSchemeTypeBox(FullBox):
    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        r = FieldReader(clz.classname(), src, rv)
        r.read('S4', 'scheme_type')
        r.read('I', 'scheme_version')
        if rv['flags'] & 0x000001:
            r.read('S0', 'scheme_uri')
        else:
            rv['scheme_uri'] = None
        return rv

    def encode_fields(self, dest):
        if self.scheme_uri is not None:
            self.flags |= 0x000001
        return super().encode_fields(dest)

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('S4', "scheme_type")
        w.write('I', "scheme_version")
        if self.scheme_uri is not None:
            w.write('S0', "scheme_uri")


@fourcc('saio')
class SampleAuxiliaryInformationOffsetsBox(FullBox):
    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        if rv["flags"] & 0x01:
            rv["aux_info_type"] = struct.unpack('>I', src.read(4))[0]
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

    def find_first_cenc_sample(self):
        senc = self.parent.find_child('senc')
        if senc is None:
            return None
        if len(senc.samples) == 0:
            return None
        tfhd = self.parent.find_child('tfhd')
        base_data_offset = None
        if tfhd is not None:
            base_data_offset = tfhd.base_data_offset
        if base_data_offset is None:
            moof = self.find_atom('moof')
            base_data_offset = moof.position
        return senc.samples[0].position - base_data_offset

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        if self.flags & 0x01:
            w.write('I', 'aux_info_type')
            w.write('I', 'aux_info_type_parameter')
        if self.offsets is None:
            pos = self.find_first_cenc_sample()
            if pos is not None:
                self.offsets = [pos]
            else:
                self.offsets = []
        w.write('I', 'entry_count', value=len(self.offsets))
        for off in self.offsets:
            if self.version == 0:
                w.write('I', 'offset', value=off)
            else:
                w.write('Q', 'offset', value=off)

    def post_encode(self, dest):
        if self.offsets is not None and len(self.offsets) != 1:
            return
        senc = self.parent.find_child('senc')
        if senc is None:
            return
        pos = self.find_first_cenc_sample()
        if self.offsets is None or pos != self.offsets[0]:
            if self.options.has_bug('saio'):
                return
            self.options.log.debug('%s: SENC sample offset has changed', self._fullname)
            self.offsets = [pos]
            pos = dest.tell()
            dest.seek(self.position)
            self.encode(dest)
            dest.seek(pos)

    def _to_json(self, exclude):
        exclude.add('aux_info_type')
        fields = super(FullBox, self)._to_json(exclude)
        if "aux_info_type" in self._fields:
            fields['aux_info_type'] = '0x%x' % self.aux_info_type
        return fields


# See section 8.8.8 of ISO/IEC 14496-12
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
            if trun['version']:
                rv["composition_time_offset"] = struct.unpack('>i', src.read(4))[0]
            else:
                rv["composition_time_offset"] = struct.unpack('>I', src.read(4))[0]
        return rv

    def encode(self, dest):
        flags = self.parent.flags
        d = FieldWriter(self, dest)
        if flags & TrackFragmentRunBox.sample_duration_present:
            d.write('I', 'duration')
        if flags & TrackFragmentRunBox.sample_size_present:
            d.write('I', 'size')
        if flags & TrackFragmentRunBox.sample_flags_present:
            d.write('I', 'flags')
        if flags & TrackFragmentRunBox.sample_composition_time_offsets_present:
            if self.parent.version:
                d.write('i', 'composition_time_offset')
            else:
                d.write('I', 'composition_time_offset')


@fourcc('trun')
class TrackFragmentRunBox(FullBox):
    data_offset_present = 0x000001
    first_sample_flags_present = 0x000004  # overrides default flags for the first sample only
    sample_duration_present = 0x000100  # sample has its own duration?
    sample_size_present = 0x000200  # sample has its own size
    sample_flags_present = 0x000400  # sample has its own flags
    sample_composition_time_offsets_present = 0x000800  # sample has a composition time offset

    OBJECT_FIELDS = {
        'samples': ListOf(TrackSample),
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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

    def encode_box_fields(self, dest):
        self._first_field_pos = dest.tell()
        self.ouput_box_fields(dest)
        for sample in self.samples:
            sample.encode(dest)

    def ouput_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('I', 'sample_count')
        if self.flags & self.data_offset_present:
            w.write('I', 'data_offset')
        if self.flags & self.first_sample_flags_present:
            w.write('I', 'first_sample_flags')

    def post_encode(self, dest):
        if (self.flags & self.data_offset_present) == 0:
            return
        pos = getattr(self, '_first_field_pos', None)
        if pos is None:
            return
        try:
            moof = self.find_atom('moof')
        except AttributeError:
            return
        # assume mdat header size is 8 bytes
        mdat_sample_start = moof.position + moof.size + 8
        first_sample_pos = moof.traf.tfhd.base_data_offset + self.data_offset
        if first_sample_pos != mdat_sample_start:
            self.options.log.debug(
                'rewriting trun data_offset from %d to %d',
                self.data_offset, mdat_sample_start - moof.traf.tfhd.base_data_offset)
            self.data_offset = mdat_sample_start - moof.traf.tfhd.base_data_offset
            cur = dest.tell()
            dest.seek(pos)
            self.ouput_box_fields(dest)
            dest.seek(cur)


@fourcc('tenc')
class TrackEncryptionBox(FullBox):
    OBJECT_FIELDS = {
        "default_kid": HexBinary,
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        r = FieldReader(clz.classname(), src, rv)
        r.read('3I', "is_encrypted")
        r.read('B', "iv_size")
        r.read(16, "default_kid")
        return rv

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('3I', "is_encrypted")
        w.write('B', "iv_size")
        w.write(16, "default_kid")


@fourcc('pssh')
class ContentProtectionSpecificBox(FullBox):
    OBJECT_FIELDS = {
        "data": Binary,
        "key_ids": ListOf(HexBinary),
        "system_id": HexBinary,
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
            raise ValueError(fr"Invalid length: {len(value)}")
        return HexBinary(value, encoding=Binary.HEX)

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        r = FieldReader(clz.classname(), src, rv)
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

    def encode_box_fields(self, dest):
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


class SegmentReference(ObjectWithFields):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            assert "src" != key
            if key not in self.__dict__:
                setattr(self, key, value)

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = {}
        r = BitsFieldReader(clz.classname(), src, rv, size=12)
        r.read(1, 'ref_type')
        r.read(31, 'ref_size')
        r.read(32, 'duration')
        r.read(1, 'starts_with_SAP')
        r.read(3, 'SAP_type')
        r.read(28, 'SAP_delta_time')
        return rv

    def _to_json(self, exclude):
        fields = {
            '_type': self.classname()
        }
        if exclude is None:
            exclude = set()
        exclude.add('parent')
        for k, v in self.__dict__.items():
            if k not in exclude:
                fields[k] = v
        return fields

    def encode(self, dest):
        w = FieldWriter(self, dest)
        w.writebits(1, 'ref_type')
        w.writebits(31, 'ref_size')
        w.writebits(32, 'duration')
        w.writebits(1, 'starts_with_SAP')
        w.writebits(3, 'SAP_type')
        w.writebits(28, 'SAP_delta_time')
        w.done()


@fourcc('sidx')
class SegmentIndexBox(FullBox):
    OBJECT_FIELDS = {
        'references': ListOf(SegmentReference),
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        r = FieldReader(clz.classname(), src, rv)
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

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('I', 'reference_id')
        w.write('I', 'timescale')
        sz = 'I' if self.version == 0 else 'Q'
        w.write(sz, 'earliest_presentation_time')
        w.write(sz, 'first_offset')
        w.write('H', 'reserved', 0)
        w.write('H', 'reference_count', len(self.references))
        for ref in self.references:
            ref.encode(w)


@fourcc('emsg')
class EventMessageBox(FullBox):
    OBJECT_FIELDS = {
        'data': Binary,
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    @classmethod
    def parse(clz, src, parent, **kwargs):
        rv = FullBox.parse(src, parent, **kwargs)
        r = FieldReader(clz.classname(), src, rv)
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

    def encode_box_fields(self, dest):
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
            d.write(None, 'data')


class IsoParser:
    @staticmethod
    def walk_atoms(filename, atom=None, options=None):
        atoms = None
        src = None
        try:
            if options is not None:
                options.log.debug('Parse %s', filename)
            if isinstance(filename, str):
                src = open(filename, mode="rb", buffering=16384)
            else:
                src = filename
            atoms = Mp4Atom.load(src, options=options)
        finally:
            if src and isinstance(filename, (str, str)):
                src.close()
        return atoms

    @staticmethod
    def show_atom(atom, atom_types, as_json, with_children, count=0):
        check_children = True
        if atom.atom_name() in atom_types:
            if atom.atom_name() in with_children:
                exclude = atom.DEFAULT_EXCLUDE.union({'atom_type'})
                check_children = False
            else:
                exclude = atom.DEFAULT_EXCLUDE.union({'atom_type', 'children'})
            if atom.atom_type == b'mdat' and 'mdat' not in with_children:
                exclude.add('data')
            if as_json:
                item = atom.toJSON(exclude=exclude, pure=True)
                item['atom_type'] = atom.atom_name()
                if atom.children is not None and 'children' in exclude:
                    item['children'] = [a.atom_name() for a in atom.children]
                if count > 0:
                    print(',')
                print(json.dumps(item, sort_keys=True, indent=2))
            else:
                exclude.remove('atom_type')
                print(atom.as_python(exclude))
            count += 1
        if check_children and atom.children is not None:
            for child in atom.children:
                count = IsoParser.show_atom(child, atom_types=atom_types, as_json=as_json,
                                            with_children=with_children, count=count)
        return count

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
        if args.json:
            print('[')
        if args.show:
            atom_types = set()
            with_children = set()
            for name in args.show.split(','):
                if name.endswith('+'):
                    name = name[:-1]
                    with_children.add(name)
                atom_types.add(name)
        for filename in args.mp4file:
            atoms = IsoParser.walk_atoms(filename, options=options)
            for atom in atoms:
                if args.tree:
                    atom.dump()
                if args.show:
                    IsoParser.show_atom(
                        atom, atom_types=atom_types, with_children=with_children,
                        as_json=args.json)
        if args.json:
            print(']')


if __name__ == "__main__":
    IsoParser.main()
