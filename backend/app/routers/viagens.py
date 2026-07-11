import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db
from app.services.exportacao import gerar_pdf_resumo_dia, gerar_zip_agendamentos
from app.services.frequencia import intervalo_do_condutor
from app.services.geracao import gerar_agendamento_dia, listar_desconsiderados_dia
from app.services.recursos import fim_viagem, janelas_sobrepoem

router = APIRouter(prefix="/viagens", tags=["viagens"])


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


def _calcular_irregularidade(db: Session, viagem: models.ViagemDia, regiao_origem_id: int | None):
    if viagem.empresa_id is None or regiao_origem_id is None:
        return False, None
    habilitada = (
        db.query(models.empresa_regiao)
        .filter(
            models.empresa_regiao.c.empresa_id == viagem.empresa_id,
            models.empresa_regiao.c.regiao_id == regiao_origem_id,
        )
        .first()
    )
    if habilitada is not None:
        return False, None
    regiao = db.get(models.Regiao, regiao_origem_id)
    nome_regiao = regiao.nome if regiao else str(regiao_origem_id)
    return True, f"Empresa da viagem nao esta habilitada para a regiao {nome_regiao} do usuario"


def _condutor_em_ferias(db: Session, condutor_id: int | None, data: dt.date) -> bool:
    if condutor_id is None:
        return False
    return (
        db.query(models.CondutorFerias)
        .filter(
            models.CondutorFerias.condutor_id == condutor_id,
            models.CondutorFerias.data_inicio <= data,
            models.CondutorFerias.data_fim >= data,
        )
        .first()
        is not None
    )


def _detectar_conflito_recurso(
    db: Session, viagem: models.ViagemDia, campo: str, resource_id: int | None
) -> models.ViagemDia | None:
    """Encontra outra viagem do mesmo dia usando o mesmo condutor/veiculo em horario sobreposto.

    Duas viagens do mesmo carro/condutor no mesmo dia sao normais (dois turnos)
    desde que uma termine (ultimo atendimento) antes da outra comecar (horario de
    saida) -- so sinaliza quando os intervalos se sobrepoem.
    """
    if resource_id is None:
        return None
    outras = (
        db.query(models.ViagemDia)
        .options(joinedload(models.ViagemDia.passageiros))
        .filter(
            models.ViagemDia.data == viagem.data,
            models.ViagemDia.id != viagem.id,
            getattr(models.ViagemDia, campo) == resource_id,
            models.ViagemDia.status != models.StatusViagemDia.CANCELADA,
        )
        .all()
    )
    fim = fim_viagem(viagem)
    inicio = viagem.horario_saida
    for outra in outras:
        if janelas_sobrepoem(inicio, fim, outra.horario_saida, fim_viagem(outra)):
            return outra
    return None


def _serializar_viagem(db: Session, viagem: models.ViagemDia) -> schemas.ViagemDiaRead:
    base = schemas.ViagemDiaRead.model_validate(viagem)
    passageiros = []
    for passageiro, passageiro_read in zip(viagem.passageiros, base.passageiros):
        irregular, motivo = _calcular_irregularidade(db, viagem, passageiro.regiao_origem_id)
        passageiros.append(passageiro_read.model_copy(update={"irregular": irregular, "motivo_irregular": motivo}))
    condutor_em_ferias = _condutor_em_ferias(db, viagem.condutor_id, viagem.data)

    conflito_condutor = _detectar_conflito_recurso(db, viagem, "condutor_id", viagem.condutor_id)
    conflito_veiculo = _detectar_conflito_recurso(db, viagem, "veiculo_id", viagem.veiculo_id)
    motivos_conflito = []
    if conflito_condutor is not None:
        motivos_conflito.append(f"Condutor tambem escalado no carro saindo {conflito_condutor.horario_saida.strftime('%H:%M')}")
    if conflito_veiculo is not None:
        motivos_conflito.append(f"Veiculo tambem escalado no carro saindo {conflito_veiculo.horario_saida.strftime('%H:%M')}")

    intervalo = intervalo_do_condutor(db, viagem.condutor_id, viagem.data)

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
    return [_serializar_viagem(db, v) for v in _query_viagens(db, data)]


@router.post("/gerar", response_model=list[schemas.ViagemDiaRead], status_code=201)
def gerar(data: dt.date, db: Session = Depends(get_db)):
    gerar_agendamento_dia(db, data)
    return [_serializar_viagem(db, v) for v in _query_viagens(db, data)]


@router.post("/abrir", response_model=schemas.ViagemDiaRead, status_code=201)
def abrir_viagem(payload: schemas.ViagemDiaAbrir, db: Session = Depends(get_db)):
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
    return _serializar_viagem(db, viagem)


@router.delete("/limpar", status_code=204)
def limpar_dia(data: dt.date, db: Session = Depends(get_db)):
    """Apaga todas as ViagemDia (e seus passageiros) de uma data -- destrutivo,
    usado pra descartar a geracao/escala do dia e recomecar do zero. Precisa
    vir antes de "/{viagem_id}" nas rotas pra nao ser capturado por ela.
    """
    viagem_ids = [
        row[0] for row in db.query(models.ViagemDia.id).filter(models.ViagemDia.data == data).all()
    ]
    if viagem_ids:
        db.query(models.ViagemDiaPassageiro).filter(
            models.ViagemDiaPassageiro.viagem_dia_id.in_(viagem_ids)
        ).delete(synchronize_session=False)
        db.query(models.ViagemDia).filter(models.ViagemDia.id.in_(viagem_ids)).delete(synchronize_session=False)
    db.commit()


@router.patch("/{viagem_id}/atribuir", response_model=schemas.ViagemDiaRead)
def atribuir_condutor_veiculo(viagem_id: int, payload: schemas.ViagemDiaAtribuir, db: Session = Depends(get_db)):
    viagem = _get_viagem_ou_404(db, viagem_id)
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
    return _serializar_viagem(db, viagem)


@router.patch("/{viagem_id}/status", response_model=schemas.ViagemDiaRead)
def alterar_status_viagem(viagem_id: int, status: models.StatusViagemDia, db: Session = Depends(get_db)):
    viagem = _get_viagem_ou_404(db, viagem_id)
    viagem.status = status
    db.commit()
    db.refresh(viagem)
    return _serializar_viagem(db, viagem)


@router.delete("/{viagem_id}", status_code=204)
def remover_viagem(viagem_id: int, db: Session = Depends(get_db)):
    viagem = _get_viagem_ou_404(db, viagem_id)
    if viagem.passageiros:
        raise HTTPException(status_code=409, detail="Mova ou remova os passageiros antes de remover o carro")
    db.delete(viagem)
    db.commit()


# --------------------------------------------------------------------------
# Passageiros dentro de uma viagem do dia
# --------------------------------------------------------------------------

@router.post("/{viagem_id}/passageiros", response_model=schemas.ViagemDiaRead, status_code=201)
def adicionar_passageiro(viagem_id: int, payload: schemas.ViagemDiaPassageiroCreate, db: Session = Depends(get_db)):
    viagem = _get_viagem_ou_404(db, viagem_id)
    if db.get(models.Usuario, payload.usuario_id) is None:
        raise HTTPException(status_code=404, detail=f"Usuario {payload.usuario_id} nao encontrado")
    _verificar_conflito(db, viagem_id, payload.usuario_id, payload.sentido)
    maior_ordem = max((p.ordem for p in viagem.passageiros), default=-1)
    passageiro = models.ViagemDiaPassageiro(viagem_dia_id=viagem_id, ordem=maior_ordem + 1, **payload.model_dump())
    db.add(passageiro)
    db.commit()
    db.refresh(viagem)
    return _serializar_viagem(db, viagem)


@router.patch("/passageiros/{passageiro_id}", response_model=schemas.ViagemDiaRead | None)
def atualizar_passageiro(passageiro_id: int, payload: schemas.ViagemDiaPassageiroAtualizar, db: Session = Depends(get_db)):
    passageiro = _get_passageiro_ou_404(db, passageiro_id)
    dados = payload.model_dump(exclude_unset=True)
    if "sentido" in dados and passageiro.viagem_dia_id is not None:
        _verificar_conflito(db, passageiro.viagem_dia_id, passageiro.usuario_id, dados["sentido"], passageiro.id)
    for campo, valor in dados.items():
        setattr(passageiro, campo, valor)
    db.commit()
    if passageiro.viagem_dia_id is None:
        return None  # orfao (sem vaga) -- nao ha viagem pra serializar
    viagem = _get_viagem_ou_404(db, passageiro.viagem_dia_id)
    return _serializar_viagem(db, viagem)


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
    _get_viagem_ou_404(db, payload.viagem_dia_destino_id)

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
    return _serializar_viagem(db, viagem)


@router.patch("/passageiros/{passageiro_id}/status", response_model=schemas.ViagemDiaRead | None)
def alterar_status_passageiro(
    passageiro_id: int, status: models.StatusAtendimentoDia, observacoes: str | None = None, db: Session = Depends(get_db)
):
    passageiro = _get_passageiro_ou_404(db, passageiro_id)
    passageiro.status = status
    if observacoes is not None:
        passageiro.observacoes = observacoes
    db.commit()
    if passageiro.viagem_dia_id is None:
        return None  # orfao (sem vaga) -- nao ha viagem pra serializar
    viagem = _get_viagem_ou_404(db, passageiro.viagem_dia_id)
    return _serializar_viagem(db, viagem)


@router.delete("/passageiros/{passageiro_id}", response_model=schemas.ViagemDiaRead | None)
def remover_passageiro(passageiro_id: int, db: Session = Depends(get_db)):
    passageiro = _get_passageiro_ou_404(db, passageiro_id)
    viagem_id = passageiro.viagem_dia_id
    db.delete(passageiro)
    db.commit()
    if viagem_id is None:
        return None  # orfao (sem vaga) -- nao ha viagem pra serializar
    viagem = _get_viagem_ou_404(db, viagem_id)
    return _serializar_viagem(db, viagem)


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

    condutores = (
        db.query(models.Condutor)
        .filter(models.Condutor.status == models.StatusCondutor.ATIVO)
        .all()
    )
    condutores_sobrando = [
        schemas.CondutorSobraRead.model_validate(c).model_copy(update={"em_ferias": c.id in em_ferias})
        for c in condutores
        if c.id not in usados_condutor
    ]

    veiculos = db.query(models.Veiculo).filter(models.Veiculo.status == models.StatusVeiculo.ATIVO).all()
    veiculos_sobrando = [schemas.VeiculoRead.model_validate(v) for v in veiculos if v.id not in usados_veiculo]

    return schemas.SobrasRead(condutores=condutores_sobrando, veiculos=veiculos_sobrando)


@router.get("/desconsiderados", response_model=list[schemas.UsuarioDesconsideradoRead])
def desconsiderados(data: dt.date, db: Session = Depends(get_db)):
    return listar_desconsiderados_dia(db, data)


@router.get("/sem-vaga", response_model=list[schemas.ViagemDiaPassageiroRead])
def listar_sem_vaga(data: dt.date, db: Session = Depends(get_db)):
    """Usuarios que ficaram sem carro na geracao (frota esgotada) -- ficam
    "orfaos" (viagem_dia_id nulo) pra alocacao manual, arrastando pra um carro
    na tela do dia.
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
        raise HTTPException(status_code=404, detail="Nenhuma viagem com condutor atribuido para essa data")
    nome_arquivo = f"agendamentos_{data.isoformat()}.zip"
    return Response(
        content=conteudo,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
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
