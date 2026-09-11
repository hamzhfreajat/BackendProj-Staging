"""Add duplicate_status and highest_duplicate_score to ads

Revision ID: 7c66a72da098
Revises: 8741ebb87513
Create Date: 2026-09-12 00:21:33.988396

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c66a72da098'
down_revision: Union[str, Sequence[str], None] = '8741ebb87513'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('ads', sa.Column('duplicate_status', sa.String(length=50), nullable=True))
    op.add_column('ads', sa.Column('highest_duplicate_score', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ads', 'highest_duplicate_score')
    op.drop_column('ads', 'duplicate_status')
