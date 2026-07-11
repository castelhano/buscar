import datetime as dt
from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Condutor,
    CondutorFerias,
    Empresa,
    Local,
    PeriodoCondutor,
    Sentido,
    StatusAtendimentoDia,
    StatusAtivoInativo,
    StatusCondutor,
    StatusVeiculo,
    StatusViagemDia,
    TipoAtendimento,
    Usuario,
    UsuarioAgendaSemanal,
    UsuarioExcecao,
    Veiculo,
    ViagemDia,
    ViagemDiaPassageiro,
    empresa_regiao,
)
from app.services.dia import dia_semana_from_date
from app.services.recursos import fim_viagem, janelas_sobrepoem

TEMPO_SAIDA_GARAGEM_MINUTOS = 60
CORTE_PERIODO_TARDE = dt.time(14, 0)


def _periodo_da_hora(hora: dt.time) -> PeriodoCondutor:
    """Ate 13:59 e Manha, a partir de 14:00 e Tarde."""
    return PeriodoCondutor.TARDE if hora >= CORTE_PERIODO_TARDE else PeriodoCondutor.MANHA


def _periodo_da_viagem(viagem: ViagemDia) -> PeriodoCondutor:
    horas = [p.hora for p in viagem.passageiros if p.status != StatusAtendimentoDia.CANCELADO]
    hora_referencia = min(horas) if horas else viagem.horario_saida
    return _periodo_da_hora(hora_referencia)


def gerar_agendamento_dia(db: Session, data: dt.date) -> list[ViagemDia]:
    """Gera as ViagemDia + ViagemDiaPassageiro de uma data a partir da agenda semanal.

    Idempotente: se ja existir ViagemDia para a data, retorna o que ja foi
    gerado em vez de duplicar (a tela de agendamento so mostra "Gerar" quando
    ainda nao existe nada para a data).

    Agrupa os usuarios Fixo por regiao de origem (ordenados por `ordem`, curado
    manualmente para manter juntos quem mora perto) e abre carros por
    regiao/sentido/horario ate a frota disponivel se esgotar; o que sobra fica
    de fora para alocacao manual na tela de escala do dia.
    """
    existentes = db.query(ViagemDia).filter(ViagemDia.data == data).all()
    if existentes:
        return existentes

    dia_semana = dia_semana_from_date(data)

    agendas = (
        db.query(UsuarioAgendaSemanal)
        .join(Usuario, UsuarioAgendaSemanal.usuario_id == Usuario.id)
        .filter(
            UsuarioAgendaSemanal.dia_semana == dia_semana,
            UsuarioAgendaSemanal.tipo == TipoAtendimento.FIXO,
            UsuarioAgendaSemanal.ativo.is_(True),
            Usuario.status == StatusAtivoInativo.ATIVO,
        )
        .order_by(UsuarioAgendaSemanal.ordem)
        .all()
    )
    print(f"[geracao] {data} ({dia_semana.name}): {len(agendas)} agendas FIXO/ativas encontradas")
    usuario_ids = [a.usuario_id for a in agendas]
    excecoes = {
        e.usuario_id: e
        for e in db.query(UsuarioExcecao).filter(
            UsuarioExcecao.data == data, UsuarioExcecao.usuario_id.in_(usuario_ids)
        )
    }
    locais_regiao = dict(db.query(Local.id, Local.regiao_id).all())

    pernas_por_regiao: dict[int, list[dict]] = defaultdict(list)
    for agenda in agendas:
        excecao = excecoes.get(agenda.usuario_id)
        if excecao and excecao.suspenso:
            continue

        origem = excecao.origem if excecao and excecao.origem else agenda.origem
        regiao_origem_id = (
            excecao.regiao_origem_id if excecao and excecao.regiao_origem_id else agenda.regiao_origem_id
        )
        destino_id = excecao.destino_id if excecao and excecao.destino_id else agenda.destino_id
        regiao_destino_id = locais_regiao.get(destino_id) if destino_id else None

        if regiao_origem_id is None:
            print(f"[geracao] usuario_id={agenda.usuario_id}: sem regiao_origem_id, ficou de fora")
            continue  # sem regiao de origem cadastrada -- fica de fora para alocacao manual

        pernas = (
            (Sentido.IDA, agenda.saida, excecao.saida if excecao else None),
            (Sentido.RETORNO, agenda.retorno, excecao.retorno if excecao else None),
        )
        for sentido, hora_padrao, hora_excecao in pernas:
            hora = hora_excecao or hora_padrao
            if hora is None:
                continue
            pernas_por_regiao[regiao_origem_id].append(
                {
                    "usuario_id": agenda.usuario_id,
                    "ordem": agenda.ordem,
                    "sentido": sentido,
                    "hora": hora,
                    "origem": origem,
                    "regiao_origem_id": regiao_origem_id,
                    "destino_id": destino_id,
                    "regiao_destino_id": regiao_destino_id,
                    "acompanhante": agenda.acompanhante,
                }
            )

    print(f"[geracao] pernas por regiao: { {k: len(v) for k, v in pernas_por_regiao.items()} }")

    todas_viagens: list[ViagemDia] = []
    janelas: dict[int, tuple[dt.time, dt.time]] = {}
    avisos_emitidos: set[tuple] = set()
    for regiao_id, pernas in pernas_por_regiao.items():
        pernas.sort(key=lambda p: (p["sentido"].value, p["hora"], p["ordem"]))
        _preencher_regiao(db, regiao_id, pernas, data, todas_viagens, janelas, avisos_emitidos)

    db.flush()
    _atribuir_condutores(db, todas_viagens, data)
    db.commit()
    for viagem in todas_viagens:
        db.refresh(viagem)
    print(f"[geracao] {len(todas_viagens)} viagens geradas")
    return todas_viagens


def _preencher_regiao(
    db: Session,
    regiao_id: int,
    pernas: list[dict],
    data: dt.date,
    todas_viagens: list[ViagemDia],
    janelas: dict[int, tuple[dt.time, dt.time]],
    avisos_emitidos: set[tuple],
) -> None:
    """Preenche os carros de uma regiao, na ordem de `ordem`, abrindo um novo
    carro (leg) sempre que o sentido/horario atual estoura a capacidade dos
    carros ja abertos para esse mesmo sentido/horario.

    Um usuario com acompanhante ocupa 2 lugares no veiculo em vez de 1.
    """
    ocupacao: dict[tuple[int, Sentido, dt.time], int] = defaultdict(int)
    abertos_por_perna: dict[tuple[Sentido, dt.time], list[ViagemDia]] = defaultdict(list)

    for perna in pernas:
        perna_chave = (perna["sentido"], perna["hora"])
        lugares = 2 if perna["acompanhante"] else 1
        viagem = next(
            (
                v
                for v in abertos_por_perna[perna_chave]
                if ocupacao[(v.id, *perna_chave)] + lugares <= v.capacidade
            ),
            None,
        )
        if viagem is None:
            viagem = _abrir_carro(db, regiao_id, perna["hora"], data, todas_viagens, janelas, avisos_emitidos)
            if viagem is None:
                continue  # sem veiculo disponivel na regiao/horario -- fica de fora para alocacao manual
            abertos_por_perna[perna_chave].append(viagem)
            todas_viagens.append(viagem)

        db.add(
            ViagemDiaPassageiro(
                viagem_dia_id=viagem.id,
                usuario_id=perna["usuario_id"],
                sentido=perna["sentido"],
                hora=perna["hora"],
                origem=perna["origem"],
                regiao_origem_id=perna["regiao_origem_id"],
                destino_id=perna["destino_id"],
                regiao_destino_id=perna["regiao_destino_id"],
                acompanhante=perna["acompanhante"],
            )
        )
        ocupacao[(viagem.id, *perna_chave)] += lugares


def _horario_garagem(hora: dt.time) -> dt.time:
    referencia = dt.datetime.combine(dt.date.today(), hora) - dt.timedelta(minutes=TEMPO_SAIDA_GARAGEM_MINUTOS)
    return referencia.time()


def _empresas_da_regiao(db: Session, regiao_id: int) -> list[int]:
    return [
        row[0]
        for row in db.query(Empresa.id)
        .join(empresa_regiao, Empresa.id == empresa_regiao.c.empresa_id)
        .filter(empresa_regiao.c.regiao_id == regiao_id)
        .all()
    ]


def _abrir_carro(
    db: Session,
    regiao_id: int,
    hora: dt.time,
    data: dt.date,
    todas_viagens: list[ViagemDia],
    janelas: dict[int, tuple[dt.time, dt.time]],
    avisos_emitidos: set[tuple],
) -> ViagemDia | None:
    empresa_ids = _empresas_da_regiao(db, regiao_id)
    if not empresa_ids:
        chave_aviso = ("sem_empresa", regiao_id)
        if chave_aviso not in avisos_emitidos:
            avisos_emitidos.add(chave_aviso)
            print(f"[geracao] regiao_id={regiao_id}: nenhuma empresa vinculada (empresa_regiao vazio pra essa regiao)")
        return None

    horario_saida = _horario_garagem(hora)
    veiculo = _proximo_veiculo_livre(db, empresa_ids, todas_viagens, janelas, data, horario_saida, hora)
    if veiculo is None:
        chave_aviso = ("sem_veiculo", regiao_id, hora)
        if chave_aviso not in avisos_emitidos:
            avisos_emitidos.add(chave_aviso)
            print(
                f"[geracao] regiao_id={regiao_id} hora={hora}: empresas {empresa_ids} sem veiculo ativo/livre nesse horario"
            )
        return None  # sem veiculo disponivel na regiao/horario para abrir novo carro

    viagem = ViagemDia(
        data=data,
        regiao_id=regiao_id,
        empresa_id=veiculo.empresa_id,
        veiculo_id=veiculo.id,
        horario_saida=horario_saida,
        capacidade=veiculo.capacidade,
        status=StatusViagemDia.PLANEJADA,
    )
    db.add(viagem)
    db.flush()
    janelas[viagem.id] = (horario_saida, hora)
    return viagem


def _proximo_veiculo_livre(
    db: Session,
    empresa_ids: list[int],
    todas_viagens: list[ViagemDia],
    janelas: dict[int, tuple[dt.time, dt.time]],
    data: dt.date,
    inicio: dt.time,
    fim: dt.time,
) -> Veiculo | None:
    """Escolhe o proximo veiculo (rodizio) livre para o intervalo [inicio, fim].

    Um veiculo ja usado hoje em outro carro continua elegivel desde que os
    intervalos nao se sobreponham -- e assim que o mesmo carro/condutor acaba
    fazendo mais de uma viagem no dia (ex: 06h00 e depois 07h00).
    """
    candidatos = (
        db.query(Veiculo)
        .filter(Veiculo.empresa_id.in_(empresa_ids), Veiculo.status == StatusVeiculo.ATIVO)
        .all()
    )

    def livre(veiculo_id: int) -> bool:
        for outra in todas_viagens:
            if outra.veiculo_id != veiculo_id:
                continue
            janela = janelas.get(outra.id)
            if janela and janelas_sobrepoem(inicio, fim, janela[0], janela[1]):
                return False
        return True

    disponiveis = [v for v in candidatos if livre(v.id)]
    if not disponiveis:
        return None
    disponiveis.sort(key=lambda v: _ultimo_uso(db, ViagemDia.veiculo_id, v.id, data))
    return disponiveis[0]


def _atribuir_condutores(db: Session, viagens: list[ViagemDia], data: dt.date) -> None:
    """Atribui condutor a cada viagem, priorizando quem foi usado ha mais tempo
    (rodizio entre dias), mas permitindo reaproveitar o mesmo condutor em
    carros do mesmo dia que nao se sobrepoem (ex: o mesmo condutor faz a
    viagem das 06h00 e depois a das 07h00). So considera condutores do mesmo
    periodo da viagem (`Condutor.periodo`, corte as 14h00) -- um condutor de
    Manha nunca e escalado numa viagem de Tarde e vice-versa.
    """
    em_ferias = {
        f.condutor_id
        for f in db.query(CondutorFerias).filter(
            CondutorFerias.data_inicio <= data, CondutorFerias.data_fim >= data
        )
    }

    for viagem in viagens:
        empresa_ids = _empresas_da_regiao(db, viagem.regiao_id)
        if not empresa_ids:
            continue

        condutor = _proximo_condutor_livre(db, empresa_ids, em_ferias, viagens, data, viagem)
        if condutor is not None:
            viagem.condutor_id = condutor.id


def _proximo_condutor_livre(
    db: Session,
    empresa_ids: list[int],
    em_ferias: set[int],
    viagens: list[ViagemDia],
    data: dt.date,
    viagem: ViagemDia,
) -> Condutor | None:
    periodo = _periodo_da_viagem(viagem)
    candidatos = (
        db.query(Condutor)
        .filter(
            Condutor.empresa_id.in_(empresa_ids),
            Condutor.status == StatusCondutor.ATIVO,
            Condutor.periodo == periodo,
        )
        .all()
    )
    candidatos = [c for c in candidatos if c.id not in em_ferias]
    if not candidatos:
        print(f"[geracao] viagem_id={viagem.id} regiao_id={viagem.regiao_id} periodo={periodo.value}: sem condutor {periodo.value} disponivel")
        return None

    inicio = viagem.horario_saida
    fim = fim_viagem(viagem)

    def livre(condutor_id: int) -> bool:
        for outra in viagens:
            if outra.id == viagem.id or outra.condutor_id != condutor_id:
                continue
            if janelas_sobrepoem(inicio, fim, outra.horario_saida, fim_viagem(outra)):
                return False
        return True

    def mesmo_veiculo_do_dia(condutor_id: int) -> bool:
        """Um condutor so opera um unico veiculo por dia: se ja foi escalado
        noutra viagem hoje, essa viagem precisa ser do mesmo veiculo."""
        for outra in viagens:
            if outra.id == viagem.id or outra.condutor_id != condutor_id:
                continue
            if outra.veiculo_id != viagem.veiculo_id:
                return False
        return True

    disponiveis = [c for c in candidatos if livre(c.id) and mesmo_veiculo_do_dia(c.id)]
    if not disponiveis:
        print(
            f"[geracao] viagem_id={viagem.id} regiao_id={viagem.regiao_id} veiculo_id={viagem.veiculo_id}: "
            "nenhum condutor livre com o mesmo veiculo do dia"
        )
        return None

    if viagem.veiculo_id is not None:
        preferenciais = [c for c in disponiveis if c.veiculo_preferencial_id == viagem.veiculo_id]
        if preferenciais:
            return preferenciais[0]

    disponiveis.sort(key=lambda c: _ultimo_uso(db, ViagemDia.condutor_id, c.id, data))
    return disponiveis[0]


def _ultimo_uso(db: Session, coluna, entidade_id: int, antes_de: dt.date) -> dt.date:
    ultimo = (
        db.query(func.max(ViagemDia.data))
        .filter(coluna == entidade_id, ViagemDia.data < antes_de)
        .scalar()
    )
    return ultimo or dt.date.min
