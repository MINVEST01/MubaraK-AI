"""add ilham_preferences to user

Revision ID: b4a5f8c3d2e1
Revises: 2d1b71b9c7a0
Create Date: 2025-12-15 01:36:10.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4a5f8c3d2e1'
down_revision: Union[str, None] = '2d1b71b9c7a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('ilham_preferences', sa.JSON(), server_default='{}', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'ilham_preferences')