"""Add market price columns to Ads

Revision ID: e06bdc982363
Revises: 7c66a72da098
Create Date: 2026-09-13 21:10:06.436023

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e06bdc982363'
down_revision: Union[str, Sequence[str], None] = '7c66a72da098'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('ads', sa.Column('market_price_status', sa.String(length=50), nullable=True))
    op.add_column('ads', sa.Column('market_average_price', sa.DECIMAL(precision=10, scale=2), nullable=True))

def downgrade() -> None:
    op.drop_column('ads', 'market_average_price')
    op.drop_column('ads', 'market_price_status')
