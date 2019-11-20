from abc import ABCMeta, abstractmethod
import datetime
import math
import os
import sys
import urlparse
import xml.etree.ElementTree as ET

_src = os.path.join(os.path.dirname(__file__),"..", "src")
if not _src in sys.path:
    sys.path.append(_src)

import drm
import mp4
import utils
from mixins import TestCaseMixin

class DashElement(TestCaseMixin):
    xmlNamespaces = {
        'cenc': 'urn:mpeg:cenc:2013',
        'dash': 'urn:mpeg:dash:schema:mpd:2011',
        'mspr': 'urn:microsoft:playready',
	'scte35': "http://www.scte.org/schemas/35/2016",
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    }

    def __init__(self, elt, parent):
        self.element = elt
        self.parent = parent
        if parent:
            self.mode = parent.mode
        base = elt.findall('./dash:BaseURL', self.xmlNamespaces)
        if base:
            self.baseurl = base[0].text
        elif parent:
            self.baseurl = parent.baseurl
        else:
            self.baseurl = None
        self.id = elt.get('id')

    @property
    def mpd(self):
        if self.parent:
            return self.parent.mpd
        return self

    @classmethod
    def init_xml_namespaces(clz):
        for prefix, url in clz.xmlNamespaces.iteritems():
            ET.register_namespace(prefix, url)


class DashValidator(DashElement):
    __metaclass__ = ABCMeta
    
    def __init__(self, mode, mpd, url):
        DashElement.init_xml_namespaces()
        if mpd is None:
            result = self.get(url)
            self.assertEqual(result.status_int, 200)
            mpd = result.xml
        if mode is None:
            if mpd.get("type") == "dynamic":
                mode = 'live'
            elif "urn:mpeg:dash:profile:isoff-on-demand:2011" in mpd.get('profiles'):
                mode = 'odvod'
            else:
                mode = 'vod'
        super(DashValidator, self).__init__(mpd, None)
        self.url = url
        self.mode = mode
        if self.baseurl is None:
            self.baseurl = url
            assert isinstance(url, basestring)
        if mode=='live':
            self.availabilityStartTime = utils.from_isodatetime(mpd.get("availabilityStartTime"))
            self.timeShiftBufferDepth = utils.from_isodatetime(mpd.get("timeShiftBufferDepth"))
        else:
            self.mediaPresentationDuration = utils.from_isodatetime(mpd.get("mediaPresentationDuration"))
            if "urn:mpeg:dash:profile:isoff-on-demand:2011" in mpd.get('profiles'):
                self.mode = 'odvod'
        self.duration = mpd.get("mediaPresentationDuration")
        if self.duration is not None:
            self.duration = utils.from_isodatetime(self.duration)
        self.publishTime = mpd.get("publishTime")
        if self.publishTime is not None:
            self.publishTime = utils.from_isodatetime(self.publishTime)
        self.periods = map(lambda p: DashPeriod(p, self),
                           self.element.findall('./dash:Period', self.xmlNamespaces))

    def validate(self):
        root = self.element
        mpd_type = root.get("type", "static")
        period = root.find('dash:Period', self.xmlNamespaces)
        self.assertIsNotNone(period, "Manifest does not have a Period element: %s"%self.url)
        if self.mode=="live":
            self.assertEqual(mpd_type, "dynamic",
                             "MPD@type must be dynamic for live manifest: %s"%self.url)
            self.assertIsNotNone(root.get("availabilityStartTime"),
                                 "MPD@availabilityStartTime must be present for live manifest: %s"%self.url)
            self.assertIsNone(root.get("mediaPresentationDuration"),
                              "MPD@mediaPresentationDuration must not be present for live manifest: %s"%self.url)
        else:
            self.assertEqual(mpd_type, "static",
                             "MPD@type must be static for VOD manifest: %s"%self.url)
            if self.duration is not None:
                self.assertGreaterThan(self.duration, datetime.timedelta(seconds=0),
                    'Invalid MPD@mediaPresentationDuration "{}": {}'.format(self.duration, self.url))
            else:
                msg = 'If MPD@mediaPresentationDuration is not present, Period@duration must be present: %s'%self.url
                self.assertGreaterThan(len(self.periods), 0, msg)
                for p in self.periods:
                    self.assertIsNotNone(p.duration, msg)
            self.assertIsNone(root.get("minimumUpdatePeriod"),
                              "MPD@minimumUpdatePeriod must not be present for VOD manifest: %s"%self.url)
            self.assertIsNone(root.get("availabilityStartTime"),
                              "MPD@availabilityStartTime must not be present for VOD manifest: %s"%self.url)

    @abstractmethod
    def get(self, url, headers=None):
        raise Exception("Not implemented")

    @abstractmethod
    def get_adaptation_set_info(self, adaptation_set, url):
        """Get the Representation object for the specified media URL.
        The returned object must have the following attributes:
        * encrypted: bool         - Is AdaptationSet encrypted ?
        * iv_size: int            - IV size in bytes (8 or 16) (N/A if encrypted==False)
        * timescale: int          - The timescale units for the AdaptationSet
        * num_segments: int       - The number of segments in the stream (VOD only)
        * segments: List[Segment] - Information about each segment (optional)
        """
        raise Exception("Not implemented")
        
class DashPeriod(DashElement):
    def __init__(self, period, parent):
        super(DashPeriod, self).__init__(period, parent)
        self.duration = period.get("duration")
        if self.duration is not None:
            self.duration = utils.from_isodatetime(self.duration)
        a = self.element.findall('./dash:AdaptationSet', self.xmlNamespaces)
        self.adaptation_sets = map(lambda a: DashAdaptationSet(a, self), a)
                                   
    def validate(self):
        for adap_set in self.adaptation_sets:
            adap_set.validate()


class DashAdaptationSet(DashElement):
    def __init__(self, adap_set, parent):
        super(DashAdaptationSet, self).__init__(adap_set, parent)
        self.template = None
        self.startNumber = 1
        templates = adap_set.findall('./dash:SegmentTemplate', self.xmlNamespaces)
        if len(templates):
            self.template = templates[0]
            self.startNumber = int(self.template.get('startNumber','1'))
        reps = adap_set.findall('./dash:Representation', self.xmlNamespaces)
        self.representations = map(lambda r: DashRepresentation(r, self), reps)
        prot = adap_set.findall('./dash:ContentProtection', self.xmlNamespaces)
        self.default_KID = None
        for p in prot:
            d = p.get("{{{}}}default_KID".format(self.xmlNamespaces['cenc']))
            if d:
                self.default_KID = d
                break
        if len(prot):
            self.assertIsNotNone(self.default_KID,
                'default_KID cannot be missing for protected stream: {}'.format(self.baseurl))

    def validate(self):
        if self.mode=="odvod":
            self.check_on_demand()
        else:
            self.check_live()

    def check_live(self):
        for rep in self.representations:
            self.assertIsNotNone(rep.template)
            init_url = rep.format_url_template(rep.init_url)
            info = self.mpd.get_adaptation_set_info(self, init_url)
            moov = rep.check_init_segment()
            num_segments = 5
            decode_time = None
            name = rep.id.lower() + '.mp4'
            #mf = models.MediaFile.query(models.MediaFile.name==name).get()
            if info and self.mode=='vod':
                num_segments = info.num_segments - 1
                decode_time = 0
            start_number = 1
            if self.mode=='live':
                now = datetime.datetime.now(tz=utils.UTC())
                delta = now - self.mpd.availabilityStartTime
                duration = int(self.template.get('duration'))
                timescale = int(self.template.get('timescale'))
                start_number = long(delta.total_seconds() * timescale / duration)
                num_segments = math.floor(self.mpd.timeShiftBufferDepth.total_seconds() * timescale / duration)
                num_segments = int(num_segments)
                start_number -= num_segments
                if start_number < self.startNumber:
                    num_segments -= self.startNumber - start_number
                    start_number = self.startNumber
                decode_time = (start_number - self.startNumber) * duration
            first=True
            for idx in range(num_segments):
                moof = rep.check_media_segment(info, idx + start_number,
                                               decode_time=decode_time, first=first)
                first=False
                if decode_time is not None:
                    decode_time = moof.traf.tfdt.base_media_decode_time
                    for sample in moof.traf.trun.samples:
                        if sample.duration:
                            decode_time += sample.duration
                        else:
                            decode_time += moov.mvex.trex.default_sample_duration

    def check_on_demand(self):
        moov=None
        for rep in self.representations:
            info = self.mpd.get_adaptation_set_info(self, rep.baseurl)
            decode_time = 0
            for seg_num, item in enumerate(rep.segments):
                if seg_num==0:
                    self.assertTrue(item.tag.endswith('Initialization'))
                    seg_range = item.get("range")
                    self.assertIsNotNone(seg_range)
                    moov = rep.check_init_segment(seg_range)
                else:
                    self.assertTrue(item.tag.endswith("SegmentURL"))
                    seg_range = item.get("mediaRange")
                    self.assertIsNotNone(seg_range)
                    moof = rep.check_media_segment(info, seg_num, decode_time=decode_time,
                                                   seg_range=seg_range)
                    try:
                        decode_time += info.segments[seg_num].duration
                    except AttributeError:
                        for sample in moof.traf.trun.samples:
                            if not sample.duration:
                                assertIsNotNone(moov)
                                sample.duration=moov.mvex.trex.default_sample_duration
                            decode_time += sample.duration


class DashRepresentation(DashElement):
    def __init__(self, rep, parent):
        super(DashRepresentation, self).__init__(rep, parent)
        self.assertIsNotNone(self.baseurl)
        st = rep.findall('./dash:SegmentTemplate', self.xmlNamespaces)
        if len(st)>0:
            self.template = st[0]
        else:
            self.template = parent.template
        segment_list = rep.findall('./dash:SegmentList', self.xmlNamespaces)
        if segment_list:
            self.segments = list(segment_list[0])
        if self.mode != "odvod":
            self.assertIsNotNone(self.template)
            self.init_url = self.template.get("initialization")
            self.init_url = urlparse.urljoin(self.baseurl, self.init_url)
            self.init_url = self.format_url_template(self.init_url, rep)
            self.media_url = self.template.get("media")
            self.media_url = urlparse.urljoin(self.baseurl, self.media_url)
        else:
            self.init_url = self.baseurl
            self.media_url = self.baseurl

    def format_url_template(self, url, seg_num=0, decode_time=0):
        url = url.replace('$RepresentationID$', self.element.get("id"))
        url = url.replace('$Bandwidth$', self.element.get("bandwidth"))
        url = url.replace('$Number$', str(seg_num))
        url = url.replace('$Time$', str(decode_time))
        url = url.replace('$$', '$')
        return url
    
    def check_init_segment(self, seg_range=None):
        if self.mode=='odvod':
            init_url = self.format_url_template(self.baseurl)
        else:
            init_url = self.format_url_template(self.init_url)
        if self.parent.default_KID:
            self.assertIn('_enc', init_url)
        headers = None
        if seg_range is not None:
            headers = {"Range": "bytes={}".format(seg_range)}
        response = self.mpd.get(init_url, headers=headers)
        src = utils.BufferedReader(None, data=response.body)
        atoms = mp4.Mp4Atom.create(src)
        self.assertGreaterThan(len(atoms), 1)
        self.assertEqual(atoms[0].atom_type, 'ftyp')
        moov = None
        for atom in atoms:
            if atom.atom_type=='moov':
                moov = atom
                break
        self.assertIsNotNone(moov)
        if not '_enc' in init_url:
            return
        try:
            pssh = moov.pssh
            #print pssh
            self.assertEqual(len(pssh.system_id), 16)
            if pssh.system_id == drm.PlayReady.RAW_SYSTEM_ID:
                pro = drm.PlayReady.parse_pro(utils.BufferedReader(None, data=pssh.data))
                #print pro
                version = pro['xml'].getroot().get("version")
                self.assertIn(version, ["4.0.0.0", "4.1.0.0", "4.2.0.0"])
        except (AttributeError) as ae:
            if 'moov' in init_url:
                if 'playready' in init_url or 'clearkey' in init_url:
                    self.assertTrue('moov' not in init_url,
                                    'PSSH box should be present in {}\n{:s}'.format(
                                        init_url, ae))
        return moov

    def check_media_segment(self, info, seg_num, decode_time, seg_range=None, first=False):
        if self.mode=='odvod':
            media_url = self.format_url_template(self.baseurl, seg_num, decode_time)
        else:
            media_url = self.format_url_template(self.media_url, seg_num, decode_time)
        if self.parent.default_KID:
            self.assertIn('_enc', media_url)
        headers = None
        #print(media_url,decode_time)
        if seg_range is not None:
            headers = {"Range": "bytes={}".format(seg_range)}
        response = self.mpd.get(media_url, headers=headers)
        if seg_range is None:
            self.assertEqual(response.status_int, 200)
        else:
            self.assertEqual(response.status_int, 206)
        src = utils.BufferedReader(None, data=response.body)
        options={}
        if info.encrypted:
            options["iv_size"] = info.iv_size
        atoms = mp4.Mp4Atom.create(src, options=options)
        self.assertGreaterThan(len(atoms), 1)
        self.assertEqual(atoms[0].atom_type, 'moof')
        moof = atoms[0]
        self.assertEqual(moof.mfhd.sequence_number, seg_num)
        if decode_time is not None:
            seg_dt = moof.traf.tfdt.base_media_decode_time
            delta = abs(decode_time - seg_dt)
            tolerance = info.timescale if first else info.timescale/10
            if delta > tolerance:
                raise AssertionError('Decode time {seg_dt:d} should be {dt:d} (delta {delta:d} for segment {num:d} in {url:s}'.format(seg_dt=seg_dt, dt=decode_time, delta=delta, num=seg_num, url=media_url))
        return moof

if __name__ == "__main__":
    import requests

    class Info(object):
        def __init__(self, **kwargs):
            for k,v in kwargs.iteritems():
                setattr(self, k, v)

    class HttpResponse(object):
        def __init__(self, response):
            self.response = response
            self.status_int = response.status_code
            self._xml = None

        @property
        def xml(self):
            if self._xml is None:
                self._xml = ET.fromstring(self.response.text)
            return self._xml

        @property
        def body(self):
            return self.response.content

    class BasicDashValidator(DashValidator):
        def __init__(self, url):
            self.session = requests.Session()
            super(BasicDashValidator, self).__init__(None, None, url)

        def get(self, url, headers=None):
            print('get', url)
            return HttpResponse(self.session.get(url))
            

        def get_adaptation_set_info(self, adaptation_set, url):
            timescale = int(adaptation_set.template.get('timescale', '1'), 10)
            duration = adaptation_set.parent.duration
            num_segments = None
            if duration is None:
                duration = adaptation_set.mpd.duration
            if duration is not None:
                seg_dur = int(adaptation_set.template.get('duration', '1'), 10)
                num_segments = int(math.floor(duration.total_seconds() * timescale / seg_dur))
            return Info(encrypted=False, timescale=timescale, num_segments=num_segments)

    bdv = BasicDashValidator(sys.argv[1])
    bdv.validate()
    for period in bdv.periods:
        period.validate()

