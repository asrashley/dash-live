#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from dataclasses import dataclass
import logging
from pathlib import Path
import shutil

from flask_login import current_user

from dashlive.drm.playready import PlayReady
from dashlive.mpeg import mp4
from dashlive.mpeg.dash.representation import Representation
from dashlive.server.models.db import db
from dashlive.server.models.key import Key, KeyMaterial
from dashlive.server.models.mediafile import MediaFile
from dashlive.server.models.stream import Stream

from .db_access import DatabaseAccess
from .info import KeyInfo, StreamInfo

@dataclass
class MockFileUpload:
    abs_name: str
    mimetype: str

    @property
    def filename(self) -> str:
        return self.abs_name.name

    def save(self, dest_filename: str) -> None:
        shutil.move(str(self.abs_name), dest_filename)


class BackendDatabaseAccess(DatabaseAccess):
    """
    Access to database using flask back-end APIs
    """
    def __init__(self) -> None:
        self.log = logging.getLogger('management')

    def login(self) -> bool:
        return current_user.is_authenticated

    def get_media_info(self, with_details: bool = False) -> bool:
        if not self.login():
            return False
        self.keys = Key.all()
        self.streams = Stream.all()
        return True

    def fetch_media_info(self, with_details: bool = False) -> bool:
        return current_user.is_authenticated

    def get_streams(self) -> list[StreamInfo]:
        return list(Stream.all())

    def get_stream_info(self, directory: str) -> Stream | None:
        return Stream.get(directory=directory)

    def add_stream(self,
                   directory: str,
                   title: str,
                   marlin_la_url: str = '',
                   playready_la_url: str = '',
                   **kwargs) -> Stream | None:
        self.log.info('Adding stream "%s" (%s)', title, directory)
        stream = Stream(
            title=title, directory=directory, marlin_la_url=marlin_la_url,
            playready_la_url=playready_la_url)
        stream.add(commit=True)
        return stream

    def get_keys(self) -> dict[str, KeyInfo]:
        rv: dict[str, KeyInfo] = {}
        for k in Key.all():
            rv[k.hkid] = k
        return rv

    def add_key(self, kid: str, computed: bool,
                key: str | None = None, alg: str | None = None) -> bool:
        if key is None:
            computed = True
        k = Key(hkid=kid, computed=computed, hkey=key, halg=alg)
        if computed:
            kid_km = KeyMaterial(kid)
            k.hkey = KeyMaterial(raw=PlayReady.generate_content_key(kid_km.raw)).hex
        k.add(commit=True)
        return True

    def upload_file(self, stream: StreamInfo, filename: Path) -> bool:
        name = Path(filename)
        mf: MediaFile | None = MediaFile.get(stream=stream, name=name.stem)
        if mf is not None:
            self.log.debug('File %s (%s) already part of stream %s',
                           filename, name.stem, stream.directory)
            return True
        if not name.exists():
            self.log.warning("%s not found", name)
            return False
        self.log.debug('Installing file %s', name)
        file_upload = MockFileUpload(name, 'application/mp4')
        mf = stream.add_file(file_upload, commit=True)
        if not mf:
            self.log.warning('Failed to add file %s', name)
            return False
        return True

    def index_file(self, stream: StreamInfo, name: Path) -> bool:
        name = Path(name)
        mf: MediaFile | None = MediaFile.get(stream=stream, name=name.stem)
        if not mf:
            self.log.error('Failed to find MediaFile %s', name.stem)
            return False
        self.log.info('Indexing file %s', mf.name)
        with mf.open_file() as src:
            atom = mp4.Wrapper(
                atom_type='wrap', position=0, size=mf.blob.size,
                parent=None, children=mp4.Mp4Atom.load(src))
        rep = Representation.load(filename=mf.name, atoms=atom.children)
        mf.representation = rep
        mf.encryption_keys = []
        for kid in rep.kids:
            key_model = Key.get(hkid=kid.hex)
            if key_model is None:
                key = KeyMaterial(
                    raw=PlayReady.generate_content_key(kid.raw))
                key_model = Key(hkid=kid.hex, hkey=key.hex, computed=True)
                key_model.add()
            mf.encryption_keys.append(key_model)
        mf.content_type = rep.content_type
        mf.bitrate = rep.bitrate
        mf.encrypted = rep.encrypted
        if not rep.bitrate:
            self.log.warning('Failed to calculate bitrate of file %s', mf.name)
            return False
        # bitrate cannot be None, therefore don't commit if
        # Representation class failed to discover the
        # bitrate
        db.session.commit()
        self.log.info('Indexing file %s complete', mf.name)
        return True

    def set_timing_ref(self, stream: StreamInfo, timing_ref: str) -> bool:
        mf = MediaFile.get(name=Path(timing_ref).stem)
        if not mf:
            return False
        stream.set_timing_reference(mf.as_stream_timing_reference())
        db.session.commit()
        return True
