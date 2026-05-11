"""Unit tests for management command importar_impressoras."""

import csv
import tempfile
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import TestCase

from printers.models import Printer
from printers.management.commands.importar_impressoras import (
    _parse_bool,
    _parse_protocol,
    _parse_csv_row,
    _read_csv,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(rows: list[dict], path: Path, headers: list[str] | None = None) -> None:
    fieldnames = headers or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _minimal_row(**overrides) -> dict:
    base = {"name": "HP Test", "ip_address": "10.0.0.1"}
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Pure function tests (no DB)
# ---------------------------------------------------------------------------

class TestParseBool:
    def test_true_values(self):
        for v in ("1", "true", "True", "sim", "yes", "s", "y", "YES"):
            assert _parse_bool(v) is True, f"Expected True for {v!r}"

    def test_false_values(self):
        for v in ("0", "false", "False", "não", "no", "n", ""):
            assert _parse_bool(v) is False, f"Expected False for {v!r}"


class TestParseProtocol:
    def test_known_protocols(self):
        assert _parse_protocol("snmp") == Printer.Protocol.SNMP
        assert _parse_protocol("http") == Printer.Protocol.HTTP
        assert _parse_protocol("auto") == Printer.Protocol.AUTO

    def test_case_insensitive(self):
        assert _parse_protocol("SNMP") == Printer.Protocol.SNMP
        assert _parse_protocol("HTTP") == Printer.Protocol.HTTP

    def test_unknown_defaults_to_auto(self):
        assert _parse_protocol("unknown") == Printer.Protocol.AUTO
        assert _parse_protocol("") == Printer.Protocol.AUTO


class TestParseCsvRow:
    def test_minimal_valid_row(self):
        row = _parse_csv_row(2, {"name": "HP408", "ip_address": "192.168.1.1"})
        assert row.is_valid
        assert row.name == "HP408"
        assert row.ip_address == "192.168.1.1"
        assert row.snmp_community == "public"
        assert row.is_active is True
        assert row.is_color is False

    def test_full_row(self):
        raw = {
            "name": "HP Color",
            "ip_address": "10.0.0.5",
            "location": "Sala TI",
            "model_name": "HP 408dn",
            "protocol": "snmp",
            "snmp_community": "private",
            "is_color": "true",
            "is_active": "false",
        }
        row = _parse_csv_row(2, raw)
        assert row.is_valid
        assert row.is_color is True
        assert row.is_active is False
        assert row.snmp_community == "private"
        assert row.protocol == Printer.Protocol.SNMP

    def test_empty_name_is_invalid(self):
        row = _parse_csv_row(2, {"name": "", "ip_address": "10.0.0.1"})
        assert not row.is_valid
        assert any("name" in e for e in row.errors)

    def test_empty_ip_is_invalid(self):
        row = _parse_csv_row(2, {"name": "HP", "ip_address": ""})
        assert not row.is_valid
        assert any("ip_address" in e for e in row.errors)

    def test_missing_optional_fields_use_defaults(self):
        row = _parse_csv_row(2, {"name": "HP", "ip_address": "10.0.0.1"})
        assert row.location == ""
        assert row.model_name == ""
        assert row.protocol == Printer.Protocol.AUTO


class TestReadCsv:
    def test_missing_required_columns_returns_error(self, tmp_path):
        csv_file = tmp_path / "bad.csv"
        _write_csv([{"only_name": "HP"}], csv_file, headers=["only_name"])
        _, errors = _read_csv(csv_file)
        assert errors
        assert any("ip_address" in e for e in errors)

    def test_valid_csv_returns_rows(self, tmp_path):
        csv_file = tmp_path / "ok.csv"
        _write_csv([_minimal_row(), _minimal_row(name="HP2", ip_address="10.0.0.2")], csv_file)
        rows, errors = _read_csv(csv_file)
        assert not errors
        assert len(rows) == 2

    def test_handles_utf8_bom(self, tmp_path):
        csv_file = tmp_path / "bom.csv"
        content = "name,ip_address\nHP Test,10.0.0.1\n"
        csv_file.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
        rows, errors = _read_csv(csv_file)
        assert not errors
        assert rows[0].name == "HP Test"


# ---------------------------------------------------------------------------
# Integration tests (with DB)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestImportarImpressorasCommand(TestCase):
    def _csv(self, rows: list[dict]) -> str:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
        )
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(tmp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        tmp.flush()
        return tmp.name

    def test_creates_new_printers(self):
        path = self._csv([_minimal_row(), _minimal_row(name="HP2", ip_address="10.0.0.2")])
        call_command("importar_impressoras", path, verbosity=0)
        assert Printer.objects.count() == 2

    def test_does_not_duplicate_same_ip(self):
        path = self._csv([_minimal_row()])
        call_command("importar_impressoras", path, verbosity=0)
        call_command("importar_impressoras", path, verbosity=0)
        assert Printer.objects.count() == 1

    def test_atualizar_flag_updates_existing(self):
        Printer.objects.create(name="Old Name", ip_address="10.0.0.1")
        path = self._csv([_minimal_row(name="New Name")])
        call_command("importar_impressoras", path, "--atualizar", verbosity=0)
        assert Printer.objects.get(ip_address="10.0.0.1").name == "New Name"

    def test_without_atualizar_keeps_existing(self):
        Printer.objects.create(name="Old Name", ip_address="10.0.0.1")
        path = self._csv([_minimal_row(name="New Name")])
        call_command("importar_impressoras", path, verbosity=0)
        assert Printer.objects.get(ip_address="10.0.0.1").name == "Old Name"

    def test_dry_run_does_not_save(self):
        path = self._csv([_minimal_row()])
        call_command("importar_impressoras", path, "--dry-run", verbosity=0)
        assert Printer.objects.count() == 0

    def test_invalid_rows_are_skipped_valid_rows_saved(self):
        rows = [
            _minimal_row(),
            {"name": "", "ip_address": "10.0.0.2"},  # invalid
        ]
        path = self._csv(rows)
        call_command("importar_impressoras", path, verbosity=0)
        assert Printer.objects.count() == 1

    def test_is_color_and_protocol_are_saved_correctly(self):
        rows = [{"name": "Color HP", "ip_address": "10.0.0.5",
                 "is_color": "true", "protocol": "http",
                 "snmp_community": "private", "is_active": "false",
                 "location": "RH", "model_name": "M452"}]
        path = self._csv(rows)
        call_command("importar_impressoras", path, verbosity=0)
        p = Printer.objects.get(ip_address="10.0.0.5")
        assert p.is_color is True
        assert p.protocol == Printer.Protocol.HTTP
        assert p.snmp_community == "private"
        assert p.is_active is False
        assert p.location == "RH"
