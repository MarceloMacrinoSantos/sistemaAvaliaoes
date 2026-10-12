@echo off
setlocal
REM ================================================================
REM  Publica (ou atualiza) o sistema na sua VM da Oracle Cloud.
REM  Na primeira vez pergunta o IP da VM e o arquivo da chave (.key).
REM  Os dados que ja estao no servidor NUNCA sao apagados.
REM ================================================================
cd /d "%~dp0"
if exist publicar-oracle.cfg (for /f "usebackq tokens=1,* delims==" %%a in ("publicar-oracle.cfg") do set "%%a=%%b")
if "%IP%"=="" set /p IP=IP publico da VM (ex.: 129.146.10.20): 
if "%CHAVE%"=="" set /p CHAVE=Caminho do arquivo da chave privada (.key) - pode arrastar o arquivo para esta janela: 
set CHAVE=%CHAVE:"=%
(echo IP=%IP%& echo CHAVE=%CHAVE%)> publicar-oracle.cfg
REM o OpenSSH do Windows recusa chaves com permissao aberta
icacls "%CHAVE%" /inheritance:r /grant:r "%USERNAME%:R" >nul
echo.
echo [1/4] Empacotando o sistema...
tar --exclude=backend/.venv --exclude=frontend/node_modules --exclude=backend/avaliacoes.db* -czf "%TEMP%\avaliacoes.tgz" backend frontend deploy || goto erro
echo [2/4] Enviando para %IP%...
scp -i "%CHAVE%" -o StrictHostKeyChecking=accept-new "%TEMP%\avaliacoes.tgz" ubuntu@%IP%:/tmp/avaliacoes.tgz || goto erro
if exist backend\avaliacoes.db (
  echo [3/4] Enviando o banco deste computador (so e usado se o servidor ainda nao tiver dados^)...
  python -c "import sqlite3;c=sqlite3.connect(r'backend\avaliacoes.db');c.execute('PRAGMA wal_checkpoint(TRUNCATE)');c.close()" 2>nul
  scp -i "%CHAVE%" backend\avaliacoes.db ubuntu@%IP%:avaliacoes.db
) else echo [3/4] Sem banco local para enviar.
echo [4/4] Instalando no servidor (a primeira vez leva alguns minutos)...
ssh -i "%CHAVE%" ubuntu@%IP% "rm -rf ~/sistema-avaliacoes && mkdir -p ~/sistema-avaliacoes && tar xzf /tmp/avaliacoes.tgz -C ~/sistema-avaliacoes && sudo bash ~/sistema-avaliacoes/deploy/oracle/instalar.sh"
pause
exit /b 0
:erro
echo.
echo Algo deu errado. Confira o IP, o arquivo da chave e se a VM esta ligada.
del publicar-oracle.cfg 2>nul
pause
