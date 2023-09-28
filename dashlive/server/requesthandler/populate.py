#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from dataclasses import dataclass
from pathlib import Path
import shutil

from flask_login import current_user

from dashlive.drm.playready import PlayReady
from dashlive.management.populate import PopulateDatabase
from dashlive.mpeg import mp4
from dashlive.mpeg.dash.representation import Representation
from dashlive.server import models

@dataclass
class MockFileUpload:
    abs_name: str
    mimetype: str

    @property
    def filename(self) -> str:
        return self.abs_name.name

    def save(self, dest_filename: str) -> None:
        shutil.move(str(self.abs_name), dest_filename)


class BackendPopulateDatabase(PopulateDatabase):
    """
    Populates the database within a Flask request handler using files
    that are already on the server.
    """
    def __init__(self) -> None:
        super().__init__(url='', username='', password='')

    def login(self) -> bool:
        current_user.is_authenticated

    def get_media_info(self, with_details: bool = False) -> bool:
        if not self.login():
            return False
        self.keys = models.Key.all()
        self.streams = models.Stream.all()
        return True

    def get_stream_info(self, directory: str) -> models.Stream | None:
        return models.Stream.get(directory=directory)

    def add_stream(self,
                   directory: str,
                   title: str,
                   marlin_la_url: str = '',
                   playready_la_url: str = '',
                   **kwargs) -> models.Stream | None:
        self.log.info('Adding stream "%s" (%s)', title, directory)
        stream = models.Stream(
            title=title, directory=directory, marlin_la_url=marlin_la_url,
            playready_la_url=playready_la_url)
        stream.add(commit=True)
        return stream

    def add_key(self, kid: str, computed: bool,
                key: str | None = None, alg: str | None = None) -> bool:
        k = models.Key(hkid=kid, computed=computed, hkey=key, halg=alg)
        k.add(commit=True)
        return True

    def upload_file_and_index(self, js_dir: Path, stream: models.Stream, name: str) -> bool:
        name = Path(name)
        if name.stem in stream.media_files:
            return True
        filename = name
        if not filename.exists():
            self.log.debug(
                "%s not found, trying directory %s", filename, js_dir)
            filename = js_dir / filename.name
        if not filename.exists():
            self.log.warning("%s not found", name)
            return False
        self.log.debug('Installing file %s', filename)
        file_upload = MockFileUpload(filename, 'application/mp4')
        mf = stream.add_file(file_upload, commit=True)
        if not mf:
            self.log.warning('Failed to add file %s', filename)
            return False
        return self.index_file(mf)

    def index_file(self, mf: models.MediaFile) -> bool:
        self.log.info('Indexing file %s', mf.name)
        with mf.open_file() as src:
            atom = mp4.Wrapper(
                atom_type='wrap', position=0, size=mf.blob.size,
                parent=None, children=mp4.Mp4Atom.load(src))
        rep = Representation.load(filename=mf.name, atoms=atom.children)
        mf.representation = rep
        mf.encryption_keys = []
        for kid in rep.kids:
            key_model = models.Key.get(hkid=kid.hex)
            if key_model is None:
                key = models.KeyMaterial(
                    raw=PlayReady.generate_content_key(kid.raw))
                key_model = models.Key(hkid=kid.hex, hkey=key.hex, computed=True)
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
        models.db.session.commit()
        self.log.info('Indexing file %s complete', mf.name)
        return True
