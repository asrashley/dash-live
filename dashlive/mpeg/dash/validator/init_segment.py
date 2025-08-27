#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import io
from pathlib import Path
import traceback
from typing import cast
import urllib.parse
from xml.etree import ElementTree

from dashlive.drm.keymaterial import KeyMaterial
from dashlive.drm.playready import PlayReady
from dashlive.mpeg import mp4
from dashlive.mpeg.dash.representation import Representation as DashRepresentation
from dashlive.mpeg.dash.validator.http_client import HttpResponse

from .dash_element import DashElement

class InitSegment(DashElement):
    atoms: list[mp4.Mp4Atom] | None
    dash_rep: DashRepresentation | None
    name: str
    seg_range: str | None
    url: str | None

    def __init__(self, parent, url: str | None, seg_range: str | None) -> None:
        super().__init__(None, parent)
        self.atoms = None
        self.dash_rep = None
        self.seg_range = seg_range
        self.url = url
        if url is not None:
            self.set_url(url)
        else:
            self.name = f'InitSegment({id(self)})'

    def set_url(self, url: str) -> None:
        self.url = url
        path = Path(urllib.parse.urlparse(url).path)
        self.name = path.name
        if self.seg_range:
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

    def media_timescale(self) -> int | None:
        if self.dash_rep:
            return self.dash_rep.timescale
        return None

    def set_dash_representation(self, info: DashRepresentation) -> None:
        self.dash_rep = info

    def get_dash_representation(self) -> DashRepresentation | None:
        return self.dash_rep

    dash_representation = property(get_dash_representation, set_dash_representation)

    @property
    def codecs(self) -> str | None:
        if self.dash_rep is None:
            return None
        return self.dash_rep.codecs

    async def load(self) -> bool:
        if self.atoms is not None and self.dash_rep is not None:
            return True
        if self.progress.aborted():
            return False
        if not self.elt.check_not_none(self.url, msg='URL of init segment is missing'):
            return False
        headers: dict[str, str] | None = None
        expected_status: int = 200
        if self.seg_range is not None:
            headers = {"Range": f"bytes={self.seg_range}"}
            expected_status = 206
        self.log.debug('GET: %s %s', self.url, headers)
        response: HttpResponse = await self.http.get(cast(str, self.url), headers=headers)
        if not self.elt.check_equal(
                response.status_code, expected_status,
                msg=f'Failed to fetch init segment: status={response.status_code}: {self.url}'):
            return False
        if self.progress.aborted():
            return False
        try:
            async with self.pool.group(self.progress) as tg:
                body: bytes = response.get_data(as_text=False)
                if self.options.save:
                    tg.submit(self.save, body)
                task = tg.submit(self.parse_body, body)
            if not task.result():
                return False
        except Exception as exc:
            traceback.print_exception(exc)
            self.elt.add_error(f'Exception whilst loading init segment: {exc}')
            self.log.error('Exception whilst loading init segment: %s', exc)
            return False
        return True

    def parse_body(self, body: bytes) -> bool:
        src = io.BufferedReader(io.BytesIO(body))
        atoms: list[mp4.Mp4Atom] = cast(
            list[mp4.Mp4Atom], mp4.Mp4Atom.load(src, options={'lazy_load': False}))
        moov: mp4.Mp4Atom | None = None
        for atm in atoms:
            if atm.atom_type == 'moov':
                moov = atm
        if moov is None:
            boxes: list[str] = [a.atom_type for a in atoms]
            self.elt.add_error(f'Failed to find moov box in {self.url} found {boxes}')
            return False
        key_ids: set[KeyMaterial] = set()
        self.dash_rep = DashRepresentation()
        self.dash_rep.process_moov(moov, key_ids)
        self.dash_rep.segments = None  # type: ignore
        self.dash_rep.start_time = -1
        self.atoms = atoms
        return True

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
                len(self.atoms), 1,
                msg='Expected more than one MP4 atom in init segment'):
            return
        self.elt.check_equal(self.atoms[0].atom_type, 'ftyp')
        moov: mp4.Mp4Atom | None = None
        for atom in self.atoms:
            if atom.atom_type == 'moov':
                moov = atom
                break
        msg = 'Failed to find MOOV box in this init segment'
        if not self.elt.check_not_none(moov, msg=msg):
            self.logging.error(msg)
            return None
        self.validate_moov(moov)
        pssh: mp4.Mp4Atom | None = moov.find_child('pssh')
        if pssh is not None:
            self.elt.check_true(
                self.options.encrypted,
                msg='PSSH should not be present in an unencrypted stream')
            self.validate_pssh(cast(mp4.ContentProtectionSpecificBox, pssh))
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
        dash_rep = self.dash_rep
        dash_timescale = self.parent.dash_timescale()
        media_timescale: int | None = self.media_timescale()
        if media_timescale == 0 or dash_timescale == 0:
            self.elt.add_error(
                f'Neither DASH timescale {dash_timescale} nor media timescale ' +
                f'{media_timescale} can be zero')
        elif media_timescale is not None and media_timescale != dash_timescale:
            ratio = max(dash_timescale, media_timescale) / float(
                min(dash_timescale, media_timescale))
            self.elt.check_equal(
                int(ratio), ratio,
                msg=(
                    f'DASH timescale {dash_timescale} and media timescale ' +
                    f'{media_timescale} are not multiples of each other'))

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

    def validate_pssh(self, pssh: mp4.ContentProtectionSpecificBox) -> None:
        self.elt.check_equal(len(pssh.system_id), 16)
        if pssh.system_id != PlayReady.RAW_SYSTEM_ID:
            return
        for pro in PlayReady.parse_pro(io.BytesIO(pssh.data.data)):
            if not self.elt.check_not_none(
                    pro.xml, msg='Failed to parse PlayReady header XML'):
                continue
            root: ElementTree.Element = cast(ElementTree.Element, pro.xml)
            version: str | None = root.get("version")
            self.elt.check_includes(
                {"4.0.0.0", "4.1.0.0", "4.2.0.0", "4.3.0.0"}, version)
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
