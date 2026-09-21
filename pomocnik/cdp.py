"""Sterowanie przegladarka protokolem DevTools (CDP), bez Playwrighta.

Pomocnik ma sie instalowac jednym kliknieciem, wiec liczy sie kazdy megabajt,
a Playwright ciagnie ze soba wlasny sterownik node. Potrzebujemy z niego
czterech operacji na stronie, wiec rozmawiamy z przegladarka wprost.

Zasady z docs/formularze.md obowiazuja tu tak samo:
  - czlowiek loguje sie sam, pomocnik nigdy nie dotyka hasla ani PIN-u karty,
  - pomocnik wypelnia pola i zatrzymuje sie przed wyslaniem,
  - sterujemy osobnym profilem przegladarki, nie prywatnym Chrome notariusza
    (od Chrome 136 sterowanie domyslnym profilem jest zreszta zablokowane).

Znane ograniczenie: szukamy pol w glownym dokumencie strony. Jesli formularz
rejestru siedzi w ramce (iframe), trzeba bedzie dolozyc wybor kontekstu -
komunikat bledu o tym przypomina.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

log = logging.getLogger("notarai.pomocnik.cdp")

PORT = 9222
CZAS_ODPOWIEDZI = 20  # sekund; formularze rejestrow potrafia myslec


class BladPrzegladarki(RuntimeError):
    """Blad po stronie przegladarki albo strony. Tresc trafia do notariusza,
    wiec nie wolno w niej umieszczac danych osobowych."""


def _pobierz_json(adres: str, czas: int = 5):
    with urllib.request.urlopen(adres, timeout=czas) as odpowiedz:
        return json.loads(odpowiedz.read().decode("utf-8"))


def karty(port: int = PORT) -> list[dict]:
    """Otwarte karty przegladarki uruchomionej z portem sterowania."""
    try:
        cele = _pobierz_json(f"http://127.0.0.1:{port}/json/list")
    except (OSError, urllib.error.URLError) as blad:
        raise BladPrzegladarki(
            "Nie moge polaczyc sie z przegladarka do formularzy. "
            "Otworz ja przyciskiem w pomocniku."
        ) from blad
    return [c for c in cele if c.get("type") == "page" and c.get("webSocketDebuggerUrl")]


def wybierz_karte(adres_prefiks: str = "", port: int = PORT) -> dict:
    """Karta, na ktorej mamy pracowac.

    Gdy znamy adres formularza, bierzemy karte z tym adresem. Dzieki temu
    pomocnik nie wpisze niczego w przypadkowa zakladke, nawet gdy notariusz
    ma otwartych kilka.
    """
    dostepne = karty(port)
    if not dostepne:
        raise BladPrzegladarki("Przegladarka do formularzy nie ma otwartej zadnej karty.")
    if adres_prefiks:
        pasujace = [k for k in dostepne if (k.get("url") or "").startswith(adres_prefiks)]
        if not pasujace:
            raise BladPrzegladarki(
                "W przegladarce do formularzy nie ma otwartej strony tego rejestru. "
                "Zaloguj sie do niego i otworz formularz."
            )
        return pasujace[0]
    return dostepne[0]


class Polaczenie:
    """Jedna karta przegladarki. Uzywac przez menedzer kontekstu."""

    def __init__(self, adres_ws: str):
        import websocket  # zaleznosc pomocnika, nie serwera

        # Chrome odrzuca polaczenia sterujace z naglowkiem Origin.
        self._ws = websocket.create_connection(
            adres_ws, timeout=CZAS_ODPOWIEDZI, suppress_origin=True, max_size=None
        )
        self._numer = 0

    def __enter__(self) -> "Polaczenie":
        return self

    def __exit__(self, *_) -> None:
        self.zamknij()

    def zamknij(self) -> None:
        try:
            self._ws.close()
        except Exception:  # noqa: BLE001 - zamykanie nie moze przeslonic wlasciwego bledu
            pass

    def polecenie(self, metoda: str, **parametry):
        self._numer += 1
        self._ws.send(json.dumps({"id": self._numer, "method": metoda, "params": parametry}))
        while True:
            wiadomosc = json.loads(self._ws.recv())
            if wiadomosc.get("id") != self._numer:
                continue  # zdarzenie strony albo odpowiedz na starsze polecenie
            if "error" in wiadomosc:
                raise BladPrzegladarki(
                    "Przegladarka odmowila: " + str(wiadomosc["error"].get("message", ""))
                )
            return wiadomosc.get("result", {})

    def oblicz(self, wyrazenie: str):
        """Wykonuje wyrazenie JavaScript w strony i zwraca wartosc."""
        wynik = self.polecenie(
            "Runtime.evaluate", expression=wyrazenie, returnByValue=True, awaitPromise=True
        )
        if wynik.get("exceptionDetails"):
            raise BladPrzegladarki("Strona odrzucila zapytanie o element formularza.")
        return wynik.get("result", {}).get("value")


class StronaCDP:
    """Adapter na interfejs Strona z formularze.silnik, oparty o CDP."""

    def __init__(self, polaczenie: Polaczenie):
        self._p = polaczenie

    @property
    def url(self) -> str:
        return self._p.oblicz("location.href") or ""

    def istnieje(self, selektor: str) -> bool:
        return bool(self._p.oblicz(f"!!document.querySelector({json.dumps(selektor)})"))

    def wpisz(self, selektor: str, wartosc: str) -> None:
        """Wpisuje tekst tak, jak zrobilby to czlowiek z klawiatury.

        Input.insertText wywoluje prawdziwe zdarzenia wejscia, wiec strony
        oparte o React czy Angular widza zmiane. Samo ustawienie .value
        czesto przechodzi im kolo nosa.

        O powodzeniu decyduje to, co po wszystkim jest w polu, a nie to, czy
        przegladarka zdazyla ustawic kursor. Gdy pole nie przyjelo pisania,
        podstawiamy wartosc wprost i dopiero wtedy uznajemy porazke.
        """
        self._ustaw_kursor(selektor)
        self._p.polecenie("Input.insertText", text=wartosc)
        self._powiadom_strone(selektor)
        if wartosc and not self.odczytaj(selektor):
            self._podstaw(selektor, wartosc)
            self._powiadom_strone(selektor)
        if wartosc and not self.odczytaj(selektor):
            raise BladPrzegladarki(
                f"Pole nie przyjelo wartosci ({selektor}). "
                "Moze byc zablokowane albo wymagac wczesniejszego wyboru."
            )

    def typ_pola(self, selektor: str) -> str:
        """Czym jest element: "password", "text", "checkbox", "select-one"...

        Pomocnik nigdy nie wpisuje do pola hasla ani PIN-u karty. Zeby moc tego
        odmowic, musi najpierw wiedziec, w co celuje selektor - mapowanie
        przychodzi z serwera i nie moze byc jedynym strazem.
        """
        return self._p.oblicz(f"""(() => {{
            const pole = document.querySelector({json.dumps(selektor)});
            if (!pole) return '';
            return (pole.type || pole.tagName || '').toLowerCase();
        }})()""") or ""

    def odczytaj(self, selektor: str) -> str:
        """Co naprawde jest w polu. Strony rejestrow czesto formatuja wpisana
        wartosc, wiec nie porownujemy jej znak w znak - patrzymy, czy cokolwiek
        zostalo przyjete."""
        return self._p.oblicz(f"""(() => {{
            const pole = document.querySelector({json.dumps(selektor)});
            if (!pole) return '';
            return ('value' in pole ? pole.value : pole.textContent) || '';
        }})()""") or ""

    def _podstaw(self, selektor: str, wartosc: str) -> None:
        self._p.oblicz(f"""(() => {{
            const pole = document.querySelector({json.dumps(selektor)});
            if (!pole) return;
            if ('value' in pole) {{ pole.value = {json.dumps(wartosc)}; }}
            else {{ pole.textContent = {json.dumps(wartosc)}; }}
        }})()""")

    def wybierz(self, selektor: str, wartosc: str) -> None:
        self.poczekaj_na(selektor, 5)
        udalo = self._p.oblicz(f"""(() => {{
            const pole = document.querySelector({json.dumps(selektor)});
            if (!pole || !pole.options) return false;
            const szukane = {json.dumps(wartosc)}.trim().toLowerCase();
            const opcja = [...pole.options].find(o =>
                (o.label || '').trim().toLowerCase() === szukane ||
                (o.text || '').trim().toLowerCase() === szukane ||
                (o.value || '').trim().toLowerCase() === szukane);
            if (!opcja) return false;
            pole.value = opcja.value;
            for (const nazwa of ['input', 'change']) {{
                pole.dispatchEvent(new Event(nazwa, {{bubbles: true}}));
            }}
            return true;
        }})()""")
        if not udalo:
            raise BladPrzegladarki(f"Na liscie nie ma takiej pozycji ({selektor}).")

    def zaznacz(self, selektor: str, tak: bool) -> None:
        self.poczekaj_na(selektor, 5)
        udalo = self._p.oblicz(f"""(() => {{
            const pole = document.querySelector({json.dumps(selektor)});
            if (!pole) return false;
            if (!!pole.checked !== {json.dumps(bool(tak))}) pole.click();
            return true;
        }})()""")
        if not udalo:
            raise BladPrzegladarki(f"Nie znalazlem pola wyboru ({selektor}).")

    def poczekaj_na_dokument(self, sekundy: float = 10) -> bool:
        """Czeka, az strona sie sparsuje. Bez tego pierwsze pytanie o pole
        trafia w pusty dokument i wyglada jak brak pola."""
        return self._czekaj("document.readyState !== 'loading'", sekundy)

    def poczekaj_na(self, selektor: str, sekundy: float = 10) -> bool:
        """Czeka na pojawienie sie elementu. Formularze rejestrow dociagaja
        pola po zalogowaniu, wiec sprawdzenie raz to za malo."""
        return self._czekaj(f"!!document.querySelector({json.dumps(selektor)})", sekundy)

    def _czekaj(self, warunek: str, sekundy: float) -> bool:
        import time

        koniec = time.monotonic() + sekundy
        while True:
            if bool(self._p.oblicz(warunek)):
                return True
            if time.monotonic() >= koniec:
                return False
            time.sleep(0.2)

    def _ustaw_kursor(self, selektor: str) -> None:
        """Ustawia kursor w pustym polu.

        Nie sprawdzamy tu document.activeElement: tuz po zaladowaniu strony
        przegladarka ustawia go z opoznieniem rzedu milisekund i wyglada to
        jak brak pola. Liczy sie, czy pole w ogole istnieje.
        """
        self.poczekaj_na(selektor, 5)
        istnieje = self._p.oblicz(f"""(() => {{
            const pole = document.querySelector({json.dumps(selektor)});
            if (!pole) return false;
            pole.focus();
            if ('value' in pole) {{ pole.value = ''; }} else {{ pole.textContent = ''; }}
            return true;
        }})()""")
        if not istnieje:
            raise BladPrzegladarki(
                f"Nie znalazlem pola na stronie ({selektor}). "
                "Sprawdz, czy formularz jest otwarty i czy nie siedzi w ramce."
            )

    def _powiadom_strone(self, selektor: str) -> None:
        """Domkniecie zdarzen. insertText daje 'input', ale 'change' strona
        zwykle dostaje dopiero przy opuszczeniu pola - a my pola nie opuszczamy."""
        self._p.oblicz(f"""(() => {{
            const pole = document.querySelector({json.dumps(selektor)});
            if (!pole) return;
            pole.dispatchEvent(new Event('change', {{bubbles: true}}));
        }})()""")


def polacz(adres_prefiks: str = "", port: int = PORT) -> tuple[Polaczenie, StronaCDP]:
    """Podlacza sie do wlasciwej karty. Zwraca (polaczenie, strona)."""
    karta = wybierz_karte(adres_prefiks, port)
    polaczenie = Polaczenie(karta["webSocketDebuggerUrl"])
    strona = StronaCDP(polaczenie)
    strona.poczekaj_na_dokument()
    log.info("podlaczono do karty przegladarki")
    return polaczenie, strona
