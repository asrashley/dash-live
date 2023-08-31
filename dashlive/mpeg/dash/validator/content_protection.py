#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import base64

from dashlive.drm.playready import PlayReady
from dashlive.mpeg import mp4
from dashlive.utils.binary import Binary
from dashlive.utils.buffered_reader import BufferedReader

from .descriptor import Descriptor

class ContentProtection(Descriptor):
    attributes = Descriptor.attributes + [
        ('cenc:default_KID', str, None),
    ]

    def validate(self, depth: int = -1) -> None:
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
