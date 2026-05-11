@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d C:\IvanReis\Paineis\HFS_PAINEL_IMPRESSORA_TONER

echo ============================================================
echo  HFS - Coleta Automatica de Toner
echo  %DATE% %TIME%
echo ============================================================

echo.
echo [1/4] Descobrindo impressoras na rede 192.168.100.0/22...
.\venv\Scripts\python manage.py descobrir_impressoras 192.168.100.0/22 --saida impressoras_descobertas.csv
if %ERRORLEVEL% NEQ 0 echo AVISO: Falha na descoberta. Continuando com impressoras ja cadastradas.

echo.
echo [2/4] Importando novas impressoras encontradas...
.\venv\Scripts\python manage.py importar_impressoras impressoras_descobertas.csv --atualizar
if %ERRORLEVEL% NEQ 0 echo AVISO: Falha na importacao.

echo.
echo [3/4] Coletando niveis de toner de todas as impressoras...
.\venv\Scripts\python manage.py collect_toner
if %ERRORLEVEL% NEQ 0 echo AVISO: Falha parcial na coleta.

echo.
echo [4/4] Gerando planilha Excel para verificacao...
set DATA=%DATE:~6,4%%DATE:~3,2%%DATE:~0,2%
.\venv\Scripts\python manage.py exportar_excel --saida "verificacao_toner_%DATA%.xlsx"
if %ERRORLEVEL% NEQ 0 echo AVISO: Falha ao gerar Excel.

echo.
echo ============================================================
echo  Concluido em %TIME%
echo  Planilha: verificacao_toner_%DATA%.xlsx
echo ============================================================
