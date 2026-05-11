"""Network discovery service: finds HP printers in IP ranges.

Strategy per IP (runs concurrently via ThreadPoolExecutor):
  1. TCP port check   — port 80 or 443 must be open (fast pre-filter)
  2. HTTP probe       — looks for HP EWS/SWS signatures, extracts name/model
  3. HTTP device info — scrapes /hp/device/DeviceInformation/Index for
                        location, alias and serial (newer HP EWS firmware)
  4. SNMP probe       — reads sysDescr + sysLocation + sysName (MIB-II)
                        sysLocation == "Localização do dispositivo" no EWS

Results are aggregated into DiscoveryResult, ready to export as CSV.
"""

import html as html_module
import ipaddress
import logging
import re
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# HP signatures found in EWS HTTP responses
_HP_HTTP_SIGNATURES = [
    "hp", "hewlett", "laserjet", "pagewide", "officejet",
    "sws", "/DevMgmt/", "hp http server",
]

_SWS_DEVICE_INFO_PATH = "/sws/app/information/device/deviceinfo.json"
_EWS_INDEX_PATHS = ["/", "/hp/device/info/configuration", "/sws/index.html"]

# HP EWS newer firmware — device information page (has Location field)
_EWS_DEVICE_INFO_PATH = "/hp/device/DeviceInformation/Index"
# HP LEDM XML — also contains location
_EWS_CONFIG_XML_PATH = "/DevMgmt/ProductConfigDyn.xml"

# Standard MIB-II OIDs
_OID_SYSDESCR   = "1.3.6.1.2.1.1.1.0"   # sysDescr   — description / model
_OID_SYSNAME    = "1.3.6.1.2.1.1.5.0"   # sysName    — hostname / apelido
_OID_SYSLOCATION = "1.3.6.1.2.1.1.6.0"  # sysLocation — "Localização do dispositivo"

_PORT_TIMEOUT = 1.0
_HTTP_PORTS = [443, 80]


@dataclass
class DiscoveryResult:
    ip: str
    is_printer: bool = False
    is_hp: bool = False
    is_color: bool = False
    name: str = ""
    model: str = ""
    location: str = ""       # auto-filled from sysLocation or EWS device info
    serial: str = ""
    protocol: str = "auto"
    snmp_responds: bool = False
    http_responds: bool = False
    errors: list[str] = field(default_factory=list)


def _tcp_port_open(ip: str, port: int, timeout: float = _PORT_TIMEOUT) -> bool:
    """Returns True if the TCP port accepts a connection."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_probe(ip: str, timeout: int) -> tuple[bool, bool, str, str]:
    """Probes HTTP/HTTPS for HP printer signatures.

    Returns: (is_hp, is_color, name, model)
    """
    session = requests.Session()
    session.verify = False

    for scheme in ("https", "http"):
        base = f"{scheme}://{ip}"

        # 1. SWS JSON — richest data source (older HP firmware)
        try:
            resp = session.get(f"{base}{_SWS_DEVICE_INFO_PATH}", timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                name = (
                    data.get("ProductName")
                    or data.get("deviceName")
                    or data.get("ModelName", "")
                ).strip()
                color_hint = str(data).lower()
                is_color = "color" in color_hint or "colour" in color_hint
                return True, is_color, name, name
        except Exception:
            pass

        # 2. EWS index pages — signature detection + title extraction
        for path in _EWS_INDEX_PATHS:
            try:
                resp = session.get(f"{base}{path}", timeout=timeout, allow_redirects=True)
                body_lower = resp.text.lower()
                server = resp.headers.get("Server", "").lower()
                combined = body_lower + " " + server

                if any(sig in combined for sig in _HP_HTTP_SIGNATURES):
                    is_color = "color" in combined or "colour" in combined
                    name, model = "", ""
                    if "<title>" in body_lower:
                        start = resp.text.lower().find("<title>") + 7
                        end = resp.text.lower().find("</title>", start)
                        name = resp.text[start:end].strip()
                        model = name
                    return True, is_color, name, model
            except Exception:
                continue

    return False, False, "", ""


def _http_device_info(ip: str, timeout: int) -> tuple[str, str, str]:
    """Scrapes HP EWS device info page for location, alias and serial.

    Tries:
      1. /hp/device/DeviceInformation/Index  (newer firmware — E-series, M-series)
      2. /DevMgmt/ProductConfigDyn.xml       (LEDM XML)

    Returns: (location, alias, serial)
    """
    session = requests.Session()
    session.verify = False

    for scheme in ("https", "http"):
        base = f"{scheme}://{ip}"

        # --- Newer HP EWS HTML page ---
        try:
            resp = session.get(f"{base}{_EWS_DEVICE_INFO_PATH}", timeout=timeout)
            if resp.status_code == 200 and "hp" in resp.text.lower():
                location = _extract_field_after_label(resp.text, [
                    "Localização do dispositivo",
                    "Device Location",
                    "Location",
                ])
                alias = _extract_field_after_label(resp.text, [
                    "Apelido",
                    "Device Name",
                    "Alias",
                ])
                serial = _extract_field_after_label(resp.text, [
                    "Número de Série do Produto",
                    "Serial Number",
                    "Product Serial Number",
                ])
                if location or alias or serial:
                    return location, alias, serial
        except Exception:
            pass

        # --- HP LEDM XML ---
        try:
            resp = session.get(f"{base}{_EWS_CONFIG_XML_PATH}", timeout=timeout)
            if resp.status_code == 200:
                location = _extract_xml_text(resp.text, [
                    "DeviceLocation", "prt-sysLocation", "SystemLocation"
                ])
                alias = _extract_xml_text(resp.text, [
                    "DeviceName", "DeviceAlias", "prt-sysName"
                ])
                serial = _extract_xml_text(resp.text, [
                    "SerialNumber", "ProductSerialNumber"
                ])
                if location or alias:
                    return location, alias, serial
        except Exception:
            pass

    return "", "", ""


def _extract_field_after_label(html: str, labels: list[str]) -> str:
    """Extracts the value that follows a label in HP EWS HTML.

    Tries two patterns within 300 chars after the label:
      1. value="..." attribute (input fields)
      2. text content of next block element (td, dd, span, div, p)
    """
    for label in labels:
        escaped = re.escape(label)
        # Pattern 1: value="..." attribute after the label
        m = re.search(
            escaped + r'.{0,300}?value="([^"]*)"',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if m and m.group(1).strip():
            return html_module.unescape(m.group(1).strip())
        # Pattern 2: text content of next block/cell element after the label
        m = re.search(
            escaped + r'.{0,300}?<(?:td|dd|span|div|p)[^>]*>\s*([^<]+?)\s*<',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if m and m.group(1).strip():
            return html_module.unescape(m.group(1).strip())
    return ""


def _extract_xml_text(xml: str, tags: list[str]) -> str:
    """Extracts text content of the first matching XML tag."""
    for tag in tags:
        m = re.search(rf"<[^>]*{re.escape(tag)}[^>]*>([^<]+)<", xml, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _snmp_probe(ip: str, timeout: int) -> tuple[bool, str, str, str]:
    """Queries SNMP MIB-II for sysDescr, sysName and sysLocation.

    sysLocation is the exact value of "Localização do dispositivo" in HP EWS.

    Returns: (responds, description, name, location)
    """
    import asyncio
    from pysnmp.hlapi.asyncio import (
        CommunityData, ContextData, ObjectIdentity,
        ObjectType, SnmpEngine, UdpTransportTarget, getCmd,
    )

    async def _get():
        engine = SnmpEngine()
        transport = UdpTransportTarget((ip, 161), timeout=timeout, retries=0)
        err_ind, err_stat, _, var_binds = await getCmd(
            engine,
            CommunityData("public", mpModel=1),
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(_OID_SYSDESCR)),
            ObjectType(ObjectIdentity(_OID_SYSNAME)),
            ObjectType(ObjectIdentity(_OID_SYSLOCATION)),
        )
        if err_ind or err_stat:
            return False, "", "", ""
        values = [str(vb[1]).strip() for vb in var_binds]
        desc     = values[0] if len(values) > 0 else ""
        sys_name = values[1] if len(values) > 1 else ""
        location = values[2] if len(values) > 2 else ""
        return True, desc, sys_name, location

    try:
        return asyncio.run(_get())
    except Exception as exc:
        logger.debug("SNMP probe failed for %s: %s", ip, exc)
        return False, "", "", ""


def scan_ip(ip: str, timeout: int = 3) -> DiscoveryResult:
    """Full probe for a single IP. Returns a populated DiscoveryResult."""
    result = DiscoveryResult(ip=ip)

    http_port_open = any(_tcp_port_open(ip, p, _PORT_TIMEOUT) for p in _HTTP_PORTS)
    snmp_port_open = _tcp_port_open(ip, 161, _PORT_TIMEOUT)

    if not http_port_open and not snmp_port_open:
        return result

    # 1. HTTP signature probe
    if http_port_open:
        try:
            is_hp, is_color, name, model = _http_probe(ip, timeout)
            result.http_responds = True
            result.is_hp = is_hp
            result.is_color = is_color
            result.name = name
            result.model = model
        except Exception as exc:
            result.errors.append(f"HTTP: {exc}")

    # 2. HTTP device info — location, alias, serial
    if http_port_open:
        try:
            location, alias, serial = _http_device_info(ip, timeout)
            if location:
                result.location = location
            if alias and not result.name:
                result.name = alias
            result.serial = serial
        except Exception as exc:
            result.errors.append(f"HTTP device info: {exc}")

    # 3. SNMP probe — description, sysName, sysLocation
    snmp_ok, snmp_desc, snmp_name, snmp_location = _snmp_probe(ip, timeout)
    if snmp_ok:
        result.snmp_responds = True

        # sysLocation is authoritative for location (same field as HP EWS)
        if snmp_location and not result.location:
            result.location = snmp_location

        if not result.name:
            result.name = snmp_name or snmp_desc[:80]
        if not result.model:
            result.model = snmp_desc[:80]

        if not result.is_hp and snmp_desc:
            desc_lower = snmp_desc.lower()
            result.is_hp = any(k in desc_lower for k in ("hp", "hewlett", "laserjet"))
            result.is_color = result.is_color or "color" in desc_lower or "colour" in desc_lower

    result.is_printer = result.is_hp or result.snmp_responds

    if result.snmp_responds and result.http_responds:
        result.protocol = "auto"
    elif result.snmp_responds:
        result.protocol = "snmp"
    elif result.http_responds:
        result.protocol = "http"

    if not result.name:
        result.name = f"Impressora {ip}"

    return result


def scan_range(
    networks: list[str],
    workers: int = 50,
    timeout: int = 3,
    only_hp: bool = True,
) -> list[DiscoveryResult]:
    """Scans all IPs in the given CIDR ranges concurrently."""
    all_ips: list[str] = []
    for net_str in networks:
        try:
            network = ipaddress.ip_network(net_str.strip(), strict=False)
            hosts = list(network.hosts()) if network.prefixlen < 32 else [network.network_address]
            all_ips.extend(str(h) for h in hosts)
        except ValueError as exc:
            logger.error("Invalid network %r: %s", net_str, exc)

    if not all_ips:
        return []

    results: list[DiscoveryResult] = []
    total = len(all_ips)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(scan_ip, ip, timeout): ip for ip in all_ips}
        done = 0
        for future in as_completed(futures):
            done += 1
            try:
                result = future.result()
                if not only_hp or result.is_hp:
                    results.append(result)
            except Exception as exc:
                ip = futures[future]
                logger.error("Unexpected error scanning %s: %s", ip, exc)
            finally:
                if done % 10 == 0 or done == total:
                    logger.info("Discovery progress: %d/%d IPs scanned", done, total)

    results.sort(key=lambda r: ipaddress.ip_address(r.ip))
    return results
