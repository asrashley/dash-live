"""Add track_id and fourcc columns to mediafile model

Revision ID: 12fc8a1bb74f
Revises: e3cdc4f4779b
Create Date: 2024-09-16 10:42:31.543128

"""
import logging
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

# revision identifiers, used by Alembic.
revision: str = '12fc8a1bb74f'
down_revision: Union[str, None] = 'e3cdc4f4779b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    try:
        op.add_column(
            'media_file',
            sa.Column('track_id', sa.Integer, index=True, nullable=True))
    except OperationalError as err:
        logging.warning('Failed to create track ID column: %s', err)
        logging.warning('Assuming migration has already been applied')
        return

    op.add_column(
        'media_file',
        sa.Column('codec_fourcc', sa.String(16), nullable=True, index=False))
    try:
        op.create_index(
            op.f('ix_media_file_track_id'), 'media_file', ['track_id'], unique=False)
    except OperationalError as err:
        logging.warning('Failed to create track ID index: %s', err)


def downgrade() -> None:
    op.drop_index(op.f('ix_media_file_track_id'), table_name='media_file')
    op.drop_column('media_file', 'track_id')
    op.drop_column('media_file', 'codec_fourcc')
