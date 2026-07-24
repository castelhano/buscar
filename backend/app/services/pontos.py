"""Resolucao de "pontos" (origem/destino de um trecho) a partir do tipo
escolhido -- ver `app.models.TipoPonto`. Compartilhado entre a config
recorrente (Agenda Semanal/Excecao, `routers/usuarios.py`) e o trecho
materializado do dia (`routers/viagens.py`): os dois preenchem os mesmos
campos (`*_tipo`, `*_id`, `*_texto`, `*_detalhe`, `regiao_*_id`) a partir da
mesma escolha de tipo, derivando regiao/rotulo/endereco automaticamente
sempre que possivel (so o tipo Avulso exige informar a regiao na mao, ja que
nao ha Local nem Usuario de onde deriva-la).
"""

import datetime as dt

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import Local, TipoPonto, Usuario, ViagemDia, ViagemDiaPassageiro


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


def mapa_destinos_do_dia(db: Session, data: dt.date) -> dict[tuple[int, int], dict]:
    """(usuario_id, ordem_trecho) -> campos brutos do destino de TODO
    passageiro do dia (qualquer carro, ou orfao sem vaga) -- usado por
    `resolver_origem_herdada` pra achar o destino do trecho ANTERIOR do mesmo
    usuario, que pode estar num carro/condutor diferente do trecho que esta
    herdando. Inclui cancelados: o registro nao foi apagado, so teve o status
    mudado, e o dado de destino continua valido pra exibir de onde o
    passageiro estava vindo.
    """
    linhas = (
        db.query(ViagemDiaPassageiro)
        .outerjoin(ViagemDia, ViagemDiaPassageiro.viagem_dia_id == ViagemDia.id)
        .filter(
            or_(
                ViagemDia.data == data,
                and_(ViagemDiaPassageiro.viagem_dia_id.is_(None), ViagemDiaPassageiro.data == data),
            )
        )
        .all()
    )
    mapa: dict[tuple[int, int], dict] = {}
    for p in linhas:
        mapa[(p.usuario_id, p.ordem_trecho)] = {
            "origem_tipo": p.destino_tipo,
            "origem_id": p.destino_id,
            "origem_texto": p.destino_texto,
            "origem_detalhe": p.destino_detalhe,
            "regiao_origem_id": p.regiao_destino_id,
        }
    return mapa


def resolver_origem_herdada(passageiro: ViagemDiaPassageiro, mapa_destinos: dict[tuple[int, int], dict]) -> dict | None:
    """Se `origem_tipo` for None ("herda o destino do trecho anterior", ver
    `resolver_trecho`), devolve os campos de origem ja resolvidos a partir do
    destino do trecho anterior do mesmo usuario nesse dia; None quando nao ha
    origem propria (`origem_tipo` preenchido) ou nao ha o que herdar.
    """
    if passageiro.origem_tipo is not None:
        return None
    return mapa_destinos.get((passageiro.usuario_id, passageiro.ordem_trecho - 1))
