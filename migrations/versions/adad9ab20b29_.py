"""Add open nebula nodes

Revision ID: adad9ab20b29
Revises: e77103337fe5
Create Date: 2020-09-24 11:27:13.969938

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = 'adad9ab20b29'
down_revision = 'e77103337fe5'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add the Open Nebula table and type to sessions table.
    """
    op.create_table('opennebula_nodes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=30), nullable=True),
    sa.Column('hostname', sa.String(length=20), nullable=True),
    sa.Column('ip', sa.String(length=15), nullable=True),
    sa.Column('state', sa.String(length=20), nullable=True),
    sa.Column('comment', sa.String(length=255), nullable=True),
    sa.Column('template_id', sa.String(length=30), nullable=True),
    sa.Column('flavor', sa.String(length=20), nullable=True),
    sa.Column('session_id', sa.String(length=37), nullable=True),
    sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], name=op.f('fk_opennebula_nodes_session_id_sessions')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_opennebula_nodes'))
    )
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('type', sa.String(length=15), nullable=True))

    op.execute("UPDATE sessions SET type = 'bare_metal'")

def downgrade():
    """
    Remove the Open Nebula table and the type from sessions table.
    """
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.drop_column('type')

    op.drop_table('opennebula_nodes')
