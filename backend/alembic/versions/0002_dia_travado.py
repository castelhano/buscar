"""dia travado

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('dia_travado',
    sa.Column('data', sa.Date(), nullable=False),
    sa.Column('travado_em', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('data')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('dia_travado')
