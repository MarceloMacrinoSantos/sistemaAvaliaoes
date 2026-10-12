@echo off
REM Copia os dados deste computador (backend\avaliacoes.db) para o banco na internet (Neon/PostgreSQL).
REM Feche o sistema antes de rodar.
cd /d "%~dp0"
where python >nul 2>nul || (echo Instale o Python em https://www.python.org/downloads/ & pause & exit /b 1)
if not exist backend\.venv\Scripts\python.exe python -m venv backend\.venv
call backend\.venv\Scripts\activate.bat
pip install -q -r backend\requirements.txt
echo.
echo  Cole a "connection string" do Neon (comeca com postgresql://) e tecle Enter.
echo  Dica: no Neon, clique em Connect e copie o texto inteiro.
set /p DESTINO=  Endereco:
if "%DESTINO%"=="" (echo Nada informado. & pause & exit /b 1)
python backend\migrar_para_postgres.py "%DESTINO%"
if errorlevel 1 (
  echo.
  echo  Se apareceu "ja tem dados" e voce quer copiar de novo, apagando o que esta no Neon:
  echo     python backend\migrar_para_postgres.py "endereco" --substituir
)
pause
