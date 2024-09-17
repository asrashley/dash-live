#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import contextlib
from pathlib import Path
from typing import cast, Optional

import flask
import sqlalchemy as sa
import sqlalchemy_jsonfield  # type: ignore
from sqlalchemy.event import listen  # type: ignore
from sqlalchemy.orm import reconstructor  # type: ignore

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

    # 'video', 'audio' or 'text'
    content_type = sa.Column(sa.String(64), nullable=True, index=True)

    track_id = sa.Column(sa.Integer, index=True, nullable=True)

    # the fourcc of the audio/video/text codec
    # 'avc1', 'avc3', 'hev1', 'mp4a', 'ec3', 'ac_3', 'stpp'
    codec_fourcc = sa.Column(sa.String(16), nullable=True, index=False)

    encrypted = sa.Column(sa.Boolean, default=False, index=True, nullable=False)

    encryption_keys: db.Mapped[list[Key]] = db.relationship(secondary=mediafile_keys, back_populates='mediafiles')

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


# pylint: disable=unused-argument
def before_mediafile_save(mapper, connect, mediafile):
    mediafile._pre_put_hook()


listen(MediaFile, 'before_insert', before_mediafile_save)
