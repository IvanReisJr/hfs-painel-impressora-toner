"""Models for printer toner monitoring."""

from django.db import models
from django.utils import timezone


class Printer(models.Model):
    """Represents a network printer to be monitored."""

    class Protocol(models.TextChoices):
        AUTO = "auto", "Auto (SNMP → HTTP)"
        SNMP = "snmp", "SNMP"
        HTTP = "http", "HTTP/EWS"

    name = models.CharField(max_length=100, verbose_name="Nome")
    ip_address = models.GenericIPAddressField(unique=True, verbose_name="Endereço IP")
    location = models.CharField(max_length=200, blank=True, verbose_name="Localização")
    model_name = models.CharField(max_length=100, blank=True, verbose_name="Modelo")
    contract_code = models.CharField(max_length=50, blank=True, default="", verbose_name="Cód. Contrato")
    serial_number = models.CharField(max_length=100, blank=True, default="", verbose_name="Nº Série")
    printer_type = models.CharField(max_length=100, blank=True, default="", verbose_name="Tipo")
    protocol = models.CharField(
        max_length=10,
        choices=Protocol.choices,
        default=Protocol.AUTO,
        verbose_name="Protocolo",
    )
    snmp_community = models.CharField(
        max_length=50, default="public", verbose_name="Community SNMP"
    )
    is_color = models.BooleanField(default=False, verbose_name="Colorida")
    is_active = models.BooleanField(default=True, verbose_name="Ativa")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Impressora"
        verbose_name_plural = "Impressoras"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.ip_address})"

    @property
    def latest_reading(self) -> "TonerReading | None":
        return self.readings.filter(success=True).order_by("-collected_at", "-pk").first()


class TonerReading(models.Model):
    """Daily toner level snapshot for a printer."""

    printer = models.ForeignKey(
        Printer,
        on_delete=models.CASCADE,
        related_name="readings",
        verbose_name="Impressora",
    )
    black_pct = models.IntegerField(null=True, blank=True, verbose_name="Preto (%)")
    cyan_pct = models.IntegerField(null=True, blank=True, verbose_name="Ciano (%)")
    magenta_pct = models.IntegerField(null=True, blank=True, verbose_name="Magenta (%)")
    yellow_pct = models.IntegerField(null=True, blank=True, verbose_name="Amarelo (%)")
    protocol_used = models.CharField(
        max_length=10, blank=True, verbose_name="Protocolo usado"
    )
    success = models.BooleanField(default=False, verbose_name="Sucesso")
    error_message = models.TextField(blank=True, verbose_name="Erro")
    collected_at = models.DateTimeField(default=timezone.now, verbose_name="Coletado em")

    class Meta:
        verbose_name = "Leitura de Toner"
        verbose_name_plural = "Leituras de Toner"
        ordering = ["-collected_at"]
        indexes = [
            models.Index(fields=["printer", "-collected_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.printer.name} — {self.collected_at:%d/%m/%Y %H:%M}"

    @property
    def lowest_color_pct(self) -> int | None:
        """Returns the lowest toner percentage among all colors (for alerting)."""
        values = [v for v in [self.black_pct, self.cyan_pct, self.magenta_pct, self.yellow_pct] if v is not None]
        return min(values) if values else None

    @property
    def alert_level(self) -> str:
        """Returns 'critical', 'warning' or 'ok' based on lowest toner."""
        pct = self.lowest_color_pct
        if pct is None:
            return "unknown"
        if pct <= 10:
            return "critical"
        if pct <= 20:
            return "warning"
        return "ok"
