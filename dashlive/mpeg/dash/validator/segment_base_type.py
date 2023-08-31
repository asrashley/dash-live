#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from dashlive.mpeg import mp4
from dashlive.utils.buffered_reader import BufferedReader

from .dash_element import DashElement
from .http_range import HttpRange
from .segment_reference import SegmentReference
from .url_type import URLType

class SegmentBaseType(DashElement):
    attributes = [
        ('timescale', int, 1),
        ('presentationTimeOffset', int, 0),
        ('indexRange', HttpRange, None),
        ('indexRangeExact', bool, False),
        ('availabilityTimeOffset', float, None),
        ('availabilityTimeComplete', bool, None),
    ]

    def __init__(self, elt, parent):
        super().__init__(elt, parent)
        inits = elt.findall('./dash:Initialization', self.xmlNamespaces)
        self.initializationList = [URLType(u, self) for u in inits]
        self.representationIndex = [URLType(i, self) for i in elt.findall('./dash:RepresentationIndex', self.xmlNamespaces)]

    def load_segment_index(self, url):
        self.checkIsNotNone(self.indexRange)
        headers = {"Range": f"bytes={self.indexRange}"}
        self.log.debug('GET: %s %s', url, headers)
        response = self.http.get(url, headers=headers)
        # 206 = partial content
        self.checkEqual(response.status_code, 206)
        if self.options.save:
            default = f'index-{self.parent.id}-{self.parent.bandwidth}'
            filename = self.output_filename(
                default, self.parent.bandwidth, prefix=self.options.prefix,
                makedirs=True)
            self.log.debug('saving index segment: %s', filename)
            with self.open_file(filename, self.options) as dest:
                dest.write(response.body)
        src = BufferedReader(None, data=response.body)
        opts = mp4.Options(strict=self.options.strict)
        atoms = mp4.Mp4Atom.load(src, options=opts)
        self.checkEqual(len(atoms), 1)
        self.checkEqual(atoms[0].atom_type, 'sidx')
        sidx = atoms[0]
        self.timescale = sidx.timescale
        start = self.indexRange.end + 1
        rv = []
        decode_time = sidx.earliest_presentation_time
        for ref in sidx.references:
            end = start + ref.ref_size - 1
            rv.append(SegmentReference(
                parent=self, url=url, start=start, end=end,
                duration=ref.duration, decode_time=decode_time))
            start = end + 1
            decode_time += ref.duration
        return rv
