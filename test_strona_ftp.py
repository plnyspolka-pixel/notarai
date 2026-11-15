"""Offline regression checks for detecting NotarAI document root on FTPS."""
import ftplib

import pytest

from infra import strona_ftp


class FakeFtp:
    def __init__(self, pages=None):
        self.pages = pages or {}
        self.requests = []

    def mlsd(self, path, facts=None):
        assert path == "/"
        return [
            ("other", {"type": "dir"}),
            ("public_html", {"type": "dir"}),
            ("backups", {"type": "dir"}),
        ]

    def retrbinary(self, command, callback):
        self.requests.append(command)
        data = self.pages.get(command)
        if data is None:
            raise ftplib.error_perm("550 File unavailable")
        callback(data)


def test_finds_notarai_in_non_root_directory():
    root = "/public_html"
    ftp = FakeFtp({
        f"RETR {root}/index.html": b"<title>notarai</title><a href='https://app.notarai.pl'>App</a>",
        f"RETR {root}/brand-site.css": b":root {color: navy}",
        "RETR index.html": b"<title>Other website</title>",
    })
    assert strona_ftp.znajdz_katalog_strony(ftp) == root
    assert f"RETR {root}/brand-site.css" in ftp.requests


def test_refuses_unrelated_website():
    ftp = FakeFtp({
        "RETR index.html": b"<title>Other company</title>",
        "RETR /public_html/index.html": b"<title>Other company</title>",
        "RETR /public_html/brand-site.css": b"body{}",
    })
    with pytest.raises(RuntimeError, match="Nie rozpoznano katalogu"):
        strona_ftp.znajdz_katalog_strony(ftp)


def test_missing_css_is_not_verified_root():
    ftp = FakeFtp({
        "RETR index.html": b"notarai - https://app.notarai.pl",
    })
    with pytest.raises(RuntimeError, match="Nie rozpoznano katalogu"):
        strona_ftp.znajdz_katalog_strony(ftp)


class ManifestFtp:
    """Serwer w pamieci: pliki pod sciezkami bezwzglednymi."""

    def __init__(self, pliki=None):
        self.pliki = dict(pliki or {})
        self.katalogi = []
        self.wyslane = []

    def retrbinary(self, command, callback):
        sciezka = command.split(" ", 1)[1]
        if sciezka not in self.pliki:
            raise ftplib.error_perm("550 File unavailable")
        callback(self.pliki[sciezka])

    def storbinary(self, command, plik):
        sciezka = command.split(" ", 1)[1]
        self.pliki[sciezka] = plik.read()
        self.wyslane.append(sciezka)

    def mkd(self, sciezka):
        self.katalogi.append(sciezka)


def _strona(tmp_path, pliki):
    for nazwa, tresc in pliki.items():
        cel = tmp_path / nazwa
        cel.parent.mkdir(parents=True, exist_ok=True)
        cel.write_text(tresc, encoding="utf-8")
    return str(tmp_path)


def test_first_publish_sends_everything_and_writes_manifest(tmp_path):
    lokalny = _strona(tmp_path, {"index.html": "a", "v2/premium.css": "b", ".ukryty": "x"})
    ftp = ManifestFtp()
    wyslane = strona_ftp.wyslij_zmiany(ftp, lokalny, "/public_html")
    assert wyslane == ["index.html", "v2/premium.css"]
    assert ftp.wyslane == ["/public_html/index.html", "/public_html/v2/premium.css",
                           "/public_html/" + strona_ftp.MANIFEST]
    assert "/public_html/v2" in ftp.katalogi
    assert "/public_html/.ukryty" not in ftp.pliki


def test_second_publish_sends_only_changed_files(tmp_path):
    lokalny = _strona(tmp_path, {"index.html": "a", "kalkulator/index.html": "b", "style.css": "c"})
    ftp = ManifestFtp()
    strona_ftp.wyslij_zmiany(ftp, lokalny, "/public_html")
    ftp.wyslane.clear()
    assert strona_ftp.wyslij_zmiany(ftp, lokalny, "/public_html") == []
    assert ftp.wyslane == []
    (tmp_path / "style.css").write_text("zmiana", encoding="utf-8")
    (tmp_path / "nowa").mkdir()
    (tmp_path / "nowa" / "index.html").write_text("n", encoding="utf-8")
    assert strona_ftp.wyslij_zmiany(ftp, lokalny, "/public_html") == ["nowa/index.html", "style.css"]
    assert ftp.wyslane[-1] == "/public_html/" + strona_ftp.MANIFEST
    assert ftp.pliki["/public_html/style.css"] == b"zmiana"


def test_file_removed_locally_stays_on_server(tmp_path):
    lokalny = _strona(tmp_path, {"index.html": "a", "stara.html": "s"})
    ftp = ManifestFtp()
    strona_ftp.wyslij_zmiany(ftp, lokalny, "/")
    (tmp_path / "stara.html").unlink()
    assert strona_ftp.wyslij_zmiany(ftp, lokalny, "/") == []
    assert ftp.pliki["/stara.html"] == b"s"


def test_broken_manifest_means_full_publish_and_missing_index_stops(tmp_path):
    lokalny = _strona(tmp_path, {"index.html": "a"})
    ftp = ManifestFtp({"/" + strona_ftp.MANIFEST: b"to nie json"})
    assert strona_ftp.czytaj_manifest(ftp, "/") == {}
    assert strona_ftp.wyslij_zmiany(ftp, lokalny, "/") == ["index.html"]
    pusty = tmp_path / "pusty"
    pusty.mkdir()
    with pytest.raises(RuntimeError):
        strona_ftp.wyslij_zmiany(ManifestFtp(), str(pusty), "/")
