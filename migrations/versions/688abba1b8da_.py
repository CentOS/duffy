"""empty message

Revision ID: 688abba1b8da
Revises: 
Create Date: 2018-01-16 22:08:43.906441

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '688abba1b8da'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():

    from duffy.extensions import db
    from duffy.models.nodes import Session
    from sqlalchemy import func

    print("Creating a session archive")
    op.execute("CREATE TABLE session_archive LIKE sessions")
    print("Inserting into the archive")
    op.execute("INSERT INTO session_archive SELECT * FROM sessions")
    print("Deleting the sessions table")
    op.execute("DELETE FROM sessions where state<>'Prod'")

    op.create_primary_key("pk_users", "users", ['apikey'])
    op.create_primary_key("pk_sessions", "sessions", ['id'])

    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('userkeys',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.String(length=37), nullable=True),
    sa.Column('key', sa.String(length=8192), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['users.apikey'], name=op.f('fk_userkeys_project_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_userkeys'))
    )
    op.drop_table('stockbk')
    op.drop_table('session_hosts')
    op.drop_table('sessions_160120a')
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.drop_column('node_id')

    with op.batch_alter_table('stock', schema=None) as batch_op:
        batch_op.add_column(sa.Column('session_id', sa.String(length=37), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_stock_session_id_sessions'), 'sessions', ['session_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('stock', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_stock_session_id_sessions'), type_='foreignkey')
        batch_op.drop_column('session_id')

    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('node_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True))

    op.create_table('sessions_160120a',
    sa.Column('id', mysql.VARCHAR(length=37), nullable=True),
    sa.Column('node_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.Column('delivered_at', sa.DATE(), nullable=True),
    sa.Column('dropped_at', sa.DATE(), nullable=True),
    sa.Column('apikey', mysql.VARCHAR(length=37), nullable=True),
    sa.Column('state', mysql.VARCHAR(length=15), nullable=True),
    mysql_default_charset=u'latin1',
    mysql_engine=u'MyISAM'
    )
    op.create_table('session_hosts',
    sa.Column('ssid', mysql.VARCHAR(length=37), nullable=True),
    sa.Column('hostname', mysql.VARCHAR(length=20), nullable=True),
    mysql_default_charset=u'latin1',
    mysql_engine=u'MyISAM'
    )
    op.create_table('stockbk',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('hostname', mysql.VARCHAR(length=20), nullable=True),
    sa.Column('ip', mysql.VARCHAR(length=15), nullable=True),
    sa.Column('chassis', mysql.VARCHAR(length=20), nullable=True),
    sa.Column('used_count', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.Column('state', mysql.VARCHAR(length=20), nullable=True),
    sa.Column('comment', mysql.VARCHAR(length=255), nullable=True),
    sa.Column('distro', mysql.VARCHAR(length=20), nullable=True),
    sa.Column('rel', mysql.VARCHAR(length=10), nullable=True),
    sa.Column('ver', mysql.VARCHAR(length=10), nullable=True),
    sa.Column('arch', mysql.VARCHAR(length=10), nullable=True),
    sa.Column('pool', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    mysql_default_charset=u'latin1',
    mysql_engine=u'MyISAM'
    )
    op.drop_table('userkeys')
    # ### end Alembic commands ###
