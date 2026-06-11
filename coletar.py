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
import django
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hfs_toner.settings')
django.setup()

from django.core.management import call_command
from printers.models import Printer, TonerReading


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

    # Coleta
    print("\n[1/2] Coletando níveis de toner de todas as impressoras...")
    try:
        call_command('collect_toner')
    except Exception as e:
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
        except Exception as e:
            print(f"AVISO: Falha ao gerar Excel: {e}")
            return 1

    print("\n" + "=" * 70)
    print(f"Concluído em {datetime.now().strftime('%H:%M:%S,%f')[:-3]}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
