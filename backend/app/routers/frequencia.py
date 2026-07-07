import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services.exportacao import gerar_csv_escalas, gerar_pdf_escalas

router = APIRouter(prefix="/frequencia", tags=["frequencia"])


@router.get("", response_model=list[schemas.FrequenciaRead])
def listar_frequencia(
    condutor_id: int | None = None,
    inicio: dt.date | None = None,
    fim: dt.date | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Frequencia)
    if condutor_id is not None:
        query = query.filter(models.Frequencia.condutor_id == condutor_id)
    if inicio is not None:
        query = query.filter(models.Frequencia.data >= inicio)
    if fim is not None:
        query = query.filter(models.Frequencia.data <= fim)
    return query.order_by(models.Frequencia.data).all()


@router.post("", response_model=schemas.FrequenciaRead, status_code=201)
def criar_frequencia(payload: schemas.FrequenciaCreate, db: Session = Depends(get_db)):
    if db.get(models.Condutor, payload.condutor_id) is None:
        raise HTTPException(status_code=404, detail=f"Condutor {payload.condutor_id} nao encontrado")
    existente = (
        db.query(models.Frequencia)
        .filter(models.Frequencia.condutor_id == payload.condutor_id, models.Frequencia.data == payload.data)
        .first()
    )
    if existente is not None:
        raise HTTPException(status_code=409, detail="Ja existe registro de frequencia para esse condutor nessa data")
    frequencia = models.Frequencia(**payload.model_dump())
    db.add(frequencia)
    db.commit()
    db.refresh(frequencia)
    return frequencia


@router.put("/{frequencia_id}", response_model=schemas.FrequenciaRead)
def atualizar_frequencia(frequencia_id: int, payload: schemas.FrequenciaCreate, db: Session = Depends(get_db)):
    frequencia = db.get(models.Frequencia, frequencia_id)
    if frequencia is None:
        raise HTTPException(status_code=404, detail=f"Frequencia {frequencia_id} nao encontrada")
    for campo, valor in payload.model_dump().items():
        setattr(frequencia, campo, valor)
    db.commit()
    db.refresh(frequencia)
    return frequencia


@router.delete("/{frequencia_id}", status_code=204)
def remover_frequencia(frequencia_id: int, db: Session = Depends(get_db)):
    frequencia = db.get(models.Frequencia, frequencia_id)
    if frequencia is None:
        raise HTTPException(status_code=404, detail=f"Frequencia {frequencia_id} nao encontrada")
    db.delete(frequencia)
    db.commit()


@router.get("/escalas/exportar")
def exportar_escalas(
    inicio: dt.date,
    fim: dt.date,
    formato: str = "csv",
    condutor_id: int | None = None,
    db: Session = Depends(get_db),
):
    if formato not in ("csv", "pdf"):
        raise HTTPException(status_code=422, detail="formato deve ser 'csv' ou 'pdf'")
    if fim < inicio:
        raise HTTPException(status_code=422, detail="data fim deve ser maior ou igual a data inicio")

    if condutor_id is not None:
        condutor = db.get(models.Condutor, condutor_id)
        if condutor is None:
            raise HTTPException(status_code=404, detail=f"Condutor {condutor_id} nao encontrado")
        condutores = [condutor]
    else:
        condutores = (
            db.query(models.Condutor)
            .filter(models.Condutor.status != models.StatusCondutor.DESLIGADO)
            .order_by(models.Condutor.nome)
            .all()
        )
    if not condutores:
        raise HTTPException(status_code=404, detail="Nenhum condutor encontrado para o filtro informado")

    if formato == "csv":
        conteudo = gerar_csv_escalas(db, condutores, inicio, fim)
        media_type, extensao = "text/csv", "csv"
    else:
        conteudo = gerar_pdf_escalas(db, condutores, inicio, fim)
        media_type, extensao = "application/pdf", "pdf"

    nome_arquivo = f"escalas_{inicio.isoformat()}_{fim.isoformat()}.{extensao}"
    return Response(
        content=conteudo,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )
