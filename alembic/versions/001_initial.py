"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-04-04 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This is handled by database.py init on first run
    # Migrations are for existing installs to add missing columns
    pass


def downgrade() -> None:
    pass