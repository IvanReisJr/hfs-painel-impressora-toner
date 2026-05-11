@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d C:\IvanReis\Paineis\HFS_PAINEL_IMPRESSORA_TONER

echo ============================================================
echo  HFS - Atualizacao Manual de Localizacao e Toner
echo  %DATE% %TIME%
echo ============================================================

echo.
echo [1/3] Descobrindo impressoras e relendo localizacoes...
.\venv\Scripts\python manage.py descobrir_impressoras 192.168.100.0/22 --saida impressoras_descobertas.csv
if %ERRORLEVEL% NEQ 0 echo AVISO: Falha na descoberta.

echo.
echo [2/3] Atualizando localizacoes no banco...
.\venv\Scripts\python manage.py importar_impressoras impressoras_descobertas.csv --atualizar
if %ERRORLEVEL% NEQ 0 echo AVISO: Falha na importacao.

echo.
echo [3/3] Coletando niveis de toner atualizados...
.\venv\Scripts\python manage.py collect_toner
if %ERRORLEVEL% NEQ 0 echo AVISO: Falha parcial na coleta.

echo.
echo ============================================================
echo  Concluido em %TIME%
echo  Atualize o painel no navegador para ver os dados novos.
echo ============================================================
pause
