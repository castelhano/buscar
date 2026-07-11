from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services.ferias import limpar_frequencia_ferias, materializar_frequencia_ferias

router_regioes = APIRouter(prefix="/regioes", tags=["regioes"])
router_locais = APIRouter(prefix="/locais", tags=["locais"])
router_locais_recesso = APIRouter(prefix="/locais-recesso", tags=["locais"])
router_empresas = APIRouter(prefix="/empresas", tags=["empresas"])
router_veiculos = APIRouter(prefix="/veiculos", tags=["veiculos"])
router_condutores = APIRouter(prefix="/condutores", tags=["condutores"])
router_ferias = APIRouter(prefix="/ferias", tags=["ferias"])


def _get_or_404(db: Session, model, id_: int):
    obj = db.get(model, id_)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} {id_} nao encontrado")
    return obj


# --------------------------------------------------------------------------
# Regiao
# --------------------------------------------------------------------------

@router_regioes.get("", response_model=list[schemas.RegiaoRead])
def listar_regioes(db: Session = Depends(get_db)):
    return db.query(models.Regiao).order_by(models.Regiao.nome).all()


@router_regioes.post("", response_model=schemas.RegiaoRead, status_code=201)
def criar_regiao(payload: schemas.RegiaoCreate, db: Session = Depends(get_db)):
    regiao = models.Regiao(**payload.model_dump())
    db.add(regiao)
    db.commit()
    db.refresh(regiao)
    return regiao


@router_regioes.put("/{regiao_id}", response_model=schemas.RegiaoRead)
def atualizar_regiao(regiao_id: int, payload: schemas.RegiaoCreate, db: Session = Depends(get_db)):
    regiao = _get_or_404(db, models.Regiao, regiao_id)
    regiao.nome = payload.nome
    db.commit()
    db.refresh(regiao)
    return regiao


@router_regioes.delete("/{regiao_id}", status_code=204)
def remover_regiao(regiao_id: int, db: Session = Depends(get_db)):
    regiao = _get_or_404(db, models.Regiao, regiao_id)
    db.delete(regiao)
    db.commit()


# --------------------------------------------------------------------------
# Local
# --------------------------------------------------------------------------

@router_locais.get("", response_model=list[schemas.LocalRead])
def listar_locais(tipo: models.TipoLocal | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Local)
    if tipo is not None:
        query = query.filter(models.Local.tipo == tipo)
    return query.order_by(models.Local.nome).all()


@router_locais.post("", response_model=schemas.LocalRead, status_code=201)
def criar_local(payload: schemas.LocalCreate, db: Session = Depends(get_db)):
    _get_or_404(db, models.Regiao, payload.regiao_id)
    local = models.Local(**payload.model_dump())
    db.add(local)
    db.commit()
    db.refresh(local)
    return local


@router_locais.put("/{local_id}", response_model=schemas.LocalRead)
def atualizar_local(local_id: int, payload: schemas.LocalCreate, db: Session = Depends(get_db)):
    local = _get_or_404(db, models.Local, local_id)
    _get_or_404(db, models.Regiao, payload.regiao_id)
    for campo, valor in payload.model_dump().items():
        setattr(local, campo, valor)
    db.commit()
    db.refresh(local)
    return local


@router_locais.delete("/{local_id}", status_code=204)
def remover_local(local_id: int, db: Session = Depends(get_db)):
    local = _get_or_404(db, models.Local, local_id)
    db.delete(local)
    db.commit()


# --------------------------------------------------------------------------
# Local - recesso (periodo em que o local fica fechado, ex: recesso escolar)
# --------------------------------------------------------------------------

@router_locais_recesso.get("", response_model=list[schemas.LocalRecessoRead])
def listar_recessos(local_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.LocalRecesso)
    if local_id is not None:
        query = query.filter(models.LocalRecesso.local_id == local_id)
    return query.order_by(models.LocalRecesso.data_inicio).all()


@router_locais_recesso.post("", response_model=schemas.LocalRecessoRead, status_code=201)
def criar_recesso(payload: schemas.LocalRecessoCreate, db: Session = Depends(get_db)):
    _get_or_404(db, models.Local, payload.local_id)
    recesso = models.LocalRecesso(**payload.model_dump())
    db.add(recesso)
    db.commit()
    db.refresh(recesso)
    return recesso


@router_locais_recesso.put("/{recesso_id}", response_model=schemas.LocalRecessoRead)
def atualizar_recesso(recesso_id: int, payload: schemas.LocalRecessoCreate, db: Session = Depends(get_db)):
    recesso = _get_or_404(db, models.LocalRecesso, recesso_id)
    _get_or_404(db, models.Local, payload.local_id)
    for campo, valor in payload.model_dump().items():
        setattr(recesso, campo, valor)
    db.commit()
    db.refresh(recesso)
    return recesso


@router_locais_recesso.delete("/{recesso_id}", status_code=204)
def remover_recesso(recesso_id: int, db: Session = Depends(get_db)):
    recesso = _get_or_404(db, models.LocalRecesso, recesso_id)
    db.delete(recesso)
    db.commit()


# --------------------------------------------------------------------------
# Empresa
# --------------------------------------------------------------------------

@router_empresas.get("", response_model=list[schemas.EmpresaRead])
def listar_empresas(db: Session = Depends(get_db)):
    return db.query(models.Empresa).order_by(models.Empresa.nome).all()


@router_empresas.post("", response_model=schemas.EmpresaRead, status_code=201)
def criar_empresa(payload: schemas.EmpresaCreate, db: Session = Depends(get_db)):
    regioes = _regioes_por_id(db, payload.regiao_ids)
    empresa = models.Empresa(nome=payload.nome, regioes=regioes)
    db.add(empresa)
    db.commit()
    db.refresh(empresa)
    return empresa


@router_empresas.put("/{empresa_id}", response_model=schemas.EmpresaRead)
def atualizar_empresa(empresa_id: int, payload: schemas.EmpresaCreate, db: Session = Depends(get_db)):
    empresa = _get_or_404(db, models.Empresa, empresa_id)
    empresa.nome = payload.nome
    empresa.regioes = _regioes_por_id(db, payload.regiao_ids)
    db.commit()
    db.refresh(empresa)
    return empresa


@router_empresas.delete("/{empresa_id}", status_code=204)
def remover_empresa(empresa_id: int, db: Session = Depends(get_db)):
    empresa = _get_or_404(db, models.Empresa, empresa_id)
    db.delete(empresa)
    db.commit()


def _regioes_por_id(db: Session, regiao_ids: list[int]) -> list[models.Regiao]:
    if not regiao_ids:
        return []
    regioes = db.query(models.Regiao).filter(models.Regiao.id.in_(regiao_ids)).all()
    encontrados = {r.id for r in regioes}
    faltando = set(regiao_ids) - encontrados
    if faltando:
        raise HTTPException(status_code=404, detail=f"Regiao(oes) nao encontrada(s): {sorted(faltando)}")
    return regioes


# --------------------------------------------------------------------------
# Veiculo
# --------------------------------------------------------------------------

@router_veiculos.get("", response_model=list[schemas.VeiculoRead])
def listar_veiculos(empresa_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Veiculo)
    if empresa_id is not None:
        query = query.filter(models.Veiculo.empresa_id == empresa_id)
    return query.order_by(models.Veiculo.prefixo).all()


@router_veiculos.post("", response_model=schemas.VeiculoRead, status_code=201)
def criar_veiculo(payload: schemas.VeiculoCreate, db: Session = Depends(get_db)):
    _get_or_404(db, models.Empresa, payload.empresa_id)
    veiculo = models.Veiculo(**payload.model_dump())
    db.add(veiculo)
    db.commit()
    db.refresh(veiculo)
    return veiculo


@router_veiculos.put("/{veiculo_id}", response_model=schemas.VeiculoRead)
def atualizar_veiculo(veiculo_id: int, payload: schemas.VeiculoCreate, db: Session = Depends(get_db)):
    veiculo = _get_or_404(db, models.Veiculo, veiculo_id)
    _get_or_404(db, models.Empresa, payload.empresa_id)
    for campo, valor in payload.model_dump().items():
        setattr(veiculo, campo, valor)
    db.commit()
    db.refresh(veiculo)
    return veiculo


@router_veiculos.delete("/{veiculo_id}", status_code=204)
def remover_veiculo(veiculo_id: int, db: Session = Depends(get_db)):
    veiculo = _get_or_404(db, models.Veiculo, veiculo_id)
    db.delete(veiculo)
    db.commit()


# --------------------------------------------------------------------------
# Condutor
# --------------------------------------------------------------------------

@router_condutores.get("", response_model=list[schemas.CondutorRead])
def listar_condutores(empresa_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Condutor)
    if empresa_id is not None:
        query = query.filter(models.Condutor.empresa_id == empresa_id)
    return query.order_by(models.Condutor.nome).all()


@router_condutores.post("", response_model=schemas.CondutorRead, status_code=201)
def criar_condutor(payload: schemas.CondutorCreate, db: Session = Depends(get_db)):
    _get_or_404(db, models.Empresa, payload.empresa_id)
    condutor = models.Condutor(**payload.model_dump())
    db.add(condutor)
    db.commit()
    db.refresh(condutor)
    return condutor


@router_condutores.put("/{condutor_id}", response_model=schemas.CondutorRead)
def atualizar_condutor(condutor_id: int, payload: schemas.CondutorCreate, db: Session = Depends(get_db)):
    condutor = _get_or_404(db, models.Condutor, condutor_id)
    _get_or_404(db, models.Empresa, payload.empresa_id)
    for campo, valor in payload.model_dump().items():
        setattr(condutor, campo, valor)
    db.commit()
    db.refresh(condutor)
    return condutor


@router_condutores.delete("/{condutor_id}", status_code=204)
def remover_condutor(condutor_id: int, db: Session = Depends(get_db)):
    condutor = _get_or_404(db, models.Condutor, condutor_id)
    db.delete(condutor)
    db.commit()


# --------------------------------------------------------------------------
# Ferias
# --------------------------------------------------------------------------

@router_ferias.get("", response_model=list[schemas.CondutorFeriasRead])
def listar_ferias(condutor_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.CondutorFerias)
    if condutor_id is not None:
        query = query.filter(models.CondutorFerias.condutor_id == condutor_id)
    return query.order_by(models.CondutorFerias.data_inicio).all()


@router_ferias.post("", response_model=schemas.CondutorFeriasRead, status_code=201)
def criar_ferias(payload: schemas.CondutorFeriasCreate, db: Session = Depends(get_db)):
    _get_or_404(db, models.Condutor, payload.condutor_id)
    ferias = models.CondutorFerias(**payload.model_dump())
    db.add(ferias)
    db.flush()
    materializar_frequencia_ferias(db, ferias.condutor_id, ferias.data_inicio, ferias.data_fim)
    db.commit()
    db.refresh(ferias)
    return ferias


@router_ferias.put("/{ferias_id}", response_model=schemas.CondutorFeriasRead)
def atualizar_ferias(ferias_id: int, payload: schemas.CondutorFeriasCreate, db: Session = Depends(get_db)):
    ferias = _get_or_404(db, models.CondutorFerias, ferias_id)
    _get_or_404(db, models.Condutor, payload.condutor_id)
    limpar_frequencia_ferias(db, ferias.condutor_id, ferias.data_inicio, ferias.data_fim)
    for campo, valor in payload.model_dump().items():
        setattr(ferias, campo, valor)
    materializar_frequencia_ferias(db, ferias.condutor_id, ferias.data_inicio, ferias.data_fim)
    db.commit()
    db.refresh(ferias)
    return ferias


@router_ferias.delete("/{ferias_id}", status_code=204)
def remover_ferias(ferias_id: int, db: Session = Depends(get_db)):
    ferias = _get_or_404(db, models.CondutorFerias, ferias_id)
    limpar_frequencia_ferias(db, ferias.condutor_id, ferias.data_inicio, ferias.data_fim)
    db.delete(ferias)
    db.commit()
