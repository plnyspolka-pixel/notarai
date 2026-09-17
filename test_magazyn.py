"""Testy magazynu - tryb lokalny i S3 (atrapa klienta, bez sieci)."""
import importlib
import json

import pytest


def _etag(dane: bytes) -> str:
    """Tak jak S3: ETag to skrot tresci w cudzyslowie."""
    import hashlib
    return '"' + hashlib.md5(dane).hexdigest() + '"'


class AtrapaS3:
    """Minimalna atrapa boto3 S3: put/get/head/list w slowniku."""

    def __init__(self):
        self.obiekty: dict[str, bytes] = {}
        self.szyfrowanie: dict[str, str] = {}
        self.pobrania = 0

    def put_object(self, Bucket, Key, Body, **kw):
        dane = Body if isinstance(Body, bytes) else Body.encode()
        self.obiekty[Key] = dane
        self.szyfrowanie[Key] = kw.get("ServerSideEncryption", "")
        return {"ETag": _etag(dane)}

    def get_object(self, Bucket, Key):
        if Key not in self.obiekty:
            raise _NoSuchKey()
        import io
        self.pobrania += 1
        return {"Body": io.BytesIO(self.obiekty[Key])}

    def head_object(self, Bucket, Key):
        if Key not in self.obiekty:
            raise _NoSuchKey()
        return {"ETag": _etag(self.obiekty[Key])}

    def get_paginator(self, nazwa):
        return _Paginator(self)


class _NoSuchKey(Exception):
    pass


_NoSuchKey.__name__ = "NoSuchKey"


class _Paginator:
    def __init__(self, s3):
        self.s3 = s3

    def paginate(self, Bucket, Prefix, Delimiter=None):
        klucze = [k for k in self.s3.obiekty if k.startswith(Prefix)]
        if Delimiter:
            prefiksy = sorted({
                Prefix + k[len(Prefix):].split(Delimiter)[0] + Delimiter
                for k in klucze if Delimiter in k[len(Prefix):]
            })
            yield {"CommonPrefixes": [{"Prefix": p} for p in prefiksy]}
        else:
            yield {"Contents": [
                {"Key": k, "ETag": _etag(self.s3.obiekty[k])} for k in sorted(klucze)
            ]}


@pytest.fixture
def magazyn_s3(tmp_path, monkeypatch):
    """magazyn w trybie s3 z atrapa klienta i tymczasowym katalogiem danych."""
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "s3")
    monkeypatch.setenv("PIECZAPP_S3_BUCKET", "testowy-bucket")
    import magazyn
    importlib.reload(magazyn)
    atrapa = AtrapaS3()
    monkeypatch.setattr(magazyn, "_s3", atrapa)
    yield magazyn, atrapa, tmp_path
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "lokalny")
    importlib.reload(magazyn)


def test_lokalny_sciezka_bez_zmian(tmp_path):
    """Kancelaria 'lokalna' -> dokladnie dawne dane/sprawy."""
    import magazyn
    importlib.reload(magazyn)
    assert magazyn.sprawy_dir(tmp_path) == tmp_path / "sprawy"


def test_lokalny_utrwal_jest_noop(tmp_path):
    import magazyn
    importlib.reload(magazyn)
    katalog = tmp_path / "sprawy" / "abc123"
    katalog.mkdir(parents=True)
    (katalog / "sprawa.json").write_text("{}")
    magazyn.utrwal_sprawe(katalog)  # nie moze rzucic ani niczego wyslac
    assert magazyn.pobierz_sprawe(katalog) is True


def test_s3_sciezka_per_kancelaria(magazyn_s3):
    magazyn, _, tmp = magazyn_s3
    znacznik = magazyn.kancelaria_var.set("kowalski")
    try:
        assert magazyn.sprawy_dir(tmp) == tmp / "kancelarie" / "kowalski" / "sprawy"
    finally:
        magazyn.kancelaria_var.reset(znacznik)


def test_s3_utrwal_i_pobierz(magazyn_s3):
    magazyn, atrapa, tmp = magazyn_s3
    znacznik = magazyn.kancelaria_var.set("kowalski")
    try:
        katalog = magazyn.sprawy_dir(tmp) / "abc123"
        (katalog / "skany").mkdir(parents=True)
        (katalog / "sprawa.json").write_text(json.dumps({"id": "abc123"}), "utf-8")
        (katalog / "skany" / "dowod.pdf").write_bytes(b"%PDF-atrapa")

        magazyn.utrwal_sprawe(katalog)
        assert "kancelarie/kowalski/sprawy/abc123/sprawa.json" in atrapa.obiekty
        assert "kancelarie/kowalski/sprawy/abc123/skany/dowod.pdf" in atrapa.obiekty
        # kazdy obiekt szyfrowany po stronie serwera
        assert all(atrapa.szyfrowanie.values())

        # symulacja restartu kontenera: pusty dysk, dane wracaja z S3
        import shutil
        shutil.rmtree(katalog)
        assert magazyn.pobierz_sprawe(katalog) is True
        assert json.loads((katalog / "sprawa.json").read_text())["id"] == "abc123"
        assert (katalog / "skany" / "dowod.pdf").read_bytes() == b"%PDF-atrapa"
    finally:
        magazyn.kancelaria_var.reset(znacznik)


def test_s3_izolacja_kancelarii(magazyn_s3):
    """Kancelaria A nie widzi spraw kancelarii B."""
    magazyn, atrapa, tmp = magazyn_s3
    zn = magazyn.kancelaria_var.set("kancelaria-a")
    try:
        katalog = magazyn.sprawy_dir(tmp) / "sprawa1"
        katalog.mkdir(parents=True)
        (katalog / "sprawa.json").write_text("{}")
        magazyn.utrwal_sprawe(katalog)
    finally:
        magazyn.kancelaria_var.reset(zn)

    zn = magazyn.kancelaria_var.set("kancelaria-b")
    try:
        assert magazyn.identyfikatory_spraw(magazyn.sprawy_dir(tmp)) == []
        assert magazyn.pobierz_sprawe(magazyn.sprawy_dir(tmp) / "sprawa1") is False
    finally:
        magazyn.kancelaria_var.reset(zn)


class TestDwieKopieAplikacji:
    """Aplikacja moze dzialac w kilku kontenerach naraz.

    Dysk kazdego z nich to tylko pamiec podreczna, wiec przed odczytem trzeba
    sprawdzic, czy druga kopia nie zmienila sprawy w S3.
    """

    @staticmethod
    def _zapisz(magazyn, katalog, tresc):
        katalog.mkdir(parents=True, exist_ok=True)
        (katalog / "sprawa.json").write_text(json.dumps(tresc), encoding="utf-8")
        magazyn.utrwal_sprawe(katalog)

    def test_druga_kopia_widzi_zmiane(self, magazyn_s3):
        magazyn, _, tmp = magazyn_s3
        zn = magazyn.kancelaria_var.set("kowalski")
        try:
            kontenerA = tmp / "a" / "abc123"
            kontenerB = tmp / "b" / "abc123"

            self._zapisz(magazyn, kontenerA, {"id": "abc123", "etap": 1})
            assert magazyn.pobierz_sprawe(kontenerB) is True
            assert json.loads((kontenerB / "sprawa.json").read_text())["etap"] == 1

            # kontener A zmienia sprawe
            self._zapisz(magazyn, kontenerA, {"id": "abc123", "etap": 3})

            # kontener B ma stara kopie na dysku - musi ja odswiezyc
            assert magazyn.pobierz_sprawe(kontenerB) is True
            assert json.loads((kontenerB / "sprawa.json").read_text())["etap"] == 3
        finally:
            magazyn.kancelaria_var.reset(zn)

    def test_aktualna_kopia_nie_jest_pobierana_ponownie(self, magazyn_s3):
        magazyn, atrapa, tmp = magazyn_s3
        zn = magazyn.kancelaria_var.set("kowalski")
        try:
            katalog = tmp / "a" / "abc123"
            self._zapisz(magazyn, katalog, {"id": "abc123"})
            przed = atrapa.pobrania
            assert magazyn.pobierz_sprawe(katalog) is True
            assert atrapa.pobrania == przed, "aktualna kopia nie powinna schodzic z S3"
        finally:
            magazyn.kancelaria_var.reset(zn)

    def test_znacznik_nie_trafia_do_s3(self, magazyn_s3):
        magazyn, atrapa, tmp = magazyn_s3
        zn = magazyn.kancelaria_var.set("kowalski")
        try:
            katalog = tmp / "a" / "abc123"
            self._zapisz(magazyn, katalog, {"id": "abc123"})
            assert (katalog / magazyn._ZNACZNIK).exists()
            assert not any(magazyn._ZNACZNIK in k for k in atrapa.obiekty)
        finally:
            magazyn.kancelaria_var.reset(zn)

    def test_brak_sprawy_w_s3_nie_kasuje_lokalnej(self, magazyn_s3):
        """Sprawa wlasnie powstaje i nie zostala jeszcze utrwalona."""
        magazyn, _, tmp = magazyn_s3
        zn = magazyn.kancelaria_var.set("kowalski")
        try:
            katalog = tmp / "a" / "nowa123"
            katalog.mkdir(parents=True)
            (katalog / "sprawa.json").write_text('{"id": "nowa123"}', encoding="utf-8")
            assert magazyn.pobierz_sprawe(katalog) is True
            assert json.loads((katalog / "sprawa.json").read_text())["id"] == "nowa123"
        finally:
            magazyn.kancelaria_var.reset(zn)


def test_s3_lista_po_restarcie(magazyn_s3):
    magazyn, atrapa, tmp = magazyn_s3
    zn = magazyn.kancelaria_var.set("kowalski")
    try:
        for nr in ("aaa", "bbb"):
            katalog = magazyn.sprawy_dir(tmp) / nr
            katalog.mkdir(parents=True)
            (katalog / "sprawa.json").write_text("{}")
            magazyn.utrwal_sprawe(katalog)
        import shutil
        shutil.rmtree(tmp / "kancelarie")
        assert magazyn.identyfikatory_spraw(magazyn.sprawy_dir(tmp)) == ["aaa", "bbb"]
    finally:
        magazyn.kancelaria_var.reset(zn)
