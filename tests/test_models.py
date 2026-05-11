"""Unit tests for printers models."""

import pytest
from django.test import TestCase

from printers.models import Printer, TonerReading


@pytest.mark.django_db
class TestPrinterModel(TestCase):
    def setUp(self):
        self.printer = Printer.objects.create(
            name="HP LaserJet 408",
            ip_address="192.168.1.10",
            location="Sala TI",
        )

    def test_str_representation(self):
        assert "HP LaserJet 408" in str(self.printer)
        assert "192.168.1.10" in str(self.printer)

    def test_latest_reading_none_when_no_readings(self):
        assert self.printer.latest_reading is None

    def test_latest_reading_returns_most_recent_success(self):
        TonerReading.objects.create(printer=self.printer, black_pct=80, success=True)
        reading = TonerReading.objects.create(printer=self.printer, black_pct=50, success=True)
        assert self.printer.latest_reading.pk == reading.pk

    def test_latest_reading_ignores_failures(self):
        TonerReading.objects.create(printer=self.printer, success=False)
        assert self.printer.latest_reading is None

    def test_default_protocol_is_auto(self):
        assert self.printer.protocol == Printer.Protocol.AUTO

    def test_default_is_active(self):
        assert self.printer.is_active is True


@pytest.mark.django_db
class TestTonerReadingModel(TestCase):
    def setUp(self):
        self.printer = Printer.objects.create(
            name="Test", ip_address="10.0.0.1", is_color=True
        )

    def test_alert_level_ok(self):
        r = TonerReading(printer=self.printer, black_pct=80, cyan_pct=70, success=True)
        assert r.alert_level == "ok"

    def test_alert_level_warning(self):
        r = TonerReading(printer=self.printer, black_pct=15, success=True)
        assert r.alert_level == "warning"

    def test_alert_level_critical(self):
        r = TonerReading(printer=self.printer, black_pct=5, success=True)
        assert r.alert_level == "critical"

    def test_alert_level_unknown_when_no_pct(self):
        r = TonerReading(printer=self.printer, success=False)
        assert r.alert_level == "unknown"

    def test_lowest_color_pct_uses_minimum(self):
        r = TonerReading(printer=self.printer, black_pct=90, cyan_pct=15, magenta_pct=80, yellow_pct=70)
        assert r.lowest_color_pct == 15

    def test_lowest_color_pct_none_when_all_null(self):
        r = TonerReading(printer=self.printer)
        assert r.lowest_color_pct is None

    def test_str_includes_printer_name(self):
        r = TonerReading.objects.create(printer=self.printer, black_pct=60, success=True)
        assert "Test" in str(r)
