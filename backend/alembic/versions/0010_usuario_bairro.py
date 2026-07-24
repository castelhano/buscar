"""usuario_bairro: adiciona Usuario.bairro

Rotulo curto do endereco de casa do usuario (ex: "Jd Imperial II"),
complementar ao endereco completo ja existente em `Usuario.detalhe`. Junto
com `detalhe` e `regiao_id`, e usado automaticamente quando um trecho
referencia o endereco principal do usuario (TipoPonto.USUARIO) como origem
ou destino, sem precisar redigitar o bairro em cada trecho.

So adiciona a coluna (nullable) -- o backfill a partir dos trechos
`UsuarioAgendaSemanalTrecho` existentes e feito num script a parte, fora
desta migracao (mesmo padrao usado pro backfill de `Usuario.regiao_id`).

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-24 11:13:54.933830

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0010'
down_revision: Union[str, Sequence[str], None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bairro', sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.drop_column('bairro')
