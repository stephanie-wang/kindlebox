"""empty message

Revision ID: 49fb024e38
Revises: 4803d1675b53
Create Date: 2015-03-03 22:03:05.856975

"""

# revision identifiers, used by Alembic.
revision = '49fb024e38'
down_revision = '4803d1675b53'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user', sa.Column('email', sa.String(length=120), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'email')
    ### end Alembic commands ###
