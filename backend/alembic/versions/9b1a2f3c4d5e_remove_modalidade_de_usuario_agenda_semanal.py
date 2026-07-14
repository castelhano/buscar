"""remove modalidade de usuario_agenda_semanal

Revision ID: 9b1a2f3c4d5e
Revises: ece1ffd29ff4
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b1a2f3c4d5e'
down_revision: Union[str, Sequence[str], None] = 'ece1ffd29ff4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('usuario_agenda_semanal', schema=None) as batch_op:
        batch_op.drop_column('modalidade')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('usuario_agenda_semanal', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'modalidade',
                sa.Enum('SOMENTE_IDA', 'IDA_E_VOLTA', name='modalidade', native_enum=False, length=20),
                nullable=False,
                server_default='IDA_E_VOLTA',
            )
        )
