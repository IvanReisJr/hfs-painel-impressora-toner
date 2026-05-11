"""HTTP/EWS client for HP printers that expose XML or JSON endpoints.

Tries multiple known HP EWS/SWS endpoints in order until one succeeds.
Supports:
  - HP SWS JSON  (/sws/app/information/consumables/consumables.json)
  - HP EWS XML   (/DevMgmt/ProductUsageDyn.xml)
  - HP EWS XML   (/DevMgmt/ConsumableConfigDyn.xml)
"""

import logging
from dataclasses import dataclass

import requests
from lxml import etree
import json

logger = logging.getLogger(__name__)

_SWS_JSON_PATH = "/sws/app/information/consumables/consumables.json"
_EWS_XML_PATHS = [
    "/DevMgmt/ProductUsageDyn.xml",
    "/DevMgmt/ConsumableConfigDyn.xml",
]

# XPath patterns for toner % in HP EWS XML
_XML_NAMESPACES = {
    "pudyn": "http://www.hp.com/schemas/imaging/con/ledm/productusagedyn/2007/11/05",
    "dd": "http://www.hp.com/schemas/imaging/con/dictionaries/1.0/",
    "ccdyn": "http://www.hp.com/schemas/imaging/con/ledm/consumableconfigdyn/2007/11/13",
}

_COLOR_KEYWORDS = {
    "black": "black_pct",
    "preto": "black_pct",
    "negro": "black_pct",
    "cyan": "cyan_pct",
    "ciano": "cyan_pct",
    "magenta": "magenta_pct",
    "yellow": "yellow_pct",
    "amarelo": "yellow_pct",
}


@dataclass
class HttpTonerResult:
    success: bool
    black_pct: int | None = None
    cyan_pct: int | None = None
    magenta_pct: int | None = None
    yellow_pct: int | None = None
    error: str = ""


def _parse_sws_json(data: dict) -> HttpTonerResult:
    """Parses HP SWS consumables JSON response."""
    result = HttpTonerResult(success=False)
    try:
        consumables = data.get("ConsumableList", data.get("consumables", []))
        if isinstance(consumables, dict):
            consumables = consumables.get("Consumable", [])
        if not isinstance(consumables, list):
            consumables = [consumables]

        for item in consumables:
            color_raw = str(item.get("Color", item.get("color", ""))).lower()
            pct_raw = item.get("ConsumablePercentageLevelRemaining",
                               item.get("percentRemaining",
                               item.get("RemainingPercent", None)))
            if pct_raw is None:
                continue

            field = _COLOR_KEYWORDS.get(color_raw)
            if field:
                setattr(result, field, max(0, min(100, int(float(pct_raw)))))

        if result.black_pct is not None:
            result.success = True
    except Exception as exc:
        result.error = f"JSON parse error: {exc}"
    return result


def _parse_ews_xml(content: bytes) -> HttpTonerResult:
    """Parses HP EWS ProductUsageDyn or ConsumableConfigDyn XML."""
    result = HttpTonerResult(success=False)
    try:
        root = etree.fromstring(content)
        # Generic search: look for elements containing percentage-like values
        # alongside color names anywhere in the tree
        color_ctx: dict[str, int] = {}
        current_color: str | None = None

        for elem in root.iter():
            tag = (elem.tag or "").split("}")[-1].lower()
            text = (elem.text or "").strip().lower()

            if "color" in tag or "name" in tag or "type" in tag:
                for key in _COLOR_KEYWORDS:
                    if key in text:
                        current_color = _COLOR_KEYWORDS[key]
                        break

            if current_color and ("percent" in tag or "level" in tag or "remaining" in tag):
                try:
                    pct = int(float(elem.text.strip()))
                    if 0 <= pct <= 100:
                        color_ctx[current_color] = pct
                        current_color = None
                except (ValueError, AttributeError):
                    pass

        for field, pct in color_ctx.items():
            setattr(result, field, pct)

        if result.black_pct is not None:
            result.success = True
    except Exception as exc:
        result.error = f"XML parse error: {exc}"
    return result


def _build_base_url(ip: str) -> str:
    return f"https://{ip}"


def fetch_toner(ip: str, timeout: int = 5) -> HttpTonerResult:
    """Tries SWS JSON then EWS XML endpoints for the given printer IP."""
    session = requests.Session()
    session.verify = False  # self-signed certs are common on HP printers
    requests.packages.urllib3.disable_warnings()

    base_url = _build_base_url(ip)

    # 1. Try SWS JSON
    try:
        resp = session.get(f"{base_url}{_SWS_JSON_PATH}", timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            parsed = _parse_sws_json(data)
            if parsed.success:
                return parsed
    except Exception as exc:
        logger.debug("SWS JSON failed for %s: %s", ip, exc)

    # 2. Try EWS XML endpoints
    for path in _EWS_XML_PATHS:
        try:
            resp = session.get(f"{base_url}{path}", timeout=timeout)
            if resp.status_code == 200:
                parsed = _parse_ews_xml(resp.content)
                if parsed.success:
                    return parsed
        except Exception as exc:
            logger.debug("EWS XML %s failed for %s: %s", path, ip, exc)

    return HttpTonerResult(success=False, error="No HTTP endpoint responded successfully")
