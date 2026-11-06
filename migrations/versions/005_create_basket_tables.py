"""create_basket_tables

Revision ID: a1b2c3d4e5f6
Revises: f8a9b0c1d2e3
Create Date: 2026-11-06 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create baskets table
    op.create_table(
        'baskets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('client_basket_id', sa.String(length=64), nullable=False),
        sa.Column('basket_idempotency_key', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('strategy_type', sa.String(length=32), nullable=False),
        sa.Column('strategy_version', sa.String(length=32), nullable=False),
        sa.Column('execution_mode', sa.String(length=16), nullable=False),
        sa.Column('basket_execution_mode', sa.String(length=16), nullable=False),
        sa.Column('failure_policy', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('exposure_state', sa.String(length=32), nullable=False),
        sa.Column('estimated_margin', sa.Float(), nullable=False),
        sa.Column('margin_snapshot', sa.JSON(), nullable=False),
        sa.Column('validation_timestamp', sa.String(length=64), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('source_timestamp', sa.String(length=64), nullable=True),
        sa.Column('retrieved_timestamp', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_basket_id')
    )
    op.create_index(op.f('ix_baskets_client_basket_id'), 'baskets', ['client_basket_id'], unique=True)
    op.create_index(op.f('ix_baskets_user_id'), 'baskets', ['user_id'], unique=False)
    op.create_index(op.f('ix_baskets_status'), 'baskets', ['status'], unique=False)
    op.create_index(op.f('ix_baskets_strategy_type'), 'baskets', ['strategy_type'], unique=False)

    # 2. Create basket_legs table
    op.create_table(
        'basket_legs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('basket_id', sa.Integer(), nullable=False),
        sa.Column('leg_index', sa.Integer(), nullable=False),
        sa.Column('trading_symbol', sa.String(length=64), nullable=False),
        sa.Column('exchange_segment', sa.String(length=16), nullable=False),
        sa.Column('instrument_token', sa.String(length=32), nullable=False),
        sa.Column('side', sa.String(length=8), nullable=False),
        sa.Column('order_type', sa.String(length=16), nullable=False),
        sa.Column('product_type', sa.String(length=16), nullable=False),
        sa.Column('validity', sa.String(length=8), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('trigger_price', sa.Float(), nullable=False),
        sa.Column('order_id', sa.String(length=64), nullable=True),
        sa.Column('broker_order_id', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('filled_quantity', sa.Integer(), nullable=False),
        sa.Column('average_price', sa.Float(), nullable=False),
        sa.Column('depends_on_leg_index', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['basket_id'], ['baskets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_basket_legs_basket_id'), 'basket_legs', ['basket_id'], unique=False)
    op.create_index(op.f('ix_basket_legs_order_id'), 'basket_legs', ['order_id'], unique=False)
    op.create_index(op.f('ix_basket_legs_broker_order_id'), 'basket_legs', ['broker_order_id'], unique=False)

    # 3. Create basket_events table
    op.create_table(
        'basket_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('basket_id', sa.Integer(), nullable=False),
        sa.Column('client_basket_id', sa.String(length=64), nullable=False),
        sa.Column('from_status', sa.String(length=32), nullable=False),
        sa.Column('to_status', sa.String(length=32), nullable=False),
        sa.Column('from_exposure', sa.String(length=32), nullable=False),
        sa.Column('to_exposure', sa.String(length=32), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('source_timestamp', sa.String(length=64), nullable=True),
        sa.Column('retrieved_timestamp', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['basket_id'], ['baskets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_basket_events_basket_id'), 'basket_events', ['basket_id'], unique=False)
    op.create_index(op.f('ix_basket_events_client_basket_id'), 'basket_events', ['client_basket_id'], unique=False)


def downgrade() -> None:
    op.drop_table('basket_events')
    op.drop_table('basket_legs')
    op.drop_table('baskets')

