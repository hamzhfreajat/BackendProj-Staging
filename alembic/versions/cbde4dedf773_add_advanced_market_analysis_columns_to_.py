"""add_advanced_market_analysis_columns_to_ads

Revision ID: cbde4dedf773
Revises: e06bdc982363
Create Date: 2026-09-15 18:41:34.078302

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cbde4dedf773'
down_revision: Union[str, Sequence[str], None] = 'e06bdc982363'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('ads', sa.Column('deviation_pct', sa.DECIMAL(precision=10, scale=4), nullable=True))
    op.add_column('ads', sa.Column('comparables_count', sa.Integer(), nullable=True))
    op.add_column('ads', sa.Column('confidence_level', sa.String(length=50), nullable=True))
    op.add_column('ads', sa.Column('matching_level_used', sa.Integer(), nullable=True))
    op.add_column('ads', sa.Column('calculated_at', sa.TIMESTAMP(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ads', 'calculated_at')
    op.drop_column('ads', 'matching_level_used')
    op.drop_column('ads', 'confidence_level')
    op.drop_column('ads', 'comparables_count')
    op.drop_column('ads', 'deviation_pct')
