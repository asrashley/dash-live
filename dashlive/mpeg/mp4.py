#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from abc import ABC, abstractmethod
import argparse
import binascii
import copy
from dataclasses import dataclass, field
from datetime import datetime
import io
import json
import logging
import os
import re
import struct
from typing import AbstractSet, Any, BinaryIO, ClassVar, Optional, TypedDict, Union, cast, override
from weakref import ref, ReferenceType

import bitstring

from dashlive.utils.binary import Binary, HexBinary
from dashlive.utils.date_time import DateTimeField, from_iso_epoch, to_iso_epoch
from dashlive.utils.fio import FieldReader, BitsFieldReader, FieldWriter, BitsFieldWriter
from dashlive.utils.hexdump import hexdump_buffer
from dashlive.utils.io_with_offset import BytesIoWithOffset
from dashlive.utils.json_object import JsonObject
from dashlive.utils.list_of import ListOf
from dashlive.utils.object_with_fields import ObjectWithFields

from .event_bus import EventBus
from .nal import Nal

MODULE_PREFIX: str = 'dashlive.mpeg.mp4.'

@dataclass(slots=True, kw_only=True)
class Options:
    mode: str = 'r'
    lazy_load: bool = True
    debug: bool = False
    iv_size: int | None = None
    strict: bool = False
    bug_compatibility: str | set | None = None
    log: logging.Logger = field(init=False)

    def __post_init__(self):
        self.log = logging.getLogger('mp4')

    def has_bug(self, name):
        if self.bug_compatibility is None:
            return False
        if isinstance(self.bug_compatibility, str):
            self.bug_compatibility = {
                s.strip() for s in self.bug_compatibility.split(',')}
        return name in self.bug_compatibility


MP4_DESCRIPTORS: dict[int, type["Descriptor"]] = {}  # map from descriptor tag to class


def mp4descriptor(tag: int):
    def func(cls: type["Descriptor"]) -> type["Descriptor"]:
        MP4_DESCRIPTORS[tag] = cls
        return cls
    return func


class Mp4Atom(ObjectWithFields):
    include_atom_type: ClassVar[bool] = False
    ATOM_FOURCC: ClassVar[str] = ''

    _parent: ReferenceType["Mp4Atom"] | None = None
    _children: list["Mp4Atom"] | None = None
    _encoded: bytes | None = None
    _ev_bus: Optional[EventBus["Mp4Atom"]] = None
    atom_type: str
    header_size: int
    init_complete: bool = False
    options: Options
    payload_start: int
    position: int
    size: int

    OBJECT_FIELDS: ClassVar[dict[str, Any]] = {
        '_children': ListOf(ObjectWithFields),
        'options': Options,
    }
    DEFAULT_EXCLUDE: ClassVar[set[str]] = {'options', '_parent'}

    def __init__(self, **kwargs) -> None:
        _parent: Mp4Atom | None = None
        if 'children' in kwargs:
            kwargs['_children'] = kwargs['children']
            del kwargs['children']
        if 'parent' in kwargs:
            if kwargs['parent'] is not None:
                _parent = kwargs['parent']()
            del kwargs['parent']
            if _parent:
                kwargs['_parent'] = ref(_parent)
        super().__init__(**kwargs)
        atom_defaults = {
            '_encoded': None,
            'options': Options(),
            'position': 0,
            'size': 0,
        }
        if 'atom_type' not in kwargs and self.ATOM_FOURCC:
            atom_defaults['atom_type'] = self.ATOM_FOURCC
        elif 'atom_type' not in kwargs and self.DEFAULT_VALUES is not None and 'atom_type' in self.DEFAULT_VALUES:
            atom_defaults['atom_type'] = self.DEFAULT_VALUES['atom_type']
        self.apply_defaults(atom_defaults)
        atom_type: str | bytes = kwargs.get("atom_type", self.ATOM_FOURCC)
        if not atom_type:
            raise KeyError('Failed to determine atom type for %s' % self.__class__.__name__)
        self._fields.add('atom_type')
        if not isinstance(atom_type, str):
            atom_type = str(atom_type, 'ascii')
        self.atom_type = atom_type
        if self._parent:
            _parent = self._parent()
        if _parent:
            self._fullname = fr'{_parent._fullname}.{self.atom_type}'
        else:
            self._fullname = self.atom_type
        if self._children is not None:
            children: list[Mp4Atom] = []
            for ch in self._children:
                ch_atom: Mp4Atom
                if isinstance(ch, dict):
                    ch_atom = IsoParser.fromJSON(ch)
                else:
                    ch_atom = ch
                object.__setattr__(ch_atom, '_parent', ref(self))
                children.append(ch_atom)
            object.__setattr__(self, '_children', children)
        object.__setattr__(self, '_init_complete', True)

    def get(self, name: str) -> "Mp4Atom":
        if self._children is None:
            raise KeyError(name)
        if '.' in name:
            here, rest = name.split('.', 1)
            return self.get(here).get(rest)
        name = name.replace('-', '_')
        for c in self._children:
            if c.atom_type.replace('-', '_') == name:
                if isinstance(c, LazyLoadedBox):
                    # NOTE: lazy_load() will replace this atom in the parent _children list
                    atom = c.lazy_load()
                    return atom
                return c
        raise KeyError(name)

    def __getitem__(self, field: str) -> "Mp4Atom":
        return self.get(field)

    def __contains__(self, field: Any) -> bool:
        if isinstance(field, str):
            try:
                self.get(field)
                return True
            except KeyError:
                return False
        if isinstance(field, "Mp4Atom"):
            children = self.get_children()
            return field in children
        return False

    def __len__(self) -> int:
        if self._children is None:
            return 0
        return len(self._children)

    def trigger_change(self) -> None:
        if self.atom_type == 'wrap':
            return
        try:
            self._ev_bus.trigger(f'change.{self.atom_type}', self)
        except AttributeError:
            pass

    def _invalidate(self) -> None:
        if self._encoded is not None:
            self._encoded = None
            p: Mp4Atom | None = None
            if self._parent:
                p = self._parent()
            if p:
                p._invalidate()

    def __setattr__(self, name: str, value: Any) -> None:
        object.__setattr__(self, name, value)
        if name[0] == '_' or "_init_complete" not in self.__dict__ or not self.__getattribute__("_init_complete"):
            return
        if name in self.__dict__.get("_fields", set()):
            self._invalidate()
            self.trigger_change()

    def __delitem__(self, name: str) -> None:
        if self._children is None:
            raise KeyError(name)
        if '.' in name:
            index = name.rindex('.')
            atom = self.get(name[:index])
            del atom[name[index + 1:]]
            return
        name = name.replace('-', '_')
        for idx, c in enumerate(self._children):
            if c.atom_type.replace('-', '_') == name:
                self.remove_child(idx)
                return
        raise KeyError(name)

    def _field_repr(self, exclude: AbstractSet[str]) -> list[str]:
        if not self.include_atom_type:
            exclude = exclude.union({'atom_type', 'options'})
        return super()._field_repr(exclude)

    def _int_field_repr(self, fields: list[str], names: AbstractSet[str]) -> list[str]:
        for name in names:
            fields.append('%s=%d' % (name, self.__getattribute__(name)))
        return fields

    def get_children(self) -> list["Mp4Atom"]:
        if self._children is None:
            return []
        return self._children

    def set_children(self, children: list["Mp4Atom"]) -> None:
        self._children = children

    children = property(get_children, set_children)

    def find_atom(self, atom_type: bytes | str,
                  check_parent: bool = True,
                  recurse_children: bool = False,
                  no_exception: bool = False,
                  max_recursion: int = 100) -> Optional["Mp4Atom"]:
        # print(f'find_atom self={self.atom_type} search={atom_type} ' + f
        #       'up={check_parent} down={recurse_children}')
        if isinstance(atom_type, bytes):
            atom_type = str(atom_type, 'ascii')
        if self.atom_type == atom_type:
            return self
        children = self.get_children()
        for idx, ch in enumerate(children):
            if ch.atom_type == atom_type:
                if isinstance(ch, LazyLoadedBox):
                    # print(f'find_atom({atom_type}) requires loading')
                    self._children[idx] = ch.lazy_load()
                    return self._children[idx]
                return ch
            if recurse_children and max_recursion > 0:
                c = ch.find_atom(
                    atom_type, check_parent=check_parent,
                    recurse_children=True, no_exception=True,
                    max_recursion=(max_recursion - 1))
                if c is not None:
                    return c
        if check_parent and self._parent:
            p = self._parent()
            if p:
                return p.find_atom(
                    atom_type, check_parent=True, recurse_children=False,
                    no_exception=no_exception)
        if no_exception:
            return None
        raise AttributeError(atom_type)

    def find_child(self, atom_type: str | bytes) -> Optional["Mp4Atom"]:
        if self._children is None:
            return None
        if isinstance(atom_type, bytes):
            atom_type = str(atom_type, 'ascii')
        return self.find_atom(
            atom_type, check_parent=False, recurse_children=True, no_exception=True)

    def find_peer(self, atom_type: str) -> Optional["Mp4Atom"]:
        if self._parent is None:
            return None
        p = self._parent()
        if p is None:
            return None
        return p.find_atom(
            atom_type, check_parent=False, recurse_children=True,
            no_exception=True, max_recursion=0)

    def index(self, atom_type: Union[str, bytes, "Mp4Atom"]) -> int:
        if self._children is None:
            raise IndexError(f"{self.atom_type} has no children")

        if isinstance(atom_type, Mp4Atom):
            for idx, c in enumerate(self._children):
                if c.atom_type == atom_type.atom_type:
                    return idx
            raise IndexError(f"{repr(atom_type)}")

        if isinstance(atom_type, bytes):
            atom_type = str(atom_type, 'ascii')
        for idx, c in enumerate(self._children):
            if c.atom_type == atom_type:
                return idx
        raise IndexError(atom_type)

    def append_child(self, child: "Mp4Atom") -> None:
        if self.options.mode == 'r':
            raise PermissionError(
                'Adding atoms is not allowed for an MP4 file opened in read-only mode')
        self.options.log.debug(
            '%s: append_child "%s"', self._fullname, child.atom_type)
        object.__setattr__(child, '_parent', ref(self))
        if self._children is None:
            self._children = [child]
        else:
            self._children.append(child)
        if child.size:
            self.update_size(child.size)
        self.trigger_change()
        child.trigger_change()
        self._invalidate()

    def insert_child(self, index: int, child: "Mp4Atom") -> None:
        if self.options.mode == 'r':
            raise PermissionError(
                'Inserting atoms is not allowed for an MP4 file opened in read-only mode')
        self.options.log.debug(
            '%s: insert_child "%s" (%d bytes) at index %d', self._fullname,
            child.atom_type, child.size, index)
        self.trigger_change()
        object.__setattr__(child, '_parent', ref(self))
        if self._children is None:
            self._children = [child]
        else:
            self._children.insert(index, child)
        if child.size == 0:
            child.encode_as_bytes()
            assert child.size > 0
        self.update_size(child.size)
        child.trigger_change()
        self._invalidate()

    def remove_child(self, idx: int) -> None:
        if self.options.mode == 'r':
            raise PermissionError(
                'Removing atoms is not allowed for an MP4 file opened in read-only mode')
        if self._children is None:
            raise IndexError('Trying to remove a child from an atom with no children')
        child = self._children[idx]
        # print(f'remove child {child.atom_type} idx={idx} size={child.size}')
        del self._children[idx]
        if child.size:
            self.update_size(-child.size)
        self.trigger_change()
        self._invalidate()

    def replace_child_by_index(self, index: int, replacement: "Mp4Atom") -> None:
        if self._children is None:
            raise IndexError('Trying to replace an atom with no children')
        if index < 0 or index >= len(self._children):
            raise IndexError(f'Child index {index} out of range')
        old: Mp4Atom = self._children[index]
        if old.atom_type != replacement.atom_type:
            raise ValueError(f'Child atom type {old.atom_type} does not match replacement atom type {replacement.atom_type}')
        self._children[index] = replacement
        if replacement.size != old.size:
            self.update_size(replacement.size - old.size)

    def replace_child_by_atom(self, atom: "Mp4Atom", replacement: "Mp4Atom") -> None:
        # print(f"replace child {atom.atom_type} with {replacement.atom_type}")
        if atom == replacement:
            return
        assert atom.atom_type == replacement.atom_type
        if self._children is None:
            raise IndexError('Trying to replace an atom with no children')
        for idx, ch in enumerate(self._children):
            if ch == atom:
                # print(f'{self.atom_type}: replacing atom at index {idx}', type(replacement))
                self._children[idx] = replacement
                if replacement.size != ch.size:
                    self.update_size(replacement.size - ch.size)
                # print([f'{type(ch)}={ch.size}' for ch in self._children])
                return
        raise AttributeError(f'Failed to find atom "{atom.atom_type}" to replace')

    def update_size(self, delta: int) -> None:
        self.size += delta
        self.trigger_change()
        if self._parent is None:
            return
        p: Mp4Atom | None = self._parent()
        if p is None:
            return
        p.update_size(delta)
        if not p._children:
            return
        needs_update: bool = False
        for ch in p._children:
            if ch == self:
                needs_update = True
            elif needs_update:
                ch.position += delta

    def encode_as_bytes(self, only_children: bool = False) -> bytes:
        out = io.BytesIO()
        if only_children:
            if self._children is not None:
                for child in self._children:
                    child.encode(dest=out)
            self.post_encode_all(dest=out)
            self.size = out.tell()
        else:
            self.encode(dest=out)
        return out.getvalue()

    def encode(self, dest: BinaryIO, depth: int = 0) -> BinaryIO:
        self.position = dest.tell()
        if len(self.atom_type) > 4:
            # 16 hex chars + 'UUID()' == 38
            assert len(self.atom_type) == 38
            fourcc = b'uuid' + binascii.a2b_hex(self.atom_type[5:-1])
        else:
            assert len(self.atom_type) == 4
            fourcc = bytes(self.atom_type, 'ascii')
        self.options.log.debug('%s: encode %s pos=%d depth=%d', self._fullname,
                               self.classname(), self.position, depth)
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
            dest.write(struct.pack('>I', self.size))
            dest.write(fourcc)
            dest.write(self._encoded)
        else:
            dest.write(struct.pack('>I', 0))
            dest.write(fourcc)
            self.encode_fields(dest=dest)
            if self._children is not None:
                for child in self._children:
                    # print(f'{indent}{self.atom_type}: encode {idx}={child.atom_type}', type(child))
                    child.encode(dest=dest, depth=(depth + 1))
            self.size = dest.tell() - self.position
            # print(f'{indent}{self.atom_type}: {self.position} -> {out.tell()} ({self.size})')
            # replace the length field
            dest.seek(self.position)
            dest.write(struct.pack('>I', self.size))
            dest.seek(0, 2)  # seek to end
            if depth == 0:
                self.post_encode_all(dest=dest)
        self.options.log.debug('%s: produced %d bytes pos=(%d .. %d)',
                               self._fullname, self.size,
                               self.position, dest.tell())
        return dest

    @abstractmethod
    def encode_fields(self, dest: BinaryIO) -> None:
        pass

    def post_encode_all(self, dest: BinaryIO) -> None:
        if self._children is not None:
            for child in self._children:
                child.post_encode_all(dest)
        self.post_encode(dest)

    def post_encode(self, dest: BinaryIO) -> None:
        return

    def atom_name(self) -> str:
        return self.atom_type

    def dump(self, indent: str = '') -> None:
        atom_type = self.atom_name()
        print('{}{}: {:d} -> {:d} [{:d} bytes]'.format(
            indent, atom_type, self.position,
            self.position + self.size, self.size))
        if 'descriptors' in self._fields:
            for d in self.descriptors:
                d.dump(indent + '  ')
        if self._children is not None:
            for c in self._children:
                c.dump(indent + '  ')

    def _to_json(self, exclude: AbstractSet) -> JsonObject:
        rv = super()._to_json(exclude)
        if self._children is not None:
            rv['children'] = [
                ch.toJSON(exclude=exclude) for ch in self._children]
        return rv


Mp4Atom.OBJECT_FIELDS['_children'] = ListOf(Mp4Atom)

class AtomFactory[T](ABC):
    # list of box names required for parsing
    REQUIRED_PEERS: ClassVar[list[str] | None] = None

    parse_children: ClassVar[bool] = False

    def fourcc(self) -> str:
        """Returns the fourcc code for the atom type created by this factory"""
        atom_class: type[Mp4Atom] = cast(type[Mp4Atom], self.atom_type())
        return atom_class.ATOM_FOURCC

    @abstractmethod
    def atom_type(self) -> type[T]:
        """Returns the class of the atom type created by this factory"""
        pass

    def create(self, **kwargs) -> T:
        """Creates a new instance of the atom type created by this factory"""
        Atom: type[Mp4Atom] = cast(type[Mp4Atom], self.atom_type())
        fourcc: str = self.fourcc()
        if 'atom_type' in kwargs:
            if kwargs['atom_type'] != fourcc and fourcc != '????':
                raise ValueError(f"atom_type {kwargs['atom_type']} does not match expected fourcc {fourcc}")
            return cast(T, Atom(**kwargs))
        return cast(T, Atom(atom_type=fourcc, **kwargs))

    def classname(self) -> str:
        """Returns the class name for the atom type created by this factory"""
        return self.atom_type().__name__

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        """Parses an atom of the type created by this factory from the specified source, returning a dict of field values"""
        return AtomFactory.parse_header(src, options, **kwargs)

    def depends_upon(self) -> set[str]:
        """Returns a set of box names that this atom depends upon for parsing"""
        return set()

    @classmethod
    def parse_header(cls, src: BinaryIO, options: Options, **kwargs) -> dict[str, Any] | None:
        """
        Parses the initial MP4 atom header (size and type)
        from the specified source, returning a dict of field values.
        The returned dict must include the following fields:
        - atom_type: The type of the atom
        - position: The position of the atom in the source
        - size: The total size of the atom
        - header_size: The size of the atom header
        - _buffer: The raw bytes of the atom header
        """
        try:
            return kwargs['initial_data']
        except KeyError:
            pass
        position = src.tell()
        data = src.read(8)
        # hexdump_buffer(f'header position={position}', data)
        if not data or len(data) != 8:
            if options is not None:
                if len(data) == 0:
                    options.log.debug("EOS at %d", position)
                else:
                    options.log.debug(
                        'Failed to read box length. pos=%d', position)
            return None
        buf: list[bytes] = [data]
        size: int
        atom_type: str | bytes
        size, atom_type = struct.unpack('>I4s', data)
        if not atom_type or len(atom_type) != 4:
            if options:
                options.log.debug('Failed to read atom type. pos=%d', position)
            return None
        if size == 0:
            # A box size of 0 means the box extends to EOF. The size must
            # include the already-read header, so compute from the box start
            # position rather than the current position.
            current_pos = src.tell()
            src.seek(0, 2)  # seek to end
            eof_pos: int = src.tell()
            size = eof_pos - position
            src.seek(current_pos)
        elif size == 1:
            size_ext = src.read(8)
            buf.append(size_ext)
            size = struct.unpack('>Q', size_ext)[0]
            if not size:
                if options:
                    options.log.debug(
                        'Failed to read atom size. pos=%d', position)
                return None
        if atom_type == b'uuid':
            uuid_data = src.read(16)
            buf.append(uuid_data)
            uuid = str(binascii.b2a_hex(uuid_data), 'ascii')
            atom_type = f'UUID({uuid})'
        else:
            atom_type = str(atom_type, 'ascii')
        return {
            "atom_type": atom_type,
            "position": position,
            "size": size,
            "header_size": src.tell() - position,
            "_buffer": b''.join(buf),
        }


class WrapperIterator:
    _wrapper: "Wrapper"
    _current: int
    _end: int

    def __init__(self, wrapper: "Wrapper"):
        self._wrapper = wrapper
        self._current = 0
        if wrapper._children is None:
            self._end = 0
        else:
            self._end = len(wrapper._children)

    def __next__(self):
        if self._current >= self._end:
            raise StopIteration
        rv = self._wrapper.children[self._current]
        self._current += 1
        return rv


class Wrapper(Mp4Atom):
    ATOM_FOURCC = 'wrap'
    DEFAULT_VALUES = {
        'atom_type': 'wrap',
        'position': 0,
        'parent': None,
        '_children': [],
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        if self._children is None:
            self._children = []

    @override
    def encode(self, dest: BinaryIO, depth: int = 0) -> BinaryIO:
        assert depth == 0
        here: int = dest.tell()
        if self._children:
            for child in self._children:
                child.encode(dest=dest, depth=(depth + 1))
            self.post_encode_all(dest=dest)
        self.size = dest.tell() - here
        return dest

    def encode_fields(self, dest: BinaryIO) -> None:
        pass

    def __iter__(self):
        return WrapperIterator(self)


class UnknownBox(Mp4Atom):
    ATOM_FOURCC = '????'
    include_atom_type = True
    OBJECT_FIELDS = {
        'data': Binary,
    }
    OBJECT_FIELDS.update(Mp4Atom.OBJECT_FIELDS)
    data: Binary | bytes | None

    def encode_fields(self, dest: BinaryIO) -> None:
        if self.data is not None:
            try:
                dest.write(self.data.data)
            except AttributeError:
                # self.data is not wrapped in a Binary() object
                dest.write(cast(bytes, self.data))


class UnknownBoxFactory(AtomFactory[UnknownBox]):
    parse_children = False

    def atom_type(self) -> type[UnknownBox]:
        return UnknownBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent=parent, options=options, **kwargs)
        if rv is None:
            return None
        size = rv["size"] - rv["header_size"]
        if size > 0:
            rv["data"] = src.read(size)
        else:
            rv["data"] = None
        return rv


class LazyLoadedBox(Mp4Atom):
    OBJECT_FIELDS = {
        '_buffer': bytes,
        **Mp4Atom.OBJECT_FIELDS,
    }
    include_atom_type = True
    debug = False
    _box_factory: AtomFactory
    _buffer: bytes
    _real_atom: Mp4Atom | None = None

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._init_complete = True

    @classmethod
    def parse(cls,
              src: BinaryIO,
              parent: Mp4Atom | None,
              options: Options,
              initial_data: dict[str, Any]) -> dict[str, Any]:
        # print(f"LazyLoadedBox.parse {initial_data['atom_type']} pos={initial_data['position']} size={initial_data['size']}",
        #       parent.__class__.__name__ if parent else None)
        rv = initial_data
        size = rv["size"] - rv["header_size"]
        if size > 0:
            rv['_buffer'] += src.read(size)
        return rv

    @override
    def encode(self, dest: BinaryIO, depth: int = 0) -> BinaryIO:
        if self._real_atom is not None:
            return self._real_atom.encode(dest, depth)
        self.position = dest.tell()
        self.options.log.debug('%s: encode lazy %s pos=%d', self._fullname,
                               self.atom_type, self.position)
        # print(f'encode {self.atom_type} LazyLoadedBox before', self.position)
        dest.write(self._buffer)
        # print('encode LazyLoadedBox after', dest.tell())
        if depth == 0:
            self.post_encode_all(dest)
        return dest

    def encode_fields(self, dest: BinaryIO) -> None:
        raise RuntimeError(
            'encode_fields should not be called for LazyLoadedBox')

    def _to_json(self, exclude: AbstractSet) -> JsonObject:
        if self._real_atom is not None:
            return self._real_atom._to_json(exclude=exclude)
        atom = self.lazy_load()
        return atom._to_json(exclude=exclude)

    def get(self, name: str) -> Mp4Atom:
        atom = self.lazy_load()
        return atom.get(name)

    @override
    def get_children(self) -> list[Mp4Atom]:
        if self._real_atom is not None:
            if self._real_atom._children is None:
                return []
            return cast(list[Mp4Atom], self._real_atom._children)
        if not self._box_factory.parse_children:
            return []
        self.options.log.debug('%s: get_children() requires loading', self._fullname)
        atom = self.lazy_load()
        if atom._children is None:
            return []
        return cast(list[Mp4Atom], atom._children)

    def __setattr__(self, name, value):
        if name[0] == '_' or "_init_complete" not in self.__dict__ or not self.__getattribute__("_init_complete"):
            object.__setattr__(self, name, value)
            return
        if name == 'position':
            object.__setattr__(self, name, value)
            return
        if self.__getattribute__("_real_atom") is None:
            self.lazy_load()
        assert self._real_atom is not None
        setattr(self._real_atom, name, value)
        object.__setattr__(self, name, value)

    def atom_changed(self, ev_name: str, atom: Mp4Atom) -> None:
        if self._real_atom is None:
            self.lazy_load()

    def lazy_load(self) -> Mp4Atom:
        if self._real_atom is not None:
            return self._real_atom
        self.options.log.debug(
            '%s: lazy loading %d bytes (%d .. %d)', self._fullname, self.size,
            self.position, self.position + self.size)
        assert self._parent is not None
        parent: Mp4Atom | None = self._parent()
        assert parent is not None
        index: int = parent.index(self)
        for name in self._box_factory.depends_upon():
            self._ev_bus.off(f'change.{name}', self.atom_changed)
        hdr = {
            "atom_type": self.atom_type,
            "position": self.position,
            "size": self.size,
            "header_size": self.header_size,
        }

        if self.options.log.isEnabledFor(logging.DEBUG):
            self.options.log.debug('lazy loading %s', self.atom_type)
            if self.debug:
                hexdump_buffer('self.buffer', self._buffer, 32)
        assert len(self._buffer) == self.size
        src = BytesIoWithOffset(self._buffer, self.position)
        src.seek(self.header_size, os.SEEK_CUR)  # skip initial header data
        kwargs = self._box_factory.parse(
            src, parent, options=self.options, initial_data=hdr)
        assert kwargs is not None
        kwargs['_parent'] = ref(parent) if parent else None
        kwargs['options'] = self.options
        atom: Mp4Atom = self._box_factory.create(**kwargs)
        assert atom.atom_type == self.atom_type
        atom._ev_bus = self._ev_bus
        self._real_atom = atom
        if parent:
            parent.replace_child_by_index(index, atom)
        if self._box_factory.parse_children:
            atom.payload_start = src.tell()
            atom._children = IsoParser.load(src, atom, options=self.options)
        self._children = atom._children
        for name in atom._fields:
            object.__setattr__(
                self, name, object.__getattribute__(atom, name))
        try:
            del self._buffer
        except AttributeError:
            pass
        here: int = src.tell()
        src.close()
        if self.options.strict and here != (self.position + self.size):
            raise RuntimeError(
                f'Expected position {self.position + self.size} but actual position {here}')
        if parent is not None:
            # as a change in this atom might impact the values in other atoms, load the peer
            # atoms that depend upon this one
            todo: list[LazyLoadedBox] = []
            children = parent.get_children()
            for ch in children:
                if ch == self or ch == atom:
                    continue
                if isinstance(ch, LazyLoadedBox) and ch._box_factory and atom.atom_type in ch._box_factory.depends_upon():
                    todo.append(ch)
            for peer in todo:
                peer.lazy_load()
        return atom


class FileTypeBox(Mp4Atom):
    ATOM_FOURCC = 'ftyp'
    OBJECT_FIELDS = {
        "compatible_brands": ListOf(str),
    }
    compatible_brands: list[str]
    major_brand: str
    minor_version: int

    def encode_fields(self, dest: BinaryIO) -> None:
        d = FieldWriter(self, dest)
        d.write(4, 'major_brand')
        d.write('I', 'minor_version')
        for cb in self.compatible_brands:
            d.write(4, 'compatible_brand', value=bytes(cb, 'ascii'))


class FileTypeBoxFactory(AtomFactory[FileTypeBox]):
    def atom_type(self) -> type[FileTypeBox]:
        return FileTypeBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options, **kwargs)
        if rv is None:
            return None
        r = FieldReader("FileTypeBox", src, rv)
        rv['major_brand'] = str(r.get(4, 'major_brand'), 'ascii')
        r.read('I', 'minor_version')
        size = rv["size"] - rv["header_size"] - 8
        rv['compatible_brands'] = []
        while size > 3:
            cb: bytes = cast(bytes, r.get(4, 'compatible_brand'))
            if len(cb) != 4:
                break
            rv['compatible_brands'].append(str(cb, 'ascii'))
            size -= 4
        return rv


class SegmentTypeBox(FileTypeBox):
    ATOM_FOURCC = 'styp'


class SegmentTypeBoxFactory(FileTypeBoxFactory):
    def atom_type(self) -> type[SegmentTypeBox]:
        return SegmentTypeBox


class Descriptor(ObjectWithFields):
    OBJECT_FIELDS: ClassVar[dict[str, Any]] = {
        'children': ListOf(ObjectWithFields),
        'data': Binary,
    }

    REQUIRED_FIELDS = {
        'tag': int,
    }

    _fullname: str
    _parent: Union[ReferenceType[Mp4Atom], ReferenceType["Descriptor"], None] = None
    _encoded: bytes | None = None
    children: list[ObjectWithFields]
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
            self._parent = ref(parent)
        else:
            self._fullname = self.classname()

    @classmethod
    def load(cls,
             src: BinaryIO,
             parent: Union["Descriptor", Mp4Atom, None],
             options: Options,
             **kwargs) -> "Descriptor":
        if options is None:
            options = Options()
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
                      parent: Union["Descriptor", Mp4Atom, None],
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
                      parent: Union["Descriptor", Mp4Atom, None],
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
                      parent: Union["Descriptor", Mp4Atom, None],
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
                      parent: Union["Descriptor", Mp4Atom, None],
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
                      parent: Union["Descriptor", Mp4Atom, None],
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


class FullBox(Mp4Atom):
    FB_HEADER_SIZE: ClassVar[int] = 4  # number of bytes used for the version and flags fields

    version: int
    flags: int

    def encode_fields(self, dest: BinaryIO) -> None:
        d = FieldWriter(self, dest)
        d.write('B', 'version')
        d.write(3, 'flags', value=struct.pack('>I', self.flags)[1:])
        self.encode_box_fields(dest)

    @abstractmethod
    def encode_box_fields(self, dest: BinaryIO) -> None:
        pass


class FullBoxFactory[T](AtomFactory[T]):
    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv, debug=options.debug)
        r.read("B", "version")
        r.read('3I', "flags")
        return rv


class BoxWithChildren(Mp4Atom):
    include_atom_type = True

    def encode_fields(self, dest: BinaryIO) -> None:
        pass


class BoxWithChildrenFactory[T](AtomFactory[T]):
    parse_children = True


class MovieBox(BoxWithChildren):
    ATOM_FOURCC = 'moov'
    include_atom_type = False


class MovieBoxFactory(BoxWithChildrenFactory[MovieBox]):
    def atom_type(self) -> type[MovieBox]:
        return MovieBox


class TrackBox(BoxWithChildren):
    ATOM_FOURCC = 'trak'
    include_atom_type = False


class TrackBoxFactory(BoxWithChildrenFactory[TrackBox]):
    def atom_type(self) -> type[TrackBox]:
        return TrackBox


class TrackFragmentBox(BoxWithChildren):
    ATOM_FOURCC = 'traf'


class TrackFragmentBoxFactory(BoxWithChildrenFactory[TrackFragmentBox]):
    def atom_type(self) -> type[TrackFragmentBox]:
        return TrackFragmentBox


class MovieFragmentBox(BoxWithChildren):
    ATOM_FOURCC = 'moof'


class MovieFragmentBoxFactory(BoxWithChildrenFactory[MovieFragmentBox]):
    def atom_type(self) -> type[MovieFragmentBox]:
        return MovieFragmentBox


class MediaInformationBox(BoxWithChildren):
    ATOM_FOURCC = 'minf'


class MediaInformationBoxFactory(BoxWithChildrenFactory[MediaInformationBox]):
    def atom_type(self) -> type[MediaInformationBox]:
        return MediaInformationBox


class MovieExtendsBox(BoxWithChildren):
    ATOM_FOURCC = 'mvex'


class MovieExtendsBoxFactory(BoxWithChildrenFactory[MovieExtendsBox]):
    def atom_type(self) -> type[MovieExtendsBox]:
        return MovieExtendsBox


class MediaDataBox(BoxWithChildren):
    ATOM_FOURCC = 'mdia'


class MediaDataBoxFactory(BoxWithChildrenFactory[MediaDataBox]):
    def atom_type(self) -> type[MediaDataBox]:
        return MediaDataBox


class SchemaInformationBox(BoxWithChildren):
    ATOM_FOURCC = 'schi'


class SchemaInformationBoxFactory(BoxWithChildrenFactory[SchemaInformationBox]):
    def atom_type(self) -> type[SchemaInformationBox]:
        return SchemaInformationBox


class ProtectionSchemeInformationBox(BoxWithChildren):
    ATOM_FOURCC = 'sinf'


class ProtectionSchemeInformationBoxFactory(BoxWithChildrenFactory[ProtectionSchemeInformationBox]):
    def atom_type(self) -> type[ProtectionSchemeInformationBox]:
        return ProtectionSchemeInformationBox


class SampleTableBox(BoxWithChildren):
    ATOM_FOURCC = 'stbl'


class SampleTableBoxFactory(BoxWithChildrenFactory[SampleTableBox]):
    def atom_type(self) -> type[SampleTableBox]:
        return SampleTableBox


class UserDataBox(BoxWithChildren):
    ATOM_FOURCC = 'udta'


class UserDataBoxFactory(BoxWithChildrenFactory[UserDataBox]):
    def atom_type(self) -> type[UserDataBox]:
        return UserDataBox


class MovieHeaderBox(FullBox):
    ATOM_FOURCC = 'mvhd'
    OBJECT_FIELDS = {
        "creation_time": DateTimeField,
        "modification_time": DateTimeField,
        "matrix": ListOf(int),
    }
    duration: int
    creation_time: datetime
    modification_time: datetime
    rate: float
    volume: float
    timescale: int
    matrix: list[int]
    next_track_id: int

    def __setattr__(self, name, value):
        if name == 'duration':
            if self.version == 0 and self.duration.bit_length() > 32:
                self.version = 1
                self.update_size(4)
        elif name == 'version':
            if value == 0 and self.duration.bit_length() > 32:
                raise ValueError('Duration is too large to use version 0 header')
        super().__setattr__(name, value)

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


class MovieHeaderBoxFactory(FullBoxFactory[MovieHeaderBox]):
    def atom_type(self) -> type[MovieHeaderBox]:
        return MovieHeaderBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv, debug=options.debug)
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


class SampleEntry(Mp4Atom):
    def encode_fields(self, dest: BinaryIO) -> None:
        dest.write(b'\0' * 6)  # reserved
        dest.write(struct.pack('>H', self.data_reference_index))


class SampleEntryFactory[T](AtomFactory[T]):
    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv, debug=options.debug)
        r.skip(6)  # reserved
        r.read('H', 'data_reference_index')
        return rv


class VisualSampleEntry(SampleEntry):
    version: int
    revision: int
    vendor: int
    temporal_quality: int
    spatial_quality: int
    width: int
    height: int
    compressorname: str
    horizresolution: float
    vertresolution: float

    def encode_fields(self, dest: BinaryIO) -> None:
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


class VisualSampleEntryFactory[T](SampleEntryFactory[T]):
    parse_children = True

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv, debug=options.debug)
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


class AVC1SampleEntry(VisualSampleEntry):
    ATOM_FOURCC = 'avc1'


class AVC1SampleEntryFactory(VisualSampleEntryFactory[AVC1SampleEntry]):
    def atom_type(self) -> type[AVC1SampleEntry]:
        return AVC1SampleEntry


class AVC3SampleEntry(VisualSampleEntry):
    ATOM_FOURCC = 'avc3'


class AVC3SampleEntryFactory(VisualSampleEntryFactory[AVC3SampleEntry]):
    def atom_type(self) -> type[AVC3SampleEntry]:
        return AVC3SampleEntry


class HEV1SampleEntry(VisualSampleEntry):
    ATOM_FOURCC = 'hev1'

class HEV1SampleEntryFactory(VisualSampleEntryFactory[HEV1SampleEntry]):
    def atom_type(self) -> type[HEV1SampleEntry]:
        return HEV1SampleEntry


class HVC1SampleEntry(VisualSampleEntry):
    ATOM_FOURCC = 'hvc1'


class HVC1SampleEntryFactory(VisualSampleEntryFactory[HVC1SampleEntry]):
    def atom_type(self) -> type[HVC1SampleEntry]:
        return HVC1SampleEntry


class EncryptedSampleEntry(VisualSampleEntry):
    ATOM_FOURCC = 'encv'


class EncryptedSampleEntryFactory(VisualSampleEntryFactory[EncryptedSampleEntry]):
    def atom_type(self) -> type[EncryptedSampleEntry]:
        return EncryptedSampleEntry


# See 3GPP TS 26.245 v8.0.0 section 5.16

class FontRecord(ObjectWithFields):
    font_id: int
    font: str

    @classmethod
    def parse(cls, src: BinaryIO, parent: dict[str, Any]) -> dict[str, Any]:
        offset: int = src.tell() - parent['position']
        rv: dict[str, Any] = {
            "offset": offset,
        }
        r: FieldReader = FieldReader(cls.classname(), src, rv)
        r.read('H', 'font_id')
        name_len: int = cast(int, r.get('B', 'font-name-length'))
        r.read(f'S{name_len}', 'font')
        rv['size'] = 3 + name_len
        return rv

    def encode(self, dest: BinaryIO) -> BinaryIO:
        w = FieldWriter(self, dest)
        w.write('H', 'font_id')
        w.write('B', 'font-name-length', value=len(self.font))
        w.write('S', 'font')
        return dest


class FontTableBox(Mp4Atom):
    ATOM_FOURCC = 'ftab'
    OBJECT_FIELDS = {
        "font_table": ListOf(FontRecord),
    }
    font_table: list[FontRecord]

    def encode_fields(self, dest: BinaryIO) -> None:
        d: FieldWriter = FieldWriter(self, dest)
        d.write('H', 'entry-count', value=len(self.font_table))
        for font in self.font_table:
            font.encode(dest)


class FontTableBoxFactory(AtomFactory[FontTableBox]):
    def atom_type(self) -> type[FontTableBox]:
        return FontTableBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv: dict[str, Any] | None = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r: FieldReader = FieldReader(self.classname(), src, rv, debug=options.debug)
        entry_count: int = cast(int, r.get('H', 'entry-count'))
        rv['font_table'] = []
        for _idx in range(entry_count):
            rv['font_table'].append(FontRecord.parse(src, rv))
        return rv


class BoxRecord(ObjectWithFields):
    @classmethod
    def parse(cls, src: BinaryIO, parent: dict[str, Any]) -> dict[str, Any]:
        rv: dict[str, Any] = {
            "offset": src.tell() - parent['position'],
            "size": 8,
        }
        r: FieldReader = FieldReader(cls.classname(), src, rv)
        r.read('H', 'top')
        r.read('H', 'left')
        r.read('H', 'bottom')
        r.read('H', 'right')
        return rv

    def encode(self, dest: BinaryIO) -> BinaryIO:
        w: FieldWriter = FieldWriter(self, dest)
        w.write('H', 'top')
        w.write('H', 'left')
        w.write('H', 'bottom')
        w.write('H', 'right')
        return dest


class StyleRecord(ObjectWithFields):
    @classmethod
    def parse(cls, src: BinaryIO, parent: dict[str, Any]) -> dict[str, Any]:
        rv: dict[str, Any] = {
            "offset": src.tell() - parent['position'],
            "size": 8,
        }
        r: FieldReader = FieldReader(cls.classname(), src, rv)
        r.read('H', 'start_char')
        r.read('H', 'end_char')
        r.read('H', 'font_id')
        r.read('B', 'face_style_flags')
        r.read('B', 'font_size')
        r.read(4, 'text_colour')
        return rv

    def encode(self, dest: BinaryIO) -> BinaryIO:
        w: FieldWriter = FieldWriter(self, dest)
        w.write('H', 'start_char')
        w.write('H', 'end_char')
        w.write('H', 'font_id')
        w.write('B', 'face_style_flags')
        w.write('B', 'font_size')
        w.write(4, 'text_colour')
        return dest


class TextSampleEntry(SampleEntry):
    ATOM_FOURCC = 'tx3g'
    OBJECT_FIELDS: ClassVar[dict[str, Any]] = {
        "default_text_box": BoxRecord,
        "default_style": StyleRecord,
        "background_colour": HexBinary,
    }
    default_text_box: BoxRecord
    default_style: StyleRecord
    display_flags: int
    horizontal_justification: int
    vertical_justification: int
    background_colour: HexBinary

    def encode_fields(self, dest: BinaryIO) -> None:
        super().encode_fields(dest)
        w: FieldWriter = FieldWriter(self, dest)
        w.write('I', 'display_flags')
        w.write('B', 'horizontal_justification')  # should be signed 8 bit
        w.write('B', 'vertical_justification')  # should be signed 8 bit
        w.write(4, 'background_colour')
        self.default_text_box.encode(dest)
        self.default_style.encode(dest)


class TextSampleEntryFactory(SampleEntryFactory[TextSampleEntry]):
    parse_children = True

    def atom_type(self) -> type[TextSampleEntry]:
        return TextSampleEntry

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options, **kwargs)
        if rv is None:
            return None
        r: FieldReader = FieldReader(self.classname(), src, rv, debug=options.debug)
        r.read('I', 'display_flags')
        r.read('B', 'horizontal_justification')  # should be signed 8 bit
        r.read('B', 'vertical_justification')  # should be signed 8 bit
        r.read(4, 'background_colour')
        rv['default_text_box'] = BoxRecord.parse(r.src, rv)
        rv['default_style'] = StyleRecord.parse(r.src, rv)
        return rv


class WebVTTConfigurationBox(Mp4Atom):
    ATOM_FOURCC = 'vttC'
    config: str

    def encode_fields(self, dest):
        super().encode_fields(dest)
        dest.write(bytes(self.config, 'utf-8'))


class WebVTTConfigurationBoxFactory(AtomFactory[WebVTTConfigurationBox]):
    def atom_type(self) -> type[WebVTTConfigurationBox]:
        return WebVTTConfigurationBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options, **kwargs)
        if rv is None:
            return None
        rv['config'] = str(src.read(rv['size'] - rv['header_size']), 'utf-8')
        return rv


class BitRateBox(Mp4Atom):
    ATOM_FOURCC = 'btrt'
    bufferSizeDB: int
    maxBitrate: int
    avgBitrate: int

    def encode_fields(self, dest):
        d = FieldWriter(self, dest, debug=self.options.debug)
        d.write('I', 'bufferSizeDB')
        d.write('I', 'maxBitrate')
        d.write('I', 'avgBitrate')


class BitRateBoxFactory(AtomFactory[BitRateBox]):
    def atom_type(self) -> type[BitRateBox]:
        return BitRateBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv, debug=options.debug)
        r.read('I', 'bufferSizeDB')
        r.read('I', 'maxBitrate')
        r.read('I', 'avgBitrate')
        return rv


class PlainTextSampleEntry(SampleEntry):
    pass


class WVTTSampleEntry(PlainTextSampleEntry):
    ATOM_FOURCC = 'wvtt'


class WVTTSampleEntryFactory(SampleEntryFactory[WVTTSampleEntry]):
    parse_children = True

    def atom_type(self) -> type[WVTTSampleEntry]:
        return WVTTSampleEntry


class XMLSubtitleSampleEntry(SampleEntry):
    ATOM_FOURCC = 'stpp'
    namespace: str
    schema_location: str
    mime_types: str
    mime: "MimeBox"

    def encode_fields(self, dest):
        super().encode_fields(dest)
        d = FieldWriter(self, dest, debug=self.options.debug)
        d.write('S0', 'namespace')
        d.write('S0', 'schema_location')
        d.write('S0', 'mime_types')


class XMLSubtitleSampleEntryFactory(SampleEntryFactory[XMLSubtitleSampleEntry]):
    parse_children = True

    def atom_type(self) -> type[XMLSubtitleSampleEntry]:
        return XMLSubtitleSampleEntry

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv, debug=options.debug)
        r.read('S0', 'namespace')
        r.read('S0', 'schema_location')
        r.read('S0', 'mime_types')
        return rv


class MimeBox(FullBox):
    ATOM_FOURCC = 'mime'
    content_type: str

    def encode_box_fields(self, dest):
        d = FieldWriter(self, dest, debug=self.options.debug)
        d.write('S0', 'content_type')


class MimeBoxFactory(FullBoxFactory[MimeBox]):
    def atom_type(self) -> type[MimeBox]:
        return MimeBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options, **kwargs)
        if rv is None:
            return None
        rv['content_type'] = src.read(rv['size'] - rv['header_size'] - 4)
        while rv['content_type'][-1] == 0:
            rv['content_type'] = rv['content_type'][:-1]
        rv['content_type'] = str(rv['content_type'], 'ascii')
        return rv


class AVCConfigurationBox(Mp4Atom):
    ATOM_FOURCC = 'avcC'
    OBJECT_FIELDS = {
        'sps': ListOf(Binary),
        'sps_ext': ListOf(Binary),
        'pps': ListOf(Binary),
    }
    configurationVersion: int
    AVCProfileIndication: int
    profile_compatibility: int
    AVCLevelIndication: int
    lengthSizeMinusOne: int
    sps: list[bytes]
    pps: list[bytes]
    chroma_format: int
    luma_bit_depth: int
    chroma_bit_depth: int
    sps_ext: list[bytes]

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


class AVCConfigurationBoxFactory(AtomFactory[AVCConfigurationBox]):
    def atom_type(self) -> type[AVCConfigurationBox]:
        return AVCConfigurationBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv, debug=options.debug)
        r.read('B', "configurationVersion")
        r.read('B', "AVCProfileIndication")
        r.read('B', "profile_compatibility")
        r.read('B', "AVCLevelIndication")
        r.read('B', "lengthSizeMinusOne", mask=0x03)
        numOfSequenceParameterSets: int = r.get('B', "numOfSequenceParameterSets", mask=0x1F)
        rv["sps"] = []
        for i in range(numOfSequenceParameterSets):
            sequenceParameterSetLength = struct.unpack('>H', src.read(2))[0]
            sequenceParameterSetNALUnit = src.read(sequenceParameterSetLength)
            rv["sps"].append(sequenceParameterSetNALUnit)
        numOfPictureParameterSets: int = r.get('B', 'numOfPictureParameterSets')
        rv["pps"] = []
        for i in range(numOfPictureParameterSets):
            pictureParameterSetLength = struct.unpack('>H', src.read(2))[0]
            pictureParameterSetNALUnit = src.read(pictureParameterSetLength)
            rv["pps"].append(pictureParameterSetNALUnit)
        end = rv["position"] + rv["size"]
        if AVCConfigurationBox.is_ext_profile(rv["AVCProfileIndication"]) and (end - src.tell()) > 3:
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


class HevcNalArray(ObjectWithFields):
    OBJECT_FIELDS = {
        'nal_units': ListOf(Binary),
    }

    @classmethod
    def parse(cls, reader: BitsFieldReader) -> dict[str, Any]:
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
class HEVCConfigurationBox(Mp4Atom):
    ATOM_FOURCC = 'hvcC'
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


class HEVCConfigurationBoxFactory(AtomFactory[HEVCConfigurationBox]):
    def atom_type(self) -> type[HEVCConfigurationBox]:
        return HEVCConfigurationBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r: BitsFieldReader = BitsFieldReader(self.classname(), src, rv, rv["size"] - rv["header_size"])
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


class PixelAspectRatioBox(Mp4Atom):
    ATOM_FOURCC = 'pasp'
    h_spacing: int
    v_spacing: int

    def encode_fields(self, dest):
        d = FieldWriter(self, dest)
        d.write('I', 'h_spacing')
        d.write('I', 'v_spacing')


class PixelAspectRatioBoxFactory(AtomFactory[PixelAspectRatioBox]):
    def atom_type(self) -> type[PixelAspectRatioBox]:
        return PixelAspectRatioBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        r.read('I', 'h_spacing')
        r.read('I', 'v_spacing')
        return rv


class AudioSampleEntry(SampleEntry):
    def encode_fields(self, dest):
        super().encode_fields(dest)
        dest.write(b'\0' * 8)  # reserved
        dest.write(struct.pack('>H', self.channel_count))
        dest.write(struct.pack('>H', self.sample_size))
        dest.write(b'\0' * 4)  # reserved
        dest.write(struct.pack('>H', self.sampling_frequency))
        dest.write(b'\0' * 2)  # reserved


class AudioSampleEntryFactory[T](SampleEntryFactory[T]):
    parse_children = True

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options, **kwargs)
        if rv is None:
            return None
        src.read(8)  # reserved
        rv["channel_count"] = struct.unpack('>H', src.read(2))[0]
        rv["sample_size"] = struct.unpack('>H', src.read(2))[0]
        src.read(4)  # reserved
        rv["sampling_frequency"] = struct.unpack('>H', src.read(2))[0]
        src.read(2)  # reserved
        return rv


class EC3SampleEntry(AudioSampleEntry):
    ATOM_FOURCC = 'ec-3'


class EC3SampleEntryFactory(AudioSampleEntryFactory[EC3SampleEntry]):
    def atom_type(self) -> type[EC3SampleEntry]:
        return EC3SampleEntry


class AC3SampleEntry(AudioSampleEntry):
    ATOM_FOURCC = 'ac-3'


class AC3SampleEntryFactory(AudioSampleEntryFactory[AC3SampleEntry]):
    def atom_type(self) -> type[AC3SampleEntry]:
        return AC3SampleEntry


class EAC3SubStream(ObjectWithFields):
    DEFAULT_EXCLUDE = {'src'}

    @classmethod
    def parse(cls, r):
        r.read(2, 'fscod')
        r.read(5, 'bsid')
        r.read(5, 'bsmod')
        r.read(3, 'acmod')
        r.kwargs['channel_count'] = EAC3SpecificBox.ACMOD_NUM_CHANS[r.kwargs['acmod']]
        r.kwargs['sampling_frequency'] = EAC3SpecificBox.FSCOD_SAMPLE_RATE[r.kwargs['fscod']]
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
class EAC3SpecificBox(Mp4Atom):
    ATOM_FOURCC = 'dec3'
    ACMOD_NUM_CHANS: ClassVar[list[int]] = [2, 1, 2, 3, 3, 4, 4, 5]
    FSCOD_SAMPLE_RATE: ClassVar[list[int]] = [48000, 44100, 32000, 0]

    OBJECT_FIELDS = {
        "substreams": ListOf(EAC3SubStream),
    }
    OBJECT_FIELDS.update(Mp4Atom.OBJECT_FIELDS)

    substreams: list[EAC3SubStream]
    data_rate: int
    flag_ec3_extension_type_a: bool = False
    complexity_index_type_a: int | None = None

    def encode_fields(self, dest) -> None:
        ba = bitstring.BitArray()
        num_ind_sub: int = len(self.substreams)
        ba.append(bitstring.pack('uint:13, uint:3', self.data_rate,
                                 num_ind_sub - 1))
        for s in self.substreams:
            s.encode_fields(ba)
        if 'flag_ec3_extension_type_a' in self._fields:
            ba.append(bitstring.pack('uint:7, bool, uint:8', 0,
                                     self.flag_ec3_extension_type_a,
                                     self.complexity_index_type_a))
        dest.write(ba.bytes)


class EAC3SpecificBoxFactory(AtomFactory[EAC3SpecificBox]):
    def atom_type(self) -> type[EAC3SpecificBox]:
        return EAC3SpecificBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r: BitsFieldReader = BitsFieldReader(self.classname(), src, rv, size=None)
        r.read(13, "data_rate")
        num_ind_sub: int = r.get(3, "num_ind_sub") + 1
        rv["substreams"] = []
        for _ in range(num_ind_sub):
            r2 = r.duplicate("EAC3SubStream", {})
            EAC3SubStream.parse(r2)
            rv["substreams"].append(EAC3SubStream(**r2.kwargs))
        if (r.bitpos() + 16) <= r.bitsize:
            r.get(7, 'reserved')
            r.read(1, 'flag_ec3_extension_type_a')
            r.read(8, 'complexity_index_type_a')
        return rv


class AC3SpecificBox(Mp4Atom):
    ATOM_FOURCC = 'dac3'
    SAMPLE_RATES: ClassVar[list[int]] = [48000, 44100, 32000, 0]
    CHANNEL_CONFIGURATIONS: ClassVar[list[tuple[int, str]]] = [
        (2, "1 + 1 (Ch1, Ch2)"),
        (1, "1/0 (C)"),
        (2, "2/0 (L, R)"),
        (3, "3/0 (L, C, R)"),
        (3, "2/1 (L, R, S)"),
        (4, "3/1 (L, C, R, S)"),
        (4, "2/2 (L, R, SL, SR)"),
        (5, "3/2 (L, C, R, SL, SR)"),
    ]

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


class AC3SpecificBoxFactory(AtomFactory[AC3SpecificBox]):
    def atom_type(self) -> type[AC3SpecificBox]:
        return AC3SpecificBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = BitsFieldReader(self.classname(), src, rv, rv["size"] - rv["header_size"])
        r.read(2, 'fscod')
        r.read(5, 'bsid')
        r.read(3, 'bsmod')
        r.read(3, 'acmod')
        r.read(1, 'lfe')
        r.read(5, 'bitrate_code')
        r.get(5, 'reserved')
        rv['sampling_frequency'] = AC3SpecificBox.SAMPLE_RATES[rv["fscod"]]
        rv['channel_count'], rv['channel_configuration'] = AC3SpecificBox.CHANNEL_CONFIGURATIONS[rv['acmod']]
        if rv['lfe']:
            rv['channel_count'] += 1
        return rv


class OriginalFormatBox(Mp4Atom):
    ATOM_FOURCC = 'frma'
    data_format: str

    def encode_fields(self, dest):
        dest.write(bytes(self.data_format, 'ascii'))


class OriginalFormatBoxFactory(AtomFactory[OriginalFormatBox]):
    def atom_type(self) -> type[OriginalFormatBox]:
        return OriginalFormatBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        rv["data_format"] = str(src.read(4), 'ascii')
        return rv


# see table 6.3 of 3GPP TS 26.244 V12.3.0
class MP4AudioSampleEntry(Mp4Atom):
    ATOM_FOURCC = 'mp4a'

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


class MP4AudioSampleEntryFactory(AtomFactory[MP4AudioSampleEntry]):
    parse_children = True

    def atom_type(self) -> type[MP4AudioSampleEntry]:
        return MP4AudioSampleEntry

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        r.get(6, 'reserved')  # (8)[6] reserved
        r.read('H', "data_reference_index")
        r.get(16, 'reserved')  # reserved 8,2,2,4
        r.read('H', "timescale")
        r.get(2, 'reserved')  # (16) reserved
        return rv


class EncryptedMP4A(MP4AudioSampleEntry):
    ATOM_FOURCC = 'enca'


class EncryptedMP4AFactory(MP4AudioSampleEntryFactory):
    def atom_type(self) -> type[EncryptedMP4A]:
        return EncryptedMP4A


class ESDescriptorBox(FullBox):
    ATOM_FOURCC = 'esds'
    OBJECT_FIELDS = {
        'descriptors': ListOf(Descriptor)
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.apply_defaults({"descriptors": []})
        for d in self.descriptors:
            d._parent = ref(self)
            d.options = self.options

    def descriptor(self, name: str) -> Descriptor | None:
        for d in self.descriptors:
            if type(d).__name__ == name:
                return d
            v = getattr(d, name)
            if v is not None:
                return v
        return None

    def remove_descriptor(self, name: str) -> None:
        if self.options.mode == 'r':
            raise PermissionError(
                'Removing descriptors is not allowed for an MP4 file opened in read-only mode')
        for idx, d in enumerate(self._fields['descriptors']):
            if type(d).__name__ == name:
                del self._fields['descriptors'][idx]
                if d.size:
                    self.size -= d.size
                self._invalidate()
                return
        raise AttributeError(name)

    def encode_box_fields(self, dest) -> None:
        for d in self.descriptors:
            d.encode(dest)


class ESDescriptorBoxFactory(FullBoxFactory):
    def atom_type(self) -> type[ESDescriptorBox]:
        return ESDescriptorBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        descriptors = []
        end = rv["position"] + rv["size"]
        while src.tell() < end:
            options.log.debug(
                'ESDescriptorBox: parse descriptor pos=%d end=%d', src.tell(), end)
            d = Descriptor.load(src, parent=parent, options=options)
            descriptors.append(d)
        rv["descriptors"] = descriptors
        return rv


class SampleDescriptionBox(FullBox):
    ATOM_FOURCC = 'stsd'

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('I', 'entry_count')


class SampleDescriptionBoxFactory(FullBoxFactory[SampleDescriptionBox]):
    parse_children = True

    def atom_type(self) -> type[SampleDescriptionBox]:
        return SampleDescriptionBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        rv["entry_count"] = struct.unpack('>I', src.read(4))[0]
        return rv


class TrackFragmentHeaderBox(FullBox):
    ATOM_FOURCC = 'tfhd'
    base_data_offset_present = 0x000001
    sample_description_index_present = 0x000002
    default_sample_duration_present = 0x000008
    default_sample_size_present = 0x000010
    default_sample_flags_present = 0x000020
    duration_is_empty = 0x010000
    default_base_is_moof = 0x020000

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


class TrackFragmentHeaderBoxFactory(FullBoxFactory[TrackFragmentHeaderBox]):
    def atom_type(self) -> type[TrackFragmentHeaderBox]:
        return TrackFragmentHeaderBox

    @override
    def depends_upon(self):
        return {'moof'}

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        rv["base_data_offset"] = None
        rv["sample_description_index"] = 0
        rv["default_sample_duration"] = 0
        rv["default_sample_size"] = 0
        rv["default_sample_flags"] = 0
        r = FieldReader(self.classname(), src, rv)
        r.read('I', 'track_id')
        if rv["flags"] & TrackFragmentHeaderBox.base_data_offset_present:
            r.read('Q', 'base_data_offset')
        elif rv["flags"] & TrackFragmentHeaderBox.default_base_is_moof:
            rv["base_data_offset"] = parent.find_atom('moof').position
        if rv["flags"] & TrackFragmentHeaderBox.sample_description_index_present:
            r.read('I', 'sample_description_index')
        if rv["flags"] & TrackFragmentHeaderBox.default_sample_duration_present:
            r.read('I', 'default_sample_duration')
        if rv["flags"] & TrackFragmentHeaderBox.default_sample_size_present:
            r.read('I', 'default_sample_size')
        if rv["flags"] & TrackFragmentHeaderBox.default_sample_flags_present:
            r.read('I', 'default_sample_flags')
        if rv["base_data_offset"] is None:
            rv["base_data_offset"] = parent.find_atom('moof').position
        return rv


class TrackHeaderBox(FullBox):
    ATOM_FOURCC = 'tkhd'
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


class TrackHeaderBoxFactory(FullBoxFactory[TrackHeaderBox]):
    def atom_type(self) -> type[TrackHeaderBox]:
        return TrackHeaderBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        rv["is_enabled"] = (rv["flags"] & TrackHeaderBox.Track_enabled) == TrackHeaderBox.Track_enabled
        rv["in_movie"] = (rv["flags"] & TrackHeaderBox.Track_in_movie) == TrackHeaderBox.Track_in_movie
        rv["in_preview"] = (rv["flags"] & TrackHeaderBox.Track_in_preview) == TrackHeaderBox.Track_in_preview
        rv["size_is_aspect_ratio"] = (
            (rv["flags"] & TrackHeaderBox.Track_size_is_aspect_ratio) == TrackHeaderBox.Track_size_is_aspect_ratio)
        sz = 'Q' if rv["version"] == 1 else 'I'
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
        for _ in range(9):
            rv["matrix"].append(r.get('I', 'matrix'))
        rv["width"] = r.get('D16.16', 'width')
        rv["height"] = r.get('D16.16', 'height')
        return rv


class TrackFragmentDecodeTimeBox(FullBox):
    ATOM_FOURCC = 'tfdt'
    base_media_decode_time: int

    def __setattr__(self, name: str, value: Any) -> None:
        if name == 'base_media_decode_time':
            if self.version == 0 and value.bit_length() > 32:
                object.__setattr__(self, 'version', 1)
                self.update_size(4)
        elif name == 'version':
            if value == 0 and self.base_media_decode_time.bit_length() > 32:
                raise ValueError(
                    'base media decode time is too large to use version 0 header')
        super().__setattr__(name, value)

    def encode_box_fields(self, dest: BinaryIO) -> None:
        assert self.base_media_decode_time >= 0
        d = FieldWriter(self, dest)
        if self.version == 1:
            d.write('Q', 'base_media_decode_time')
        else:
            assert self.base_media_decode_time < (2 << 32)
            d.write('I', 'base_media_decode_time')


class TrackFragmentDecodeTimeBoxFactory(FullBoxFactory[TrackFragmentDecodeTimeBox]):
    def atom_type(self) -> type[TrackFragmentDecodeTimeBox]:
        return TrackFragmentDecodeTimeBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        if rv["version"] == 1:
            rv["base_media_decode_time"] = struct.unpack('>Q', src.read(8))[0]
        else:
            rv["base_media_decode_time"] = struct.unpack('>I', src.read(4))[0]
        return rv


class TrackExtendsBox(FullBox):
    ATOM_FOURCC = 'trex'

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('I', 'track_id')
        w.write('I', 'default_sample_description_index')
        w.write('I', 'default_sample_duration')
        w.write('I', 'default_sample_size')
        w.write('I', 'default_sample_flags')


class TrackExtendsBoxFactory(FullBoxFactory[TrackExtendsBox]):
    def atom_type(self) -> type[TrackExtendsBox]:
        return TrackExtendsBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        r.read('I', "track_id")
        r.read('I', "default_sample_description_index")
        r.read('I', "default_sample_duration")
        r.read('I', "default_sample_size")
        r.read('I', "default_sample_flags")
        return rv


class MediaHeaderBox(FullBox):
    ATOM_FOURCC = 'mdhd'
    OBJECT_FIELDS = {
        "creation_time": DateTimeField,
        "modification_time": DateTimeField,
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

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
        chars: list[int] = [ord(c) - 0x60 for c in list(self.language)] + [0, 0, 0]
        lang: int = (chars[0] << 10) + (chars[1] << 5) + chars[2]
        w.write('H', 'lang', value=lang)
        w.write('H', 'pre_defined', value=0)


class MediaHeaderBoxFactory(FullBoxFactory[MediaHeaderBox]):
    def atom_type(self) -> type[MediaHeaderBox]:
        return MediaHeaderBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
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
        src.read(2)
        return rv


class MovieFragmentHeaderBox(FullBox):
    ATOM_FOURCC = 'mfhd'

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('I', 'sequence_number')


class MovieFragmentHeaderBoxFactory(FullBoxFactory[MovieFragmentHeaderBox]):
    def atom_type(self) -> type[MovieFragmentHeaderBox]:
        return MovieFragmentHeaderBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        rv["sequence_number"] = struct.unpack('>I', src.read(4))[0]
        return rv


class HandlerBox(FullBox):
    ATOM_FOURCC = 'hdlr'

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('I', 'pre_defined', value=0)
        w.write('S4', 'handler_type')
        w.write(None, 'reserved', value=(b'\0' * 12))  # reserved = 0
        w.write('S0', 'name')


class HandlerBoxFactory(FullBoxFactory[HandlerBox]):
    def atom_type(self) -> type[HandlerBox]:
        return HandlerBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        src.read(4)
        rv["handler_type"] = str(src.read(4), 'utf-8')
        src.read(12)
        name_len = rv["position"] + rv["size"] - src.tell()
        name_bytes = src.read(name_len)
        while name_len and name_bytes[-1] == 0:
            name_bytes = name_bytes[:-1]
            name_len -= 1
        rv["name"] = str(name_bytes, 'utf-8')
        return rv


class MovieExtendsHeaderBox(FullBox):
    ATOM_FOURCC = 'mehd'

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        if self.version == 1:
            w.write('Q', 'fragment_duration')
        else:
            w.write('I', 'fragment_duration')


class MovieExtendsHeaderBoxFactory(FullBoxFactory[MovieExtendsHeaderBox]):
    def atom_type(self) -> type[MovieExtendsHeaderBox]:
        return MovieExtendsHeaderBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        if rv["version"] == 1:
            rv["fragment_duration"] = struct.unpack('>Q', src.read(8))[0]
        else:
            rv["fragment_duration"] = struct.unpack('>I', src.read(4))[0]
        return rv


class SampleAuxiliaryInformationSizesBox(FullBox):
    ATOM_FOURCC = 'saiz'

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


class SampleAuxiliaryInformationSizesBoxFactory(FullBoxFactory[SampleAuxiliaryInformationSizesBox]):
    def atom_type(self) -> type[SampleAuxiliaryInformationSizesBox]:
        return SampleAuxiliaryInformationSizesBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        if rv["flags"] & 1:
            rv["aux_info_type"] = struct.unpack('>I', src.read(4))[0]
            rv["aux_info_type_parameter"] = struct.unpack('>I', src.read(4))[0]
        rv["default_sample_info_size"] = struct.unpack('B', src.read(1))[0]
        rv["sample_info_sizes"] = []
        rv["sample_count"] = struct.unpack('>I', src.read(4))[0]
        if rv["default_sample_info_size"] == 0:
            for _ in range(rv["sample_count"]):
                rv["sample_info_sizes"].append(struct.unpack('B', src.read(1))[0])
        return rv


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


class CencSampleEncryptionBox(FullBox):
    ATOM_FOURCC = 'senc'
    OBJECT_FIELDS = {
        "kid": HexBinary,
        "samples": ListOf(CencSampleAuxiliaryData),
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

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
        for i in range(num_entries):
            if saiz.sample_info_sizes:
                size = saiz.sample_info_sizes[i]
            else:
                size = saiz.default_sample_info_size
            if size:
                s = CencSampleAuxiliaryData.parse(
                    src, size, rv["iv_size"], rv["flags"], rv)
                rv["samples"].append(s)
        return rv


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


class ProtectionSchemeTypeBox(FullBox):
    ATOM_FOURCC = 'schm'

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


class ProtectionSchemeTypeBoxFactory(FullBoxFactory[ProtectionSchemeTypeBox]):
    def atom_type(self) -> type[ProtectionSchemeTypeBox]:
        return ProtectionSchemeTypeBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        r.read('S4', 'scheme_type')
        r.read('I', 'scheme_version')
        if rv['flags'] & 0x000001:
            r.read('S0', 'scheme_uri')
        else:
            rv['scheme_uri'] = None
        return rv


class SampleAuxiliaryInformationOffsetsBox(FullBox):
    ATOM_FOURCC = 'saio'

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        if self.flags & 0x01:
            w.write('I', 'aux_info_type')
            w.write('I', 'aux_info_type_parameter')
        if self.offsets is None:
            pos = self.find_first_cenc_sample()
            if pos < 0:
                # As the CENC box has not yet encoded, the pos might
                # be negative, e.g. if the moof position has moved.
                # the post_encode() function will fix this after the
                # entire MP4 file has been generated.
                pos = 0
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

    def find_first_cenc_sample(self) -> int | None:
        if self._parent is None:
            return None
        parent = self._parent()
        if not parent:
            return None
        senc = parent.find_child('senc')
        if senc is None:
            return None
        if len(senc.samples) == 0:
            return None
        tfhd = parent.find_child('tfhd')
        base_data_offset: int | None = None
        if tfhd is not None:
            base_data_offset = tfhd.base_data_offset
        if base_data_offset is None:
            moof = self.find_atom('moof')
            base_data_offset = moof.position
        assert base_data_offset is not None
        senc_sample_pos: int = senc.position + senc.samples[0].offset
        return senc_sample_pos - base_data_offset

    def post_encode(self, dest):
        if self.offsets is not None and len(self.offsets) != 1:
            return
        if self._parent is None:
            return
        parent = self._parent()
        if not parent:
            return
        senc = parent.find_child('senc')
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


class SampleAuxiliaryInformationOffsetsBoxFactory(FullBoxFactory[SampleAuxiliaryInformationOffsetsBox]):
    def atom_type(self) -> type[SampleAuxiliaryInformationOffsetsBox]:
        return SampleAuxiliaryInformationOffsetsBox

    @override
    def depends_upon(self) -> set[str]:
        return {'moof', 'senc', 'tfhd'}

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        if rv["flags"] & 0x01:
            rv["aux_info_type"] = struct.unpack('>I', src.read(4))[0]
            rv["aux_info_type_parameter"] = struct.unpack('>I', src.read(4))[0]
        entry_count = struct.unpack('>I', src.read(4))[0]
        rv["offsets"] = []
        for _ in range(entry_count):
            if rv["version"] == 0:
                o = struct.unpack('>I', src.read(4))[0]
            else:
                o = struct.unpack('>Q', src.read(8))[0]
            rv["offsets"].append(o)
        return rv


# See section 8.8.8 of ISO/IEC 14496-12
class TrackSample(ObjectWithFields):
    REQUIRED_FIELDS = {
        'index': int,
        'offset': int,
    }
    composition_time_offset: int
    duration: int | None
    flags: int
    index: int
    offset: int
    size: int

    @classmethod
    def parse(
            cls, src: BinaryIO, index: int, offset: int,
            trun: dict[str, Any], tfhd: TrackFragmentHeaderBox) -> dict[str, Any]:
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

    def encode(self, dest: BinaryIO, version: int, flags: int) -> None:
        d = FieldWriter(self, dest)
        if flags & TrackFragmentRunBox.sample_duration_present:
            d.write('I', 'duration')
        if flags & TrackFragmentRunBox.sample_size_present:
            d.write('I', 'size')
        if flags & TrackFragmentRunBox.sample_flags_present:
            d.write('I', 'flags')
        if flags & TrackFragmentRunBox.sample_composition_time_offsets_present:
            if version:
                d.write('i', 'composition_time_offset')
            else:
                d.write('I', 'composition_time_offset')


class TrackFragmentRunBox(FullBox):
    ATOM_FOURCC = 'trun'
    data_offset_present: ClassVar[int] = 0x000001
    first_sample_flags_present: ClassVar[int] = 0x000004  # overrides default flags for the first sample only
    sample_duration_present: ClassVar[int] = 0x000100  # sample has its own duration?
    sample_size_present: ClassVar[int] = 0x000200  # sample has its own size
    sample_flags_present: ClassVar[int] = 0x000400  # sample has its own flags
    sample_composition_time_offsets_present: ClassVar[int] = 0x000800  # sample has a composition time offset

    samples: list[TrackSample]

    OBJECT_FIELDS = {
        'samples': ListOf(TrackSample),
        **FullBox.OBJECT_FIELDS,
    }

    def parse_samples(self, src: BinaryIO, nal_length_field_length: int) -> None:
        tfhd: Mp4Atom | None = self.find_peer("tfhd")
        assert tfhd is not None, "Failed to find tfhd box for trun box"
        for sample in self.samples:
            pos = sample.offset + tfhd.base_data_offset
            end = pos + sample.size
            sample.nals = []
            while pos < end:
                src.seek(pos)
                nal = Nal(src, nal_length_field_length)
                pos += nal.size + nal_length_field_length
                sample.nals.append(nal)

    @override
    def encode_box_fields(self, dest: BinaryIO) -> None:
        pos = self.position + self.header_size + FullBox.FB_HEADER_SIZE
        assert pos == dest.tell()
        self.output_box_fields(dest)
        for sample in self.samples:
            self.options.log.debug(f"Encoding sample {sample.index} at offset {dest.tell()} with size {sample.size}")
            sample.encode(dest, self.version, self.flags)

    def output_box_fields(self, dest: BinaryIO) -> None:
        w = FieldWriter(self, dest)
        self.sample_count = len(self.samples)
        self.options.log.debug(f"Encoding trun box with {self.sample_count} samples")
        w.write('I', 'sample_count')
        if self.flags & self.data_offset_present:
            w.write('I', 'data_offset')
        if self.flags & self.first_sample_flags_present:
            w.write('I', 'first_sample_flags')

    def post_encode(self, dest: BinaryIO) -> None:
        moof = self.find_atom(
            'moof', check_parent=True, recurse_children=False,
            no_exception=True)
        if moof is None:
            self.options.log.info('%s: Failed to find moof box', self._fullname)
            return
        mdat = moof.find_peer('mdat')
        if mdat is None:
            self.options.log.info('%s: Failed to find mdat box', self._fullname)
            return
        mdat_sample_start = moof.position + moof.size + mdat.header_size

        tfhd: TrackFragmentHeaderBox = moof['traf.tfhd']
        first_sample_pos: int = tfhd.base_data_offset
        if (self.flags & self.data_offset_present) != 0:
            first_sample_pos += self.data_offset
        if first_sample_pos != mdat_sample_start:
            self.options.log.debug(
                'rewriting trun data_offset from %d to %d',
                self.data_offset,
                mdat_sample_start - tfhd.base_data_offset)
            self.data_offset = mdat_sample_start - tfhd.base_data_offset
            assert self.data_offset >= 0
            cur = dest.tell()
            if (self.flags & self.data_offset_present) == 0:
                self.flags |= self.data_offset_present
                dest.seek(self.position + self.header_size)
                self.encode_fields(dest)
            else:
                pos: int = self.position + self.header_size + FullBox.FB_HEADER_SIZE
                dest.seek(pos)
                self.output_box_fields(dest)
            dest.seek(cur)


class TrackFragmentRunBoxFactory(FullBoxFactory[TrackFragmentRunBox]):
    def atom_type(self) -> type[TrackFragmentRunBox]:
        return TrackFragmentRunBox

    @override
    def depends_upon(self):
        return {'moof', 'traf', 'mdat', 'tfhd'}

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        tfhd: TrackFragmentHeaderBox = cast(TrackFragmentHeaderBox, parent.get('tfhd'))
        sample_count = struct.unpack('>I', src.read(4))[0]
        rv["sample_count"] = sample_count
        if rv["flags"] & TrackFragmentRunBox.data_offset_present:
            rv["data_offset"] = struct.unpack('>i', src.read(4))[0]
        else:
            rv["data_offset"] = 0
        if rv["flags"] & TrackFragmentRunBox.first_sample_flags_present:
            rv["first_sample_flags"] = struct.unpack('>I', src.read(4))[0]
        else:
            rv["first_sample_flags"] = 0
        rv["samples"] = []
        offset: int = rv["data_offset"]
        samples: list[TrackSample] = []
        for i in range(sample_count):
            ts = TrackSample.parse(src, i, offset, rv, tfhd)
            ts = TrackSample(**ts)
            samples.append(ts)
            offset += ts.size
        rv["samples"] = samples
        return rv


class TrackEncryptionBox(FullBox):
    ATOM_FOURCC = 'tenc'
    OBJECT_FIELDS = {
        "default_kid": HexBinary,
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('3I', "is_encrypted")
        w.write('B', "iv_size")
        w.write(16, "default_kid")


class TrackEncryptionBoxFactory(FullBoxFactory[TrackEncryptionBox]):
    def atom_type(self) -> type[TrackEncryptionBox]:
        return TrackEncryptionBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        r.read('3I', "is_encrypted")
        r.read('B', "iv_size")
        r.read(16, "default_kid")
        return rv


class ContentProtectionSpecificBox(FullBox):
    ATOM_FOURCC = 'pssh'
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
    def _fixup_binary_field(value: Binary | str | bytes) -> Binary:
        if value is None:
            return None
        if isinstance(value, Binary):
            return value
        if len(value) != 16:
            if re.match(r'^(0x)?[0-9a-f-]+$', value, re.IGNORECASE):
                if value.startswith('0x'):
                    value = value[2:]
                value = binascii.unhexlify(value.replace('-', ''))
        if len(value) != 16:
            raise ValueError(fr"Invalid length: {len(value)}")
        return HexBinary(value, encoding=Binary.HEX)

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


class ContentProtectionSpecificBoxFactory(FullBoxFactory[ContentProtectionSpecificBox]):
    def atom_type(self) -> type[ContentProtectionSpecificBox]:
        return ContentProtectionSpecificBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        r.read(16, "system_id")
        rv["key_ids"] = []
        if rv["version"] > 0:
            kid_count = r.get('I', 'kid_count')
            for _ in range(kid_count):
                rv["key_ids"].append(r.read(16, 'kid'))
        data_size = r.get('I', 'data_size')
        if data_size > 0:
            r.read(data_size, "data")
        else:
            rv["data"] = None
        return rv


class SegmentReference(ObjectWithFields):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            assert "src" != key
            if key not in self.__dict__:
                setattr(self, key, value)

    @classmethod
    def parse(cls, src, parent, **kwargs):
        rv = {}
        r = BitsFieldReader(cls.classname(), src, rv, size=12)
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


class SegmentIndexBox(FullBox):
    ATOM_FOURCC = 'sidx'
    OBJECT_FIELDS = {
        'references': ListOf(SegmentReference),
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

    def encode_box_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('I', 'reference_id')
        w.write('I', 'timescale')
        sz = 'I' if self.version == 0 else 'Q'
        w.write(sz, 'earliest_presentation_time')
        w.write(sz, 'first_offset')
        w.write('H', 'reserved', 0)
        w.write('H', 'reference_count', len(self.references))
        for segment_ref in self.references:
            segment_ref.encode(w)


class SegmentIndexBoxFactory(FullBoxFactory[SegmentIndexBox]):
    def atom_type(self) -> type[SegmentIndexBox]:
        return SegmentIndexBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
        r.read('I', 'reference_id')
        r.read('I', 'timescale')
        sz = 'I' if rv['version'] == 0 else 'Q'
        r.read(sz, 'earliest_presentation_time')
        r.read(sz, 'first_offset')
        r.skip(2)
        ref_count = r.get('H', 'reference_count')
        rv["references"] = []
        for _ in range(ref_count):
            rv["references"].append(
                SegmentReference(**SegmentReference.parse(src, parent)))
        return rv


class EventMessageBox(FullBox):
    ATOM_FOURCC = 'emsg'
    OBJECT_FIELDS = {
        'data': Binary,
    }
    OBJECT_FIELDS.update(FullBox.OBJECT_FIELDS)

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


class EventMessageBoxFactory(FullBoxFactory[EventMessageBox]):
    def atom_type(self) -> type[EventMessageBox]:
        return EventMessageBox

    def parse(self, src: BinaryIO, parent: Mp4Atom, options: Options, **kwargs) -> dict[str, Any] | None:
        rv = super().parse(src, parent, options=options, **kwargs)
        if rv is None:
            return None
        r = FieldReader(self.classname(), src, rv)
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


FOURCC_TO_ATOM: dict[str, AtomFactory] = {}  # map from fourcc code to Mp4Atom class factory

NAMES_TO_ATOM: dict[str, AtomFactory] = {
    # 'BoxWithChildren': BoxWithChildrenFactory(),
    'UnknownBox': UnknownBoxFactory(),
}  # map from class name to Mp4Atom class factory

ALL_ATOMS: list[type[AtomFactory]] = [
    FileTypeBoxFactory,
    SegmentTypeBoxFactory,
    MovieBoxFactory,
    TrackBoxFactory,
    TrackFragmentBoxFactory,
    MovieFragmentBoxFactory,
    MediaInformationBoxFactory,
    MovieExtendsBoxFactory,
    MediaDataBoxFactory,
    SchemaInformationBoxFactory,
    ProtectionSchemeInformationBoxFactory,
    SampleTableBoxFactory,
    UserDataBoxFactory,
    MovieHeaderBoxFactory,
    AVC1SampleEntryFactory,
    AVC3SampleEntryFactory,
    HEV1SampleEntryFactory,
    HVC1SampleEntryFactory,
    EncryptedSampleEntryFactory,
    FontTableBoxFactory,
    TextSampleEntryFactory,
    WebVTTConfigurationBoxFactory,
    BitRateBoxFactory,
    WVTTSampleEntryFactory,
    XMLSubtitleSampleEntryFactory,
    MimeBoxFactory,
    AVCConfigurationBoxFactory,
    HEVCConfigurationBoxFactory,
    PixelAspectRatioBoxFactory,
    EC3SampleEntryFactory,
    AC3SampleEntryFactory,
    EAC3SpecificBoxFactory,
    AC3SpecificBoxFactory,
    OriginalFormatBoxFactory,
    MP4AudioSampleEntryFactory,
    EncryptedMP4AFactory,
    ESDescriptorBoxFactory,
    SampleDescriptionBoxFactory,
    TrackFragmentHeaderBoxFactory,
    TrackHeaderBoxFactory,
    TrackFragmentDecodeTimeBoxFactory,
    TrackExtendsBoxFactory,
    MediaHeaderBoxFactory,
    MovieFragmentHeaderBoxFactory,
    HandlerBoxFactory,
    MovieExtendsHeaderBoxFactory,
    SampleAuxiliaryInformationSizesBoxFactory,
    CencSampleEncryptionBoxFactory,
    PiffSampleEncryptionBoxFactory,
    ProtectionSchemeTypeBoxFactory,
    SampleAuxiliaryInformationOffsetsBoxFactory,
    TrackFragmentRunBoxFactory,
    TrackEncryptionBoxFactory,
    ContentProtectionSpecificBoxFactory,
    SegmentIndexBoxFactory,
    EventMessageBoxFactory,
]  # list of all atom factories


class DeferredBox(TypedDict):
    factory: AtomFactory
    initial_data: dict[str, Any]
    index: int


class IsoParser:
    @staticmethod
    def walk_atoms(filename: str | BinaryIO, atom: Mp4Atom | None = None, options: Options | None = None) -> list[Mp4Atom]:
        atoms: list[Mp4Atom] = []
        src = None
        try:
            if options is not None:
                options.log.debug('Parse %s', filename)
            if isinstance(filename, str):
                src = open(filename, mode="rb", buffering=32768)
            else:
                src = filename
            atoms = cast(list[Mp4Atom], IsoParser.load(src, options=options))
        finally:
            if src and isinstance(filename, (str, str)):
                src.close()
        return atoms

    @staticmethod
    def show_atom(atom, atom_types: set[str], as_json: bool, with_children: set[str],
                  count: int = 0) -> int:
        check_children = True
        if atom.atom_name() in atom_types:
            if atom.atom_name() in with_children:
                exclude = atom.DEFAULT_EXCLUDE
                check_children = False
            else:
                exclude = atom.DEFAULT_EXCLUDE.union({'children'})
            if atom.atom_type == b'mdat' and 'mdat' not in with_children:
                exclude.add('data')
            if as_json:
                if count > 0:
                    print(',')
                item = atom.toJSON(exclude=exclude, pure=True)
                item['atom_type'] = atom.atom_name()
                if atom.children is not None and 'children' in exclude:
                    item['children'] = [a.atom_name() for a in atom.children]
                print(json.dumps(item, sort_keys=True, indent=2))
            else:
                try:
                    exclude.remove('atom_type')
                except KeyError:
                    pass
                print(atom.as_python(exclude))
            count += 1
        if check_children and atom.children is not None:
            ch_count = 0
            for child in atom.children:
                ch_count += IsoParser.show_atom(
                    child, atom_types=atom_types, as_json=as_json,
                    with_children=with_children, count=ch_count)
        return count

    @classmethod
    def load(cls,
             src: BinaryIO,
             parent: Mp4Atom | None = None,
             options: Options | dict[str, Any] | None = None) -> list[Mp4Atom]:
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
        assert options is not None
        cls._setup()
        end: int | None = None
        prefix: str = ''
        cursor: int
        ev_bus: EventBus["Mp4Atom"]
        rv: list[Mp4Atom] = []
        top_level: bool = parent is None
        if parent is not None:
            try:
                cursor = parent.payload_start
            except AttributeError:
                cursor = src.tell()
            end = parent.position + parent.size
            prefix = f'{parent._fullname}: '
            assert parent._ev_bus is not None
            ev_bus = parent._ev_bus
            # the _children list might be used when parsing an atom, as it
            # might need to get data from one of its peers
            if parent._children is None:
                parent._children = rv
            else:
                rv = parent._children
        else:
            cursor = src.tell()
            parent = Wrapper(position=src.tell(), options=options)
            ev_bus = EventBus["Mp4Atom"]()
            parent._ev_bus = ev_bus
        if options.iv_size and options.iv_size > 16:
            # assume user has provided IV size in bits rather than bytes
            options.iv_size = options.iv_size // 8
            assert options.iv_size in {8, 16}
        if end is None:
            options.log.debug('%sLoad start=%d end=None', prefix, cursor)
        else:
            options.log.debug('%sLoad start=%d end=%d (%d)', prefix,
                              cursor, end, end - cursor)
        deferred_boxes: list[DeferredBox] = []
        unknown = UnknownBoxFactory()
        while end is None or cursor < end:
            assert cursor is not None
            if src.tell() != cursor:
                options.log.debug('Move cursor from %d to %d', src.tell(), cursor)
                src.seek(cursor)
            hdr = AtomFactory.parse_header(src, options=options)
            if hdr is None:
                break
            factory: AtomFactory
            factory = FOURCC_TO_ATOM.get(hdr['atom_type'], unknown)  # pyright: ignore[reportFunctionMemberAccess]
            options.log.debug('%sfound atom "%s" type=%s pos=%d size=%d',
                              prefix,
                              hdr['atom_type'], type(factory).__name__,
                              hdr['position'], hdr['size'])
            encoded: bytes | None = None
            if options.mode == 'rw' and not factory.parse_children:
                sz = hdr["size"] - hdr["header_size"]
                if sz == 0:
                    encoded = b''
                else:
                    here: int = src.tell()
                    encoded = src.read(sz)
                    src.seek(here)
            if factory.REQUIRED_PEERS is not None:
                required = set(factory.REQUIRED_PEERS)
                for name in factory.REQUIRED_PEERS:
                    if parent.find_child(name) is not None:
                        required.remove(name)
                if required:
                    options.log.debug(
                        'Defer parsing of "%s" as %s needs to be parsed',
                        hdr['atom_type'], list(required))
                    db: DeferredBox = {'factory': factory, 'initial_data': hdr, 'index': len(rv)}
                    deferred_boxes.append(db)
                    cursor += hdr['size']
                    continue
            lazy_load_this_atom: bool = not top_level and options.lazy_load and factory != unknown
            if lazy_load_this_atom:
                options.log.debug(
                    'lazy loading parent=%s this=%s pos=%d', parent.atom_type,
                    hdr["atom_type"], hdr["position"])
                kwargs = LazyLoadedBox.parse(src, parent, options=options, initial_data=hdr)
                # hexdump_buffer(
                #    f'lazy {kwargs["atom_type"]}@{kwargs["position"]}', kwargs['buffer'], 32)
            else:
                del hdr['_buffer']
                kwargs = factory.parse(src, parent, options=options, initial_data=hdr)
            if kwargs is None:
                break
            kwargs['_parent'] = ref(parent)
            kwargs['options'] = options
            atom: Mp4Atom
            if lazy_load_this_atom:
                atom = LazyLoadedBox(**kwargs)
                atom._box_factory = factory
                deps = factory.depends_upon()
                for name in deps:
                    ev_bus.on(f'change.{name}', atom.atom_changed)
            else:
                atom = factory.create(**kwargs)
                atom.payload_start = src.tell()
            atom._encoded = encoded
            atom._ev_bus = ev_bus
            rv.append(atom)
            # print(f'name={atom.atom_name()} pos={atom.position} size={atom.size} children={factory.parse_children}')
            if factory.parse_children:
                # options.log.debug('Parse %s children', hdr['atom_type'])
                atom._children = []
                cls.load(src, parent=atom, options=options)
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
            df_factory: AtomFactory = item['factory']
            src.seek(hdr['position'] + hdr['header_size'])
            df_kwargs = df_factory.parse(
                src, parent, options=options, initial_data=hdr)
            assert df_kwargs is not None
            df_kwargs['_parent'] = ref(parent) if parent else None
            df_kwargs['options'] = options
            new_atom = df_factory.create(**df_kwargs)
            new_atom.payload_start = src.tell()
            if df_factory.parse_children:
                options.log.debug('Parse %s children', new_atom.atom_type)
                cls.load(src, new_atom, options)
            options.log.debug('finished parsing of deferred "%s"',
                              new_atom.atom_type)
            rv.insert(item['index'], new_atom)
        src.seek(cur_pos)
        return rv

    @classmethod
    def load_wrapped(cls,
                     src: BinaryIO,
                     options: Options | dict[str, Any] | None = None,
                     ) -> Wrapper:
        position: int = src.tell()
        if options is None:
            options = Options()
        elif isinstance(options, dict):
            options = Options(**options)
        children: list[Mp4Atom] = IsoParser.load(src, options=options)
        size: int = src.tell() - position
        return Wrapper(children=children, options=options, position=position, size=size)

    @classmethod
    def fromJSON(cls,
                 src: dict[str, Any] | list[dict[str, Any]],
                 parent: Mp4Atom | None = None,
                 options: Options | dict | None = None) -> Mp4Atom | list[Mp4Atom]:
        cls._setup()
        assert src is not None
        if options is None:
            options = Options()
        elif isinstance(options, dict):
            options = Options(**options)
        if isinstance(src, list):
            return [cast(Mp4Atom, cls.fromJSON(atom)) for atom in src]

        factory: AtomFactory
        if '_type' in src:
            name = src['_type']
            if name.startswith(MODULE_PREFIX):
                name = name[len(MODULE_PREFIX):]
            factory = NAMES_TO_ATOM[name]
        elif 'atom_type' in src:
            factory = FOURCC_TO_ATOM[src['atom_type']]
        else:
            factory = UnknownBoxFactory()
        src['_parent'] = ref(parent) if parent else None
        src['options'] = options
        if 'children' not in src and '_children' not in src:
            return factory.create(**src)
        try:
            children = src['_children']
        except KeyError:
            children = src['children']
        rv = factory.create(**src)
        assert rv is not None
        rv._children = []
        if children is None:
            return rv
        for child in children:
            if isinstance(child, dict):
                child['_parent'] = ref(rv)
                child['options'] = options
                atom = cls.fromJSON(child)
                assert isinstance(atom, Mp4Atom)
                rv._children.append(atom)
            else:
                rv._children.append(child)
        return rv

    @classmethod
    def _setup(cls) -> None:
        if not FOURCC_TO_ATOM:
            factory_type: type[AtomFactory]
            for factory_type in ALL_ATOMS:
                ft = factory_type()
                FOURCC_TO_ATOM[ft.fourcc()] = ft
                NAMES_TO_ATOM[ft.classname()] = ft

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
        options = Options(lazy_load=False)
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
            count = 0
            for atom in atoms:
                if args.tree:
                    atom.dump()
                if args.show:
                    count += IsoParser.show_atom(
                        atom, atom_types=atom_types, with_children=with_children,
                        as_json=args.json, count=count)
        if args.json:
            print(']')


if __name__ == "__main__":
    IsoParser.main()
