"""Unit tests for printers.services.collector."""

from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase

from printers.models import Printer, TonerReading
from printers.services.collector import collect_printer, collect_all_active
from printers.services.snmp_client import SnmpTonerResult
from printers.services.http_client import HttpTonerResult


def _make_printer(**kwargs) -> Printer:
    defaults = {"name": "TestPrinter", "ip_address": "10.0.0.1", "snmp_community": "public"}
    defaults.update(kwargs)
    return Printer(**defaults)


@pytest.mark.django_db
class TestCollectPrinter(TestCase):
    def setUp(self):
        self.printer = Printer.objects.create(
            name="HP408", ip_address="192.168.1.1", protocol=Printer.Protocol.AUTO
        )

    @patch("printers.services.collector._collect_snmp")
    def test_snmp_success_saves_reading(self, mock_snmp):
        mock_snmp.return_value = SnmpTonerResult(success=True, black_pct=75)
        result = collect_printer(self.printer)
        assert result.success is True
        assert result.protocol_used == "snmp"
        assert TonerReading.objects.filter(printer=self.printer, success=True).exists()

    @patch("printers.services.collector._collect_http")
    @patch("printers.services.collector._collect_snmp")
    def test_auto_falls_back_to_http_when_snmp_fails(self, mock_snmp, mock_http):
        mock_snmp.return_value = SnmpTonerResult(success=False, error="timeout")
        mock_http.return_value = HttpTonerResult(success=True, black_pct=60)
        result = collect_printer(self.printer)
        assert result.success is True
        assert result.protocol_used == "http"

    @patch("printers.services.collector._collect_http")
    @patch("printers.services.collector._collect_snmp")
    def test_both_fail_saves_failed_reading(self, mock_snmp, mock_http):
        mock_snmp.return_value = SnmpTonerResult(success=False, error="no route")
        mock_http.return_value = HttpTonerResult(success=False, error="connection refused")
        result = collect_printer(self.printer)
        assert result.success is False
        assert TonerReading.objects.filter(printer=self.printer, success=False).exists()

    @patch("printers.services.collector._collect_snmp")
    def test_snmp_protocol_only_calls_snmp(self, mock_snmp):
        self.printer.protocol = Printer.Protocol.SNMP
        self.printer.save()
        mock_snmp.return_value = SnmpTonerResult(success=True, black_pct=50)
        result = collect_printer(self.printer)
        assert mock_snmp.called
        assert result.protocol_used == "snmp"

    @patch("printers.services.collector._collect_http")
    def test_http_protocol_only_calls_http(self, mock_http):
        self.printer.protocol = Printer.Protocol.HTTP
        self.printer.save()
        mock_http.return_value = HttpTonerResult(success=True, black_pct=40)
        result = collect_printer(self.printer)
        assert mock_http.called
        assert result.protocol_used == "http"


@pytest.mark.django_db
class TestCollectAllActive(TestCase):
    @patch("printers.services.collector.collect_printer")
    def test_collects_only_active_printers(self, mock_collect):
        Printer.objects.create(name="Active", ip_address="10.0.0.1", is_active=True)
        Printer.objects.create(name="Inactive", ip_address="10.0.0.2", is_active=False)
        mock_collect.return_value = MagicMock(success=True)
        results = collect_all_active()
        assert len(results) == 1

    @patch("printers.services.collector.collect_printer")
    def test_exception_in_printer_does_not_stop_others(self, mock_collect):
        Printer.objects.create(name="P1", ip_address="10.0.0.1", is_active=True)
        Printer.objects.create(name="P2", ip_address="10.0.0.2", is_active=True)
        mock_collect.side_effect = [Exception("crash"), MagicMock(success=True)]
        results = collect_all_active()
        assert len(results) == 2
        assert results[0].success is False
        assert results[1].success is True
