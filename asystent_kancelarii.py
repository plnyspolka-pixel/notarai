"""Asystent kancelarii: notariusz mowi po swojemu, co ma dzialac inaczej,
a asystent od razu to ustawia.

Przyklady:
  "nie pisz mi <<BRAK>>, zostawiaj znak zapytania"   -> ustawienie "braki"
  "kwoty zawsze cyframi i slownie"                     -> zasada kancelarii
  "nie sprawdzaj mi numeracji ustepow"                 -> wylaczenie kontroli
  "paragrafy taksy to nie paragrafy aktu"              -> prosba o zmiane w programie

Model (Claude przez Bedrock w eu-central-1) dostaje narzedzia, ktore wolaja
TE SAME funkcje co reczne ustawienia (zasady.py, ustawienia_kancelarii.py).
Asystent nie ma innej drogi do danych kancelarii niz te narzedzia.

Bezpieczenstwo:
  - zmiany wprowadza tylko notariusz (wlasciciel kancelarii) - te same
    uprawnienia co ekran ustawien; pracownik moze pytac i zglaszac prosby,
  - kazda zmiana trafia do dziennika (plik kancelarii "asystent") i da sie ja
    cofnac ("cofnij"),
  - prosby o zmiane programu ida do samonaprawy po anonimizacji
    (samonaprawa.zglos_prosbe), najwyzej MAX_PROSB_NA_DOBE na kancelarie,
  - rozmowa nie trafia do logow (tylko nazwy narzedzi i wynik).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import bedrock
import klauzule
import magazyn
import samonaprawa
import ustawienia_kancelarii
import zasady

log = logging.getLogger("pieczapp.asystent_kancelarii")

PLIK = "asystent"
MAX_KROKOW = 6
MAX_DZIENNIKA = 30
MAX_PROSB_NA_DOBE = 5
MAX_HISTORII = 20

SYSTEM = """Jesteś asystentem ustawień w aplikacji notarai (asystent kancelarii notarialnej, \
który sporządza projekty aktów). Rozmawiasz z notariuszem albo pracownikiem kancelarii po polsku, \
krótko i bez żargonu informatycznego. Nie zgaduj płci rozmówcy: pisz formami neutralnymi \
(„ustawione”, „można cofnąć”, „proszę napisać”), bez „Pan/Pani” i bez przechodzenia na „ty”.

Twoje zadanie: zrozumieć, co ma działać inaczej, i OD RAZU to ustawić narzędziami. Nie każ \
notariuszowi szukać opcji w menu. Każdy notariusz dopasowuje aplikację pod siebie: sposób pisania \
aktów (zasady, wytyczne), wygląd i sposób pracy (wielkość tekstu, ekran po zalogowaniu, chowanie \
narzędzi z menu) - to wszystko są ustawienia tej kancelarii, nie zmiany dla innych. Gdy notariusz \
chce dopasować coś, czego nie ma w ustawieniach (np. inny układ ekranu, nowy przycisk, inna \
kolejność kroków), zgłoś to przez zglos_zmiane_programu jako "przełącznik dla tej kancelarii: ..." \
- powstanie zwykle w ciągu godziny i od razu będziesz mógł go włączać.

Jak działać:
1. Najpierw sprawdź stan narzędziem pokaz_ustawienia, jeśli nie znasz obecnych ustawień.
2. Wybierz najlepsze narzędzie:
   - zmien_ustawienie - ogólne ustawienia kancelarii (lista z opisami w opisie narzędzia), np. \
sposób oznaczania brakujących danych w Wordzie: "opis" = <<BRAK: ...>> albo "pytajnik" = ?,
   - dodaj_zasade - reguła redakcyjna kancelarii zdaniem notariusza (zamiany słów, zakazane \
i wymagane sformułowania, kwoty słownie, format dat, cudzysłowy, wymagane części aktu, wytyczne). \
Zdanie zasady pisz tak, jak powiedziałby je notariusz aplikantowi; wynik narzędzia mówi, jak \
aplikacja je zrozumiała - jeśli źle, popraw albo usuń,
   - zmien_zasade / usun_zasade - istniejące zasady (identyfikator z pokaz_ustawienia),
   - ustaw_kontrole - wbudowane kontrole konstrukcji aktu (numeracja paragrafów i ustępów, \
odesłania, luki, warianty) - wyłączaj tylko na wyraźną prośbę,
   - cofnij_ostatnia_zmiane - gdy ktoś chce wrócić do poprzedniego stanu,
   - zglos_zmiane_programu - gdy prośby NIE da się spełnić ustawieniem ani zasadą (aplikacja \
działa źle albo potrzebna jest nowa funkcja). Opisz problem ogólnie, bez danych klientów.
3. Po zmianie powiedz jednym-dwoma zdaniami, co dokładnie się zmieniło, od kiedy działa \
(od następnego projektu) i że można to cofnąć, pisząc "cofnij".
4. Gdy prośba jest niejasna albo może zepsuć projekty (np. wyłączenie kontroli), dopytaj jednym \
pytaniem, zamiast zgadywać.
5. Nigdy nie zmieniaj treści konkretnego aktu - od tego jest projekt i rozmowa o sprawie.
6. Nie przepisuj danych klientów (nazwisk, PESEL, adresów, numerów dokumentów) do narzędzi.
7. Gdy narzędzie odpowie, że brak uprawnień - wyjaśnij, że zmiany wprowadza notariusz \
(właściciel kancelarii), a prośbę można zgłosić.
"""


def _narzedzie(nazwa: str, opis: str, wlasciwosci: dict | None = None, wymagane: list[str] | None = None) -> dict:
    return {"name": nazwa, "description": opis, "inputSchema": {"json": {
        "type": "object", "properties": wlasciwosci or {}, "required": wymagane or []}}}


NARZEDZIA = [
    _narzedzie("pokaz_ustawienia", "Obecne ustawienia kancelarii: ogólne, zasady (z identyfikatorami) "
               "i wbudowane kontrole konstrukcji aktu."),
    _narzedzie("zmien_ustawienie", "Zmienia ustawienie ogólne kancelarii. Ustawienia: "
               + "; ".join(f"{k} - {o}" for k, o in ustawienia_kancelarii.OPISY_USTAWIEN.items()), {
        "klucz": {"type": "string", "enum": sorted(ustawienia_kancelarii.OPISY_USTAWIEN)},
        "wartosc": {"type": "string"}}, ["klucz", "wartosc"]),
    _narzedzie("dodaj_zasade", "Dodaje zasadę kancelarii zapisaną zdaniem notariusza.", {
        "zdanie": {"type": "string"},
        "poziom": {"type": "string", "enum": ["blokuje", "ostrzega"]}}, ["zdanie"]),
    _narzedzie("zmien_zasade", "Zmienia istniejącą zasadę: treść, poziom albo włączenie.", {
        "id": {"type": "string"}, "zdanie": {"type": "string"},
        "poziom": {"type": "string", "enum": ["blokuje", "ostrzega"]},
        "wlaczona": {"type": "boolean"}}, ["id"]),
    _narzedzie("usun_zasade", "Usuwa zasadę kancelarii.", {"id": {"type": "string"}}, ["id"]),
    _narzedzie("ustaw_kontrole", "Włącza albo wyłącza wbudowaną kontrolę konstrukcji aktu.", {
        "kod": {"type": "string", "enum": sorted(klauzule.KONSTRUKCJA)},
        "wlaczona": {"type": "boolean"}}, ["kod", "wlaczona"]),
    _narzedzie("cofnij_ostatnia_zmiane", "Cofa ostatnią zmianę wprowadzoną przez asystenta."),
    _narzedzie("zglos_zmiane_programu", "Przekazuje prośbę o zmianę w programie zespołowi notarai "
               "(automatyczna naprawa). Tylko gdy nie da się tego ustawić.", {
                   "opis": {"type": "string", "description": "Co działa źle albo czego brakuje i jak "
                            "powinno działać. Bez danych klientów."}}, ["opis"]),
]


class BrakUprawnien(Exception):
    pass


# ---------------------------------------------------------------------------
# Dziennik zmian (cofanie)
# ---------------------------------------------------------------------------
def _domyslne() -> dict:
    return {"zmiany": [], "prosby": []}


def _zapisz_zmiane(opis: str, cofniecie: dict) -> None:
    def zmiana(dane: dict) -> None:
        dane.setdefault("zmiany", []).append({
            "czas": datetime.now().isoformat(timespec="seconds"), "opis": opis, "cofniecie": cofniecie})
        dane["zmiany"] = dane["zmiany"][-MAX_DZIENNIKA:]
    magazyn.zmien_plik_kancelarii(PLIK, zmiana, _domyslne())


def _ustawienia_teraz() -> dict:
    zas = zasady.wczytaj()
    return {
        "ogolne": ustawienia_kancelarii.wczytaj(),
        "zasady": [{"id": z["id"], "zdanie": z["tekst"], "jak_rozumiem": z.get("opis", ""),
                    "poziom": z["poziom"], "wlaczona": z.get("wlaczona", True)}
                   for z in zas.get("zasady", [])],
        "kontrole": {k: {"opis": opis, "wlaczona": k not in zas.get("wbudowane_wylaczone", [])}
                     for k, opis in klauzule.KONSTRUKCJA.items()},
    }


# ---------------------------------------------------------------------------
# Narzedzia
# ---------------------------------------------------------------------------
def _zmien_ustawienie(w: dict) -> dict:
    klucz, wartosc = w.get("klucz"), str(w.get("wartosc", "")).strip()
    if klucz not in ustawienia_kancelarii.OPISY_USTAWIEN:
        raise ValueError("Nieznane ustawienie.")
    przed = ustawienia_kancelarii.wczytaj()[klucz]
    po = ustawienia_kancelarii.zapisz({klucz: wartosc})[klucz]
    _zapisz_zmiane(f"ustawienie {klucz}: {przed} -> {po}", {"rodzaj": "ustawienie", "klucz": klucz, "wartosc": przed})
    return {"zmieniono": klucz, "bylo": przed, "jest": po}


def _dodaj_zasade(w: dict) -> dict:
    nadpisania = {"poziom": w["poziom"]} if w.get("poziom") in zasady.POZIOMY else None
    wynik = zasady.dodaj(str(w.get("zdanie", "")), nadpisania, zrodlo="asystent")
    z = wynik["zasada"]
    if not wynik["juz_byla"]:
        cofniecie = {"rodzaj": "usun_zasade", "id": z["id"]}
        if wynik.get("zastapiona"):
            stara = wynik["zastapiona"]
            cofniecie = {"rodzaj": "przywroc_zastapiona", "id": z["id"],
                         "zdanie": stara["tekst"], "poziom": stara["poziom"]}
        _zapisz_zmiane(f"dodano zasade: {z['tekst']}", cofniecie)
    return {"id": z["id"], "juz_byla": wynik["juz_byla"], "jak_rozumiem": z.get("opis", ""),
            "typ": z["typ"], "zastapiona": (wynik.get("zastapiona") or {}).get("tekst")}


def _znajdz_zasade(identyfikator: str) -> dict:
    for z in zasady.wczytaj().get("zasady", []):
        if z["id"] == identyfikator:
            return z
    raise KeyError("Nie ma zasady o tym identyfikatorze.")


def _zmien_zasade(w: dict) -> dict:
    stara = _znajdz_zasade(str(w.get("id", "")))
    zmiany = {}
    if w.get("zdanie"):
        zmiany["tekst"] = str(w["zdanie"])
    if w.get("poziom") in zasady.POZIOMY:
        zmiany["poziom"] = w["poziom"]
    if isinstance(w.get("wlaczona"), bool):
        zmiany["wlaczona"] = w["wlaczona"]
    if not zmiany:
        raise ValueError("Nic do zmiany.")
    nowa = zasady.zmien(stara["id"], zmiany)
    _zapisz_zmiane(f"zmieniono zasade: {stara['tekst']}", {
        "rodzaj": "zmien_zasade", "id": stara["id"],
        "zmiany": {"tekst": stara["tekst"], "poziom": stara["poziom"], "wlaczona": stara.get("wlaczona", True)}})
    return {"id": nowa["id"], "jak_rozumiem": nowa.get("opis", ""), "poziom": nowa["poziom"],
            "wlaczona": nowa.get("wlaczona", True)}


def _usun_zasade(w: dict) -> dict:
    stara = _znajdz_zasade(str(w.get("id", "")))
    zasady.usun(stara["id"])
    _zapisz_zmiane(f"usunieto zasade: {stara['tekst']}", {
        "rodzaj": "przywroc_zasade", "zdanie": stara["tekst"], "poziom": stara["poziom"],
        "wlaczona": stara.get("wlaczona", True), "zakres": stara.get("zakres")})
    return {"usunieto": stara["tekst"]}


def _ustaw_kontrole(w: dict) -> dict:
    kod, wlaczona = w.get("kod"), bool(w.get("wlaczona"))
    if kod not in klauzule.KONSTRUKCJA:
        raise ValueError("Nieznana kontrola.")
    byla = kod not in zasady.wczytaj().get("wbudowane_wylaczone", [])
    zasady.ustaw_wbudowana(kod, wlaczona)
    _zapisz_zmiane(f"kontrola {kod}: {'wlaczona' if wlaczona else 'wylaczona'}",
                   {"rodzaj": "kontrola", "kod": kod, "wlaczona": byla})
    return {"kontrola": klauzule.KONSTRUKCJA[kod], "wlaczona": wlaczona}


def _cofnij(_: dict) -> dict:
    dane = magazyn.wczytaj_plik_kancelarii(PLIK, _domyslne())
    if not dane.get("zmiany"):
        return {"cofnieto": None, "uwaga": "Nie ma zmian do cofnięcia."}
    ostatnia = dane["zmiany"][-1]
    c = ostatnia["cofniecie"]
    if c["rodzaj"] == "ustawienie":
        ustawienia_kancelarii.zapisz({c["klucz"]: c["wartosc"]})
    elif c["rodzaj"] == "usun_zasade":
        zasady.usun(c["id"])
    elif c["rodzaj"] == "przywroc_zastapiona":
        zasady.usun(c["id"])
        zasady.dodaj(c["zdanie"], {"poziom": c["poziom"]}, zrodlo="asystent")
    elif c["rodzaj"] == "zmien_zasade":
        zasady.zmien(c["id"], c["zmiany"])
    elif c["rodzaj"] == "przywroc_zasade":
        zasady.dodaj(c["zdanie"], {"poziom": c["poziom"], "wlaczona": c["wlaczona"], "zakres": c.get("zakres")},
                     zrodlo="asystent")
    elif c["rodzaj"] == "kontrola":
        zasady.ustaw_wbudowana(c["kod"], c["wlaczona"])

    def zdejmij(d: dict) -> None:
        if d.get("zmiany") and d["zmiany"][-1] == ostatnia:
            d["zmiany"].pop()
    magazyn.zmien_plik_kancelarii(PLIK, zdejmij, _domyslne())
    return {"cofnieto": ostatnia["opis"]}


def _zglos(w: dict) -> dict:
    granica = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    dane = magazyn.wczytaj_plik_kancelarii(PLIK, _domyslne())
    if sum(1 for p in dane.get("prosby", []) if p["czas"] >= granica) >= MAX_PROSB_NA_DOBE:
        return {"przyjeto": False, "uwaga": f"Limit {MAX_PROSB_NA_DOBE} próśb na dobę - spróbuj jutro."}
    wynik = samonaprawa.zglos_prosbe(str(w.get("opis", "")))

    def zapisz(d: dict) -> None:
        d.setdefault("prosby", []).append({"czas": datetime.now().isoformat(timespec="seconds"),
                                           "odcisk": wynik["odcisk"], "opis": wynik["tekst"],
                                           "wyslano": wynik["wyslano"]})
        d["prosby"] = d["prosby"][-MAX_DZIENNIKA:]
    magazyn.zmien_plik_kancelarii(PLIK, zapisz, _domyslne())
    return {"przyjeto": True, "numer": wynik["odcisk"],
            "co_dalej": ("Przekazane do automatycznej naprawy "
                         + ("od razu" if wynik["wyslano"] else "(przegląd co 30 minut)")
                         + ": zmiana pojawi się zwykle w ciągu godziny jako ustawienie tej kancelarii "
                         "albo trafi do zespołu notarai do decyzji. Postęp i szacowany czas widać "
                         "na bieżąco pod rozmową z asystentem.")}


# ---------------------------------------------------------------------------
# Postep prosb (co widzi notariusz)
# ---------------------------------------------------------------------------
# Etap -> (opis dla notariusza, typowy czas etapu w minutach). Kolejnosc = postep.
ETAPY = [
    ("w_kolejce", "Czeka na podjęcie", 0),
    ("przyjete", "Przyjęte - agent zaczyna pracę", 1),
    ("analiza", "Agent szuka przyczyny i przygotowuje zmianę", 12),
    ("kontrola", "Testy i kontrola bezpieczeństwa zmiany", 5),
    ("recenzja", "Niezależne sprawdzenie zmiany", 4),
    ("wdrazanie", "Wdrażanie na serwer", 8),
    ("obserwacja", "Gotowe - zmiana już działa, sprawdzam jeszcze, czy wszystko w porządku", 0),
    ("gotowe", "Gotowe - zmiana działa", 0),
]
KONCOWE = {
    "gotowe": "Gotowe - zmiana działa",
    "do_decyzji": "Czeka na zespół notarai",
    "cofniete": "Wycofane - zespół notarai to sprawdzi",
}
PRZEGLAD_CO_MIN = 60   # bez tokenu: przeglad zastepczy co godzine


def _parametr_postepu(odcisk: str) -> dict | None:
    try:
        import boto3
        import config
        odp = boto3.client("ssm", region_name=config.REGION).get_parameter(Name=f"/notarai/samonaprawa/{odcisk}")
        return json.loads(odp["Parameter"]["Value"])
    except Exception:  # noqa: BLE001 - brak parametru = jeszcze w kolejce
        return None


def _minuty_od(czas_iso: str, teraz: datetime) -> float:
    """Minuty od chwili zapisanej w ISO; czas bez strefy traktujemy jako UTC (kontener)."""
    try:
        od = datetime.fromisoformat(str(czas_iso).replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if od.tzinfo is None:
        od = od.replace(tzinfo=timezone.utc)
    return max(0.0, (teraz - od).total_seconds() / 60)


def postep_prosby(prosba: dict, stan: dict | None, teraz: datetime | None = None) -> dict:
    """Pasek postepu i szacowany czas do wdrozenia jednej prosby."""
    teraz = teraz or datetime.now(timezone.utc)
    kolejnosc = [e for e, _, _ in ETAPY]
    etap = (stan or {}).get("etap") or "w_kolejce"
    wynik = {"numer": prosba["odcisk"], "opis": prosba.get("opis", "")[:300], "zgloszono": prosba["czas"],
             "etap": etap, "uwaga": (stan or {}).get("opis", "")}
    if etap in KONCOWE and etap != "gotowe":
        return wynik | {"etykieta": KONCOWE[etap], "procent": 100, "pozostalo_min": None, "zakonczona": True}
    if etap not in kolejnosc:
        etap = "w_kolejce"
        wynik["etap"] = etap
    i = kolejnosc.index(etap)
    if etap in ("obserwacja", "gotowe"):
        return wynik | {"etykieta": ETAPY[i][1], "procent": 100, "pozostalo_min": 0, "zakonczona": etap == "gotowe"}
    w_etapie = _minuty_od(stan["czas"] if stan else prosba["czas"], teraz)
    if etap == "w_kolejce":
        biezacy = 1 if prosba.get("wyslano") else max(1, PRZEGLAD_CO_MIN - w_etapie)
        zrobione = 0.0
    else:
        biezacy = max(1, ETAPY[i][2] - w_etapie)
        zrobione = sum(m for _, _, m in ETAPY[1:i]) + max(0, ETAPY[i][2] - biezacy)
    calosc = sum(m for _, _, m in ETAPY[1:]) or 1
    return wynik | {"etykieta": ETAPY[i][1], "procent": int(min(95, 5 + 90 * zrobione / calosc)),
                    "pozostalo_min": int(round(biezacy + sum(m for _, _, m in ETAPY[i + 1:]))),
                    "zakonczona": False}


def prosby_z_postepem(limit: int = 10) -> list[dict]:
    dane = magazyn.wczytaj_plik_kancelarii(PLIK, _domyslne())
    prosby = list(reversed(dane.get("prosby", [])))[:limit]
    return [postep_prosby(p, _parametr_postepu(p["odcisk"])) for p in prosby]


_ZMIENIAJACE = {"zmien_ustawienie": _zmien_ustawienie, "dodaj_zasade": _dodaj_zasade,
                "zmien_zasade": _zmien_zasade, "usun_zasade": _usun_zasade,
                "ustaw_kontrole": _ustaw_kontrole, "cofnij_ostatnia_zmiane": _cofnij}


def wykonaj(nazwa: str, wejscie: dict, moze_zmieniac: bool) -> dict:
    """Wynik narzedzia dla modelu. Bledy wracaja jako {"blad": ...}, nie wyjatki."""
    try:
        if nazwa == "pokaz_ustawienia":
            return _ustawienia_teraz()
        if nazwa == "zglos_zmiane_programu":
            return _zglos(wejscie)
        if nazwa in _ZMIENIAJACE:
            if not moze_zmieniac:
                return {"blad": "brak_uprawnien",
                        "uwaga": "Zmiany wprowadza notariusz (właściciel kancelarii)."}
            return _ZMIENIAJACE[nazwa](wejscie)
        return {"blad": "nieznane narzędzie"}
    except (ValueError, KeyError) as e:
        return {"blad": str(e).strip("'")}
    except RuntimeError as e:   # kancelaria trzyma pliki u siebie
        return {"blad": str(e)}


# ---------------------------------------------------------------------------
# Rozmowa
# ---------------------------------------------------------------------------
def _tury(historia: list[dict], wiadomosc: str) -> list[dict]:
    tury: list[dict] = []
    for t in historia[-MAX_HISTORII:]:
        rola = "assistant" if t.get("rola") == "asystent" else "user"
        tresc = str(t.get("tresc", "")).strip()
        if not tresc:
            continue
        if tury and tury[-1]["role"] == rola:
            tury[-1]["content"][0]["text"] += "\n\n" + tresc
        else:
            tury.append({"role": rola, "content": [{"text": tresc}]})
    while tury and tury[0]["role"] != "user":
        tury.pop(0)
    if tury and tury[-1]["role"] == "user":
        tury[-1]["content"][0]["text"] += "\n\n" + wiadomosc
    else:
        tury.append({"role": "user", "content": [{"text": wiadomosc}]})
    return tury


def rozmawiaj(historia: list[dict], wiadomosc: str, moze_zmieniac: bool) -> dict:
    """Tura rozmowy: {"odpowiedz", "zmiany": [{"narzedzie", "wynik"}]}."""
    system = SYSTEM + ("" if moze_zmieniac else
                       "\nUWAGA: rozmawiasz z pracownikiem bez uprawnień do zmian - możesz "
                       "wyjaśniać i zgłaszać prośby, ale nie zmieniać ustawień.")
    tury = _tury(historia, wiadomosc.strip())
    zmiany: list[dict] = []
    for _ in range(MAX_KROKOW):
        wynik = bedrock.tura_z_narzedziami(system, tury, NARZEDZIA)
        tury.append(wynik["wiadomosc"])
        uzycia = [b["toolUse"] for b in wynik["wiadomosc"].get("content", []) if "toolUse" in b]
        if wynik["powod"] != "tool_use" or not uzycia:
            tekst = "".join(b.get("text", "") for b in wynik["wiadomosc"].get("content", [])).strip()
            return {"odpowiedz": tekst or "Gotowe.", "zmiany": zmiany}
        odpowiedzi = []
        for u in uzycia:
            rezultat = wykonaj(u["name"], u.get("input") or {}, moze_zmieniac)
            log.info("asystent kancelarii: narzedzie %s -> %s", u["name"],
                     "blad" if "blad" in rezultat else "ok")
            if u["name"] != "pokaz_ustawienia" and "blad" not in rezultat:
                zmiany.append({"narzedzie": u["name"], "wynik": rezultat})
            odpowiedzi.append({"toolResult": {"toolUseId": u["toolUseId"],
                                              "content": [{"json": json.loads(json.dumps(rezultat, default=str))}]}})
        tury.append({"role": "user", "content": odpowiedzi})
    return {"odpowiedz": "Zrobiłem, co się dało - sprawdź zmiany poniżej.", "zmiany": zmiany}
