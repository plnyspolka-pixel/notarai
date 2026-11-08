"""Taksa notarialna - silnik liczenia kosztow czynnosci dla klienta kancelarii.

Zrodla (sprawdzone 07.11.2026 w Dzienniku Ustaw):
  - rozporzadzenie Ministra Sprawiedliwosci z 28.06.2004 r. w sprawie
    maksymalnych stawek taksy notarialnej, tekst jednolity Dz.U. 2024 poz. 1566
    (stawki do 4.11.2026 r.),
  - rozporzadzenie zmieniajace z 13.10.2026 r., Dz.U. 2026 poz. 1370,
    w zyciu od 5.11.2026 r. (nowe progi powyzej 2 mln zl, limity 25 000 /
    15 000 zl, wypisy 12/10/8 zl za strone, wniosek KW 300 zl, nowe stawki
    stale),
  - ustawa o kosztach sadowych w sprawach cywilnych (oplaty od wpisow w KW),
  - ustawa o podatku od czynnosci cywilnoprawnych (PCC 2 %, hipoteka 19 zl).

Uklad i wartosci domyslne (wypisy, PCC, hipoteka, lista dokumentow, lista
czynnosci stalych) pochodza z C.A.R. - Cyfrowego Asystenta Rejenta, kalkulatora
napisanego przez notariusza dla notariuszy (https://lukaszkupis-dev.github.io/CAR/).

Zasada jak w calej aplikacji: liczy kod, nie model. Model (kalkulator.py)
ustala tylko parametry rozmowy z klientem, a kwoty wychodza stad.
Wszystko w Decimal, zaokraglenie do grosza "pol w gore".
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

GROSZ = Decimal("0.01")
VAT = Decimal("0.23")

# Zmiana stawek: Dz.U. 2026 poz. 1370 weszla w zycie 5 listopada 2026 r.
ZMIANA_2026 = date(2026, 11, 5)

# Minimalne wynagrodzenie za prace - podstawa stawek z ustaw szczegolnych
# (art. 17^14 ust. 3 ustawy o spoldzielniach mieszkaniowych: 1/4,
# art. 19a ust. 7 ustawy o ochronie praw lokatorow: 1/10).
PLACA_MINIMALNA = {2025: Decimal("4666"), 2026: Decimal("4806")}

# Pozycje spoza rozporzadzenia, ktore kancelarie zwykle dolicza do aktu
# przenoszacego nieruchomosc. Wartosci domyslne z C.A.R.
PCC_PROCENT = Decimal("2")
PCC_HIPOTEKA = Decimal("19")          # hipoteka na zabezpieczenie wierzytelnosci o wysokosci nieustalonej
OPLATA_REJESTRACYJNA = Decimal("5")   # pozycja z C.A.R.; nie wynika z rozporzadzenia o taksie

# Oplaty sadowe od wnioskow o wpis w ksiedze wieczystej (u.k.s.c. art. 42-46).
OPLATY_SADOWE = {
    "wpis_wlasnosci": ("wpis prawa własności (użytkowania wieczystego, spółdzielczego prawa)", Decimal("200")),
    "wpis_hipoteki": ("wpis hipoteki", Decimal("200")),
    "wpis_ograniczonego_prawa": ("wpis służebności, użytkowania lub innego ograniczonego prawa", Decimal("200")),
    "wpis_roszczenia": ("wpis roszczenia (np. z umowy deweloperskiej lub przedwstępnej)", Decimal("150")),
    "wpis_wlasnosci_spadek": ("wpis własności na podstawie dziedziczenia, działu spadku lub zniesienia współwłasności", Decimal("150")),
    "zalozenie_kw": ("założenie księgi wieczystej", Decimal("100")),
    "wykreslenie_hipoteki": ("wykreślenie hipoteki", Decimal("100")),
    "inny_wpis": ("inny wpis w księdze wieczystej", Decimal("100")),
}

# ---------------------------------------------------------------- tabele stawek

_PROGI_WSPOLNE = [
    # (gorna granica, kwota bazowa, nadwyzka ponad, procent od nadwyzki)
    (3_000, 100, 0, "0"),
    (10_000, 100, 3_000, "0.03"),
    (30_000, 310, 10_000, "0.02"),
    (60_000, 710, 30_000, "0.01"),
    (1_000_000, 1_010, 60_000, "0.004"),
    (2_000_000, 4_770, 1_000_000, "0.002"),
]

TABELE = {
    "2004": {
        "id": "2004",
        "etykieta": "Stawki do 4 listopada 2026 r.",
        "podstawa": "rozporządzenie MS z 28.06.2004 r., t.j. Dz.U. 2024 poz. 1566",
        "progi": _PROGI_WSPOLNE + [(None, 6_770, 2_000_000, "0.0025")],
        "limit": Decimal("10000"), "limit_grupa1": Decimal("7500"),
        "wypis": [(None, Decimal("6"))],
        "wniosek_kw": Decimal("200"),      # § 16 (czynnosc niewymieniona)
        "niewymieniona": Decimal("200"),
        "podpis_z_suma_limit": Decimal("300"),
    },
    "2026": {
        "id": "2026",
        "etykieta": "Stawki od 5 listopada 2026 r.",
        "podstawa": "rozporządzenie MS z 28.06.2004 r. w brzmieniu od 5.11.2026 r. (Dz.U. 2026 poz. 1370)",
        "progi": _PROGI_WSPOLNE + [(5_000_000, 6_770, 2_000_000, "0.0025"),
                                   (None, 14_270, 5_000_000, "0.0015")],
        "limit": Decimal("25000"), "limit_grupa1": Decimal("15000"),
        "wypis": [(10, Decimal("12")), (20, Decimal("10")), (None, Decimal("8"))],
        "wniosek_kw": Decimal("300"),      # § 15c
        "niewymieniona": Decimal("400"),
        "podpis_z_suma_limit": Decimal("500"),
    },
}

ULAMKI = {"1": Decimal("1"), "1/2": Decimal("0.5"), "1/4": Decimal("0.25"), "1/10": Decimal("0.1")}

# ---------------------------------------------------------------- dokumenty

# Co klient zwykle przynosi do kancelarii - wykaz z C.A.R., pogrupowany wg urzedow.
DOKUMENTY = {
    "dowody": ("Strony czynności", "Dowody osobiste lub paszporty wszystkich stron, numery PESEL, stan cywilny (ustrój majątkowy)"),
    "podstawa_nabycia": ("Podstawa nabycia", "Dokument nabycia: akt notarialny, postanowienie sądu, przydział ze spółdzielni albo akt własności ziemi"),
    "numer_kw": ("Podstawa nabycia", "Numer księgi wieczystej"),
    "wypis_rejestru_gruntow": ("Starostwo powiatowe (w mieście na prawach powiatu: urząd miasta)", "Wypis z rejestru gruntów"),
    "wypis_z_wyrysem": ("Starostwo powiatowe (w mieście na prawach powiatu: urząd miasta)", "Wypis z wyrysem z rejestru gruntów"),
    "plan_lasu": ("Starostwo powiatowe (w mieście na prawach powiatu: urząd miasta)", "Zaświadczenie o uproszczonym planie urządzenia lasu"),
    "mpzp": ("Urząd miasta lub gminy", "Zaświadczenie o przeznaczeniu w miejscowym planie zagospodarowania przestrzennego"),
    "rewitalizacja": ("Urząd miasta lub gminy", "Zaświadczenie o położeniu na obszarze rewitalizacji"),
    "sse": ("Urząd miasta lub gminy", "Zaświadczenie o specjalnej strefie ekonomicznej"),
    "podzial": ("Urząd miasta lub gminy", "Decyzja o podziale nieruchomości z mapą, jeśli był podział"),
    "zameldowanie": ("Wydział meldunkowy", "Zaświadczenie o osobach zameldowanych (albo o braku zameldowanych)"),
    "spoldzielnia_zaleglosci": ("Spółdzielnia lub zarządca", "Zaświadczenie o braku zaległości w opłatach"),
    "spoldzielnia_prawo": ("Spółdzielnia lub zarządca", "Zaświadczenie ze spółdzielni o przysługującym prawie (do założenia księgi wieczystej)"),
    "us_art19": ("Urząd skarbowy", "Zaświadczenie o podatku od spadków i darowizn (art. 19), gdy nabycie nastąpiło przez spadek, darowiznę lub zasiedzenie"),
    "swiadectwo_energetyczne": ("Dodatkowo", "Świadectwo charakterystyki energetycznej"),
    "umowa_kredytu": ("Bank", "Umowa kredytu i zaświadczenie banku o hipotece (przy zakupie na kredyt)"),
    "akt_zgonu": ("Akt poświadczenia dziedziczenia", "Odpis aktu zgonu"),
    "akt_malzenstwa": ("Akt poświadczenia dziedziczenia", "Odpisy aktów małżeństwa"),
    "akt_urodzenia": ("Akt poświadczenia dziedziczenia", "Odpisy aktów urodzenia spadkobierców"),
    "pesel_zmarlego": ("Akt poświadczenia dziedziczenia", "Numer PESEL zmarłego (zaświadczenie z urzędu)"),
    "testament_dokument": ("Akt poświadczenia dziedziczenia", "Testament, jeśli został sporządzony"),
}

_DOK_NIERUCHOMOSC = ["dowody", "podstawa_nabycia", "numer_kw", "us_art19"]
_DOK_GRUNT = ["wypis_rejestru_gruntow", "wypis_z_wyrysem", "mpzp", "rewitalizacja", "plan_lasu", "sse", "podzial"]
_DOK_LOKAL = ["zameldowanie", "spoldzielnia_zaleglosci", "swiadectwo_energetyczne"]
_DOK_SPADEK = ["dowody", "akt_zgonu", "akt_malzenstwa", "akt_urodzenia", "pesel_zmarlego", "testament_dokument", "numer_kw"]

# ---------------------------------------------------------------- czynnosci z wartoscia

# Rodzaje aktow, za ktore stawka zalezy od wartosci (§ 3) - z ulamkiem z § 6
# i § 7. "pcc" to procent podatku od czynnosci cywilnoprawnych, ktory zwykle
# wchodzi w gre (0 = czynnosc bez PCC, np. darowizna albo umowa z VAT).
RODZAJE = [
    {"id": "sprzedaz_lokalu", "grupa": "Sprzedaż", "nazwa": "Sprzedaż lokalu mieszkalnego (odrębna własność)",
     "ulamek": "1/2", "podstawa": "§ 6 pkt 19", "pcc": "2", "sad": ["wpis_wlasnosci"],
     "dokumenty": _DOK_NIERUCHOMOSC + _DOK_LOKAL + ["umowa_kredytu"]},
    {"id": "sprzedaz_spoldzielcze", "grupa": "Sprzedaż", "nazwa": "Sprzedaż spółdzielczego własnościowego prawa do lokalu",
     "ulamek": "1/2", "podstawa": "§ 6 pkt 5", "pcc": "2", "sad": ["wpis_wlasnosci"],
     "dokumenty": ["dowody", "podstawa_nabycia", "numer_kw", "spoldzielnia_prawo", "spoldzielnia_zaleglosci", "zameldowanie", "us_art19", "umowa_kredytu"]},
    {"id": "sprzedaz_domu", "grupa": "Sprzedaż", "nazwa": "Sprzedaż nieruchomości zabudowanej domem jednorodzinnym",
     "ulamek": "1/2", "podstawa": "§ 6 pkt 18", "pcc": "2", "sad": ["wpis_wlasnosci"],
     "dokumenty": _DOK_NIERUCHOMOSC + _DOK_GRUNT + ["zameldowanie", "swiadectwo_energetyczne", "umowa_kredytu"]},
    {"id": "sprzedaz_dzialki_budowlanej", "grupa": "Sprzedaż", "nazwa": "Sprzedaż działki budowlanej (niezabudowanej)",
     "ulamek": "1/2", "podstawa": "§ 6 pkt 17", "pcc": "2", "sad": ["wpis_wlasnosci"],
     "dokumenty": _DOK_NIERUCHOMOSC + _DOK_GRUNT},
    {"id": "sprzedaz_inna", "grupa": "Sprzedaż", "nazwa": "Sprzedaż innej nieruchomości (rolna, lokal użytkowy, działka niebudowlana, udział, garaż)",
     "ulamek": "1", "podstawa": "§ 5 i § 3", "pcc": "2", "sad": ["wpis_wlasnosci"],
     "dokumenty": _DOK_NIERUCHOMOSC + _DOK_GRUNT},
    {"id": "przeniesienie_w_wykonaniu", "grupa": "Sprzedaż", "nazwa": "Umowa przenosząca własność w wykonaniu umowy warunkowej lub zobowiązującej",
     "ulamek": "1/2", "podstawa": "§ 6 pkt 2", "pcc": "2", "sad": ["wpis_wlasnosci"],
     "dokumenty": _DOK_NIERUCHOMOSC},
    {"id": "umowa_przedwstepna", "grupa": "Sprzedaż", "nazwa": "Umowa przedwstępna, warunkowa albo zobowiązująca",
     "ulamek": "1/2", "podstawa": "§ 6 pkt 1", "pcc": "0", "sad": [],
     "dokumenty": ["dowody", "podstawa_nabycia", "numer_kw"]},
    {"id": "umowa_deweloperska", "grupa": "Deweloper", "nazwa": "Umowa deweloperska",
     "ulamek": "1/2", "podstawa": "§ 6 pkt 15a", "pcc": "0", "sad": ["wpis_roszczenia"],
     "dokumenty": ["dowody"]},
    {"id": "przeniesienie_od_dewelopera", "grupa": "Deweloper", "nazwa": "Ustanowienie odrębnej własności lokalu i przeniesienie własności (od dewelopera, także dom z gruntem)",
     "ulamek": "1/2", "podstawa": "§ 6 pkt 16 i 18", "pcc": "0", "sad": ["zalozenie_kw", "wpis_wlasnosci"],
     "dokumenty": ["dowody", "umowa_kredytu"]},
    {"id": "darowizna_lokalu_grupa1", "grupa": "Darowizna", "nazwa": "Darowizna lokalu (odrębna własność) w najbliższej rodzinie z ulgą mieszkaniową",
     "ulamek": "1/2", "podstawa": "§ 6 pkt 15", "pcc": "0", "sad": ["wpis_wlasnosci"],
     "dokumenty": _DOK_NIERUCHOMOSC + ["zameldowanie", "spoldzielnia_zaleglosci"]},
    {"id": "darowizna_inna", "grupa": "Darowizna", "nazwa": "Darowizna innej nieruchomości (dom, działka, lokal bez ulgi, spółdzielcze prawo)",
     "ulamek": "1", "podstawa": "§ 5 i § 3", "pcc": "0", "sad": ["wpis_wlasnosci"],
     "dokumenty": _DOK_NIERUCHOMOSC + _DOK_GRUNT},
    {"id": "dozywocie", "grupa": "Inne umowy", "nazwa": "Umowa dożywocia",
     "ulamek": "1", "podstawa": "§ 5 i § 3", "pcc": "2", "sad": ["wpis_wlasnosci", "wpis_ograniczonego_prawa"],
     "dokumenty": _DOK_NIERUCHOMOSC + _DOK_GRUNT},
    {"id": "zamiana", "grupa": "Inne umowy", "nazwa": "Umowa zamiany (wartość: droższy z zamienianych przedmiotów)",
     "ulamek": "1", "podstawa": "§ 5, § 3 i § 2 ust. 3 pkt 1", "pcc": "2", "sad": ["wpis_wlasnosci"],
     "dokumenty": _DOK_NIERUCHOMOSC + _DOK_GRUNT},
    {"id": "dzial_spadku", "grupa": "Inne umowy", "nazwa": "Dział spadku lub zniesienie współwłasności (wartość: cały dzielony majątek)",
     "ulamek": "1", "podstawa": "§ 5, § 3 i § 2 ust. 3 pkt 2", "pcc": "0", "sad": ["wpis_wlasnosci_spadek"],
     "dokumenty": _DOK_NIERUCHOMOSC},
    {"id": "sluzebnosc", "grupa": "Inne umowy", "nazwa": "Ustanowienie służebności lub użytkowania (wartość prawa)",
     "ulamek": "1", "podstawa": "§ 5 i § 3", "pcc": "1", "sad": ["wpis_ograniczonego_prawa"],
     "dokumenty": ["dowody", "numer_kw", "wypis_z_wyrysem"]},
    {"id": "hipoteka_kredyt", "grupa": "Hipoteka", "nazwa": "Ustanowienie hipoteki zabezpieczającej kredyt bankowy mieszkaniowy albo na działalność gospodarczą",
     "ulamek": "1/4", "podstawa": "§ 7 ust. 1 pkt 1", "pcc": "0", "sad": ["wpis_hipoteki"], "pcc_hipoteka": True,
     "dokumenty": ["dowody", "numer_kw", "umowa_kredytu"]},
    {"id": "hipoteka_inna", "grupa": "Hipoteka", "nazwa": "Ustanowienie innej hipoteki",
     "ulamek": "1/2", "podstawa": "§ 6 pkt 11", "pcc": "0", "sad": ["wpis_hipoteki"], "pcc_hipoteka": True,
     "dokumenty": ["dowody", "numer_kw"]},
    {"id": "umowa_spolki", "grupa": "Spółki", "nazwa": "Umowa spółki albo podwyższenie kapitału (wartość: wkłady lub kwota podwyższenia)",
     "ulamek": "1", "podstawa": "§ 5, § 3 i § 9 ust. 2", "pcc": "0.5", "sad": [],
     "dokumenty": ["dowody"]},
    {"id": "przystapienie_spzoo", "grupa": "Spółki", "nazwa": "Oświadczenie o przystąpieniu do spółki z o.o. lub objęciu udziałów",
     "ulamek": "1/10", "podstawa": "§ 7 ust. 2", "pcc": "0", "sad": [],
     "dokumenty": ["dowody"]},
    {"id": "najem_dzierzawa", "grupa": "Inne umowy", "nazwa": "Umowa najmu lub dzierżawy (wartość: czynsz za czas umowy, przy umowie bezterminowej za 10 lat)",
     "ulamek": "1", "podstawa": "§ 5, § 3 i § 2 ust. 3 pkt 7", "pcc": "0", "sad": [],
     "dokumenty": ["dowody", "numer_kw"]},
    {"id": "projekt_aktu", "grupa": "Inne", "nazwa": "Projekt aktu notarialnego obejmującego umowę albo potwierdzenie oświadczenia woli z innego aktu",
     "ulamek": "1/4", "podstawa": "§ 7 ust. 1", "pcc": "0", "sad": [],
     "dokumenty": ["dowody"]},
    {"id": "poswiadczenie_podpisu_z_suma", "grupa": "Poświadczenia", "nazwa": "Poświadczenie podpisu na dokumencie z oznaczoną sumą pieniężną",
     "ulamek": "1/10", "podstawa": "§ 13 pkt 1 lit. a", "pcc": "0", "sad": [], "limit": "podpis_z_suma_limit",
     "bez_wypisow": True, "dokumenty": ["dowody"]},
    {"id": "inna_z_wartoscia", "grupa": "Inne", "nazwa": "Inna czynność, której wartość da się określić (pełna stawka)",
     "ulamek": "1", "podstawa": "§ 5 i § 3", "pcc": "0", "sad": [],
     "dokumenty": ["dowody"]},
]
RODZAJE_WG_ID = {r["id"]: r for r in RODZAJE}

# ---------------------------------------------------------------- czynnosci stale

def _st(ident, grupa, nazwa, podstawa, stara, nowa, **reszta):
    wpis = {"id": ident, "grupa": grupa, "nazwa": nazwa, "podstawa": podstawa,
            "kwoty": {"2004": Decimal(str(stara)), "2026": Decimal(str(nowa))}}
    wpis.update(reszta)
    return wpis


OPCJE = {
    "wybor_prawa": {"nazwa": "Wybór prawa (czynność niewymieniona, § 16)", "kwoty": {"2004": Decimal("200"), "2026": Decimal("400")}},
    "protokol": {"nazwa": "Protokół (§ 10 pkt 3)", "kwoty": {"2004": Decimal("200"), "2026": Decimal("400")}},
    "crwan": {"nazwa": "Rejestracja w CRWAN (czynność niewymieniona, § 16)", "kwoty": {"2004": Decimal("200"), "2026": Decimal("400")}},
}

CZYNNOSCI_STALE = [
    # spoldzielnie, lokatorzy
    {"id": "przeniesienie_spoldzielcze", "grupa": "Spółdzielnie mieszkaniowe",
     "nazwa": "Przeniesienie własności lokalu ze spółdzielczego własnościowego prawa (art. 17¹⁴ ust. 3 u.s.m.)",
     "podstawa": "ustawa o spółdzielniach mieszkaniowych", "ulamek_placy": "1/4",
     "wniosek_kw": True, "hipoteka": True, "sad": ["zalozenie_kw", "wpis_wlasnosci"],
     "dokumenty": ["dowody", "spoldzielnia_prawo", "spoldzielnia_zaleglosci", "zameldowanie"]},
    {"id": "najem_okazjonalny", "grupa": "Najem okazjonalny",
     "nazwa": "Oświadczenie o poddaniu się egzekucji przy najmie okazjonalnym (art. 19a ust. 7 u.o.p.l.)",
     "podstawa": "ustawa o ochronie praw lokatorów", "ulamek_placy": "1/10", "dokumenty": ["dowody"]},
    # umowy
    _st("umowa_majatkowa", "Umowy", "Umowa majątkowa małżeńska (intercyza)", "§ 8 pkt 2", 400, 400, dokumenty=["dowody"]),
    _st("zbycie_krus", "Umowy", "Zbycie nieruchomości ze świadczeniami z KRUS lub rentą strukturalną", "§ 8 pkt 1", 600, 600,
        wniosek_kw=True, sad=["wpis_wlasnosci"], dokumenty=_DOK_NIERUCHOMOSC + _DOK_GRUNT),
    _st("zrzeczenie_wlasnosci", "Umowy", "Zrzeczenie się własności nieruchomości lub użytkowania wieczystego", "§ 8 pkt 7", 80, 80,
        wniosek_kw=True, sad=["wpis_wlasnosci"], dokumenty=_DOK_NIERUCHOMOSC),
    _st("zwolnienie_od_obciazen", "Umowy", "Zwolnienie nieruchomości od obciążeń lub zrzeczenie się prawa (wartość nieokreślona)", "§ 8 pkt 6", 60, 200,
        wniosek_kw=True, sad=["wykreslenie_hipoteki"], dokumenty=["dowody", "numer_kw"]),
    # testamenty
    _st("testament", "Testamenty", "Testament", "§ 8 pkt 3", 50, 200, opcje=["wybor_prawa"], dokumenty=["dowody"]),
    _st("testament_z_zapisem", "Testamenty", "Testament z zapisem zwykłym, poleceniem lub wydziedziczeniem", "§ 8 pkt 4", 150, 300,
        opcje=["wybor_prawa"], dokumenty=["dowody"]),
    _st("testament_windykacyjny", "Testamenty", "Testament z zapisem windykacyjnym", "§ 8 pkt 4a", 200, 400,
        opcje=["wybor_prawa"], dokumenty=["dowody", "numer_kw"]),
    _st("odwolanie_testamentu", "Testamenty", "Odwołanie testamentu", "§ 8 pkt 5", 30, 50, dokumenty=["dowody"]),
    # pelnomocnictwa i oswiadczenia
    _st("pelnomocnictwo_jedna", "Pełnomocnictwa i oświadczenia", "Pełnomocnictwo do jednej czynności", "§ 8 pkt 8", 30, 100, dokumenty=["dowody"]),
    _st("pelnomocnictwo_wiele", "Pełnomocnictwa i oświadczenia", "Pełnomocnictwo do więcej niż jednej czynności", "§ 8 pkt 8", 100, 200, dokumenty=["dowody"]),
    _st("oswiadczenie_spadek", "Pełnomocnictwa i oświadczenia", "Oświadczenie o przyjęciu lub odrzuceniu spadku", "§ 8 pkt 9", 50, 100,
        opcje=["protokol"], dokumenty=["dowody", "akt_zgonu"]),
    # dziedziczenie
    _st("apd", "Dziedziczenie", "Akt poświadczenia dziedziczenia", "§ 10a ust. 1", 50, 200, dokumenty=_DOK_SPADEK),
    _st("apd_windykacyjny", "Dziedziczenie", "Akt poświadczenia dziedziczenia z zapisem windykacyjnym", "§ 10a ust. 2", 100, 300, dokumenty=_DOK_SPADEK),
    _st("protokol_dziedziczenia", "Dziedziczenie", "Protokół dziedziczenia", "§ 10a ust. 3", 100, 200, dokumenty=_DOK_SPADEK),
    _st("projekt_protokolu_dziedziczenia", "Dziedziczenie", "Projekt protokołu dziedziczenia", "§ 10a ust. 5", 100, 200, dokumenty=_DOK_SPADEK),
    _st("zgoda_na_protokol", "Dziedziczenie", "Protokół zgody na spisanie protokołu dziedziczenia według projektu", "§ 10a ust. 6", 50, 100, dokumenty=["dowody"]),
    _st("eps", "Dziedziczenie", "Europejskie poświadczenie spadkowe", "§ 10a ust. 4", 400, 600, dokumenty=_DOK_SPADEK),
    _st("otwarcie_testamentu", "Dziedziczenie", "Protokół otwarcia i ogłoszenia testamentu", "§ 10a ust. 7", 50, 100, dokumenty=["dowody", "akt_zgonu", "testament_dokument"]),
    _st("zaswiadczenie_wykonawca", "Dziedziczenie", "Zaświadczenie o powołaniu wykonawcy testamentu", "§ 10a ust. 8", 30, 50, dokumenty=["dowody"]),
    # protokoly
    _st("protokol_spzoo", "Protokoły", "Protokół zgromadzenia wspólników sp. z o.o. lub walnego zgromadzenia spółdzielni", "§ 9 ust. 1 pkt 1", 750, 900, opcje=["crwan"]),
    _st("protokol_wza", "Protokoły", "Protokół walnego zgromadzenia akcjonariuszy", "§ 9 ust. 1 pkt 2", 1100, 1300, opcje=["crwan"]),
    _st("protokol_inna_spolka", "Protokoły", "Protokół zgromadzenia wspólników innej spółki, posiedzenia zarządu, rady nadzorczej lub komisji rewizyjnej", "§ 9 ust. 1 pkt 3", 500, 500, opcje=["crwan"]),
    _st("protokol_wspolnota", "Protokoły", "Protokół zebrania wspólnoty mieszkaniowej", "§ 9 ust. 1 pkt 4", 300, 500),
    _st("protokol_tfi", "Protokoły", "Protokół z oświadczeniem TFI o zmianie statutu funduszu", "§ 9 ust. 1 pkt 5", 1000, 1000),
    _st("protokol_licytacja_niedoszla", "Protokoły", "Protokół niedojścia do skutku licytacji, przetargu lub losowania", "§ 10 pkt 1", 100, 200),
    _st("protokol_przechowanie", "Protokoły", "Protokół przyjęcia dokumentu na przechowanie", "§ 10 pkt 2", 50, 200),
    _st("przechowanie_miesiac", "Protokoły", "Przechowanie dokumentu, za każdy rozpoczęty miesiąc", "§ 10 pkt 2", 20, 50, bez_wypisow=True),
    _st("protokol_inny", "Protokoły", "Inny protokół", "§ 10 pkt 3", 200, 400),
    # zarzad sukcesyjny
    _st("zarzadca_akt", "Zarząd sukcesyjny", "Akt powołania lub odwołania zarządcy sukcesyjnego", "§ 10b ust. 1", 50, 100, dokumenty=["dowody"]),
    _st("zarzadca_zgoda", "Zarząd sukcesyjny", "Oświadczenie o zgodzie na powołanie lub odwołanie zarządcy, zgoda zarządcy", "§ 10b ust. 2", 50, 100, dokumenty=["dowody"]),
    _st("zarzadca_protokol", "Zarząd sukcesyjny", "Protokół powołania lub odwołania zarządcy sukcesyjnego", "§ 10b ust. 3", 100, 200, dokumenty=["dowody"]),
    _st("zarzadca_rezygnacja", "Zarząd sukcesyjny", "Protokół rezygnacji zarządcy sukcesyjnego", "§ 10b ust. 4", 50, 100, dokumenty=["dowody"]),
    # poswiadczenia
    _st("poswiadczenie_podpisu", "Poświadczenia", "Poświadczenie podpisu na pełnomocnictwie lub innym dokumencie", "§ 13 pkt 1 lit. b", 20, 60, bez_wypisow=True, dokumenty=["dowody"]),
    {"id": "poswiadczenie_odpisu", "grupa": "Poświadczenia", "nazwa": "Poświadczenie zgodności odpisu z okazanym dokumentem (od strony)",
     "podstawa": "§ 13 pkt 2", "od_stron": True, "bez_wypisow": True, "dokumenty": ["dowody"]},
    {"id": "poswiadczenie_daty", "grupa": "Poświadczenia", "nazwa": "Poświadczenie czasu okazania dokumentu (od strony)",
     "podstawa": "§ 13 pkt 3", "od_stron": True, "bez_wypisow": True, "dokumenty": ["dowody"]},
    _st("poswiadczenie_zycia_zus", "Poświadczenia", "Poświadczenie pozostawania przy życiu dla świadczeń z ubezpieczenia społecznego", "§ 13 pkt 4 lit. a", 5, 5, bez_wypisow=True, dokumenty=["dowody"]),
    _st("poswiadczenie_zycia_inne", "Poświadczenia", "Poświadczenie pozostawania przy życiu w innym celu", "§ 13 pkt 4 lit. b", 30, 30, bez_wypisow=True, dokumenty=["dowody"]),
    _st("poswiadczenie_miejsca", "Poświadczenia", "Poświadczenie pozostawania osoby w określonym miejscu", "§ 13 pkt 5", 30, 30, bez_wypisow=True, dokumenty=["dowody"]),
    # rejestr akcjonariuszy PSA
    _st("psa_rejestr_rok", "Rejestr akcjonariuszy PSA", "Prowadzenie rejestru akcjonariuszy, za każdy rozpoczęty rok", "§ 15b ust. 1", 1200, 1200, bez_wypisow=True),
    _st("psa_wpis", "Rejestr akcjonariuszy PSA", "Wpis w rejestrze akcjonariuszy", "§ 15b ust. 2", 100, 100, bez_wypisow=True),
    _st("psa_informacja", "Rejestr akcjonariuszy PSA", "Informacja z rejestru akcjonariuszy", "§ 15b ust. 3", 50, 50, bez_wypisow=True),
    # pozostale
    _st("wniosek_kw", "Pozostałe", "Złożenie wniosku o wpis w księdze wieczystej", "§ 15c (do 4.11.2026 § 16)", 200, 300, bez_wypisow=True),
    _st("czynnosc_niewymieniona", "Pozostałe", "Czynność niewymieniona w rozporządzeniu", "§ 16", 200, 400),
    _st("poza_kancelaria_dzien", "Pozostałe", "Czynność poza kancelarią w porze dziennej, za każdą godzinę", "§ 17 ust. 1 pkt 1", 50, 100, bez_wypisow=True),
    _st("poza_kancelaria_noc", "Pozostałe", "Czynność poza kancelarią w nocy lub w dzień wolny, za każdą godzinę", "§ 17 ust. 1 pkt 2", 100, 200, bez_wypisow=True),
]
STALE_WG_ID = {c["id"]: c for c in CZYNNOSCI_STALE}

# Domyslne wypisy (z C.A.R.): akt z wartoscia 6 x 6 stron, czynnosc stala 1 x 2.
DOMYSLNE_WYPISY = {"wartosc": (6, 6), "stala": (1, 2)}

# ---------------------------------------------------------------- liczenie

def kwota(x) -> Decimal:
    """Liczba, napis ('450 000,50') albo Decimal -> Decimal; smieci i ujemne = 0."""
    if x is None or x is False or x is True:
        return Decimal("0")
    if isinstance(x, Decimal):
        wynik = x
    else:
        try:
            wynik = Decimal(str(x).replace(" ", "").replace(" ", "").replace("zł", "").replace(",", "."))
        except Exception:
            return Decimal("0")
    if not wynik.is_finite() or wynik < 0:
        return Decimal("0")
    return wynik


def grosze(x) -> Decimal:
    return kwota(x).quantize(GROSZ, rounding=ROUND_HALF_UP)


def brutto(netto) -> Decimal:
    return grosze(kwota(netto) * (1 + VAT))


def tabela(dzien: date | None = None) -> dict:
    dzien = dzien or date.today()
    return TABELE["2026"] if dzien >= ZMIANA_2026 else TABELE["2004"]


def stawka_podstawowa(wartosc, dzien: date | None = None, grupa1: bool = False) -> tuple[Decimal, bool]:
    """Maksymalna stawka z § 3 (netto) i czy zadzialal limit (10 000/25 000 zl).

    Limit dla I grupy podatkowej (malzonek, zstepni, wstepni, rodzenstwo,
    pasierb, ojczym, macocha, ziec, synowa, tesciowie) jest nizszy.
    """
    w = kwota(wartosc)
    if w <= 0:
        return Decimal("0"), False
    t = tabela(dzien)
    stawka = Decimal("0")
    for gorna, baza, ponad, procent in t["progi"]:
        if gorna is None or w <= gorna:
            stawka = Decimal(baza) + (w - Decimal(ponad)) * Decimal(procent)
            break
    limit = t["limit_grupa1"] if grupa1 else t["limit"]
    if stawka > limit:
        return limit, True
    return grosze(stawka), False


def koszt_wypisu(strony: int, dzien: date | None = None) -> Decimal:
    """Netto za jeden wypis; progi 12/10/8 zl licza sie dla kazdego wypisu osobno."""
    strony = max(0, int(strony or 0))
    koszt = Decimal("0")
    poprzednia = 0
    for gorna, cena in tabela(dzien)["wypis"]:
        n = max(0, min(strony, gorna if gorna is not None else strony) - poprzednia)
        koszt += n * cena
        if gorna is None or strony <= gorna:
            break
        poprzednia = gorna
    return koszt


def placa_minimalna(dzien: date | None = None) -> Decimal:
    dzien = dzien or date.today()
    return PLACA_MINIMALNA.get(dzien.year, PLACA_MINIMALNA[max(PLACA_MINIMALNA)])


def _data(parametry: dict) -> date:
    tekst = str(parametry.get("data") or "")
    try:
        return date.fromisoformat(tekst[:10])
    except ValueError:
        return date.today()


def _liczba(x, domyslna: int, maks: int = 1000) -> int:
    try:
        n = int(Decimal(str(x)))
    except Exception:
        return domyslna
    return max(0, min(n, maks))


class Kalkulacja:
    """Zbiera pozycje kosztorysu i sumuje je."""

    def __init__(self, dzien: date):
        self.dzien = dzien
        self.tabela = tabela(dzien)
        self.pozycje: list[dict] = []
        self.uwagi: list[str] = []
        self.dokumenty: set[str] = set()

    def dodaj(self, rodzaj: str, etykieta: str, netto, podstawa: str = "", z_vat: bool = True, uwaga: str = "") -> dict:
        """rodzaj: taksa | wypisy | pcc | sad | inne. Z VAT tylko wynagrodzenie notariusza."""
        netto = grosze(netto)
        kwota_brutto = brutto(netto) if z_vat else netto
        pozycja = {"rodzaj": rodzaj, "etykieta": etykieta, "netto": netto,
                   "vat": kwota_brutto - netto, "brutto": kwota_brutto, "podstawa": podstawa}
        if uwaga:
            pozycja["uwaga"] = uwaga
        self.pozycje.append(pozycja)
        return pozycja

    def wynik(self) -> dict:
        sumy = {k: Decimal("0") for k in ("taksa_netto", "taksa_brutto", "vat", "wypisy", "pcc", "sad", "inne", "razem")}
        for p in self.pozycje:
            sumy["razem"] += p["brutto"]
            sumy["vat"] += p["vat"]
            if p["rodzaj"] == "taksa":
                sumy["taksa_netto"] += p["netto"]
                sumy["taksa_brutto"] += p["brutto"]
            elif p["rodzaj"] in sumy:
                sumy[p["rodzaj"]] += p["brutto"]
        grupy: dict[str, list[str]] = {}
        for klucz in DOKUMENTY:
            if klucz in self.dokumenty:
                grupa, nazwa = DOKUMENTY[klucz]
                grupy.setdefault(grupa, []).append(nazwa)
        kolejnosc = {"taksa": 0, "wypisy": 1, "pcc": 2, "sad": 3, "inne": 4}
        pozycje = sorted(self.pozycje, key=lambda p: kolejnosc.get(p["rodzaj"], 9))
        return {
            "tabela": {k: self.tabela[k] for k in ("id", "etykieta", "podstawa")},
            "data": self.dzien.isoformat(),
            "pozycje": [_na_json(p) for p in pozycje],
            "sumy": {k: _liczba_json(v) for k, v in sumy.items()},
            "razem": _liczba_json(sumy["razem"]),
            "uwagi": self.uwagi,
            "dokumenty": [{"grupa": g, "pozycje": d} for g, d in grupy.items()],
        }


def _liczba_json(x: Decimal) -> float:
    return float(grosze(x))


def _na_json(pozycja: dict) -> dict:
    return {k: (_liczba_json(v) if isinstance(v, Decimal) else v) for k, v in pozycja.items()}


def oblicz(parametry: dict) -> dict:
    """Kosztorys czynnosci. Parametry (wszystkie opcjonalne poza czynnosciami):

    data            ISO; decyduje o tabeli stawek (domyslnie dzis)
    czynnosci       [{rodzaj: id z RODZAJE, wartosc, opis?, ulamek?, rabat_netto?}]
    stale           [{id: id z CZYNNOSCI_STALE, ilosc?, opcje?: [id], wypisy?, strony?,
                      dokumentow?, stron_dokumentu?, wniosek_kw?, hipoteka?: kwota}]
    grupa1          czynnosc miedzy osobami z I grupy podatkowej (nizszy limit)
    pcc             None = wg rodzaju czynnosci; True/False wymusza
    hipoteka        None | {kwota?, kredyt_mieszkaniowy?: True} - hipoteka w tym samym akcie
    wypisy, strony  liczba wypisow aktu i stron jednego wypisu
    wniosek_kw      None = gdy czynnosc tego wymaga; True/False wymusza
    oplaty_sadowe   None = wg rodzaju czynnosci; lista kluczy OPLATY_SADOWE wymusza
    oplata_rejestracyjna  None = przy wpisie do KW; True/False wymusza
    """
    dzien = _data(parametry)
    k = Kalkulacja(dzien)
    t = k.tabela
    grupa1 = bool(parametry.get("grupa1"))
    czynnosci = [c for c in (parametry.get("czynnosci") or []) if isinstance(c, dict)][:6]
    stale = [s for s in (parametry.get("stale") or []) if isinstance(s, dict)][:12]
    hipoteka = parametry.get("hipoteka")
    if not isinstance(hipoteka, dict):
        hipoteka = {"kwota": kwota(hipoteka)} if hipoteka not in (None, False, "", 0) else None

    wartosc_razem = Decimal("0")
    potrzebny_wniosek = False
    oplaty_domyslne: list[str] = []
    pcc_domyslne = Decimal("0")
    jest_wypis = False

    # --- czynnosci z wartoscia (§ 3 z ulamkami z § 6 i § 7)
    for c in czynnosci:
        rodzaj = RODZAJE_WG_ID.get(str(c.get("rodzaj") or ""), RODZAJE_WG_ID["inna_z_wartoscia"])
        wartosc = kwota(c.get("wartosc"))
        if wartosc <= 0:
            continue
        ulamek = str(c.get("ulamek") or rodzaj["ulamek"])
        mnoznik = ULAMKI.get(ulamek, ULAMKI[rodzaj["ulamek"]])
        podstawa, limit = stawka_podstawowa(wartosc, dzien, grupa1)
        netto = grosze(podstawa * mnoznik)
        uwaga = ""
        if rodzaj.get("limit"):
            szczegolny = t[rodzaj["limit"]]
            if netto > szczegolny:
                netto, uwaga = szczegolny, f"Zastosowano limit {zl(szczegolny)} netto ({rodzaj['podstawa']})."
        elif limit:
            uwaga = (f"Zastosowano limit taksy {zl(t['limit_grupa1'] if grupa1 else t['limit'])} netto"
                     + (" (I grupa podatkowa)." if grupa1 else "."))
        rabat = kwota(c.get("rabat_netto"))
        if rabat > 0 and rabat < netto:
            uwaga = (uwaga + " " if uwaga else "") + f"Taksa po rabacie zamiast stawki maksymalnej {zl(netto)} netto."
            netto = grosze(rabat)
        opis = " ".join(str(c.get("opis") or rodzaj["nazwa"]).split())[:120]
        opis = opis[:1].lower() + opis[1:]
        etykieta = f"taksa notarialna: {opis}" + (f" ({ulamek} stawki)" if ulamek != "1" else "")
        k.dodaj("taksa", etykieta, netto, rodzaj["podstawa"], uwaga=uwaga)
        if uwaga:
            k.uwagi.append(uwaga)
        wartosc_razem += wartosc
        pcc_domyslne += grosze(wartosc * Decimal(rodzaj["pcc"]) / 100)
        if rodzaj["sad"]:
            potrzebny_wniosek = True
            oplaty_domyslne += rodzaj["sad"]
        if rodzaj.get("pcc_hipoteka") and hipoteka is None:
            hipoteka = {"kwota": Decimal("0"), "bez_taksy": True}
        k.dokumenty.update(rodzaj.get("dokumenty", []))
        if not rodzaj.get("bez_wypisow"):
            jest_wypis = True

    # --- hipoteka w tym samym akcie (np. zakup na kredyt): 1/4 albo 1/2 stawki od kwoty hipoteki
    if hipoteka is not None:
        kwota_hipoteki = kwota(hipoteka.get("kwota"))
        if kwota_hipoteki > 0 and not hipoteka.get("bez_taksy"):
            ulamek = "1/4" if hipoteka.get("kredyt_mieszkaniowy", True) else "1/2"
            podstawa, limit = stawka_podstawowa(kwota_hipoteki, dzien, grupa1)
            k.dodaj("taksa", f"taksa notarialna: ustanowienie hipoteki {zl(kwota_hipoteki)} ({ulamek} stawki)",
                    podstawa * ULAMKI[ulamek], "§ 7 ust. 1 pkt 1" if ulamek == "1/4" else "§ 6 pkt 11")
            k.dokumenty.add("umowa_kredytu")
        k.dodaj("pcc", "PCC od ustanowienia hipoteki", PCC_HIPOTEKA, "ustawa o PCC, art. 7 ust. 1 pkt 7 lit. b", z_vat=False)
        oplaty_domyslne.append("wpis_hipoteki")
        potrzebny_wniosek = True

    # --- czynnosci ze stala stawka (§ 8-§ 17 i ustawy szczegolne)
    for s in stale:
        czynnosc = STALE_WG_ID.get(str(s.get("id") or ""))
        if not czynnosc:
            continue
        ilosc = _liczba(s.get("ilosc"), 1, 120) or 1
        if czynnosc.get("od_stron"):
            dokumentow = _liczba(s.get("dokumentow"), 1, 500) or 1
            stron = _liczba(s.get("stron_dokumentu"), 1, 2000) or 1
            netto = koszt_wypisu(stron, dzien) * dokumentow
            opis = f"{czynnosc['nazwa']} ({dokumentow} × {stron} str.)" if dokumentow > 1 else f"{czynnosc['nazwa']} ({stron} str.)"
        elif czynnosc.get("ulamek_placy"):
            licznik, mianownik = czynnosc["ulamek_placy"].split("/")
            netto = grosze(placa_minimalna(dzien) * Decimal(licznik) / Decimal(mianownik)) * ilosc
            opis = f"{czynnosc['nazwa']} ({czynnosc['ulamek_placy']} płacy minimalnej)" + (f" ×{ilosc}" if ilosc > 1 else "")
        else:
            netto = czynnosc["kwoty"][t["id"]] * ilosc
            opis = czynnosc["nazwa"] + (f" ×{ilosc}" if ilosc > 1 else "")
        k.dodaj("taksa", f"taksa notarialna: {opis}", netto, czynnosc["podstawa"])
        for opcja in s.get("opcje") or []:
            if opcja in (czynnosc.get("opcje") or []):
                k.dodaj("taksa", f"taksa notarialna: {OPCJE[opcja]['nazwa']}", OPCJE[opcja]["kwoty"][t["id"]], "§ 16")
        if not czynnosc.get("bez_wypisow"):
            w, st = DOMYSLNE_WYPISY["stala"]
            wypisy_s = _liczba(s.get("wypisy"), w, 100)
            strony_s = _liczba(s.get("strony"), st, 500)
            if wypisy_s and strony_s:
                k.dodaj("wypisy", f"wypisy ({wypisy_s} × {strony_s} str.)", koszt_wypisu(strony_s, dzien) * wypisy_s, "§ 12")
        if czynnosc.get("wniosek_kw") and s.get("wniosek_kw", True):
            potrzebny_wniosek = True
            oplaty_domyslne += czynnosc.get("sad", [])
        kwota_hip = kwota(s.get("hipoteka"))
        if czynnosc.get("hipoteka") and kwota_hip > 0:
            podstawa, _ = stawka_podstawowa(kwota_hip, dzien, grupa1)
            k.dodaj("taksa", f"taksa notarialna: ustanowienie hipoteki {zl(kwota_hip)} (1/4 stawki)", podstawa * ULAMKI["1/4"], "§ 7 ust. 1 pkt 1")
            k.dodaj("pcc", "PCC od ustanowienia hipoteki", PCC_HIPOTEKA, "ustawa o PCC", z_vat=False)
            oplaty_domyslne.append("wpis_hipoteki")
            potrzebny_wniosek = True
        k.dokumenty.update(czynnosc.get("dokumenty", []))

    # --- wypisy aktu z wartoscia
    if jest_wypis:
        w, st = DOMYSLNE_WYPISY["wartosc"]
        wypisy = _liczba(parametry.get("wypisy"), w, 100)
        strony = _liczba(parametry.get("strony"), st, 500)
        if wypisy and strony:
            k.dodaj("wypisy", f"wypisy aktu ({wypisy} × {strony} str.)", koszt_wypisu(strony, dzien) * wypisy, "§ 12")

    # --- PCC od wartosci
    pcc = parametry.get("pcc")
    if pcc is None:
        pcc = pcc_domyslne > 0
    if pcc and wartosc_razem > 0:
        procent = kwota(parametry.get("pcc_procent")) or (
            max((Decimal(RODZAJE_WG_ID.get(str(c.get("rodzaj") or ""), RODZAJE_WG_ID["inna_z_wartoscia"])["pcc"]) for c in czynnosci), default=PCC_PROCENT) or PCC_PROCENT)
        k.dodaj("pcc", f"podatek od czynności cywilnoprawnych (PCC {str(procent).replace('.', ',')} %)",
                wartosc_razem * procent / 100, "ustawa o PCC", z_vat=False)
    elif wartosc_razem > 0 and pcc_domyslne > 0:
        k.uwagi.append("Nie doliczono PCC. Podatek nie wystąpi, gdy sprzedaż jest opodatkowana VAT "
                       "(np. zakup od dewelopera) albo gdy nabywca korzysta ze zwolnienia dla pierwszego mieszkania "
                       "(art. 9 pkt 17 ustawy o PCC).")

    # --- oplaty sadowe
    oplaty = parametry.get("oplaty_sadowe")
    if isinstance(oplaty, dict):            # model potrafi oddac {"wpis_wlasnosci": 1}
        oplaty = [k for k, v in oplaty.items() if v]
    elif isinstance(oplaty, str):
        oplaty = [oplaty]
    if not isinstance(oplaty, list):
        oplaty = oplaty_domyslne
    widziane: list[str] = []
    for klucz in oplaty:
        if klucz in OPLATY_SADOWE and klucz not in widziane:
            widziane.append(klucz)
            nazwa, kwota_oplaty = OPLATY_SADOWE[klucz]
            k.dodaj("sad", f"opłata sądowa: {nazwa}", kwota_oplaty, "u.k.s.c.", z_vat=False)
    dodatkowa = kwota(parametry.get("oplata_sadowa_inna"))
    if dodatkowa > 0:
        k.dodaj("sad", "opłata sądowa (inna)", dodatkowa, "u.k.s.c.", z_vat=False)

    # --- wniosek o wpis w ksiedze wieczystej i oplata rejestracyjna
    wniosek = parametry.get("wniosek_kw")
    if wniosek is None:
        wniosek = potrzebny_wniosek or bool(widziane)
    if wniosek:
        k.dodaj("taksa", "wniosek o wpis w księdze wieczystej", t["wniosek_kw"], "§ 15c" if t["id"] == "2026" else "§ 16")
    rejestracyjna = parametry.get("oplata_rejestracyjna")
    if rejestracyjna is None:
        rejestracyjna = bool(wniosek)
    if rejestracyjna:
        k.dodaj("inne", "opłata rejestracyjna", OPLATA_REJESTRACYJNA, "", z_vat=False)

    if not k.pozycje:
        k.uwagi.append("Brak czynności do policzenia. Podaj rodzaj czynności i wartość.")
    wynik = k.wynik()
    wynik["wartosc"] = _liczba_json(wartosc_razem)
    wynik["grupa1"] = grupa1
    wynik["tekst"] = tekst_kalkulacji(wynik)
    return wynik


# ---------------------------------------------------------------- prezentacja

def zl(x) -> str:
    """1234.5 -> '1 234,50 zł' (twarde spacje jak w C.A.R.)."""
    calkowite, grosze_ = f"{grosze(x):.2f}".split(".")
    with_sep = ""
    for i, cyfra in enumerate(reversed(calkowite)):
        if i and i % 3 == 0:
            with_sep = " " + with_sep
        with_sep = cyfra + with_sep
    return f"{with_sep},{grosze_} zł"


ZASTRZEZENIE = ("Kwoty są szacunkowe i liczone według maksymalnych stawek z rozporządzenia; "
                "notariusz może zastosować niższą taksę, a ostateczny koszt zależy od treści aktu. "
                "Wyliczenie nie zastępuje informacji z kancelarii.")


def tekst_kalkulacji(wynik: dict, podpis: str = "") -> str:
    """Gotowa wiadomosc dla klienta - do skopiowania do SMS-a albo e-maila (wzor z C.A.R.)."""
    if not wynik.get("pozycje"):
        return ""
    naglowek = "Szacunkowe koszty brutto czynności notarialnej"
    if wynik.get("wartosc"):
        naglowek += f" (wartość: {zl(wynik['wartosc'])})"
    linie = [naglowek + ":", ""]
    for p in wynik["pozycje"]:
        linie.append(f"{p['etykieta']}: {zl(p['brutto'])}")
    linie += ["", f"RAZEM: {zl(wynik['razem'])}"]
    if wynik.get("uwagi"):
        linie += [""] + [u for u in wynik["uwagi"]]
    linie += ["", f"{wynik['tabela']['etykieta']} {ZASTRZEZENIE}"]
    if podpis.strip():
        linie += ["", podpis.strip()]
    return "\n".join(linie)


def katalog() -> dict:
    """Dane dla formularza na stronie i dla modelu: rodzaje, czynnosci stale, oplaty."""
    t = tabela()
    return {
        "tabela": {k: t[k] for k in ("id", "etykieta", "podstawa")},
        "zmiana": ZMIANA_2026.isoformat(),
        "rodzaje": [{k: r[k] for k in ("id", "grupa", "nazwa", "ulamek", "podstawa")} | {"pcc": r["pcc"]} for r in RODZAJE],
        "stale": [{"id": c["id"], "grupa": c["grupa"], "nazwa": c["nazwa"], "podstawa": c["podstawa"],
                   "kwota": _liczba_json(c["kwoty"][t["id"]]) if "kwoty" in c else None,
                   "od_stron": bool(c.get("od_stron")), "ulamek_placy": c.get("ulamek_placy"),
                   "bez_wypisow": bool(c.get("bez_wypisow")), "opcje": c.get("opcje", []),
                   "wniosek_kw": bool(c.get("wniosek_kw")), "hipoteka": bool(c.get("hipoteka"))}
                  for c in CZYNNOSCI_STALE],
        "opcje": {k: {"nazwa": v["nazwa"], "kwota": _liczba_json(v["kwoty"][t["id"]])} for k, v in OPCJE.items()},
        "oplaty_sadowe": {k: {"nazwa": v[0], "kwota": _liczba_json(v[1])} for k, v in OPLATY_SADOWE.items()},
        "vat": _liczba_json(VAT * 100), "pcc_procent": _liczba_json(PCC_PROCENT),
        "pcc_hipoteka": _liczba_json(PCC_HIPOTEKA), "oplata_rejestracyjna": _liczba_json(OPLATA_REJESTRACYJNA),
        "wypis": [[g, _liczba_json(c)] for g, c in t["wypis"]], "wniosek_kw": _liczba_json(t["wniosek_kw"]),
        "limit": _liczba_json(t["limit"]), "limit_grupa1": _liczba_json(t["limit_grupa1"]),
        "placa_minimalna": _liczba_json(placa_minimalna()),
        "domyslne_wypisy": DOMYSLNE_WYPISY,
    }


def opis_dla_modelu(dzien: date | None = None) -> str:
    """Katalog w formie, ktora model dostaje w promptcie - identyfikatory, ktorych ma uzywac."""
    t = tabela(dzien)
    linie = [f"OBOWIAZUJACA TABELA: {t['etykieta']} ({t['podstawa']}).",
             f"Limit taksy od wartosci: {zl(t['limit'])} netto, miedzy osobami z I grupy podatkowej {zl(t['limit_grupa1'])} netto.",
             "", "RODZAJE CZYNNOSCI Z WARTOSCIA (pole \"rodzaj\"): id | nazwa | czesc stawki | PCC"]
    for r in RODZAJE:
        linie.append(f"- {r['id']} | {r['nazwa']} | {r['ulamek']} stawki ({r['podstawa']}) | PCC {r['pcc']} %")
    linie += ["", "CZYNNOSCI ZE STALA STAWKA (pole \"stale\", id): id | nazwa | stawka netto"]
    for c in CZYNNOSCI_STALE:
        if "kwoty" in c:
            stawka = zl(c["kwoty"][t["id"]])
        elif c.get("od_stron"):
            stawka = "od strony (12/10/8 zl); podaj dokumentow i stron_dokumentu"
        else:
            stawka = f"{c['ulamek_placy']} placy minimalnej ({zl(placa_minimalna(dzien) * ULAMKI.get(c['ulamek_placy'], Decimal('1')))})"
        dodatki = []
        if c.get("opcje"):
            dodatki.append("opcje: " + ", ".join(c["opcje"]))
        if c.get("hipoteka"):
            dodatki.append("mozliwa hipoteka (pole hipoteka: kwota)")
        linie.append(f"- {c['id']} | {c['nazwa']} | {stawka}" + (" | " + "; ".join(dodatki) if dodatki else ""))
    linie += ["", "OPLATY SADOWE (pole \"oplaty_sadowe\", klucze): " + ", ".join(f"{k} ({zl(v[1])})" for k, v in OPLATY_SADOWE.items())]
    return "\n".join(linie)
