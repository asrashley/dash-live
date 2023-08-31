#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import base64

from dashlive import scte35
from dashlive.mpeg import MPEG_TIMEBASE
from dashlive.utils.buffered_reader import BufferedReader

from .dash_element import DashElement
from .descriptor import Descriptor

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
        self.children = []
        for child in elt:
            self.children.append(child)

    def validate(self, depth: int = -1) -> None:
        if self.children:
            self.checkIsNone(self.messageData)
        if self.contentEncoding is not None:
            self.checkEqual(self.contentEncoding, 'base64')
        if self.parent.schemeIdUri == EventStreamBase.SCTE35_XML_BIN_EVENTS:
            self.checkEqual(len(self.children), 1)
            bin_elt = self.children[0].findall('./scte35:Binary', self.xmlNamespaces)
            self.checkIsNotNone(bin_elt)
            self.checkEqual(len(bin_elt), 1)
            data = base64.b64decode(bin_elt[0].text)
            src = BufferedReader(None, data=data)
            sig = scte35.BinarySignal.parse(src, size=len(data))
            timescale = self.parent.timescale
            self.checkIn('splice_insert', sig)
            self.checkIn('break_duration', sig['splice_insert'])
            duration = sig['splice_insert']['break_duration']['duration']
            self.checkAlmostEqual(
                self.duration / float(timescale), duration / float(MPEG_TIMEBASE))
            self.scte35_binary_signal = sig


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


class EventStream(EventStreamBase):
    """
    An EventStream, where events are carried in the manifest
    """

    def validate(self, depth: int = -1) -> None:
        super().validate(depth)
        self.checkNotEqual(self.schemeIdUri, self.SCTE35_INBAND_EVENTS)
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
        self.checkEqual(len(self.children), 0)
