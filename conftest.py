"""Wspólne funkcje pomocnicze dla testów."""
from walidacja import WAGI_PESEL


def z_suma_kontrolna(dziesiec_cyfr: str) -> str:
    """Dodaje cyfrę kontrolną PESEL do 10-cyfrowego prefiksu."""
    suma = sum(int(c) * w for c, w in zip(dziesiec_cyfr, WAGI_PESEL))
    return dziesiec_cyfr + str((10 - suma % 10) % 10)


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _bez_poczty_w_testach():
    """Zaden test nie laczy sie z prawdziwa Poczta Polska.

    Sledzenie odpowiada "brak w systemie", e-Nadawca - bledem; testy, ktore
    potrzebuja konkretnych odpowiedzi, podstawiaja wlasny transport.
    """
    import httpx
    import poczta_polska
    import sledzenie

    def brak(zadanie):
        if "sledzenie" in zadanie.url.host or "tt.poczta-polska.pl" == zadanie.url.host:
            return httpx.Response(200, text=(
                '<e:Envelope xmlns:e="http://schemas.xmlsoap.org/soap/envelope/"><e:Body><r><return>'
                '<numer>X</numer><status>-1</status></return></r></e:Body></e:Envelope>'))
        return httpx.Response(503, text="test: brak Poczty")
    # Bez fixture monkeypatch: wspolna instancja zmienilaby kolejnosc sprzatania
    # (cofniecie zmiennych srodowiska po przeladowaniu modulow w innych testach).
    sledzenie.TRANSPORT = poczta_polska.TRANSPORT = httpx.MockTransport(brak)
    yield
    sledzenie.TRANSPORT = poczta_polska.TRANSPORT = None


@pytest.fixture(autouse=True)
def _bez_modelu_przy_kontroli_zasad():
    """Kontrola zasad kancelarii po projekcie (i ustalenia z korespondencji) nie wola prawdziwego Bedrock.
    Testy poprawki przez model podstawiaja wlasne funkcje.

    Bez monkeypatch - z tego samego powodu co wyzej (kolejnosc sprzatania).
    """
    import bedrock

    def brak(*_a, **_k):
        raise RuntimeError("test: brak modelu")
    oryginaly = bedrock.popraw_wg_zasad, bedrock.sprawdz_wytyczne, bedrock.wyciagnij_ustalenia
    bedrock.popraw_wg_zasad = bedrock.sprawdz_wytyczne = bedrock.wyciagnij_ustalenia = brak
    yield
    bedrock.popraw_wg_zasad, bedrock.sprawdz_wytyczne, bedrock.wyciagnij_ustalenia = oryginaly
