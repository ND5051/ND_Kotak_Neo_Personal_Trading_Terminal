"""create_order_tables

Revision ID: f8a9b0c1d2e3
Revises: e5f7a1b2c3d4
Create Date: 2026-11-06 14:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, None] = 'e5f7a1b2c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create orders table
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('client_order_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('broker_order_id', sa.String(length=64), nullable=True),
        sa.Column('exchange_order_id', sa.String(length=64), nullable=True),
        sa.Column('instrument_token', sa.String(length=32), nullable=False),
        sa.Column('exchange_segment', sa.String(length=16), nullable=False),
        sa.Column('trading_symbol', sa.String(length=64), nullable=False),
        sa.Column('side', sa.String(length=8), nullable=False),
        sa.Column('order_type', sa.String(length=16), nullable=False),
        sa.Column('product_type', sa.String(length=16), nullable=False),
        sa.Column('validity', sa.String(length=8), nullable=False, server_default='DAY'),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('filled_quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pending_quantity', sa.Integer(), nullable=False),
        sa.Column('disclosed_quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('price', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('trigger_price', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('average_price', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('exchange_timestamp', sa.String(length=64), nullable=True),
        sa.Column('source_timestamp', sa.String(length=64), nullable=True),
        sa.Column('retrieved_timestamp', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_order_id')
    )
    op.create_index('idx_orders_user_status', 'orders', ['user_id', 'status'])
    op.create_index('idx_orders_broker_id', 'orders', ['broker_order_id'])
    op.create_index('idx_orders_symbol', 'orders', ['trading_symbol'])
    op.create_index('idx_orders_status', 'orders', ['status'])

    # 2. Create order_events table
    op.create_table(
        'order_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('client_order_id', sa.String(length=64), nullable=False),
        sa.Column('from_status', sa.String(length=32), nullable=False),
        sa.Column('to_status', sa.String(length=32), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('payload_snapshot', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_order_events_order_id', 'order_events', ['order_id'])
    op.create_index('idx_order_events_client_order_id', 'order_events', ['client_order_id'])

    # 3. Create trade_executions table
    op.create_table(
        'trade_executions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('trade_id', sa.String(length=64), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('client_order_id', sa.String(length=64), nullable=False),
        sa.Column('broker_order_id', sa.String(length=64), nullable=False),
        sa.Column('fill_quantity', sa.Integer(), nullable=False),
        sa.Column('fill_price', sa.Float(), nullable=False),
        sa.Column('exchange_segment', sa.String(length=16), nullable=False),
        sa.Column('trading_symbol', sa.String(length=64), nullable=False),
        sa.Column('exchange_timestamp', sa.String(length=64), nullable=False),
        sa.Column('retrieved_timestamp', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trade_id')
    )
    op.create_index('idx_trade_executions_order_id', 'trade_executions', ['order_id'])
    op.create_index('idx_trade_executions_client_order_id', 'trade_executions', ['client_order_id'])


def downgrade() -> None:
    op.drop_table('trade_executions')
    op.drop_table('order_events')
    op.drop_table('orders')
