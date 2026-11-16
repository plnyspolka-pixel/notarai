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


class FakeFtpZapis:
    """Serwer FTPS w pamieci: pliki pod sciezkami absolutnymi."""

    def __init__(self, pliki=None):
        self.pliki = dict(pliki or {})
        self.wyslane = []

    def retrbinary(self, command, callback):
        sciezka = command.split(" ", 1)[1]
        if sciezka not in self.pliki:
            raise ftplib.error_perm("550 File unavailable")
        callback(self.pliki[sciezka])

    def storbinary(self, command, f):
        sciezka = command.split(" ", 1)[1]
        self.pliki[sciezka] = f.read()
        self.wyslane.append(sciezka)

    def mkd(self, sciezka):
        raise ftplib.error_perm("550 exists")


def _strona(tmp_path, pliki):
    for nazwa, tresc in pliki.items():
        p = tmp_path / "strona" / nazwa
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(tresc)
    return str(tmp_path / "strona")


def test_wyslij_zmiany_pierwszy_raz_wysyla_wszystko_i_manifest(tmp_path):
    lokalny = _strona(tmp_path, {"index.html": b"a", "blog/index.html": b"b", ".git/x": b"no"})
    ftp = FakeFtpZapis({"/public_html/index.html": b"stare"})
    kopia = tmp_path / "kopia"
    zmienione = strona_ftp.wyslij_zmiany(ftp, lokalny, "/public_html", str(kopia))
    assert zmienione == ["blog/index.html", "index.html"]
    assert ftp.pliki["/public_html/index.html"] == b"a"
    assert "/public_html/.git/x" not in ftp.pliki
    assert f"/public_html/{strona_ftp.MANIFEST}" == ftp.wyslane[-1]
    # Kopia zawiera poprzednia wersje nadpisanego pliku, nowych plikow nie.
    assert (kopia / "index.html").read_bytes() == b"stare"
    assert not (kopia / "blog" / "index.html").exists()


def test_wyslij_zmiany_drugi_raz_tylko_zmienione(tmp_path):
    lokalny = _strona(tmp_path, {"index.html": b"a", "style.css": b"c"})
    ftp = FakeFtpZapis()
    strona_ftp.wyslij_zmiany(ftp, lokalny, "/")
    ftp.wyslane.clear()
    (tmp_path / "strona" / "style.css").write_bytes(b"c2")
    assert strona_ftp.wyslij_zmiany(ftp, lokalny, "/") == ["style.css"]
    assert ftp.wyslane == ["/style.css", f"/{strona_ftp.MANIFEST}"]
    ftp.wyslane.clear()
    assert strona_ftp.wyslij_zmiany(ftp, lokalny, "/") == []
    assert ftp.wyslane == []
