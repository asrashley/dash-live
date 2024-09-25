#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import contextlib
import hashlib
import logging
from pathlib import Path
from typing import cast, Callable, Optional

import flask
from langcodes import tag_is_valid
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
from dashlive.utils.lang import UNDEFINED_LANGS
from dashlive.utils.string import str_or_none

from .db import db
from .error_reason import ErrorReason
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

    def get_fields(self, **kwargs) -> list[JsonObject]:
        errors: dict[ErrorReason, str] = {}
        for err in self.errors:
            errors[err.reason] = err.details
        lang: str | None = None
        if self.representation:
            lang = self.representation.lang
        return [{
            "name": "track_id",
            "title": "Track ID",
            "type": "number",
            "min": 1,
            "max": 0xFFFFFFFF,
            "value": kwargs.get("track_id", self.track_id),
            "error": errors.get(ErrorReason.DUPLICATE_TRACK_IDS, None),
        }, {
            "name": "lang",
            "title": "Language",
            "type": "text",
            "maxlength": 100,
            "value": str_or_none(kwargs.get("lang", lang)),
            "error": errors.get(ErrorReason.INVALID_LANGUAGE_TAG, None),
        }]

    def parse_media_file(self,
                         blob_folder: Path | None = None,
                         session: DatabaseSession | None = None) -> bool:
        from dashlive.drm.keymaterial import KeyMaterial
        from dashlive.drm.playready import PlayReady

        if session is None:
            session = db.session

        for err in self.errors:
            session.delete(err)

        if blob_folder is None:
            abs_path = self.absolute_path(self.stream.directory)
        else:
            abs_path = blob_folder / self.stream.directory
        src_name = abs_path / self.blob.filename
        if not src_name.exists():
            err = MediaFileError(
                media_file=self,
                reason=ErrorReason.FILE_NOT_FOUND,
                details=f'No such file or directory: {src_name}')
            session.add(err)
            return False
        with self.blob.open_file(abs_path, start=0, buffer_size=16384) as src:
            atom = mp4.Wrapper(
                atom_type='wrap', position=0, size=self.blob.size,
                parent=None, children=mp4.Mp4Atom.load(src))
        rep = Representation.load(filename=self.name, atoms=atom.children)
        if not rep.segments:
            err = MediaFileError(
                media_file=self,
                reason=ErrorReason.NO_FRAGMENTS,
                details='Not a fragmented MP4 file')
            session.add(err)
            return False
        if len(rep.segments) < 3:
            err = MediaFileError(
                media_file=self,
                reason=ErrorReason.NOT_ENOUGH_FRAGMENTS,
                details='At least 2 media segments are required')
            session.add(err)
            return False
        if rep.bitrate is None:
            err = MediaFileError(
                media_file=self,
                reason=ErrorReason.FAILED_TO_DETECT_BITRATE,
                details='Insufficient data to calculate bitrate')
            session.add(err)
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
        if rep.lang not in UNDEFINED_LANGS and not tag_is_valid(rep.lang):
            err = MediaFileError(
                media_file=self,
                reason=ErrorReason.INVALID_LANGUAGE_TAG,
                details=f'Invalid language tag "{rep.lang}"')
            session.add(err)
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
        try:
            with new_filename.open('wb') as dest:
                with abs_name.open('rb') as src:
                    for frag in self.representation.segments:
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
        except Exception as err:
            new_filename.unlink(missing_ok=True)
            logging.error(
                'Failed to create new MP4 file "%s": %s', new_filename, err)
            return False

        stats = new_filename.stat()
        old_blob = self.blob
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
        if old_blob.auto_delete:
            session.delete(old_blob)
        return True


# pylint: disable=unused-argument
def before_mediafile_save(mapper, connect, mediafile):
    mediafile._pre_put_hook()


listen(MediaFile, 'before_insert', before_mediafile_save)
