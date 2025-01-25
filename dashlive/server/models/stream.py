#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import datetime
import hashlib
import logging
from pathlib import Path
from typing import cast, AbstractSet, ClassVar, Optional, NamedTuple

import flask
import sqlalchemy as sa
from sqlalchemy.orm import relationship, Mapped, mapped_column
import sqlalchemy_jsonfield  # type: ignore
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from dashlive.utils.json_object import JsonObject
from dashlive.utils.string import str_or_none
from dashlive.mpeg.dash.reference import StreamTimingReference

from .base import Base
from .blob import Blob
from .db import db
from .mediafile import MediaFile
from .mixin import ModelMixin

class TrackSummary(NamedTuple):
    content_type: str
    count: int

class StreamTrackSummary(NamedTuple):
    video: TrackSummary
    audio: TrackSummary
    text: TrackSummary


class Stream(ModelMixin["Stream"], Base):
    """
    Model for each media stream
    """
    __plural__: ClassVar[str] = 'Streams'
    __tablename__: ClassVar[str] = 'Stream'

    pk: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    title: Mapped[str] = mapped_column(sa.String(120))
    directory: Mapped[str] = mapped_column(sa.String(32), unique=True, index=True)
    marlin_la_url: Mapped[str | None] = mapped_column(sa.String(), nullable=True)
    playready_la_url: Mapped[str | None] = mapped_column(sa.String(), nullable=True)
    media_files: Mapped[list[MediaFile]] = relationship('MediaFile', cascade="all, delete")
    timing_ref: Mapped[JsonObject | None] = mapped_column(
        'timing_reference',
        sqlalchemy_jsonfield.JSONField(
            enforce_string=True,
            enforce_unicode=False
        ),
        nullable=True)
    defaults: Mapped[JsonObject | None] = mapped_column(
        'defaults',
        sqlalchemy_jsonfield.JSONField(
            enforce_string=True,
            enforce_unicode=False
        ),
        nullable=True)

    @classmethod
    def get(cls, **kwargs) -> Optional["Stream"]:
        """
        Get one object from this model, or None if not found
        """
        return cls.get_one(**kwargs)

    @classmethod
    def all(cls) -> list["Stream"]:
        """
        Return all items from this table
        """
        return cast(list["Stream"], cls.get_all())

    def toJSON(self, pure: bool = False,
               exclude: AbstractSet | None = None) -> JsonObject:
        timing_ref: str | None = None
        if self.timing_ref is not None:
            timing_ref = self.timing_ref['media_name']
        rv = {
            'pk': self.pk,
            'title': self.title,
            'directory': self.directory,
            'marlin_la_url': self.marlin_la_url,
            'playready_la_url': self.playready_la_url,
            'timing_ref': timing_ref,
        }
        if exclude is None:
            return rv
        for k in rv.keys():
            if k in exclude:
                del rv[k]
        return rv

    def get_fields(self, **kwargs) -> list[JsonObject]:

        has_media_files = False
        if self.pk:
            has_media_files = MediaFile.count(stream=self) > 0
        return [{
            "name": "title",
            "title": "Title",
            "type": "text",
            "maxlength": 100,
            "value": kwargs.get("title", self.title),
        }, {
            "name": "directory",
            "title": "Directory",
            "type": "text",
            "pattern": "[A-Za-z0-9]+",
            "minlength": 3,
            "maxlength": 30,
            "disabled": has_media_files,
            "value": kwargs.get("directory", self.directory),
        }, {
            "name": "marlin_la_url",
            "title": "Marlin LA URL",
            "type": "url",
            "pattern": "((ms3[hsa]*)|(https?))://.*",
            "value": str_or_none(kwargs.get("marlin_la_url", self.marlin_la_url)),
        }, {
            "name": "playready_la_url",
            "title": "PlayReady LA URL",
            "type": "url",
            "pattern": "https?://.*",
            "value": str_or_none(kwargs.get("playready_la_url", self.playready_la_url)),
        }]

    def get_timing_reference_file(self) -> MediaFile | None:
        if self.timing_ref is None:
            return None
        return MediaFile.get(
            name=self.timing_reference.media_name, stream_pk=self.pk)

    def get_timing_reference(self) -> StreamTimingReference | None:
        if self.timing_ref is None:
            return None
        try:
            return StreamTimingReference(**self.timing_ref)
        except TypeError:
            return None

    def set_timing_reference(
            self, ref: StreamTimingReference | None) -> None:
        if ref is None:
            self.timing_ref = None
        else:
            self.timing_ref = ref.toJSON()

    timing_reference = property(get_timing_reference, set_timing_reference)

    def duration(self) -> datetime.timedelta:
        tref = self.get_timing_reference()
        if tref is not None:
            return tref.media_duration_timedelta()
        for mfile in self.media_files:
            if mfile.representation is not None:
                return mfile.representation.media_duration_timedelta()
        return datetime.timedelta(0)

    def add_file(self, file_upload: FileStorage, commit: bool = False) -> MediaFile:
        filename = Path(secure_filename(file_upload.filename))
        upload_folder = Path(flask.current_app.config['BLOB_FOLDER']) / self.directory
        logging.debug('upload_folder="%s"', upload_folder)
        if not upload_folder.exists():
            upload_folder.mkdir(parents=True)
        assert upload_folder.exists()
        abs_filename = upload_folder / filename
        logging.debug('destination file "%s"', abs_filename)
        mf = MediaFile.get(name=filename.stem)
        if mf:
            mf.delete_file()
            mf.delete()
        blob = Blob.get_one(filename=filename.name)
        if blob:
            blob.delete_file(upload_folder)
            blob.delete()
        file_upload.save(abs_filename)
        blob = Blob(
            filename=filename.name,
            size=abs_filename.stat().st_size,
            content_type=file_upload.mimetype)
        with abs_filename.open('rb') as src:
            digest = hashlib.file_digest(src, 'sha1')
            blob.sha1_hash = digest.hexdigest()
        logging.debug("%s hash=%s", abs_filename, blob.sha1_hash)
        db.session.add(blob)
        mf = MediaFile(
            name=filename.stem, stream=self, blob=blob,
            content_type=file_upload.mimetype)
        db.session.add(mf)
        if not commit:
            return mf
        db.session.commit()
        return MediaFile.get(name=filename.stem, stream=self)

    def track_summary(self) -> StreamTrackSummary:
        """
        Produces a summary of all tracks in this stream
        """
        tracks: list[TrackSummary] = []
        for content_type in ['video', 'audio', 'text']:
            stmt = db.select(
                sa.func.count(sa.distinct(MediaFile.track_id))).filter_by(
                    stream_pk=self.pk, content_type=content_type)
            num_tracks: int = db.session.execute(stmt).scalar_one()
            tracks.append(TrackSummary(content_type, num_tracks))
        return StreamTrackSummary(
            video=tracks[0], audio=tracks[1], text=tracks[2])
