"""Management command: python manage.py importar_impressoras arquivo.csv

Importa impressoras a partir de um arquivo CSV.
Suporta criação de novas impressoras e atualização das existentes (upsert por IP).

Colunas obrigatórias: name, ip_address
Colunas opcionais  : location, model_name, protocol, snmp_community, is_color, is_active

Exemplo de uso:
    python manage.py importar_impressoras impressoras.csv
    python manage.py importar_impressoras impressoras.csv --atualizar
    python manage.py importar_impressoras impressoras.csv --dry-run
"""

import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from printers.models import Printer

_REQUIRED_COLUMNS = {"name", "ip_address"}

_BOOL_TRUE = {"1", "true", "sim", "yes", "s", "y"}

_PROTOCOL_MAP = {
    "auto": Printer.Protocol.AUTO,
    "snmp": Printer.Protocol.SNMP,
    "http": Printer.Protocol.HTTP,
}


@dataclass
class ImportRow:
    row_num: int
    name: str
    ip_address: str
    location: str = ""
    model_name: str = ""
    protocol: str = Printer.Protocol.AUTO
    snmp_community: str = "public"
    is_color: bool = False
    is_active: bool = True
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


@dataclass
class ImportSummary:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    invalid: int = 0


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in _BOOL_TRUE


def _parse_protocol(value: str) -> str:
    return _PROTOCOL_MAP.get(value.strip().lower(), Printer.Protocol.AUTO)


def _validate_row(row: ImportRow) -> None:
    if not row.name.strip():
        row.errors.append("'name' não pode ser vazio")
    if not row.ip_address.strip():
        row.errors.append("'ip_address' não pode ser vazio")


def _parse_csv_row(row_num: int, raw: dict[str, str]) -> ImportRow:
    """Converts a raw CSV dict into a typed ImportRow with validation."""
    parsed = ImportRow(
        row_num=row_num,
        name=raw.get("name", "").strip(),
        ip_address=raw.get("ip_address", "").strip(),
        location=raw.get("location", "").strip(),
        model_name=raw.get("model_name", "").strip(),
        protocol=_parse_protocol(raw.get("protocol", "auto")),
        snmp_community=raw.get("snmp_community", "public").strip() or "public",
        is_color=_parse_bool(raw.get("is_color", "false")),
        is_active=_parse_bool(raw.get("is_active", "true")),
    )
    _validate_row(parsed)
    return parsed


def _read_csv(path: Path) -> tuple[list[ImportRow], list[str]]:
    """Reads the CSV file and returns (rows, header_errors)."""
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        headers = set(reader.fieldnames or [])
        missing = _REQUIRED_COLUMNS - headers
        if missing:
            return [], [f"Colunas obrigatórias ausentes no CSV: {', '.join(sorted(missing))}"]

        rows = [_parse_csv_row(i + 2, row) for i, row in enumerate(reader)]
    return rows, []


def _apply_row(row: ImportRow, allow_update: bool) -> tuple[str, Printer]:
    """Creates or updates a Printer from a validated ImportRow.

    Returns ('created'|'updated'|'skipped', printer_instance).
    """
    defaults = {
        "name": row.name,
        "location": row.location,
        "model_name": row.model_name,
        "protocol": row.protocol,
        "snmp_community": row.snmp_community,
        "is_color": row.is_color,
        "is_active": row.is_active,
    }

    printer, created = Printer.objects.get_or_create(
        ip_address=row.ip_address,
        defaults=defaults,
    )

    if created:
        return "created", printer

    if not allow_update:
        return "skipped", printer

    for attr, value in defaults.items():
        setattr(printer, attr, value)
    printer.save()
    return "updated", printer


class Command(BaseCommand):
    help = "Importa impressoras a partir de um arquivo CSV (upsert por IP)"

    def add_arguments(self, parser):
        parser.add_argument(
            "arquivo",
            type=str,
            help="Caminho para o arquivo CSV",
        )
        parser.add_argument(
            "--atualizar",
            action="store_true",
            default=False,
            help="Atualiza impressoras já existentes (mesmo IP)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Simula a importação sem salvar no banco",
        )

    def handle(self, *args, **options):
        path = Path(options["arquivo"])
        allow_update = options["atualizar"]
        dry_run = options["dry_run"]

        if not path.exists():
            raise CommandError(f"Arquivo não encontrado: {path}")
        if path.suffix.lower() != ".csv":
            raise CommandError("O arquivo deve ter extensão .csv")

        rows, header_errors = _read_csv(path)
        if header_errors:
            for err in header_errors:
                self.stderr.write(self.style.ERROR(err))
            sys.exit(1)

        if not rows:
            self.stdout.write(self.style.WARNING("CSV está vazio — nenhuma impressora importada."))
            return

        # Report validation errors before touching the DB
        invalid_rows = [r for r in rows if not r.is_valid]
        if invalid_rows:
            self.stdout.write(self.style.ERROR(f"\n{len(invalid_rows)} linha(s) com erro:"))
            for r in invalid_rows:
                for err in r.errors:
                    self.stdout.write(self.style.ERROR(f"  Linha {r.row_num}: {err}"))
            self.stdout.write("")

        valid_rows = [r for r in rows if r.is_valid]
        summary = ImportSummary(invalid=len(invalid_rows))

        if dry_run:
            self._print_dry_run(valid_rows, allow_update)
            return

        with transaction.atomic():
            for row in valid_rows:
                action, _ = _apply_row(row, allow_update)
                if action == "created":
                    summary.created += 1
                elif action == "updated":
                    summary.updated += 1
                else:
                    summary.skipped += 1

        self._print_summary(summary, len(rows))

    def _print_dry_run(self, rows: list[ImportRow], allow_update: bool) -> None:
        self.stdout.write(self.style.WARNING("\n[DRY-RUN] Nenhuma alteração foi salva.\n"))
        existing_ips = set(
            Printer.objects.filter(
                ip_address__in=[r.ip_address for r in rows]
            ).values_list("ip_address", flat=True)
        )
        for row in rows:
            if row.ip_address in existing_ips:
                action = "ATUALIZAR" if allow_update else "IGNORAR (já existe)"
            else:
                action = "CRIAR"
            self.stdout.write(f"  [{action}] {row.name} — {row.ip_address}")
        self.stdout.write(f"\nTotal: {len(rows)} linha(s) válida(s)")

    def _print_summary(self, s: ImportSummary, total: int) -> None:
        self.stdout.write(f"\nImportação concluída — {total} linha(s) processada(s):")
        if s.created:
            self.stdout.write(self.style.SUCCESS(f"  [OK] Criadas     : {s.created}"))
        if s.updated:
            self.stdout.write(self.style.SUCCESS(f"  [OK] Atualizadas : {s.updated}"))
        if s.skipped:
            self.stdout.write(self.style.WARNING(f"  [--] Ignoradas (ja existem, use --atualizar): {s.skipped}"))
        if s.invalid:
            self.stdout.write(self.style.ERROR(f"  [ERRO] Invalidas : {s.invalid}"))
