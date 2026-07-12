import datetime as dt
import os
import sqlite3
import tempfile

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.auth import obter_conta_atual
from app.database import DATABASE_PATH

router = APIRouter(prefix="/backup", tags=["backup"], dependencies=[Depends(obter_conta_atual)])


@router.get("")
def baixar_backup() -> FileResponse:
    """Devolve uma copia do banco inteiro pra download manual (usuario baixa
    e guarda onde quiser, ex: numa pasta de nuvem).

    Usa a API de backup nativa do sqlite3 (`Connection.backup`) em vez de
    copiar o arquivo `.db` cru -- com o banco em modo WAL, um copy simples as
    vezes perde dado ja commitado mas ainda so no `-wal` (que so e
    incorporado ao arquivo principal num checkpoint); a API de backup lida
    com isso corretamente mesmo com o servidor rodando.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    origem = sqlite3.connect(DATABASE_PATH)
    try:
        destino = sqlite3.connect(tmp.name)
        try:
            origem.backup(destino)
        finally:
            destino.close()
    finally:
        origem.close()

    nome_arquivo = f"buscar_backup_{dt.datetime.now().strftime('%Y-%m-%d_%H%M%S')}.db"
    return FileResponse(
        tmp.name,
        media_type="application/octet-stream",
        filename=nome_arquivo,
        background=BackgroundTask(os.unlink, tmp.name),
    )
