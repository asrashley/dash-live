import logging
import os
from typing import AbstractSet, Any, BinaryIO, ClassVar, Protocol, cast, override
from weakref import ref

from dashlive.utils.hexdump import hexdump_buffer
from dashlive.utils.io_with_offset import BytesIoWithOffset
from dashlive.utils.json_object import JsonObject

from ..options import Options
from ..atom import Mp4Atom
from ..atom_factory import AtomFactory

class AtomLoader(Protocol):
    def __call__(self, src: BinaryIO, parent: Mp4Atom, options: Options) -> list[Mp4Atom]:
        ...


class LazyLoadedBox(Mp4Atom):
    CHILDREN_LOADER: ClassVar[AtomLoader]
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
              parent: Mp4Atom,
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

    @override
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
            atom._children = LazyLoadedBox.CHILDREN_LOADER(src, atom, options=self.options)
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
