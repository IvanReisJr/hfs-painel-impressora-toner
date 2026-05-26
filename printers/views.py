"""Views for HFS Printer Toner Dashboard."""

import json
import threading
from datetime import timedelta

from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt

from printers.models import Printer, TonerReading
from printers.services.collector import collect_printer, collect_all_active

# flags de controle para evitar execuções simultâneas
_collecting_all = False
_discovering    = False


@require_GET
def dashboard(request):
    """Main dashboard: all active printers with latest toner reading."""
    printers = Printer.objects.filter(is_active=True).prefetch_related("readings")

    rows = []
    for printer in printers:
        reading = printer.latest_reading
        rows.append({"printer": printer, "reading": reading})

    context = {
        "rows": rows,
        "total": len(rows),
        "critical": sum(1 for r in rows if r["reading"] and r["reading"].alert_level == "critical"),
        "warning": sum(1 for r in rows if r["reading"] and r["reading"].alert_level == "warning"),
        "no_data": sum(1 for r in rows if not r["reading"]),
    }
    return render(request, "printers/dashboard.html", context)


@require_GET
def printer_detail(request, pk: int):
    """Detail page: 30-day toner history chart for a single printer."""
    printer = get_object_or_404(Printer, pk=pk)
    since = timezone.now() - timedelta(days=30)
    readings = (
        printer.readings.filter(success=True, collected_at__gte=since)
        .order_by("collected_at")
        .values("collected_at", "black_pct", "cyan_pct", "magenta_pct", "yellow_pct")
    )

    labels = [r["collected_at"].strftime("%d/%m %H:%M") for r in readings]
    chart_data = {
        "labels": labels,
        "black": [r["black_pct"] for r in readings],
        "cyan": [r["cyan_pct"] for r in readings],
        "magenta": [r["magenta_pct"] for r in readings],
        "yellow": [r["yellow_pct"] for r in readings],
    }

    latest = printer.latest_reading
    latest_bars = []
    if latest:
        latest_bars = [
            ("Preto (K)", latest.black_pct, "#333333"),
            ("Ciano (C)", latest.cyan_pct, "#0dcaf0"),
            ("Magenta (M)", latest.magenta_pct, "#d63384"),
            ("Amarelo (Y)", latest.yellow_pct, "#ffc107"),
        ]
        if not printer.is_color:
            latest_bars = latest_bars[:1]

    context = {
        "printer": printer,
        "chart_data_json": json.dumps(chart_data),
        "latest": latest,
        "latest_bars": latest_bars,
    }
    return render(request, "printers/printer_detail.html", context)


@require_GET
def api_status(request):
    """JSON API: returns current toner status for all active printers."""
    printers = Printer.objects.filter(is_active=True)
    data = []
    for p in printers:
        reading = p.latest_reading
        data.append({
            "id": p.pk,
            "name": p.name,
            "ip": p.ip_address,
            "location": p.location,
            "is_color": p.is_color,
            "alert_level": reading.alert_level if reading else "unknown",
            "black_pct": reading.black_pct if reading else None,
            "cyan_pct": reading.cyan_pct if reading else None,
            "magenta_pct": reading.magenta_pct if reading else None,
            "yellow_pct": reading.yellow_pct if reading else None,
            "collected_at": reading.collected_at.isoformat() if reading else None,
        })
    return JsonResponse({"printers": data, "total": len(data)})


@csrf_exempt
@require_POST
def api_collect_now(request, pk: int):
    """Triggers an immediate collection for one printer (called from UI)."""
    printer = get_object_or_404(Printer, pk=pk, is_active=True)
    result = collect_printer(printer)
    return JsonResponse({
        "success": result.success,
        "protocol_used": result.protocol_used,
        "error": result.error,
    })


@csrf_exempt
@require_POST
def api_collect_all(request):
    """Coleta toner de todas as impressoras ativas em background."""
    global _collecting_all
    if _collecting_all:
        return JsonResponse({"success": False, "message": "Coleta já em andamento, aguarde."})

    def run():
        global _collecting_all
        _collecting_all = True
        try:
            collect_all_active()
        finally:
            _collecting_all = False

    threading.Thread(target=run, daemon=True).start()
    return JsonResponse({"success": True, "message": "Coleta iniciada — o painel atualiza em instantes."})


@csrf_exempt
@require_POST
def api_update_locations(request):
    """Sincroniza cadastro de impressoras a partir da planilha Excel."""
    global _discovering
    if _discovering:
        return JsonResponse({"success": False, "message": "Sincronização já em andamento, aguarde."})

    def run():
        global _discovering
        _discovering = True
        try:
            import re
            import pandas as pd
            from printers.models import Printer

            TIPOS_ATIVOS = ["Impressora PB", "Multifuncional PB", "Multifuncional Color"]
            PLANILHA = "Inventário_Impressoras_Simpress_Validadas.xlsx"

            df = pd.read_excel(PLANILHA, sheet_name="Parque Impressoras")

            def fix_ip(ip):
                ip = str(ip).strip()
                m = re.match(r"^(\d{1,3})(\d{3})(\d{3})(\d{1,3})$", ip)
                return f"{m.group(1)}.{m.group(2)}.{m.group(3)}.{m.group(4)}" if m else ip

            df["Ip"] = df["Ip"].apply(fix_ip)
            df = df[df["Ip"].str.match(r"^\d+\.\d+\.\d+\.\d+$", na=False)]

            for _, row in df.iterrows():
                ip   = str(row["Ip"]).strip()
                tipo = str(row.get("Tipo", "")).strip()
                ativo = tipo in TIPOS_ATIVOS
                Printer.objects.filter(ip_address=ip).update(
                    location=str(row.get("Local HSF", "")).strip(),
                    model_name=str(row.get("Modelo", "")).strip(),
                    printer_type=tipo,
                    contract_code=str(row.get("Codigo Contrato", "")).strip(),
                    serial_number=str(row.get("Numero Serie", "")).strip(),
                    is_active=ativo,
                )
        finally:
            _discovering = False

    threading.Thread(target=run, daemon=True).start()
    return JsonResponse({"success": True, "message": "Sincronizando planilha — aguarde alguns segundos."})


@csrf_exempt
@require_POST
def api_update_location(request, pk: int):
    """Atualiza a localização de uma impressora."""
    printer = get_object_or_404(Printer, pk=pk)
    data = json.loads(request.body)
    printer.location = data.get("location", "").strip()
    printer.save(update_fields=["location"])
    return JsonResponse({"success": True, "location": printer.location})


@require_GET
def api_job_status(request):
    """Retorna se há jobs em andamento."""
    return JsonResponse({
        "collecting_all": _collecting_all,
        "discovering":    _discovering,
    })
