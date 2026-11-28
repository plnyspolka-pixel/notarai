"""Printers and scanners of the office network, controlled from every workstation.

Found the way Windows and phones find them (mDNS / Bonjour): IPP printers and eSCL (AirScan) scanners
announce themselves in the local network, so no driver is needed: a PDF goes to the printer with an IPP
Print-Job, and a scan comes back as a PDF over eSCL. Printers installed in Windows are listed too (and
those of the other workstations, through the office link). The office gives each device a name
(„Sekretariat”, „Gabinet”), and that name works in commands on every workstation.
"""
import re
import struct
import threading
import time
import urllib.parse

SERVICES = {
    "_ipp._tcp.local.": ("drukarka", "ipp"), "_ipps._tcp.local.": ("drukarka", "ipps"),
    "_pdl-datastream._tcp.local.": ("drukarka", "raw"), "_printer._tcp.local.": ("drukarka", "lpd"),
    "_uscan._tcp.local.": ("skaner", "escl"), "_uscans._tcp.local.": ("skaner", "escls"),
}


class DeviceError(Exception):
    """Fixed Polish message, safe to show."""


def discover(seconds: float = 3.0, *, zeroconf_factory=None) -> list[dict]:
    """Printers and scanners announcing themselves in this network. Read only; nothing is printed."""
    try:
        from zeroconf import ServiceBrowser, Zeroconf
    except Exception:
        return []
    found: dict[str, dict] = {}
    lock = threading.Lock()
    zc = (zeroconf_factory or Zeroconf)()

    class Listener:
        def add_service(self, zc_, kind, name):
            info = zc_.get_service_info(kind, name, timeout=1500)
            if info is None or not info.parsed_addresses():
                return
            props = {k.decode(errors="ignore"): (v or b"").decode(errors="ignore") for k, v in (info.properties or {}).items()}
            role, protocol = SERVICES[kind]
            model = props.get("ty") or props.get("product", "").strip("()") or name.split("._")[0]
            address = info.parsed_addresses()[0]
            key = f"{role}:{address}"
            with lock:
                current = found.get(key)
                # Prefer the protocol NotarAI can drive without a driver: IPP for printers, eSCL for scanners.
                better = current is None or (protocol in {"ipp", "escl"} and current["protocol"] not in {"ipp", "escl"})
                if better:
                    found[key] = {"kind": role, "model": model, "address": address, "port": info.port,
                                  "protocol": protocol, "path": props.get("rp", ""), "id": key,
                                  "formats": props.get("pdl", ""), "color": props.get("Color", props.get("cs", ""))}

        def update_service(self, *args):
            pass

        def remove_service(self, *args):
            pass

    try:
        browsers = [ServiceBrowser(zc, kind, Listener()) for kind in SERVICES]
        time.sleep(seconds)
        for browser in browsers:
            browser.cancel()
    finally:
        zc.close()
    return sorted(found.values(), key=lambda d: (d["kind"], d["model"]))


# ---------------------------------------------------------------- IPP: printing a PDF without a driver
def _attr(tag: int, name: str, value: bytes) -> bytes:
    return struct.pack(">bH", tag, len(name)) + name.encode() + struct.pack(">H", len(value)) + value


def ipp_print_request(uri: str, pdf: bytes, job: str, request_id: int = 1) -> bytes:
    body = struct.pack(">bbHI", 2, 0, 0x0002, request_id)          # IPP 2.0, Print-Job
    body += b"\x01"                                                  # operation attributes
    body += _attr(0x47, "attributes-charset", b"utf-8")
    body += _attr(0x48, "attributes-natural-language", b"pl")
    body += _attr(0x45, "printer-uri", uri.encode())
    body += _attr(0x42, "requesting-user-name", b"NotarAI")
    body += _attr(0x42, "job-name", job.encode()[:200])
    body += _attr(0x49, "document-format", b"application/pdf")
    return body + b"\x03" + pdf


def ipp_print(device: dict, pdf: bytes, job: str, *, post=None) -> None:
    if device.get("protocol") not in {"ipp", "ipps"}:
        raise DeviceError(f"Drukarka {device.get('model')} nie przyjmuje druku przez sieć bez sterownika (IPP). "
                          "Zainstaluj ją w Windows, a NotarAI wydrukuje przez sterownik.")
    if "pdf" not in device.get("formats", "pdf").lower() and device.get("formats"):
        raise DeviceError(f"Drukarka {device.get('model')} nie drukuje PDF bezpośrednio. Zainstaluj ją w Windows.")
    scheme = "https" if device["protocol"] == "ipps" else "http"
    path = "/" + (device.get("path") or "ipp/print").lstrip("/")
    url = f"{scheme}://{device['address']}:{device['port']}{path}"
    uri = f"ipp://{device['address']}:{device['port']}{path}"
    payload = ipp_print_request(uri, pdf, job)
    if post is None:
        import httpx

        def post(target, data):
            return httpx.post(target, content=data, headers={"Content-Type": "application/ipp"}, timeout=60,
                              verify=False)        # printers use self-made certificates; nothing secret is read back
    try:
        response = post(url, payload)
    except Exception:
        raise DeviceError(f"Drukarka {device.get('model')} nie odpowiada. Sprawdź, czy jest włączona.") from None
    content = getattr(response, "content", b"")
    status = struct.unpack(">H", content[2:4])[0] if len(content) >= 4 else 0xFFFF
    if getattr(response, "status_code", 200) != 200 or status > 0x00FF:
        raise DeviceError(f"Drukarka {device.get('model')} odrzuciła wydruk (kod {status:#06x}).")


# ---------------------------------------------------------------- eSCL: scanning to PDF without a driver
SCAN_SETTINGS = """<?xml version="1.0" encoding="UTF-8"?>
<scan:ScanSettings xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03" xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm">
  <pwg:Version>2.6</pwg:Version>
  <pwg:InputSource>{source}</pwg:InputSource>
  <scan:ColorMode>{color}</scan:ColorMode>
  <scan:XResolution>{dpi}</scan:XResolution>
  <scan:YResolution>{dpi}</scan:YResolution>
  <pwg:DocumentFormat>application/pdf</pwg:DocumentFormat>
  <scan:DocumentFormatExt>application/pdf</scan:DocumentFormatExt>
</scan:ScanSettings>"""


def escl_scan(device: dict, *, dpi: int = 300, color: bool = False, feeder: bool = False, client=None,
              wait=time.sleep) -> bytes:
    """One scan (all pages from the feeder, or the glass) as a PDF."""
    if device.get("protocol") not in {"escl", "escls"}:
        raise DeviceError(f"Skaner {device.get('model')} nie skanuje przez sieć bez sterownika (eSCL).")
    scheme = "https" if device["protocol"] == "escls" else "http"
    base = f"{scheme}://{device['address']}:{device['port']}/" + (device.get("path") or "eSCL").strip("/")
    if client is None:
        import httpx

        client = httpx.Client(timeout=120, verify=False)
    settings = SCAN_SETTINGS.format(source="Feeder" if feeder else "Platen", color="RGB24" if color else "Grayscale8", dpi=dpi)
    try:
        created = client.post(base + "/ScanJobs", content=settings.encode(), headers={"Content-Type": "text/xml"})
        if created.status_code not in (200, 201) or "location" not in {k.lower() for k in created.headers}:
            raise DeviceError(f"Skaner {device.get('model')} nie przyjął zadania (kod {created.status_code}).")
        job = next(v for k, v in created.headers.items() if k.lower() == "location")
        job = job if job.startswith("http") else urllib.parse.urljoin(base + "/", job)
        pages = []
        for _ in range(200):
            page = client.get(job.rstrip("/") + "/NextDocument")
            if page.status_code == 200:
                pages.append(page.content)
                if not feeder:
                    break
            elif page.status_code == 404 and pages:
                break                                # the feeder is empty: done
            elif page.status_code in (503, 409, 404):
                wait(1)                              # still scanning
            else:
                raise DeviceError(f"Skaner {device.get('model')} przerwał skanowanie (kod {page.status_code}).")
    except DeviceError:
        raise
    except Exception:
        raise DeviceError(f"Skaner {device.get('model')} nie odpowiada. Sprawdź, czy jest włączony i ma papier.") from None
    if not pages:
        raise DeviceError(f"Skaner {device.get('model')} nie oddał żadnej strony.")
    return pages[0] if len(pages) == 1 else _join_pdfs(pages)


def _join_pdfs(parts: list[bytes]) -> bytes:
    import io

    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for part in parts:
        for page in PdfReader(io.BytesIO(part)).pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def word_to_pdf(name: str, data: bytes) -> bytes:
    """DOCX/DOC/RTF to PDF with the office's Word (Windows), for printers that take PDF."""
    import os
    import tempfile
    from pathlib import Path

    if name.lower().endswith(".pdf"):
        return data
    if os.name != "nt":
        raise DeviceError("Zamiana na PDF do druku działa na komputerze z Wordem.")
    import pythoncom
    import win32com.client

    folder = Path(tempfile.mkdtemp(prefix="notarai-pdf-"))
    source, target = folder / Path(name).name, folder / (Path(name).stem + ".pdf")
    source.write_bytes(data)
    pythoncom.CoInitialize()
    word = win32com.client.DispatchEx("Word.Application")
    try:
        word.Visible = False
        document = word.Documents.Open(str(source), ReadOnly=True)
        document.ExportAsFixedFormat(str(target), 17)          # 17 = PDF
        document.Close(False)
    except Exception:
        raise DeviceError("Word nie zamienił dokumentu na PDF do druku.") from None
    finally:
        word.Quit()
    return target.read_bytes()


# ---------------------------------------------------------------- names given by the office
def match(devices: list[dict], names: dict, wanted: str) -> dict | None:
    """A device by the office's name for it, by model, or by address."""
    wanted = re.sub(r"\s+", " ", wanted.strip().lower())
    for device in devices:
        own = names.get(device["id"], "").lower()
        if own and (own == wanted or own in wanted):
            return device
    for device in devices:
        if wanted and (wanted in device["model"].lower() or wanted == device["address"]):
            return device
    return None
