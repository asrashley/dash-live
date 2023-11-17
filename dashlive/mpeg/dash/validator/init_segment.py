#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from pathlib import Path
import urllib.parse

from dashlive.drm.playready import PlayReady
from dashlive.mpeg import mp4
from dashlive.mpeg.dash.representation import Representation as DashRepresentation
from dashlive.utils.buffered_reader import BufferedReader

from .dash_element import DashElement

class InitSegment(DashElement):
    def __init__(self, parent, url: str | None, seg_range: str | None) -> None:
        super().__init__(None, parent)
        self.seg_range = seg_range
        self.url = url
        self.atoms: list[mp4.Mp4Atom] | None = None
        path = Path(urllib.parse.urlparse(url).path)
        self.name = path.name
        self.codecs: str | None = None
        if seg_range:
            self.name += f'?range={self.seg_range}'

    def children(self) -> list[DashElement]:
        return []

    async def get_moov(self) -> mp4.Mp4Atom | None:
        if self.atoms is None:
            if not await self.load():
                return None
        for atom in self.atoms:
            if atom.atom_type == 'moov':
                return atom
        return None

    async def load(self) -> bool:
        if not self.elt.check_not_none(self.url, msg='URL of init segment is missing'):
            return False
        if self.seg_range is not None:
            headers = {"Range": f"bytes={self.seg_range}"}
            expected_status = 206
        else:
            headers = None
            expected_status = 200
        self.log.debug('GET: %s %s', self.url, headers)
        response = await self.http.get(self.url, headers=headers)
        if not self.elt.check_equal(
                response.status_code, expected_status,
                msg=f'Failed to load init segment: {response.status_code}: {self.url}'):
            return False
        async with self.pool.group() as tg:
            body = response.get_data(as_text=False)
            if self.options.save:
                tg.submit(self.save, body)
            parse_task = tg.submit(self.parse_body, body)
        exc = parse_task.exception()
        if exc:
            self.elt.add_error(f'Failed to load init segment: {exc}')
            self.log.error('Failed to load init segment: %s', exc)
            return False
        return True

    def parse_body(self, body: bytes) -> None:
        src = BufferedReader(None, data=body)
        self.atoms = mp4.Mp4Atom.load(src)

    def save(self, body: bytes) -> None:
        adp = self.parent.parent
        if self.parent.id:
            default = f'init-{adp.id}-{self.parent.id}'
        else:
            default = f'init-{adp.id}-{self.parent.bandwidth}'
        filename = self.output_filename(
            default=default, bandwidth=self.parent.bandwidth,
            prefix=self.options.prefix, elt_id=self.parent.id,
            makedirs=True)
        self.log.debug('saving init segment: %s', filename)
        with self.open_file(filename, self.options) as dest:
            dest.write(body)

    async def validate(self, depth: int = -1) -> None:
        if not self.elt.check_not_none(self.url, msg='URL of init segment is missing'):
            return
        if self.atoms is None:
            if not await self.load():
                self.elt.add_error('Failed to load init segment')
                return
        if not self.elt.check_greater_than(
                len(self.atoms), 1, msg='Expected more than one MP4 atom in init segment'):
            return
        self.elt.check_equal(self.atoms[0].atom_type, 'ftyp')
        moov = None
        for atom in self.atoms:
            if atom.atom_type == 'moov':
                moov = atom
                break
        msg = 'Failed to find MOOV box in this init segment'
        if not self.elt.check_not_none(moov, msg=msg):
            self.logging.error(msg)
            return None
        self.validate_moov(moov)
        pssh = moov.find_child('pssh')
        if pssh is not None:
            self.elt.check_true(
                self.options.encrypted,
                msg='PSSH should not be present in an unencrypted stream')
            self.validate_pssh(pssh)
        else:
            if self.parent.parent.contentType != 'video':
                return
            # A PSSH box is optional, as the DRM information might be in
            # the manifest
            if 'moov' in self.url and ('playready' in self.url or 'clearkey' in self.url):
                self.elt.check_true(
                    'moov' not in self.url, None, None,
                    'PSSH box should be present in an encrypted stream')

    def validate_moov(self, moov: mp4.Mp4Atom) -> None:
        dash_rep = DashRepresentation()
        key_ids = set()
        dash_rep.process_moov(moov, key_ids)
        self.codecs = dash_rep.codecs
        timescale = self.parent.timescale()
        self.elt.check_equal(
            dash_rep.timescale, self.parent.timescale(),
            msg=f'Expected timescale to be {timescale} but found {dash_rep.timescale}')
        if self.parent.codecs:
            self.elt.check_equal(
                dash_rep.codecs.lower(), self.parent.codecs.lower(),
                msg=f'Expected codec to be {self.parent.codecs} but found {dash_rep.codecs}')
        if self.parent.parent.contentType == 'video':
            self.elt.check_less_than_or_equal(
                self.parent.height, dash_rep.height,
                msg=f'Expected height to be {self.parent.height} but found {dash_rep.height}')
            self.elt.check_less_than_or_equal(
                self.parent.width, dash_rep.width,
                msg=f'Expected width to be {self.parent.width} but found {dash_rep.width}')
            framerate = self.parent.frameRate
            if framerate is None:
                framerate = self.parent.parent.frameRate
            if framerate is not None and 'frameRate' in dash_rep._fields:
                msg = f'Expected frame rate {framerate.value} but found {dash_rep.frameRate}'
                self.elt.check_almost_equal(
                    framerate.value, dash_rep.frameRate,
                    msg=msg, clause='5.3.12.2')
        elif self.parent.parent.contentType == 'audio':
            audioSamplingRate = self.parent.audioSamplingRate
            if audioSamplingRate is None:
                audioSamplingRate = self.parent.parent.audioSamplingRate
            if audioSamplingRate is not None:
                msg = (f'Expected audio sampling rate to be {audioSamplingRate} ' +
                       f'but found {dash_rep.sampleRate}')
                self.elt.check_equal(audioSamplingRate, dash_rep.sampleRate, msg=msg)

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
