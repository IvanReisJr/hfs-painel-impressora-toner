"""Management command: python manage.py descobrir_impressoras <ranges> [opções]

Varre ranges de IP em busca de impressoras HP e gera um CSV pronto para importar.

Exemplos:
    # Varrer uma rede /24
    python manage.py descobrir_impressoras 192.168.103.0/24

    # Varrer múltiplas redes
    python manage.py descobrir_impressoras 192.168.103.0/24 192.168.100.0/24

    # Testar IPs específicos
    python manage.py descobrir_impressoras 192.168.103.88/32 192.168.100.173/32

    # Salvar resultado em arquivo diferente
    python manage.py descobrir_impressoras 192.168.1.0/24 --saida minha_rede.csv

    # Incluir todos os dispositivos que respondem (não só HP)
    python manage.py descobrir_impressoras 192.168.1.0/24 --todos

    # Ajustar paralelismo e timeout
    python manage.py descobrir_impressoras 192.168.1.0/24 --workers 100 --timeout 2
"""

import csv
import sys
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from printers.services.discovery import scan_range, DiscoveryResult

_DEFAULT_OUTPUT = "impressoras_descobertas.csv"
_CSV_FIELDNAMES = [
    "name", "ip_address", "location", "model_name",
    "protocol", "snmp_community", "is_color", "is_active", "serial",
]


def _result_to_csv_row(r: DiscoveryResult) -> dict:
    return {
        "name": r.name or f"Impressora {r.ip}",
        "ip_address": r.ip,
        "location": r.location,   # auto-filled from sysLocation / EWS page
        "model_name": r.model,
        "protocol": r.protocol,
        "snmp_community": "public",
        "is_color": "true" if r.is_color else "false",
        "is_active": "true",
        "serial": r.serial,
    }


def _write_csv(results: list[DiscoveryResult], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(_result_to_csv_row(r) for r in results)


class Command(BaseCommand):
    help = "Varre ranges de IP e gera CSV com impressoras HP encontradas"

    def add_arguments(self, parser):
        parser.add_argument(
            "ranges",
            nargs="+",
            type=str,
            help="Ranges de IP em notação CIDR. Ex: 192.168.1.0/24",
        )
        parser.add_argument(
            "--saida",
            type=str,
            default=_DEFAULT_OUTPUT,
            help=f"Arquivo CSV de saída (padrão: {_DEFAULT_OUTPUT})",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=50,
            help="Número de threads paralelas (padrão: 50)",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=3,
            help="Timeout por IP em segundos (padrão: 3)",
        )
        parser.add_argument(
            "--todos",
            action="store_true",
            default=False,
            help="Inclui todos os dispositivos que respondem, não só HP",
        )

    def handle(self, *args, **options):
        ranges = options["ranges"]
        output_path = Path(options["saida"])
        workers = options["workers"]
        timeout = options["timeout"]
        only_hp = not options["todos"]

        # Estimate total IPs
        total_ips = self._count_ips(ranges)
        self.stdout.write(
            f"\n[SCAN] Iniciando varredura de {total_ips} enderecos IP"
            f" em {len(ranges)} rede(s)..."
        )
        self.stdout.write(f"   Workers : {workers} threads paralelas")
        self.stdout.write(f"   Timeout : {timeout}s por IP")
        self.stdout.write(
            f"   Filtro  : {'somente HP' if only_hp else 'todos os dispositivos'}\n"
        )

        start = time.time()
        results = scan_range(
            networks=ranges,
            workers=workers,
            timeout=timeout,
            only_hp=only_hp,
        )
        elapsed = time.time() - start

        if not results:
            self.stdout.write(self.style.WARNING(
                "\nNenhuma impressora HP encontrada nos ranges informados.\n"
                "Dicas:\n"
                "  - Confirme que a maquina esta na mesma rede\n"
                "  - Tente --todos para ver todos os dispositivos que respondem\n"
                "  - Aumente --timeout se a rede for lenta\n"
            ))
            return

        _write_csv(results, output_path)

        self._print_table(results)
        self.stdout.write(
            self.style.SUCCESS(
                f"\n[OK] {len(results)} impressora(s) encontrada(s) em {elapsed:.1f}s"
            )
        )
        self.stdout.write(f"  CSV salvo em: {output_path.resolve()}\n")
        self.stdout.write(
            "  Proximo passo: revise o CSV (preencha 'location') e importe:\n"
            f"  python manage.py importar_impressoras {output_path}\n"
        )

    def _print_table(self, results: list[DiscoveryResult]) -> None:
        self.stdout.write(
            f"\n{'IP':<18} {'Nome / Modelo':<35} {'Localização':<22} {'Cor':<5} {'SNMP':<5} {'HTTP':<5} Proto"
        )
        self.stdout.write("-" * 100)
        for r in results:
            color    = "Sim" if r.is_color else "Não"
            snmp     = "✓" if r.snmp_responds else "✗"
            http     = "✓" if r.http_responds else "✗"
            name_col = (r.name or r.model or "—")[:33]
            loc_col  = (r.location or "—")[:20]
            self.stdout.write(
                f"{r.ip:<18} {name_col:<35} {loc_col:<22} {color:<5} {snmp:<5} {http:<5} {r.protocol}"
            )

    @staticmethod
    def _count_ips(ranges: list[str]) -> int:
        import ipaddress
        total = 0
        for net_str in ranges:
            try:
                net = ipaddress.ip_network(net_str.strip(), strict=False)
                total += net.num_addresses - (2 if net.prefixlen < 31 else 0)
            except ValueError:
                pass
        return total
