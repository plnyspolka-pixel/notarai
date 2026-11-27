"""Printers and scanners of the office network: found, named, printed to and scanned from."""
import base64
import struct
import time

import pytest
from fastapi.testclient import TestClient

from worker.api import create_app
from worker.init_vault import initialize
from worker.peripherals import DeviceError, escl_scan, ipp_print, ipp_print_request, match

PRINTER = {"kind": "drukarka", "model": "HP LaserJet M402", "address": "192.168.1.30", "port": 631, "protocol": "ipp",
           "path": "ipp/print", "id": "drukarka:192.168.1.30", "formats": "application/pdf,image/urf", "color": ""}
SCANNER = {"kind": "skaner", "model": "Brother MFC-L2710", "address": "192.168.1.31", "port": 80, "protocol": "escl",
           "path": "eSCL", "id": "skaner:192.168.1.31", "formats": "", "color": ""}


class Answer:
    def __init__(self, status, content=b"", headers=None):
        self.status_code, self.content, self.headers = status, content, headers or {}


def test_an_ipp_print_job_carries_the_pdf_and_reads_the_status():
    request = ipp_print_request("ipp://p:631/ipp/print", b"%PDF-1.4", "umowa.docx")
    assert request[:8] == struct.pack(">bbHI", 2, 0, 0x0002, 1) and request.endswith(b"\x03%PDF-1.4")
    assert b"application/pdf" in request and b"umowa.docx" in request
    sent = []
    ipp_print(PRINTER, b"%PDF", "a", post=lambda url, data: sent.append(url) or Answer(200, b"\x02\x00\x00\x00"))
    assert sent == ["http://192.168.1.30:631/ipp/print"]
    with pytest.raises(DeviceError):
        ipp_print(PRINTER, b"%PDF", "a", post=lambda url, data: Answer(200, b"\x02\x00\x04\x00"))   # client error
    with pytest.raises(DeviceError):
        ipp_print({**PRINTER, "protocol": "raw"}, b"%PDF", "a", post=lambda *a: Answer(200))


def test_an_escl_scan_waits_for_the_page_and_joins_the_feeder():
    class Scanner:
        def __init__(self, pages):
            self.pages, self.asked = list(pages), 0

        def post(self, url, content, headers):
            assert url == "http://192.168.1.31:80/eSCL/ScanJobs" and b"Grayscale8" in content
            return Answer(201, headers={"Location": "/eSCL/ScanJobs/7"})

        def get(self, url):
            assert url == "http://192.168.1.31:80/eSCL/ScanJobs/7/NextDocument"
            self.asked += 1
            if self.asked == 1:
                return Answer(503)                       # still scanning
            return Answer(200, self.pages.pop(0)) if self.pages else Answer(404)
    assert escl_scan(SCANNER, client=Scanner([b"%PDF-glass"]), wait=lambda s: None) == b"%PDF-glass"
    with pytest.raises(DeviceError):
        escl_scan({**SCANNER, "protocol": "raw"}, client=Scanner([]))


def test_names_given_by_the_office_find_the_device():
    names = {"drukarka:192.168.1.30": "Sekretariat"}
    assert match([PRINTER], names, "sekretariat") is PRINTER
    assert match([PRINTER], names, "laserjet") is PRINTER and match([PRINTER], {}, "gabinet") is None


def test_find_name_print_and_scan_by_talking(tmp_path):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    printed, scanned = [], []
    client = TestClient(create_app(home, device_scan=lambda: [PRINTER, SCANNER],
                                   ipp=lambda device, pdf, job: printed.append((device["model"], pdf, job)),
                                   to_pdf=lambda name, data: b"%PDF:" + data,
                                   escl=lambda device, **options: scanned.append(options) or b"%PDF-scan"))

    def say(text, case=None):
        return client.post("/v2/chat", headers=admin, json={"text": text, "case": case}).json()["blocks"]
    listing = say("znajdź drukarki")[0]["text"]
    assert "HP LaserJet M402 (192.168.1.30, druk bez sterownika)" in listing and "Brother MFC-L2710" in listing
    named = say("nazwij drukarkę HP LaserJet jako Sekretariat")[0]["text"]
    assert "nazywa się teraz „Sekretariat”" in named
    say("nazwij skaner brother jako Gabinet")
    assert "„Sekretariat” – HP LaserJet M402" in say("drukarki")[0]["text"]
    client.post("/v2/documents", headers=admin, json={"id": None, "expected_version": 0, "name": "umowa.docx", "case": "s",
                                                       "content_b64": base64.b64encode(b"DOCX").decode()})
    done = say("wydrukuj umowa.docx na drukarce Sekretariat", case="s")
    assert printed == [("HP LaserJet M402", b"%PDF:DOCX", "umowa.docx")] and "„Sekretariat”" in done[0]["text"]
    assert "Do której sprawy" in say("zeskanuj")[0]["text"]
    started = say("zeskanuj na skanerze gabinet w kolorze", case="s")
    job = next(b for b in started if b["type"] == "job")["id"]
    for _ in range(50):
        answer = client.get(f"/v2/jobs/{job}", headers=admin).json()
        if answer["done"]:
            break
        time.sleep(0.05)
    assert scanned == [{"color": True, "feeder": False}]
    assert answer["blocks"][1]["items"][0]["name"].startswith("skan ")
