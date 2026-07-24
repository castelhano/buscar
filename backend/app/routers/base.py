from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import obter_conta_atual
from app.database import get_db
from app.services.base import (
    alterar_hora_viagem,
    criar_grupo,
    criar_grupo_revezamento,
    criar_viagem,
    definir_carros_revezamento,
    definir_condutores_revezamento,
    girar_grupo_revezamento,
    mover_membro,
    montar_estrutura_base,
    remover_grupo,
    remover_grupo_revezamento,
    remover_membro,
    remover_viagem,
)
from app.services.exportacao import gerar_csv_grupos_revezamento, gerar_pdf_ocupacao_base

router = APIRouter(prefix="/base", tags=["base"], dependencies=[Depends(obter_conta_atual)])


@router.get("/ocupacao/pdf")
def baixar_ocupacao_base(
    dia_semana: models.DiaSemana | None = None,
    semana: bool = False,
    db: Session = Depends(get_db),
):
    if not semana and dia_semana is None:
        raise HTTPException(status_code=400, detail="Informe dia_semana ou semana=true")
    dias = list(models.DiaSemana) if semana else [dia_semana]
    conteudo = gerar_pdf_ocupacao_base(db, dias, modo_semana=semana)
    if conteudo is None:
        raise HTTPException(status_code=404, detail="Nenhum carro cadastrado no molde base para gerar a ocupacao")
    nome_arquivo = "ocupacao_semana.pdf" if semana else f"ocupacao_{dia_semana.value}.pdf"
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.get("/{dia_semana}", response_model=schemas.EstruturaBaseRead)
def obter_estrutura(dia_semana: models.DiaSemana, db: Session = Depends(get_db)):
    return montar_estrutura_base(db, dia_semana)


@router.get("/{dia_semana}/revezamentos/csv")
def baixar_grupos_revezamento_csv(dia_semana: models.DiaSemana, db: Session = Depends(get_db)):
    conteudo = gerar_csv_grupos_revezamento(db, dia_semana)
    nome_arquivo = f"grupos_revezamento_{dia_semana.value}.csv"
    return Response(
        content=conteudo,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.post("/{dia_semana}/grupos", response_model=schemas.EstruturaBaseRead, status_code=201)
def criar_grupo_base(dia_semana: models.DiaSemana, db: Session = Depends(get_db)):
    criar_grupo(db, dia_semana)
    return montar_estrutura_base(db, dia_semana)


@router.delete("/grupos/{grupo_id}", response_model=schemas.EstruturaBaseRead)
def remover_grupo_base(grupo_id: int, db: Session = Depends(get_db)):
    grupo = db.get(models.GrupoBase, grupo_id)
    if grupo is None:
        raise HTTPException(status_code=404, detail=f"Grupo {grupo_id} nao encontrado")
    dia_semana = grupo.dia_semana
    remover_grupo(db, grupo_id)
    return montar_estrutura_base(db, dia_semana)


@router.post("/grupos/{grupo_id}/viagens", response_model=schemas.EstruturaBaseRead, status_code=201)
def criar_viagem_base(grupo_id: int, payload: schemas.ViagemBaseCreate, db: Session = Depends(get_db)):
    grupo = db.get(models.GrupoBase, grupo_id)
    if grupo is None:
        raise HTTPException(status_code=404, detail=f"Grupo {grupo_id} nao encontrado")
    try:
        criar_viagem(db, grupo_id, payload.hora)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    return montar_estrutura_base(db, grupo.dia_semana)


@router.post("/{dia_semana}/revezamentos", response_model=schemas.EstruturaBaseRead, status_code=201)
def criar_grupo_revezamento_base(dia_semana: models.DiaSemana, payload: schemas.GrupoRevezamentoCreate, db: Session = Depends(get_db)):
    criar_grupo_revezamento(db, dia_semana, payload.rotulo)
    return montar_estrutura_base(db, dia_semana)


@router.delete("/revezamentos/{grupo_revezamento_id}", response_model=schemas.EstruturaBaseRead)
def remover_grupo_revezamento_base(grupo_revezamento_id: int, db: Session = Depends(get_db)):
    revezamento = db.get(models.GrupoRevezamento, grupo_revezamento_id)
    if revezamento is None:
        raise HTTPException(status_code=404, detail=f"Grupo de revezamento {grupo_revezamento_id} nao encontrado")
    dia_semana = revezamento.dia_semana
    remover_grupo_revezamento(db, grupo_revezamento_id)
    return montar_estrutura_base(db, dia_semana)


@router.put("/revezamentos/{grupo_revezamento_id}/carros", response_model=schemas.EstruturaBaseRead)
def definir_carros_revezamento_base(grupo_revezamento_id: int, payload: schemas.CarrosRevezamentoSet, db: Session = Depends(get_db)):
    try:
        dia_semana = definir_carros_revezamento(db, grupo_revezamento_id, payload.grupo_base_ids)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    return montar_estrutura_base(db, dia_semana)


@router.put("/revezamentos/{grupo_revezamento_id}/condutores", response_model=schemas.EstruturaBaseRead)
def definir_condutores_revezamento_base(grupo_revezamento_id: int, payload: schemas.CondutoresRevezamentoSet, db: Session = Depends(get_db)):
    try:
        dia_semana = definir_condutores_revezamento(db, grupo_revezamento_id, payload.condutor_ids)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    return montar_estrutura_base(db, dia_semana)


@router.post("/revezamentos/{grupo_revezamento_id}/girar", response_model=schemas.EstruturaBaseRead)
def girar_grupo_revezamento_base(grupo_revezamento_id: int, db: Session = Depends(get_db)):
    try:
        dia_semana = girar_grupo_revezamento(db, grupo_revezamento_id)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    return montar_estrutura_base(db, dia_semana)


@router.delete("/viagens/{viagem_id}", response_model=schemas.EstruturaBaseRead)
def remover_viagem_base(viagem_id: int, db: Session = Depends(get_db)):
    viagem = db.get(models.ViagemBase, viagem_id)
    if viagem is None:
        raise HTTPException(status_code=404, detail=f"Viagem {viagem_id} nao encontrada")
    dia_semana = viagem.grupo.dia_semana
    remover_viagem(db, viagem_id)
    return montar_estrutura_base(db, dia_semana)


@router.patch("/viagens/{viagem_id}/hora", response_model=schemas.EstruturaBaseRead)
def alterar_hora_viagem_base(viagem_id: int, payload: schemas.ViagemBaseAlterarHora, db: Session = Depends(get_db)):
    viagem = db.get(models.ViagemBase, viagem_id)
    if viagem is None:
        raise HTTPException(status_code=404, detail=f"Viagem {viagem_id} nao encontrada")
    dia_semana = viagem.grupo.dia_semana
    try:
        alterar_hora_viagem(db, viagem_id, payload.hora)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    return montar_estrutura_base(db, dia_semana)


@router.patch("/membros/{agenda_trecho_id}/mover", response_model=schemas.EstruturaBaseRead)
def mover_membro_base(agenda_trecho_id: int, payload: schemas.MembroBaseMover, db: Session = Depends(get_db)):
    try:
        dia_semana = mover_membro(
            db, agenda_trecho_id, payload.grupo_base_id, payload.hora, payload.ordem
        )
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    return montar_estrutura_base(db, dia_semana)


@router.delete("/membros/{membro_id}", response_model=schemas.EstruturaBaseRead)
def remover_membro_base(membro_id: int, db: Session = Depends(get_db)):
    membro = db.get(models.MembroViagemBase, membro_id)
    if membro is None:
        raise HTTPException(status_code=404, detail=f"Membro {membro_id} nao encontrado")
    dia_semana = membro.viagem.grupo.dia_semana
    remover_membro(db, membro_id)
    return montar_estrutura_base(db, dia_semana)
