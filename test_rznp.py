"""Testy kontraktowe RZNP 2.0.8 na emulatorze (MockTransport). Wyłącznie
syntetyczne numery PESEL z poprawną sumą kontrolną - nie należą do osób."""
import httpx
import pytest
import rznp

def _p(base):  # syntetyczny PESEL z sumą kontrolną
    w = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
    return base + str((10 - sum(int(c) * k for c, k in zip(base, w)) % 10) % 10)

ZAS, NIEZ = _p("4405140135"), _p("5001010000")
NOW = "2026-11-25T10:00:00+01:00"

def emulator(r):
    assert r.headers["X-REQUEST-ID"]
    if r.headers.get("X-API-KEY") != "klucz-testowy":
        return httpx.Response(401, json={"kod": "20221120:000001", "komunikat": "klucz"})
    import json
    b = json.loads(r.content)
    if r.url.path.endswith("/aktualny"):
        st = "ZASTRZEZONY" if b["PESEL"] == ZAS else "NIEZASTRZEZONY"
        return httpx.Response(200, json={"aktualnyStatus": {"status": st}, "dataICzasWeryfikacji": NOW})
    return httpx.Response(200, json={"statusy": [{"status": "ZASTRZEZONY", "dataICzasPoczatkuWaznosciStatusu": NOW},
                                                  {"status": "NIEZASTRZEZONY"}], "dataICzasWeryfikacji": NOW})

def kl(fn=emulator, klucz="klucz-testowy"):
    return rznp.KlientRznp(klucz, baza_emulatora="http://localhost:8082/api/v1",
                           client=httpx.Client(transport=httpx.MockTransport(fn)))

def test_zastrzezony_i_niezastrzezony():
    assert kl().aktualny(ZAS, "Weryfikacja przed aktem")["status"] == "ZASTRZEZONY"
    assert kl().aktualny(NIEZ, "Weryfikacja przed aktem")["status"] == "NIEZASTRZEZONY"

def test_na_dzien_dwa_statusy():
    r = kl().na_dzien(ZAS, "2026-01-02", "Historia umowy")
    assert [s["status"] for s in r["statusy"]] == ["ZASTRZEZONY", "NIEZASTRZEZONY"]

def test_bledny_pesel_i_powod_lokalnie():
    c = kl()
    with pytest.raises(rznp.NiepoprawneZapytanie):
        c.aktualny("12345678901", "Powod testowy")
    with pytest.raises(rznp.NiepoprawneZapytanie):
        c.aktualny(ZAS, "x")
    with pytest.raises(rznp.NiepoprawneZapytanie):
        c.aktualny(ZAS, "Powód <script>")
    with pytest.raises(rznp.NiepoprawneZapytanie):
        c.na_dzien(ZAS, "2026-13-40", "Powod testowy")

def test_brak_autoryzacji():
    with pytest.raises(rznp.BrakAutoryzacji):
        kl(klucz="zly").aktualny(ZAS, "Powod testowy")

@pytest.mark.parametrize("kod", [500, 503, 504])
def test_awaria_nie_oznacza_braku_zastrzezenia(kod):
    c = kl(lambda r: httpx.Response(kod, json={"kod": "20221103:143921", "komunikat": "x",
                                               "planowanaNiedostepnoscDo": NOW}))
    with pytest.raises(rznp.Niedostepny) as e:
        c.aktualny(ZAS, "Powod testowy")
    assert e.value.http == kod

def test_timeout_i_polaczenie():
    def f(r):
        raise httpx.ReadTimeout("t")
    with pytest.raises(rznp.Niedostepny):
        kl(f).aktualny(ZAS, "Powod testowy")

@pytest.mark.parametrize("tresc", [{}, {"aktualnyStatus": {"status": "BRAK"}, "dataICzasWeryfikacji": NOW},
                                   {"aktualnyStatus": {"status": "NIEZASTRZEZONY"}}, []])
def test_niepoprawna_odpowiedz_to_blad_nie_brak_zastrzezenia(tresc):
    with pytest.raises(rznp.Niedostepny):
        kl(lambda r: httpx.Response(200, json=tresc)).aktualny(ZAS, "Powod testowy")

def test_pesel_i_klucz_nie_wyciekaja():
    c = kl(lambda r: httpx.Response(400, json={"kod": "x", "komunikat": ZAS}))
    with pytest.raises(rznp.NiepoprawneZapytanie) as e:
        c.aktualny(ZAS, "Powod testowy")
    assert ZAS not in str(e.value) and "klucz-testowy" not in repr(c)

def test_domyslnie_wylaczony_i_produkcja_wymaga_zgody():
    with pytest.raises(ValueError):
        rznp.KlientRznp("k")
    with pytest.raises(ValueError):
        rznp.KlientRznp("", "int")
    with pytest.raises(ValueError):
        rznp.KlientRznp("k", "prod")
    assert rznp.KlientRznp("k", "int")
    with pytest.raises(ValueError):
        rznp.KlientRznp("k", baza_emulatora="https://example.com")

def test_bez_przekierowan():
    with pytest.raises(rznp.Niedostepny):
        kl(lambda r: httpx.Response(302, headers={"Location": "https://example.com"})).aktualny(ZAS, "Powod testowy")
