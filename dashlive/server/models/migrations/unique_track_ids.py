#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import datetime
from pathlib import Path

from dashlive.mpeg.mp4 import Wrapper
from dashlive.utils.files import generate_new_filename
from dashlive.utils.timezone import UTC

from ..db import db
from ..error_reason import ErrorReason
from ..mediafile import MediaFile
from ..mediafile_error import MediaFileError
from ..session import DatabaseSession

from .data_migration import DataMigration

class EnsureTrackIdsAreUnique(DataMigration):
    def __init__(self, blob_folder: Path) -> None:
        super().__init__()
        self.blob_folder = blob_folder

    def upgrade(self, session: DatabaseSession) -> None:
        content_types = self.find_content_types(session)
        self.log.debug('Content types: %s', content_types)
        next_track_ids = self.find_next_track_ids(session)
        mp4_fixups = self.assign_track_ids(session, content_types, next_track_ids)
        session.commit()  # make sure MediaFileError entrys are written to db
        for pk, track_id in mp4_fixups:
            media = session.execute(
                db.select(MediaFile).filter_by(pk=pk)).scalar_one_or_none()
            if media is None:
                self.log.error('Failed to get MediaFile pk=%d', pk)
                continue
            success = self.modify_media_file(session, media, track_id)
            if not success:
                self.log.error(
                    'Failed to update track ID for %d: %s', media.pk, media.name)

    def downgrade(self, session: DatabaseSession) -> None:
        pass

    def find_content_types(self, session: DatabaseSession) -> list[str]:
        content_types = ['video', 'audio', 'text']
        for media in session.query(MediaFile):
            if media.rep is None:
                if not media.parse_media_file(self.blob_folder):
                    continue
            media._pre_put_hook()
            if media.content_type not in content_types:
                content_types.append(media.content_type)
        return content_types

    @staticmethod
    def find_next_track_ids(session: DatabaseSession) -> dict[int, int]:
        next_track_ids: dict[int, int] = {}
        for media in session.query(MediaFile):
            if media.rep is None:
                continue
            try:
                next_track_ids[media.stream_pk] = max(
                    next_track_ids[media.stream_pk],
                    media.representation.track_id + 1)
            except KeyError:
                next_track_ids[media.stream_pk] = media.representation.track_id + 1
        return next_track_ids

    def assign_track_ids(self,
                         session: DatabaseSession,
                         content_types: list[str],
                         next_track_ids: dict[int, int]
                         ) -> list[tuple[int, int]]:
        track_id_map: dict[tuple[int, str, str], int] = {}
        track_content: dict[tuple[int, int], tuple[str, str]] = {}
        mp4_fixups: list[tuple[int, int]] = []
        for c_type in content_types:
            for media in session.query(MediaFile).filter_by(content_type=c_type):
                if media.rep is None:
                    self.log.warning(
                        'Representation information missing for mediafile %d %s',
                        media.pk, media.name)
                    continue
                self.log.info(
                    'Populating track ID for stream %d file %d', media.stream_pk,
                    media.pk)
                new_id = self.populate_track_id(
                    session, media, track_id_map, track_content, next_track_ids)
                if new_id is not None:
                    mp4_fixups.append((media.pk, new_id))
        return mp4_fixups

    def populate_track_id(self,
                          session: DatabaseSession,
                          media: MediaFile,
                          track_id_map: dict,
                          track_content: dict,
                          next_track_ids: dict[int, int]
                          ) -> int | None:
        assert media._representation is not None
        assert media.codec_fourcc is not None
        track_id_key = (media.stream_pk, media.content_type, media.codec_fourcc)
        try:
            media.track_id = track_id_map[track_id_key]
        except KeyError:
            media.track_id = media.representation.track_id
        self.log.info(
            'stream %d file %d: track=%d codec=%s', media.stream_pk, media.pk,
            media.track_id, media.codec_fourcc)
        track_key = (media.stream_pk, media.track_id)
        content_key = (media.content_type, media.codec_fourcc)
        if track_content.get(track_key, content_key) != content_key:
            self.log.warning(
                'Duplicate track ID for stream %d file %d',
                media.stream_pk, media.pk)
            details = (
                f'track ID {media.track_id} already exists of type ' +
                f'{track_content[track_key]}, but file {media.name} ' +
                f'is of type {content_key}')
            self.log.warning('%s', details)
            media.track_id = next_track_ids[media.stream_pk]
            next_track_ids[media.stream_pk] += 1
            track_key = (media.stream_pk, media.track_id)
            self.log.warning(
                'Using track ID %d for %s', media.track_id, content_key)
            err = MediaFileError(
                media_file=media,
                reason=ErrorReason.DUPLICATE_TRACK_IDS,
                details=details)
            session.add(err)

        track_content[track_key] = content_key
        track_id_map[track_id_key] = media.track_id
        if media.track_id != media.representation.track_id:
            self.log.warning(
                'File %s needs to have its track ID updated from %d to %d',
                media.blob.filename, media.representation.track_id,
                media.track_id)
            return media.track_id
        return None

    def modify_media_file(self,
                          session: DatabaseSession,
                          media: MediaFile,
                          track_id: int) -> bool:
        abs_path = self.blob_folder / media.stream.directory
        filename = Path(media.blob.filename)
        new_name = generate_new_filename(
            abs_path, f'{filename.stem}_{track_id:02d}', filename.suffix)
        self.log.warning(
            'Creating new MP4 file %s from %s with track ID %d',
            new_name, abs_path / filename, track_id)
        return media.modify_media_file(
            session=session, blob_folder=self.blob_folder, new_filename=new_name,
            modify_atoms=lambda atom: EnsureTrackIdsAreUnique.set_track_id(
                atom, track_id))

    @staticmethod
    def set_track_id(wrap: Wrapper, new_track_id: int) -> bool:
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
