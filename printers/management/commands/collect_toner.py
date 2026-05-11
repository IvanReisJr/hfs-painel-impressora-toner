"""Management command: python manage.py collect_toner [--ip IP]

Collects toner readings for all active printers (or a specific IP).
Can be scheduled via cron, Task Scheduler, or APScheduler.
"""

import logging

from django.core.management.base import BaseCommand, CommandError

from printers.models import Printer
from printers.services.collector import collect_all_active, collect_printer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Coleta níveis de toner de impressoras via SNMP ou HTTP"

    def add_arguments(self, parser):
        parser.add_argument(
            "--ip",
            type=str,
            default=None,
            help="Coleta somente a impressora com este IP (opcional)",
        )

    def handle(self, *args, **options):
        ip_filter = options.get("ip")

        if ip_filter:
            try:
                printer = Printer.objects.get(ip_address=ip_filter, is_active=True)
            except Printer.DoesNotExist:
                raise CommandError(f"Impressora ativa com IP {ip_filter!r} não encontrada.")

            result = collect_printer(printer)
            results = [result]
        else:
            results = collect_all_active()

        total = len(results)
        ok = sum(1 for r in results if r.success)
        fail = total - ok

        self.stdout.write(f"\nColeta finalizada: {total} impressoras")
        self.stdout.write(self.style.SUCCESS(f"  Sucesso : {ok}"))
        if fail:
            self.stdout.write(self.style.ERROR(f"  Falha   : {fail}"))

        for r in results:
            if not r.success:
                self.stdout.write(
                    self.style.WARNING(f"  [FALHA] {r.printer_name}: {r.error}")
                )
