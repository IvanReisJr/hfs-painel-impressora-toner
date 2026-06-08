@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PGCLIENTENCODING=UTF8
set PGLANG=C
cd /d C:\Pietro\Projetos\HFS_PAINEL_IMPRESSORA_TONER\HFS_PAINEL_IMPRESSORA_TONER

echo ============================================================
echo  HFS - Coleta Automatica de Toner
echo  %DATE% %TIME%
echo ============================================================

echo.
echo [1/2] Coletando niveis de toner de todas as impressoras...
.\venv\Scripts\python manage.py collect_toner
if %ERRORLEVEL% NEQ 0 echo AVISO: Falha parcial na coleta.

echo.
echo [2/2] Gerando planilha Excel para verificacao...
set DATA=%DATE:~6,4%%DATE:~3,2%%DATE:~0,2%
.\venv\Scripts\python manage.py exportar_excel --saida "verificacao_toner_%DATA%.xlsx"
if %ERRORLEVEL% NEQ 0 echo AVISO: Falha ao gerar Excel.

echo.
echo ============================================================
echo  Concluido em %TIME%
echo  Planilha: verificacao_toner_%DATA%.xlsx
echo ============================================================
