"""CollectorService: orchestrates toner collection for all active printers.

Strategy per printer:
  - Protocol.SNMP  → SNMP only
  - Protocol.HTTP  → HTTP/EWS only
  - Protocol.AUTO  → try SNMP first, fallback to HTTP
"""

import logging
from dataclasses import dataclass

from django.conf import settings

from printers.models import Printer, TonerReading
from printers.services import snmp_client, http_client

logger = logging.getLogger(__name__)


@dataclass
class CollectionResult:
    printer_id: int
    printer_name: str
    success: bool
    protocol_used: str
    error: str = ""


def _collect_snmp(printer: Printer) -> snmp_client.SnmpTonerResult:
    return snmp_client.fetch_toner(
        ip=printer.ip_address,
        community=printer.snmp_community,
        timeout=getattr(settings, "SNMP_TIMEOUT", 3),
        retries=getattr(settings, "SNMP_RETRIES", 1),
    )


def _collect_http(printer: Printer) -> http_client.HttpTonerResult:
    return http_client.fetch_toner(
        ip=printer.ip_address,
        timeout=getattr(settings, "HTTP_TIMEOUT", 5),
    )


def _save_reading(printer: Printer, result, protocol: str) -> TonerReading:
    is_color = printer.is_color
    return TonerReading.objects.create(
        printer=printer,
        black_pct=getattr(result, "black_pct", None),
        cyan_pct=getattr(result, "cyan_pct", None) if is_color else None,
        magenta_pct=getattr(result, "magenta_pct", None) if is_color else None,
        yellow_pct=getattr(result, "yellow_pct", None) if is_color else None,
        protocol_used=protocol,
        success=result.success,
        error_message=getattr(result, "error", ""),
    )


def collect_printer(printer: Printer) -> CollectionResult:
    """Collects toner data for a single printer and persists the reading."""
    protocol_used = ""

    if printer.protocol == Printer.Protocol.SNMP:
        result = _collect_snmp(printer)
        protocol_used = "snmp"

    elif printer.protocol == Printer.Protocol.HTTP:
        result = _collect_http(printer)
        protocol_used = "http"

    else:  # AUTO
        snmp_result = _collect_snmp(printer)
        if snmp_result.success:
            result = snmp_result
            protocol_used = "snmp"
        else:
            logger.debug(
                "SNMP failed for %s (%s), trying HTTP fallback",
                printer.name,
                printer.ip_address,
            )
            result = _collect_http(printer)
            protocol_used = "http"

    _save_reading(printer, result, protocol_used)

    return CollectionResult(
        printer_id=printer.pk,
        printer_name=printer.name,
        success=result.success,
        protocol_used=protocol_used,
        error=getattr(result, "error", ""),
    )


def collect_all_active() -> list[CollectionResult]:
    """Runs collection for every active printer. Returns list of results."""
    printers = Printer.objects.filter(is_active=True)
    results = []
    for printer in printers:
        try:
            results.append(collect_printer(printer))
        except Exception as exc:
            logger.error("Unexpected error collecting %s: %s", printer.name, exc)
            results.append(
                CollectionResult(
                    printer_id=printer.pk,
                    printer_name=printer.name,
                    success=False,
                    protocol_used="",
                    error=str(exc),
                )
            )
    return results
