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

    def delete_objects(self, Bucket, Delete):
        for o in Delete["Objects"]:
            self.obiekty.pop(o["Key"], None)

    def get_paginator(self, nazwa):
        return _Paginator(self, nazwa)


class _NoSuchKey(Exception):
    pass


_NoSuchKey.__name__ = "NoSuchKey"


class _Paginator:
    def __init__(self, s3, nazwa="list_objects_v2"):
        self.s3 = s3
        self.nazwa = nazwa

    def paginate(self, Bucket, Prefix, Delimiter=None):
        klucze = [k for k in self.s3.obiekty if k.startswith(Prefix)]
        if self.nazwa == "list_object_versions":
            # Bucket ma wersjonowanie: kazdy plik ma tu jedna wersje biezaca.
            yield {"Versions": [{"Key": k, "VersionId": "v1"} for k in sorted(klucze)]}
            return
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

    def test_druga_kopia_widzi_projekt(self, magazyn_s3):
        """Blad z produkcji 20.09.2026: sporzadzenie projektu dokladalo
        projekt.docx i projekt.txt, nie ruszajac sprawa.json. Znacznik
        pilnowal wtedy samego sprawa.json, wiec druga kopia aplikacji uznawala
        swoja kopie za aktualna - notariusz nie mogl wrocic do wlasnego
        projektu ani go pobrac, a starsze sprawy dzialaly."""
        magazyn, _, tmp = magazyn_s3
        zn = magazyn.kancelaria_var.set("kowalski")
        try:
            kontenerA = tmp / "a" / "abc123"
            kontenerB = tmp / "b" / "abc123"

            self._zapisz(magazyn, kontenerA, {"id": "abc123"})
            assert magazyn.pobierz_sprawe(kontenerB) is True

            # A sporzadza projekt - metadane sprawy bez zmian
            (kontenerA / "projekt.docx").write_bytes(b"PK-docx")
            (kontenerA / "projekt.txt").write_text("pierwsza wersja", encoding="utf-8")
            magazyn.utrwal_sprawe(kontenerA)

            assert magazyn.pobierz_sprawe(kontenerB) is True
            assert (kontenerB / "projekt.docx").exists(), "projekt musi byc widoczny"
            assert (kontenerB / "projekt.txt").read_text("utf-8") == "pierwsza wersja"

            # A poprawia projekt - zmiana tresci istniejacego pliku
            (kontenerA / "projekt.txt").write_text("po poprawkach", encoding="utf-8")
            magazyn.utrwal_sprawe(kontenerA)

            assert magazyn.pobierz_sprawe(kontenerB) is True
            assert (kontenerB / "projekt.txt").read_text("utf-8") == "po poprawkach"
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


class TestUsuwanieSprawy:
    """Prawo do usuniecia danych: usunieta ma znaczyc usunieta."""

    def test_kasuje_dysk_i_wszystkie_wersje_w_s3(self, magazyn_s3):
        magazyn, atrapa, tmp = magazyn_s3
        zn = magazyn.kancelaria_var.set("kowalski")
        try:
            katalog = magazyn.sprawy_dir(tmp) / "abc123"
            (katalog / "skany").mkdir(parents=True)
            (katalog / "sprawa.json").write_text('{"id": "abc123"}', encoding="utf-8")
            (katalog / "skany" / "dowod.pdf").write_bytes(b"%PDF")
            magazyn.utrwal_sprawe(katalog)
            assert any("abc123" in k for k in atrapa.obiekty)

            usuniete = magazyn.usun_sprawe(katalog)

            assert usuniete >= 2
            assert not katalog.exists(), "katalog sprawy ma zniknac z dysku"
            assert not any("abc123" in k for k in atrapa.obiekty), "w S3 nie moze nic zostac"
        finally:
            magazyn.kancelaria_var.reset(zn)

    def test_nie_rusza_spraw_innej_kancelarii(self, magazyn_s3):
        magazyn, atrapa, tmp = magazyn_s3
        zn = magazyn.kancelaria_var.set("kancelaria-a")
        try:
            katalog_a = magazyn.sprawy_dir(tmp) / "sprawa1"
            katalog_a.mkdir(parents=True)
            (katalog_a / "sprawa.json").write_text("{}")
            magazyn.utrwal_sprawe(katalog_a)
        finally:
            magazyn.kancelaria_var.reset(zn)

        zn = magazyn.kancelaria_var.set("kancelaria-b")
        try:
            katalog_b = magazyn.sprawy_dir(tmp) / "sprawa1"
            katalog_b.mkdir(parents=True)
            (katalog_b / "sprawa.json").write_text("{}")
            magazyn.utrwal_sprawe(katalog_b)
            magazyn.usun_sprawe(katalog_b)
        finally:
            magazyn.kancelaria_var.reset(zn)

        assert any("kancelaria-a/sprawy/sprawa1" in k for k in atrapa.obiekty), \
            "usuniecie u jednej kancelarii nie moze dotknac drugiej"

    def test_tryb_lokalny_kasuje_sam_katalog(self, tmp_path):
        import magazyn
        importlib.reload(magazyn)
        katalog = tmp_path / "sprawy" / "abc123"
        katalog.mkdir(parents=True)
        (katalog / "sprawa.json").write_text("{}")
        assert magazyn.usun_sprawe(katalog) == 0
        assert not katalog.exists()


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


class TestUsuwanieKancelarii:
    def _zapisz(self, magazyn, tmp, kancelaria, sprawa="s1"):
        zn = magazyn.kancelaria_var.set(kancelaria)
        try:
            katalog = magazyn.sprawy_dir(tmp) / sprawa
            katalog.mkdir(parents=True)
            (katalog / "sprawa.json").write_text("{}")
            magazyn.utrwal_sprawe(katalog)
        finally:
            magazyn.kancelaria_var.reset(zn)

    def test_kasuje_wszystko_pod_kancelaria(self, magazyn_s3):
        magazyn, atrapa, tmp = magazyn_s3
        self._zapisz(magazyn, tmp, "kancelaria-a")
        atrapa.obiekty["kancelarie/kancelaria-a/zlecenia/z1.json"] = b"{}"
        atrapa.obiekty["kancelarie/kancelaria-a/pomocnicy/p1.json"] = b"{}"

        usuniete = magazyn.usun_kancelarie("kancelaria-a", tmp)

        assert usuniete == 3
        assert not any(k.startswith("kancelarie/kancelaria-a/") for k in atrapa.obiekty)
        assert not (tmp / "kancelarie" / "kancelaria-a").exists()

    def test_nie_rusza_kancelarii_o_podobnym_identyfikatorze(self, magazyn_s3):
        magazyn, atrapa, tmp = magazyn_s3
        self._zapisz(magazyn, tmp, "kancelaria-a")
        self._zapisz(magazyn, tmp, "kancelaria-ab")
        atrapa.obiekty["kancelarie/admin/kancelarie.json"] = b"{}"

        magazyn.usun_kancelarie("kancelaria-a", tmp)

        assert any(k.startswith("kancelarie/kancelaria-ab/") for k in atrapa.obiekty)
        assert "kancelarie/admin/kancelarie.json" in atrapa.obiekty
        assert (tmp / "kancelarie" / "kancelaria-ab").exists()

    @pytest.mark.parametrize("zly", ["", "admin", "lokalna", "../admin", "a/b"])
    def test_odrzuca_zastrzezone_i_sciezki(self, magazyn_s3, zly):
        magazyn, atrapa, tmp = magazyn_s3
        atrapa.obiekty["kancelarie/admin/kancelarie.json"] = b"{}"
        with pytest.raises(ValueError):
            magazyn.usun_kancelarie(zly, tmp)
        assert "kancelarie/admin/kancelarie.json" in atrapa.obiekty


class TestTylkoZmienionePliki:
    """Dwie kopie aplikacji zapisuja te sama sprawe: kazda wysyla tylko to, co sama
    zmienila, wiec nie nadpisuje nowszych zmian drugiej w innych plikach."""

    def test_stara_kopia_nie_nadpisuje_zmian_drugiej(self, magazyn_s3):
        magazyn, atrapa, tmp = magazyn_s3
        zn = magazyn.kancelaria_var.set("kowalski")
        try:
            a, b = tmp / "a" / "abc123", tmp / "b" / "abc123"
            a.mkdir(parents=True)
            (a / "sprawa.json").write_text('{"id": "abc123"}', encoding="utf-8")
            (a / "odczyt.json").write_text('{"wersja": 1}', encoding="utf-8")
            (a / "projekt.txt").write_text("v1", encoding="utf-8")
            magazyn.utrwal_sprawe(a)
            assert magazyn.pobierz_sprawe(b) is True

            # A poprawia odczyt; B (z kopia sprzed tej zmiany) zapisuje projekt.
            (a / "odczyt.json").write_text('{"wersja": 2}', encoding="utf-8")
            magazyn.utrwal_sprawe(a)
            (b / "projekt.txt").write_text("v2 z kopii B", encoding="utf-8")
            magazyn.utrwal_sprawe(b)

            klucz = lambda n: f"kancelarie/kowalski/sprawy/abc123/{n}"  # noqa: E731
            assert atrapa.obiekty[klucz("odczyt.json")] == b'{"wersja": 2}', "B nie moze cofnac zmiany A"
            assert atrapa.obiekty[klucz("projekt.txt")] == "v2 z kopii B".encode()
            # Obie kopie dociagaja zmiane drugiej.
            assert magazyn.pobierz_sprawe(b) and json.loads((b / "odczyt.json").read_text())["wersja"] == 2
            assert magazyn.pobierz_sprawe(a) and (a / "projekt.txt").read_text("utf-8") == "v2 z kopii B"
        finally:
            magazyn.kancelaria_var.reset(zn)

    def test_wysyla_i_pobiera_tylko_zmienione(self, magazyn_s3):
        magazyn, atrapa, tmp = magazyn_s3
        zn = magazyn.kancelaria_var.set("kowalski")
        try:
            a, b = tmp / "a" / "abc123", tmp / "b" / "abc123"
            (a / "skany").mkdir(parents=True)
            (a / "sprawa.json").write_text("{}", encoding="utf-8")
            for i in range(5):
                (a / "skany" / f"s{i}.png").write_bytes(b"PNG" * (i + 1))
            magazyn.utrwal_sprawe(a)
            magazyn.pobierz_sprawe(b)
            wyslane = []
            oryginal = atrapa.put_object
            atrapa.put_object = lambda **kw: wyslane.append(kw["Key"]) or oryginal(**kw)
            (a / "sprawa.json").write_text('{"nazwa": "x"}', encoding="utf-8")
            magazyn.utrwal_sprawe(a)
            assert [k.rsplit("/", 1)[1] for k in wyslane] == ["sprawa.json"]
            przed = atrapa.pobrania
            assert magazyn.pobierz_sprawe(b) is True
            assert atrapa.pobrania - przed == 1, "skany sie nie zmienily - nie schodza ponownie"
            assert not any(magazyn._SKROTY in k for k in atrapa.obiekty)
        finally:
            magazyn.kancelaria_var.reset(zn)

    def test_sprawa_sprzed_skrotow_nie_jest_wysylana_od_nowa(self, magazyn_s3):
        magazyn, atrapa, tmp = magazyn_s3
        zn = magazyn.kancelaria_var.set("kowalski")
        try:
            a = tmp / "a" / "abc123"
            a.mkdir(parents=True)
            (a / "sprawa.json").write_text("{}", encoding="utf-8")
            (a / "odczyt.json").write_text("{}", encoding="utf-8")
            magazyn.utrwal_sprawe(a)
            (a / magazyn._SKROTY).unlink()              # stan sprzed tej zmiany
            assert magazyn.pobierz_sprawe(a) is True    # znacznik zgodny - skroty z plikow
            wyslane = []
            oryginal = atrapa.put_object
            atrapa.put_object = lambda **kw: wyslane.append(kw["Key"]) or oryginal(**kw)
            magazyn.utrwal_sprawe(a)
            assert wyslane == []
        finally:
            magazyn.kancelaria_var.reset(zn)
