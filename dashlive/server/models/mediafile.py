#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import contextlib
import datetime
import hashlib
import logging
from pathlib import Path
from typing import cast, Callable, Optional

import flask
import sqlalchemy as sa
from sqlalchemy.event import listen  # type: ignore
from sqlalchemy.orm import Mapped, reconstructor, relationship  # type: ignore
import sqlalchemy_jsonfield  # type: ignore

from dashlive.mpeg.dash.representation import Representation
from dashlive.mpeg.dash.reference import StreamTimingReference
from dashlive.mpeg import mp4
from dashlive.utils.buffered_reader import BufferedReader
from dashlive.utils.date_time import to_iso_datetime
from dashlive.utils.json_object import JsonObject
from dashlive.utils.timezone import UTC

from .db import db
from .key import Key
from .mixin import ModelMixin
from .mediafile_keys import mediafile_keys
from .mediafile_error import MediaFileError
from .session import DatabaseSession

class MediaFile(db.Model, ModelMixin):
    """representation of one MP4 file"""
    __plural__ = 'MediaFiles'

    pk: Mapped[int] = db.Column('pk', sa.Integer, primary_key=True)
    name = sa.Column('name', sa.String(200), nullable=False, unique=True, index=True)
    stream_pk = sa.Column(
        'stream', sa.Integer, sa.ForeignKey('Stream.pk'),
        nullable=False)
    stream = relationship('Stream', back_populates='media_files')
    blob_pk = sa.Column('blob', sa.Integer, sa.ForeignKey('Blob.pk'),
                        nullable=False, unique=True)
    blob = relationship('Blob', back_populates='mediafile',
                        cascade='all, delete')
    rep = sa.Column(
        'rep',
        sqlalchemy_jsonfield.JSONField(
            enforce_string=True,
            enforce_unicode=False
        ),
        nullable=True)
    bitrate = sa.Column(sa.Integer, default=0, index=True, nullable=False)

    # 'video', 'audio' or 'text'
    content_type = sa.Column(sa.String(64), nullable=True, index=True)

    track_id = sa.Column(sa.Integer, index=True, nullable=True)

    # the fourcc of the audio/video/text codec
    # 'avc1', 'avc3', 'hev1', 'mp4a', 'ec3', 'ac_3', 'stpp'
    codec_fourcc = sa.Column(sa.String(16), nullable=True, index=False)

    encrypted = sa.Column(sa.Boolean, default=False, index=True, nullable=False)

    encryption_keys: Mapped[list[Key]] = relationship(secondary=mediafile_keys, back_populates='mediafiles')

    errors: Mapped[list["MediaFileError"]] = relationship(
        'MediaFileError', cascade="all, delete")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._post_init()

    @reconstructor
    def _reconstructor(self) -> None:
        self._post_init()

    def _post_init(self) -> None:
        self._representation: Representation | None = None
        if self.rep is not None:
            self._representation = Representation(**self.rep)

    def _pre_put_hook(self) -> None:
        if self._representation is None:
            return
        if self.content_type is None:
            self.content_type = self._representation.content_type
            self.encrypted = self._representation.encrypted
            self.bitrate = self._representation.bitrate
        if self.codec_fourcc is None:
            self.codec_fourcc = self._representation.codecs.split('.')[0]
        if self.track_id is None:
            self.track_id = self._representation.track_id

    def get_representation(self):
        if self._representation is None and self.rep:
            self._representation = Representation(**self.rep)
            try:
                if self._representation.version < Representation.VERSION:
                    self._representation = None
            except AttributeError:
                self._representation = None
        return self._representation

    def set_representation(self, rep):
        self.rep = rep.toJSON(pure=True)
        self._representation = rep

    representation = property(get_representation, set_representation)

    @classmethod
    def all(clz, order_by: list[sa.Column] | None = None) -> list["MediaFile"]:
        return cast(list["MediaFile"], clz.get_all(order_by=order_by))

    @classmethod
    def search(clz,
               max_items: int | None = None,
               order_by: list[sa.Column] | None = None,
               stream: Optional["Stream"] = None,  # noqa: F821
               **kwargs) -> list["MediaFile"]:
        if stream is not None:
            kwargs['stream_pk'] = stream.pk
        if order_by is None:
            order_by = [MediaFile.bitrate]
        return super().search(max_items=max_items, order_by=order_by, **kwargs)

    @classmethod
    def get(clz, **kwargs) -> Optional["MediaFile"]:
        """
        Get one entry by name from the database
        """
        return cast(Optional[MediaFile], clz.get_one(**kwargs))

    def toJSON(self, convert_date: bool = True, pure: bool = False) -> JsonObject:
        blob = self.blob.to_dict(exclude={'rep', 'blob', 'stream_pk', 'encryption_keys'})
        if blob["created"] and (convert_date or pure):
            blob["created"] = to_iso_datetime(blob["created"])
        retval = self.to_dict()
        retval['blob'] = blob
        retval['encryption_keys'] = [
            ky.to_dict(exclude={'mediafiles'}) for ky in self.encryption_keys]
        retval['representation'] = self.representation
        if retval['representation'] is not None:
            retval['representation'] = retval['representation'].toJSON(pure=pure)
        return retval

    @classmethod
    def absolute_path(cls, stream_dir: Path) -> Path:
        app = flask.current_app
        return Path(app.config['BLOB_FOLDER']) / stream_dir

    def open_file(self, start: int | None = None,
                  buffer_size: int = 4096) -> contextlib.AbstractContextManager:
        abs_path = self.absolute_path(self.stream.directory)
        return self.blob.open_file(abs_path, start=start, buffer_size=buffer_size)

    def delete_file(self) -> None:
        abs_path = self.absolute_path(self.stream.directory)
        self.blob.delete_file(abs_path)

    def as_stream_timing_reference(self) -> StreamTimingReference | None:
        if self.representation is None:
            return None
        return StreamTimingReference(
            media_name=self.name,
            media_duration=self.representation.mediaDuration,
            segment_duration=self.representation.segment_duration,
            num_media_segments=self.representation.num_media_segments,
            timescale=self.representation.timescale)

    def parse_media_file(self, blob_folder: Path | None = None) -> bool:
        from dashlive.drm.keymaterial import KeyMaterial
        from dashlive.drm.playready import PlayReady

        if blob_folder is None:
            abs_path = self.absolute_path(self.stream.directory)
        else:
            abs_path = blob_folder / self.stream.directory
        if not abs_path.exists():
            return False
        with self.blob.open_file(abs_path, start=0, buffer_size=16384) as src:
            atom = mp4.Wrapper(
                atom_type='wrap', position=0, size=self.blob.size,
                parent=None, children=mp4.Mp4Atom.load(src))
        rep = Representation.load(filename=self.name, atoms=atom.children)
        if rep.bitrate is None:
            return False
        self.representation = rep
        self.rep = rep.toJSON(pure=True)
        self.content_type = rep.content_type
        self.bitrate = rep.bitrate
        self.encrypted = rep.encrypted
        self.encryption_keys = []
        for kid in rep.kids:
            key_model = Key.get(hkid=kid.hex, session=session)
            if key_model is None:
                key = KeyMaterial(
                    raw=PlayReady.generate_content_key(kid.raw))
                key_model = Key(hkid=kid.hex, hkey=key.hex, computed=True)
                session.add(key_model)
            self.encryption_keys.append(key_model)
        return True

    def modify_media_file(self,
                          new_filename: Path,
                          modify_atoms: Callable[[mp4.Wrapper], bool],
                          session: DatabaseSession | None = None,
                          blob_folder: Path | None = None
                          ) -> bool:
        from .blob import Blob

        if blob_folder is None:
            abs_path = self.absolute_path(self.stream.directory)
        else:
            abs_path = blob_folder / self.stream.directory
        abs_name = abs_path / self.blob.filename
        if not abs_name.exists():
            logging.error('Blob file %s does not exist', abs_name)
            return False
        if new_filename.exists():
            logging.error('New mp4 file "%s" already exists', new_filename)
            return False
        if session is None:
            session = db.session
        if self.rep is None:
            if not self.parse_media_file(
                    blob_folder=blob_folder, session=session):
                raise IOError(f'Failed to parse {abs_name}')
        assert self.representation is not None
        mp4_options = mp4.Options(mode='rw', lazy_load=True)
        if self.representation.encrypted:
            mp4_options.iv_size = self.representation.iv_size

        logging.info('Creating MP4 file "%s"', new_filename)
        with new_filename.open('wb') as dest:
            for frag in self.representation.segments:
                with abs_name.open('rb') as src:
                    src.seek(frag.pos)
                    reader = BufferedReader(
                        src, offset=frag.pos, size=frag.size, buffersize=16384)
                    atom = mp4.Mp4Atom.load(
                        reader, options=mp4_options, use_wrapper=True)
                    changed = modify_atoms(atom)
                    if changed:
                        dest.write(atom.encode())
                    else:
                        src.seek(frag.pos)
                        dest.write(src.read(frag.size))

        stats = new_filename.stat()
        blob = Blob(filename=new_filename.name, size=stats.st_size,
                    content_type=self.blob.content_type,
                    auto_delete=self.blob.auto_delete)
        with new_filename.open('rb') as src:
            digest = hashlib.file_digest(src, 'sha1')
            blob.sha1_hash = digest.hexdigest()

        session.add(blob)
        self.blob = blob
        logging.info('Parsing new MP4 file "%s"', new_filename)
        self.parse_media_file(blob_folder=blob_folder, session=session)
        logging.info('Finished creating MP4 file "%s"', new_filename)
        return True

    @classmethod
    def ensure_track_ids_are_unique(cls,
                                    session: DatabaseSession,
                                    blob_folder: Path) -> None:
        content_types = ['video', 'audio', 'text']
        next_track_ids: dict[int, int] = {}
        for media in session.query(cls):
            if media.rep is None:
                if not media.parse_media_file(blob_folder):
                    continue
            media._pre_put_hook()
            if media.content_type not in content_types:
                content_types.append(media.content_type)
            try:
                next_track_ids[media.stream_pk] = max(
                    next_track_ids[media.stream_pk],
                    media.representation.track_id + 1)
            except KeyError:
                next_track_ids[media.stream_pk] = media.representation.track_id + 1

        track_id_map: dict[tuple[int, str, str], int] = {}
        track_content: dict[tuple[int, int], tuple[str, str]] = {}
        mp4_fixups: list[tuple[int, int]] = []
        for c_type in content_types:
            for media in session.query(cls).filter_by(content_type=c_type):
                if media.rep is None:
                    continue
                logging.info(
                    'Populating track ID for stream %d file %d', media.stream_pk,
                    media.pk)
                new_id = media._populate_track_id(
                    track_id_map, track_content, next_track_ids)
                if new_id is not None:
                    mp4_fixups.append((media.pk, new_id))

        for pk, track_id in mp4_fixups:
            media = session.execute(
                db.select(cls).filter_by(pk=pk)).scalar_one_or_none()
            if media is None:
                raise RuntimeError(f'Failed to get MediaFile {pk}')
            abs_path = blob_folder / media.stream.directory
            filename = Path(media.blob.filename)
            new_name = abs_path / f'{filename.stem}_{track_id:02d}{filename.suffix}'
            index = 1
            while new_name.exists():
                new_name = abs_path / f'{filename.stem}_{track_id:02d}_{index:02d}{filename.suffix}'
                index += 1
            logging.warning('Creating new MP4 file %s from %s with track ID %d',
                            new_name, abs_path / filename, track_id)
            if not media.modify_media_file(
                    session=session, blob_folder=blob_folder, new_filename=new_name,
                    modify_atoms=lambda atom: MediaFile._set_track_id(atom, track_id)):
                raise IOError(f'Failed to update track ID for {filename}')

    def _populate_track_id(self,
                           track_id_map: dict,
                           track_content: dict,
                           next_track_ids: dict[int, int]) -> int | None:
        assert self._representation is not None
        assert self.codec_fourcc is not None
        track_id_key = (self.stream_pk, self.content_type, self.codec_fourcc)
        try:
            self.track_id = track_id_map[track_id_key]
        except KeyError:
            self.track_id = self.representation.track_id
        logging.info(
            'stream %d file %d: track=%d codec=%s', self.stream_pk, self.pk,
            self.track_id, self.codec_fourcc)
        track_key = (self.stream_pk, self.track_id)
        content_key = (self.content_type, self.codec_fourcc)
        if track_content.get(track_key, content_key) != content_key:
            logging.warning(
                'Duplicate track ID for stream %d file %d',
                self.stream_pk, self.pk)
            logging.warning(
                'track ID %d already exists of type %s, but this track is of type %s',
                self.track_id, track_content[track_key], content_key)
            self.track_id = next_track_ids[self.stream_pk]
            next_track_ids[self.stream_pk] += 1
            track_key = (self.stream_pk, self.track_id)
            logging.warning(
                'Using track ID %d for %s', self.track_id, content_key)
        track_content[track_key] = content_key
        track_id_map[track_id_key] = self.track_id
        if self.track_id != self.representation.track_id:
            logging.warning(
                'File %s needs to have its track ID updated from %d to %d',
                self.blob.filename, self.representation.track_id,
                self.track_id)
            return self.track_id
        return None

    @staticmethod
    def _set_track_id(wrap: mp4.Wrapper, new_track_id: int) -> bool:
        try:
            moov = wrap.moov
            moov.trak.tkhd.track_id = new_track_id
            moov.mvex.trex.track_id = new_track_id
            moov.mvhd.next_track_id = new_track_id + 1
            moov.trak.tkhd.modification_time = datetime.datetime.now(tz=UTC())
            return True
        except AttributeError:
            pass
        try:
            moof = wrap.moof
            moof.traf.tfhd.track_id = new_track_id
            return True
        except AttributeError:
            pass
        return False

# pylint: disable=unused-argument
def before_mediafile_save(mapper, connect, mediafile):
    mediafile._pre_put_hook()


listen(MediaFile, 'before_insert', before_mediafile_save)
