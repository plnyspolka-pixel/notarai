"""Obscura --stealth MCP jako opcjonalny odczyt EKW dla pojedynczej sprawy.

Uzywa wyłącznie narzędzi oficjalnego MCP: navigate, fill_form, evaluate,
snapshot, close. Nie obchodzi CAPTCHA/WAF, nie rotuje IP, nie odpytuje masowo.
Wynik jest niekompletny => brak zapisu jako poprawnej księgi.
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime
from urllib.parse import urlparse

import httpx
import magazyn

PORTAL = "https://przegladarka-ekw.ms.gov.pl/eukw_prz/KsiegiWieczyste/wyszukiwanieKW"
ZRODLO = "EKW Ministerstwo Sprawiedliwosci (Obscura MCP stealth)"
SEKCJE = (("I-O", "Dzial I-O"), ("I-Sp", "Dzial I-Sp"),
          ("II", "Dzial II"), ("III", "Dzial III"), ("IV", "Dzial IV"))
_LOCK = threading.Lock()
_BLOKADY = ("error 15", "incapsula", "imperva", "access denied",
            "request unsuccessful", "request blocked", "captcha", "robot verification")


class ProblemObscura(Exception):
    def __init__(self, kod: str, opis: str):
        self.kod = kod
        super().__init__(opis)


def konfiguracja() -> tuple[str, str]:
    return (os.getenv("PIECZAPP_OBSCURA_MCP_URL", "").strip(),
            os.getenv("PIECZAPP_OBSCURA_MCP_TOKEN", "").strip())


def dostepne() -> bool:
    # Jeden MCP ma jeden stan przegladarki: aktywuj tylko dla dedykowanej kancelarii.
    # Inne kancelarie w SaaS korzystaja ze swoich osobnych dostawcow.
    url, token = konfiguracja()
    przypisana = os.getenv("PIECZAPP_OBSCURA_KANCELARIA", "").strip()
    return bool(url and token and przypisana and przypisana == magazyn.kancelaria())


def _adres(url: str) -> str:
    parsed = urlparse(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ProblemObscura("konfiguracja", "Adres Obscura MCP zawiera niedozwolone parametry")
    if parsed.scheme == "https" and parsed.hostname:
        return url
    if parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost"):
        return url
    raise ProblemObscura("konfiguracja", "Obscura MCP wymaga HTTPS albo lokalnego loopback")


def _tekst(odp: dict) -> str:
    return "\n".join(str(x.get("text", "")) for x in odp.get("content", [])
                     if x.get("type") == "text")


class MCP:
    def __init__(self, klient: httpx.Client):
        self.klient = klient
        self.url, self.token = konfiguracja()
        if not self.url or not self.token:
            raise ProblemObscura("brak_tokenu", "Obscura MCP nie jest skonfigurowana")
        self.url = _adres(self.url)
        self.licznik = 0

    def rpc(self, metoda: str, parametry: dict | None = None) -> dict:
        self.licznik += 1
        naglowki = {"Authorization": "Bearer " + self.token,
                    "Accept": "application/json, text/event-stream"}
        cf_id = os.getenv("PIECZAPP_CF_ACCESS_CLIENT_ID", "").strip()
        cf_secret = os.getenv("PIECZAPP_CF_ACCESS_CLIENT_SECRET", "").strip()
        if bool(cf_id) != bool(cf_secret):
            raise ProblemObscura("konfiguracja", "Wymagane oba naglowki Cloudflare Access")
        if cf_id:
            naglowki.update({"CF-Access-Client-Id": cf_id, "CF-Access-Client-Secret": cf_secret})
        try:
            odp = self.klient.post(self.url, json={
                "jsonrpc": "2.0", "id": self.licznik, "method": metoda,
                "params": parametry or {}}, headers=naglowki)
            if odp.status_code in (401, 403):
                raise ProblemObscura("blad_tokenu", "Obscura MCP odmowila dostepu")
            if odp.status_code == 429:
                raise ProblemObscura("limit", "Limit wywolan Obscura MCP")
            odp.raise_for_status()
            if len(odp.content) > 2_000_000:
                raise ProblemObscura("niepelny", "Zbyt duza odpowiedz Obscura MCP")
            if "text/event-stream" in odp.headers.get("content-type", ""):
                wiersze = [x[5:].strip() for x in odp.text.splitlines() if x.startswith("data:")]
                if not wiersze:
                    raise ValueError("Empty MCP stream")
                dane = json.loads(wiersze[-1])
            else:
                dane = odp.json()
        except ProblemObscura:
            raise
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ProblemObscura("niedostepny", "Obscura MCP nie odpowiada lub zwraca bledny format") from exc
        if not isinstance(dane, dict) or "error" in dane:
            raise ProblemObscura("niedostepny", "Blad protokolu Obscura MCP")
        wynik = dane.get("result")
        if not isinstance(wynik, dict) or wynik.get("isError"):
            raise ProblemObscura("niedostepny", "Narzedzie Obscura MCP zakonczylo sie bledem")
        return wynik

    def narzedzie(self, nazwa: str, arg: dict | None = None) -> str:
        return _tekst(self.rpc("tools/call", {"name": nazwa, "arguments": arg or {}}))

    def odczyt(self) -> dict:
        expr = """(() => JSON.stringify({
          url: location.href, title: document.title || '',
          text: (document.body?.innerText || '').slice(0, 70000),
          tables: Array.from(document.querySelectorAll('table'))
            .map(x => x.innerText || '').filter(x => x.trim().length > 20)
            .join('\\n').slice(0, 65000)
        }))()"""
        raw = self.narzedzie("browser_evaluate", {"expression": expr})
        try:
            strona = json.loads(raw)
        except ValueError as exc:
            raise ProblemObscura("niepelny", "Nie udalo sie odczytac DOM EKW") from exc
        u = urlparse(str(strona.get("url") or ""))
        if u.scheme != "https" or u.hostname != "przegladarka-ekw.ms.gov.pl":
            raise ProblemObscura("niedostepny", "Przegladarka opuscila oficjalny portal EKW")
        niskie = (strona.get("text") or "").lower()
        if any(w in niskie for w in _BLOKADY):
            raise ProblemObscura("blokada", "Portal EKW zablokowal automatyczny odczyt; potrzebne sprawdzenie reczne")
        return strona

    def kliknij(self, rodzaj: str, etykieta: str = "") -> None:
        # Scisle ograniczone do widocznych kontrolek portalu. Bez wykonywania skryptow ze strony.
        params = json.dumps({"kind": rodzaj, "label": etykieta}, ensure_ascii=False)
        expression = """(() => {
          const opt = """ + params + """;
          const norm = s => (s || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'')
             .toLowerCase().replace(/\\s+/g,' ').trim();
          const buttons = [...document.querySelectorAll('a,button,input[type=submit],input[type=button],[role=tab]')];
          const label = el => norm(el.innerText || el.value || el.textContent || '');
          let hit;
          if(opt.kind === 'search') hit = buttons.find(el => /^(wyszukaj|szukaj)(\\s|$)/.test(label(el)));
          else if(opt.kind === 'current') hit = buttons.find(el => label(el).includes('przegladanie aktualnej tresci') &&
                                                   !label(el).includes('dotychczasowa'));
          else if(opt.kind === 'section') hit = buttons.find(el => label(el) === norm(opt.label) ||
                                             label(el) === norm(opt.label.replace('Dzial ', '')));
          if(!hit) return 'MISSING';
          hit.click(); return 'CLICKED';
        })()"""
        if self.narzedzie("browser_evaluate", {"expression": expression}).strip() != "CLICKED":
            raise ProblemObscura("niepelny", "Nie rozpoznano etapu nawigacji EKW: " + rodzaj)


def pobierz(numer: str, klient: httpx.Client | None = None) -> dict:
    """Jedno zadanie = jedna KW. Wszelkie problemy koncza sie bez trwałego wyniku."""
    czesci = numer.split("/")
    if len(czesci) != 3:
        raise ProblemObscura("niepelny", "Nieprawidlowy format numeru KW")
    own = klient is None
    if not _LOCK.acquire(blocking=False):
        raise ProblemObscura("limit", "Przegladarka Obscura jest zajeta innym zadaniem")
    try:
        k = klient or httpx.Client(timeout=httpx.Timeout(45, connect=10), follow_redirects=False)
        m = MCP(k)
        try:
            tools = m.rpc("tools/list")
            dost = {x.get("name") for x in tools.get("tools", [])}
            potrzebne = {"browser_navigate", "browser_fill_form", "browser_evaluate", "browser_close"}
            if not potrzebne.issubset(dost):
                raise ProblemObscura("konfiguracja", "Obscura MCP nie udostepnia wymaganych narzedzi")
            m.narzedzie("browser_navigate", {"url": PORTAL})
            m.odczyt()
            pola = [{"selector": "#kodWydzialuInput", "value": czesci[0]},
                    {"selector": "#numerKsiegiWieczystej", "value": czesci[1]},
                    {"selector": "#cyfraKontrolna", "value": czesci[2]}]
            m.narzedzie("browser_fill_form", {"fields": pola})
            m.kliknij("search")
            wynik = m.odczyt()
            if "przeglądanie aktualnej treści" not in wynik["text"].lower() and (
                    "przegladanie aktualnej tresci" not in wynik["text"].lower()):
                raise ProblemObscura("niepelny", "Nie uzyskano ekranu wyboru aktualnej tresci KW")
            m.kliknij("current")
            ekran = m.odczyt()
            if numer not in ekran.get("text", "").replace(" ", ""):
                raise ProblemObscura("niepelny", "Portal nie potwierdzil numeru zwroconej księgi")
            dzialy = []
            odczyty = []
            for oznaczenie, nazwa in SEKCJE:
                m.kliknij("section", nazwa)
                ekran = m.odczyt()
                raw = (ekran.get("tables") or "").strip() or (ekran.get("text") or "").strip()
                brak = bool(re.search(r"\bBRAK\s+WPIS[OÓ]W\b", raw, re.I))
                if len(raw) < 24 and not brak:
                    raise ProblemObscura("niepelny", "Brak zawartosci dzialu " + oznaczenie)
                odczyty.append(raw)
                dzialy.append({"oznaczenie": oznaczenie, "tytul": nazwa,
                               "pusty": brak, "tekst": "BRAK WPISÓW" if brak else raw})
            if len(set(odczyty)) != len(SEKCJE):
                raise ProblemObscura("niepelny", "Widoki działow sa nierozroznialne; odczyt odrzucony")
            return {"numer_kw": numer, "kod_sadu": czesci[0], "sad": "", "typ": "",
                    "widok": "aktualna", "dzialy": dzialy,
                    "pobrano": datetime.now().isoformat(timespec="seconds"),
                    "zrodlo": ZRODLO, "dostawca": "obscura"}
        finally:
            try:
                m.narzedzie("browser_close")
            except Exception:
                pass
            if own:
                k.close()
    finally:
        _LOCK.release()
