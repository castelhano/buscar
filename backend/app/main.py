import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.routers import auth, contas, frequencia, usuarios, viagens
from app.routers.cadastros import (
    router_condutores,
    router_empresas,
    router_ferias,
    router_locais,
    router_locais_recesso,
    router_regioes,
    router_veiculos,
)

app = FastAPI(title="Buscar - Agendamento de Transporte")


def _mensagem_integridade(exc: IntegrityError) -> str:
    """Traduz a mensagem crua do sqlite3 (FK/UNIQUE/CHECK) numa mensagem
    apresentavel, sem precisar de tratamento manual em cada endpoint.
    """
    origem = str(getattr(exc, "orig", exc))
    if "FOREIGN KEY constraint failed" in origem or "NOT NULL constraint failed" in origem:
        # SQLAlchemy tenta anular a FK do filho ao deletar o pai (sem cascade
        # configurado); como a coluna e NOT NULL, o sqlite recusa a UPDATE.
        return "Nao e possivel concluir a operacao: existem registros vinculados a este item."
    if "UNIQUE constraint failed" in origem:
        return "Ja existe um registro com esses mesmos valores."
    if "CHECK constraint failed" in origem:
        return "Os valores informados nao atendem as regras de validacao."
    return "A operacao viola uma regra de integridade do banco de dados."


@app.exception_handler(IntegrityError)
def _handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": _mensagem_integridade(exc)})

_origens_padrao = "http://localhost:5173,http://127.0.0.1:5173"
_origens = os.environ.get("BUSCAR_CORS_ORIGINS", _origens_padrao).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origens,
    allow_methods=["*"],
    allow_headers=["*"],
    # sem isso o fetch() do frontend nao consegue ler Content-Disposition
    # (downloads autenticados precisam do header pra nomear o arquivo).
    expose_headers=["Content-Disposition"],
)

app.include_router(auth.router)
app.include_router(contas.router)
app.include_router(router_regioes)
app.include_router(router_locais)
app.include_router(router_locais_recesso)
app.include_router(router_empresas)
app.include_router(router_veiculos)
app.include_router(router_condutores)
app.include_router(router_ferias)
app.include_router(usuarios.router)
app.include_router(viagens.router)
app.include_router(frequencia.router)


@app.get("/health")
def health():
    return {"status": "ok"}
