"""Add MediaFileError table

Revision ID: 4400649632bb
Revises: 12fc8a1bb74f
Create Date: 2024-09-22 12:12:45.726268

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from dashlive.server.models.type_decorators import IntEnumType
from dashlive.server.models.error_reason import ErrorReason

# revision identifiers, used by Alembic.
revision: str = '4400649632bb'
down_revision: Union[str, None] = '12fc8a1bb74f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'media_file_error',
        sa.Column('pk', sa.Integer(), nullable=False),
        sa.Column('reason', IntEnumType(ErrorReason), nullable=False),
        sa.Column('details', sa.String(length=200), nullable=False),
        sa.Column('media_pk', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['media_pk'], ['media_file.pk'], ),
        sa.PrimaryKeyConstraint('pk'),
        sa.UniqueConstraint(
            "reason", "media_pk", name="single_reason_per_file"),
        if_not_exists=True
    )


def downgrade() -> None:
    op.drop_table('media_file_error')
