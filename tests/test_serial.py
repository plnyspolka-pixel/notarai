"""Testy generatora serialu na notarai.pl (seo/serial.py)."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from seo import serial  # noqa: E402

KORZEN_REPO = Path(__file__).resolve().parent.parent


def _odc(id_, nr, publish_at, wideo="serial/media/{id}.mp4", status="gotowy", **pliki):
    return {"id": id_, "sezon": 1, "odcinek": nr, "tytul": f"Tytuł {nr}", "publish_at": publish_at,
            "opis": f"Opis {nr}", "pliki": {"wideo": wideo.format(id=id_), **pliki}, "status": status}


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "serial" / "media").mkdir(parents=True)
    zasoby = tmp_path / "serial" / "zasoby"
    zasoby.mkdir()
    for plik in ("serial.css", "serial.js"):
        (zasoby / plik).write_text("/* */", encoding="utf-8")
    (tmp_path / "strona").mkdir()
    (tmp_path / "strona" / "sitemap.xml").write_text(
        '<?xml version="1.0"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n</urlset>\n',
        encoding="utf-8")
    return tmp_path


def _zapisz(repo, odcinki, z_wideo=()):
    for id_ in z_wideo:
        (repo / "serial" / "media" / f"{id_}.mp4").write_bytes(b"mp4")
    kolejka = repo / "serial" / "odcinki.json"
    kolejka.write_text(json.dumps({"odcinki": odcinki}, ensure_ascii=False), encoding="utf-8")
    return kolejka


def _buduj(repo, kolejka, teraz, log=None):
    return serial.zbuduj(serial.teraz_warszawa(teraz), kolejka=kolejka, cel=repo / "strona" / "serial",
                         korzen=repo, zasoby=repo / "serial" / "zasoby", log=log or (lambda *_: None))


def test_odcinek_przed_premiera_nie_jest_publikowany(repo):
    kolejka = _zapisz(repo, [_odc("s01e01", 1, "2026-11-23T16:00:00+01:00")], z_wideo=["s01e01"])
    assert _buduj(repo, kolejka, "2026-11-23T15:59:00+01:00") == []
    assert not (repo / "strona" / "serial" / "s01e01").exists()
    assert not (repo / "strona" / "serial" / "media" / "s01e01.mp4").exists()
    assert "s01e01" not in (repo / "strona" / "serial" / "rss.xml").read_text(encoding="utf-8")


def test_odcinek_po_premierze_ma_strone_media_rss_i_sitemap(repo):
    kolejka = _zapisz(repo, [_odc("s01e01", 1, "2026-11-23T16:00:00+01:00")], z_wideo=["s01e01"])
    wynik = _buduj(repo, kolejka, "2026-11-23T16:00:00+01:00")
    assert [o["id"] for o in wynik] == ["s01e01"]
    cel = repo / "strona" / "serial"
    assert (cel / "s01e01" / "index.html").is_file()
    assert (cel / "media" / "s01e01.mp4").is_file()
    glowna = (cel / "index.html").read_text(encoding="utf-8")
    assert serial.NAPIS_KONCOWY in glowna and 'class="znaczek-ai"' in glowna
    assert "utm_campaign=komputerku" in glowna and "utm_content=s01e01" in glowna
    assert "/serial/s01e01/" in (cel / "rss.xml").read_text(encoding="utf-8")
    assert "https://notarai.pl/serial/s01e01/" in (repo / "strona" / "sitemap.xml").read_text(encoding="utf-8")


def test_brak_wideo_pomija_odcinek_i_loguje(repo):
    kolejka = _zapisz(repo, [_odc("s01e01", 1, "2026-11-23T09:00:00+01:00")])
    log = []
    assert _buduj(repo, kolejka, "2026-11-23T10:00:00+01:00", log=log.append) == []
    assert any("BRAK WIDEO" in w for w in log)
    assert "wkrótce" in (repo / "strona" / "serial" / "index.html").read_text(encoding="utf-8")


def test_wstrzymany_nie_jest_publikowany(repo):
    kolejka = _zapisz(repo, [_odc("s01e01", 1, "2026-11-20T09:00:00+01:00", status="wstrzymany")],
                      z_wideo=["s01e01"])
    assert _buduj(repo, kolejka, "2026-11-23T10:00:00+01:00") == []


def test_przyszly_odcinek_nie_jest_linkowany_z_poprzedniego(repo):
    kolejka = _zapisz(repo, [_odc("s01e01", 1, "2026-11-23T16:00:00+01:00"),
                             _odc("s01e02", 2, "2026-11-24T09:00:00+01:00")], z_wideo=["s01e01", "s01e02"])
    _buduj(repo, kolejka, "2026-11-23T20:00:00+01:00")
    strona = (repo / "strona" / "serial" / "s01e01" / "index.html").read_text(encoding="utf-8")
    assert "s01e02" not in strona and "Tytuł 2" not in strona
    _buduj(repo, kolejka, "2026-11-24T09:01:00+01:00")
    strona = (repo / "strona" / "serial" / "s01e01" / "index.html").read_text(encoding="utf-8")
    assert "/serial/s01e02/" in strona
    glowna = (repo / "strona" / "serial" / "index.html").read_text(encoding="utf-8")
    assert '<h2 id="odc-t">Tytuł 2</h2>' in glowna  # najnowszy na górze


def test_plakat_i_napisy_tylko_gdy_istnieja(repo):
    o = _odc("s01e01", 1, "2026-11-23T16:00:00+01:00", plakat="serial/media/s01e01.jpg",
             napisy="serial/media/s01e01.vtt")
    kolejka = _zapisz(repo, [o], z_wideo=["s01e01"])
    _buduj(repo, kolejka, "2026-11-23T17:00:00+01:00")
    strona = (repo / "strona" / "serial" / "index.html").read_text(encoding="utf-8")
    assert "poster=" not in strona and "<track" not in strona
    (repo / "serial" / "media" / "s01e01.vtt").write_text("WEBVTT\n", encoding="utf-8")
    _buduj(repo, kolejka, "2026-11-23T17:00:00+01:00")
    assert '<track kind="subtitles"' in (repo / "strona" / "serial" / "index.html").read_text(encoding="utf-8")


def test_wideo_z_adresu_https(repo):
    kolejka = _zapisz(repo, [_odc("s01e01", 1, "2026-11-23T16:00:00+01:00",
                                  wideo="https://media.example/s01e01.mp4")])
    assert len(_buduj(repo, kolejka, "2026-11-23T17:00:00+01:00")) == 1
    assert "https://media.example/s01e01.mp4" in (repo / "strona" / "serial" / "index.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("teraz,oczekiwane", [
    ("2026-11-23T08:59:00+01:00", False),
    ("2026-11-23T09:05:00+01:00", True),
    ("2026-11-23T16:20:00+01:00", True),
    ("2026-11-23T17:00:00+01:00", False),
    # czas letni: 07:00 UTC = 9:00 w Warszawie, 08:00 UTC = 10:00
    ("2026-06-15T07:00:00+00:00", True),
    ("2026-06-15T08:00:00+00:00", False),
    # czas zimowy: 08:00 UTC = 9:00, 07:00 UTC = 8:00
    ("2026-11-23T08:00:00+00:00", True),
    ("2026-11-23T07:00:00+00:00", False),
    ("2026-11-23T15:00:00+00:00", True),
])
def test_okno_publikacji_w_strefie_warszawy(teraz, oczekiwane):
    assert serial.czy_pora(serial.teraz_warszawa(teraz)) is oczekiwane


def test_walidacja_kolejki(tmp_path):
    zla = tmp_path / "k.json"
    zla.write_text(json.dumps({"odcinki": [_odc("a", 1, "2026-11-23T16:00:00")]}), encoding="utf-8")
    with pytest.raises(ValueError, match="strefy"):
        serial.wczytaj(zla)
    zla.write_text(json.dumps({"odcinki": [_odc("a", 1, "2026-11-23T16:00:00+01:00"),
                                            _odc("a", 2, "2026-11-23T17:00:00+01:00")]}), encoding="utf-8")
    with pytest.raises(ValueError, match="powtórzony"):
        serial.wczytaj(zla)


def test_kolejka_w_repo_jest_poprawna():
    dane = serial.wczytaj(KORZEN_REPO / "serial" / "odcinki.json")
    assert dane["odcinki"], "kolejka nie może być pusta"
    for o in dane["odcinki"]:
        assert o["id"] == f"s{o['sezon']:02d}e{o['odcinek']:02d}"
        if o.get("kotwica"):
            assert "zmienione" in o["kotwica"], "kotwica musi mówić, że osoby i szczegóły zmieniono"


def test_pliki_wrzucone_do_strony_trafiaja_do_zrodla(repo):
    kolejka = _zapisz(repo, [_odc("s01e01", 1, "2026-11-23T16:00:00+01:00")])
    media = repo / "strona" / "serial" / "media"
    media.mkdir(parents=True)
    (media / "s01e01.mp4").write_bytes(b"mp4")
    assert _buduj(repo, kolejka, "2026-11-23T10:00:00+01:00") == []  # przed premiera
    assert (repo / "serial" / "media" / "s01e01.mp4").is_file()
    assert not (media / "s01e01.mp4").exists()  # przed premiera nic nie lezy na stronie
    assert len(_buduj(repo, kolejka, "2026-11-23T16:01:00+01:00")) == 1
    assert (media / "s01e01.mp4").is_file()
