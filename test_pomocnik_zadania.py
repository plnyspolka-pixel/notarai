"""Testy wykonawcow zlecen pomocnika. Atrapa portalu, zero polaczen z KRZ."""
import krz_portal
import rejestry
from pomocnik import zadania


class AtrapaPortalu:
    """Zachowuje sie jak krz_cdp.StronaKRZ, ale niczego nie otwiera."""

    def __init__(self, teksty, psuj_dla=()):
        self.teksty, self.i = list(teksty), 0
        self.psuj_dla = set(psuj_dla)
        self.wpisane = []

    def otworz(self): pass
    def wybierz_zakladke(self, nazwa): pass
    def wpisz_identyfikator(self, wartosc):
        if wartosc in self.psuj_dla:
            raise RuntimeError(f"portal odmowil dla {wartosc}")
        self.wpisane.append(wartosc)
    def wyszukaj(self): pass
    def wyczysc(self): pass
    def tekst_wyniku(self):
        tekst = self.teksty[self.i % len(self.teksty)]
        self.i += 1
        return tekst
    def zrzut(self, cel): cel.write_bytes(b"png")


class AtrapaPolaczenia:
    def __init__(self): self.zamkniete = False
    def zamknij(self): self.zamkniete = True


def polaczenie_z(portal):
    polaczenie = AtrapaPolaczenia()
    def polacz(*a, **k):
        return polaczenie, portal
    polacz.polaczenie = polaczenie
    return polacz


def zlecenie(osoby, sprawa="abc123"):
    return {"id": "z1", "rodzaj": "krz", "sprawa": sprawa, "tresc": {"osoby": osoby}}


def test_sprawdza_kazda_osobe(tmp_path, monkeypatch):
    monkeypatch.setattr(zadania, "katalog_zrzutow", lambda sprawa: tmp_path)
    monkeypatch.setattr(krz_portal, "ODSTEP_S", 0)
    portal = AtrapaPortalu(["Brak wyników"])
    raport = zadania.krz(zlecenie([
        {"pesel": "44051401359", "etykieta": "zbywca"},
        {"pesel": "85031512331", "etykieta": "nabywca"},
    ]), polacz=polaczenie_z(portal), portal_z=lambda s: portal)

    assert [s["etykieta"] for s in raport["sprawdzenia"]] == ["zbywca", "nabywca"]
    assert all(s["status"] == "brak_wpisu" for s in raport["sprawdzenia"])
    assert raport["bledy"] == []
    assert len(portal.wpisane) == 4, "dwie zakladki na osobe"


def test_blad_jednej_osoby_nie_przerywa_reszty(tmp_path, monkeypatch):
    monkeypatch.setattr(zadania, "katalog_zrzutow", lambda sprawa: tmp_path)
    monkeypatch.setattr(krz_portal, "ODSTEP_S", 0)
    portal = AtrapaPortalu(["Brak wyników"], psuj_dla={"44051401359"})
    raport = zadania.krz(zlecenie([
        {"pesel": "44051401359", "etykieta": "zbywca"},
        {"pesel": "85031512331", "etykieta": "nabywca"},
    ]), polacz=polaczenie_z(portal), portal_z=lambda s: portal)

    assert [s["etykieta"] for s in raport["sprawdzenia"]] == ["nabywca"]
    assert len(raport["bledy"]) == 1 and "zbywca" in raport["bledy"][0]


def test_komunikat_bledu_nie_niesie_numeru(tmp_path, monkeypatch):
    monkeypatch.setattr(zadania, "katalog_zrzutow", lambda sprawa: tmp_path)
    monkeypatch.setattr(krz_portal, "ODSTEP_S", 0)
    portal = AtrapaPortalu(["Brak wyników"], psuj_dla={"44051401359"})
    raport = zadania.krz(zlecenie([{"pesel": "44051401359", "etykieta": "zbywca"}]),
                         polacz=polaczenie_z(portal), portal_z=lambda s: portal)
    assert "44051401359" not in str(raport["bledy"])


def test_zawsze_zamyka_polaczenie(tmp_path, monkeypatch):
    """Przegladarka zostaje otwarta dla notariusza, ale nasz kanal sterowania nie."""
    monkeypatch.setattr(zadania, "katalog_zrzutow", lambda sprawa: tmp_path)
    monkeypatch.setattr(krz_portal, "ODSTEP_S", 0)
    portal = AtrapaPortalu(["Brak wyników"])
    polacz = polaczenie_z(portal)
    zadania.krz(zlecenie([{"pesel": "44051401359"}]), polacz=polacz, portal_z=lambda s: portal)
    assert polacz.polaczenie.zamkniete


def test_zlecenie_bez_osob_mowi_o_tym_wprost(tmp_path, monkeypatch):
    monkeypatch.setattr(zadania, "katalog_zrzutow", lambda sprawa: tmp_path)
    raport = zadania.krz(zlecenie([]), polacz=polaczenie_z(AtrapaPortalu([])), portal_z=lambda s: s)
    assert raport["sprawdzenia"] == [] and raport["bledy"]


def test_zrzuty_zostaja_u_notariusza(tmp_path, monkeypatch):
    monkeypatch.setattr(zadania, "katalog_zrzutow", lambda sprawa: tmp_path)
    monkeypatch.setattr(krz_portal, "ODSTEP_S", 0)
    portal = AtrapaPortalu(["Brak wyników"])
    zadania.krz(zlecenie([{"pesel": "44051401359"}]),
                polacz=polaczenie_z(portal), portal_z=lambda s: portal)
    pliki = list(tmp_path.glob("krz_*.png"))
    assert len(pliki) == 2
    assert all("1359" in p.name and "44051401359" not in p.name for p in pliki), \
        "nazwa zrzutu niesie cztery koncowe cyfry, nigdy caly numer"


def test_maskowanie_zgodne_z_tym_w_sladzie_audytowym():
    """krz_portal.maskuj powtarza rejestry.maskuj_pesel, zeby nie zalezec od
    serwera. Gdyby sie rozjechaly, zamaskowany numer przestalby pasowac do
    wpisow w sprawie - ten test ma to zlapac od razu."""
    for numer in ["44051401359", "85031512331", "123", "", "abc", "1234567890123"]:
        assert krz_portal.maskuj(numer) == rejestry.maskuj_pesel(numer), numer
