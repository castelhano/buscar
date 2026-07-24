"""Resolucao de "pontos" (origem/destino de um trecho) a partir do tipo
escolhido -- ver `app.models.TipoPonto`. Compartilhado entre a config
recorrente (Agenda Semanal/Excecao, `routers/usuarios.py`) e o trecho
materializado do dia (`routers/viagens.py`): os dois preenchem os mesmos
campos (`*_tipo`, `*_id`, `*_texto`, `*_detalhe`, `regiao_*_id`) a partir da
mesma escolha de tipo, derivando regiao/rotulo/endereco automaticamente
sempre que possivel (so o tipo Avulso exige informar a regiao na mao, ja que
nao ha Local nem Usuario de onde deriva-la).
"""

from sqlalchemy.orm import Session

from app.models import Local, TipoPonto, Usuario


class PontoInvalido(ValueError):
    """Ponto (origem ou destino) invalido -- o router converte pra HTTPException 400."""


def resolver_ponto(
    db: Session,
    tipo: TipoPonto,
    usuario: Usuario,
    local_id: int | None,
    texto: str | None,
    detalhe: str | None,
    regiao_override_id: int | None,
    lado: str,
) -> dict:
    """Resolve os campos persistidos de um lado (origem OU destino) de um
    trecho a partir do tipo escolhido. `lado` e so pra mensagem de erro
    ("origem"/"destino").
    """
    if tipo == TipoPonto.LOCAL:
        if local_id is None:
            raise PontoInvalido(f"Informe o local da {lado}")
        local = db.get(Local, local_id)
        if local is None:
            raise PontoInvalido(f"Local {local_id} nao encontrado")
        return {"tipo": tipo, "id": local_id, "texto": None, "detalhe": None, "regiao_id": local.regiao_id}
    if tipo == TipoPonto.USUARIO:
        if usuario.regiao_id is None:
            raise PontoInvalido(
                f"Usuario {usuario.nome} nao tem regiao cadastrada -- necessaria pra usar o endereco "
                f"dele como {lado}"
            )
        return {"tipo": tipo, "id": None, "texto": None, "detalhe": None, "regiao_id": usuario.regiao_id}
    if tipo == TipoPonto.AVULSO:
        if not texto:
            raise PontoInvalido(f"Informe o rotulo da {lado} avulsa")
        if regiao_override_id is None:
            raise PontoInvalido(f"Informe a regiao da {lado} avulsa")
        return {"tipo": tipo, "id": None, "texto": texto, "detalhe": detalhe, "regiao_id": regiao_override_id}
    raise PontoInvalido(f"Tipo de ponto invalido: {tipo}")


def resolver_trecho(
    db: Session,
    usuario: Usuario,
    *,
    origem_tipo: TipoPonto | None,
    origem_id: int | None,
    origem_texto: str | None,
    origem_detalhe: str | None,
    regiao_origem_id: int | None,
    destino_tipo: TipoPonto,
    destino_id: int | None,
    destino_texto: str | None,
    destino_detalhe: str | None,
    regiao_destino_id: int | None,
    primeiro: bool,
) -> dict:
    """Resolve os dois lados (origem + destino) de um trecho.

    `origem_tipo` nulo so e valido quando `primeiro` e False -- significa
    "herda o destino do trecho anterior" (ver `regiao_alocacao_trecho` em
    `services/geracao.py`), unico caso em que um trecho fica sem origem
    propria.
    """
    if origem_tipo is None:
        if primeiro:
            raise PontoInvalido("Informe a origem do primeiro trecho")
        dados = {
            "origem_tipo": None,
            "origem_id": None,
            "origem_texto": None,
            "origem_detalhe": None,
            "regiao_origem_id": None,
        }
    else:
        ponto = resolver_ponto(db, origem_tipo, usuario, origem_id, origem_texto, origem_detalhe, regiao_origem_id, "origem")
        dados = {
            "origem_tipo": ponto["tipo"],
            "origem_id": ponto["id"],
            "origem_texto": ponto["texto"],
            "origem_detalhe": ponto["detalhe"],
            "regiao_origem_id": ponto["regiao_id"],
        }

    ponto_destino = resolver_ponto(
        db, destino_tipo, usuario, destino_id, destino_texto, destino_detalhe, regiao_destino_id, "destino"
    )
    dados.update(
        {
            "destino_tipo": ponto_destino["tipo"],
            "destino_id": ponto_destino["id"],
            "destino_texto": ponto_destino["texto"],
            "destino_detalhe": ponto_destino["detalhe"],
            "regiao_destino_id": ponto_destino["regiao_id"],
        }
    )
    return dados
