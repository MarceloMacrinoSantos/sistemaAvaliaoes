@echo off
REM Libera a porta 8000 no Firewall do Windows para os alunos acessarem o sistema.
REM De dois cliques e aceite a pergunta de administrador. So precisa fazer uma vez.
net session >nul 2>nul || (powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b)
netsh advfirewall firewall delete rule name="Sistema de Avaliacoes" >nul 2>nul
netsh advfirewall firewall add rule name="Sistema de Avaliacoes" dir=in action=allow protocol=TCP localport=8000 profile=any
echo.
echo Porta 8000 liberada no Firewall (redes publicas e privadas).
echo Agora rode o iniciar.bat e acesse pelos outros computadores.
pause
