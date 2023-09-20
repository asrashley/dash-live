#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from dashlive.drm.playready import PlayReady
from dashlive.mpeg import mp4
from dashlive.utils.buffered_reader import BufferedReader

from .dash_element import DashElement

class InitSegment(DashElement):
    def __init__(self, parent, url, info, seg_range):
        super().__init__(None, parent)
        self.info = info
        self.seg_range = seg_range
        self.url = url

    def children(self) -> list[DashElement]:
        return []

    def validate(self, depth: int = -1) -> mp4.Mp4Atom | None:
        if not self.elt.check_not_none(self.url):
            return None
        if self.seg_range is not None:
            headers = {"Range": f"bytes={self.seg_range}"}
            expected_status = 206
        else:
            headers = None
            expected_status = 200
        self.log.debug('GET: %s %s', self.url, headers)
        response = self.http.get(self.url, headers=headers)
        self.elt.check_equal(
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
        try:
            atoms = mp4.Mp4Atom.load(src)
        except Exception as err:
            self.elt.add_error(f'Failed to load init segment: {err}')
            self.log.error('Failed to load init segment: %s', err)
            return None
        self.elt.check_greater_than(len(atoms), 1)
        self.elt.check_equal(atoms[0].atom_type, 'ftyp')
        moov = None
        for atom in atoms:
            if atom.atom_type == 'moov':
                moov = atom
                break
        msg='Failed to find MOOV box in this init segment'
        if not self.elt.check_not_none(moov, msg=msg):
            self.logging.error(msg)
            return None
        if not self.info.encrypted:
            return moov
        try:
            self.validate_pssh(moov.pssh)
        except (AttributeError) as ae:
            # A PSSH box is optional, as the DRM information might be in
            # the manifest
            if 'moov' in self.url and ('playready' in self.url or 'clearkey' in self.url):
                self.elt.check_true(
                    'moov' not in self.url, None, None,
                    f'PSSH box should be present in {self.url}\n{ae}')
        return moov

    def validate_pssh(self, pssh) -> None:
        self.elt.check_equal(len(pssh.system_id), 16)
        if pssh.system_id != PlayReady.RAW_SYSTEM_ID:
            return
        for pro in PlayReady.parse_pro(
                BufferedReader(None, data=pssh.data.data)):
            root = pro['xml'].getroot()
            version = root.get("version")
            self.elt.check_includes(
                ["4.0.0.0", "4.1.0.0", "4.2.0.0", "4.3.0.0"], version)
            if 'playready_version' not in self.mpd.params:
                continue
            version = float(self.mpd.params['playready_version'])
            if version < 2.0:
                self.elt.check_equal(root.attrib['version'], "4.0.0.0")
            elif version < 3.0:
                self.elt.check_includes(
                    {"4.0.0.0", "4.1.0.0"}, root.attrib['version'])
            elif version < 4.0:
                self.elt.check_includes(
                    {"4.0.0.0", "4.1.0.0", "4.2.0.0"}, root.attrib['version'])
