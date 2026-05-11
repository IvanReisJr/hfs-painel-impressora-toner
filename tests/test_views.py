"""Unit tests for printers views."""

import json
from unittest.mock import patch

import pytest
from django.test import Client, TestCase
from django.urls import reverse

from printers.models import Printer, TonerReading


@pytest.mark.django_db
class TestDashboardView(TestCase):
    def setUp(self):
        self.client = Client()
        self.printer = Printer.objects.create(name="HP408", ip_address="192.168.1.1", is_active=True)

    def test_dashboard_returns_200(self):
        resp = self.client.get(reverse("printers:dashboard"))
        assert resp.status_code == 200

    def test_dashboard_shows_printer_name(self):
        resp = self.client.get(reverse("printers:dashboard"))
        assert b"HP408" in resp.content

    def test_dashboard_inactive_printer_not_shown(self):
        self.printer.is_active = False
        self.printer.save()
        resp = self.client.get(reverse("printers:dashboard"))
        assert b"HP408" not in resp.content

    def test_dashboard_context_has_summary_counts(self):
        resp = self.client.get(reverse("printers:dashboard"))
        assert "total" in resp.context
        assert "critical" in resp.context
        assert "warning" in resp.context


@pytest.mark.django_db
class TestPrinterDetailView(TestCase):
    def setUp(self):
        self.client = Client()
        self.printer = Printer.objects.create(name="HP408", ip_address="192.168.1.1")

    def test_detail_returns_200(self):
        resp = self.client.get(reverse("printers:printer_detail", args=[self.printer.pk]))
        assert resp.status_code == 200

    def test_detail_404_for_unknown_printer(self):
        resp = self.client.get(reverse("printers:printer_detail", args=[99999]))
        assert resp.status_code == 404

    def test_detail_context_has_chart_data(self):
        resp = self.client.get(reverse("printers:printer_detail", args=[self.printer.pk]))
        assert "chart_data_json" in resp.context
        data = json.loads(resp.context["chart_data_json"])
        assert "labels" in data


@pytest.mark.django_db
class TestApiStatus(TestCase):
    def setUp(self):
        self.client = Client()

    def test_returns_json(self):
        Printer.objects.create(name="HP1", ip_address="10.0.0.1", is_active=True)
        resp = self.client.get(reverse("printers:api_status"))
        assert resp.status_code == 200
        data = resp.json()
        assert "printers" in data
        assert data["total"] == 1

    def test_excludes_inactive_printers(self):
        Printer.objects.create(name="HP2", ip_address="10.0.0.2", is_active=False)
        resp = self.client.get(reverse("printers:api_status"))
        assert resp.json()["total"] == 0


@pytest.mark.django_db
class TestApiCollectNow(TestCase):
    def setUp(self):
        self.client = Client()
        self.printer = Printer.objects.create(name="HP408", ip_address="192.168.1.1", is_active=True)

    @patch("printers.views.collect_printer")
    def test_collect_now_returns_json(self, mock_collect):
        from printers.services.collector import CollectionResult
        mock_collect.return_value = CollectionResult(
            printer_id=self.printer.pk, printer_name="HP408",
            success=True, protocol_used="snmp"
        )
        resp = self.client.post(reverse("printers:api_collect_now", args=[self.printer.pk]))
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_collect_now_404_for_inactive(self):
        self.printer.is_active = False
        self.printer.save()
        resp = self.client.post(reverse("printers:api_collect_now", args=[self.printer.pk]))
        assert resp.status_code == 404
