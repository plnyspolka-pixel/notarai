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
# Jak zbudowac selektor wskazujacy dokladnie ten element. Wspolne dla listy
# elementow i dla szukania po tekscie, zeby oba mowily o stronie tak samo.
_JS_SCIEZKA = """
const sciezka = (el) => {
    if (el.id) return '#' + CSS.escape(el.id);
    if (el.name) return el.tagName.toLowerCase() + '[name="' + CSS.escape(el.name) + '"]';
    const kroki = [];
    let w = el;
    while (w && w.nodeType === 1 && w !== document.body) {
        const rodzic = w.parentNode;
        if (!rodzic) break;
        const rodzenstwo = [...rodzic.children].filter(e => e.tagName === w.tagName);
        kroki.unshift(w.tagName.toLowerCase() + ':nth-of-type(' + (rodzenstwo.indexOf(w) + 1) + ')');
        w = rodzic;
    }
    return 'body > ' + kroki.join(' > ');
};
"""

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
        self._ws.send(json.dumps({"id": self._numer, "method": metoda,
                                  "params": {k: v for k, v in parametry.items()
                                             if v is not None}}))
        while True:
            wiadomosc = json.loads(self._ws.recv())
            if wiadomosc.get("id") != self._numer:
                continue  # zdarzenie strony albo odpowiedz na starsze polecenie
            if "error" in wiadomosc:
                raise BladPrzegladarki(
                    "Przegladarka odmowila: " + str(wiadomosc["error"].get("message", ""))
                )
            return wiadomosc.get("result", {})

    def oblicz(self, wyrazenie: str, kontekst: int | None = None):
        """Wykonuje wyrazenie JavaScript i zwraca wartosc.

        `kontekst` wskazuje ramke strony. Formularze urzedowe lubia siedziec w
        iframe (KRZ tak wlasnie ma), a kod wykonany w dokumencie glownym nie
        widzi ich pol w ogole.
        """
        wynik = self.polecenie(
            "Runtime.evaluate", expression=wyrazenie, returnByValue=True,
            awaitPromise=True, contextId=kontekst,
        )
        if wynik.get("exceptionDetails"):
            raise BladPrzegladarki("Strona odrzucila zapytanie o element formularza.")
        return wynik.get("result", {}).get("value")

    def konteksty(self) -> list[dict]:
        """Ramki strony jako osobne konteksty wykonania kodu.

        Dla kazdej ramki tworzymy wlasny, odizolowany swiat: widzi ten sam
        dokument, ale nie miesza sie ze skryptami strony.
        """
        self.polecenie("Page.enable")
        ramki: list[dict] = []

        def zejdz(wezel: dict) -> None:
            if "frame" in wezel:
                ramki.append(wezel["frame"])
            for dziecko in wezel.get("childFrames") or []:
                zejdz(dziecko)

        zejdz(self.polecenie("Page.getFrameTree").get("frameTree", {}))
        wynik = []
        for ramka in ramki:
            try:
                odp = self.polecenie("Page.createIsolatedWorld",
                                     frameId=ramka["id"], worldName="notarai")
            except BladPrzegladarki:
                continue  # ramka zdazyla zniknac albo jest nam niedostepna
            wynik.append({"ramka": ramka["id"], "adres": ramka.get("url", ""),
                          "kontekst": odp.get("executionContextId")})
        return wynik


class StronaCDP:
    """Adapter na interfejs Strona z formularze.silnik, oparty o CDP."""

    def __init__(self, polaczenie: Polaczenie, kontekst: int | None = None):
        self._p = polaczenie
        self._kontekst = kontekst   # None = dokument glowny, inaczej ramka

    def _ob(self, wyrazenie: str):
        return self._p.oblicz(wyrazenie, self._kontekst)

    def ramki(self) -> list["StronaCDP"]:
        """Strona widziana z kazdej ramki osobno, razem z dokumentem glownym."""
        return [StronaCDP(self._p, k["kontekst"]) for k in self._p.konteksty()
                if k.get("kontekst")]

    def ramka_z(self, selektor: str, sekundy: float = 20) -> "StronaCDP":
        """Ramka, w ktorej jest wskazany element.

        Formularze urzedowe lubia siedziec w iframe - KRZ tak wlasnie ma.
        Szukanie po zawartosci jest odporniejsze niz zapamietywanie adresu
        ramki, bo ten potrafi sie zmienic przy kazdym wdrozeniu portalu.
        """
        import time

        koniec = time.monotonic() + sekundy
        while True:
            for ramka in self.ramki():
                try:
                    if ramka.istnieje(selektor):
                        return ramka
                except BladPrzegladarki:
                    continue
            if time.monotonic() >= koniec:
                raise BladPrzegladarki(
                    f"Nie znalazlem formularza na stronie ({selektor}) - "
                    "ani w dokumencie glownym, ani w zadnej ramce."
                )
            time.sleep(0.5)

    def ramka_z_tekstem(self, fragment: str, sekundy: float = 20) -> "StronaCDP":
        """Ramka, w ktorej widac taki napis. Dla portali bez stalych selektorow."""
        import time

        koniec = time.monotonic() + sekundy
        while True:
            for ramka in self.ramki():
                try:
                    if ramka.selektor_po_tekscie(fragment):
                        return ramka
                except BladPrzegladarki:
                    continue
            if time.monotonic() >= koniec:
                raise BladPrzegladarki(
                    f"Nie znalazlem na stronie napisu „{fragment}” - "
                    "ani w dokumencie glownym, ani w zadnej ramce."
                )
            time.sleep(0.5)

    @property
    def url(self) -> str:
        return self._ob("location.href") or ""

    def istnieje(self, selektor: str) -> bool:
        return bool(self._ob(f"!!document.querySelector({json.dumps(selektor)})"))

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

    def kliknij(self, selektor: str) -> None:
        """Klika wskazany element.

        Wypelnianie formularzy tej czynnosci nie uzywa i uzywac nie bedzie -
        tam pomocnik zatrzymuje sie przed przyciskiem wysylki. Klikanie jest
        potrzebne sekcji "Klikamy", gdzie model prowadzi przegladarke, i to
        ona pilnuje, w co kliknac nie wolno (patrz klikamy.WYSYLKA).
        """
        self.poczekaj_na(selektor, 5)
        udalo = self._ob(f"""(() => {{
            const el = document.querySelector({json.dumps(selektor)});
            if (!el) return false;
            el.scrollIntoView({{block: 'center'}});
            el.click();
            return true;
        }})()""")
        if not udalo:
            raise BladPrzegladarki(f"Nie znalazlem elementu do klikniecia ({selektor}).")

    def otworz(self, adres: str) -> None:
        self._p.polecenie("Page.navigate", url=adres)
        self.poczekaj_na_dokument()

    def selektor_po_tekscie(self, fragment: str) -> str | None:
        """Selektor widocznego elementu z takim tekstem, najglebiej zagniezdzonego.

        Portale urzedowe nie gwarantuja nazw klas ani identyfikatorow, ale
        gwarantuja napisy - bo te widzi urzednik i uzytkownik. "Osoba fizyczna
        nieprowadzaca dzialalnosci gospodarczej" przetrwa zmiane ukladu strony
        dluzej niz jakikolwiek selektor CSS.
        """
        return self._ob(f"""(() => {{
            {_JS_SCIEZKA}
            const szukane = {json.dumps(fragment)}.toLowerCase();
            const widoczny = (el) => {{
                const p = el.getBoundingClientRect();
                return p.width > 0 && p.height > 0 && getComputedStyle(el).visibility !== 'hidden';
            }};
            const pasuje = [...document.querySelectorAll('*')].filter(el =>
                widoczny(el) && (el.textContent || '').toLowerCase().includes(szukane));
            if (!pasuje.length) return null;
            // Najglebszy pasujacy: rodzic tez "zawiera" ten tekst, ale klikniecie
            // w rodzica trafia obok.
            pasuje.sort((a, b) => (a.textContent || '').length - (b.textContent || '').length);
            return sciezka(pasuje[0]);
        }})()""")

    def zrzut(self, cel) -> None:
        """Zrzut widocznej czesci strony. Dowod starannosci do akt sprawy."""
        import base64
        from pathlib import Path

        wynik = self._p.polecenie("Page.captureScreenshot", format="png")
        dane = wynik.get("data")
        if not dane:
            raise BladPrzegladarki("Przegladarka nie oddala zrzutu ekranu.")
        Path(cel).write_bytes(base64.b64decode(dane))

    def elementy(self, limit: int = 120) -> list[dict]:
        """Co na stronie da sie kliknac albo wypelnic, z gotowym selektorem.

        Model dostaje numerowana liste, a nie wspolrzedne na obrazku. Klikniecie
        "w punkt x,y" jest zgadywaniem: wystarczy, ze strona przeskoczy o dwa
        piksele i trafiamy w inny przycisk. Selektor wskazuje konkretny element
        albo nie wskazuje niczego, co w formularzu urzedowym jest roznica
        miedzy pomylka a jej brakiem.
        """
        return self._ob(f"""(() => {{
            {_JS_SCIEZKA}
            const widoczny = (el) => {{
                const p = el.getBoundingClientRect();
                return p.width > 0 && p.height > 0 && getComputedStyle(el).visibility !== 'hidden';
            }};
            const opis = (el) => (
                el.getAttribute('aria-label') || el.placeholder || el.title ||
                (el.labels && el.labels[0] ? el.labels[0].textContent : '') ||
                (el.value && el.type === 'submit' ? el.value : '') ||
                el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 100);
            const wybor = 'a[href], button, input, select, textarea, [role=button], [onclick], [contenteditable]';
            return [...document.querySelectorAll(wybor)]
                .filter(widoczny)
                .slice(0, {int(limit)})
                .map((el, i) => ({{
                    nr: i + 1,
                    rola: (el.tagName.toLowerCase() + (el.type ? ':' + el.type : '')),
                    opis: opis(el),
                    selektor: sciezka(el),
                }}));
        }})()""") or []

    def tekst_strony(self, limit: int = 4000) -> str:
        """Widoczny tekst strony - do oceny, czy jestesmy tam, gdzie trzeba."""
        tresc = self._ob(
            "(document.body ? document.body.innerText : '').replace(/\\s+\\n/g, '\\n')"
        ) or ""
        return tresc[:limit]

    def typ_pola(self, selektor: str) -> str:
        """Czym jest element: "password", "text", "checkbox", "select-one"...

        Pomocnik nigdy nie wpisuje do pola hasla ani PIN-u karty. Zeby moc tego
        odmowic, musi najpierw wiedziec, w co celuje selektor - mapowanie
        przychodzi z serwera i nie moze byc jedynym strazem.
        """
        return self._ob(f"""(() => {{
            const pole = document.querySelector({json.dumps(selektor)});
            if (!pole) return '';
            return (pole.type || pole.tagName || '').toLowerCase();
        }})()""") or ""

    def odczytaj(self, selektor: str) -> str:
        """Co naprawde jest w polu. Strony rejestrow czesto formatuja wpisana
        wartosc, wiec nie porownujemy jej znak w znak - patrzymy, czy cokolwiek
        zostalo przyjete."""
        return self._ob(f"""(() => {{
            const pole = document.querySelector({json.dumps(selektor)});
            if (!pole) return '';
            return ('value' in pole ? pole.value : pole.textContent) || '';
        }})()""") or ""

    def _podstaw(self, selektor: str, wartosc: str) -> None:
        self._ob(f"""(() => {{
            const pole = document.querySelector({json.dumps(selektor)});
            if (!pole) return;
            if ('value' in pole) {{ pole.value = {json.dumps(wartosc)}; }}
            else {{ pole.textContent = {json.dumps(wartosc)}; }}
        }})()""")

    def wybierz(self, selektor: str, wartosc: str) -> None:
        self.poczekaj_na(selektor, 5)
        udalo = self._ob(f"""(() => {{
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
        udalo = self._ob(f"""(() => {{
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
            if bool(self._ob(warunek)):
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
        istnieje = self._ob(f"""(() => {{
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
        self._ob(f"""(() => {{
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
