
from abc import ABC, abstractmethod
import binascii
import struct
from typing import Any, BinaryIO, ClassVar, cast

from .atom import Mp4Atom
from .options import Options

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
