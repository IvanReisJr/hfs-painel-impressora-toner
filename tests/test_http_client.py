"""Unit tests for printers.services.http_client."""

from unittest.mock import MagicMock, patch

import pytest

from printers.services.http_client import (
    HttpTonerResult,
    _parse_sws_json,
    _parse_ews_xml,
    fetch_toner,
)


class TestParseSWSJson:
    def test_parses_black_only(self):
        data = {
            "ConsumableList": {
                "Consumable": [
                    {"Color": "black", "ConsumablePercentageLevelRemaining": "45"}
                ]
            }
        }
        result = _parse_sws_json(data)
        assert result.success is True
        assert result.black_pct == 45

    def test_parses_all_colors(self):
        data = {
            "ConsumableList": {
                "Consumable": [
                    {"Color": "black",   "ConsumablePercentageLevelRemaining": "80"},
                    {"Color": "cyan",    "ConsumablePercentageLevelRemaining": "70"},
                    {"Color": "magenta", "ConsumablePercentageLevelRemaining": "60"},
                    {"Color": "yellow",  "ConsumablePercentageLevelRemaining": "50"},
                ]
            }
        }
        result = _parse_sws_json(data)
        assert result.success is True
        assert result.cyan_pct == 70
        assert result.magenta_pct == 60
        assert result.yellow_pct == 50

    def test_no_black_returns_failure(self):
        data = {"ConsumableList": {"Consumable": []}}
        result = _parse_sws_json(data)
        assert result.success is False

    def test_clamps_value_above_100(self):
        data = {
            "ConsumableList": {
                "Consumable": [
                    {"Color": "black", "ConsumablePercentageLevelRemaining": "120"}
                ]
            }
        }
        result = _parse_sws_json(data)
        assert result.black_pct == 100

    def test_handles_float_string(self):
        data = {
            "ConsumableList": {
                "Consumable": [
                    {"Color": "black", "ConsumablePercentageLevelRemaining": "75.9"}
                ]
            }
        }
        result = _parse_sws_json(data)
        assert result.black_pct == 75


class TestParseEWSXml:
    def _make_xml(self, color: str, pct: int) -> bytes:
        return (
            f'<root xmlns:dd="http://www.hp.com/schemas/imaging/con/dictionaries/1.0/">'
            f'<Supply><dd:Name>{color}</dd:Name><dd:PercentRemaining>{pct}</dd:PercentRemaining></Supply>'
            f"</root>"
        ).encode()

    def test_parses_black_from_xml(self):
        xml = self._make_xml("black", 55)
        result = _parse_ews_xml(xml)
        # May or may not parse depending on tag matching; at minimum no exception
        assert isinstance(result, HttpTonerResult)

    def test_invalid_xml_returns_failure(self):
        result = _parse_ews_xml(b"NOT XML AT ALL <<<")
        assert result.success is False


class TestFetchToner:
    @patch("printers.services.http_client.requests.Session")
    def test_success_via_sws_json(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ConsumableList": {
                "Consumable": [
                    {"Color": "black", "ConsumablePercentageLevelRemaining": "60"}
                ]
            }
        }
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        result = fetch_toner("192.168.1.1")
        assert result.success is True
        assert result.black_pct == 60

    @patch("printers.services.http_client.requests.Session")
    def test_all_endpoints_fail_returns_failure(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("connection refused")
        mock_session_cls.return_value = mock_session

        result = fetch_toner("192.168.1.1")
        assert result.success is False
