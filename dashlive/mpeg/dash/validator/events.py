#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import base64
import binascii

from dashlive import scte35
from dashlive.mpeg import MPEG_TIMEBASE
from dashlive.utils.buffered_reader import BufferedReader
from dashlive.utils.binary import Binary

from .dash_element import DashElement
from .descriptor import Descriptor

class Scte35Binary(DashElement):
    def __init__(self, elt, parent: DashElement, schemeIdUri: str) -> None:
        super().__init__(elt, parent)
        self.schemeIdUri = schemeIdUri
        try:
            data = Binary(elt.text, encoding=Binary.BASE64, decode=True)
            src = BufferedReader(None, data=data.data)
            self.signal = scte35.BinarySignal.parse(src, size=len(data))
        except (ValueError, binascii.Error) as err:
            self.elt.add_error(str(err))
            self.signal = None

    def children(self) -> list[DashElement]:
        return []

    def validate(self, depth: int = -1) -> None:
        self.attrs.check_equal(
            self.schemeIdUri, EventStreamBase.SCTE35_XML_BIN_EVENTS)
        if self.signal is None:
            return
        ev_stream = self.find_parent('EventStream')
        self.elt.check_includes(sig, 'splice_insert')
        self.elt.check_includes(sig['splice_insert'], 'break_duration')
        duration = sig['splice_insert']['break_duration']['duration']
        self.elt.check_almost_equal(
            self.duration / float(ev_stream.timescale), duration / float(MPEG_TIMEBASE))


# <scte35:Signal><scte35:Binary>{{binary|base64}}</scte35:Binary></scte35:Signal>
class Scte35EventElement(DashElement):
    def __init__(self, elt, parent: DashElement, schemeIdUri: str) -> None:
        super().__init__(elt, parent)
        bins = elt.findall('./scte35:Binary', self.xmlNamespaces)
        self._children = [Scte35Binary(b, self, schemeIdUri) for b in bins]

    def children(self) -> list[DashElement]:
        return self._children

    def validate(self, depth: int = - 1) -> None:
        if depth == 0:
            return
        for ch in self._children:
            ch.validate(depth - 1)

class DashEvent(DashElement):
    """
    Contains the information for one manifest DASH event
    """
    attributes = [
        ('contentEncoding', str, None),
        ('duration', int, -1),
        ('id', int, None),
        ('messageData', str, None),
        ('presentationTime', int, 0),
    ]

    def __init__(self, elt, parent: DashElement) -> None:
        super().__init__(elt, parent)
        self._children = []
        schemeIdUri = self.parent.schemeIdUri
        for child in elt:
            if child.prefix:
                ns = child.nsmap[child.prefix]
                if ns == self.xmlNamespaces['scte35']:
                    self._children.append(Scte35EventElement(child, self, schemeIdUri))
                    continue
            self._children.append(DashEventElement(child, self))

    def children(self) -> list[DashElement]:
        return self._children

    def validate(self, depth: int = -1) -> None:
        if self._children:
            self.elt.check_none(
                self.messageData,
                msg='message data is not allowed when the DashElement has children')
        if self.contentEncoding is not None:
            self.elt.check_equal(
                self.contentEncoding, 'base64',
                msg='content encoding must be Base64')
        if depth > 0:
            for ch in self._children:
                ch.validate(depth - 1)


class EventStreamBase(Descriptor):
    """
    Base class for inband and MPD event streams
    """

    SCTE35_XML_EVENTS = "urn:scte:scte35:2013:xml"
    SCTE35_XML_BIN_EVENTS = "urn:scte:scte35:2014:xml+bin"
    SCTE35_INBAND_EVENTS = "urn:scte:scte35:2013:bin"

    attributes = Descriptor.attributes + [
        ('timescale', int, 1),
        ('presentationTimeOffset', int, 0),
    ]

    def __init__(self, elt, parent) -> None:
        super().__init__(elt, parent)
        evs = elt.findall('./dash:Event', self.xmlNamespaces)
        self.events = [DashEvent(a, self) for a in evs]

    def children(self) -> list[DashEvent]:
        return super().children() + self.events


class EventStream(EventStreamBase):
    """
    An EventStream, where events are carried in the manifest
    """

    def validate(self, depth: int = -1) -> None:
        super().validate(depth)
        self.attrs.check_not_equal(self.schemeIdUri, self.SCTE35_INBAND_EVENTS)
        if depth == 0:
            return
        for event in self.events:
            event.validate(depth - 1)


class InbandEventStream(EventStreamBase):
    """
    An EventStream, where events are carried in the media
    """
    def validate(self, depth: int = -1) -> None:
        super().validate(depth)
        self.elt.check_equal(
            len(self._children), 0,
            msg='Event elements are not allowed in an inband EventStream element')
