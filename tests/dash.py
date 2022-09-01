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

from abc import ABCMeta, abstractmethod
import base64
import collections
import datetime
import logging
import math
import os
import re
import sys
import time
import urlparse
import xml.etree.ElementTree as ET

_src = os.path.join(os.path.dirname(__file__), "..", "src")
if _src not in sys.path:
    sys.path.append(_src)

import mixins
import mp4
from mpeg import MPEG_TIMEBASE
import scte35
import utils
from drm.playready import PlayReady

class Options(object):
    def __init__(self, strict=True):
        self.strict = strict


class UTC(datetime.tzinfo):
    def utcoffset(self, dt):
        return datetime.timedelta(0)

    def dst(self, dt):
        return datetime.timedelta(0)

    def tzname(self):
        return 'UTC'


class RelaxedDateTime(datetime.datetime):
    def replace(self, **kwargs):
        if kwargs.get('hour', 0) > 23 and kwargs.get('day') is None:
            kwargs['day'] = self.day + kwargs['hour'] // 24
            kwargs['hour'] = kwargs['hour'] % 24
        return super(RelaxedDateTime, self).replace(**kwargs)


class ValidationException(Exception):
    def __init__(self, args):
        super(ValidationException, self).__init__(args)


class MissingSegmentException(ValidationException):
    def __init__(self, url, response):
        msg = 'Failed to get segment: {0:d} {1} {2}'.format(
            response.status_int, response.status, url)
        super(
            MissingSegmentException, self).__init__(
            (msg, url, response.status))
        self.url = url
        self.status = response.status_int
        self.reason = response.status


class HttpClient(mixins.TestCaseMixin):
    __metaclass__ = ABCMeta

    @abstractmethod
    def get(self, url, headers=None, params=None, status=None, xhr=False):
        raise Exception("Not implemented")


class ContextAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        url = getattr(self.extra, "url", None)
        if url is not None and 'http' not in msg:
            return '%s\n    "%s"\n' % (msg, url), kwargs
        return msg, kwargs


class DashElement(mixins.TestCaseMixin):
    __metaclass__ = ABCMeta

    class Parent(object):
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
        else:
            assert options is not None
            self.options = options
        # self.log = logging.getLogger(self.classname)
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
                    self.baseurl = urlparse.urljoin(
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
                val = elt.get("{{{0}}}{1}".format(self.xmlNamespaces[ns], nm))
            else:
                val = elt.get(name)
            if val is not None:
                try:
                    val = conv(val)
                except (ValueError) as err:
                    self.log.error('Attribute "%s@%s" has invalid value "%s": %s',
                                   self.classname, name, val, err)
                    print(ET.tostring(elt))
                    raise
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
        for prefix, url in clz.xmlNamespaces.iteritems():
            ET.register_namespace(prefix, url)

    @abstractmethod
    def validate(self, depth=-1):
        raise Exception("Not implemented")

    def unique_id(self):
        rv = [self.classname, self.ID]
        p = self.parent
        while p is not None:
            rv.append(p.ID)
            p = p.parent
        return '/'.join(rv)

    def _check_true(self, result, a, b, msg, template):
        if not result:
            if msg is None:
                msg = template.format(a, b)
            if self.options.strict:
                raise AssertionError(msg)
            self.log.warning('%s', msg)


class DashValidator(DashElement):
    __metaclass__ = ABCMeta

    def __init__(self, url, http_client, mode=None, options=None):
        DashElement.init_xml_namespaces()
        super(DashValidator, self).__init__(None, parent=None, options=options)
        self.http = http_client
        self.baseurl = self.url = url
        self.options = options if options is not None else Options()
        self.mode = mode
        self.validator = self
        self.xml = None
        self.manifest = None
        self.prev_manifest = None

    def load(self, xml=None):
        self.prev_manifest = self.manifest
        self.xml = xml
        if self.xml is None:
            result = self.http.get(self.url)
            self.assertEqual(result.status_int, 200,
                             'Failed to load manifest: {0:d} {1}'.format(
                                 result.status_int, self.url))
            self.xml = result.xml
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

    def save_manifest(self, filename=None):
        now = RelaxedDateTime.now(UTC())
        if filename is None:
            filename = self.url
        if filename.startswith('http:'):
            parts = urlparse.urlsplit(filename)
            head, tail = os.path.split(parts.path)
            if tail and tail[0] != '.':
                filename = tail
            else:
                filename = 'manifest.mpd'
        else:
            head, tail = os.path.split(filename)
            if tail:
                filename = tail
        if self.options.dest:
            if not os.path.exists(self.options.dest):
                os.makedirs(self.options.dest)
            root, ext = os.path.splitext(filename)
            filename = r'{}-{}{}'.format(root, now.isoformat(), ext)
            ET.ElementTree(
                self.manifest.element).write(
                os.path.join(
                    self.options.dest,
                    filename))
        else:
            print(ET.tostring(self.manifest.element))

    def sleep(self):
        self.assertEqual(self.mode, 'live')
        self.assertIsNotNone(self.manifest)
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


class RepresentationInfo(object):
    def __init__(self, encrypted, timescale, num_segments=0, **kwargs):
        self.encrypted = encrypted
        self.timescale = timescale
        self.num_segments = num_segments
        self.tested_media_segment = set()
        self.init_segment = None
        self.media_segments = []
        self.segments = []
        for k, v in kwargs.iteritems():
            setattr(self, k, v)


class Manifest(DashElement):
    attributes = [
        ('availabilityStartTime', utils.from_isodatetime, None),
        ('minimumUpdatePeriod', utils.from_isodatetime, None),
        ('timeShiftBufferDepth', utils.from_isodatetime, None),
        ('mediaPresentationDuration', utils.from_isodatetime, None),
        ('publishTime', utils.from_isodatetime, None),
    ]

    def __init__(self, parent, url, mode, xml):
        super(Manifest, self).__init__(xml, parent)
        self.url = url
        parsed = urlparse.urlparse(url)
        self.params = {}
        for key, value in urlparse.parse_qs(parsed.query).iteritems():
            self.params[key] = value[0]
        self.mode = mode
        if self.baseurl is None:
            self.baseurl = url
            assert isinstance(url, basestring)
        if mode != 'live':
            if "urn:mpeg:dash:profile:isoff-on-demand:2011" in xml.get(
                    'profiles'):
                self.mode = 'odvod'
        if self.publishTime is None:
            self.publishTime = datetime.datetime.now()
        self.mpd_type = xml.get("type", "static")
        self.periods = map(lambda p: Period(p, self),
                           xml.findall('./dash:Period', self.xmlNamespaces))
        self.dump_attributes()

    @property
    def mpd(self):
        return self

    def validate(self, depth=-1):
        self.assertGreaterThan(len(self.periods), 0,
                               "Manifest does not have a Period element: %s" % self.url)
        if self.mode == "live":
            self.assertEqual(self.mpd_type, "dynamic",
                             "MPD@type must be dynamic for live manifest: %s" % self.url)
            self.assertIsNotNone(self.availabilityStartTime,
                                 "MPD@availabilityStartTime must be present for live manifest: %s" % self.url)
            self.assertIsNotNone(self.timeShiftBufferDepth,
                                 "MPD@timeShiftBufferDepth must be present for live manifest: %s" % self.url)
            self.assertIsNone(self.mediaPresentationDuration,
                              "MPD@mediaPresentationDuration must not be present for live manifest: %s" % self.url)
        else:
            self.assertEqual(self.mpd_type, "static",
                             "MPD@type must be static for VOD manifest: %s" % self.url)
            if self.mediaPresentationDuration is not None:
                self.assertGreaterThan(self.mediaPresentationDuration, datetime.timedelta(seconds=0),
                                       'Invalid MPD@mediaPresentationDuration "{}": {}'.format(
                    self.mediaPresentationDuration, self.url))
            else:
                msg = 'If MPD@mediaPresentationDuration is not present, ' +\
                      'Period@duration must be present: ' + self.url
                for p in self.periods:
                    self.assertIsNotNone(p.duration, msg)
            self.assertIsNone(self.minimumUpdatePeriod,
                              "MPD@minimumUpdatePeriod must not be present for VOD manifest: %s" % self.url)
            self.assertIsNone(self.availabilityStartTime,
                              "MPD@availabilityStartTime must not be present for VOD manifest: %s" % self.url)
        if depth != 0:
            for period in self.periods:
                period.validate(depth - 1)


class DescriptorElement(object):
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
        ('value', str, None),
    ]

    def __init__(self, elt, parent):
        super(Descriptor, self).__init__(elt, parent)
        self.children = []
        for child in elt:
            self.children.append(DescriptorElement(child))

    def validate(self, depth=-1):
        self.assertIsNotNone(self.schemeIdUri)


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
        super(DashEvent, self).__init__(elt, parent)
        self.children = []
        for child in elt:
            self.children.append(child)

    def validate(self, depth=-1):
        if self.children:
            self.assertIsNone(self.messageData)
        if self.contentEncoding is not None:
            self.assertEqual(self.contentEncoding, 'base64')
        if self.parent.schemeIdUri == EventStreamBase.SCTE35_XML_BIN_EVENTS:
            self.assertEqual(len(self.children), 1)
            bin_elt = self.children[0].findall('./scte35:Binary', self.xmlNamespaces)
            self.assertIsNotNone(bin_elt)
            self.assertEqual(len(bin_elt), 1)
            data = base64.b64decode(bin_elt[0].text)
            src = utils.BufferedReader(None, data=data)
            sig = scte35.BinarySignal.parse(src, size=len(data))
            timescale = self.parent.timescale
            self.assertIn('splice_insert', sig)
            self.assertIn('break_duration', sig['splice_insert'])
            duration = sig['splice_insert']['break_duration']['duration']
            self.assertAlmostEqual(self.duration / timescale, duration / MPEG_TIMEBASE)
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
        super(EventStreamBase, self).__init__(elt, parent)
        evs = elt.findall('./dash:Event', self.xmlNamespaces)
        self.events = map(lambda a: DashEvent(a, self), evs)


class EventStream(EventStreamBase):
    """
    An EventStream, where events are carried in the manifest
    """

    def __init__(self, elt, parent):
        super(EventStream, self).__init__(elt, parent)

    def validate(self, depth=-1):
        super(EventStream, self).validate(depth)
        self.assertNotEqual(self.schemeIdUri, self.SCTE35_INBAND_EVENTS)
        if depth == 0:
            return
        for event in self.events:
            event.validate(depth - 1)


class InbandEventStream(EventStreamBase):
    """
    An EventStream, where events are carried in the media
    """

    def __init__(self, elt, parent):
        super(InbandEventStream, self).__init__(elt, parent)

    def validate(self, depth=-1):
        super(InbandEventStream, self).validate(depth)
        self.assertEqual(len(self.children), 0)

class Period(DashElement):
    attributes = [
        ('start', utils.from_isodatetime, None),
        # self.parent.mediaPresentationDuration),
        ('duration', utils.from_isodatetime, DashElement.Parent),
    ]

    def __init__(self, period, parent):
        super(Period, self).__init__(period, parent)
        if self.parent.mpd_type == 'dynamic':
            if self.start is None:
                self.start = parent.availabilityStartTime
            else:
                self.start = parent.availabilityStartTime + \
                    datetime.timedelta(seconds=self.start.total_seconds())
        adps = period.findall('./dash:AdaptationSet', self.xmlNamespaces)
        self.adaptation_sets = map(lambda a: AdaptationSet(a, self), adps)
        evs = period.findall('./dash:EventStream', self.xmlNamespaces)
        self.event_streams = map(lambda r: EventStream(r, self), evs)

    def validate(self, depth=-1):
        if depth == 0:
            return
        for adap_set in self.adaptation_sets:
            adap_set.validate(depth - 1)
        for evs in self.event_streams:
            evs.validate(depth - 1)


class SegmentBaseType(DashElement):
    attributes = [
        ('timescale', int, 1),
        ('presentationTimeOffset', int, None),
        ('indexRange', str, None),
        ('indexRangeExact', bool, False),
        ('availabilityTimeOffset', float, None),
        ('availabilityTimeComplete', bool, None),
    ]

    def __init__(self, elt, parent):
        super(SegmentBaseType, self).__init__(elt, parent)
        inits = elt.findall('./dash:Initialization', self.xmlNamespaces)
        self.initializationList = map(lambda u: URLType(u, self), inits)
        self.representationIndex = map(lambda i: URLType(i, self),
                                       elt.findall('./dash:RepresentationIndex', self.xmlNamespaces))


class URLType(DashElement):
    attributes = [
        ("sourceURL", str, None),
        ("range", str, None),
    ]

    def __init__(self, elt, parent):
        super(URLType, self).__init__(elt, parent)

    def validate(self, depth=-1):
        pass


class FrameRateType(mixins.TestCaseMixin):
    pattern = re.compile(r"([0-9]*[0-9])(/[0-9]*[0-9])?$")

    def __init__(self, num, denom=1):
        if isinstance(num, basestring):
            match = self.pattern.match(num)
            self.assertIsNotNone(match, 'Invalid frame rate "{0}", pattern is "{1}"'.format(
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
        return '{0:d}/{1:d}'.format(self.num, self.denom)

    def validate(self, depth=-1):
        pass


class MultipleSegmentBaseType(SegmentBaseType):
    attributes = SegmentBaseType.attributes + [
        ('duration', int, None),
        ('startNumber', int, DashElement.Parent),
    ]

    def __init__(self, elt, parent):
        super(MultipleSegmentBaseType, self).__init__(elt, parent)
        self.segmentTimeline = None
        timeline = elt.findall('./dash:SegmentTimeline', self.xmlNamespaces)
        if len(timeline):
            self.segmentTimeline = SegmentTimeline(timeline[0], self)
        self.BitstreamSwitching = None
        bss = elt.findall('./dash:BitstreamSwitching', self.xmlNamespaces)
        if len(bss):
            self.BitstreamSwitching = bss[0].text

    def validate(self, depth=-1):
        super(MultipleSegmentBaseType, self).validate(depth)
        if self.segmentTimeline is not None:
            # 5.3.9.2.1: The attribute @duration and the element SegmentTimeline
            # shall not be present at the same time.
            self.assertIsNone(self.duration)


class RepresentationBaseType(DashElement):
    attributes = [
        ('profiles', str, None),
        ('width', int, None),
        ('height', int, None),
        ('frameRate', FrameRateType, None),
        ('mimeType', str, None),
    ]

    def __init__(self, elt, parent):
        super(RepresentationBaseType, self).__init__(elt, parent)
        prot = elt.findall('./dash:ContentProtection', self.xmlNamespaces)
        self.contentProtection = map(
            lambda cp: ContentProtection(
                cp, self), prot)
        self.segmentTemplate = None
        templates = elt.findall('./dash:SegmentTemplate', self.xmlNamespaces)
        if len(templates):
            self.segmentTemplate = SegmentTemplate(templates[0], self)
        self.segmentList = None
        seg_list = elt.findall('./dash:SegmentList', self.xmlNamespaces)
        self.segmentList = map(lambda s: SegmentListType(s, self), seg_list)


class SegmentTimeline(DashElement):
    SegmentEntry = collections.namedtuple(
        'SegmentEntry', ['start', 'duration'])

    def __init__(self, timeline, parent):
        super(SegmentTimeline, self).__init__(timeline, parent)
        self.segments = []
        start = None
        self.duration = 0
        for seg in timeline:
            repeat = int(seg.get('r', '0')) + 1
            t = seg.get('t')
            start = int(t, 10) if t is not None else start
            self.assertIsNotNone(start)
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
        super(SegmentTemplate, self).__init__(template, parent)
        if self.startNumber is None:
            self.startNumber = 1


class SegmentListType(MultipleSegmentBaseType):
    def __init__(self, elt, parent):
        super(SegmentListType, self).__init__(elt, parent)
        urls = elt.findall('./dash:SegmentURL', self.xmlNamespaces)
        self.segmentURLs = map(lambda u: SegmentURL(u, self), urls)

    def validate(self, depth=-1):
        super(SegmentListType, self).validate(depth)
        self.assertGreaterThan(len(self.segmentURLs), 0)
        self.assertGreaterThan(len(self.segmentURLs[0].initializationList), 0)


class SegmentURL(DashElement):
    attributes = [
        ('media', str, None),
        ('mediaRange', str, None),
        ('index', str, None),
        ('indexRange', str, None),
    ]

    def __init__(self, template, parent):
        super(SegmentURL, self).__init__(template, parent)

    def validate(self, depth=-1):
        self.assertIsNotNone(self.media)
        self.assertIsNotNone(self.index)


class ContentProtection(Descriptor):
    attributes = Descriptor.attributes + [
        ('cenc:default_KID', str, None),
    ]

    def __init__(self, elt, parent):
        super(ContentProtection, self).__init__(elt, parent)

    def validate(self, depth=-1):
        super(ContentProtection, self).validate(depth)
        if self.schemeIdUri == "urn:mpeg:dash:mp4protection:2011":
            self.assertEqual(self.value, "cenc")
        else:
            self.assertStartsWith(self.schemeIdUri, "urn:uuid:")
        if depth == 0:
            return
        for child in self.children:
            if child.tag == '{urn:mpeg:cenc:2013}pssh':
                data = base64.b64decode(child.text)
                src = utils.BufferedReader(None, data=data)
                atoms = mp4.Mp4Atom.create(src)
                self.assertEqual(len(atoms), 1)
                self.assertEqual(atoms[0].atom_type, 'pssh')
                pssh = atoms[0]
                if PlayReady.is_supported_scheme_id(self.schemeIdUri):
                    self.assertEqual(pssh.system_id, PlayReady.RAW_SYSTEM_ID)
                    pro = self.parse_playready_pro(pssh.data)
                    self.validate_playready_pro(pro)
            elif child.tag == '{urn:microsoft:playready}pro':
                self.assertTrue(
                    PlayReady.is_supported_scheme_id(
                        self.schemeIdUri))
                data = base64.b64decode(child.text)
                pro = self.parse_playready_pro(data)
                self.validate_playready_pro(pro)

    def parse_playready_pro(self, data):
        return PlayReady.parse_pro(utils.BufferedReader(None, data=data))

    def validate_playready_pro(self, pro):
        self.assertEqual(len(pro), 1)
        xml = pro[0]['xml'].getroot()
        self.assertEqual(
            xml.tag,
            '{http://schemas.microsoft.com/DRM/2007/03/PlayReadyHeader}WRMHEADER')
        self.assertIn(
            xml.attrib['version'], [
                "4.0.0.0", "4.1.0.0", "4.2.0.0", "4.3.0.0"])
        if 'playready_version' in self.mpd.params:
            version = float(self.mpd.params['playready_version'])
            if version < 2.0:
                self.assertEqual(xml.attrib['version'], "4.0.0.0")
                self.assertEqual(
                    self.schemeIdUri,
                    "urn:uuid:" +
                    PlayReady.SYSTEM_ID_V10)
            elif version < 3.0:
                self.assertIn(xml.attrib['version'], ["4.0.0.0", "4.1.0.0"])
            elif version < 4.0:
                self.assertIn(
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
        super(AdaptationSet, self).__init__(adap_set, parent)
        reps = adap_set.findall('./dash:Representation', self.xmlNamespaces)
        self.default_KID = None
        for cp in self.contentProtection:
            if cp.default_KID:
                self.default_KID = cp.default_KID
                break
        self.representations = map(lambda r: Representation(r, self), reps)
        ibevs = adap_set.findall('./dash:InbandEventStream', self.xmlNamespaces)
        self.event_streams = map(lambda r: InbandEventStream(r, self), ibevs)

    def validate(self, depth=-1):
        if len(self.contentProtection):
            self.assertIsNotNone(self.default_KID,
                                 'default_KID cannot be missing for protected stream: {}'.format(self.baseurl))
        self.assertIn(self.contentType, ['video', 'audio', None])
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
        ('qualityRanking', int, None),
        ('dependencyId', str, None),
    ]

    def __init__(self, rep, parent):
        super(Representation, self).__init__(rep, parent)
        if self.segmentTemplate is None:
            self.segmentTemplate = parent.segmentTemplate
        if self.segmentTemplate is None:
            self.assertEqual(self.mode, 'odvod')
        self.assertIsNotNone(self.baseurl)
        if self.mode != "odvod":
            self.generate_segments_live_profile()
        else:
            self.generate_segments_on_demand_profile()
        self.assertIsNotNone(self.init_segment)
        self.assertIsNotNone(self.media_segments)
        self.assertGreaterThan(len(self.media_segments), 0,
                               'Failed to generate any segments for Representation %s of %s' % (
                                   self.unique_id(), self.mpd.url))

    def init_seg_url(self):
        if self.mode == 'odvod':
            return self.format_url_template(self.baseurl)
        self.assertIsNotNone(self.segmentTemplate)
        self.assertIsNotNone(self.segmentTemplate.initialization)
        url = self.format_url_template(self.segmentTemplate.initialization)
        return urlparse.urljoin(self.baseurl, url)

    def generate_segments_live_profile(self):
        self.assertNotEqual(self.mode, 'odvod')
        self.assertIsNotNone(self.segmentTemplate)
        info = self.validator.get_representation_info(self)
        self.assertIsNotNone(info)
        decode_time = getattr(info, "decode_time", None)
        start_number = getattr(info, "start_number", None)
        timeline = self.segmentTemplate.segmentTimeline
        if self.mode == 'vod':
            self.assertIsNotNone(info.num_segments)
            num_segments = info.num_segments
            decode_time = 0
            start_number = 1
        else:
            seg_duration = self.segmentTemplate.duration
            if seg_duration is None:
                self.assertIsNotNone(timeline)
                seg_duration = timeline.duration / len(timeline.segments)
            if timeline is not None:
                num_segments = len(timeline.segments)
                if decode_time is None:
                    decode_time = timeline.segments[0].start
            else:
                self.assertIsNotNone(self.mpd.timeShiftBufferDepth)
                self.assertGreaterThan(self.mpd.timeShiftBufferDepth.total_seconds(),
                                       seg_duration / self.segmentTemplate.timescale)
                num_segments = math.floor(self.mpd.timeShiftBufferDepth.total_seconds() *
                                          self.segmentTemplate.timescale / seg_duration)
                num_segments = int(num_segments)
                self.assertGreaterThan(num_segments, 0)
                num_segments = min(num_segments, 25)
            now = datetime.datetime.now(tz=utils.UTC())
            elapsed_time = now - self.mpd.availabilityStartTime
            last_fragment = self.segmentTemplate.startNumber + int(utils.scale_timedelta(
                elapsed_time, self.segmentTemplate.timescale, seg_duration))
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
        self.assertIsNotNone(start_number)
        self.assertIsNotNone(decode_time)
        self.init_segment = InitSegment(self, self.init_seg_url(), info, None)
        self.media_segments = []
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
        self.log.debug('Generating %d MediaSegments', num_segments)
        for idx in range(num_segments):
            url = self.format_url_template(
                self.segmentTemplate.media, seg_num, decode_time)
            url = urlparse.urljoin(self.baseurl, url)
            if self.parent.contentType == 'audio':
                tol = tolerance * frameRate / 2
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

    def generate_segments_on_demand_profile(self):
        self.media_segments = []
        self.init_segment = None
        info = self.validator.get_representation_info(self)
        self.assertIsNotNone(info)
        decode_time = None
        if info.segments:
            decode_time = 0
        seg_list = []
        for sl in self.segmentList:
            if sl.initializationList:
                self.assertIsNotNone(sl.initializationList[0].range)
                url = self.baseurl
                if sl.initializationList[0].sourceURL is not None:
                    url = sl.initializationList[0].sourceURL
                url = self.format_url_template(url)
                self.init_segment = InitSegment(
                    self, url, info, sl.initializationList[0].range)
            seg_list += sl.segmentURLs
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
        for idx, item in enumerate(seg_list):
            self.assertIsNotNone(item.mediaRange)
            url = self.baseurl
            if item.media is not None:
                url = item.media
            seg_num = idx + 1
            if idx == 0 and self.segmentTemplate and self.segmentTemplate.segmentTimeline:
                seg_num = None
            if self.parent.contentType == 'audio':
                tol = tolerance * frameRate / 2
            elif idx == 0:
                tol = tolerance * 2
            else:
                tol = tolerance
            ms = MediaSegment(self, url, info, seg_num=seg_num, decode_time=decode_time,
                              tolerance=tol, seg_range=item.mediaRange)
            self.media_segments.append(ms)
            if info.segments:
                decode_time += info.segments[idx + 1]['duration']

    def validate(self, depth=-1):
        self.assertIsNotNone(self.bandwidth)
        info = self.validator.get_representation_info(self)
        if getattr(info, "moov", None) is None:
            info.moov = self.init_segment.validate(depth - 1)
            self.validator.set_representation_info(self, info)
        self.assertIsNotNone(info.moov)
        if depth == 0:
            return
        if self.mode == "odvod":
            self.check_on_demand_profile()
        else:
            self.check_live_profile()
        next_decode_time = self.media_segments[0].decode_time
        # next_seg_num = self.media_segments[0].seg_num
        self.log.debug('starting next_decode_time: %s', str(next_decode_time))
        for seg in self.media_segments:
            seg.set_info(info)
            if seg.decode_time is None:
                self.assertIsNotNone(next_decode_time)
                seg.decode_time = next_decode_time
            else:
                self.assertEqual(next_decode_time, seg.decode_time,
                                 '{0}: expected decode time {1} but got {2}'.format(
                                     seg.url, next_decode_time, seg.decode_time))
            if seg.seg_range is None and seg.url in info.tested_media_segment:
                next_decode_time = seg.next_decode_time
                continue
            moof = seg.validate(depth - 1)
            self.assertIsNotNone(moof)
            if seg.seg_num is None:
                seg.seg_num = moof.mfhd.sequence_number
            # next_seg_num = seg.seg_num + 1
            for sample in moof.traf.trun.samples:
                if not sample.duration:
                    sample.duration = info.moov.mvex.trex.default_sample_duration
                next_decode_time += sample.duration
            seg.next_decode_time = next_decode_time

    def check_live_profile(self):
        self.assertIsNotNone(self.segmentTemplate)
        if self.mode == 'vod':
            return
        self.assertEqual(self.mode, 'live')
        seg_duration = self.segmentTemplate.duration
        timeline = self.segmentTemplate.segmentTimeline
        timescale = self.segmentTemplate.timescale
        decode_time = None
        if seg_duration is None:
            self.assertIsNotNone(timeline)
            seg_duration = timeline.duration / len(timeline.segments)
        if timeline is not None:
            num_segments = len(self.segmentTemplate.segmentTimeline.segments)
            decode_time = timeline.segments[0].start
        else:
            self.assertIsNotNone(self.mpd.timeShiftBufferDepth)
            num_segments = math.floor(self.mpd.timeShiftBufferDepth.total_seconds() *
                                      timescale / seg_duration)
            num_segments = int(num_segments)
            num_segments = min(num_segments, 25)
        now = datetime.datetime.now(tz=utils.UTC())
        elapsed_time = now - self.mpd.availabilityStartTime
        startNumber = self.segmentTemplate.startNumber
        # TODO: subtract Period@start
        last_fragment = startNumber + int(utils.scale_timedelta(elapsed_time, timescale,
                                                                seg_duration))
        first_fragment = last_fragment - math.floor(
            self.mpd.timeShiftBufferDepth.total_seconds() * timescale / seg_duration)
        if first_fragment < startNumber:
            num_segments -= startNumber - first_fragment
            if num_segments < 1:
                num_segments = 1
            first_fragment = startNumber
        if decode_time is None:
            decode_time = (first_fragment - startNumber) * seg_duration
        self.assertIsNotNone(decode_time)
        pos = self.mpd.availabilityStartTime + \
            datetime.timedelta(seconds=(decode_time / timescale))
        earliest_pos = now - self.mpd.timeShiftBufferDepth - \
            datetime.timedelta(seconds=(seg_duration / timescale))
        self.checkGreaterThanOrEqual(pos, earliest_pos,
                                     'Position {0} is before first available fragment time {1}'.format(
                                         pos, earliest_pos))
        self.checkLessThan(pos, now,
                           'Pos {0} is after current time of day {1}'.format(pos, now))

    def check_on_demand_profile(self):
        pass

    def format_url_template(self, url, seg_num=0, decode_time=0):
        url = url.replace('$RepresentationID$', self.ID)
        url = url.replace('$Bandwidth$', str(self.bandwidth))
        url = url.replace('$Number$', str(seg_num))
        url = url.replace('$Time$', str(decode_time))
        url = url.replace('$$', '$')
        return url


class InitSegment(DashElement):
    def __init__(self, parent, url, info, seg_range):
        super(InitSegment, self).__init__(None, parent)
        self.info = info
        self.seg_range = seg_range
        self.url = url

    def validate(self, depth=-1):
        headers = None
        if self.seg_range is not None:
            headers = {"Range": "bytes={}".format(self.seg_range)}
        self.log.debug('GET: %s %s', self.url, headers)
        response = self.http.get(self.url, headers=headers)
        src = utils.BufferedReader(None, data=response.body)
        atoms = mp4.Mp4Atom.create(src)
        self.assertGreaterThan(len(atoms), 1)
        self.assertEqual(atoms[0].atom_type, 'ftyp')
        moov = None
        for atom in atoms:
            if atom.atom_type == 'moov':
                moov = atom
                break
        self.assertIsNotNone(moov)
        if not self.info.encrypted:
            return moov
        try:
            pssh = moov.pssh
            self.assertEqual(len(pssh.system_id), 16)
            if pssh.system_id == PlayReady.RAW_SYSTEM_ID:
                for pro in PlayReady.parse_pro(
                        utils.BufferedReader(None, data=pssh.data)):
                    root = pro['xml'].getroot()
                    version = root.get("version")
                    self.assertIn(
                        version, [
                            "4.0.0.0", "4.1.0.0", "4.2.0.0", "4.3.0.0"])
                    if 'playready_version' not in self.mpd.params:
                        continue
                    version = float(self.mpd.params['playready_version'])
                    if version < 2.0:
                        self.assertEqual(root.attrib['version'], "4.0.0.0")
                    elif version < 3.0:
                        self.assertIn(
                            root.attrib['version'], [
                                "4.0.0.0", "4.1.0.0"])
                    elif version < 4.0:
                        self.assertIn(
                            root.attrib['version'], [
                                "4.0.0.0", "4.1.0.0", "4.2.0.0"])
        except (AttributeError) as ae:
            if 'moov' in self.url:
                if 'playready' in self.url or 'clearkey' in self.url:
                    self.assertTrue('moov' not in self.url,
                                    'PSSH box should be present in {}\n{:s}'.format(
                                        self.url, ae))
        return moov


class MediaSegment(DashElement):
    def __init__(self, parent, url, info, seg_num,
                 decode_time, tolerance, seg_range):
        super(MediaSegment, self).__init__(None, parent)
        self.info = info
        self.seg_num = seg_num
        self.decode_time = decode_time
        self.tolerance = tolerance
        self.seg_range = seg_range
        self.url = url
        self.log.debug('%s $Number$=%d $Time$=%s tolerance=%d', url, seg_num,
                       str(decode_time), tolerance)

    def set_info(self, info):
        self.info = info

    def validate(self, depth=-1, all_atoms=False):
        headers = None
        if self.seg_range is not None:
            headers = {"Range": "bytes={}".format(self.seg_range)}
        self.log.debug('MediaSegment: %s %s', self.url, headers)
        response = self.http.get(self.url, headers=headers)
        if self.seg_range is None:
            if response.status_int != 200:
                raise MissingSegmentException(self.url, response)
        else:
            if response.status_int != 206:
                raise MissingSegmentException(self.url, response)
        src = utils.BufferedReader(None, data=response.body)
        options = {}
        if self.info.encrypted:
            options["iv_size"] = self.info.iv_size
        atoms = mp4.Mp4Atom.create(src, options=options)
        self.assertGreaterThan(len(atoms), 1)
        moof = None
        for a in atoms:
            if a.atom_type == 'moof':
                moof = a
                break
            self.assertNotEqual(a.atom_type, 'mdat')
        self.assertIsNotNone(moof)
        if self.seg_num is not None:
            self.checkEqual(moof.mfhd.sequence_number, self.seg_num,
                            msg='Sequence number error, expected {0}, got {1}'.format(
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


if __name__ == "__main__":
    import argparse
    import requests

    class HttpResponse(mixins.TestCaseMixin):
        def __init__(self, response):
            self.response = response
            self.status_code = self.status_int = response.status_code
            self._xml = None
            self.headers = response.headers
            self.headerlist = response.headers.keys()
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
                self.assertIn(text, self.response.text)

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
                self.assertEqual(rv.status_code, status)
            return rv

    class BasicDashValidator(DashValidator):
        def __init__(self, url, options):
            super(
                BasicDashValidator,
                self).__init__(
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
            timescale = rep.segmentTemplate.timescale
            num_segments = None
            if rep.segmentTemplate.segmentTimeline is not None:
                num_segments = len(rep.segmentTemplate.segmentTimeline.segments)
            else:
                duration = rep.parent.parent.duration
                if duration is None:
                    duration = rep.mpd.mediaPresentationDuration
                if duration is not None:
                    seg_dur = rep.segmentTemplate.duration
                    num_segments = int(
                        math.floor(
                            duration.total_seconds() *
                            timescale /
                            seg_dur))
            return RepresentationInfo(encrypted=False, timescale=timescale,
                                      num_segments=num_segments)

        def set_representation_info(self, representation, info):
            self.representations[representation.unique_id()] = info

    parser = argparse.ArgumentParser(
        description='DASH live manifest validator')
    parser.add_argument('--strict', action='store_true', dest='strict',
                        help='Abort if an error is detected')
    parser.add_argument(
        '-d',
        '--dest',
        help='directory to store results',
        required=False)
    parser.add_argument(
        '-s',
        '--save',
        help='save all fragments into <dest>',
        action='store_true')
    parser.add_argument('-v', '--verbose', action='count',
                        help='increase verbosity', default=0)
    parser.add_argument(
        'manifest',
        help='URL or filename of manifest to validate')
    args = parser.parse_args(namespace=Options(strict=False))
    # FORMAT = r"%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s\n  [%(url)s]"
    FORMAT = r"%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s"
    logging.basicConfig(format=FORMAT)
    args.log = logging.getLogger(__name__)
    args.log.addFilter(mixins.HideMixinsFilter())
    if args.verbose > 0:
        args.log.setLevel(logging.DEBUG)
    bdv = BasicDashValidator(args.manifest, args)
    bdv.load()
    if args.dest:
        bdv.save_manifest()
    done = False
    while not done:
        try:
            bdv.validate()
            if bdv.manifest.mpd_type != 'dynamic':
                done = True
            else:
                bdv.sleep()
                bdv.load()
        except (AssertionError, ValidationException) as err:
            logging.error(err)
            if args.dest:
                bdv.save_manifest()
                now = RelaxedDateTime.now(UTC())
                filename = r'error-{}.txt'.format(now.isoformat())
                filename = os.path.join(args.dest, filename)
                with open(filename, 'w') as err_file:
                    err_file.write(str(err) + '\n')
            if args.strict:
                raise
