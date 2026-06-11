#!/usr/bin/env python
r"""Script standalone de coleta de toner para HFS.

Não depende de BAT ou permissões administrativas.

Uso:
    python coletar.py
    python coletar.py --exportar
    venv\Scripts\python coletar.py
"""

import os
import sys
import json
import django
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hfs_toner.settings')
django.setup()

from django.core.management import call_command
from printers.models import Printer, TonerReading

STATUS_FILE = BASE_DIR / "coleta_status.json"


def _save_status(status: str, ok: int = 0, fail: int = 0, error: str = ""):
    """Salva status da coleta em arquivo JSON."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "ok": ok,
        "fail": fail,
        "total": ok + fail,
        "error": error,
    }
    try:
        STATUS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"Aviso: não foi possível salvar status: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Coleta de toner HFS")
    parser.add_argument(
        "--exportar",
        action="store_true",
        help="Gera planilha Excel após coleta"
    )
    args = parser.parse_args()

    print("=" * 70)
    print(f"HFS - Coleta Automática de Toner")
    print(f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S,%f')[:-3]}")
    print("=" * 70)

    # Salvar status: iniciando
    _save_status("em_progresso", ok=0, fail=0, error="Iniciando coleta...")

    # Coleta
    print("\n[1/2] Coletando níveis de toner de todas as impressoras...")
    try:
        from io import StringIO
        from contextlib import redirect_stdout

        # Capturar output do manage.py collect_toner
        output = StringIO()
        with redirect_stdout(output):
            call_command('collect_toner')

        # Extrair números (OK e Falha) da saída
        output_str = output.getvalue()
        print(output_str)

        # Tentar extrair OK e Falha do output
        ok = fail = 0
        for line in output_str.split('\n'):
            if 'Sucesso' in line:
                try:
                    ok = int(line.split(':')[1].strip())
                except:
                    pass
            elif 'Falha' in line:
                try:
                    fail = int(line.split(':')[1].strip())
                except:
                    pass
    except Exception as e:
        _save_status("erro", error=str(e))
        print(f"AVISO: Falha na coleta: {e}")
        return 1

    # Exportar (opcional)
    if args.exportar:
        print("\n[2/2] Gerando planilha Excel para verificação...")
        try:
            data = datetime.now().strftime("%Y%m%d")
            call_command(
                'exportar_excel',
                saida=f'verificacao_toner_{data}.xlsx'
            )
            _save_status("sucesso", ok=ok, fail=fail)
        except Exception as e:
            _save_status("erro_excel", ok=ok, fail=fail, error=str(e))
            print(f"AVISO: Falha ao gerar Excel: {e}")
            return 1
    else:
        _save_status("sucesso", ok=ok, fail=fail)

    print("\n" + "=" * 70)
    print(f"Concluído em {datetime.now().strftime('%H:%M:%S,%f')[:-3]}")
    print("[OK] Status salvo em: coleta_status.json")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
