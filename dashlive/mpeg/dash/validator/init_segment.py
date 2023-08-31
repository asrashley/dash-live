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

    def validate(self, depth: int = -1) -> None:
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
