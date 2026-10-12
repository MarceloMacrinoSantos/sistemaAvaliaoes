@echo off
REM Inicia o sistema na rede local (Windows). De dois cliques neste arquivo.
cd /d "%~dp0"
where python >nul 2>nul || (echo Instale o Python em https://www.python.org/downloads/ marcando "Add python.exe to PATH" & pause & exit /b 1)
REM O ambiente .venv nao funciona se a pasta foi copiada de outro computador: recria se estiver quebrado
if exist backend\.venv\Scripts\python.exe (
  backend\.venv\Scripts\python.exe -c "import fastapi" >nul 2>nul || rmdir /s /q backend\.venv
)
if not exist backend\.venv\Scripts\python.exe python -m venv backend\.venv
call backend\.venv\Scripts\activate.bat
pip install -q -r backend\requirements.txt
python backend\porta_livre.py || (pause & exit /b 1)
if not exist frontend\dist\index.html (
  cd frontend && call npm install && call npm run build && cd ..
)
for /f %%i in ('python backend\ip_local.py') do set IP=%%i
echo.
echo ==========================================================
echo  Sistema de Avaliacoes no ar!
echo  Neste computador:           http://localhost:8000
echo  Alunos (mesma rede/Wi-Fi):  http://%IP%:8000
echo  QR code para os alunos escanearem (ou abra http://localhost:8000/qrcode para projetar):
python backend\qr_terminal.py http://%IP%:8000/aluno
echo  Se o endereco acima nao abrir nos outros computadores, tente:
python backend\ip_local.py todos
echo  e rode UMA VEZ o liberar-firewall.bat (libera a porta 8000).
echo  Para encerrar: feche esta janela.
echo ==========================================================
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
