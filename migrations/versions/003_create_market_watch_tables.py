"""create_market_watch_tables

Revision ID: e5f7a1b2c3d4
Revises: 6b0dd678a5e4
Create Date: 2026-11-06 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f7a1b2c3d4'
down_revision: Union[str, None] = '6b0dd678a5e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create watchlists table
    op.create_table(
        'watchlists',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uix_watchlists_user_name'),
    )
    op.create_index(op.f('ix_watchlists_user_id'), 'watchlists', ['user_id'], unique=False)

    # 2. Create watchlist_items table
    op.create_table(
        'watchlist_items',
        sa.Column('watchlist_id', sa.Integer(), nullable=False),
        sa.Column('instrument_token', sa.String(length=32), nullable=False),
        sa.Column('exchange_segment', sa.String(length=16), nullable=False),
        sa.Column('trading_symbol', sa.String(length=64), nullable=False),
        sa.Column('display_name', sa.String(length=128), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['watchlist_id'], ['watchlists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('watchlist_id', 'instrument_token', 'exchange_segment', name='uix_watchlist_item_unique'),
    )
    op.create_index(op.f('ix_watchlist_items_watchlist_id'), 'watchlist_items', ['watchlist_id'], unique=False)
    op.create_index(op.f('ix_watchlist_items_instrument_token'), 'watchlist_items', ['instrument_token'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_watchlist_items_instrument_token'), table_name='watchlist_items')
    op.drop_index(op.f('ix_watchlist_items_watchlist_id'), table_name='watchlist_items')
    op.drop_table('watchlist_items')
    op.drop_index(op.f('ix_watchlists_user_id'), table_name='watchlists')
    op.drop_table('watchlists')
