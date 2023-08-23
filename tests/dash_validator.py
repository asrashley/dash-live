#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from abc import abstractmethod
import base64
import collections
import datetime
import io
import json
import logging
import math
import os
import re
import time
import traceback
from typing import Any, Never
import urllib.parse

from lxml import etree as ET

from dashlive.drm.playready import PlayReady
from dashlive.testcase.mixin import HideMixinsFilter, TestCaseMixin
from dashlive.mpeg import MPEG_TIMEBASE, mp4
from dashlive import scte35
from dashlive.utils.date_time import from_isodatetime, scale_timedelta, to_iso_datetime, UTC
from dashlive.utils.binary import Binary
from dashlive.utils.buffered_reader import BufferedReader

class ValidatorOptions:
    """
    Options that can be passed to the DASH validator
    """
    def __init__(self, strict=True, encrypted=False, save=False, iv_size=None,
                 duration=None, prefix=None):
        self.strict = strict
        self.encrypted = encrypted
        self.save = save
        self.iv_size = iv_size
        self.start_time = RelaxedDateTime.now(UTC())
        self.duration = duration
        self.prefix = prefix


class RelaxedDateTime(datetime.datetime):
    def replace(self, **kwargs):
        if kwargs.get('hour', 0) > 23 and kwargs.get('day') is None:
            kwargs['day'] = self.day + kwargs['hour'] // 24
            kwargs['hour'] = kwargs['hour'] % 24
        return super().replace(**kwargs)


class ValidationException(Exception):
    def __init__(self, args):
        super().__init__(args)


class MissingSegmentException(ValidationException):
    def __init__(self, url, response):
        msg = 'Failed to get segment: {:d} {} {}'.format(
            response.status_code, response.status, url)
        super().__init__(
            (msg, url, response.status))
        self.url = url
        self.status = response.status_code
        self.reason = response.status


class HttpClient(TestCaseMixin):
    @abstractmethod
    def get(self, url, headers=None, params=None, status=None, xhr=False):
        raise Exception("Not implemented")


class ContextAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        url = getattr(self.extra, "url", None)
        if url is not None and 'http' not in msg:
            return f'{msg}\n    "{url}"\n', kwargs
        return msg, kwargs


class DashElement(TestCaseMixin):
    class Parent:
        pass
    xmlNamespaces = {
        'cenc': 'urn:mpeg:cenc:2013',
        'dash': 'urn:mpeg:dash:schema:mpd:2011',
        'mspr': 'urn:microsoft:playready',
        'scte35': "http://www.scte.org/schemas/35/2016",
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'prh': 'http://schemas.microsoft.com/DRM/2007/03/PlayReadyHeader',
    }

    attributes = []

    def __init__(self, elt, parent, options=None, url=None):
        self.parent = parent
        self.url = url
        if parent:
            self.mode = parent.mode
            self.url = parent.url
            self.validator = getattr(parent, "validator")
            self.options = parent.options
            self.http = parent.http
            self.errors = parent.errors
            self.filenames = parent.filenames
        else:
            assert options is not None
            self.options = options
            self.errors = []
            self.filenames = set()
        # self.log = logging.getLogger(self.classname())
        #    log.addFilter(mixins.HideMixinsFilter())
        self.log = ContextAdapter(self.options.log, self)
        self.log.setLevel = self.options.log.setLevel
        self.baseurl = None
        self.ID = None
        if elt is not None:
            base = elt.findall('./dash:BaseURL', self.xmlNamespaces)
            if len(base):
                self.baseurl = base[0].text
                if self.parent and not self.baseurl.startswith('http'):
                    self.baseurl = urllib.parse.urljoin(
                        parent.baseurl, self.baseurl)
            elif parent:
                self.baseurl = parent.baseurl
            self.ID = elt.get('id')
        if self.ID is None:
            self.ID = str(id(self))
        self.parse_attributes(elt, self.attributes)

    def parse_attributes(self, elt, attributes):
        for name, conv, dflt in attributes:
            if ':' in name:
                ns, nm = name.split(':')
                name = nm
                val = elt.get(f"{{{self.xmlNamespaces[ns]}}}{nm}")
            else:
                val = elt.get(name)
            if val is not None:
                try:
                    val = conv(val)
                except (ValueError) as err:
                    self.log.error('Attribute "%s@%s" has invalid value "%s": %s',
                                   self.classname(), name, val, err)
                    xml = ET.tostring(elt)
                    print(f'Error parsing attribute "{name}": {xml}')
                    raise err
            elif dflt == DashElement.Parent:
                val = getattr(self.parent, name, None)
            else:
                val = dflt
            setattr(self, name, val)

    def dump_attributes(self):
        for item in self.attributes:
            self.log.debug(
                '%s="%s"', item[0], str(
                    getattr(
                        self, item[0], None)))

    @property
    def mpd(self):
        if self.parent:
            return self.parent.mpd
        return self

    @classmethod
    def init_xml_namespaces(clz):
        for prefix, url in clz.xmlNamespaces.items():
            ET.register_namespace(prefix, url)

    @abstractmethod
    def validate(self, depth=-1) -> Never:
        raise Exception("Not implemented")

    def unique_id(self) -> str:
        rv = [self.classname(), self.ID]
        p = self.parent
        while p is not None:
            rv.append(p.ID)
            p = p.parent
        return '/'.join(rv)

    def _check_true(self, result: bool, a: Any, b: Any,
                    msg: str | None, template: str) -> bool:
        if not result:
            if msg is None:
                msg = template.format(a, b)
            if self.options.strict:
                raise AssertionError(msg)
            self.log.warning('%s', msg)
            self.errors.append(msg)
        return result

    def output_filename(self, default, bandwidth, prefix=None, filename=None, makedirs=False):
        if filename is None:
            filename = self.url
        if filename.startswith('http:'):
            parts = urllib.parse.urlsplit(filename)
            head, tail = os.path.split(parts.path)
            if tail and tail[0] != '.':
                filename = tail
            else:
                filename = default
        else:
            head, tail = os.path.split(filename)
            if tail:
                filename = tail
        if '?' in filename:
            filename = filename.split('?')[0]
        if '#' in filename:
            filename = filename.split('#')[0]
        root, ext = os.path.splitext(filename)
        if root == '':
            root, ext = os.path.splitext(default)
        now = self.options.start_time.replace(microsecond=0)
        dest = os.path.join(self.options.dest,
                            to_iso_datetime(now).replace(':', '-'))
        if prefix is not None and bandwidth is not None:
            filename = f'{prefix}_{bandwidth}.mp4'
        else:
            filename = ''.join([root, ext])
        self.log.debug('dest=%s, filename=%s', dest, filename)
        if makedirs:
            if not os.path.exists(dest):
                os.makedirs(dest)
        return os.path.join(dest, filename)

    def open_file(self, filename, options):
        self.filenames.add(filename)
        if options.prefix:
            fd = open(filename, 'ab')
            fd.seek(0, os.SEEK_END)
            return fd
        return open(filename, 'wb')


class DashValidator(DashElement):
    def __init__(self, url, http_client, mode=None, options=None, xml=None):
        DashElement.init_xml_namespaces()
        super().__init__(None, parent=None, options=options)
        self.http = http_client
        self.baseurl = self.url = url
        self.options = options if options is not None else ValidatorOptions()
        self.mode = mode
        self.validator = self
        self.xml = xml
        self.manifest = None
        self.prev_manifest = None
        if xml is not None:
            self.manifest = Manifest(self, self.url, self.mode, self.xml)

    def load(self, xml=None):
        self.prev_manifest = self.manifest
        self.xml = xml
        if self.xml is None:
            result = self.http.get(self.url)
            self.assertEqual(
                result.status_code, 200,
                f'Failed to load manifest: {result.status_code} {self.url}')
            # print(result.text)
            xml = ET.parse(io.BytesIO(result.get_data(as_text=False)))
            self.xml = xml.getroot()
        if self.mode is None:
            if self.xml.get("type") == "dynamic":
                self.mode = 'live'
            elif "urn:mpeg:dash:profile:isoff-on-demand:2011" in self.xml.get('profiles'):
                self.mode = 'odvod'
            else:
                self.mode = 'vod'
        self.manifest = Manifest(self, self.url, self.mode, self.xml)

    def validate(self, depth=-1):
        if self.xml is None:
            self.load()
        if self.options.save:
            self.save_manifest()
        if self.mode == 'live' and self.prev_manifest is not None:
            if self.prev_manifest.availabilityStartTime != self.manifest.availabilityStartTime:
                raise ValidationException('availabilityStartTime has changed from {:s} to {:s}'.format(
                    self.prev_manifest.availabilityStartTime.isoformat(),
                    self.manifest.availabilityStartTime.isoformat()))
            age = self.manifest.publishTime - self.prev_manifest.publishTime
            fmt = (r'Manifest should have updated by now. minimumUpdatePeriod is {0} but ' +
                   r'manifest has not been updated for {1} seconds')
            self.checkLessThan(
                age, 5 * self.manifest.minimumUpdatePeriod,
                fmt.format(self.manifest.minimumUpdatePeriod, age.total_seconds()))
        self.manifest.validate(depth=depth)
        if self.options.save and self.options.prefix:
            kids = set()
            for p in self.manifest.periods:
                for a in p.adaptation_sets:
                    if a.default_KID is not None:
                        kids.add(a.default_KID)
            config = {
                'keys': [{'computed': True, 'kid': kid} for kid in list(kids)],
                'streams': [{
                    'prefix': self.options.prefix,
                    'title': self.url
                }],
                'files': list(self.manifest.filenames)
            }
            filename = self.output_filename(
                default=None, bandwidth=None, filename=f'{self.options.prefix}.json')
            with open(filename, 'w') as dest:
                json.dump(config, dest, indent=2)
        return self.errors

    def save_manifest(self, filename=None):
        if self.options.dest:
            filename = self.output_filename(
                'manifest.mpd', bandwidth=None, filename=filename, makedirs=True)
            ET.ElementTree(self.xml).write(filename, xml_declaration=True)
        else:
            print(ET.tostring(self.xml))

    def sleep(self):
        self.checkEqual(self.mode, 'live')
        self.checkIsNotNone(self.manifest)
        dur = max(self.manifest.minimumUpdatePeriod.seconds, 1)
        self.log.info('Wait %d seconds', dur)
        time.sleep(dur)

    @abstractmethod
    def get_representation_info(self, representation):
        """Get the Representation object for the specified media URL.
        The returned object must have the following attributes:
        * encrypted: bool         - Is AdaptationSet encrypted ?
        * iv_size: int            - IV size in bytes (8 or 16) (N/A if encrypted==False)
        * timescale: int          - The timescale units for the AdaptationSet
        * num_segments: int       - The number of segments in the stream (VOD only)
        * segments: List[Segment] - Information about each segment (optional)
        """
        raise Exception("Not implemented")

    @abstractmethod
    def set_representation_info(self, representation, info):
        raise Exception("Not implemented")


class RepresentationInfo:
    def __init__(self, encrypted, timescale, num_segments=0, **kwargs):
        self.encrypted = encrypted
        self.timescale = timescale
        self.num_segments = num_segments
        self.tested_media_segment = set()
        self.init_segment = None
        self.media_segments = []
        self.segments = []
        for k, v in kwargs.items():
            setattr(self, k, v)


class Manifest(DashElement):
    attributes = [
        ('availabilityStartTime', from_isodatetime, None),
        ('minimumUpdatePeriod', from_isodatetime, None),
        ('timeShiftBufferDepth', from_isodatetime, None),
        ('mediaPresentationDuration', from_isodatetime, None),
        ('publishTime', from_isodatetime, None),
    ]

    def __init__(self, parent, url, mode, xml):
        super().__init__(xml, parent)
        self.url = url
        parsed = urllib.parse.urlparse(url)
        self.params = {}
        for key, value in urllib.parse.parse_qs(parsed.query).items():
            self.params[key] = value[0]
        self.mode = mode
        if self.baseurl is None:
            self.baseurl = url
            assert isinstance(url, str)
        if mode != 'live':
            if "urn:mpeg:dash:profile:isoff-on-demand:2011" in xml.get(
                    'profiles'):
                self.mode = 'odvod'
        if self.publishTime is None:
            self.publishTime = datetime.datetime.now()
        self.mpd_type = xml.get("type", "static")
        self.periods = [Period(p, self) for p in xml.findall('./dash:Period', self.xmlNamespaces)]
        self.dump_attributes()

    @property
    def mpd(self):
        return self

    def validate(self, depth=-1):
        self.checkGreaterThan(len(self.periods), 0,
                              "Manifest does not have a Period element: %s" % self.url)
        if self.mode == "live":
            self.checkEqual(
                self.mpd_type, "dynamic",
                "MPD@type must be dynamic for live manifest: %s" % self.url)
            self.checkIsNotNone(
                self.availabilityStartTime,
                "MPD@availabilityStartTime must be present for live manifest: %s" % self.url)
            self.checkIsNotNone(
                self.timeShiftBufferDepth,
                "MPD@timeShiftBufferDepth must be present for live manifest: %s" % self.url)
            self.checkIsNone(
                self.mediaPresentationDuration,
                "MPD@mediaPresentationDuration must not be present for live manifest: %s" % self.url)
        else:
            msg = r'MPD@type must be static for VOD manifest, got "{}": {}'.format(
                self.mpd_type, self.url)
            self.checkEqual(self.mpd_type, "static", msg=msg)
            if self.mediaPresentationDuration is not None:
                self.checkGreaterThan(
                    self.mediaPresentationDuration,
                    datetime.timedelta(seconds=0),
                    'Invalid MPD@mediaPresentationDuration "{}": {}'.format(
                        self.mediaPresentationDuration, self.url))
            else:
                msg = 'If MPD@mediaPresentationDuration is not present, ' +\
                      'Period@duration must be present: ' + self.url
                for p in self.periods:
                    self.checkIsNotNone(p.duration, msg)
            self.checkIsNone(
                self.minimumUpdatePeriod,
                "MPD@minimumUpdatePeriod must not be present for VOD manifest: %s" % self.url)
            self.checkIsNone(
                self.availabilityStartTime,
                "MPD@availabilityStartTime must not be present for VOD manifest: %s" % self.url)
        if depth != 0:
            for period in self.periods:
                period.validate(depth - 1)


class DescriptorElement:
    def __init__(self, elt):
        self.attributes = elt.attrib
        self.tag = elt.tag
        self.children = []
        self.text = elt.text
        for child in elt:
            self.children.append(DescriptorElement(child))


class Descriptor(DashElement):
    attributes = [
        ('schemeIdUri', str, None),
        ('value', str, ""),
    ]

    def __init__(self, elt, parent):
        super().__init__(elt, parent)
        self.children = []
        for child in elt:
            self.children.append(DescriptorElement(child))

    def validate(self, depth=-1):
        self.checkIsNotNone(self.schemeIdUri)


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

    def __init__(self, elt, parent):
        super().__init__(elt, parent)
        self.children = []
        for child in elt:
            self.children.append(child)

    def validate(self, depth=-1):
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

    def __init__(self, elt, parent):
        super().__init__(elt, parent)
        evs = elt.findall('./dash:Event', self.xmlNamespaces)
        self.events = [DashEvent(a, self) for a in evs]


class EventStream(EventStreamBase):
    """
    An EventStream, where events are carried in the manifest
    """

    def __init__(self, elt, parent):
        super().__init__(elt, parent)

    def validate(self, depth=-1):
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

    def __init__(self, elt, parent):
        super().__init__(elt, parent)

    def validate(self, depth=-1):
        super().validate(depth)
        self.checkEqual(len(self.children), 0)

class Period(DashElement):
    attributes = [
        ('start', from_isodatetime, None),
        # self.parent.mediaPresentationDuration),
        ('duration', from_isodatetime, DashElement.Parent),
    ]

    def __init__(self, period, parent):
        super().__init__(period, parent)
        if self.parent.mpd_type == 'dynamic':
            if self.start is None:
                self.start = parent.availabilityStartTime
            else:
                self.start = parent.availabilityStartTime + \
                    datetime.timedelta(seconds=self.start.total_seconds())
        adps = period.findall('./dash:AdaptationSet', self.xmlNamespaces)
        self.adaptation_sets = [AdaptationSet(a, self) for a in adps]
        evs = period.findall('./dash:EventStream', self.xmlNamespaces)
        self.event_streams = [EventStream(r, self) for r in evs]

    def validate(self, depth=-1):
        if depth == 0:
            return
        for adap_set in self.adaptation_sets:
            adap_set.validate(depth - 1)
        for evs in self.event_streams:
            evs.validate(depth - 1)


class HttpRange:
    def __init__(self, start, end=None):
        if end is None:
            start, end = start.split('-')
        self.start = int(start)
        self.end = int(end)

    def __str__(self):
        return f'{self.start}-{self.end}'


class SegmentReference(DashElement):
    REPR_FMT = 'SegmentReference(url={sourceURL}, duration={duration}, decode_time={decode_time}, mediaRange={mediaRange}'

    def __init__(self, parent, url, start, end, decode_time, duration):
        super().__init__(elt=None, url=url, parent=parent)
        self.sourceURL = url
        self.media = url
        self.mediaRange = HttpRange(start, end)
        self.decode_time = decode_time
        self.duration = duration

    def validate(self, depth=-1):
        self.checkGreaterThan(self.duration, 0)

    def __repr__(self):
        return self.REPR_FMT.format(**self.__dict__)


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

class URLType(DashElement):
    attributes = [
        ("sourceURL", str, None),
        ("range", HttpRange, None),
    ]

    def __init__(self, elt, parent):
        super().__init__(elt, parent)

    def validate(self, depth=-1):
        pass


class FrameRateType(TestCaseMixin):
    pattern = re.compile(r"([0-9]*[0-9])(/[0-9]*[0-9])?$")

    def __init__(self, num, denom=1):
        if isinstance(num, str):
            match = self.pattern.match(num)
            self.checkIsNotNone(match, 'Invalid frame rate "{}", pattern is "{}"'.format(
                num, self.pattern.pattern))
            num = int(match.group(1), 10)
            if match.group(2):
                denom = int(match.group(2)[1:])
        self.num = num
        self.denom = denom
        if denom == 1:
            self.value = num
        else:
            self.value = float(num) / float(denom)

    def __float__(self):
        return self.value

    def __repr__(self):
        if self.denom == 1:
            return str(self.value)
        return f'{self.num:d}/{self.denom:d}'

    def validate(self, depth=-1):
        pass


class MultipleSegmentBaseType(SegmentBaseType):
    attributes = SegmentBaseType.attributes + [
        ('duration', int, None),
        ('startNumber', int, DashElement.Parent),
    ]

    def __init__(self, elt, parent):
        super().__init__(elt, parent)
        self.segmentTimeline = None
        timeline = elt.findall('./dash:SegmentTimeline', self.xmlNamespaces)
        if len(timeline):
            self.segmentTimeline = SegmentTimeline(timeline[0], self)
        self.BitstreamSwitching = None
        bss = elt.findall('./dash:BitstreamSwitching', self.xmlNamespaces)
        if len(bss):
            self.BitstreamSwitching = bss[0].text

    def validate(self, depth=-1):
        super().validate(depth)
        if self.segmentTimeline is not None:
            # 5.3.9.2.1: The attribute @duration and the element SegmentTimeline
            # shall not be present at the same time.
            self.checkIsNone(self.duration)


class RepresentationBaseType(DashElement):
    attributes = [
        ('profiles', str, None),
        ('width', int, None),
        ('height', int, None),
        ('frameRate', FrameRateType, None),
        ('mimeType', str, None),
    ]

    def __init__(self, elt, parent):
        super().__init__(elt, parent)
        prot = elt.findall('./dash:ContentProtection', self.xmlNamespaces)
        self.contentProtection = [ContentProtection(cp, self) for cp in prot]
        self.segmentTemplate = None
        templates = elt.findall('./dash:SegmentTemplate', self.xmlNamespaces)
        if len(templates):
            self.segmentTemplate = SegmentTemplate(templates[0], self)
        self.segmentList = None
        seg_list = elt.findall('./dash:SegmentList', self.xmlNamespaces)
        self.segmentList = [SegmentListType(s, self) for s in seg_list]
        ibevs = elt.findall('./dash:InbandEventStream', self.xmlNamespaces)
        self.event_streams = [InbandEventStream(r, self) for r in ibevs]


class SegmentTimeline(DashElement):
    SegmentEntry = collections.namedtuple(
        'SegmentEntry', ['start', 'duration'])

    def __init__(self, timeline, parent):
        super().__init__(timeline, parent)
        self.segments = []
        start = None
        self.duration = 0
        for seg in timeline:
            repeat = int(seg.get('r', '0')) + 1
            t = seg.get('t')
            start = int(t, 10) if t is not None else start
            if start is None and not self.options.strict:
                self.log.warning('start attribute is missing for first entry in SegmentTimeline')
                start = 0
            self.checkIsNotNone(start)
            duration = int(seg.get('d'), 10)
            for r in range(repeat):
                self.segments.append(self.SegmentEntry(start, duration))
                start += duration
                self.duration += duration

    def validate(self, depth=-1):
        return


class SegmentTemplate(MultipleSegmentBaseType):
    attributes = MultipleSegmentBaseType.attributes + [
        ('media', str, None),
        ('index', str, None),
        ('initialization', str, None),
        ('bitstreamSwitching', str, None),
    ]

    def __init__(self, template, parent):
        super().__init__(template, parent)
        if self.startNumber is None:
            self.startNumber = 1


class SegmentListType(MultipleSegmentBaseType):
    def __init__(self, elt, parent):
        super().__init__(elt, parent)
        urls = elt.findall('./dash:SegmentURL', self.xmlNamespaces)
        self.segmentURLs = [SegmentURL(u, self) for u in urls]

    def validate(self, depth=-1):
        super().validate(depth)
        self.checkGreaterThan(len(self.segmentURLs), 0)
        self.checkGreaterThan(len(self.segmentURLs[0].initializationList), 0)


class SegmentURL(DashElement):
    attributes = [
        ('media', str, None),
        ('mediaRange', HttpRange, None),
        ('index', str, None),
        ('indexRange', HttpRange, None),
    ]

    def __init__(self, template, parent):
        super().__init__(template, parent)

    def validate(self, depth=-1):
        self.checkIsNotNone(self.media)
        self.checkIsNotNone(self.index)


class ContentProtection(Descriptor):
    attributes = Descriptor.attributes + [
        ('cenc:default_KID', str, None),
    ]

    def __init__(self, elt, parent):
        super().__init__(elt, parent)

    def validate(self, depth=-1):
        super().validate(depth)
        if self.schemeIdUri == "urn:mpeg:dash:mp4protection:2011":
            self.checkEqual(self.value, "cenc")
        else:
            self.checkStartsWith(self.schemeIdUri, "urn:uuid:")
        if depth == 0:
            return
        for child in self.children:
            if child.tag == '{urn:mpeg:cenc:2013}pssh':
                data = base64.b64decode(child.text)
                src = BufferedReader(None, data=data)
                atoms = mp4.Mp4Atom.load(src)
                self.checkEqual(len(atoms), 1)
                self.checkEqual(atoms[0].atom_type, 'pssh')
                pssh = atoms[0]
                if PlayReady.is_supported_scheme_id(self.schemeIdUri):
                    self.checkIsInstance(pssh.system_id, Binary)
                    self.checkEqual(pssh.system_id.data, PlayReady.RAW_SYSTEM_ID)
                    self.checkIsInstance(pssh.data, Binary)
                    pro = self.parse_playready_pro(pssh.data.data)
                    self.validate_playready_pro(pro)
            elif child.tag == '{urn:microsoft:playready}pro':
                self.checkTrue(
                    PlayReady.is_supported_scheme_id(
                        self.schemeIdUri))
                data = base64.b64decode(child.text)
                pro = self.parse_playready_pro(data)
                self.validate_playready_pro(pro)

    def parse_playready_pro(self, data):
        return PlayReady.parse_pro(BufferedReader(None, data=data))

    def validate_playready_pro(self, pro):
        self.checkEqual(len(pro), 1)
        xml = pro[0]['xml'].getroot()
        self.checkEqual(
            xml.tag,
            '{http://schemas.microsoft.com/DRM/2007/03/PlayReadyHeader}WRMHEADER')
        self.checkIn(
            xml.attrib['version'], [
                "4.0.0.0", "4.1.0.0", "4.2.0.0", "4.3.0.0"])
        if 'playready_version' in self.mpd.params:
            version = float(self.mpd.params['playready_version'])
            if version < 2.0:
                self.checkEqual(xml.attrib['version'], "4.0.0.0")
                self.checkEqual(
                    self.schemeIdUri,
                    "urn:uuid:" +
                    PlayReady.SYSTEM_ID_V10)
            elif version < 3.0:
                self.checkIn(xml.attrib['version'], ["4.0.0.0", "4.1.0.0"])
            elif version < 4.0:
                self.checkIn(
                    xml.attrib['version'], [
                        "4.0.0.0", "4.1.0.0", "4.2.0.0"])


class AdaptationSet(RepresentationBaseType):
    attributes = RepresentationBaseType.attributes + [
        ('group', int, None),
        ('lang', str, None),
        ('contentType', str, None),
        ('minBandwidth', int, None),
        ('maxBandwidth', int, None),
        ('minWidth', int, None),
        ('maxWidth', int, None),
        ('minHeight', int, None),
        ('maxHeight', int, None),
        ('minFrameRate', FrameRateType, None),
        ('maxFrameRate', FrameRateType, None),
    ]

    def __init__(self, adap_set, parent):
        super().__init__(adap_set, parent)
        reps = adap_set.findall('./dash:Representation', self.xmlNamespaces)
        self.default_KID = None
        for cp in self.contentProtection:
            if cp.default_KID:
                self.default_KID = cp.default_KID
                break
        self.representations = [Representation(r, self) for r in reps]

    def validate(self, depth=-1):
        if len(self.contentProtection):
            self.checkIsNotNone(
                self.default_KID,
                f'default_KID cannot be missing for protected stream: {self.baseurl}')
        self.checkIn(
            self.contentType,
            {'video', 'audio', 'text', 'image', 'font', 'application', None})
        if self.options.strict:
            self.checkIsNotNone(self.mimeType, 'mimeType is a mandatory attribute')
        if self.mimeType is None:
            self.log.warning('mimeType is a mandatory attribute')
        if not self.options.encrypted:
            self.checkEqual(len(self.contentProtection), 0)
        if depth == 0:
            return
        for cp in self.contentProtection:
            cp.validate(depth - 1)
        for rep in self.representations:
            try:
                rep.validate(depth - 1)
            except (AssertionError, ValidationException) as err:
                if self.options.strict:
                    raise
                self.log.error(err, exc_info=err)


class Representation(RepresentationBaseType):
    attributes = RepresentationBaseType.attributes + [
        ('bandwidth', int, None),
        ('id', str, None),
        ('qualityRanking', int, None),
        ('dependencyId', str, None),
    ]

    def __init__(self, rep, parent):
        super().__init__(rep, parent)
        if self.segmentTemplate is None:
            self.segmentTemplate = parent.segmentTemplate
        if self.segmentTemplate is None:
            self.checkEqual(self.mode, 'odvod')
        self.checkIsNotNone(self.baseurl)
        if self.mode == "odvod":
            segmentBase = rep.findall('./dash:SegmentBase', self.xmlNamespaces)
            self.checkLessThan(len(segmentBase), 2)
            if len(segmentBase):
                self.segmentBase = MultipleSegmentBaseType(
                    segmentBase[0], self)
            else:
                self.segmentBase = None
            self.generate_segments_on_demand_profile()
        else:
            self.generate_segments_live_profile()
        self.checkIsNotNone(self.init_segment)
        self.checkIsNotNone(self.media_segments)
        if self.mode != "live":
            self.checkGreaterThan(
                len(self.media_segments), 0,
                'Failed to generate any segments for Representation {} for MPD {}'.format(
                    self.unique_id(), self.mpd.url))

    def init_seg_url(self):
        if self.mode == 'odvod':
            return self.format_url_template(self.baseurl)
        self.checkIsNotNone(self.segmentTemplate)
        self.checkIsNotNone(self.segmentTemplate.initialization)
        url = self.format_url_template(self.segmentTemplate.initialization)
        return urllib.parse.urljoin(self.baseurl, url)

    def generate_segments_live_profile(self) -> None:
        self.assertNotEqual(self.mode, 'odvod')
        if not self.checkIsNotNone(self.segmentTemplate):
            return
        info = self.validator.get_representation_info(self)
        if not self.checkIsNotNone(info):
            return
        decode_time = getattr(info, "decode_time", None)
        start_number = getattr(info, "start_number", None)
        self.media_segments = []
        if not self.checkIsNotNone(self.segmentTemplate):
            self.init_segment = InitSegment(self, None, info, None)
            return
        self.init_segment = InitSegment(self, self.init_seg_url(), info, None)
        timeline = self.segmentTemplate.segmentTimeline
        seg_duration = self.segmentTemplate.duration
        if seg_duration is None:
            self.assertIsNotNone(timeline)
            seg_duration = timeline.duration / len(timeline.segments)
        if self.mode == 'vod':
            if not self.checkIsNotNone(info.num_segments):
                return
            num_segments = info.num_segments
            decode_time = self.segmentTemplate.presentationTimeOffset
            start_number = 1
        else:
            if timeline is not None:
                num_segments = len(timeline.segments)
                if decode_time is None:
                    decode_time = timeline.segments[0].start
            else:
                if not self.checkIsNotNone(
                        self.mpd.timeShiftBufferDepth,
                        msg='MPD@timeShiftBufferDepth is required for a live stream'):
                    return
                num_segments = math.floor((self.mpd.timeShiftBufferDepth.total_seconds() *
                                          self.segmentTemplate.timescale) / seg_duration)
                num_segments = int(num_segments)
                if num_segments == 0:
                    self.checkEqual(self.mpd.timeShiftBufferDepth.total_seconds(), 0)
                    return
                self.checkGreaterThan(
                    self.mpd.timeShiftBufferDepth.total_seconds(),
                    seg_duration / float(self.segmentTemplate.timescale))
                self.checkGreaterThan(num_segments, 0)
            now = datetime.datetime.now(tz=UTC())
            elapsed_time = now - self.mpd.availabilityStartTime
            elapsed_tc = scale_timedelta(elapsed_time, self.segmentTemplate.timescale, 1)
            elapsed_tc -= self.segmentTemplate.presentationTimeOffset
            last_fragment = self.segmentTemplate.startNumber + int(elapsed_tc // seg_duration)
            # first_fragment = last_fragment - math.floor(
            #    self.mpd.timeShiftBufferDepth.total_seconds() * self.segmentTemplate.timescale /
            #    seg_duration)
            if start_number is None:
                start_number = last_fragment - num_segments
            if start_number < self.segmentTemplate.startNumber:
                num_segments -= self.segmentTemplate.startNumber - start_number
                if num_segments < 1:
                    num_segments = 1
                start_number = self.segmentTemplate.startNumber
            if decode_time is None:
                decode_time = (
                    start_number - self.segmentTemplate.startNumber) * seg_duration
        self.checkIsNotNone(start_number)
        self.checkIsNotNone(decode_time)
        seg_num = start_number
        frameRate = 24
        if self.frameRate is not None:
            frameRate = self.frameRate.value
        elif self.parent.maxFrameRate is not None:
            frameRate = self.parent.maxFrameRate.value
        elif self.parent.minFrameRate is not None:
            frameRate = self.parent.minFrameRate.value
        if self.segmentTemplate is not None:
            tolerance = self.segmentTemplate.timescale / frameRate
        else:
            tolerance = info.timescale / frameRate
        num_segments = min(num_segments, 20)
        self.log.debug('Generating %d MediaSegments', num_segments)
        if timeline is not None:
            msg = r'Expected segment segmentTimeline to have at least {} items, found {}'.format(
                num_segments, len(timeline.segments))
            self.checkGreaterOrEqual(len(timeline.segments), num_segments, msg)
        for idx in range(num_segments):
            url = self.format_url_template(
                self.segmentTemplate.media, seg_num, decode_time)
            url = urllib.parse.urljoin(self.baseurl, url)
            if self.parent.contentType == 'audio':
                tol = tolerance * frameRate / 2.0
            elif idx == 0:
                tol = tolerance * 2
            else:
                tol = tolerance
            ms = MediaSegment(self, url, info, seg_num=seg_num, decode_time=decode_time,
                              tolerance=tol, seg_range=None)
            self.media_segments.append(ms)
            seg_num += 1
            if timeline is not None:
                decode_time += timeline.segments[idx].duration
            else:
                decode_time = None
            if self.options.duration is not None:
                if decode_time is None:
                    dt = seg_num * seg_duration
                else:
                    dt = decode_time
                if dt >= (self.options.duration * self.segmentTemplate.timescale):
                    return

    def generate_segments_on_demand_profile(self):
        self.media_segments = []
        self.init_segment = None
        info = self.validator.get_representation_info(self)
        self.checkIsNotNone(info)
        decode_time = None
        if info.segments:
            decode_time = 0
        if self.segmentBase and self.segmentBase.initializationList:
            url = self.baseurl
            if self.segmentBase.initializationList[0].sourceURL is not None:
                url = self.segmentBase.initializationList[0].sourceURL
            url = self.format_url_template(url)
            self.init_segment = InitSegment(
                self, url, info,
                self.segmentBase.initializationList[0].range)
        seg_list = []
        for sl in self.segmentList:
            if sl.initializationList:
                self.checkIsNotNone(sl.initializationList[0].range)
                url = self.baseurl
                if sl.initializationList[0].sourceURL is not None:
                    url = sl.initializationList[0].sourceURL
                url = self.format_url_template(url)
                self.init_segment = InitSegment(
                    self, url, info, sl.initializationList[0].range)
            seg_list += sl.segmentURLs
        if not seg_list and self.segmentBase and self.segmentBase.indexRange:
            seg_list = self.segmentBase.load_segment_index(self.baseurl)
            decode_time = seg_list[0].decode_time
        frameRate = 24
        if self.frameRate is not None:
            frameRate = self.frameRate.value
        elif self.parent.maxFrameRate is not None:
            frameRate = self.parent.maxFrameRate.value
        elif self.parent.minFrameRate is not None:
            frameRate = self.parent.minFrameRate.value
        if self.segmentTemplate is not None:
            tolerance = self.segmentTemplate.timescale / frameRate
            timescale = self.segmentTemplate.timescale
        else:
            tolerance = info.timescale / frameRate
            timescale = info.timescale
        for idx, item in enumerate(seg_list):
            self.checkIsNotNone(item.mediaRange)
            url = self.baseurl
            if item.media is not None:
                url = item.media
            seg_num = idx + 1
            if idx == 0 and self.segmentTemplate and self.segmentTemplate.segmentTimeline:
                seg_num = None
            if self.parent.contentType == 'audio':
                tol = tolerance * frameRate / 2.0
            elif idx == 0:
                tol = tolerance * 2
            else:
                tol = tolerance
            dt = getattr(item, 'decode_time', decode_time)
            ms = MediaSegment(self, url, info, seg_num=seg_num,
                              decode_time=dt, tolerance=tol,
                              seg_range=item.mediaRange)
            self.media_segments.append(ms)
            if info.segments:
                decode_time += info.segments[idx + 1]['duration']
            if self.options.duration is not None:
                if decode_time >= (self.options.duration * timescale):
                    return

    def validate(self, depth=-1):
        self.checkIsNotNone(self.bandwidth, 'bandwidth is a mandatory attribute')
        self.checkIsNotNone(self.id, 'id is a mandatory attribute')
        if self.options.strict:
            self.checkIsNotNone(self.mimeType, 'mimeType is a mandatory attribute')
        if self.mimeType is None:
            self.log.warning('mimeType is a mandatory attribute')
        info = self.validator.get_representation_info(self)
        if getattr(info, "moov", None) is None:
            info.moov = self.init_segment.validate(depth - 1)
            self.validator.set_representation_info(self, info)
        self.checkIsNotNone(info.moov)
        if self.options.encrypted:
            if self.contentProtection:
                cp_elts = self.contentProtection
            else:
                cp_elts = self.parent.contentProtection
            if self.parent.contentType == 'video':
                self.checkGreaterThan(
                    len(cp_elts), 0,
                    msg='An encrypted stream must have ContentProtection elements')
                found = False
                for elt in cp_elts:
                    if (elt.schemeIdUri == "urn:mpeg:dash:mp4protection:2011" and
                            elt.value == "cenc"):
                        found = True
                self.checkTrue(
                    found, msg="DASH CENC ContentProtection element not found")
        else:
            # parent ContentProtection elements checked in parent's validate()
            self.checkEqual(len(self.contentProtection), 0)
        if depth == 0:
            return
        if self.mode == "odvod":
            self.check_on_demand_profile()
        else:
            self.check_live_profile()
        if len(self.media_segments) == 0:
            return
        next_decode_time = self.media_segments[0].decode_time
        # next_seg_num = self.media_segments[0].seg_num
        self.log.debug('starting next_decode_time: %s', str(next_decode_time))
        for seg in self.media_segments:
            seg.set_info(info)
            if seg.decode_time is None:
                self.checkIsNotNone(next_decode_time)
                seg.decode_time = next_decode_time
            else:
                self.checkEqual(
                    next_decode_time, seg.decode_time,
                    '{}: expected decode time {} but got {}'.format(
                        seg.url, next_decode_time, seg.decode_time))
            if seg.seg_range is None and seg.url in info.tested_media_segment:
                next_decode_time = seg.next_decode_time
                continue
            moof = seg.validate(depth - 1)
            self.checkIsNotNone(moof)
            if seg.seg_num is None:
                seg.seg_num = moof.mfhd.sequence_number
            # next_seg_num = seg.seg_num + 1
            for sample in moof.traf.trun.samples:
                if not sample.duration:
                    sample.duration = info.moov.mvex.trex.default_sample_duration
                next_decode_time += sample.duration
            seg.next_decode_time = next_decode_time

    def check_live_profile(self):
        self.checkIsNotNone(self.segmentTemplate)
        if self.mode == 'vod':
            return
        self.checkEqual(self.mode, 'live')
        seg_duration = self.segmentTemplate.duration
        timeline = self.segmentTemplate.segmentTimeline
        timescale = self.segmentTemplate.timescale
        decode_time = None
        if seg_duration is None:
            self.checkIsNotNone(timeline)
            seg_duration = timeline.duration / float(len(timeline.segments))
        if timeline is not None:
            num_segments = len(self.segmentTemplate.segmentTimeline.segments)
            decode_time = timeline.segments[0].start
        else:
            self.checkIsNotNone(self.mpd.timeShiftBufferDepth)
            num_segments = math.floor(self.mpd.timeShiftBufferDepth.total_seconds() *
                                      timescale / seg_duration)
            num_segments = int(num_segments)
            num_segments = min(num_segments, 25)
        now = datetime.datetime.now(tz=UTC())
        elapsed_time = now - self.mpd.availabilityStartTime
        startNumber = self.segmentTemplate.startNumber
        # TODO: subtract Period@start
        last_fragment = startNumber + int(
            scale_timedelta(elapsed_time, timescale, seg_duration))
        first_fragment = last_fragment - math.floor(
            self.mpd.timeShiftBufferDepth.total_seconds() * timescale / seg_duration)
        if first_fragment < startNumber:
            num_segments -= startNumber - first_fragment
            if num_segments < 1:
                num_segments = 1
            first_fragment = startNumber
        if decode_time is None:
            decode_time = (first_fragment - startNumber) * seg_duration
        self.checkIsNotNone(decode_time)
        pos = (self.mpd.availabilityStartTime +
               datetime.timedelta(seconds=(decode_time / float(timescale))))
        earliest_pos = (now - self.mpd.timeShiftBufferDepth -
                        datetime.timedelta(seconds=(seg_duration / float(timescale))))
        self.checkGreaterThanOrEqual(
            pos, earliest_pos,
            'Position {} is before first available fragment time {}'.format(
                pos, earliest_pos))
        self.checkLessThan(
            pos, now, f'Pos {pos} is after current time of day {now}')

    def check_on_demand_profile(self):
        pass

    def format_url_template(self, url, seg_num=0, decode_time=0):
        """
        Replaces the template variables according the DASH template syntax
        """
        def repfn(matchobj, value):
            if isinstance(value, str):
                return value
            fmt = matchobj.group(1)
            if fmt is None:
                if isinstance(value, str):
                    fmt = r'%s'
                else:
                    fmt = r'%d'
            fmt = '{0' + fmt.replace('%', ':') + '}'
            return fmt.format(value)
        for name, value in [('RepresentationID', self.ID),
                            ('Bandwidth', self.bandwidth),
                            ('Number', seg_num),
                            ('Time', decode_time),
                            ('', '$')]:
            rx = re.compile(fr'\${name}(%0\d+d)?\$')
            url = rx.sub(lambda match: repfn(match, value), url)
        return url


class InitSegment(DashElement):
    def __init__(self, parent, url, info, seg_range):
        super().__init__(None, parent)
        self.info = info
        self.seg_range = seg_range
        self.url = url

    def validate(self, depth=-1):
        self.checkIsNotNone(self.url)
        if self.url is None:
            return
        if self.seg_range is not None:
            headers = {"Range": f"bytes={self.seg_range}"}
            expected_status = 206
        else:
            headers = None
            expected_status = 200
        self.log.debug('GET: %s %s', self.url, headers)
        response = self.http.get(self.url, headers=headers)
        # if response.status_code != expected_status:
        #     print(response.text)
        self.checkEqual(
            response.status_code, expected_status,
            msg=f'Failed to load init segment: {response.status_code}: {self.url}')
        if self.options.save:
            default = f'init-{self.parent.id}-{self.parent.bandwidth}'
            filename = self.output_filename(
                default, self.parent.bandwidth, prefix=self.options.prefix,
                makedirs=True)
            self.log.debug('saving init segment: %s', filename)
            with self.open_file(filename, self.options) as dest:
                dest.write(response.body)
        src = BufferedReader(None, data=response.get_data(as_text=False))
        atoms = mp4.Mp4Atom.load(src)
        self.checkGreaterThan(len(atoms), 1)
        self.checkEqual(atoms[0].atom_type, 'ftyp')
        moov = None
        for atom in atoms:
            if atom.atom_type == 'moov':
                moov = atom
                break
        self.checkIsNotNone(moov)
        if not self.info.encrypted:
            return moov
        try:
            pssh = moov.pssh
            self.checkEqual(len(pssh.system_id), 16)
            if pssh.system_id == PlayReady.RAW_SYSTEM_ID:
                for pro in PlayReady.parse_pro(
                        BufferedReader(None, data=pssh.data.data)):
                    root = pro['xml'].getroot()
                    version = root.get("version")
                    self.checkIn(
                        version, [
                            "4.0.0.0", "4.1.0.0", "4.2.0.0", "4.3.0.0"])
                    if 'playready_version' not in self.mpd.params:
                        continue
                    version = float(self.mpd.params['playready_version'])
                    if version < 2.0:
                        self.checkEqual(root.attrib['version'], "4.0.0.0")
                    elif version < 3.0:
                        self.checkIn(
                            root.attrib['version'], [
                                "4.0.0.0", "4.1.0.0"])
                    elif version < 4.0:
                        self.checkIn(
                            root.attrib['version'], [
                                "4.0.0.0", "4.1.0.0", "4.2.0.0"])
        except (AttributeError) as ae:
            if 'moov' in self.url:
                if 'playready' in self.url or 'clearkey' in self.url:
                    self.checkTrue(
                        'moov' not in self.url,
                        f'PSSH box should be present in {self.url}\n{ae}')
        return moov


class MediaSegment(DashElement):
    def __init__(self, parent, url, info, seg_num,
                 decode_time, tolerance, seg_range):
        super().__init__(None, parent)
        self.info = info
        self.seg_num = seg_num
        self.decode_time = decode_time
        self.tolerance = tolerance
        self.seg_range = seg_range
        self.url = url
        self.log.debug('MediaSegment: url=%s $Number$=%s $Time$=%s tolerance=%d',
                       url, str(seg_num), str(decode_time), tolerance)

    def set_info(self, info):
        self.info = info

    def validate(self, depth=-1, all_atoms=False):
        headers = None
        if self.seg_range is not None:
            headers = {"Range": f"bytes={self.seg_range}"}
        self.log.debug('MediaSegment: url=%s headers=%s', self.url, headers)
        response = self.http.get(self.url, headers=headers)
        if self.seg_range is None:
            if response.status_code != 200:
                raise MissingSegmentException(self.url, response)
        else:
            if response.status_code != 206:
                raise MissingSegmentException(self.url, response)
        if self.parent.mimeType is not None:
            if self.options.strict:
                self.checkStartsWith(response.headers['content-type'],
                                     self.parent.mimeType)
        if self.options.save:
            default = f'media-{self.parent.id}-{self.parent.bandwidth}-{self.seg_num}'
            filename = self.output_filename(
                default, self.parent.bandwidth, prefix=self.options.prefix)
            self.log.debug('saving media segment: %s', filename)
            with self.open_file(filename, self.options) as dest:
                dest.write(response.body)
        src = BufferedReader(None, data=response.get_data(as_text=False))
        options = {"strict": True}
        self.checkEqual(self.options.encrypted, self.info.encrypted)
        if self.info.encrypted:
            options["iv_size"] = self.info.iv_size
        atoms = mp4.Mp4Atom.load(src, options=options)
        self.checkGreaterThan(len(atoms), 1)
        moof = None
        mdat = None
        for a in atoms:
            if a.atom_type == 'emsg':
                self.check_emsg_box(a)
            elif a.atom_type == 'moof':
                moof = a
            elif a.atom_type == 'mdat':
                mdat = a
                self.checkIsNotNone(
                    moof,
                    msg='Failed to find moof box before mdat box')
        self.checkIsNotNone(moof)
        self.checkIsNotNone(mdat)
        try:
            senc = moof.traf.senc
            self.checkNotEqual(
                self.info.encrypted, False,
                msg='senc box should not be found in a clear stream')
            saio = moof.traf.find_child('saio')
            self.checkIsNotNone(
                saio,
                msg='saio box is required for an encrypted stream')
            self.checkEqual(
                len(saio.offsets), 1,
                msg='saio box should only have one offset entry')
            tfhd = moof.traf.find_child('tfhd')
            if tfhd is None:
                base_data_offset = moof.position
            else:
                base_data_offset = tfhd.base_data_offset
            self.checkEqual(
                senc.samples[0].position,
                saio.offsets[0] + base_data_offset,
                msg=(r'saio.offsets[0] should point to first CencSampleAuxiliaryData entry. ' +
                     'Expected {}, got {}'.format(
                         senc.samples[0].position, saio.offsets[0] + base_data_offset)))
            self.checkEqual(len(moof.traf.trun.samples), len(senc.samples))
        except AttributeError:
            self.checkNotEqual(
                self.info.encrypted, True,
                msg='Failed to find senc box in encrypted stream')
        if self.seg_num is not None:
            self.checkEqual(moof.mfhd.sequence_number, self.seg_num,
                            msg='Sequence number error, expected {}, got {}'.format(
                                self.seg_num, moof.mfhd.sequence_number))
        moov = self.info.moov
        if self.decode_time is not None:
            self.log.debug(
                'decode_time=%s base_media_decode_time=%d delta=%d',
                str(self.decode_time),
                moof.traf.tfdt.base_media_decode_time,
                abs(moof.traf.tfdt.base_media_decode_time - self.decode_time))
            seg_dt = moof.traf.tfdt.base_media_decode_time
            msg = 'Decode time {seg_dt:d} should be {dt:d} for segment {num} in {url:s}'.format(
                seg_dt=seg_dt, dt=self.decode_time, num=self.seg_num, url=self.url)
            self.checkAlmostEqual(
                seg_dt,
                self.decode_time,
                delta=self.tolerance,
                msg=msg)
        first_sample_pos = moof.traf.tfhd.base_data_offset + moof.traf.trun.data_offset
        last_sample_end = first_sample_pos
        for samp in moof.traf.trun.samples:
            last_sample_end += samp.size
        msg = ' '.join([
            r'trun.data_offset must point inside the MDAT box.',
            r'trun points to {} but first sample of MDAT is {}'.format(
                first_sample_pos, mdat.position + mdat.header_size),
            r'trun last sample is {} but end of MDAT is {}'.format(
                last_sample_end, mdat.position + mdat.size),
        ])
        self.checkGreaterThanOrEqual(first_sample_pos, mdat.position + mdat.header_size, msg)
        self.checkLessThanOrEqual(last_sample_end, mdat.position + mdat.size, msg)
        if self.options.strict:
            self.checkEqual(first_sample_pos, mdat.position + mdat.header_size, msg)
        pts_values = set()
        dts = moof.traf.tfdt.base_media_decode_time
        for sample in moof.traf.trun.samples:
            try:
                pts = dts + sample.composition_time_offset
            except AttributeError:
                pts = dts
            self.checkNotIn(pts, pts_values)
            pts_values.add(pts)
            if sample.duration is None:
                dts += moov.mvex.trex.default_sample_duration
            else:
                dts += sample.duration
        self.duration = dts - moof.traf.tfdt.base_media_decode_time
        if all_atoms:
            return atoms
        return moof

    def check_emsg_box(self, emsg):
        found = False
        for evs in self.parent.event_streams:
            self.log.debug('Found schemeIdUri="%s", value="%s"',
                           evs.schemeIdUri, evs.value)
            if (evs.schemeIdUri == emsg.scheme_id_uri and
                    evs.value == emsg.value):
                self.checkIsInstance(evs, InbandEventStream)
                found = True
        for evs in self.parent.parent.event_streams:
            self.log.debug('Found schemeIdUri="%s", value="%s"',
                           evs.schemeIdUri, evs.value)
            if (evs.schemeIdUri == emsg.scheme_id_uri and
                    evs.value == emsg.value):
                self.checkIsInstance(evs, InbandEventStream)
                found = True
        self.checkTrue(
            found,
            'Failed to find an InbandEventStream with schemeIdUri="{}" value="{}"'.format(
                emsg.scheme_id_uri, emsg.value))


if __name__ == "__main__":
    import argparse
    import requests

    class HttpResponse(TestCaseMixin):
        def __init__(self, response):
            self.response = response
            self.status_int = self.status_code = response.status_code
            self._xml = None
            self.headers = response.headers
            self.headerlist = list(response.headers.keys())
            if response.ok:
                self.status = 'OK'
            else:
                self.status = response.reason

        @property
        def xml(self):
            if self._xml is None:
                self._xml = ET.fromstring(self.response.text)
            return self._xml

        @property
        def forms(self, id):
            raise Exception("Not implemented")

        @property
        def json(self):
            return self.response.json

        @property
        def body(self):
            return self.response.content

        def mustcontain(self, *strings):
            for text in strings:
                self.checkIn(text, self.response.text)

        def warning(self, fmt, *args):
            logging.getLogger(__name__).warning(fmt, *args)

    class RequestsHttpClient(HttpClient):
        def __init__(self):
            self.session = requests.Session()

        def get(self, url, headers=None, params=None, status=None, xhr=False):
            try:
                self.log.debug('GET %s', url)
            except AttributeError:
                print('GET %s' % (url))
            if xhr:
                if headers is None:
                    headers = {'X-REQUESTED-WITH': 'XMLHttpRequest'}
                else:
                    h = {'X-REQUESTED-WITH': 'XMLHttpRequest'}
                    h.update(headers)
                    headers = h
            rv = HttpResponse(
                self.session.get(
                    url,
                    data=params,
                    headers=headers))
            if status is not None:
                self.checkEqual(rv.status_code, status)
            return rv

    class BasicDashValidator(DashValidator):
        def __init__(self, url, options):
            super().__init__(
                url,
                RequestsHttpClient(),
                options=options)
            self.representations = {}
            self.url = url

        def get_representation_info(self, rep):
            try:
                return self.representations[rep.unique_id()]
            except KeyError:
                pass
            if rep.mode == 'odvod':
                timescale = rep.segmentBase.timescale
            elif rep.segmentTemplate is not None:
                timescale = rep.segmentTemplate.timescale
            else:
                timescale = 1
            num_segments = None
            if rep.segmentTemplate and rep.segmentTemplate.segmentTimeline is not None:
                num_segments = len(rep.segmentTemplate.segmentTimeline.segments)
            else:
                duration = rep.parent.parent.duration
                if duration is None:
                    duration = rep.mpd.mediaPresentationDuration
                if duration is not None and rep.segmentTemplate:
                    seg_dur = rep.segmentTemplate.duration
                    num_segments = int(
                        math.floor(duration.total_seconds() * timescale / seg_dur))
            return RepresentationInfo(encrypted=self.options.encrypted,
                                      iv_size=self.options.ivsize,
                                      timescale=timescale,
                                      num_segments=num_segments)

        def set_representation_info(self, representation, info):
            self.representations[representation.unique_id()] = info

    parser = argparse.ArgumentParser(
        description='DASH live manifest validator')
    parser.add_argument('--strict', action='store_true', dest='strict',
                        help='Abort if an error is detected')
    parser.add_argument('-e', '--encrypted', action='store_true', dest='encrypted',
                        help='Stream is encrypted')
    parser.add_argument('-s', '--save',
                        help='save all fragments into <dest>',
                        action='store_true')
    parser.add_argument('-d', '--dest',
                        help='directory to store results',
                        required=False)
    parser.add_argument('-p', '--prefix',
                        help='filename prefix to use when storing media files',
                        required=False)
    parser.add_argument('--duration',
                        help='Maximum duration (in seconds)',
                        type=int,
                        required=False)
    parser.add_argument('--ivsize',
                        help='IV size (in bits or bytes)',
                        type=int,
                        default=64,
                        required=False)
    parser.add_argument('-v', '--verbose',
                        action='count',
                        help='increase verbosity',
                        default=0)
    parser.add_argument(
        'manifest',
        help='URL or filename of manifest to validate')
    args = parser.parse_args(namespace=ValidatorOptions(strict=False))
    # FORMAT = r"%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s\n  [%(url)s]"
    FORMAT = r"%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s"
    logging.basicConfig(format=FORMAT)
    args.log = logging.getLogger(__name__)
    args.log.addFilter(HideMixinsFilter())
    if args.verbose > 0:
        args.log.setLevel(logging.DEBUG)
        logging.getLogger('mp4').setLevel(logging.DEBUG)
        logging.getLogger('fio').setLevel(logging.DEBUG)
    if args.ivsize > 16:
        args.ivsize = args.ivsize // 8
    bdv = BasicDashValidator(args.manifest, args)
    bdv.load()
    if args.dest:
        bdv.save_manifest()
    done = False
    while not done:
        if bdv.manifest.mpd_type != 'dynamic':
            done = True
        try:
            bdv.validate()
            if bdv.manifest.mpd_type == 'dynamic' and not done:
                bdv.sleep()
                bdv.load()
        except (AssertionError, ValidationException) as err:
            logging.error(err)
            traceback.print_exc()
            if args.dest:
                bdv.save_manifest()
                filename = bdv.output_filename('error.txt', makedirs=True)
                with open(filename, 'w') as err_file:
                    err_file.write(str(err) + '\n')
                    traceback.print_exc(file=err_file)
            if args.strict:
                raise
