"""add user settings for ilham_ai

Revision ID: c8a9b7d6e5f4
Revises: b4a5f8c3d2e1
Create Date: 2025-12-15 01:36:25.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8a9b7d6e5f4'
down_revision: Union[str, None] = 'b4a5f8c3d2e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('settings_enable_ilham_contextual', sa.Boolean(), server_default='true', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'settings_enable_ilham_contextual')