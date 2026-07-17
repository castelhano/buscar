import datetime as dt
from collections import defaultdict
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import obter_conta_atual
from app.database import get_db
from app.services.exportacao import (
    gerar_pdf_agendamento_bloco,
    gerar_pdf_agendamento_condutor,
    gerar_pdf_resumo_dia,
    gerar_png_agendamento_bloco,
    gerar_png_agendamento_condutor,
    gerar_zip_agendamentos,
    gerar_zip_agendamentos_png,
    nome_arquivo_seguro,
)
from app.services.frequencia import INTERVALO_PADRAO_POR_PERIODO
from app.services.geracao import _periodo_da_viagem, gerar_agendamento_dia, horario_garagem, listar_desconsiderados_dia
from app.services.recursos import fim_viagem, janelas_sobrepoem

router = APIRouter(prefix="/viagens", tags=["viagens"], dependencies=[Depends(obter_conta_atual)])


def _get_viagem_ou_404(db: Session, viagem_id: int) -> models.ViagemDia:
    viagem = db.get(models.ViagemDia, viagem_id)
    if viagem is None:
        raise HTTPException(status_code=404, detail=f"ViagemDia {viagem_id} nao encontrada")
    return viagem


def _get_passageiro_ou_404(db: Session, passageiro_id: int) -> models.ViagemDiaPassageiro:
    passageiro = db.get(models.ViagemDiaPassageiro, passageiro_id)
    if passageiro is None:
        raise HTTPException(status_code=404, detail=f"Passageiro {passageiro_id} nao encontrado")
    return passageiro


def _verificar_dia_destravado(db: Session, data: dt.date) -> None:
    """Bloqueia mutacoes num dia travado (ver /travar) -- protege contra
    edicao nao intencional depois que o agendamento do dia foi fechado.
    """
    if db.get(models.DiaTravado, data) is not None:
        raise HTTPException(status_code=409, detail="Dia travado: destrave para editar o agendamento")


def _verificar_viagem_destravada(db: Session, viagem: models.ViagemDia) -> None:
    _verificar_dia_destravado(db, viagem.data)


def _verificar_passageiro_destravado(db: Session, passageiro: models.ViagemDiaPassageiro) -> None:
    if passageiro.viagem_dia_id is not None:
        viagem = _get_viagem_ou_404(db, passageiro.viagem_dia_id)
        _verificar_dia_destravado(db, viagem.data)
    elif passageiro.data is not None:
        _verificar_dia_destravado(db, passageiro.data)


def _verificar_conflito(
    db: Session, viagem_dia_id: int, usuario_id: int, sentido: models.Sentido, excluir_passageiro_id: int | None = None
) -> None:
    query = db.query(models.ViagemDiaPassageiro).filter(
        models.ViagemDiaPassageiro.viagem_dia_id == viagem_dia_id,
        models.ViagemDiaPassageiro.usuario_id == usuario_id,
        models.ViagemDiaPassageiro.sentido == sentido,
    )
    if excluir_passageiro_id is not None:
        query = query.filter(models.ViagemDiaPassageiro.id != excluir_passageiro_id)
    if query.first() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Usuario ja possui um atendimento de {sentido.value} nesse carro",
        )


@dataclass
class _ContextoDia:
    """Lookups pre-carregados pra serializar as viagens de um dia sem
    disparar uma query por viagem/passageiro (evita N+1 em /viagens e /gerar).
    """

    regioes_habilitadas: set[tuple[int, int]]
    nomes_regiao: dict[int, str]
    condutores_em_ferias: set[int]
    intervalos_condutor: dict[int, tuple[dt.time, dt.time] | None]
    conflitos_condutor: dict[int, models.ViagemDia]
    conflitos_veiculo: dict[int, models.ViagemDia]


def _mapa_conflitos(viagens: list[models.ViagemDia], campo: str) -> dict[int, models.ViagemDia]:
    """Pra cada viagem, acha a primeira outra viagem do mesmo dia usando o
    mesmo condutor/veiculo em horario sobreposto -- calculado em memoria sobre
    a lista do dia ja carregada, sem uma query por viagem.

    Duas viagens do mesmo carro/condutor no mesmo dia sao normais (dois turnos)
    desde que uma termine (ultimo atendimento) antes da outra comecar (horario
    de saida) -- so sinaliza quando os intervalos se sobrepoem.
    """
    por_recurso: dict[int, list[models.ViagemDia]] = defaultdict(list)
    for v in viagens:
        recurso_id = getattr(v, campo)
        if recurso_id is not None:
            por_recurso[recurso_id].append(v)

    resultado: dict[int, models.ViagemDia] = {}
    for grupo in por_recurso.values():
        for v in grupo:
            fim_v = fim_viagem(v)
            for outra in grupo:
                if outra.id == v.id or outra.status == models.StatusViagemDia.CANCELADA:
                    continue
                if janelas_sobrepoem(v.horario_saida, fim_v, outra.horario_saida, fim_viagem(outra)):
                    resultado[v.id] = outra
                    break
    return resultado


def _intervalos_dos_condutores(
    db: Session, condutor_ids: set[int], data: dt.date
) -> dict[int, tuple[dt.time, dt.time] | None]:
    if not condutor_ids:
        return {}
    frequencias = {
        f.condutor_id: f
        for f in db.query(models.Frequencia).filter(
            models.Frequencia.condutor_id.in_(condutor_ids), models.Frequencia.data == data
        )
    }
    condutores = {c.id: c for c in db.query(models.Condutor).filter(models.Condutor.id.in_(condutor_ids))}
    resultado: dict[int, tuple[dt.time, dt.time] | None] = {}
    for condutor_id in condutor_ids:
        freq = frequencias.get(condutor_id)
        if freq is not None and freq.intervalo_inicio is not None and freq.intervalo_fim is not None:
            resultado[condutor_id] = (freq.intervalo_inicio, freq.intervalo_fim)
            continue
        condutor = condutores.get(condutor_id)
        resultado[condutor_id] = INTERVALO_PADRAO_POR_PERIODO.get(condutor.periodo) if condutor else None
    return resultado


def _construir_contexto_dia(
    db: Session, data: dt.date, viagens_do_dia: list[models.ViagemDia] | None = None
) -> _ContextoDia:
    if viagens_do_dia is None:
        viagens_do_dia = _query_viagens(db, data)

    regioes_habilitadas = {
        (empresa_id, regiao_id)
        for empresa_id, regiao_id in db.query(
            models.empresa_regiao.c.empresa_id, models.empresa_regiao.c.regiao_id
        ).all()
    }
    nomes_regiao = dict(db.query(models.Regiao.id, models.Regiao.nome).all())
    condutores_em_ferias = {
        f.condutor_id
        for f in db.query(models.CondutorFerias).filter(
            models.CondutorFerias.data_inicio <= data, models.CondutorFerias.data_fim >= data
        )
    }
    condutor_ids = {v.condutor_id for v in viagens_do_dia if v.condutor_id is not None}

    return _ContextoDia(
        regioes_habilitadas=regioes_habilitadas,
        nomes_regiao=nomes_regiao,
        condutores_em_ferias=condutores_em_ferias,
        intervalos_condutor=_intervalos_dos_condutores(db, condutor_ids, data),
        conflitos_condutor=_mapa_conflitos(viagens_do_dia, "condutor_id"),
        conflitos_veiculo=_mapa_conflitos(viagens_do_dia, "veiculo_id"),
    )


def _calcular_irregularidade(empresa_id: int | None, regiao_origem_id: int | None, contexto: _ContextoDia):
    if empresa_id is None or regiao_origem_id is None:
        return False, None
    if (empresa_id, regiao_origem_id) in contexto.regioes_habilitadas:
        return False, None
    nome_regiao = contexto.nomes_regiao.get(regiao_origem_id, str(regiao_origem_id))
    return True, f"Empresa da viagem nao esta habilitada para a regiao {nome_regiao} do usuario"


def _serializar_viagem(viagem: models.ViagemDia, contexto: _ContextoDia) -> schemas.ViagemDiaRead:
    base = schemas.ViagemDiaRead.model_validate(viagem)
    passageiros = []
    for passageiro, passageiro_read in zip(viagem.passageiros, base.passageiros):
        irregular, motivo = _calcular_irregularidade(viagem.empresa_id, passageiro.regiao_origem_id, contexto)
        passageiros.append(passageiro_read.model_copy(update={"irregular": irregular, "motivo_irregular": motivo}))
    condutor_em_ferias = viagem.condutor_id is not None and viagem.condutor_id in contexto.condutores_em_ferias

    conflito_condutor = contexto.conflitos_condutor.get(viagem.id)
    conflito_veiculo = contexto.conflitos_veiculo.get(viagem.id)
    motivos_conflito = []
    if conflito_condutor is not None:
        motivos_conflito.append(f"Condutor tambem escalado no carro saindo {conflito_condutor.horario_saida.strftime('%H:%M')}")
    if conflito_veiculo is not None:
        motivos_conflito.append(f"Veiculo tambem escalado no carro saindo {conflito_veiculo.horario_saida.strftime('%H:%M')}")

    intervalo = contexto.intervalos_condutor.get(viagem.condutor_id) if viagem.condutor_id is not None else None

    return base.model_copy(
        update={
            "passageiros": passageiros,
            "condutor_em_ferias": condutor_em_ferias,
            "conflito_horario": bool(motivos_conflito),
            "motivo_conflito_horario": "; ".join(motivos_conflito) or None,
            "intervalo_inicio": intervalo[0] if intervalo else None,
            "intervalo_fim": intervalo[1] if intervalo else None,
        }
    )


def _serializar_passageiro_orfao(passageiro: models.ViagemDiaPassageiro) -> schemas.ViagemDiaPassageiroRead:
    """Serializa um passageiro sem viagem_dia_id (orfao/sem vaga), mesmo formato
    usado em /sem-vaga, em vez de devolver null (200 com corpo vazio confundia
    o cliente, que esperava sempre o mesmo formato de objeto).
    """
    return schemas.ViagemDiaPassageiroRead.model_validate(passageiro).model_copy(
        update={"irregular": False, "motivo_irregular": None}
    )


def _query_viagens(db: Session, data: dt.date):
    return (
        db.query(models.ViagemDia)
        .options(joinedload(models.ViagemDia.passageiros).joinedload(models.ViagemDiaPassageiro.usuario))
        .filter(models.ViagemDia.data == data)
        .order_by(models.ViagemDia.regiao_id, models.ViagemDia.horario_saida)
        .all()
    )


@router.get("", response_model=list[schemas.ViagemDiaRead])
def listar_viagens(data: dt.date, db: Session = Depends(get_db)):
    viagens_do_dia = _query_viagens(db, data)
    contexto = _construir_contexto_dia(db, data, viagens_do_dia)
    return [_serializar_viagem(v, contexto) for v in viagens_do_dia]


@router.get("/travamento", response_model=schemas.DiaTravadoRead)
def obter_travamento(data: dt.date, db: Session = Depends(get_db)):
    travamento = db.get(models.DiaTravado, data)
    return schemas.DiaTravadoRead(data=data, travado=travamento is not None, travado_em=travamento.travado_em if travamento else None)


@router.post("/travar", response_model=schemas.DiaTravadoRead)
def travar_dia(data: dt.date, db: Session = Depends(get_db)):
    if db.get(models.DiaTravado, data) is None:
        db.add(models.DiaTravado(data=data))
        db.commit()
    travamento = db.get(models.DiaTravado, data)
    return schemas.DiaTravadoRead(data=data, travado=True, travado_em=travamento.travado_em)


@router.post("/destravar", status_code=204)
def destravar_dia(data: dt.date, db: Session = Depends(get_db)):
    travamento = db.get(models.DiaTravado, data)
    if travamento is not None:
        db.delete(travamento)
        db.commit()


@router.post("/gerar", response_model=list[schemas.ViagemDiaRead], status_code=201)
def gerar(data: dt.date, db: Session = Depends(get_db)):
    _verificar_dia_destravado(db, data)
    gerar_agendamento_dia(db, data)
    viagens_do_dia = _query_viagens(db, data)
    contexto = _construir_contexto_dia(db, data, viagens_do_dia)
    return [_serializar_viagem(v, contexto) for v in viagens_do_dia]


@router.post("/abrir", response_model=schemas.ViagemDiaRead, status_code=201)
def abrir_viagem(payload: schemas.ViagemDiaAbrir, db: Session = Depends(get_db)):
    _verificar_dia_destravado(db, payload.data)
    if db.get(models.Regiao, payload.regiao_id) is None:
        raise HTTPException(status_code=404, detail=f"Regiao {payload.regiao_id} nao encontrada")
    viagem = models.ViagemDia(
        data=payload.data,
        regiao_id=payload.regiao_id,
        horario_saida=payload.horario_saida,
        capacidade=payload.capacidade,
        status=models.StatusViagemDia.PLANEJADA,
    )
    db.add(viagem)
    db.commit()
    db.refresh(viagem)
    return _serializar_viagem(viagem, _construir_contexto_dia(db, viagem.data))


@router.delete("/limpar", status_code=204)
def limpar_dia(data: dt.date, db: Session = Depends(get_db)):
    """Apaga todas as ViagemDia (e seus passageiros) de uma data -- destrutivo,
    usado pra descartar a geracao/escala do dia e recomecar do zero. Precisa
    vir antes de "/{viagem_id}" nas rotas pra nao ser capturado por ela.

    Tambem apaga os "sem vaga" orfaos (viagem_dia_id NULL) daquela data --
    sem isso, gerar/limpar/gerar de novo acumula orfaos duplicados de
    tentativas anteriores no painel de Sem Vaga.
    """
    _verificar_dia_destravado(db, data)
    viagem_ids = [
        row[0] for row in db.query(models.ViagemDia.id).filter(models.ViagemDia.data == data).all()
    ]
    if viagem_ids:
        db.query(models.ViagemDiaPassageiro).filter(
            models.ViagemDiaPassageiro.viagem_dia_id.in_(viagem_ids)
        ).delete(synchronize_session=False)
        db.query(models.ViagemDia).filter(models.ViagemDia.id.in_(viagem_ids)).delete(synchronize_session=False)
    db.query(models.ViagemDiaPassageiro).filter(
        models.ViagemDiaPassageiro.viagem_dia_id.is_(None), models.ViagemDiaPassageiro.data == data
    ).delete(synchronize_session=False)
    db.commit()


@router.post("/copiar", response_model=list[schemas.ViagemDiaRead], status_code=201)
def copiar_dia(payload: schemas.ViagemDiaCopiar, db: Session = Depends(get_db)):
    """Copia carros (blocos) escolhidos de `data_origem` pra `data_destino`,
    duplicando ViagemDia e passageiros. So aceita destino vazio (sem nenhum
    registro) pra nao arriscar sobrescrever agendamento ja existente.
    """
    _verificar_dia_destravado(db, payload.data_destino)

    tem_dado_no_destino = (
        db.query(models.ViagemDia.id).filter(models.ViagemDia.data == payload.data_destino).first() is not None
        or db.query(models.ViagemDiaPassageiro.id)
        .filter(models.ViagemDiaPassageiro.viagem_dia_id.is_(None), models.ViagemDiaPassageiro.data == payload.data_destino)
        .first()
        is not None
    )
    if tem_dado_no_destino:
        raise HTTPException(status_code=409, detail="O dia destino ja possui agendamento")

    ancora_ids = list(dict.fromkeys(payload.ancora_ids))
    if not ancora_ids:
        raise HTTPException(status_code=400, detail="Nenhum carro selecionado para copiar")

    ancoras = db.query(models.ViagemDia).filter(models.ViagemDia.id.in_(ancora_ids)).all()
    por_id = {v.id: v for v in ancoras}
    for ancora_id in ancora_ids:
        ancora = por_id.get(ancora_id)
        if ancora is None:
            raise HTTPException(status_code=404, detail=f"ViagemDia {ancora_id} nao encontrada")
        if ancora.data != payload.data_origem:
            raise HTTPException(status_code=400, detail=f"Viagem {ancora_id} nao pertence a data de origem informada")
        if ancora.grupo_viagem_id is not None:
            raise HTTPException(status_code=400, detail=f"Viagem {ancora_id} nao e a ancora do bloco")

    viagens_a_copiar = (
        db.query(models.ViagemDia)
        .options(joinedload(models.ViagemDia.passageiros))
        .filter(
            (models.ViagemDia.id.in_(ancora_ids)) | (models.ViagemDia.grupo_viagem_id.in_(ancora_ids)),
        )
        .all()
    )

    novas_viagens: list[models.ViagemDia] = []
    for ancora_id in ancora_ids:
        ancora = por_id[ancora_id]
        pernas = [ancora] + [v for v in viagens_a_copiar if v.grupo_viagem_id == ancora_id]

        nova_ancora = models.ViagemDia(
            data=payload.data_destino,
            regiao_id=ancora.regiao_id,
            empresa_id=ancora.empresa_id,
            condutor_id=ancora.condutor_id,
            veiculo_id=ancora.veiculo_id,
            horario_saida=ancora.horario_saida,
            capacidade=ancora.capacidade,
            status=models.StatusViagemDia.PLANEJADA,
            ordem_exibicao=ancora.ordem_exibicao,
        )
        db.add(nova_ancora)
        db.flush()
        novas_viagens.append(nova_ancora)

        for perna in pernas:
            viagem_destino = nova_ancora
            if perna.id != ancora.id:
                nova_perna = models.ViagemDia(
                    data=payload.data_destino,
                    regiao_id=perna.regiao_id,
                    empresa_id=perna.empresa_id,
                    condutor_id=perna.condutor_id,
                    veiculo_id=perna.veiculo_id,
                    horario_saida=perna.horario_saida,
                    capacidade=perna.capacidade,
                    status=models.StatusViagemDia.PLANEJADA,
                    grupo_viagem_id=nova_ancora.id,
                )
                db.add(nova_perna)
                db.flush()
                novas_viagens.append(nova_perna)
                viagem_destino = nova_perna

            for passageiro in perna.passageiros:
                db.add(
                    models.ViagemDiaPassageiro(
                        viagem_dia_id=viagem_destino.id,
                        usuario_id=passageiro.usuario_id,
                        sentido=passageiro.sentido,
                        hora=passageiro.hora,
                        origem=passageiro.origem,
                        regiao_origem_id=passageiro.regiao_origem_id,
                        destino_id=passageiro.destino_id,
                        regiao_destino_id=passageiro.regiao_destino_id,
                        acompanhante=passageiro.acompanhante,
                        ordem=passageiro.ordem,
                        status=models.StatusAtendimentoDia.AGENDADO,
                        observacoes=passageiro.observacoes,
                        fixo=passageiro.fixo,
                    )
                )

    db.commit()
    viagens_do_dia = _query_viagens(db, payload.data_destino)
    contexto = _construir_contexto_dia(db, payload.data_destino, viagens_do_dia)
    return [_serializar_viagem(v, contexto) for v in viagens_do_dia]


@router.patch("/{viagem_id}/atribuir", response_model=schemas.ViagemDiaRead)
def atribuir_condutor_veiculo(viagem_id: int, payload: schemas.ViagemDiaAtribuir, db: Session = Depends(get_db)):
    viagem = _get_viagem_ou_404(db, viagem_id)
    _verificar_viagem_destravada(db, viagem)
    if payload.limpar:
        viagem.condutor_id = None
        viagem.veiculo_id = None
        viagem.empresa_id = None
        db.commit()
        db.refresh(viagem)
        return _serializar_viagem(viagem, _construir_contexto_dia(db, viagem.data))

    dados = payload.model_dump(exclude_unset=True)
    if dados.get("veiculo_id") is not None:
        veiculo = db.get(models.Veiculo, dados["veiculo_id"])
        if veiculo is None:
            raise HTTPException(status_code=404, detail=f"Veiculo {dados['veiculo_id']} nao encontrado")
        viagem.veiculo_id = veiculo.id
        viagem.empresa_id = veiculo.empresa_id
    if dados.get("condutor_id") is not None:
        if db.get(models.Condutor, dados["condutor_id"]) is None:
            raise HTTPException(status_code=404, detail=f"Condutor {dados['condutor_id']} nao encontrado")
        viagem.condutor_id = dados["condutor_id"]
    if "observacoes" in dados:
        viagem.observacoes = dados["observacoes"]
    db.commit()
    db.refresh(viagem)
    return _serializar_viagem(viagem, _construir_contexto_dia(db, viagem.data))


@router.patch("/atribuir-bloco", response_model=list[schemas.ViagemDiaRead])
def atribuir_condutor_veiculo_bloco(payload: schemas.ViagemDiaAtribuirBloco, db: Session = Depends(get_db)):
    """Atribui condutor/veiculo a todas as pernas de um bloco (carro) de uma vez.

    Se o condutor/veiculo escolhido ja estiver escalado em outro bloco do
    mesmo dia, troca os dois -- o outro bloco herda o condutor/veiculo que
    este bloco tinha antes (ou fica sem, se este bloco tambem nao tinha) --
    sem mexer em viagens nem em passageiros.
    """
    viagens_bloco = db.query(models.ViagemDia).filter(models.ViagemDia.id.in_(payload.viagem_ids)).all()
    if len(viagens_bloco) != len(set(payload.viagem_ids)):
        raise HTTPException(status_code=404, detail="Uma ou mais viagens do bloco nao foram encontradas")
    if not viagens_bloco:
        raise HTTPException(status_code=400, detail="Nenhuma viagem informada")

    data = viagens_bloco[0].data
    _verificar_dia_destravado(db, data)
    atual_veiculo_id = viagens_bloco[0].veiculo_id
    atual_empresa_id = viagens_bloco[0].empresa_id
    atual_condutor_id = viagens_bloco[0].condutor_id
    # Carro e identificado por periodo (Manha/Tarde): um veiculo usado so de
    # manha esta livre pra ser escalado a tarde, entao a troca so deve
    # considerar outro bloco escalado no mesmo periodo do bloco atual.
    periodo_bloco = _periodo_da_viagem(viagens_bloco[0])

    def _outro_bloco(filtro_coluna, valor, mesmo_periodo=False):
        outras = (
            db.query(models.ViagemDia)
            .filter(models.ViagemDia.data == data, filtro_coluna == valor, models.ViagemDia.id.notin_(payload.viagem_ids))
            .all()
        )
        if mesmo_periodo:
            outras = [v for v in outras if _periodo_da_viagem(v) == periodo_bloco]
        if not outras:
            return []
        ancoras = list({v.grupo_viagem_id or v.id for v in outras})
        return (
            db.query(models.ViagemDia)
            .filter((models.ViagemDia.id.in_(ancoras)) | (models.ViagemDia.grupo_viagem_id.in_(ancoras)))
            .all()
        )

    if payload.veiculo_id is not None and payload.veiculo_id != atual_veiculo_id:
        veiculo = db.get(models.Veiculo, payload.veiculo_id)
        if veiculo is None:
            raise HTTPException(status_code=404, detail=f"Veiculo {payload.veiculo_id} nao encontrado")
        for v in _outro_bloco(models.ViagemDia.veiculo_id, payload.veiculo_id, mesmo_periodo=True):
            v.veiculo_id = atual_veiculo_id
            v.empresa_id = atual_empresa_id
        for v in viagens_bloco:
            v.veiculo_id = veiculo.id
            v.empresa_id = veiculo.empresa_id

    if payload.condutor_id is not None and payload.condutor_id != atual_condutor_id:
        condutor = db.get(models.Condutor, payload.condutor_id)
        if condutor is None:
            raise HTTPException(status_code=404, detail=f"Condutor {payload.condutor_id} nao encontrado")
        for v in _outro_bloco(models.ViagemDia.condutor_id, payload.condutor_id):
            v.condutor_id = atual_condutor_id
        for v in viagens_bloco:
            v.condutor_id = condutor.id

    db.commit()
    for v in viagens_bloco:
        db.refresh(v)
    contexto = _construir_contexto_dia(db, data)
    return [_serializar_viagem(v, contexto) for v in viagens_bloco]


@router.patch("/reordenar-blocos", status_code=204)
def reordenar_blocos(payload: schemas.ReordenarBlocosPayload, db: Session = Depends(get_db)):
    """Regrava a ordem de exibicao dos carros de um dia -- so essa data, nao
    mexe no molde da Base. `ancora_ids` e a lista completa dos blocos
    exibidos num periodo (Manha/Tarde), na nova ordem desejada; cada id tem
    que ser a ancora do bloco (a perna com grupo_viagem_id nulo), que e onde
    a ordem fica gravada.
    """
    _verificar_dia_destravado(db, payload.data)
    ids_unicos = list(dict.fromkeys(payload.ancora_ids))
    viagens = db.query(models.ViagemDia).filter(models.ViagemDia.id.in_(ids_unicos)).all()
    por_id = {v.id: v for v in viagens}
    for ancora_id in ids_unicos:
        viagem = por_id.get(ancora_id)
        if viagem is None:
            raise HTTPException(status_code=404, detail=f"ViagemDia {ancora_id} nao encontrada")
        if viagem.data != payload.data:
            raise HTTPException(status_code=400, detail=f"Viagem {ancora_id} nao pertence a data informada")
        if viagem.grupo_viagem_id is not None:
            raise HTTPException(status_code=400, detail=f"Viagem {ancora_id} nao e a ancora do bloco")

    for posicao, ancora_id in enumerate(ids_unicos, start=1):
        por_id[ancora_id].ordem_exibicao = posicao
    db.commit()


@router.patch("/{viagem_id}/status", response_model=schemas.ViagemDiaRead)
def alterar_status_viagem(viagem_id: int, status: models.StatusViagemDia, db: Session = Depends(get_db)):
    viagem = _get_viagem_ou_404(db, viagem_id)
    _verificar_viagem_destravada(db, viagem)
    viagem.status = status
    db.commit()
    db.refresh(viagem)
    return _serializar_viagem(viagem, _construir_contexto_dia(db, viagem.data))


@router.delete("/{viagem_id}", status_code=204)
def remover_viagem(viagem_id: int, db: Session = Depends(get_db)):
    viagem = _get_viagem_ou_404(db, viagem_id)
    _verificar_viagem_destravada(db, viagem)
    if viagem.passageiros:
        raise HTTPException(status_code=409, detail="Mova ou remova os passageiros antes de remover a viagem")
    # Se a viagem removida for a ancora do grupo (grupo_viagem_id nulo), as
    # pernas irmas que apontam pra ela via grupo_viagem_id ficariam com FK
    # orfa -- reancora essas pernas na primeira irma restante antes de deletar.
    irmas = db.query(models.ViagemDia).filter(models.ViagemDia.grupo_viagem_id == viagem.id).all()
    if irmas:
        nova_ancora = irmas[0]
        nova_ancora.grupo_viagem_id = None
        nova_ancora.ordem_exibicao = viagem.ordem_exibicao
        for irma in irmas[1:]:
            irma.grupo_viagem_id = nova_ancora.id
    db.delete(viagem)
    db.commit()


# --------------------------------------------------------------------------
# Passageiros dentro de uma viagem do dia
# --------------------------------------------------------------------------

@router.post("/{viagem_id}/passageiros", response_model=schemas.ViagemDiaRead, status_code=201)
def adicionar_passageiro(viagem_id: int, payload: schemas.ViagemDiaPassageiroCreate, db: Session = Depends(get_db)):
    viagem = _get_viagem_ou_404(db, viagem_id)
    _verificar_viagem_destravada(db, viagem)
    if db.get(models.Usuario, payload.usuario_id) is None:
        raise HTTPException(status_code=404, detail=f"Usuario {payload.usuario_id} nao encontrado")
    _verificar_conflito(db, viagem_id, payload.usuario_id, payload.sentido)
    maior_ordem = max((p.ordem for p in viagem.passageiros), default=-1)
    passageiro = models.ViagemDiaPassageiro(
        viagem_dia_id=viagem_id, ordem=maior_ordem + 1, fixo=False, **payload.model_dump()
    )
    db.add(passageiro)
    db.commit()
    db.refresh(viagem)
    return _serializar_viagem(viagem, _construir_contexto_dia(db, viagem.data))


@router.patch("/passageiros/{passageiro_id}", response_model=schemas.ViagemDiaRead | schemas.ViagemDiaPassageiroRead)
def atualizar_passageiro(passageiro_id: int, payload: schemas.ViagemDiaPassageiroAtualizar, db: Session = Depends(get_db)):
    passageiro = _get_passageiro_ou_404(db, passageiro_id)
    _verificar_passageiro_destravado(db, passageiro)
    dados = payload.model_dump(exclude_unset=True)
    if "sentido" in dados and passageiro.viagem_dia_id is not None:
        _verificar_conflito(db, passageiro.viagem_dia_id, passageiro.usuario_id, dados["sentido"], passageiro.id)
    for campo, valor in dados.items():
        setattr(passageiro, campo, valor)
    db.commit()
    if passageiro.viagem_dia_id is None:
        return _serializar_passageiro_orfao(passageiro)  # orfao (sem vaga) -- nao ha viagem pra serializar
    viagem = _get_viagem_ou_404(db, passageiro.viagem_dia_id)
    return _serializar_viagem(viagem, _construir_contexto_dia(db, viagem.data))


@router.patch("/passageiros/{passageiro_id}/mover", response_model=schemas.ViagemDiaRead)
def mover_passageiro(passageiro_id: int, payload: schemas.ViagemDiaPassageiroMover, db: Session = Depends(get_db)):
    """Move um passageiro pra outra viagem (ou reordena dentro da mesma).

    O grupo de horario (a viagem/leg de destino) e quem manda: se o destino ja
    tem gente, o passageiro movido adota a hora/sentido de quem ja esta la
    (nao o contrario -- arrastar alguem de 06h00 pro grupo das 07h00 deve
    deixar esse alguem as 07h00, sem alterar o rotulo do grupo). Tambem
    reindexa o `ordem` de todo mundo no destino na posicao alvo, pra
    persistir a sequencia visual (drag dentro da mesma leva reordena so).
    """
    passageiro = _get_passageiro_ou_404(db, passageiro_id)
    _verificar_passageiro_destravado(db, passageiro)
    viagem_destino = _get_viagem_ou_404(db, payload.viagem_dia_destino_id)
    _verificar_dia_destravado(db, viagem_destino.data)

    irmaos = (
        db.query(models.ViagemDiaPassageiro)
        .filter(
            models.ViagemDiaPassageiro.viagem_dia_id == payload.viagem_dia_destino_id,
            models.ViagemDiaPassageiro.id != passageiro_id,
        )
        .order_by(models.ViagemDiaPassageiro.hora, models.ViagemDiaPassageiro.ordem)
        .all()
    )
    referencia = irmaos[0] if irmaos else None
    sentido_destino = referencia.sentido if referencia else passageiro.sentido

    _verificar_conflito(db, payload.viagem_dia_destino_id, passageiro.usuario_id, sentido_destino, passageiro.id)

    if referencia is not None:
        passageiro.hora = referencia.hora
        passageiro.sentido = referencia.sentido
    passageiro.viagem_dia_id = payload.viagem_dia_destino_id
    passageiro.data = None  # saiu do container "Sem vaga" (se estava la)

    posicao = len(irmaos) if payload.ordem is None else max(0, min(payload.ordem, len(irmaos)))
    irmaos.insert(posicao, passageiro)
    for indice, p in enumerate(irmaos):
        p.ordem = indice

    db.commit()
    viagem = _get_viagem_ou_404(db, payload.viagem_dia_destino_id)
    return _serializar_viagem(viagem, _construir_contexto_dia(db, viagem.data))


@router.patch("/passageiros/{passageiro_id}/mover-bloco", response_model=schemas.ViagemDiaRead)
def mover_passageiro_para_bloco(
    passageiro_id: int, payload: schemas.ViagemDiaPassageiroMoverBloco, db: Session = Depends(get_db)
):
    """Move um passageiro pro bloco (carro) inteiro, soltado fora de uma leg
    especifica -- igual ao modo Base: quem manda e o proprio sentido/hora do
    passageiro, que decide em qual leg do bloco ele entra, criando a leg
    on-the-fly se o carro ainda nao tiver uma pro horario dele.
    """
    passageiro = _get_passageiro_ou_404(db, passageiro_id)
    _verificar_passageiro_destravado(db, passageiro)
    ancora = _get_viagem_ou_404(db, payload.bloco_id)
    _verificar_dia_destravado(db, ancora.data)
    bloco_id = ancora.grupo_viagem_id or ancora.id

    viagens_bloco = (
        db.query(models.ViagemDia)
        .filter(
            (models.ViagemDia.id == bloco_id) | (models.ViagemDia.grupo_viagem_id == bloco_id),
        )
        .all()
    )
    ids_bloco = [v.id for v in viagens_bloco]

    destino = (
        db.query(models.ViagemDiaPassageiro)
        .filter(
            models.ViagemDiaPassageiro.viagem_dia_id.in_(ids_bloco),
            models.ViagemDiaPassageiro.sentido == passageiro.sentido,
            models.ViagemDiaPassageiro.hora == passageiro.hora,
            models.ViagemDiaPassageiro.id != passageiro_id,
        )
        .first()
    )

    if destino is not None:
        viagem_destino_id = destino.viagem_dia_id
    else:
        modelo = viagens_bloco[0]
        nova_viagem = models.ViagemDia(
            data=modelo.data,
            regiao_id=modelo.regiao_id,
            empresa_id=modelo.empresa_id,
            condutor_id=modelo.condutor_id,
            veiculo_id=modelo.veiculo_id,
            horario_saida=horario_garagem(passageiro.hora),
            capacidade=modelo.capacidade,
            status=models.StatusViagemDia.PLANEJADA,
            grupo_viagem_id=bloco_id,
        )
        db.add(nova_viagem)
        db.flush()
        viagem_destino_id = nova_viagem.id

    _verificar_conflito(db, viagem_destino_id, passageiro.usuario_id, passageiro.sentido, passageiro.id)

    irmaos = (
        db.query(models.ViagemDiaPassageiro)
        .filter(
            models.ViagemDiaPassageiro.viagem_dia_id == viagem_destino_id,
            models.ViagemDiaPassageiro.id != passageiro_id,
        )
        .order_by(models.ViagemDiaPassageiro.hora, models.ViagemDiaPassageiro.ordem)
        .all()
    )
    passageiro.viagem_dia_id = viagem_destino_id
    passageiro.data = None  # saiu do container "Sem vaga" (se estava la)
    irmaos.append(passageiro)
    for indice, p in enumerate(irmaos):
        p.ordem = indice

    db.commit()
    viagem = _get_viagem_ou_404(db, viagem_destino_id)
    return _serializar_viagem(viagem, _construir_contexto_dia(db, viagem.data))


@router.patch("/passageiros/{passageiro_id}/status", response_model=schemas.ViagemDiaRead | schemas.ViagemDiaPassageiroRead)
def alterar_status_passageiro(
    passageiro_id: int, status: models.StatusAtendimentoDia, observacoes: str | None = None, db: Session = Depends(get_db)
):
    passageiro = _get_passageiro_ou_404(db, passageiro_id)
    _verificar_passageiro_destravado(db, passageiro)
    passageiro.status = status
    if observacoes is not None:
        passageiro.observacoes = observacoes
    db.commit()
    if passageiro.viagem_dia_id is None:
        return _serializar_passageiro_orfao(passageiro)  # orfao (sem vaga) -- nao ha viagem pra serializar
    viagem = _get_viagem_ou_404(db, passageiro.viagem_dia_id)
    return _serializar_viagem(viagem, _construir_contexto_dia(db, viagem.data))


@router.delete("/passageiros/{passageiro_id}", response_model=schemas.ViagemDiaRead | schemas.ViagemDiaPassageiroRead)
def remover_passageiro(passageiro_id: int, db: Session = Depends(get_db)):
    passageiro = _get_passageiro_ou_404(db, passageiro_id)
    _verificar_passageiro_destravado(db, passageiro)
    viagem_id = passageiro.viagem_dia_id
    dados_orfao = _serializar_passageiro_orfao(passageiro) if viagem_id is None else None
    db.delete(passageiro)
    db.commit()
    if viagem_id is None:
        return dados_orfao  # orfao (sem vaga) -- nao ha viagem pra serializar
    viagem = _get_viagem_ou_404(db, viagem_id)
    return _serializar_viagem(viagem, _construir_contexto_dia(db, viagem.data))


# --------------------------------------------------------------------------
# Sobras (carros e condutores nao escalados no dia)
# --------------------------------------------------------------------------

@router.get("/sobras", response_model=schemas.SobrasRead)
def sobras(data: dt.date, db: Session = Depends(get_db)):
    viagens_do_dia = db.query(models.ViagemDia).filter(models.ViagemDia.data == data).all()
    usados_condutor = {v.condutor_id for v in viagens_do_dia if v.condutor_id is not None}
    usados_veiculo = {v.veiculo_id for v in viagens_do_dia if v.veiculo_id is not None}
    em_ferias = {
        f.condutor_id
        for f in db.query(models.CondutorFerias).filter(
            models.CondutorFerias.data_inicio <= data, models.CondutorFerias.data_fim >= data
        )
    }
    em_folga = {
        f.condutor_id
        for f in db.query(models.Frequencia).filter(
            models.Frequencia.data == data, models.Frequencia.tipo == models.StatusFrequencia.FOLGA
        )
    }

    condutores = (
        db.query(models.Condutor)
        .filter(models.Condutor.status == models.StatusCondutor.ATIVO)
        .all()
    )
    condutores_sobrando = [
        schemas.CondutorSobraRead.model_validate(c).model_copy(update={"em_ferias": c.id in em_ferias})
        for c in condutores
        if c.id not in usados_condutor and c.id not in em_folga
    ]

    veiculos = db.query(models.Veiculo).filter(models.Veiculo.status == models.StatusVeiculo.ATIVO).all()
    veiculos_sobrando = [schemas.VeiculoRead.model_validate(v) for v in veiculos if v.id not in usados_veiculo]

    return schemas.SobrasRead(condutores=condutores_sobrando, veiculos=veiculos_sobrando)


@router.get("/desconsiderados", response_model=list[schemas.UsuarioDesconsideradoRead])
def desconsiderados(data: dt.date, db: Session = Depends(get_db)):
    return listar_desconsiderados_dia(db, data)


@router.get("/sem-vaga", response_model=list[schemas.ViagemDiaPassageiroRead])
def listar_sem_vaga(data: dt.date, db: Session = Depends(get_db)):
    """Usuarios que ficaram sem carro na geracao (fora da Base, excecao de
    horario, ou frota esgotada) -- ficam "orfaos" (viagem_dia_id nulo) pra
    alocacao manual, arrastando pra um carro na tela do dia.
    """
    passageiros = (
        db.query(models.ViagemDiaPassageiro)
        .options(joinedload(models.ViagemDiaPassageiro.usuario))
        .filter(models.ViagemDiaPassageiro.viagem_dia_id.is_(None), models.ViagemDiaPassageiro.data == data)
        .order_by(models.ViagemDiaPassageiro.hora)
        .all()
    )
    return [
        schemas.ViagemDiaPassageiroRead.model_validate(p).model_copy(update={"irregular": False, "motivo_irregular": None})
        for p in passageiros
    ]


@router.get("/agendamentos/zip")
def baixar_agendamentos(data: dt.date, db: Session = Depends(get_db)):
    conteudo = gerar_zip_agendamentos(db, data)
    if conteudo is None:
        raise HTTPException(status_code=404, detail="Nenhuma viagem gerada para essa data")
    nome_arquivo = f"agendamentos_{data.isoformat()}.zip"
    return Response(
        content=conteudo,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.get("/agendamentos/pdf")
def baixar_agendamento_condutor(
    data: dt.date, condutor_id: int | None = None, bloco_id: int | None = None, db: Session = Depends(get_db)
):
    if condutor_id is not None:
        condutor = db.get(models.Condutor, condutor_id)
        if condutor is None:
            raise HTTPException(status_code=404, detail=f"Condutor {condutor_id} nao encontrado")
        conteudo = gerar_pdf_agendamento_condutor(db, data, condutor_id)
        nome_arquivo = nome_arquivo_seguro(f"{condutor.matricula}_{condutor.apelido or condutor.nome}")
    elif bloco_id is not None:
        conteudo = gerar_pdf_agendamento_bloco(db, data, bloco_id)
        nome_arquivo = f"Indefinido_{bloco_id}"
    else:
        raise HTTPException(status_code=400, detail="Informe condutor_id ou bloco_id")

    if conteudo is None:
        raise HTTPException(status_code=404, detail="Nenhuma viagem encontrada para essa data")
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}.pdf"'},
    )


@router.get("/agendamentos/zip-png")
def baixar_agendamentos_png(data: dt.date, db: Session = Depends(get_db)):
    conteudo = gerar_zip_agendamentos_png(db, data)
    if conteudo is None:
        raise HTTPException(status_code=404, detail="Nenhuma viagem gerada para essa data")
    nome_arquivo = f"agendamentos_{data.isoformat()}.zip"
    return Response(
        content=conteudo,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.get("/agendamentos/png")
def baixar_agendamento_condutor_png(
    data: dt.date, condutor_id: int | None = None, bloco_id: int | None = None, db: Session = Depends(get_db)
):
    if condutor_id is not None:
        condutor = db.get(models.Condutor, condutor_id)
        if condutor is None:
            raise HTTPException(status_code=404, detail=f"Condutor {condutor_id} nao encontrado")
        conteudo = gerar_png_agendamento_condutor(db, data, condutor_id)
        nome_arquivo = nome_arquivo_seguro(f"{condutor.matricula}_{condutor.apelido or condutor.nome}")
    elif bloco_id is not None:
        conteudo = gerar_png_agendamento_bloco(db, data, bloco_id)
        nome_arquivo = f"Indefinido_{bloco_id}"
    else:
        raise HTTPException(status_code=400, detail="Informe condutor_id ou bloco_id")

    if conteudo is None:
        raise HTTPException(status_code=404, detail="Nenhuma viagem encontrada para essa data")
    return Response(
        content=conteudo,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}.png"'},
    )


@router.get("/agendamentos/resumo")
def baixar_resumo_dia(data: dt.date, db: Session = Depends(get_db)):
    conteudo = gerar_pdf_resumo_dia(db, data)
    if conteudo is None:
        raise HTTPException(status_code=404, detail="Nenhuma viagem gerada para essa data")
    nome_arquivo = f"resumo_{data.isoformat()}.pdf"
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.post("/sobras/condutor/{condutor_id}/folga", response_model=schemas.FrequenciaRead)
def marcar_folga(condutor_id: int, data: dt.date, db: Session = Depends(get_db)):
    _verificar_dia_destravado(db, data)
    if db.get(models.Condutor, condutor_id) is None:
        raise HTTPException(status_code=404, detail=f"Condutor {condutor_id} nao encontrado")
    frequencia = (
        db.query(models.Frequencia)
        .filter(models.Frequencia.condutor_id == condutor_id, models.Frequencia.data == data)
        .first()
    )
    if frequencia is None:
        frequencia = models.Frequencia(condutor_id=condutor_id, data=data, tipo=models.StatusFrequencia.FOLGA)
        db.add(frequencia)
    else:
        frequencia.tipo = models.StatusFrequencia.FOLGA
    db.commit()
    db.refresh(frequencia)
    return frequencia
