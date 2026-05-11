"""Unit tests for printers.services.snmp_client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from printers.services.snmp_client import _calc_percent, SnmpTonerResult, fetch_toner


class TestCalcPercent:
    def test_normal_values(self):
        assert _calc_percent(50, 100) == 50

    def test_zero_current(self):
        assert _calc_percent(0, 100) == 0

    def test_full_cartridge(self):
        assert _calc_percent(100, 100) == 100

    def test_max_negative_two_returns_direct_pct(self):
        """When max == -2, the printer returns a raw percentage."""
        assert _calc_percent(75, -2) == 75

    def test_max_negative_two_clamps_to_100(self):
        assert _calc_percent(110, -2) == 100

    def test_max_negative_two_clamps_to_0(self):
        # When max==-2 (direct pct mode), negative current is still invalid → None
        assert _calc_percent(-5, -2) is None

    def test_invalid_max_zero_returns_none(self):
        assert _calc_percent(50, 0) is None

    def test_invalid_negative_current(self):
        assert _calc_percent(-1, 100) is None

    def test_rounds_correctly(self):
        assert _calc_percent(1, 3) == 33


class TestFetchTonerSNMP:
    @patch("printers.services.snmp_client.asyncio.run")
    def test_returns_result_object(self, mock_run):
        mock_run.return_value = SnmpTonerResult(success=True, black_pct=80)
        result = fetch_toner("192.168.1.1")
        assert result.success is True
        assert result.black_pct == 80

    @patch("printers.services.snmp_client.asyncio.run")
    def test_failure_returns_unsuccessful_result(self, mock_run):
        mock_run.return_value = SnmpTonerResult(success=False, error="timeout")
        result = fetch_toner("192.168.1.1")
        assert result.success is False
        assert "timeout" in result.error

    @patch("printers.services.snmp_client.asyncio.run")
    def test_color_printer_fills_all_slots(self, mock_run):
        mock_run.return_value = SnmpTonerResult(
            success=True, black_pct=90, cyan_pct=70, magenta_pct=60, yellow_pct=50
        )
        result = fetch_toner("192.168.1.1")
        assert result.cyan_pct == 70
        assert result.magenta_pct == 60
        assert result.yellow_pct == 50
