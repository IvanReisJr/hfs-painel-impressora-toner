@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d C:\IvanReis\Paineis\HFS_PAINEL_IMPRESSORA_TONER

echo ============================================================
echo  HFS - Coleta Manual de Toner
echo  %DATE% %TIME%
echo ============================================================

echo.
echo [1/1] Coletando niveis de toner de todas as impressoras...
.\venv\Scripts\python manage.py collect_toner
if %ERRORLEVEL% NEQ 0 echo AVISO: Falha parcial na coleta.

echo.
echo ============================================================
echo  Concluido em %TIME%
echo  Atualize o painel no navegador para ver os dados novos.
echo ============================================================
pause
