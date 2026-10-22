"""login attempts table

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-22 12:25:00.406042+00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('login_attempts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_login_attempts'))
    )
    op.create_index('ix_login_attempts_key_created', 'login_attempts', ['key_hash', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_login_attempts_key_created', table_name='login_attempts')
    op.drop_table('login_attempts')
