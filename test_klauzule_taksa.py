"""Paragrafy podstawy taksy to cytaty z rozporzadzenia, nie paragrafy aktu.

Zgloszenie kancelarii 23.11.2026: kontrola zasad pokazywala "Numeracja
paragrafow: powtorzone § 1..7", "ustepy nie ida po kolei" i "Odeslanie
§10a ust. 3 wskazuje paragraf, ktorego nie ma w akcie" dla czesci z taksa,
a przenumerowanie moglo zmienic cytaty z rozporzadzenia. Dane zmyslone.
"""
import klauzule

AKT = """AKT NOTARIALNY

1. Adam Testowy, syn Jana i Ewy, PESEL <<BRAK: numer PESEL>>,
2. Ewa Testowa, córka Piotra i Anny,
zwani dalej Stawającymi.

§ 1. 1. Stawający oświadczają, że są właścicielami lokalu.
2. Dla lokalu prowadzona jest księga wieczysta.
§ 2. Stawający sprzedają lokal, o którym mowa w § 1 ust. 1.
§ 3. Koszty tego aktu ponoszą Kupujący.

Pobrano:
§ 1 taksę notarialną na podstawie § 3 pkt 4 rozporządzenia Ministra Sprawiedliwości z dnia 28 czerwca 2004 r. w sprawie maksymalnych stawek taksy notarialnej
§ 2 ust. 1 i § 10a ust. 3 tego rozporządzenia - 200 zł,
§ 3 podatek VAT 23% - 46 zł,
1. opłata sądowa - 200 zł,
1. podatek od czynności cywilnoprawnych - 2000 zł.
"""

TAKSA_W_ZDANIU = """§ 1. Sprzedający sprzedaje lokal.
§ 2. Koszty ponosi Kupujący.

Taksa notarialna (tekst jednolity Dz.U. z 2024 r. poz. 1566 ze zm.), z §10a ust. 3 - 200 zł i podatku VAT 23% - 46 zł.
"""


def _kody(tekst):
    return {p["kod"] for p in klauzule.sprawdz_konstrukcje(klauzule.rozbij(tekst))}


def test_paragrafy_taksy_nie_psuja_numeracji_ani_odeslan():
    kody = _kody(AKT)
    assert "numeracja_paragrafow" not in kody
    assert "numeracja_ustepow" not in kody
    assert "odeslania" not in kody


def test_paragrafy_aktu_dalej_liczone():
    rozbior = klauzule.rozbij(AKT)
    assert [p.numer for p in rozbior.paragrafy()] == ["1", "2", "3"]
    assert all(k.taksa for k in rozbior.klauzule if "taks" in k.tekst.lower() and "Koszty" not in k.tekst)


def test_odeslanie_po_nazwie_rozporzadzenia_to_cytat():
    assert "odeslania" not in _kody(TAKSA_W_ZDANIU)
    assert klauzule.odeslania_w_tekscie("(tekst jednolity Dz.U. z 2024 r. poz. 1566 ze zm.), z §10a ust. 3") == []


def test_przenumerowanie_nie_rusza_taksy():
    tekst = AKT.replace("§ 3. Koszty", "§ 5. Koszty")   # luka w numeracji aktu
    nowy, zmiany = klauzule.przenumeruj(tekst)
    assert zmiany == {"5": "3"}
    taksa_przed = tekst[tekst.index("Pobrano:"):]
    assert nowy[nowy.index("Pobrano:"):] == taksa_przed
    assert "§ 3. Koszty" in nowy


def test_cytat_przepisu_na_poczatku_linii_to_nie_paragraf():
    tekst = "§ 1. Stawający oświadcza.\n§ 3 ust. 1 rozporządzenia stosuje się odpowiednio.\n§ 2. Koniec."
    assert [p.numer for p in klauzule.rozbij(tekst).paragrafy()] == ["1", "2"]
    assert "numeracja_paragrafow" not in _kody(tekst)


def test_prawdziwe_bledy_nadal_wykrywane():
    assert "numeracja_paragrafow" in _kody("§ 1. A.\n§ 1. B.\n§ 2. C.")
    assert "odeslania" in _kody("§ 1. Jak w § 7 ust. 2.\n§ 2. Koniec.")
    # paragraf aktu o kosztach (z kropka) to jeszcze akt, nie poczatek taksy
    assert "numeracja_paragrafow" in _kody("§ 1. A.\n§ 2. Taksę notarialną pobrano od Kupującego.\n§ 4. C.")
