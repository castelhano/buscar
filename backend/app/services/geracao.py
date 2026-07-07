import datetime as dt
from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    AgendamentoBase,
    Condutor,
    CondutorFerias,
    Empresa,
    Local,
    Sentido,
    StatusAtivoInativo,
    StatusCondutor,
    StatusVeiculo,
    StatusViagemDia,
    TipoAtendimento,
    Usuario,
    UsuarioAgendaSemanal,
    UsuarioAgendamentoBase,
    UsuarioExcecao,
    Veiculo,
    ViagemDia,
    ViagemDiaPassageiro,
    empresa_regiao,
)
from app.services.dia import dia_semana_from_date, dia_tipo_from_date


def gerar_agendamento_dia(db: Session, data: dt.date) -> list[ViagemDia]:
    """Gera as ViagemDia + ViagemDiaPassageiro de uma data a partir do AgendamentoBase.

    Idempotente: se ja existir ViagemDia para a data, retorna o que ja foi
    gerado em vez de duplicar (a tela de agendamento so mostra "Gerar" quando
    ainda nao existe nada para a data).
    """
    existentes = db.query(ViagemDia).filter(ViagemDia.data == data).all()
    if existentes:
        return existentes

    dia_tipo = dia_tipo_from_date(data)
    dia_semana = dia_semana_from_date(data)

    viagem_por_base: dict[int, ViagemDia] = {}
    viagens_por_regiao: dict[int, list[ViagemDia]] = defaultdict(list)
    for base in db.query(AgendamentoBase).filter(AgendamentoBase.dia_tipo == dia_tipo).all():
        viagem = ViagemDia(
            data=data,
            agendamento_base_id=base.id,
            regiao_id=base.regiao_id,
            horario_saida=base.inicio,
            capacidade=base.capacidade,
            status=StatusViagemDia.PLANEJADA,
        )
        db.add(viagem)
        viagem_por_base[base.id] = viagem
    db.flush()
    for viagem in viagem_por_base.values():
        viagens_por_regiao[viagem.regiao_id].append(viagem)

    vinculo_por_usuario: dict[int, UsuarioAgendamentoBase] = {
        v.usuario_id: v
        for v in (
            db.query(UsuarioAgendamentoBase)
            .join(AgendamentoBase, UsuarioAgendamentoBase.agendamento_base_id == AgendamentoBase.id)
            .filter(AgendamentoBase.dia_tipo == dia_tipo)
            .all()
        )
    }
    excecoes = {e.usuario_id: e for e in db.query(UsuarioExcecao).filter(UsuarioExcecao.data == data).all()}
    locais_regiao = dict(db.query(Local.id, Local.regiao_id).all())

    agendas = (
        db.query(UsuarioAgendaSemanal)
        .join(Usuario, UsuarioAgendaSemanal.usuario_id == Usuario.id)
        .filter(
            UsuarioAgendaSemanal.dia_semana == dia_semana,
            UsuarioAgendaSemanal.tipo == TipoAtendimento.FIXO,
            UsuarioAgendaSemanal.ativo.is_(True),
            Usuario.status == StatusAtivoInativo.ATIVO,
        )
        .all()
    )

    ocupacao: dict[tuple[int, Sentido], int] = defaultdict(int)

    for agenda in agendas:
        excecao = excecoes.get(agenda.usuario_id)
        if excecao and excecao.suspenso:
            continue

        origem = (excecao.origem if excecao and excecao.origem else agenda.origem)
        regiao_origem_id = (
            excecao.regiao_origem_id if excecao and excecao.regiao_origem_id else agenda.regiao_origem_id
        )
        destino_id = excecao.destino_id if excecao and excecao.destino_id else agenda.destino_id
        regiao_destino_id = locais_regiao.get(destino_id) if destino_id else None

        pernas = (
            (Sentido.IDA, agenda.saida, excecao.saida if excecao else None),
            (Sentido.RETORNO, agenda.retorno, excecao.retorno if excecao else None),
        )
        for sentido, hora_padrao, hora_excecao in pernas:
            hora = hora_excecao or hora_padrao
            if hora is None:
                continue

            viagem = _escolher_viagem(
                db,
                viagem_por_base,
                viagens_por_regiao,
                ocupacao,
                vinculo_por_usuario.get(agenda.usuario_id),
                regiao_origem_id,
                sentido,
                data,
            )
            if viagem is None:
                continue  # sem carro/veiculo disponivel na regiao -- fica de fora para alocacao manual

            db.add(
                ViagemDiaPassageiro(
                    viagem_dia_id=viagem.id,
                    usuario_id=agenda.usuario_id,
                    sentido=sentido,
                    hora=hora,
                    origem=origem,
                    regiao_origem_id=regiao_origem_id,
                    destino_id=destino_id,
                    regiao_destino_id=regiao_destino_id,
                )
            )
            ocupacao[(viagem.id, sentido)] += 1

    db.flush()
    todas_viagens = [v for lista in viagens_por_regiao.values() for v in lista]
    _revesar_condutores_veiculos(db, todas_viagens, data)
    db.commit()
    for viagem in todas_viagens:
        db.refresh(viagem)
    return todas_viagens


def _tem_capacidade(viagem: ViagemDia, sentido: Sentido, ocupacao: dict) -> bool:
    return ocupacao[(viagem.id, sentido)] < viagem.capacidade


def _escolher_viagem(
    db: Session,
    viagem_por_base: dict[int, ViagemDia],
    viagens_por_regiao: dict[int, list[ViagemDia]],
    ocupacao: dict,
    vinculo: UsuarioAgendamentoBase | None,
    regiao_origem_id: int | None,
    sentido: Sentido,
    data: dt.date,
) -> ViagemDia | None:
    if vinculo is not None:
        designada = viagem_por_base.get(vinculo.agendamento_base_id)
        if designada is not None and _tem_capacidade(designada, sentido, ocupacao):
            return designada

    if regiao_origem_id is None:
        return None

    for viagem in viagens_por_regiao.get(regiao_origem_id, []):
        if _tem_capacidade(viagem, sentido, ocupacao):
            return viagem

    return _abrir_carro_extra(db, viagens_por_regiao, regiao_origem_id, data)


def _abrir_carro_extra(
    db: Session, viagens_por_regiao: dict[int, list[ViagemDia]], regiao_id: int, data: dt.date
) -> ViagemDia | None:
    ja_abertos = len(viagens_por_regiao.get(regiao_id, []))
    if ja_abertos >= _capacidade_frota_regiao(db, regiao_id):
        return None  # sem veiculo disponivel na regiao para abrir novo carro

    referencia = next(iter(viagens_por_regiao.get(regiao_id, [])), None)
    viagem = ViagemDia(
        data=data,
        agendamento_base_id=None,
        regiao_id=regiao_id,
        horario_saida=referencia.horario_saida if referencia else dt.time(6, 0),
        capacidade=referencia.capacidade if referencia else 4,
        status=StatusViagemDia.PLANEJADA,
        observacoes="Carro extra aberto automaticamente na geracao",
    )
    db.add(viagem)
    db.flush()
    viagens_por_regiao[regiao_id].append(viagem)
    return viagem


def _capacidade_frota_regiao(db: Session, regiao_id: int) -> int:
    empresa_ids = [
        row[0]
        for row in db.query(Empresa.id)
        .join(empresa_regiao, Empresa.id == empresa_regiao.c.empresa_id)
        .filter(empresa_regiao.c.regiao_id == regiao_id)
        .all()
    ]
    if not empresa_ids:
        return 0
    return (
        db.query(Veiculo)
        .filter(Veiculo.empresa_id.in_(empresa_ids), Veiculo.status == StatusVeiculo.ATIVO)
        .count()
    )


def _revesar_condutores_veiculos(db: Session, viagens: list[ViagemDia], data: dt.date) -> None:
    """Atribui condutor/veiculo a cada viagem, priorizando quem foi usado ha mais tempo.

    Isso distribui o uso entre a frota/condutores da regiao (rodizio) em vez de
    sempre escalar os mesmos primeiros cadastrados.
    """
    usados_condutor: set[int] = set()
    usados_veiculo: set[int] = set()
    em_ferias = {
        f.condutor_id
        for f in db.query(CondutorFerias).filter(
            CondutorFerias.data_inicio <= data, CondutorFerias.data_fim >= data
        )
    }

    for viagem in viagens:
        empresa_ids = [
            row[0]
            for row in db.query(Empresa.id)
            .join(empresa_regiao, Empresa.id == empresa_regiao.c.empresa_id)
            .filter(empresa_regiao.c.regiao_id == viagem.regiao_id)
            .all()
        ]
        if not empresa_ids:
            continue

        veiculo = _proximo_veiculo(db, empresa_ids, usados_veiculo, data)
        if veiculo is not None:
            viagem.veiculo_id = veiculo.id
            viagem.empresa_id = veiculo.empresa_id
            usados_veiculo.add(veiculo.id)

        condutor = _proximo_condutor(db, empresa_ids, usados_condutor, em_ferias, data, veiculo)
        if condutor is not None:
            viagem.condutor_id = condutor.id
            usados_condutor.add(condutor.id)


def _proximo_veiculo(db: Session, empresa_ids: list[int], usados: set[int], data: dt.date) -> Veiculo | None:
    candidatos = (
        db.query(Veiculo)
        .filter(Veiculo.empresa_id.in_(empresa_ids), Veiculo.status == StatusVeiculo.ATIVO)
        .all()
    )
    candidatos = [v for v in candidatos if v.id not in usados]
    if not candidatos:
        return None
    candidatos.sort(key=lambda v: _ultimo_uso(db, ViagemDia.veiculo_id, v.id, data))
    return candidatos[0]


def _proximo_condutor(
    db: Session,
    empresa_ids: list[int],
    usados: set[int],
    em_ferias: set[int],
    data: dt.date,
    veiculo: Veiculo | None,
) -> Condutor | None:
    candidatos = (
        db.query(Condutor)
        .filter(Condutor.empresa_id.in_(empresa_ids), Condutor.status == StatusCondutor.ATIVO)
        .all()
    )
    candidatos = [c for c in candidatos if c.id not in usados and c.id not in em_ferias]
    if not candidatos:
        return None
    if veiculo is not None:
        preferenciais = [c for c in candidatos if c.veiculo_preferencial_id == veiculo.id]
        if preferenciais:
            return preferenciais[0]
    candidatos.sort(key=lambda c: _ultimo_uso(db, ViagemDia.condutor_id, c.id, data))
    return candidatos[0]


def _ultimo_uso(db: Session, coluna, entidade_id: int, antes_de: dt.date) -> dt.date:
    ultimo = (
        db.query(func.max(ViagemDia.data))
        .filter(coluna == entidade_id, ViagemDia.data < antes_de)
        .scalar()
    )
    return ultimo or dt.date.min
