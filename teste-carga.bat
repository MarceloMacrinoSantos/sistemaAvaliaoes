@echo off
REM Teste geral: 66 alunos fazendo uma prova ao mesmo tempo no sistema publicado.
REM Cria dados de TESTE separados (logins T+RM) e apaga tudo no final. Nao mexe nos alunos reais.
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul || (echo Instale o Python em https://www.python.org/downloads/ & pause & exit /b 1)
set URL=https://sistema-avaliacoes.onrender.com
set /p URL2=  Endereco do sistema [Enter = %URL%]: 
if not "%URL2%"=="" set URL=%URL2%
set /p LOGIN=  Seu login de professor: 
set /p SENHA=  Sua senha: 
python teste-carga\teste_carga.py "%URL%" "%LOGIN%" "%SENHA%"
pause
