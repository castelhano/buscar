from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import exigir_admin, obter_conta_atual
from app.database import get_db
from app.services.pontos import PontoInvalido, resolver_trecho

router = APIRouter(prefix="/usuarios", tags=["usuarios"], dependencies=[Depends(obter_conta_atual)])


def _get_usuario_ou_404(db: Session, usuario_id: int) -> models.Usuario:
    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail=f"Usuario {usuario_id} nao encontrado")
    return usuario


def _preparar_trecho_dados(db: Session, usuario: models.Usuario, trecho: schemas.TrechoCreate, primeiro: bool) -> dict:
    """Resolve origem/destino do trecho a partir do tipo escolhido em cada
    lado (ver `app.services.pontos.resolver_trecho`) e devolve os campos
    prontos pra persistir, incluindo `hora`/`acompanhante`.
    """
    try:
        dados = resolver_trecho(
            db,
            usuario,
            origem_tipo=trecho.origem_tipo,
            origem_id=trecho.origem_id,
            origem_texto=trecho.origem_texto,
            origem_detalhe=trecho.origem_detalhe,
            regiao_origem_id=trecho.regiao_origem_id,
            destino_tipo=trecho.destino_tipo,
            destino_id=trecho.destino_id,
            destino_texto=trecho.destino_texto,
            destino_detalhe=trecho.destino_detalhe,
            regiao_destino_id=trecho.regiao_destino_id,
            primeiro=primeiro,
        )
    except PontoInvalido as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    dados["hora"] = trecho.hora
    dados["acompanhante"] = trecho.acompanhante
    return dados


def _sincronizar_trechos(
    db: Session,
    usuario: models.Usuario,
    existentes: list,
    novos: list[schemas.TrechoCreate],
    trecho_cls: type,
    campo_pai: str,
    pai_id: int,
) -> None:
    """Substitui a lista de trechos casando por POSICAO (ordem), nao
    apagando-e-recriando tudo -- um trecho cujo indice sobrevive na edicao
    mantem o mesmo id, preservando vinculos externos que apontam pra ele
    (`MembroViagemBase.agenda_trecho_id` no modo Base). So os trechos
    excedentes (indices que deixaram de existir) sao removidos de fato.
    """
    existentes = sorted(existentes, key=lambda t: t.ordem)
    for indice, trecho_payload in enumerate(novos):
        dados = _preparar_trecho_dados(db, usuario, trecho_payload, primeiro=indice == 0)
        if indice < len(existentes):
            trecho = existentes[indice]
            for campo, valor in dados.items():
                setattr(trecho, campo, valor)
        else:
            db.add(trecho_cls(ordem=indice, **{campo_pai: pai_id}, **dados))
    for excedente in existentes[len(novos):]:
        db.delete(excedente)


@router.get("", response_model=list[schemas.UsuarioRead])
def listar_usuarios(
    status: models.StatusAtivoInativo | None = None,
    nome: str | None = None,
    somente_fixo: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(models.Usuario)
    if status is not None:
        query = query.filter(models.Usuario.status == status)
    if nome:
        query = query.filter(func.lower(models.Usuario.nome).contains(nome.lower()))
    if somente_fixo:
        query = query.filter(
            models.Usuario.id.in_(
                db.query(models.UsuarioAgendaSemanal.usuario_id).filter(
                    models.UsuarioAgendaSemanal.tipo == models.TipoAtendimento.FIXO,
                    models.UsuarioAgendaSemanal.ativo.is_(True),
                )
            )
        )
    return query.order_by(models.Usuario.nome).all()


def _verificar_grupo_familiar(db: Session, grupo_familiar_id: int | None) -> None:
    if grupo_familiar_id is not None and db.get(models.GrupoFamiliar, grupo_familiar_id) is None:
        raise HTTPException(status_code=404, detail=f"Grupo familiar {grupo_familiar_id} nao encontrado")


def _verificar_regiao(db: Session, regiao_id: int | None) -> None:
    if regiao_id is not None and db.get(models.Regiao, regiao_id) is None:
        raise HTTPException(status_code=404, detail=f"Regiao {regiao_id} nao encontrada")


@router.post("", response_model=schemas.UsuarioRead, status_code=201, dependencies=[Depends(exigir_admin)])
def criar_usuario(payload: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    _verificar_grupo_familiar(db, payload.grupo_familiar_id)
    _verificar_regiao(db, payload.regiao_id)
    usuario = models.Usuario(**payload.model_dump())
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.get("/{usuario_id}", response_model=schemas.UsuarioComAgendaRead)
def obter_usuario(usuario_id: int, db: Session = Depends(get_db)):
    usuario = (
        db.query(models.Usuario)
        .options(joinedload(models.Usuario.agenda_semanal), joinedload(models.Usuario.excecoes))
        .filter(models.Usuario.id == usuario_id)
        .first()
    )
    if usuario is None:
        raise HTTPException(status_code=404, detail=f"Usuario {usuario_id} nao encontrado")
    return usuario


@router.put("/{usuario_id}", response_model=schemas.UsuarioRead, dependencies=[Depends(exigir_admin)])
def atualizar_usuario(usuario_id: int, payload: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    usuario = _get_usuario_ou_404(db, usuario_id)
    _verificar_grupo_familiar(db, payload.grupo_familiar_id)
    _verificar_regiao(db, payload.regiao_id)
    for campo, valor in payload.model_dump().items():
        setattr(usuario, campo, valor)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete("/{usuario_id}", status_code=204, dependencies=[Depends(exigir_admin)])
def remover_usuario(usuario_id: int, db: Session = Depends(get_db)):
    usuario = _get_usuario_ou_404(db, usuario_id)

    tem_agenda = db.query(models.UsuarioAgendaSemanal).filter(models.UsuarioAgendaSemanal.usuario_id == usuario_id).first()
    tem_excecao = db.query(models.UsuarioExcecao).filter(models.UsuarioExcecao.usuario_id == usuario_id).first()
    tem_viagem = db.query(models.ViagemDiaPassageiro).filter(models.ViagemDiaPassageiro.usuario_id == usuario_id).first()
    if tem_agenda is not None or tem_excecao is not None or tem_viagem is not None:
        raise HTTPException(
            status_code=409,
            detail="Nao e possivel remover o usuario: existem registros relacionados (agenda semanal, excecoes ou viagens). Remova-os primeiro.",
        )

    db.delete(usuario)
    db.commit()


# --------------------------------------------------------------------------
# Agenda semanal (padrao Fixo/Eventual por dia da semana)
# --------------------------------------------------------------------------

@router.get("/{usuario_id}/agenda-semanal", response_model=list[schemas.UsuarioAgendaSemanalRead])
def listar_agenda_semanal(usuario_id: int, db: Session = Depends(get_db)):
    _get_usuario_ou_404(db, usuario_id)
    return (
        db.query(models.UsuarioAgendaSemanal)
        .options(joinedload(models.UsuarioAgendaSemanal.trechos))
        .filter(models.UsuarioAgendaSemanal.usuario_id == usuario_id)
        .all()
    )


@router.post(
    "/{usuario_id}/agenda-semanal",
    response_model=schemas.UsuarioAgendaSemanalRead,
    status_code=201,
    dependencies=[Depends(exigir_admin)],
)
def criar_agenda_semanal(usuario_id: int, payload: schemas.UsuarioAgendaSemanalCreate, db: Session = Depends(get_db)):
    usuario = _get_usuario_ou_404(db, usuario_id)
    dados = payload.model_dump(exclude={"trechos"})
    agenda = models.UsuarioAgendaSemanal(usuario_id=usuario_id, **dados)
    db.add(agenda)
    db.flush()
    for indice, trecho_payload in enumerate(payload.trechos):
        trecho_dados = _preparar_trecho_dados(db, usuario, trecho_payload, primeiro=indice == 0)
        db.add(models.UsuarioAgendaSemanalTrecho(agenda_id=agenda.id, ordem=indice, **trecho_dados))
    db.commit()
    db.refresh(agenda)
    return agenda


@router.put(
    "/{usuario_id}/agenda-semanal/{agenda_id}",
    response_model=schemas.UsuarioAgendaSemanalRead,
    dependencies=[Depends(exigir_admin)],
)
def atualizar_agenda_semanal(
    usuario_id: int, agenda_id: int, payload: schemas.UsuarioAgendaSemanalCreate, db: Session = Depends(get_db)
):
    agenda = db.get(models.UsuarioAgendaSemanal, agenda_id)
    if agenda is None or agenda.usuario_id != usuario_id:
        raise HTTPException(status_code=404, detail="Agenda semanal nao encontrada para esse usuario")
    dados = payload.model_dump(exclude={"trechos"})
    for campo, valor in dados.items():
        setattr(agenda, campo, valor)
    _sincronizar_trechos(
        db, agenda.usuario, agenda.trechos, payload.trechos, models.UsuarioAgendaSemanalTrecho, "agenda_id", agenda.id
    )
    db.commit()
    db.refresh(agenda)
    return agenda


@router.delete("/{usuario_id}/agenda-semanal/{agenda_id}", status_code=204, dependencies=[Depends(exigir_admin)])
def remover_agenda_semanal(usuario_id: int, agenda_id: int, db: Session = Depends(get_db)):
    agenda = db.get(models.UsuarioAgendaSemanal, agenda_id)
    if agenda is None or agenda.usuario_id != usuario_id:
        raise HTTPException(status_code=404, detail="Agenda semanal nao encontrada para esse usuario")
    db.delete(agenda)
    db.commit()


# --------------------------------------------------------------------------
# Excecoes pontuais (uma data especifica)
# --------------------------------------------------------------------------

@router.get("/{usuario_id}/excecoes", response_model=list[schemas.UsuarioExcecaoRead])
def listar_excecoes(usuario_id: int, db: Session = Depends(get_db)):
    _get_usuario_ou_404(db, usuario_id)
    return (
        db.query(models.UsuarioExcecao)
        .options(joinedload(models.UsuarioExcecao.trechos))
        .filter(models.UsuarioExcecao.usuario_id == usuario_id)
        .all()
    )


@router.post(
    "/{usuario_id}/excecoes",
    response_model=schemas.UsuarioExcecaoRead,
    status_code=201,
    dependencies=[Depends(exigir_admin)],
)
def criar_excecao(usuario_id: int, payload: schemas.UsuarioExcecaoCreate, db: Session = Depends(get_db)):
    usuario = _get_usuario_ou_404(db, usuario_id)
    dados = payload.model_dump(exclude={"trechos"})
    excecao = models.UsuarioExcecao(usuario_id=usuario_id, **dados)
    db.add(excecao)
    db.flush()
    if excecao.operacao != models.OperacaoExcecao.SUSPENSAO:
        for indice, trecho_payload in enumerate(payload.trechos):
            trecho_dados = _preparar_trecho_dados(db, usuario, trecho_payload, primeiro=indice == 0)
            db.add(models.UsuarioExcecaoTrecho(excecao_id=excecao.id, ordem=indice, **trecho_dados))
    db.commit()
    db.refresh(excecao)
    return excecao


@router.put(
    "/{usuario_id}/excecoes/{excecao_id}", response_model=schemas.UsuarioExcecaoRead, dependencies=[Depends(exigir_admin)]
)
def atualizar_excecao(
    usuario_id: int, excecao_id: int, payload: schemas.UsuarioExcecaoCreate, db: Session = Depends(get_db)
):
    excecao = db.get(models.UsuarioExcecao, excecao_id)
    if excecao is None or excecao.usuario_id != usuario_id:
        raise HTTPException(status_code=404, detail="Excecao nao encontrada para esse usuario")
    dados = payload.model_dump(exclude={"trechos"})
    for campo, valor in dados.items():
        setattr(excecao, campo, valor)
    novos_trechos = [] if payload.operacao == models.OperacaoExcecao.SUSPENSAO else payload.trechos
    _sincronizar_trechos(
        db, excecao.usuario, excecao.trechos, novos_trechos, models.UsuarioExcecaoTrecho, "excecao_id", excecao.id
    )
    db.commit()
    db.refresh(excecao)
    return excecao


@router.delete("/{usuario_id}/excecoes/{excecao_id}", status_code=204, dependencies=[Depends(exigir_admin)])
def remover_excecao(usuario_id: int, excecao_id: int, db: Session = Depends(get_db)):
    excecao = db.get(models.UsuarioExcecao, excecao_id)
    if excecao is None or excecao.usuario_id != usuario_id:
        raise HTTPException(status_code=404, detail="Excecao nao encontrada para esse usuario")
    db.delete(excecao)
    db.commit()
