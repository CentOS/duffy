"""ignore failed nodes in unique indexes

Revision ID: 36cf064c0481
Revises: ce2e575cb800
Create Date: 2023-07-27 11:29:37.405520
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "36cf064c0481"
down_revision = "ce2e575cb800"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("active_hostname_index")
    op.create_index(
        "active_hostname_index",
        "nodes",
        ["hostname"],
        unique=True,
        postgresql_where=sa.text(
            "retired_at IS NULL AND state <> 'provisioning'::node_state_enum"
            + " AND state <> 'failed'::node_state_enum"
        ),
        sqlite_where=sa.text(
            "retired_at IS NULL AND state != 'provisioning' AND state != 'failed'"
        ),
    )
    op.drop_index("active_ipaddr_index")
    op.create_index(
        "active_ipaddr_index",
        "nodes",
        ["ipaddr"],
        unique=True,
        postgresql_where=sa.text(
            "retired_at IS NULL AND state <> 'provisioning'::node_state_enum"
            + " AND state <> 'failed'::node_state_enum"
        ),
        sqlite_where=sa.text(
            "retired_at IS NULL AND state != 'provisioning' AND state != 'failed'"
        ),
    )


def downgrade():
    op.drop_index("active_hostname_index")
    op.create_index(
        "active_hostname_index",
        "nodes",
        ["hostname"],
        unique=True,
        postgresql_where=sa.text("retired_at IS NULL AND state <> 'provisioning'::node_state_enum"),
        sqlite_where=sa.text("retired_at IS NULL AND state != 'provisioning'"),
    )
    op.drop_index("active_ipaddr_index")
    op.create_index(
        "active_ipaddr_index",
        "nodes",
        ["ipaddr"],
        unique=True,
        postgresql_where=sa.text("retired_at IS NULL AND state <> 'provisioning'::node_state_enum"),
        sqlite_where=sa.text("retired_at IS NULL AND state != 'provisioning'"),
    )
