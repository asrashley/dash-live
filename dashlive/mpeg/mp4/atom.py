#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from abc import abstractmethod
import binascii
import io
import re
import struct
from typing import AbstractSet, Any, BinaryIO, ClassVar, Optional, Protocol, Union
from weakref import ref, ReferenceType


from dashlive.utils.json_object import JsonObject
from dashlive.utils.list_of import ListOf
from dashlive.utils.object_with_fields import ObjectWithFields

from .event_bus import EventBus
from .options import Options

MODULE_PREFIX_RE: re.Pattern = re.compile(
    r'^(dashlive\.mpeg\.)?(mp4\.boxes\.)?(?P<filename>[A-Za-z0-9_-]+)\.(?P<box_name>[A-Za-z0-9_-]+)$')


class FromJSON(Protocol):
    def __call__(self,
                 src: dict[str, Any] | list[dict[str, Any]],
                 parent: Optional["Mp4Atom"] = None,
                 options: Optional[Union[Options, dict]] = None) -> Union["Mp4Atom", list["Mp4Atom"]]:
        ...

def _from_json(
        src: dict[str, Any],
        parent: Optional["Mp4Atom"] = None,
        options: Optional[Union[Options, dict]] = None) -> "Mp4Atom":
    raise NotImplementedError('fromJSON is not implemented for %s' % src.get('atom_type', 'unknown'))

class Mp4Atom(ObjectWithFields):
    include_atom_type: ClassVar[bool] = False
    ATOM_FOURCC: ClassVar[str] = ''
    FROM_JSON: ClassVar[FromJSON] = _from_json

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
                    ch_atom = self.__class__.FROM_JSON(ch)
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
                # NOTE: lazy_load() in LazyLoadedBox will replace this atom in the parent _children list
                return c.lazy_load()
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
        if isinstance(field, Mp4Atom):
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

    def lazy_load(self) -> "Mp4Atom":
        return self

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
                from .boxes.lazy_loaded import LazyLoadedBox  # noqa: E402
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
                if c is atom_type:
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
        if '_type' in rv and rv['_type'].startswith('dashlive.mpeg.mp4.boxes.'):
            rv['_type'] = MODULE_PREFIX_RE.sub(r'\g<box_name>', rv['_type'])
        if self._children is not None:
            rv['children'] = [
                ch.toJSON(exclude=exclude) for ch in self._children]
        return rv


Mp4Atom.OBJECT_FIELDS['_children'] = ListOf(Mp4Atom)
