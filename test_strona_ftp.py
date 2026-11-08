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
