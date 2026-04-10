from typing import Any, BinaryIO, cast

from ..atom import Mp4Atom
from ..atom_factory import AtomFactory
from ..options import Options

from dashlive.utils.binary import Binary


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
