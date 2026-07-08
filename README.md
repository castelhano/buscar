# Buscar - Agendamento de Transporte

Aplicação composta por um backend em **FastAPI + SQLAlchemy + SQLite** e um
frontend em **React + Vite + TypeScript**.

## Estrutura do projeto

```
buscar/
├── backend/        # API FastAPI, modelos SQLAlchemy e migrações Alembic
└── frontend/        # SPA em React (Vite)
```

## Pré-requisitos

- Python 3.10+
- Node.js 20+ e npm
- Não é necessário instalar um servidor de banco de dados: o backend usa
  **SQLite**, com o arquivo de banco criado automaticamente em
  `backend/buscar.db`.

## Backend

### Dependências

Definidas em [`backend/requirements.txt`](backend/requirements.txt):

| Pacote     | Uso                                                        |
|------------|-------------------------------------------------------------|
| `fastapi`  | Framework web da API                                        |
| `uvicorn`  | Servidor ASGI usado para rodar a aplicação                  |
| `sqlalchemy` | ORM e acesso ao banco SQLite                               |
| `alembic`  | Migrações de schema do banco                                 |
| `reportlab`| Geração de relatórios/PDFs (usado em `app/services/exportacao.py`) |

`pydantic` é instalado automaticamente como dependência do `fastapi`.

### Instalação

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configuração (opcional)

Variáveis de ambiente reconhecidas pelo backend (todas opcionais, com padrão
sensato caso não sejam definidas):

| Variável               | Padrão                                              | Descrição                                   |
|------------------------|------------------------------------------------------|----------------------------------------------|
| `BUSCAR_DB_PATH`       | `backend/buscar.db`                                  | Caminho do arquivo SQLite                     |
| `BUSCAR_CORS_ORIGINS`  | `http://localhost:5173,http://127.0.0.1:5173`        | Origens permitidas no CORS (separadas por vírgula) |

### Migrações do banco

```bash
alembic upgrade head
```

Isso cria/atualiza o arquivo `buscar.db` com todas as tabelas necessárias.

### Rodando a API

```bash
uvicorn app.main:app --reload --port 8123
```

A API sobe em `http://127.0.0.1:8123` (porta escolhida para bater com o
padrão configurado no frontend — veja abaixo). Endpoint de health-check:
`GET /health`.

## Frontend

### Dependências principais

Definidas em [`frontend/package.json`](frontend/package.json):

| Pacote                  | Uso                                            |
|--------------------------|-------------------------------------------------|
| `react` / `react-dom`    | Biblioteca de UI                                |
| `react-router-dom`       | Roteamento SPA                                  |
| `@tanstack/react-query`  | Data fetching / cache de chamadas à API         |
| `@dnd-kit/*`             | Drag-and-drop (arraste de itens na interface)   |
| `vite`                   | Build tool / dev server                          |
| `typescript`             | Tipagem estática                                 |
| `oxlint`                 | Linter                                           |
| `playwright`             | Testes end-to-end                                |

### Instalação

```bash
cd frontend
npm install
```

### Configuração (opcional)

O frontend chama a API em `http://127.0.0.1:8123` por padrão
(`src/api/client.ts`). Para apontar para outro endereço, crie um arquivo
`frontend/.env`:

```
VITE_API_BASE=http://127.0.0.1:8123
```

### Rodando o frontend

```bash
npm run dev
```

Acesse `http://localhost:5173`.

## Passo a passo resumido (do zero)

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8123 &

# Frontend (em outro terminal)
cd frontend
npm install
npm run dev
```

Depois disso, abra `http://localhost:5173` no navegador.

## Outros comandos úteis

- Lint do frontend: `npm run lint`
- Build de produção do frontend: `npm run build`
- Nova migração de banco (após alterar `app/models.py`):
  ```bash
  alembic revision --autogenerate -m "descrição da mudança"
  alembic upgrade head
  ```
