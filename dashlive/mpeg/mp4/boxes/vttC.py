#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO

from ..atom import Mp4Atom
from ..atom_factory import AtomFactory
from ..options import Options


class WebVTTConfigurationBox(Mp4Atom):
    ATOM_FOURCC = 'vttC'
    config: str

    def encode_fields(self, dest: BinaryIO) -> None:
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
