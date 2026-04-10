#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, BinaryIO

from dashlive.utils.fio import FieldReader, FieldWriter

from ..atom import Mp4Atom
from ..options import Options

from .sample_entry import SampleEntry, SampleEntryFactory

class XMLSubtitleSampleEntry(SampleEntry):
    ATOM_FOURCC = 'stpp'
    namespace: str
    schema_location: str
    mime_types: str

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
