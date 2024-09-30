"""Add AdaptationSet, Period and MultiPeriodStream tables

Revision ID: b49e3234ce8a
Revises: 4afbed324b31
Create Date: 2024-09-30 14:34:32.287749

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from dashlive.mpeg.dash.content_role import ContentRole
from dashlive.server.models.type_decorators import IntEnumType

# revision identifiers, used by Alembic.
revision: str = 'b49e3234ce8a'
down_revision: Union[str, None] = '4afbed324b31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mp_stream',
        sa.Column('pk', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_mp_stream_name'), 'mp_stream', ['name'], unique=True)

    op.create_table(
        'period',
        sa.Column('pk', sa.Integer(), nullable=False),
        sa.Column('pid', sa.String(length=62), nullable=False),
        sa.Column('parent_pk', sa.Integer(), nullable=False),
        sa.Column('ordering', sa.Integer(), nullable=False),
        sa.Column('stream_pk', sa.Integer(), nullable=False),
        sa.Column('start', sa.Interval(), nullable=True),
        sa.Column('duration', sa.Interval(), nullable=True),
        sa.ForeignKeyConstraint(['parent_pk'], ['mp_stream.pk'], ),
        sa.ForeignKeyConstraint(['stream_pk'], ['Stream.pk'], ),
        sa.PrimaryKeyConstraint('pk'),
        sa.UniqueConstraint('parent_pk', 'pid',
                            name='single_period_id_per_mp_stream'),
        sa.UniqueConstraint('parent_pk', 'ordering',
                            name='unique_order_per_mp_stream')
    )

    op.create_table(
        'adaptation_set',
        sa.Column('pk', sa.Integer(), nullable=False),
        sa.Column('period_pk', sa.Integer(), nullable=False),
        sa.Column('track_id', sa.Integer(), nullable=False),
        sa.Column('role', IntEnumType(ContentRole), nullable=False),
        sa.Column('content_type', sa.String(length=62), nullable=False),
        sa.ForeignKeyConstraint(['period_pk'], ['period.pk'], ),
        sa.PrimaryKeyConstraint('pk'),
        sa.UniqueConstraint('period_pk', 'track_id',
                            name='single_track_id_per_period')
    )


def downgrade() -> None:
    op.drop_table('adaptation_set')
    op.drop_table('period')
    op.drop_index(op.f('ix_mp_stream_name'), table_name='mp_stream')
    op.drop_table('mp_stream')
