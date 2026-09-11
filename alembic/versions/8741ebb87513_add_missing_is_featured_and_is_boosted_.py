"""Add missing is_featured and is_boosted columns to ad_search_index

Revision ID: 8741ebb87513
Revises: 5ee2b5ff018a
Create Date: 2026-09-11 23:03:41.589921

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8741ebb87513'
down_revision: Union[str, Sequence[str], None] = '5ee2b5ff018a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('ad_search_index', sa.Column('is_featured', sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ad_search_index', 'is_featured')
