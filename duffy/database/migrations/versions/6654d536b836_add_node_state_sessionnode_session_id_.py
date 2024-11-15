"""Add Node.state, SessionNode.session_id indexes

Revision ID: 6654d536b836
Revises: 36cf064c0481
Create Date: 2023-09-06 21:42:56.647045
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "6654d536b836"
down_revision = "36cf064c0481"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f("nodes_state_index"), "nodes", ["state"], unique=False)
    op.create_index(
        op.f("sessions_nodes_session_id_index"), "sessions_nodes", ["session_id"], unique=False
    )


def downgrade():
    op.drop_index(op.f("sessions_nodes_session_id_index"), table_name="sessions_nodes")
    op.drop_index(op.f("nodes_state_index"), table_name="nodes")
