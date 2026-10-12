@echo off
REM Coloca o sistema na internet (link https://...trycloudflare.com) sem precisar liberar Firewall ou rede.
cd /d "%~dp0"
start "Sistema de Avaliacoes" cmd /k iniciar.bat
python backend\tunel.py
pause
