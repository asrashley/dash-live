#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO
from weakref import ref

from dashlive.utils.list_of import ListOf

from ..atom import Mp4Atom
from .full import FullBox, FullBoxFactory
from ..descriptors import Descriptor
from ..options import Options


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
