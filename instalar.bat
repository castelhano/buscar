@echo off
setlocal

rem Atualiza o codigo antes de instalar. Tudo fica dentro de um bloco ( )
rem porque o cmd le o bloco inteiro antes de executar: se o pull alterar
rem este proprio arquivo, a execucao nao se perde. Depois do pull o script
rem chama a si mesmo (versao nova) com --sem-pull e nao volta pra ca.
if /i not "%~1"=="--sem-pull" (
    echo === Atualizando codigo ^(git pull^) ===
    where git >nul 2>nul
    if errorlevel 1 (
        echo Git nao encontrado no PATH. Seguindo com a versao atual.
    ) else (
        git -C "%~dp0." pull --ff-only
        if errorlevel 1 (
            echo.
            echo Nao foi possivel atualizar o codigo ^(sem internet ou alteracoes locais^).
            choice /m "Continuar a instalacao com a versao atual"
            if errorlevel 2 exit /b 1
        )
    )
    echo.
    "%~f0" --sem-pull
)

echo === Instalando backend ===
cd /d "%~dp0backend"

if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat
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
