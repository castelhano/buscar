@echo off
setlocal

echo === Instalando backend ===
cd /d "%~dp0backend"

if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo Erro ao criar/ativar o ambiente virtual do backend.
    pause
    exit /b 1
)

pip install -r requirements.txt
if errorlevel 1 (
    echo Erro ao instalar dependencias do backend.
    pause
    exit /b 1
)

alembic upgrade head
if errorlevel 1 (
    echo Erro ao migrar o banco de dados.
    pause
    exit /b 1
)

if not exist buscar.db (
    python -m app.seed
)

call deactivate

echo.
echo === Instalando frontend ===
cd /d "%~dp0frontend"

call npm install
if errorlevel 1 (
    echo Erro ao instalar dependencias do frontend.
    pause
    exit /b 1
)

call npm run build
if errorlevel 1 (
    echo Erro ao gerar o build do frontend.
    pause
    exit /b 1
)

echo.
echo Instalacao concluida. Use iniciar.bat para rodar o sistema.
pause
