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
from .descriptor_element import DescriptorElement
from .validation_flag import ValidationFlag

class ContentProtection(Descriptor):
    attributes = Descriptor.attributes + [
        ('cenc:default_KID', str, None),
    ]

    async def validate(self) -> None:
        await super().validate()
        if ValidationFlag.CONTENT_PROTECTION not in self.options.verify:
            self.progress.inc()
            return
        if self.schemeIdUri == "urn:mpeg:dash:mp4protection:2011":
            self.attrs.check_equal(
                self.value, "cenc", template=r'{0} != {1}')
        else:
            self.attrs.check_starts_with(
                self.schemeIdUri, "urn:uuid:",
                template=r'Expected schemeIdUri to start with {1} but found {0}')
        async with self.pool.group(self.progress) as tg:
            for child in self.children():
                if child.tag == '{urn:mpeg:cenc:2013}pssh':
                    tg.submit(self.validate_cenc_element, child)
                elif child.tag == '{urn:microsoft:playready}pro':
                    tg.submit(self.validate_pro_element, child)
        self.progress.inc()

    def validate_cenc_element(self, child: DescriptorElement) -> None:
        data = base64.b64decode(child.text)
        src = BufferedReader(None, data=data)
        atoms = mp4.Mp4Atom.load(src)
        self.elt.check_equal(len(atoms), 1, msg='Expected one child element')
        self.elt.check_equal(
            atoms[0].atom_type, 'pssh',
            template=r'Atom type should be PSSH but got "{0}"')
        pssh = atoms[0]
        if not self.elt.check_true(
                PlayReady.is_supported_scheme_id(self.schemeIdUri),
                msg=f'Unsupported PlayReady scheme id "{self.schemeIdUri}"'):
            return
        self.elt.check_is_instance(
            pssh.system_id, Binary,
            msg='System ID should have been parsed to a Binary object')
        self.elt.check_equal(
            pssh.system_id.data, PlayReady.RAW_SYSTEM_ID,
            msg=f'Expected system ID {PlayReady.SYSTEM_ID} but got {pssh.system_id}')
        self.elt.check_is_instance(
            pssh.data, Binary,
            msg='PSSH payload should have been parsed to a Binary object')
        pro = self.parse_playready_pro(pssh.data.data)
        self.validate_playready_pro(pro)

    def validate_pro_element(self, child: DescriptorElement) -> None:
        self.elt.check_true(
            PlayReady.is_supported_scheme_id(self.schemeIdUri),
            msg=f'System ID "{self.schemeIdUri}" is not supported')
        data = base64.b64decode(child.text)
        pro = self.parse_playready_pro(data)
        self.validate_playready_pro(pro)

    def parse_playready_pro(self, data: bytes) -> None:
        return PlayReady.parse_pro(BufferedReader(None, data=data))

    def validate_playready_pro(self, pro) -> None:
        self.elt.check_equal(len(pro), 1)
        xml = pro[0]['xml'].getroot()
        self.elt.check_equal(
            xml.tag,
            '{http://schemas.microsoft.com/DRM/2007/03/PlayReadyHeader}WRMHEADER')
        self.elt.check_includes(
            ["4.0.0.0", "4.1.0.0", "4.2.0.0", "4.3.0.0"],
            xml.attrib['version'])
        if 'playready_version' in self.mpd.params:
            version = float(self.mpd.params['playready_version'])
            if version < 2.0:
                self.elt.check_equal(xml.attrib['version'], "4.0.0.0")
                self.elt.check_equal(
                    self.schemeIdUri,
                    "urn:uuid:" +
                    PlayReady.SYSTEM_ID_V10)
            elif version < 3.0:
                self.elt.check_includes(
                    {"4.0.0.0", "4.1.0.0"},
                    xml.attrib['version'], )
            elif version < 4.0:
                self.elt.check_includes(
                    {"4.0.0.0", "4.1.0.0", "4.2.0.0"},
                    xml.attrib['version'])
