"""trecho_observacoes: adiciona observacoes em UsuarioAgendaSemanalTrecho e UsuarioExcecaoTrecho

Nota pre-cadastrada no trecho (Fixo ou Excecao) que a geracao do dia copia
pro ViagemDiaPassageiro.observacoes -- evita ter que redigitar na tela do
dia toda vez que o mesmo atendimento se repete (ex: recorrencias de
Excecao).

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0012'
down_revision: Union[str, Sequence[str], None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('usuario_agenda_semanal_trecho', schema=None) as batch_op:
        batch_op.add_column(sa.Column('observacoes', sa.Text(), nullable=True))
    with op.batch_alter_table('usuario_excecao_trecho', schema=None) as batch_op:
        batch_op.add_column(sa.Column('observacoes', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('usuario_excecao_trecho', schema=None) as batch_op:
        batch_op.drop_column('observacoes')
    with op.batch_alter_table('usuario_agenda_semanal_trecho', schema=None) as batch_op:
        batch_op.drop_column('observacoes')
