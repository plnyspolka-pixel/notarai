"""Komunikacja z Amazon Bedrock.

Trzy przebiegi:
  1. transkrypcja - kazda strona osobno, w wysokiej rozdzielczosci -> tekst
  2. ekstrakcja   - transkrypcje pogrupowane w dokumenty -> dane w JSON
  3. generowanie  - wzor + zwalidowane dane -> projekt dokumentu

Strony czytamy pojedynczo, bo jedno zadanie z dziesiatkami obrazow zmusza
do ich pomniejszania (drobny druk tabel staje sie nieczytelny), a model
zajety naraz czytaniem i wnioskowaniem gubi przypisanie wierszy tabel
i stron do dokumentow. Miedzy ekstrakcja a generowaniem wchodzi walidacja
i czlowiek.

UWAGA: nie logujemy tresci promptow ani odpowiedzi. Ani do pliku, ani na konsole.
"""
import contextvars
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

import config
import dokumenty
import prompty
import tokenomia

log = logging.getLogger("pieczapp.bedrock")

_ustawienia = Config(
    region_name=config.REGION,
    # Duza sprawa to kilkaset wywolan w krotkim czasie - adaptacyjne
    # ponowienia zwalniaja tempo zamiast przerywac odczyt przy dlawieniu.
    retries={"max_attempts": 10, "mode": "adaptive"},
    # Odpowiedz przychodzi strumieniem, ale przy dlugim mysleniu przerwy
    # miedzy porcjami bywaja dlugie.
    read_timeout=3600,
    connect_timeout=15,
    max_pool_connections=max(10, config.ROWNOLEGLE * 2),
)

_blokada = threading.Lock()
_klient_bedrock = None

# Odpowiedz dla paczki stron nie potrzebuje 128 tys. tokenow, a tyle
# rezerwowaloby limit przepustowosci konta przy kazdym rownoleglym wywolaniu.
MAX_WYJSCIE_PACZKA = 64000

# Obrazow w jednym zadaniu. Powyzej 20 Bedrock wymaga mniejszych obrazow
# (najwyzej 2000 px), a my chcemy pelnej rozdzielczosci pasow.
MAX_OBRAZOW = 20

# Modele, ktore przyjmuja myslenie adaptacyjne i parametr wysilku (4.6+).
_ADAPTACYJNE = re.compile(r"claude-(opus|sonnet|haiku)-(4-[6-9]|5)|claude-fable-5")
# Limit odpowiedzi w rozmowie o sprawie i w podsumowaniu ustalen.
MAX_TOKENOW_ROZMOWY = config.MAX_WYJSCIE


def _klient():
    # Bez nazwy profilu boto3 bierze poswiadczenia ze standardowego lancucha:
    # [default] z ~/.aws na stanowisku, rola zadania ECS w chmurze.
    global _klient_bedrock
    with _blokada:
        if _klient_bedrock is None:
            if config.PROFIL_AWS:
                sesja = boto3.Session(profile_name=config.PROFIL_AWS, region_name=config.REGION)
            else:
                sesja = boto3.Session(region_name=config.REGION)
            _klient_bedrock = sesja.client("bedrock-runtime", config=_ustawienia)
        return _klient_bedrock


class Przeciazenie(RuntimeError):
    """Bedrock odrzucil zadanie przez limit zapytan, mimo ponowien."""


class NiepoprawnyJson(ValueError):
    """Odpowiedz modelu nie daje sie odczytac jako JSON, nawet po naprawie."""


# Ile razy probujemy zestawienia danych (blad JSON albo limit zapytan).
PROB_ZESTAWIENIA = 3


# Kody, ktore Bedrock zwraca przy wyczerpanym limicie zapytan. Porownujemy
# malymi literami: przed strumieniem przychodzi "ThrottlingException", a juz
# w trakcie strumienia - "throttlingException" (EventStreamError).
_PRZECIAZENIE = {"throttlingexception", "toomanyrequestsexception",
                 "servicequotaexceededexception"}

# Bledy przejsciowe po stronie AWS: ponowienie zwykle pomaga, przerwanie
# odczytu po kilkudziesieciu minutach pracy - nie.
_PRZEJSCIOWE = {"serviceunavailableexception", "internalserverexception",
                "modeltimeoutexception", "modelerrorexception", "modelnotreadyexception",
                "modelstreamerrorexception"}
# Bledy polaczenia botocore (nie ClientError), rowniez przejsciowe.
_PRZEJSCIOWE_POLACZENIA = ("ReadTimeoutError", "ConnectTimeoutError", "EndpointConnectionError",
                           "ConnectionClosedError", "ResponseStreamingError", "IncompleteReadError")
# Ile razy wywolujemy model przy bledzie przejsciowym i ile czekamy (s * nr proby).
PROB_WYWOLANIA = 3
PRZERWA_PONOWIENIA = 5


def _kod_bledu(blad: BaseException) -> str:
    """Kod bledu AWS malymi literami ("" dla wyjatkow spoza boto)."""
    odpowiedz = getattr(blad, "response", None) or {}
    return str(odpowiedz.get("Error", {}).get("Code", "")).lower()


def _tresc_bledu(blad: BaseException) -> str:
    odpowiedz = getattr(blad, "response", None) or {}
    return str(odpowiedz.get("Error", {}).get("Message", "") or blad)


def _przejsciowy(blad: BaseException) -> bool:
    if isinstance(blad, ClientError):
        return _kod_bledu(blad) in _PRZEJSCIOWE
    return isinstance(blad, BotoCoreError) and type(blad).__name__ in _PRZEJSCIOWE_POLACZENIA


def opis_bledu(blad: BaseException) -> str:
    """Komunikat dla notariusza zamiast surowego tekstu wyjatku boto.

    Boto mowi po angielsku, nazwa operacji i kodem; notariusz ma wiedziec, co
    zrobic: poczekac, podzielic sprawe, poprawic skan albo zglosic blad do
    notarai. Bez tresci sprawy - tylko rodzaj bledu i ustawienia modelu.
    """
    if isinstance(blad, (Przeciazenie, ValueError)):
        return str(blad)   # nasze wyjatki sa juz po polsku
    kod = _kod_bledu(blad)
    tresc = _tresc_bledu(blad)
    plaska = tresc.lower()
    if kod == "validationexception":
        if "too long" in plaska or "input length" in plaska or ("token" in plaska and "exceed" in plaska):
            return ("Sprawa jest za duża na jedno zapytanie do modelu. Podziel skany na mniejsze "
                    "sprawy (mniej stron naraz) i spróbuj ponownie.")
        if "image" in plaska:
            return ("Jeden ze skanów ma obraz, którego model nie przyjął (za duży albo w nieobsługiwanym "
                    "formacie). Zapisz go jako PDF lub JPG i spróbuj ponownie.")
        if "model" in plaska and any(w in plaska for w in ("identifier", "not supported", "isn't supported",
                                                            "on-demand", "inference profile", "doesn't support")):
            return (f"Model {config.MODEL} nie jest dostępny w tej postaci na koncie AWS notarai. "
                    "To ustawienie po stronie notarai, nie Twoje - zgłoś błąd, sprawa jest zapisana.")
        return (f"Model odrzucił zapytanie ({tresc.strip() or 'ValidationException'}). "
                "Jeśli błąd się powtarza, zgłoś go do notarai.")
    if kod in {"accessdeniedexception", "resourcenotfoundexception"}:
        return (f"Konto AWS notarai nie ma dostępu do modelu {config.MODEL} w regionie {config.REGION}. "
                "To ustawienie po stronie notarai, nie Twoje - zgłoś błąd, sprawa jest zapisana.")
    if kod in {"expiredtokenexception", "unrecognizedclientexception", "invalidsignatureexception"} \
            or type(blad).__name__ in ("NoCredentialsError", "PartialCredentialsError"):
        return ("Aplikacja straciła poświadczenia do AWS. Spróbuj ponownie za chwilę; jeśli błąd "
                "się powtarza, zgłoś go do notarai.")
    if _przejsciowy(blad):
        return ("Model Bedrock chwilowo nie odpowiada (zakłócenie po stronie AWS). Odczekaj kilka "
                "minut i spróbuj ponownie - sprawa i skany są zapisane.")
    return (f"Błąd modelu ({kod or type(blad).__name__}). Spróbuj ponownie; jeśli błąd się "
            "powtarza, zgłoś go do notarai.")


def _parametry_modelu(max_tokenow: int, myslenie: bool, wysilek: str | None = None,
                      model: str | None = None) -> tuple[dict, dict]:
    """inferenceConfig i additionalModelRequestFields dla wskazanego modelu."""
    model = model or config.MODEL
    ustawienia: dict = {"maxTokens": max_tokenow}
    dodatkowe: dict = {}
    adaptacyjny = bool(_ADAPTACYJNE.search(model))
    if myslenie:
        # Przy mysleniu temperatura musi zostac domyslna.
        if adaptacyjny:
            dodatkowe["thinking"] = {"type": "adaptive"}
            dodatkowe["output_config"] = {"effort": wysilek or config.WYSILEK}
        else:
            dodatkowe["thinking"] = {"type": "enabled", "budget_tokens": max(1024, max_tokenow // 2)}
    elif config.przyjmuje_temperature(model):
        ustawienia["temperature"] = 0
    if adaptacyjny:
        # Kontekst 1M tokenow - koncowe zestawienie duzej sprawy go potrzebuje.
        dodatkowe["anthropic_beta"] = ["context-1m-2025-08-07"]
    return ustawienia, dodatkowe


def _rozmowa(
    system: str, tresc: list[dict], max_tokenow: int | None = None,
    historia: list[dict] | None = None, myslenie: bool | None = None,
    wysilek: str | None = None, model: str | None = None,
) -> str:
    """Jedno wywolanie modelu. `historia` to wczesniejsze tury [{"role","content"}].

    Odpowiedz odbieramy strumieniem: dlugie odpowiedzi z mysleniem potrafia
    trwac dluzej, niz wytrzymuje zwykle wywolanie. Blad przejsciowy AWS
    (takze w trakcie strumienia, czego botocore sam nie ponawia) powtarzamy
    do PROB_WYWOLANIA razy, zanim przerwiemy prace.
    """
    for proba in range(1, PROB_WYWOLANIA + 1):
        try:
            return _rozmowa_raz(system, tresc, max_tokenow, historia, myslenie, wysilek, model)
        except Przeciazenie:
            raise
        except (ClientError, BotoCoreError) as blad:
            if not _przejsciowy(blad) or proba == PROB_WYWOLANIA:
                raise
            log.warning("Bedrock: blad przejsciowy %s, ponawiam (%d)",
                        _kod_bledu(blad) or type(blad).__name__, proba)
            time.sleep(PRZERWA_PONOWIENIA * proba)
    raise RuntimeError("nieosiagalne")   # pragma: no cover


def _rozmowa_raz(system, tresc, max_tokenow, historia, myslenie, wysilek, model) -> str:
    max_tokenow = max_tokenow or config.MAX_WYJSCIE
    myslenie = config.MYSLENIE if myslenie is None else myslenie
    model = model or config.MODEL
    ustawienia, dodatkowe = _parametry_modelu(max_tokenow, myslenie, wysilek, model)
    wiadomosci = list(historia or []) + [{"role": "user", "content": tresc}]
    zadanie = {
        "modelId": model,
        "system": [{"text": system}],
        "messages": wiadomosci,
        "inferenceConfig": ustawienia,
    }
    if dodatkowe:
        zadanie["additionalModelRequestFields"] = dodatkowe
    czesci: list[str] = []
    powod = None
    uzycie: dict = {}
    try:
        odpowiedz = _klient().converse_stream(**zadanie)
        for zdarzenie in odpowiedz["stream"]:
            if "contentBlockDelta" in zdarzenie:
                # tylko tekst odpowiedzi; bloki myslenia (reasoningContent) pomijamy
                czesci.append(zdarzenie["contentBlockDelta"]["delta"].get("text", ""))
            elif "messageStop" in zdarzenie:
                powod = zdarzenie["messageStop"].get("stopReason")
            elif "metadata" in zdarzenie:
                uzycie = zdarzenie["metadata"].get("usage", {})
    except ClientError as blad:
        # Ponawianie zrobil juz klient boto3. Jesli mimo to nie przeszlo,
        # limit jest wyczerpany na dluzej - mowimy o tym wprost, zamiast
        # pokazywac notariuszowi nazwe wyjatku.
        if _kod_bledu(blad) in _PRZECIAZENIE:
            log.warning("Bedrock odrzucil zadanie z powodu limitu zapytan")
            raise Przeciazenie(
                "Model jest chwilowo przeciazony (limit zapytan na koncie AWS). "
                "Odczekaj minute i sprobuj ponownie."
            ) from blad
        raise
    log.info(
        "wywolanie modelu: wejscie=%s wyjscie=%s",
        uzycie.get("inputTokens"),
        uzycie.get("outputTokens"),
    )
    # Koszt wywolania do licznika biezacej akcji (tokenomia) - same liczby tokenow.
    tokenomia.dolicz(model, uzycie)
    wynik = "".join(czesci).strip()

    if powod == "max_tokens":
        log.error("odpowiedz modelu ucieta przy limicie %d tokenow", max_tokenow)
        raise ValueError(
            f"Odpowiedz modelu zostala ucieta (limit {max_tokenow} tokenow). "
            "Podziel sprawe na mniejsze czesci."
        )
    return wynik


# ---------------------------------------------------------------- transkrypcja

def transkrybuj_paczke(strony: list[dict], wysilek: str | None = None) -> list[dict]:
    """Przebieg 1 dla kilku kolejnych stron w jednym wywolaniu.

    Kazda strona idzie jako obraz calej strony plus pasy w pelnej
    rozdzielczosci. Strony sa oznaczone "STRONA n" - po tych znacznikach
    rozdzielamy odpowiedz. Strony, ktorych model nie oddal, wracaja z kluczem
    "brak", zeby wywolujacy przeczytal je jeszcze raz pojedynczo.
    """
    obrazy = [dokumenty.obrazy_strony(s) for s in strony]
    if len(strony) > 1 and sum(1 + len(o["pasy"]) for o in obrazy) > MAX_OBRAZOW:
        polowa = len(strony) // 2  # wyjatkowo dlugie strony - dzielimy paczke
        return (transkrybuj_paczke(strony[:polowa], wysilek)
                + transkrybuj_paczke(strony[polowa:], wysilek))

    tresc: list[dict] = []
    for nr, (strona, o) in enumerate(zip(strony, obrazy), start=1):
        tresc.append({"text": f"=== STRONA {nr}: plik {strona['dokument']}, strona {strona['strona']} === "
                              "Obraz calej strony (do orientacji w ukladzie)."})
        tresc.append({"image": {"format": "png", "source": {"bytes": o["calosc"]}}})
        for i, pas in enumerate(o["pasy"], start=1):
            tresc.append({"text": f"STRONA {nr}, pas {i} z {len(o['pasy'])}, liczac od gory, "
                                  "w wyzszej rozdzielczosci (pasy zachodza na siebie)."})
            tresc.append({"image": {"format": "png", "source": {"bytes": pas}}})
        if o["tekst"]:
            tresc.append({"text": f"STRONA {nr} - WARSTWA TEKSTOWA PDF (dokladne znaki, "
                                  "kolejnosc moze byc pomieszana):\n" + o["tekst"]})
    tresc.append({"text": prompty.polecenie_transkrypcji(len(strony))})

    surowa = _rozmowa(prompty.TRANSKRYPCJA, tresc, max_tokenow=MAX_WYJSCIE_PACZKA, wysilek=wysilek)
    czesci = _podziel_na_strony(surowa, len(strony))
    wyniki = []
    for nr, (strona, o) in enumerate(zip(strony, obrazy), start=1):
        if nr in czesci:
            wynik = _naglowek_transkrypcji(czesci[nr])
        else:
            wynik = {"brak": True}
        wynik.update({"dokument": strona["dokument"], "strona": strona["strona"],
                      "pasow": len(o["pasy"]), "warstwa_tekstowa": bool(o["tekst"])})
        wyniki.append(wynik)
    return wyniki


_ZNACZNIK_STRONY = re.compile(r"^=+\s*STRONA\s+(\d+)\b[^\n]*$", re.MULTILINE)


def _podziel_na_strony(surowa: str, ile: int) -> dict[int, str]:
    """{nr strony w paczce: jej czesc odpowiedzi}."""
    znaczniki = list(_ZNACZNIK_STRONY.finditer(surowa))
    if not znaczniki:
        return {1: surowa} if ile == 1 else {}
    czesci = {}
    for i, z in enumerate(znaczniki):
        koniec = znaczniki[i + 1].start() if i + 1 < len(znaczniki) else len(surowa)
        nr = int(z.group(1))
        if 1 <= nr <= ile:
            czesci[nr] = surowa[z.end():koniec].strip()
    return czesci


def _naglowek_transkrypcji(surowa: str) -> dict:
    """Rozdziela naglowek (TYP:, NR_KW: ...) od tresci strony."""
    naglowek, separator, tresc = surowa.partition("\n---")
    if not separator:  # model pominal separator - cala odpowiedz to tresc
        naglowek, tresc = "", surowa
    pola = {}
    for linia in naglowek.splitlines():
        klucz, dwukropek, wartosc = linia.partition(":")
        if dwukropek:
            pola[klucz.strip().upper()] = wartosc.strip()

    def puste(w: str | None) -> str | None:
        return None if not w or w.lower() in {"brak", "nie dotyczy", "-", "null"} else w

    return {
        "typ": puste(pola.get("TYP")) or "nieustalony",
        "nr_kw": puste(pola.get("NR_KW")),
        "poczatek": pola.get("POCZATEK_DOKUMENTU", "").lower().startswith("tak"),
        "numeracja": puste(pola.get("NUMERACJA")),
        "dzial": puste(pola.get("DZIAL")),
        "tresc": tresc.lstrip("-").strip(),
    }


def _paczki(strony: list[dict]) -> list[list[dict]]:
    """Kolejne strony tego samego pliku, po STRON_W_PACZCE."""
    paczki: list[list[dict]] = []
    for s in strony:
        if (paczki and len(paczki[-1]) < config.STRON_W_PACZCE
                and paczki[-1][-1]["dokument"] == s["dokument"]):
            paczki[-1].append(s)
        else:
            paczki.append([s])
    return paczki


def transkrybuj_strony(strony: list[dict], postep=None, wysilek: str | None = None) -> list[dict]:
    """Przebieg 1 dla calej sprawy, paczki rownolegle. Kolejnosc stron zachowana.

    `postep(gotowe, wszystkie)` jest wolany po kazdej paczce (liczone w stronach).
    """
    paczki = _paczki(strony)
    wyniki: list[list[dict] | None] = [None] * len(paczki)
    gotowe = 0
    with ThreadPoolExecutor(max_workers=max(1, config.ROWNOLEGLE)) as pula:
        # Kopia kontekstu na kazde zadanie: watki puli nie dziedzicza go same,
        # a niesie on kancelarie i licznik kosztow akcji (tokenomia).
        zadania = {pula.submit(contextvars.copy_context().run, _transkrybuj_z_ponowieniem, p, wysilek): i
                   for i, p in enumerate(paczki)}
        for zadanie in as_completed(zadania):
            i = zadania[zadanie]
            wyniki[i] = zadanie.result()
            gotowe += len(paczki[i])
            if postep:
                postep(gotowe, len(strony))
    return [t for paczka in wyniki for t in paczka]  # type: ignore[union-attr]


def _transkrybuj_z_ponowieniem(paczka: list[dict], wysilek: str | None = None, proby: int = 3) -> list[dict]:
    """Ponowienia ponad te z botocore: dlawienie potrafi trwac dluzej niz
    jego wycofanie, a pojedyncza ucieta odpowiedz nie powinna psuc sprawy.
    Strony pominiete w odpowiedzi czytamy jeszcze raz, kazda osobno."""
    for proba in range(1, proby + 1):
        try:
            wyniki = transkrybuj_paczke(paczka, wysilek)
            break
        except Przeciazenie:
            # Limit zapytan na minute - przeczekanie go to jedyne, co pomaga.
            if proba == proby:
                raise
            log.warning("paczka od strony %d (%d str.): limit zapytan, czekam (%d)",
                        paczka[0]["strona"], len(paczka), proba)
            time.sleep(60 * proba)
        except ClientError as blad:
            kod = _kod_bledu(blad)
            if kod in {"validationexception", "accessdeniedexception"} or proba == proby:
                raise
            log.warning("paczka od strony %d (%d str.): %s, ponawiam (%d)",
                        paczka[0]["strona"], len(paczka), kod, proba)
        except ValueError:
            if proba == proby:
                raise
            log.warning("paczka od strony %d (%d str.): niepelna odpowiedz, ponawiam (%d)",
                        paczka[0]["strona"], len(paczka), proba)
    if len(paczka) > 1:
        for i, w in enumerate(wyniki):
            if w.get("brak"):
                log.warning("strona %d pominieta w paczce, czytam osobno", w["strona"])
                wyniki[i] = _transkrybuj_z_ponowieniem([paczka[i]], wysilek, proby)[0]
    for w in wyniki:
        if w.pop("brak", False):
            raise ValueError(f"Nie udalo sie przepisac strony {w['strona']} pliku {w['dokument']}.")
    return wyniki


_STRONA_PIERWSZA = re.compile(r"\b(strona|str\.?)\s*1\s*(z|/)\s*\d+", re.IGNORECASE)


def pogrupuj_dokumenty(transkrypcje: list[dict]) -> list[dict]:
    """Laczy kolejne strony w dokumenty i przenosi numer KW na strony bez niego.

    Nowy dokument zaczyna sie, gdy: zmienia sie plik, model rozpoznal pierwsza
    strone dokumentu, numeracja to "strona 1 z N" albo na stronie jest inny
    numer KW niz w biezacym dokumencie. Strona bez numeru KW nalezy do
    dokumentu, w ktorym lezy - wlasnie takie strony mylily wczesniej odczyt.
    """
    grupy: list[dict] = []
    for t in transkrypcje:
        biezacy = grupy[-1] if grupy else None
        nowy = (
            biezacy is None
            or t["dokument"] != biezacy["plik"]
            or t.get("poczatek")
            or bool(t.get("numeracja") and _STRONA_PIERWSZA.search(t["numeracja"]))
            or bool(t.get("nr_kw") and biezacy["nr_kw"]
                    and _kw(t["nr_kw"]) != _kw(biezacy["nr_kw"]))
        )
        if nowy:
            biezacy = {"nr": len(grupy) + 1, "plik": t["dokument"], "typ": t.get("typ"),
                       "nr_kw": t.get("nr_kw"), "strony": []}
            grupy.append(biezacy)
        elif t.get("nr_kw") and not biezacy["nr_kw"]:
            biezacy["nr_kw"] = t["nr_kw"]
        biezacy["strony"].append(t)
    return grupy


def _kw(numer: str) -> str:
    return re.sub(r"[^0-9A-Z]", "", numer.upper())


def _tresc_z_transkrypcji(transkrypcje: list[dict]) -> list[dict]:
    """Transkrypcje jako tekst dla ekstrakcji: mapa dokumentow, potem
    kazdy dokument w wyraznych granicach, z numerem KW przy kazdej stronie."""
    grupy = pogrupuj_dokumenty(transkrypcje)
    mapa = ["MAPA DOKUMENTOW SPRAWY (podzial ustalony z naglowkow stron):"]
    for g in grupy:
        zakres = f"{g['strony'][0]['strona']}-{g['strony'][-1]['strona']}"
        mapa.append(f"- Dokument {g['nr']}: {g['typ']}"
                    + (f", KW {g['nr_kw']}" if g["nr_kw"] else "")
                    + f" (plik {g['plik']}, strony {zakres})")
    czesci = ["\n".join(mapa)]
    for g in grupy:
        linie = [f"===== DOKUMENT {g['nr']}: {g['typ']}"
                 + (f" | KSIEGA WIECZYSTA {g['nr_kw']}" if g["nr_kw"] else "")
                 + f" | plik {g['plik']} ====="]
        for t in g["strony"]:
            kw = ""
            if g["nr_kw"]:
                kw = (f" | KW na stronie: {t['nr_kw']}" if t.get("nr_kw")
                      else f" | KW na stronie: brak, strona nalezy do KW {g['nr_kw']}")
            linie.append(f"--- [{t['dokument']}, strona {t['strona']}]"
                         + (f" | dzial: {t['dzial']}" if t.get("dzial") else "") + kw + " ---")
            linie.append(t.get("tresc", ""))
        linie.append(f"===== KONIEC DOKUMENTU {g['nr']} =====")
        czesci.append("\n".join(linie))
    return [{"text": c} for c in czesci]


# ---------------------------------------------------------------- ekstrakcja

def odczytaj_sprawe(
    strony: list[dict], pola: list[str], opis: str, legenda: dict | None = None,
    postep=None, wysilek: str | None = None,
) -> tuple[dict, list[dict]]:
    """Pelny odczyt: transkrypcja stron, potem zestawienie danych.

    Zwraca (odczyt, transkrypcje). `postep(etap, gotowe, wszystkie)`.
    `wysilek` (low/medium/high/max) zastepuje PIECZAPP_WYSILEK dla tej sprawy.
    """
    transkrypcje = transkrybuj_strony(
        strony, (lambda g, w: postep("transkrypcja", g, w)) if postep else None, wysilek
    )
    if postep:
        postep("zestawienie", 0, 1)
    return odczytaj_dane(transkrypcje, pola, opis, legenda, wysilek), transkrypcje


def odczytaj_dane(
    strony: list[dict], pola: list[str], opis: str, legenda: dict | None = None,
    wysilek: str | None = None,
) -> dict:
    """Przebieg 2 - zestawienie danych.

    `strony` to transkrypcje z transkrybuj_strony (klucz "tresc") albo,
    dla malych spraw i testow, strony z gotowym obrazem (klucz "png").
    """
    if strony and all("tresc" in s for s in strony):
        tresc = _tresc_z_transkrypcji(strony)
    else:
        tresc = []
        for strona in strony:
            tresc.append({"text": f"[{strona['dokument']}, strona {strona['strona']}]"})
            tresc.append({"image": {"format": "png", "source": {"bytes": strona["png"]}}})
    pola_pelne = list(pola) + [p for p in prompty.POLA_STALE if p not in pola]
    tresc.append({"text": prompty.polecenie_ekstrakcji(pola_pelne, opis, legenda)})

    # Zestawienie przychodzi po wielu minutach przepisywania stron. Blad na tym
    # etapie nie moze przekreslac calej pracy: transkrypcje sa w reku, wiec
    # zestawienie ponawiamy, zamiast konczyc sprawe bledem.
    for proba in range(1, PROB_ZESTAWIENIA + 1):
        try:
            surowa = _rozmowa(prompty.EKSTRAKCJA, tresc, wysilek=wysilek)
            wynik = _wczytaj_json_z_naprawa(surowa)
            break
        except Przeciazenie:
            if proba == PROB_ZESTAWIENIA:
                raise
            log.warning("zestawienie: limit zapytan, czekam (%d)", proba)
            time.sleep(60 * proba)
        except NiepoprawnyJson:
            if proba == PROB_ZESTAWIENIA:
                raise
            log.warning("zestawienie: niepoprawny JSON mimo naprawy, ponawiam (%d)", proba)
    wynik["pola"] = _przypisz_nazwy(wynik.get("pola", []), pola_pelne)
    return wynik


def _przypisz_nazwy(odczytane: list[dict], pola: list[str]) -> list[dict]:
    """Model zwraca numer pola; nazwa z listy jest rozstrzygajaca.

    Pola spoza listy (nr 0 albo brak nr) zachowuja nazwe od modelu,
    z prefiksem "+ ", zeby bylo widac, ze to dodatek modelu.
    """
    wynik = []
    for pole in odczytane:
        if not isinstance(pole, dict):
            continue
        nr = pole.get("nr")
        if isinstance(nr, int) and 1 <= nr <= len(pola):
            pole["nazwa"] = pola[nr - 1]
        else:
            nazwa = str(pole.get("nazwa", "")).strip()
            if nazwa in pola:
                pass
            elif not nazwa.startswith("+ "):
                pole["nazwa"] = f"+ {nazwa or 'bez nazwy'}"
        wynik.append(pole)
    return wynik


def sporzadz_projekt(
    wzor: str, dane: list[dict], opis: str, legenda: dict | None = None,
    rozmowa: list[dict] | None = None, personalizacja: str = "",
) -> str:
    """Przebieg 2 - wypelnienie wzoru zwalidowanymi danymi i ustaleniami z rozmowy.
    `personalizacja`: zasady i styl kancelarii (blok tekstu do polecenia)."""
    ustalenia = _ustalenia(rozmowa or [])
    tresc = [{"text": prompty.polecenie_generowania(wzor, dane, opis, legenda, ustalenia, personalizacja)}]
    return _oczysc_projekt(_rozmowa(prompty.GENEROWANIE, tresc))


def popraw_wg_zasad(tekst: str, naruszenia: list[dict]) -> str:
    """Jedna tura poprawki projektu: tylko miejsca naruszajace zasady kancelarii.
    Wynik i tak przechodzi ponowna kontrole w zasady.egzekwuj()."""
    if not config.POPRAWA_ZASAD:
        raise RuntimeError("poprawa przez model wylaczona")
    tresc = [{"text": prompty.polecenie_poprawy(tekst, naruszenia)}]
    return _oczysc_projekt(_rozmowa(prompty.POPRAWA_ZASAD, tresc))


def sprawdz_wytyczne(tekst: str, wytyczne: list[dict]) -> list[dict]:
    """Kontrola wytycznych, ktorych nie da sie sprawdzic regula. Zwraca
    [{"zasada", "fragment", "uwaga"}] - tylko dla znanych identyfikatorow."""
    if not wytyczne or not config.POPRAWA_ZASAD:
        return []
    tresc = [{"text": prompty.polecenie_kontroli(tekst, wytyczne)}]
    wynik = _wczytaj_json_z_naprawa(_rozmowa(prompty.KONTROLA_WYTYCZNYCH, tresc,
                                             max_tokenow=MAX_TOKENOW_ROZMOWY, myslenie=False))
    znane = {w["id"] for w in wytyczne}
    return [n for n in wynik.get("naruszenia", []) if isinstance(n, dict) and n.get("zasada") in znane]


def _ustalenia(rozmowa: list[dict]) -> str:
    """Blok ustalen do generowania: podsumowanie rozmowy, a gdy zawiedzie - zapis.

    Bez zadnej wypowiedzi notariusza nie ma czego podsumowywac (same pytania
    asystenta nie sa ustaleniami), wiec oszczedzamy wywolanie modelu.
    """
    if not any(w.get("rola") == "uzytkownik" for w in rozmowa):
        return ""
    try:
        podsumowanie = podsumuj_rozmowe(rozmowa)
    except (Przeciazenie, ValueError, ClientError) as blad:
        log.warning("podsumowanie rozmowy nieudane (%s), generowanie z pelnym zapisem",
                    type(blad).__name__)
        return prompty.ustalenia_z_rozmowy(rozmowa)
    if not podsumowanie:
        log.warning("puste podsumowanie rozmowy, generowanie z pelnym zapisem")
        return prompty.ustalenia_z_rozmowy(rozmowa)
    return prompty.ustalenia_podsumowane(podsumowanie)


def podsumuj_rozmowe(rozmowa: list[dict]) -> str:
    """Ostateczne ustalenia z rozmowy z notariuszem, punkt po punkcie."""
    tresc = [{"text": "ZAPIS ROZMOWY:\n" + prompty.zapis_rozmowy(rozmowa)
              + "\n\nWypisz ostateczne ustalenia."}]
    return _oczysc_projekt(_rozmowa(prompty.PODSUMOWANIE_ROZMOWY, tresc,
                                    max_tokenow=MAX_TOKENOW_ROZMOWY))


def wyciagnij_do_formularza(tekst_aktu: str, pola: list[dict]) -> list[dict]:
    """Dobiera wartosci pol formularza z tresci aktu.

    Zwraca liste wpisow: pole, wartosc (albo None), cytat uzasadniajacy,
    pewnosc i uwage. Cytat jest po to, zeby notariusz mogl sprawdzic zrodlo
    bez czytania calego aktu.
    """
    if not pola:
        return []
    tresc = [{"text": prompty.polecenie_formularza(tekst_aktu, pola)}]
    surowa = _rozmowa(prompty.FORMULARZ, tresc)
    wynik = _wczytaj_json_z_naprawa(surowa)

    nazwy_pol = {p["nazwa"] for p in pola}
    odpowiedzi = {}
    for wpis in wynik.get("pola", []):
        nazwa = str(wpis.get("pole", "")).strip()
        if nazwa in nazwy_pol:          # model bywa kreatywny w nazwach
            odpowiedzi[nazwa] = wpis

    braki = len(nazwy_pol) - len(odpowiedzi)
    log.info("formularz: pol=%d dopasowanych=%d bez odpowiedzi=%d",
             len(nazwy_pol), len(odpowiedzi), braki)

    return [
        {
            "pole": p["nazwa"],
            "wartosc": (odpowiedzi.get(p["nazwa"], {}).get("wartosc") or None),
            "cytat": str(odpowiedzi.get(p["nazwa"], {}).get("cytat", ""))[:200],
            "pewnosc": odpowiedzi.get(p["nazwa"], {}).get("pewnosc", "niska"),
            "uwaga": str(odpowiedzi.get(p["nazwa"], {}).get("uwaga", "")),
        }
        for p in pola
    ]


MAX_TOKENOW_USTALEN = 4000


def _klucz_pola(nazwa: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\"'„”“«»]", "", nazwa or "")).strip().lower()


def _dopasowania_pol(pola: list[str]) -> dict:
    """{klucz: pelna nazwa} - z pelnej nazwy, z czesci po „:” i z samego kodu („www”)."""
    wynik = {}
    for nazwa in pola:
        kod, _, opis = nazwa.partition(":")
        for wariant in (nazwa, opis, kod) if opis else (nazwa,):
            klucz = _klucz_pola(wariant)
            if klucz:
                wynik.setdefault(klucz, nazwa)
    return wynik


def wyciagnij_ustalenia(tekst: str, temat: str, pola: list[str]) -> list[dict]:
    """Ustalenia z jednej wiadomosci e-mail dot. pol sprawy (korespondencja.py).

    Bez myslenia i z krotka odpowiedzia: to wypisanie cytatow, nie wnioskowanie.
    Zrodlo (kto napisal, jaka ma role) dopisuje korespondencja.py, nie model.
    Wynik nigdy nie trafia do pol odczytu ani do projektu.
    """
    if not (tekst or "").strip():
        return []
    surowa = _rozmowa(prompty.USTALENIA_Z_KORESPONDENCJI,
                      [{"text": prompty.polecenie_ustalen(tekst, temat, pola)}],
                      max_tokenow=MAX_TOKENOW_USTALEN, myslenie=False)
    wynik = _wczytaj_json_z_naprawa(surowa)
    dopasowania = _dopasowania_pol(pola)
    ustalenia = []
    for u in wynik.get("ustalenia") or []:
        surowe = str(u.get("pole", "")).strip()
        wartosc = str(u.get("wartosc") or "").strip()
        if surowe.lower().startswith("inne:"):
            pole = "inne:" + surowe[5:]
        else:
            # Model bywa niedokladny: pelna nazwa, sama nazwa bez kodu albo sam kod.
            pole = dopasowania.get(_klucz_pola(surowe))
        if not wartosc or not pole:
            continue
        ustalenia.append({
            "pole": pole, "wartosc": wartosc[:200], "cytat": str(u.get("cytat", ""))[:200],
            "pewnosc": "wysoka" if u.get("pewnosc") == "wysoka" else "niska",
            "relacja": bool(u.get("relacja")), "czyje": str(u.get("czyje", ""))[:80],
        })
    log.info("ustalenia z korespondencji: zwrocono=%d przyjeto=%d",
             len(wynik.get("ustalenia") or []), len(ustalenia))
    return ustalenia


# Testy podmieniaja wyciagnij_ustalenia (conftest) - tu zostaje prawdziwa funkcja.
_wyciagnij_ustalenia = wyciagnij_ustalenia


def _oczysc_projekt(tekst: str) -> str:
    """Usuwa naglowki markdown i ogrodzenia kodu, ktore model czasem dopisuje."""
    linie = []
    for linia in tekst.split("\n"):
        if linia.lstrip().startswith("#") or linia.strip().startswith("```"):
            continue
        linie.append(linia)
    return "\n".join(linie).strip()


def _wczytaj_json(tekst: str) -> dict:
    oczyszczony = tekst.strip()
    if oczyszczony.startswith("```"):
        oczyszczony = oczyszczony.split("\n", 1)[1]
        oczyszczony = oczyszczony.rsplit("```", 1)[0]
    poczatek = oczyszczony.find("{")
    koniec = oczyszczony.rfind("}")
    if poczatek == -1 or koniec == -1:
        raise NiepoprawnyJson("Model nie zwrocil poprawnego JSON-a")
    fragment = oczyszczony[poczatek : koniec + 1]

    # strict=False: surowe znaki nowej linii i tabulatory w wartosciach
    # (przepisany tekst dokumentu) nie sa powodem, zeby odrzucac odpowiedz.
    try:
        return json.loads(fragment, strict=False)
    except json.JSONDecodeError as e:
        blad = e
        log.warning("Blad parsowania JSON z modelu. Pozycja: linia %d, kolumna %d", e.lineno, e.colno)

    # Typowe usterki modelu: przecinek przed } lub ] oraz cudzyslow z tresci
    # dokumentu (np. nazwa spolki "ABC") niezabezpieczony w wartosci.
    bez_przecinkow = re.sub(r',(\s*[}\]])', r'\1', fragment)
    for naprawiony in (bez_przecinkow, _napraw_cudzyslowy(bez_przecinkow)):
        if naprawiony == fragment:
            continue
        try:
            wynik = json.loads(naprawiony, strict=False)
            log.info("JSON z modelu naprawiony lokalnie")
            return wynik
        except json.JSONDecodeError:
            pass

    # Nie logujemy fragmentu odpowiedzi - moglby zawierac dane osobowe.
    log.error(
        "Niepoprawny JSON z modelu: %d znakow, %d linii, blad w linii %d",
        len(fragment), fragment.count("\n"), blad.lineno,
    )
    raise NiepoprawnyJson(
        f"Model zwrocil niepoprawny JSON ({blad.msg}, linia {blad.lineno}). "
        "Sprobuj ponownie."
    ) from blad


def _napraw_cudzyslowy(tekst: str) -> str:
    """Zabezpiecza cudzyslowy wewnatrz wartosci tekstowych.

    Cudzyslow w napisie uznajemy za zamykajacy, gdy dalej (po bialych znakach)
    stoi , : } ] albo koniec tekstu. Kazdy inny to znak z tresci dokumentu.
    """
    wynik: list[str] = []
    w_napisie = False
    i = 0
    while i < len(tekst):
        znak = tekst[i]
        if w_napisie and znak == "\\":
            wynik.append(tekst[i:i + 2])
            i += 2
            continue
        if znak == '"':
            if not w_napisie:
                w_napisie = True
            else:
                j = i + 1
                while j < len(tekst) and tekst[j] in " \t\r\n":
                    j += 1
                if j == len(tekst) or tekst[j] in ",:}]":
                    w_napisie = False
                else:
                    wynik.append('\\"')
                    i += 1
                    continue
        wynik.append(znak)
        i += 1
    return "".join(wynik)


def _wczytaj_json_z_naprawa(tekst: str) -> dict:
    """_wczytaj_json, a gdy zawiedzie - poprawka skladni przez model.

    Krotkie wywolanie bez myslenia i bez skanow: model dostaje tylko wlasna
    odpowiedz i ma poprawic skladnie, nie tresc. Kosztuje ulamek ponownego
    zestawienia, ktore przy duzej sprawie trwa kilkanascie minut.
    """
    try:
        return _wczytaj_json(tekst)
    except NiepoprawnyJson as blad:
        log.warning("prosze model o poprawienie skladni JSON (%d znakow)", len(tekst))
        tresc = [{"text": f"BLAD PARSERA: {blad}\n\nJSON DO POPRAWIENIA:\n{tekst}"}]
        try:
            poprawiony = _rozmowa(prompty.NAPRAWA_JSON, tresc,
                                  max_tokenow=min(64000, len(tekst) // 2 + 4000), myslenie=False)
        except ValueError:  # ucieta poprawka - zostaje bledem pierwotnym
            raise blad from None
        return _wczytaj_json(poprawiony)


def rozmawiaj(kontekst: str, historia: list[dict], wiadomosc: str) -> str:
    """Tura rozmowy o sprawie. `historia` to lista {"rola": uzytkownik|asystent, "tresc"}.

    Kontekst sprawy (odczytane dane) wchodzi jako pierwsza tura uzytkownika,
    zeby nie powielac go w kazdej wiadomosci.
    """
    tury = [
        {"role": "user", "content": [{"text": kontekst + "\n\n" + prompty.PIERWSZE_PYTANIA}]},
    ]
    for w in historia:
        rola = "user" if w["rola"] == "uzytkownik" else "assistant"
        if tury[-1]["role"] == rola:  # Bedrock wymaga naprzemiennych rol
            tury[-1]["content"].append({"text": w["tresc"]})
        else:
            tury.append({"role": rola, "content": [{"text": w["tresc"]}]})
    if wiadomosc is None:
        # pierwsza tura: pytania wstepne - kontekst juz jest ostatnia tura uzytkownika
        ostatnia = tury.pop()
        return _rozmowa(prompty.ROZMOWA, ostatnia["content"], max_tokenow=MAX_TOKENOW_ROZMOWY, historia=tury)
    if tury[-1]["role"] == "user":
        tury[-1]["content"].append({"text": wiadomosc})
        ostatnia = tury.pop()
        return _rozmowa(prompty.ROZMOWA, ostatnia["content"], max_tokenow=MAX_TOKENOW_ROZMOWY, historia=tury)
    return _rozmowa(prompty.ROZMOWA, [{"text": wiadomosc}], max_tokenow=MAX_TOKENOW_ROZMOWY, historia=tury)


# Odpowiedz kalkulatora to krotki JSON z parametrami; kwoty liczy taksa.py.
MAX_TOKENOW_KALKULATORA = 1500


def rozmowa_kalkulatora(system: str, tury: list[dict], wiadomosc: str, model: str | None = None) -> str:
    """Tura rozmowy klienta kancelarii z kalkulatorem taksy (kalkulator.py).

    Bez myslenia: dobor parametrow jest prosty, a klient czeka na stronie.
    `tury` to gotowe, naprzemienne tury Bedrock [{"role","content"}].
    `model` to osobny profil kalkulatora, zeby publiczny czat nie zjadal
    limitu zapytan modelu, ktory czyta skany kancelarii.
    """
    return _rozmowa(system, [{"text": wiadomosc}], max_tokenow=MAX_TOKENOW_KALKULATORA,
                    historia=tury, myslenie=False, model=model)


def nastepny_krok(cel: str, stan: dict, kroki: list[dict]) -> dict:
    """Jedna decyzja agenta prowadzacego przegladarke notariusza.

    Model stoi po stronie serwera, bo tu jest dostep do Bedrocka. Komputer
    notariusza go nie ma i miec nie musi - dostaje gotowa czynnosc do
    wykonania, a nie klucze do modelu.
    """
    from pomocnik import klikamy

    tresc = klikamy.polecenie_dla_modelu(cel, stan, kroki)
    odpowiedz = _rozmowa(prompty.KLIKAMY, [{"text": tresc}], max_tokenow=700, myslenie=False)
    return klikamy.odpowiedz_na_slownik(odpowiedz)
