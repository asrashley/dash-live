import contextlib
from pathlib import Path
from typing import cast, Optional

import flask
import sqlalchemy as sa
import sqlalchemy_jsonfield  # type: ignore
from sqlalchemy.event import listen  # type: ignore

from dashlive.mpeg.dash.representation import Representation
from dashlive.mpeg.dash.reference import StreamTimingReference
from dashlive.utils.date_time import to_iso_datetime
from dashlive.utils.json_object import JsonObject
from .db import db
from .key import Key
from .mixin import ModelMixin
from .mediafile_keys import mediafile_keys

class MediaFile(db.Model, ModelMixin):
    """representation of one MP4 file"""
    __plural__ = 'MediaFiles'

    pk: db.Mapped[int] = db.Column('pk', sa.Integer, primary_key=True)
    name = sa.Column('name', sa.String(200), nullable=False, unique=True, index=True)
    stream_pk = sa.Column(
        'stream', sa.Integer, sa.ForeignKey('Stream.pk'),
        nullable=False)
    stream = db.relationship('Stream', back_populates='media_files')
    blob_pk = sa.Column('blob', sa.Integer, sa.ForeignKey('Blob.pk'),
                        nullable=False, unique=True)
    blob = db.relationship('Blob', back_populates='mediafile',
                           cascade='all, delete')
    rep = sa.Column(
        'rep',
        sqlalchemy_jsonfield.JSONField(
            enforce_string=True,
            enforce_unicode=False
        ),
        nullable=True)
    bitrate = sa.Column(sa.Integer, default=0, index=True, nullable=False)
    content_type = sa.Column(sa.String(64), nullable=True, index=True)
    encrypted = sa.Column(sa.Boolean, default=False, index=True, nullable=False)
    encryption_keys: db.Mapped[list[Key]] = db.relationship(secondary=mediafile_keys, back_populates='mediafiles')

    _representation = None

    def _pre_put_hook(self):
        if self._representation is not None:
            if self.content_type is None:
                self.content_type = self._representation.content_type
                self.encrypted = self._representation.encrypted
                self.bitrate = self._representation.bitrate

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
    def all(clz, order_by: tuple | None = None) -> list["MediaFile"]:
        return cast(list["MediaFile"], clz.get_all(order_by=order_by))

    @classmethod
    def search(clz, content_type: str | None = None,
               encrypted: bool | None = None,
               stream: Optional["Stream"] = None,  # noqa: F821
               max_items: int | None = None) -> list["MediaFile"]:
        # print('MediaFile.all()', contentType, encrypted, prefix, maxItems)
        query = db.select(MediaFile)
        if content_type is not None:
            query = query.filter_by(content_type=content_type)
        if encrypted is not None:
            query = query.filter_by(encrypted=encrypted)
        if stream is not None:
            query = query.filter_by(stream_pk=stream.pk)
        query = query.order_by(MediaFile.bitrate)
        if max_items is not None:
            query = query.limit(max_items)
        return list(db.session.execute(query).scalars())

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


# pylint: disable=unused-argument
def before_mediafile_save(mapper, connect, mediafile):
    mediafile._pre_put_hook()


listen(MediaFile, 'before_insert', before_mediafile_save)
