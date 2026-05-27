"""SNMP client for reading toner levels from HP printers.

Uses standard Printer MIB (RFC 3805) OIDs:
  - prtMarkerSuppliesLevel:       .1.3.6.1.2.1.43.11.1.1.9
  - prtMarkerSuppliesMaxCapacity: .1.3.6.1.2.1.43.11.1.1.8
"""

import asyncio
import logging
from dataclasses import dataclass

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    get_cmd,
)

logger = logging.getLogger(__name__)

_OID_LEVEL_BASE = "1.3.6.1.2.1.43.11.1.1.9.1"
_OID_MAX_BASE = "1.3.6.1.2.1.43.11.1.1.8.1"

_CARTRIDGE_SLOTS = {
    "black_pct": 1,
    "cyan_pct": 2,
    "magenta_pct": 3,
    "yellow_pct": 4,
}


@dataclass
class SnmpTonerResult:
    success: bool
    black_pct: int | None = None
    cyan_pct: int | None = None
    magenta_pct: int | None = None
    yellow_pct: int | None = None
    error: str = ""


def _calc_percent(current: int, maximum: int) -> int | None:
    """Calculates toner percentage; returns None for invalid input.

    When max == -2 the printer returns a direct percentage value.
    """
    if maximum == 0 or current < 0:
        return None
    if maximum == -2:
        return max(0, min(100, current))
    if maximum < 0:
        return None
    return max(0, min(100, round(current * 100 / maximum)))


async def _fetch_async(
    ip: str,
    community: str,
    timeout: int,
    retries: int,
) -> SnmpTonerResult:
    result = SnmpTonerResult(success=False)
    engine = SnmpEngine()
    transport = await UdpTransportTarget.create((ip, 161), timeout=timeout, retries=retries)

    try:
        for field_name, slot in _CARTRIDGE_SLOTS.items():
            error_indication, error_status, _, var_binds = await get_cmd(
                engine,
                CommunityData(community, mpModel=1),
                transport,
                ContextData(),
                ObjectType(ObjectIdentity(f"{_OID_LEVEL_BASE}.{slot}")),
                ObjectType(ObjectIdentity(f"{_OID_MAX_BASE}.{slot}")),
            )

            if error_indication:
                result.error = str(error_indication)
                break  # falha de rede — não adianta tentar os demais slots
            if error_status:
                continue  # OID não existe neste slot (ex: impressora mono sem cor)

            if len(var_binds) >= 2:
                try:
                    current = int(var_binds[0][1])
                    maximum = int(var_binds[1][1])
                    pct = _calc_percent(current, maximum)
                    if pct is not None:
                        setattr(result, field_name, pct)
                except (TypeError, ValueError):
                    continue

        if result.black_pct is not None:
            result.success = True

    except Exception as exc:
        result.error = str(exc)
        logger.warning("SNMP error for %s: %s", ip, exc)

    engine.close_dispatcher()
    return result


def fetch_toner(
    ip: str,
    community: str = "public",
    timeout: int = 3,
    retries: int = 1,
) -> SnmpTonerResult:
    """Synchronous entry point — runs the async SNMP fetch."""
    return asyncio.run(_fetch_async(ip, community, timeout, retries))
