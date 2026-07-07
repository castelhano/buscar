from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


def _get_usuario_ou_404(db: Session, usuario_id: int) -> models.Usuario:
    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail=f"Usuario {usuario_id} nao encontrado")
    return usuario


@router.get("", response_model=list[schemas.UsuarioRead])
def listar_usuarios(status: models.StatusAtivoInativo | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Usuario)
    if status is not None:
        query = query.filter(models.Usuario.status == status)
    return query.order_by(models.Usuario.nome).all()


@router.post("", response_model=schemas.UsuarioRead, status_code=201)
def criar_usuario(payload: schemas.UsuarioCreate, db: Session = Depends(get_db)):
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


@router.put("/{usuario_id}", response_model=schemas.UsuarioRead)
def atualizar_usuario(usuario_id: int, payload: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    usuario = _get_usuario_ou_404(db, usuario_id)
    for campo, valor in payload.model_dump().items():
        setattr(usuario, campo, valor)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete("/{usuario_id}", status_code=204)
def remover_usuario(usuario_id: int, db: Session = Depends(get_db)):
    usuario = _get_usuario_ou_404(db, usuario_id)
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
        .filter(models.UsuarioAgendaSemanal.usuario_id == usuario_id)
        .all()
    )


@router.post("/{usuario_id}/agenda-semanal", response_model=schemas.UsuarioAgendaSemanalRead, status_code=201)
def criar_agenda_semanal(usuario_id: int, payload: schemas.UsuarioAgendaSemanalCreate, db: Session = Depends(get_db)):
    _get_usuario_ou_404(db, usuario_id)
    existente = (
        db.query(models.UsuarioAgendaSemanal)
        .filter(
            models.UsuarioAgendaSemanal.usuario_id == usuario_id,
            models.UsuarioAgendaSemanal.dia_semana == payload.dia_semana,
        )
        .first()
    )
    if existente is not None:
        raise HTTPException(status_code=409, detail="Usuario ja possui agenda cadastrada para esse dia da semana")
    agenda = models.UsuarioAgendaSemanal(usuario_id=usuario_id, **payload.model_dump())
    db.add(agenda)
    db.commit()
    db.refresh(agenda)
    return agenda


@router.put("/{usuario_id}/agenda-semanal/{agenda_id}", response_model=schemas.UsuarioAgendaSemanalRead)
def atualizar_agenda_semanal(
    usuario_id: int, agenda_id: int, payload: schemas.UsuarioAgendaSemanalCreate, db: Session = Depends(get_db)
):
    agenda = db.get(models.UsuarioAgendaSemanal, agenda_id)
    if agenda is None or agenda.usuario_id != usuario_id:
        raise HTTPException(status_code=404, detail="Agenda semanal nao encontrada para esse usuario")
    for campo, valor in payload.model_dump().items():
        setattr(agenda, campo, valor)
    db.commit()
    db.refresh(agenda)
    return agenda


@router.delete("/{usuario_id}/agenda-semanal/{agenda_id}", status_code=204)
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
    return db.query(models.UsuarioExcecao).filter(models.UsuarioExcecao.usuario_id == usuario_id).all()


@router.post("/{usuario_id}/excecoes", response_model=schemas.UsuarioExcecaoRead, status_code=201)
def criar_excecao(usuario_id: int, payload: schemas.UsuarioExcecaoCreate, db: Session = Depends(get_db)):
    _get_usuario_ou_404(db, usuario_id)
    existente = (
        db.query(models.UsuarioExcecao)
        .filter(models.UsuarioExcecao.usuario_id == usuario_id, models.UsuarioExcecao.data == payload.data)
        .first()
    )
    if existente is not None:
        raise HTTPException(status_code=409, detail="Usuario ja possui excecao cadastrada para essa data")
    excecao = models.UsuarioExcecao(usuario_id=usuario_id, **payload.model_dump())
    db.add(excecao)
    db.commit()
    db.refresh(excecao)
    return excecao


@router.put("/{usuario_id}/excecoes/{excecao_id}", response_model=schemas.UsuarioExcecaoRead)
def atualizar_excecao(
    usuario_id: int, excecao_id: int, payload: schemas.UsuarioExcecaoCreate, db: Session = Depends(get_db)
):
    excecao = db.get(models.UsuarioExcecao, excecao_id)
    if excecao is None or excecao.usuario_id != usuario_id:
        raise HTTPException(status_code=404, detail="Excecao nao encontrada para esse usuario")
    for campo, valor in payload.model_dump().items():
        setattr(excecao, campo, valor)
    db.commit()
    db.refresh(excecao)
    return excecao


@router.delete("/{usuario_id}/excecoes/{excecao_id}", status_code=204)
def remover_excecao(usuario_id: int, excecao_id: int, db: Session = Depends(get_db)):
    excecao = db.get(models.UsuarioExcecao, excecao_id)
    if excecao is None or excecao.usuario_id != usuario_id:
        raise HTTPException(status_code=404, detail="Excecao nao encontrada para esse usuario")
    db.delete(excecao)
    db.commit()
