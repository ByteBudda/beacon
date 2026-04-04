"""Add trial_period table

Revision ID: 002_add_trial
Revises: 001_initial
Create Date: 2026-04-04 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '002_add_trial'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add trial_periods table for PRO trial tracking
    op.create_table('trial_periods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('plan', sa.String(20), nullable=False),
        sa.Column('started_at', sa.Float(), nullable=False),
        sa.Column('expires_at', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_trial_user', 'trial_periods', ['user_id'])
    
    # Add trial_eligible column to users
    op.add_column('users', sa.Column('trial_eligible', sa.Boolean(), default=True))


def downgrade() -> None:
    op.drop_column('users', 'trial_eligible')
    op.drop_index('idx_trial_user')
    op.drop_table('trial_periods')