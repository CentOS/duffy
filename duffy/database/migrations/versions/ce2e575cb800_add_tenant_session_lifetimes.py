"""Add tenant session lifetimes

Revision ID: ce2e575cb800
Revises:
Create Date: 2022-05-09 16:40:06.491392
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ce2e575cb800"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tenants", sa.Column("session_lifetime", sa.Interval(), nullable=True))
    op.add_column("tenants", sa.Column("session_lifetime_max", sa.Interval(), nullable=True))


def downgrade():
    op.drop_column("tenants", "session_lifetime_max")
    op.drop_column("tenants", "session_lifetime")
