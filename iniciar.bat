@echo off
setlocal

cd /d "%~dp0backend"

if not exist .venv (
    echo Ambiente nao instalado. Rode instalar.bat primeiro.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

echo Aplicando migracoes do banco...
alembic upgrade head
if errorlevel 1 (
    echo Erro ao migrar o banco de dados.
    pause
    exit /b 1
)

start "Buscar - servidor" /min cmd /c ".venv\Scripts\activate.bat && uvicorn app.main:app --host 127.0.0.1 --port 8123"

timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:8123
