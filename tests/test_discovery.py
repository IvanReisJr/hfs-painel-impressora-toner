"""Unit tests for printers.services.discovery."""

from unittest.mock import MagicMock, patch

import pytest

from printers.services.discovery import (
    DiscoveryResult,
    _extract_field_after_label,
    _extract_xml_text,
    _http_device_info,
    _http_probe,
    _tcp_port_open,
    scan_ip,
    scan_range,
)

# Shorthand for the 4-tuple _snmp_probe now returns
_SNMP_EMPTY   = (False, "", "", "")
_SNMP_HP_ONLY = (True, "HP LaserJet 408", "HP408", "")
_SNMP_WITH_LOC = (True, "HP LaserJet MFP E42540", "HP MFP", "DP 3 ANDAR")


# ---------------------------------------------------------------------------
# TCP port check
# ---------------------------------------------------------------------------

class TestTcpPortOpen:
    @patch("printers.services.discovery.socket.create_connection")
    def test_returns_true_when_port_open(self, mock_conn):
        mock_conn.return_value.__enter__ = MagicMock(return_value=None)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        assert _tcp_port_open("10.0.0.1", 80) is True

    @patch("printers.services.discovery.socket.create_connection", side_effect=OSError)
    def test_returns_false_when_port_closed(self, _):
        assert _tcp_port_open("10.0.0.1", 80) is False


# ---------------------------------------------------------------------------
# HTML / XML field extractors
# ---------------------------------------------------------------------------

class TestExtractFieldAfterLabel:
    def test_extracts_value_attribute(self):
        html = '<label>Localização do dispositivo</label><input value="DP 3 ANDAR"/>'
        assert _extract_field_after_label(html, ["Localização do dispositivo"]) == "DP 3 ANDAR"

    def test_extracts_text_content(self):
        html = '<td>Device Location</td><td>Sala TI</td>'
        assert _extract_field_after_label(html, ["Device Location"]) == "Sala TI"

    def test_returns_empty_when_not_found(self):
        html = "<html><body>nothing here</body></html>"
        assert _extract_field_after_label(html, ["Location"]) == ""

    def test_tries_multiple_labels_in_order(self):
        html = '<label>Location</label><input value="2nd Floor"/>'
        result = _extract_field_after_label(html, ["Localização do dispositivo", "Location"])
        assert result == "2nd Floor"


class TestExtractXmlText:
    def test_extracts_tag_text(self):
        xml = "<root><DeviceLocation>Sala RH</DeviceLocation></root>"
        assert _extract_xml_text(xml, ["DeviceLocation"]) == "Sala RH"

    def test_case_insensitive(self):
        xml = "<root><devicelocation>TI</devicelocation></root>"
        assert _extract_xml_text(xml, ["DeviceLocation"]) == "TI"

    def test_returns_empty_when_not_found(self):
        assert _extract_xml_text("<root/>", ["DeviceLocation"]) == ""

    def test_tries_multiple_tags(self):
        xml = "<root><SystemLocation>Andar 2</SystemLocation></root>"
        assert _extract_xml_text(xml, ["DeviceLocation", "SystemLocation"]) == "Andar 2"


# ---------------------------------------------------------------------------
# HTTP device info scraper
# ---------------------------------------------------------------------------

class TestHttpDeviceInfo:
    @patch("printers.services.discovery.requests.Session")
    def test_extracts_location_from_ews_html(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        html = (
            "<html><body>hp"
            '<label>Localização do dispositivo</label>'
            '<input value="DP 3 ANDAR"/>'
            "</body></html>"
        )
        mock_session.get.return_value = MagicMock(status_code=200, text=html)
        location, alias, serial = _http_device_info("10.0.0.1", timeout=3)
        assert location == "DP 3 ANDAR"

    @patch("printers.services.discovery.requests.Session")
    def test_extracts_location_from_xml(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        def side_effect(url, **kwargs):
            if "DeviceInformation" in url:
                raise Exception("not found")
            return MagicMock(
                status_code=200,
                text="<root><DeviceLocation>Sala TI</DeviceLocation></root>",
            )

        mock_session.get.side_effect = side_effect
        location, _, _ = _http_device_info("10.0.0.1", timeout=3)
        assert location == "Sala TI"

    @patch("printers.services.discovery.requests.Session")
    def test_returns_empty_when_no_device_info(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = Exception("refused")
        location, alias, serial = _http_device_info("10.0.0.1", timeout=3)
        assert location == ""
        assert alias == ""
        assert serial == ""


# ---------------------------------------------------------------------------
# HTTP probe
# ---------------------------------------------------------------------------

class TestHttpProbe:
    @patch("printers.services.discovery.requests.Session")
    def test_detects_hp_from_sws_json(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"ProductName": "HP LaserJet 408"},
        )
        is_hp, is_color, name, model = _http_probe("10.0.0.1", timeout=3)
        assert is_hp is True
        assert name == "HP LaserJet 408"

    @patch("printers.services.discovery.requests.Session")
    def test_detects_color_printer(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"ProductName": "HP Color LaserJet M452"},
        )
        _, is_color, _, _ = _http_probe("10.0.0.1", timeout=3)
        assert is_color is True

    @patch("printers.services.discovery.requests.Session")
    def test_falls_back_to_ews_page_title(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        def side_effect(url, **kwargs):
            if "sws/app" in url:
                raise Exception("not found")
            return MagicMock(
                status_code=200,
                text="<html><title>HP LaserJet 408dn</title><body>hp ews</body></html>",
                headers={"Server": "HP HTTP Server"},
            )

        mock_session.get.side_effect = side_effect
        is_hp, _, name, _ = _http_probe("10.0.0.1", timeout=3)
        assert is_hp is True
        assert "HP LaserJet" in name

    @patch("printers.services.discovery.requests.Session")
    def test_non_hp_device_returns_false(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(side_effect=Exception("not json")),
            text="<html><title>Router</title></html>",
            headers={"Server": "nginx"},
        )
        is_hp, _, _, _ = _http_probe("10.0.0.1", timeout=3)
        assert is_hp is False

    @patch("printers.services.discovery.requests.Session")
    def test_all_requests_fail_returns_false(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = Exception("connection refused")
        is_hp, _, _, _ = _http_probe("10.0.0.1", timeout=3)
        assert is_hp is False


# ---------------------------------------------------------------------------
# scan_ip — uses new 4-tuple _snmp_probe and _http_device_info
# ---------------------------------------------------------------------------

class TestScanIp:
    @patch("printers.services.discovery._snmp_probe", return_value=_SNMP_EMPTY)
    @patch("printers.services.discovery._http_device_info", return_value=("Sala TI", "", ""))
    @patch("printers.services.discovery._http_probe", return_value=(True, False, "HP LaserJet 408", "HP LaserJet 408"))
    @patch("printers.services.discovery._tcp_port_open", return_value=True)
    def test_hp_found_via_http_with_location(self, _, __, _device, ___):
        result = scan_ip("10.0.0.1")
        assert result.is_hp is True
        assert result.name == "HP LaserJet 408"
        assert result.location == "Sala TI"

    @patch("printers.services.discovery._snmp_probe", return_value=_SNMP_WITH_LOC)
    @patch("printers.services.discovery._http_device_info", return_value=("", "", ""))
    @patch("printers.services.discovery._http_probe", return_value=(False, False, "", ""))
    @patch("printers.services.discovery._tcp_port_open", return_value=True)
    def test_snmp_location_fills_location_field(self, _, __, ___, ____):
        result = scan_ip("10.0.0.1")
        assert result.location == "DP 3 ANDAR"
        assert result.snmp_responds is True

    @patch("printers.services.discovery._snmp_probe", return_value=_SNMP_WITH_LOC)
    @patch("printers.services.discovery._http_device_info", return_value=("DP 3 ANDAR EWS", "", ""))
    @patch("printers.services.discovery._http_probe", return_value=(True, False, "HP MFP", "HP MFP"))
    @patch("printers.services.discovery._tcp_port_open", return_value=True)
    def test_http_location_takes_priority_over_snmp(self, _, __, ___, ____):
        """HTTP device info is set first; SNMP only fills if empty."""
        result = scan_ip("10.0.0.1")
        assert result.location == "DP 3 ANDAR EWS"

    @patch("printers.services.discovery._snmp_probe", return_value=(True, "HP LaserJet Enterprise", "HP", ""))
    @patch("printers.services.discovery._http_device_info", return_value=("", "", ""))
    @patch("printers.services.discovery._http_probe", return_value=(False, False, "", ""))
    @patch("printers.services.discovery._tcp_port_open", side_effect=lambda ip, port, *a: port == 161)
    def test_snmp_only_printer(self, _, __, ___, ____):
        result = scan_ip("10.0.0.1")
        assert result.snmp_responds is True
        assert result.is_hp is True
        assert result.protocol == "snmp"

    @patch("printers.services.discovery._snmp_probe", return_value=_SNMP_HP_ONLY)
    @patch("printers.services.discovery._http_device_info", return_value=("", "", ""))
    @patch("printers.services.discovery._http_probe", return_value=(True, False, "HP LaserJet", "HP LaserJet"))
    @patch("printers.services.discovery._tcp_port_open", return_value=True)
    def test_both_protocols_sets_auto(self, _, __, ___, ____):
        result = scan_ip("10.0.0.1")
        assert result.protocol == "auto"

    @patch("printers.services.discovery._tcp_port_open", return_value=False)
    def test_no_open_ports_returns_empty_result(self, _):
        result = scan_ip("10.0.0.1")
        assert result.is_printer is False
        assert result.is_hp is False

    @patch("printers.services.discovery._snmp_probe", return_value=_SNMP_EMPTY)
    @patch("printers.services.discovery._http_device_info", return_value=("", "", "SN123"))
    @patch("printers.services.discovery._http_probe", return_value=(True, False, "", ""))
    @patch("printers.services.discovery._tcp_port_open", return_value=True)
    def test_serial_filled_from_http_device_info(self, _, __, ___, ____):
        result = scan_ip("10.0.0.1")
        assert result.serial == "SN123"

    @patch("printers.services.discovery._snmp_probe", return_value=_SNMP_EMPTY)
    @patch("printers.services.discovery._http_device_info", return_value=("", "", ""))
    @patch("printers.services.discovery._http_probe", return_value=(True, True, "", ""))
    @patch("printers.services.discovery._tcp_port_open", return_value=True)
    def test_fallback_name_uses_ip(self, _, __, ___, ____):
        result = scan_ip("192.168.1.55")
        assert "192.168.1.55" in result.name


# ---------------------------------------------------------------------------
# scan_range
# ---------------------------------------------------------------------------

class TestScanRange:
    @patch("printers.services.discovery.scan_ip")
    def test_scans_all_hosts_in_range(self, mock_scan):
        mock_scan.return_value = DiscoveryResult(ip="10.0.0.1", is_hp=True)
        scan_range(["10.0.0.0/30"])  # 2 usable hosts: .1 and .2
        assert mock_scan.call_count == 2

    @patch("printers.services.discovery.scan_ip")
    def test_only_hp_filters_non_hp(self, mock_scan):
        def side(ip, timeout=3):
            return DiscoveryResult(ip=ip, is_hp=(ip == "10.0.0.1"))
        mock_scan.side_effect = side
        results = scan_range(["10.0.0.0/30"], only_hp=True)
        assert all(r.is_hp for r in results)
        assert len(results) == 1

    @patch("printers.services.discovery.scan_ip")
    def test_results_sorted_by_ip(self, mock_scan):
        mock_scan.side_effect = lambda ip, timeout=3: DiscoveryResult(ip=ip, is_hp=True)
        results = scan_range(["10.0.0.0/30"], only_hp=False)
        ips = [r.ip for r in results]
        assert ips == sorted(ips, key=lambda x: tuple(int(p) for p in x.split(".")))

    def test_invalid_network_returns_empty(self):
        assert scan_range(["not-a-network"]) == []

    @patch("printers.services.discovery.scan_ip", side_effect=Exception("crash"))
    def test_exception_in_single_ip_does_not_stop_scan(self, _):
        results = scan_range(["10.0.0.0/30"], only_hp=False)
        assert isinstance(results, list)
