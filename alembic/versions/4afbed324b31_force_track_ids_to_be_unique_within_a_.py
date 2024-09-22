"""force track IDs to be unique within a stream

Revision ID: 4afbed324b31
Revises: 4400649632bb
Create Date: 2024-09-17 11:01:45.332478

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from dashlive.server.models.migrations.unique_track_ids import EnsureTrackIdsAreUnique
from dashlive.server.folders import AppFolders

# revision identifiers, used by Alembic.
revision: str = '4afbed324b31'
down_revision: Union[str, None] = '4400649632bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = ('12fc8a1bb74f',)


def upgrade() -> None:
    folders = AppFolders()
    print(folders)
    folders.check(check_media=False)
    bind = op.get_bind()
    session = sa.orm.Session(bind=bind)
    migration = EnsureTrackIdsAreUnique(folders.blob_folder)
    migration.upgrade(session)
    session.commit()
    op.create_index('media_file_track_id', 'media_file', ['stream', 'track_id'])


def downgrade() -> None:
    op.drop_index('media_file_track_id', 'media_file')
    folders = AppFolders()
    bind = op.get_bind()
    session = sa.orm.Session(bind=bind)
    migration = EnsureTrackIdsAreUnique(folders.blob_folder)
    migration.downgrade(session)
    session.commit()
