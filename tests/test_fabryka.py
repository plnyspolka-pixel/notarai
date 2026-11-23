"""Testy fabryki odcinków: sloty i bufor, bramka scenariusza, plan zleceń, kolejka, karta sprawy."""
import copy
from datetime import datetime

import pytest

from tools.fabryka import karta, plan, publikacja, sloty, walidatory
from tools.fabryka.wspolne import WARSZAWA

W = WARSZAWA


def d(s):
    return datetime.fromisoformat(s)


# ---------------------------------------------------------------- sloty i bufor
def test_sloty_dwa_dziennie_od_rana():
    s = sloty.sloty_od(d("2026-11-24T08:00:00+01:00"), 3)
    assert [x.isoformat() for x in s] == [
        "2026-11-24T09:00:00+01:00", "2026-11-24T16:00:00+01:00", "2026-11-25T09:00:00+01:00"]


def test_slot_dokladnie_o_dziewiatej_przechodzi_na_szesnasta():
    assert sloty.sloty_od(d("2026-11-24T09:00:00+01:00"), 1)[0].hour == 16


def test_zmiana_czasu_na_letni_i_zimowy():
    # 28.03.2027 o 2:00 zmiana na czas letni: 27.03 16:00 jest +01:00, 28.03 09:00 już +02:00.
    wiosna = sloty.sloty_od(d("2027-03-27T10:00:00+01:00"), 2)
    assert [x.utcoffset().total_seconds() / 3600 for x in wiosna] == [1, 2]
    jesien = sloty.sloty_od(d("2026-10-24T17:00:00+02:00"), 2)
    assert jesien[0].isoformat() == "2026-10-25T09:00:00+01:00"
    assert all(x.hour in (9, 16) for x in wiosna + jesien)


def _kol(*wpisy):
    return {"odcinki": [dict(id=i, publish_at=t, status=st, pliki={"wideo": w}) for i, t, st, w in wpisy]}


def test_wolne_sloty_po_ostatnim_zajetym_bez_dziur():
    k = _kol(("s01e01", "2026-11-24T09:00:00+01:00", "gotowy", "https://x/1.mp4"),
             ("s01e02", "2026-11-25T09:00:00+01:00", "gotowy", "https://x/2.mp4"))
    s = sloty.wolne_sloty(k, d("2026-11-24T08:00:00+01:00"), 1)
    assert s[0].isoformat() == "2026-11-25T16:00:00+01:00"


def test_wpis_zastepczy_bez_wideo_nie_zajmuje_slotu_ani_bufora():
    k = _kol(("s01e01", "2026-11-23T16:00:00+01:00", "gotowy", "serial/media/nie-ma.mp4"))
    assert sloty.bufor(k, d("2026-11-23T12:00:00+01:00")) == 0
    assert sloty.wolne_sloty(k, d("2026-11-23T12:00:00+01:00"), 1)[0].hour == 16


def test_bufor_i_wielkosc_paczki():
    k = _kol(*[(f"e{i}", f"2026-11-2{4 + i // 2}T{'09' if i % 2 == 0 else '16'}:00:00+01:00", "gotowy",
                f"https://x/{i}.mp4") for i in range(4)])
    teraz = d("2026-11-24T08:00:00+01:00")
    assert sloty.bufor(k, teraz) == 4
    assert sloty.wielkosc_paczki(4) == 2
    assert sloty.wielkosc_paczki(3) == 4


def test_numeracja_bez_przerwy_miedzy_sezonami():
    assert sloty.nastepne_numery((1, 39), 3) == [(1, 40), (2, 1), (2, 2)]
    assert sloty.nastepne_numery(None, 1) == [(1, 1)]


# ---------------------------------------------------------------- bramka scenariusza
def _u(id, typ, czas, **k):
    return dict(id=id, typ=typ, czas_s=czas, **k)


def _mowa(id, kto, czas, kw="Tego wczoraj nie było.", **k):
    return _u(id, "mowiace", czas, postac=kto, kwestia=kw, kwestia_v3=f"[calm] {kw}", znacznik=None, **k)


def scenariusz_wzorcowy():
    lista = {k: {"ok": True, "jak": "spełnione"} for k in walidatory.LISTA_THRILLERA}
    sc = {
        "id": "s01e09", "sezon": 1, "odcinek": 9, "slot": "09:00", "tytul": "Niedziela bez ksiąg",
        "sprawa_kotwica": "A17", "prowadzi": "helena", "typ_otwarcia": "A",
        "muzyka": {"typ": "brak"}, "pytanie_koncowe": "Czy Helena dobrze zrobiła, że kazała czekać?",
        "lista_kontrolna": lista,
        "sceny": [
            {"id": "sc1", "rola": "zimne_otwarcie", "plan": "s02", "kamera": "K03", "ujecia": [
                _mowa("u1", "helena", 3.0), _mowa("u2", "kuba", 3.0)]},
            {"id": "sc2", "rola": "tytul", "ujecia": [_u("u3", "plansza", 1.5, tekst="Niedziela bez ksiąg")]},
            {"id": "sc3", "rola": "swiat", "plan": "s02", "kamera": "K01", "ujecia": [
                _mowa("u4", "marta", 6.0), _u("u5", "bez_mowy", 3.0), _mowa("u6", "helena", 5.0)]},
            {"id": "sc4", "rola": "zwrot1", "plan": "s02", "kamera": "K02", "ujecia": [
                _u("u7", "dokument", 5.0, dokument={"szablon": "notatka"}), _mowa("u8", "kuba", 6.0, zart=True)]},
            {"id": "sc5", "rola": "praca", "plan": "s02", "kamera": "K02", "ujecia": [
                _u("u9", "ekran", 6.0, ekran={"funkcja": "pobranie treści KW"}), _mowa("u10", "marta", 8.0)]},
            {"id": "sc6", "rola": "szczyt", "plan": "s02", "kamera": "K03", "ujecia": [
                _mowa("u11", "helena", 8.0), _u("u12", "bez_mowy", 3.0)]},
            {"id": "sc7", "rola": "zawieszenie", "plan": "s02", "kamera": "K01", "ujecia": [
                _mowa("u13", "basia", 6.0)]},
            {"id": "sc8", "rola": "plansza_koncowa", "ujecia": [
                _u("u14", "plansza", 4.0, tekst=walidatory.PLANSZA_KONCOWA)]},
        ],
    }
    return sc


def test_wzorcowy_przechodzi():
    sc = scenariusz_wzorcowy()
    assert 60 <= walidatory.dlugosc(sc) <= 90
    assert walidatory.sprawdz(sc) == []


def _z(fn):
    sc = scenariusz_wzorcowy()
    fn(sc)
    return walidatory.sprawdz(sc)


def test_plansza_w_pierwszych_3_s():
    p = _z(lambda sc: sc["sceny"][0]["ujecia"].insert(0, _u("u0", "plansza", 2.0, tekst="logo")))
    assert any("pierwszych 3 s" in x for x in p)


def test_ekran_w_szczycie():
    def f(sc):
        sc["sceny"][5]["ujecia"].insert(0, _u("ux", "ekran", 2.0, ekran={"funkcja": "x"}))
    assert any("oknie szczytu" in x for x in _z(f))


def test_dwa_zarty_i_zart_kosztem_klienta():
    def f(sc):
        sc["sceny"][6]["ujecia"][0]["zart"] = True
        sc["sceny"][2]["ujecia"][0].update(postac="irena", zart=True)
    p = _z(f)
    assert any("jeden żart" in x for x in p) and any("kosztem klienta" in x for x in p)


def test_kwestia_bez_tagu_v3():
    p = _z(lambda sc: sc["sceny"][0]["ujecia"][0].update(kwestia_v3="bez tagu"))
    assert any("tagiem ElevenLabs v3" in x for x in p)


def test_sygnatura_pesel_i_nazwisko_konsultanta():
    def f(sc):
        sc["sceny"][2]["ujecia"][0]["kwestia"] = "Jak w sprawie I ACa 740/16, PESEL 44051401359."
        sc["konsultant"] = {"nazwisko": "Kowalska"}
    p = _z(f)
    assert any("sygnatura" in x for x in p) and any("PESEL" in x for x in p) and any("konsultanta" in x for x in p)


@pytest.mark.parametrize("kotw,oczek", [("P07", "wykluczona"), ("H17", "wykluczona"), ("P01", "od sezonu 2"), ("", "brak kotwicy")])
def test_kotwice(kotw, oczek):
    assert any(oczek in x for x in _z(lambda sc: sc.update(sprawa_kotwica=kotw)))


def test_kotwica_uzyta_w_sezonie_ale_motyw_dozwolony():
    sc = scenariusz_wzorcowy()
    assert any("już użyta" in x for x in walidatory.sprawdz(sc, uzyte_w_sezonie={"A17"}))
    sc["sprawa_kotwica"] = "A17 (motyw)"
    assert not any("już użyta" in x for x in walidatory.sprawdz(sc, uzyte_w_sezonie={"A17"}))


def test_prompt_z_tekstem_i_dlugosc():
    def f(sc):
        sc["sceny"][2]["ujecia"][1]["prompt_ruchu"] = "camera pans over a document with text"
        sc["sceny"][6]["ujecia"][0]["czas_s"] = 30
    p = _z(f)
    assert any("prompt obrazu" in x for x in p) and any("poza zakresem" in x for x in p)


def test_plansza_w_srodku_i_brak_zdania_koncowego():
    def f(sc):
        sc["sceny"][3]["ujecia"].append(_u("uy", "plansza", 1.0, tekst="Tymczasem"))
        sc["sceny"][-1]["ujecia"][0]["tekst"] = "Koniec"
    p = _z(f)
    assert any("w środku" in x for x in p) and any("plansza końcowa" in x for x in p)


def test_smiech_z_tasmy_i_powtorzony_typ_otwarcia():
    sc = scenariusz_wzorcowy()
    sc["muzyka"] = {"typ": "ciepla", "uwagi": "laugh track po żarcie"}
    p = walidatory.sprawdz(sc, poprzedni_typ_otwarcia="A")
    assert any("taśmy" in x for x in p) and any("typ otwarcia" in x for x in p)


def test_lista_thrillera_wymaga_uzasadnienia():
    p = _z(lambda sc: sc["lista_kontrolna"].update(jeden_szczyt={"ok": True, "jak": ""}))
    assert any("jeden_szczyt" in x for x in p)


def test_scenografia_sprawdza_kamery_i_znaczniki():
    sceno = {"s02": {"kamery": [{"nazwa": "K01"}, {"nazwa": "K02"}, {"nazwa": "K03"}],
                     "znaczniki": [{"nazwa": "M_Helena_szczyt"}]}}
    sc = scenariusz_wzorcowy()
    assert walidatory.sprawdz(sc, scenografia=sceno) == []
    sc["sceny"][0]["ujecia"][0]["znacznik"] = "M_nie_ma"
    sc["sceny"][2]["plan"] = "s99"
    p = walidatory.sprawdz(sc, scenografia=sceno)
    assert any("M_nie_ma" in x for x in p) and any("s99" in x for x in p)


# ---------------------------------------------------------------- plan zleceń
def test_glosy_tylko_v3_lub_nowszy():
    sc = scenariusz_wzorcowy()
    assert plan.glosy(sc)["model_id"] == "eleven_v4"
    with pytest.raises(plan.BladPlanu):
        plan.glosy(sc, model="eleven_multilingual_v2")


def test_brak_glosu_postaci_przerywa():
    sc = scenariusz_wzorcowy()
    sc["sceny"][6]["ujecia"][0]["postac"] = "zosia"
    with pytest.raises(plan.BladPlanu, match="zosia"):
        plan.glosy(sc)


def test_gpu_jedna_paczka_mowa_jedno_ziarno_niemy_dwa():
    sc = scenariusz_wzorcowy()
    g = plan.gpu(sc)
    mowiace = [u for s in sc["sceny"] for u in s["ujecia"] if u["typ"] == "mowiace"]
    nieme = [u for s in sc["sceny"] for u in s["ujecia"] if u["typ"] == "bez_mowy"]
    assert len(g["shots"]) == len(mowiace) + 2 * len(nieme)
    mowa = [s for s in g["shots"] if s["workflow"] == "infinitetalk.a2v"]
    assert all(s["audio"].endswith(".mp3") and s["tlo_planu"].startswith("scenografia/rendery/s02/") for s in mowa)
    assert all(s["seconds"] <= 3 for s in g["shots"] if s["workflow"] == "ltx25.flf2v")


def test_montaz_os_czasu_i_plansza_koncowa():
    m = plan.montaz(scenariusz_wzorcowy(), "https://magazyn.example.eu/serial")
    assert m["os_czasu"][0]["od_s"] == 0 and m["plansza_koncowa"] == walidatory.PLANSZA_KONCOWA
    assert m["cel"] == "https://magazyn.example.eu/serial/s01e09/" and m["znaczek_ai"] is True


# ---------------------------------------------------------------- kolejka publikacji
def test_publikacja_https_i_status():
    sc = scenariusz_wzorcowy()
    with pytest.raises(ValueError, match="https"):
        publikacja.wpis(sc, d("2026-11-24T09:00:00+01:00"), {"wideo": "serial/media/x.mp4"}, 75, "ok")
    w = publikacja.wpis(sc, d("2026-11-24T09:00:00+01:00"), {"wideo": "https://x/a.mp4"}, 75, None)
    assert w["status"] == "w_produkcji"
    w = publikacja.wpis(sc, d("2026-11-24T09:00:00+01:00"), {"wideo": "https://x/a.mp4"}, 75, "przeszedł bramkę")
    assert w["status"] == "gotowy" and w["kotwica"] == walidatory.PLANSZA_KONCOWA


def test_dopisz_zastepuje_wpis_zastepczy_i_bierze_nastepny_slot():
    kol = _kol(("s01e09", "2026-11-23T16:00:00+01:00", "gotowy", "serial/media/nie-ma.mp4"),
               ("s01e08", "2026-11-24T09:00:00+01:00", "gotowy", "https://x/8.mp4"))
    w = publikacja.dopisz(kol, scenariusz_wzorcowy(), {"wideo": "https://x/9.mp4"}, 75, "ok",
                          d("2026-11-23T12:00:00+01:00"))
    assert w["publish_at"] == "2026-11-24T16:00:00+01:00"
    assert [o["id"] for o in kol["odcinki"]].count("s01e09") == 1
    with pytest.raises(ValueError):
        publikacja.dopisz(kol, scenariusz_wzorcowy(), {"wideo": "https://x/9.mp4"}, 75, "ok",
                          d("2026-11-23T12:00:00+01:00"))


# ---------------------------------------------------------------- karta sprawy
def test_anonimizacja():
    t = ("Sąd Rejonowy w Wałczu. Powód Z. S. (1) zamieszkały przy ul. Długiej 5, PESEL 44051401359, "
         "zapłacił 55.000 zł dnia 19 lutego 2004 roku; notariusz Barbara Kowalska; 37,95 m2; 29.07.2009r.; "
         "wynosiła 314.000 złotych w dniu 11 października 2010r.; akt rep. A 1001/2010.")
    a = karta.anonimizuj(t)
    for zakazane in ("Wałczu", "Z. S.", "Długiej", "44051401359", "55.000", "lutego 2004", "Kowalska", "37,95", "2009",
                     "314.000", "2010", "1001/2010"):
        assert zakazane not in a, zakazane


def test_plan_sezonu_z_biblii():
    p = karta.plan_sezonu(1)
    assert len(p) == 40
    assert p[9]["kotwica"] == "A17" and p[9]["slot"] == "09:00"
    assert karta.kotwice(p[1]["kotwica"]) == ["H18", "A13"]


def test_rekord_z_linkiem_saos():
    r = karta.Rekord("H23", "| H23 | banknoty | ... | [orzeczenie](https://www.saos.org.pl/judgments/58319) |", "06.md")
    assert r.saos_id == "58319"
