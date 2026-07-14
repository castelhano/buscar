"""Modo Base (molde por dia da semana): CRUD de `GrupoBase`/`ViagemBase`/
`MembroViagemBase` e leitura da estrutura completa pra tela -- sem nenhuma
restricao de regiao/capacidade (isso so entra em jogo na geracao real, ver
`app.services.geracao`).
"""
import datetime as dt

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import DiaSemana, GrupoBase, Local, MembroViagemBase, Sentido, UsuarioAgendaSemanal, ViagemBase
from app.services.geracao import agendas_fixo_da_semana, montar_pernas


def montar_estrutura_base(db: Session, dia_semana: DiaSemana) -> dict:
    """Le grupos/viagens/membros do dia da semana + calcula quem ainda nao
    esta classificado em nenhum grupo (agenda elegivel hoje sem
    `MembroViagemBase` nesse sentido).
    """
    agendas = agendas_fixo_da_semana(db, dia_semana)
    locais_regiao = dict(db.query(Local.id, Local.regiao_id).all())
    pernas_por_regiao = montar_pernas(agendas, {}, set(), locais_regiao)
    pernas_por_agenda_sentido = {
        (p["agenda_id"], p["sentido"]): p for pernas in pernas_por_regiao.values() for p in pernas
    }

    grupos_db = (
        db.query(GrupoBase)
        .options(joinedload(GrupoBase.viagens).joinedload(ViagemBase.membros))
        .filter(GrupoBase.dia_semana == dia_semana)
        .order_by(GrupoBase.ordem_exibicao, GrupoBase.id)
        .all()
    )

    def _serializar_perna(perna: dict) -> dict:
        return {
            "usuario_id": perna["usuario_id"],
            "usuario_nome": perna["usuario"].nome,
            "usuario_abbr": perna["usuario"].abbr,
            "origem": perna["origem"],
            "regiao_origem_id": perna["regiao_origem_id"],
            "destino_id": perna["destino_id"],
            "regiao_destino_id": perna["regiao_destino_id"],
            "acompanhante": perna["acompanhante"],
        }

    classificados: set[tuple[int, Sentido]] = set()
    grupos_saida = []
    for grupo in grupos_db:
        viagens_saida = []
        for viagem in sorted(grupo.viagens, key=lambda v: v.hora):
            membros_saida = []
            for membro in sorted(viagem.membros, key=lambda m: m.ordem):
                perna = pernas_por_agenda_sentido.get((membro.agenda_id, viagem.sentido))
                if perna is None:
                    continue  # agenda nao elegivel mais (removida/inativa) -- nao aparece
                classificados.add((membro.agenda_id, viagem.sentido))
                membros_saida.append(
                    {"id": membro.id, "agenda_id": membro.agenda_id, "ordem": membro.ordem, **_serializar_perna(perna)}
                )
            viagens_saida.append(
                {
                    "id": viagem.id,
                    "grupo_base_id": grupo.id,
                    "sentido": viagem.sentido,
                    "hora": viagem.hora,
                    "membros": membros_saida,
                }
            )
        grupos_saida.append(
            {
                "id": grupo.id,
                "dia_semana": grupo.dia_semana,
                "rotulo": grupo.rotulo,
                "ordem_exibicao": grupo.ordem_exibicao,
                "viagens": viagens_saida,
            }
        )

    nao_classificados = [
        {"agenda_id": perna["agenda_id"], "sentido": perna["sentido"], "hora": perna["hora"], **_serializar_perna(perna)}
        for chave, perna in pernas_por_agenda_sentido.items()
        if chave not in classificados
    ]
    nao_classificados.sort(key=lambda p: (p["hora"], p["usuario_nome"]))

    return {"grupos": grupos_saida, "nao_classificados": nao_classificados}


def criar_grupo(db: Session, dia_semana: DiaSemana) -> GrupoBase:
    maior_ordem = db.query(func.max(GrupoBase.ordem_exibicao)).filter(GrupoBase.dia_semana == dia_semana).scalar()
    grupo = GrupoBase(dia_semana=dia_semana, ordem_exibicao=(maior_ordem or 0) + 1)
    db.add(grupo)
    db.commit()
    db.refresh(grupo)
    return grupo


def remover_grupo(db: Session, grupo_id: int) -> None:
    grupo = db.get(GrupoBase, grupo_id)
    if grupo is None:
        raise ValueError("Grupo nao encontrado")
    db.delete(grupo)
    db.commit()


def criar_viagem(db: Session, grupo_id: int, sentido: Sentido, hora: dt.time) -> ViagemBase:
    grupo = db.get(GrupoBase, grupo_id)
    if grupo is None:
        raise ValueError("Grupo nao encontrado")
    existente = (
        db.query(ViagemBase)
        .filter(ViagemBase.grupo_base_id == grupo_id, ViagemBase.sentido == sentido, ViagemBase.hora == hora)
        .first()
    )
    if existente is not None:
        raise ValueError("Ja existe uma viagem nesse sentido/horario nesse carro")
    viagem = ViagemBase(grupo_base_id=grupo_id, sentido=sentido, hora=hora)
    db.add(viagem)
    db.commit()
    db.refresh(viagem)
    return viagem


def remover_viagem(db: Session, viagem_id: int) -> None:
    viagem = db.get(ViagemBase, viagem_id)
    if viagem is None:
        raise ValueError("Viagem nao encontrada")
    db.delete(viagem)
    db.commit()


def alterar_hora_viagem(db: Session, viagem_id: int, nova_hora: dt.time) -> DiaSemana:
    """Muda o horario de uma `ViagemBase` e propaga pra agenda semanal de
    cada membro (saida/retorno conforme o sentido) -- ao contrario de
    `mover_membro`, aqui e o horario que muda pra bater com o carro, nao o
    contrario.
    """
    viagem = db.get(ViagemBase, viagem_id)
    if viagem is None:
        raise ValueError("Viagem nao encontrada")
    dia_semana = viagem.grupo.dia_semana
    if viagem.hora == nova_hora:
        return dia_semana

    conflito = (
        db.query(ViagemBase)
        .filter(
            ViagemBase.grupo_base_id == viagem.grupo_base_id,
            ViagemBase.sentido == viagem.sentido,
            ViagemBase.hora == nova_hora,
            ViagemBase.id != viagem_id,
        )
        .first()
    )
    if conflito is not None:
        raise ValueError("Ja existe uma viagem nesse sentido/horario nesse carro")

    for membro in viagem.membros:
        if viagem.sentido == Sentido.IDA:
            membro.agenda.saida = nova_hora
        else:
            membro.agenda.retorno = nova_hora

    viagem.hora = nova_hora
    db.commit()
    return dia_semana


def _reindexar_viagem(db: Session, viagem_base_id: int) -> None:
    membros = (
        db.query(MembroViagemBase)
        .filter(MembroViagemBase.viagem_base_id == viagem_base_id)
        .order_by(MembroViagemBase.ordem, MembroViagemBase.id)
        .all()
    )
    for indice, membro in enumerate(membros, start=1):
        membro.ordem = indice


def remover_membro(db: Session, membro_id: int) -> None:
    membro = db.get(MembroViagemBase, membro_id)
    if membro is None:
        raise ValueError("Membro nao encontrado")
    viagem_base_id = membro.viagem_base_id
    db.delete(membro)
    db.flush()
    _reindexar_viagem(db, viagem_base_id)
    db.commit()


def mover_membro(
    db: Session,
    agenda_id: int,
    sentido: Sentido,
    grupo_base_id: int,
    hora: dt.time,
    ordem: int | None,
) -> DiaSemana:
    """Move (ou classifica pela primeira vez) a perna `sentido` da agenda pra
    dentro do carro `grupo_base_id`, no horario `hora` -- cria a viagem_base
    on-the-fly se ainda nao existir nesse carro. Sem nenhuma checagem de
    regiao/capacidade: e livre por construcao, so a geracao real decide se da
    pra materializar como carro de verdade. Devolve o `dia_semana` da agenda,
    pro chamador recarregar a estrutura certa.
    """
    agenda = db.get(UsuarioAgendaSemanal, agenda_id)
    if agenda is None:
        raise ValueError("Agenda nao encontrada")
    hora_agenda = agenda.saida if sentido == Sentido.IDA else agenda.retorno
    if hora_agenda is None:
        raise ValueError("Usuario nao tem esse sentido nesse dia da semana")
    if hora_agenda != hora:
        # o horario de um membro tem que bater com o horario real da agenda
        # dele -- Base so agrupa em carros, nao muda quando a pessoa e
        # atendida. Sem essa checagem, um drop solto em cima de uma viagem
        # de outro horario corromperia silenciosamente o horario "efetivo"
        # dessa pessoa na geracao (ela ficaria com hora real X dentro de uma
        # viagem_base rotulada com hora Y).
        raise ValueError(
            f"Horario informado ({hora}) nao bate com o horario real do usuario nesse sentido ({hora_agenda})"
        )
    dia_semana = agenda.dia_semana

    grupo = db.get(GrupoBase, grupo_base_id)
    if grupo is None or grupo.dia_semana != dia_semana:
        raise ValueError("Grupo nao encontrado para esse dia da semana")

    viagem_destino = (
        db.query(ViagemBase)
        .filter(ViagemBase.grupo_base_id == grupo_base_id, ViagemBase.sentido == sentido, ViagemBase.hora == hora)
        .first()
    )
    if viagem_destino is None:
        viagem_destino = ViagemBase(grupo_base_id=grupo_base_id, sentido=sentido, hora=hora)
        db.add(viagem_destino)
        db.flush()

    antigos = (
        db.query(MembroViagemBase)
        .join(ViagemBase, MembroViagemBase.viagem_base_id == ViagemBase.id)
        .filter(MembroViagemBase.agenda_id == agenda_id, ViagemBase.sentido == sentido)
        .all()
    )
    viagens_origem = {m.viagem_base_id for m in antigos if m.viagem_base_id != viagem_destino.id}
    for antigo in antigos:
        db.delete(antigo)
    db.flush()
    for viagem_origem_id in viagens_origem:
        _reindexar_viagem(db, viagem_origem_id)

    membro = MembroViagemBase(viagem_base_id=viagem_destino.id, agenda_id=agenda_id, ordem=0)
    db.add(membro)
    db.flush()

    membros = (
        db.query(MembroViagemBase)
        .filter(MembroViagemBase.viagem_base_id == viagem_destino.id)
        .order_by(MembroViagemBase.ordem, MembroViagemBase.id)
        .all()
    )
    membros_sem_novo = [m for m in membros if m.id != membro.id]
    posicao = len(membros_sem_novo) if ordem is None else max(0, min(ordem, len(membros_sem_novo)))
    membros_sem_novo.insert(posicao, membro)
    for indice, m in enumerate(membros_sem_novo, start=1):
        m.ordem = indice

    db.commit()
    return dia_semana
