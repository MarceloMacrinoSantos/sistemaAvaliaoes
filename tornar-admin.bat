@echo off
REM Torna um usuario ADMINISTRADOR (use se ninguem lembrar a senha do admin). Feche o sistema antes.
cd /d "%~dp0backend"
if exist .venv\Scripts\python.exe (set PY=.venv\Scripts\python.exe) else (set PY=python)
%PY% tornar_admin.py
echo.
set /p LOGIN=Digite o login que deve virar administrador: 
set /p SENHA=Nova senha (deixe vazio para manter a atual): 
%PY% tornar_admin.py %LOGIN% %SENHA%
pause
