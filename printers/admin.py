"""Django admin configuration for printer toner monitoring."""

from django.contrib import admin
from django.utils.html import format_html

from printers.models import Printer, TonerReading


class TonerReadingInline(admin.TabularInline):
    model = TonerReading
    extra = 0
    readonly_fields = ("collected_at", "black_pct", "cyan_pct", "magenta_pct", "yellow_pct", "protocol_used", "success", "error_message")
    can_delete = False
    max_num = 10
    ordering = ("-collected_at",)


@admin.register(Printer)
class PrinterAdmin(admin.ModelAdmin):
    list_display = ("name", "ip_address", "location", "model_name", "protocol", "is_color", "is_active", "toner_status")
    list_filter = ("is_active", "is_color", "protocol")
    search_fields = ("name", "ip_address", "location")
    list_editable = ("is_active",)
    inlines = [TonerReadingInline]

    @admin.display(description="Toner atual")
    def toner_status(self, obj: Printer) -> str:
        reading = obj.latest_reading
        if not reading:
            return "Sem dados"
        level = reading.alert_level
        pct = reading.black_pct
        colors = {"critical": "#dc3545", "warning": "#ffc107", "ok": "#198754"}
        color = colors.get(level, "#6c757d")
        return format_html(
            '<span style="color:{}; font-weight:bold;">⬤ {}% (K)</span>',
            color,
            pct,
        )


@admin.register(TonerReading)
class TonerReadingAdmin(admin.ModelAdmin):
    list_display = ("printer", "black_pct", "cyan_pct", "magenta_pct", "yellow_pct", "protocol_used", "success", "collected_at")
    list_filter = ("success", "protocol_used", "printer")
    search_fields = ("printer__name", "printer__ip_address")
    readonly_fields = ("collected_at",)
    date_hierarchy = "collected_at"
