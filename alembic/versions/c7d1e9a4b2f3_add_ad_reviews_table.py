"""Add ad_reviews table

Revision ID: c7d1e9a4b2f3
Revises: cbde4dedf773
Create Date: 2026-10-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c7d1e9a4b2f3'
down_revision: Union[str, Sequence[str], None] = 'cbde4dedf773'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The app also runs Base.metadata.create_all on startup, so the table may already exist
    if sa.inspect(op.get_bind()).has_table('ad_reviews'):
        return
    op.create_table('ad_reviews',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ad_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('rating', sa.Integer(), nullable=False),
    sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('is_hidden', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['ad_id'], ['ads.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('ad_id', 'user_id', name='uq_ad_reviews_ad_user')
    )
    op.create_index(op.f('ix_ad_reviews_id'), 'ad_reviews', ['id'], unique=False)
    op.create_index(op.f('ix_ad_reviews_ad_id'), 'ad_reviews', ['ad_id'], unique=False)
    op.create_index(op.f('ix_ad_reviews_user_id'), 'ad_reviews', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ad_reviews_user_id'), table_name='ad_reviews')
    op.drop_index(op.f('ix_ad_reviews_ad_id'), table_name='ad_reviews')
    op.drop_index(op.f('ix_ad_reviews_id'), table_name='ad_reviews')
    op.drop_table('ad_reviews')
