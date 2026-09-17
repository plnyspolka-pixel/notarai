"""Komunikacja z Amazon Bedrock.

Dwa osobne przebiegi:
  1. ekstrakcja  - skany  -> dane w JSON
  2. generowanie - wzor + zwalidowane dane -> projekt dokumentu

Rozdzielenie jest celowe. Miedzy przebiegami wchodzi walidacja i czlowiek.

UWAGA: nie logujemy tresci promptow ani odpowiedzi. Ani do pliku, ani na konsole.
"""
import json
import logging

import boto3
from botocore.config import Config

import config
import prompty

log = logging.getLogger("pieczapp.bedrock")

_ustawienia = Config(
    region_name=config.REGION,
    retries={"max_attempts": 3, "mode": "standard"},
    read_timeout=300,
    connect_timeout=15,
)


def _klient():
    # Bez nazwy profilu boto3 bierze poswiadczenia ze standardowego lancucha:
    # [default] z ~/.aws na stanowisku, rola instancji w chmurze.
    if config.PROFIL_AWS:
        sesja = boto3.Session(profile_name=config.PROFIL_AWS, region_name=config.REGION)
    else:
        sesja = boto3.Session(region_name=config.REGION)
    return sesja.client("bedrock-runtime", config=_ustawienia)


def _rozmowa(system: str, tresc: list[dict], max_tokenow: int, historia: list[dict] | None = None) -> str:
    """Jedno wywolanie modelu. `historia` to wczesniejsze tury [{"role","content"}]."""
    wiadomosci = list(historia or []) + [{"role": "user", "content": tresc}]
    odpowiedz = _klient().converse(
        modelId=config.MODEL,
        system=[{"text": system}],
        messages=wiadomosci,
        inferenceConfig={"maxTokens": max_tokenow, "temperature": 0},
    )
    uzycie = odpowiedz.get("usage", {})
    log.info(
        "wywolanie modelu: wejscie=%s wyjscie=%s",
        uzycie.get("inputTokens"),
        uzycie.get("outputTokens"),
    )
    czesci = odpowiedz["output"]["message"]["content"]
    wynik = "".join(c.get("text", "") for c in czesci).strip()

    if odpowiedz.get("stopReason") == "max_tokens":
        log.error("odpowiedz modelu ucieta przy limicie %d tokenow", max_tokenow)
        raise ValueError(
            f"Odpowiedz modelu zostala ucieta (limit {max_tokenow} tokenow). "
            "Zmniejsz liczbe pol we wzorze albo liczbe stron."
        )

    # Ostrzegaj, gdy odpowiedz jest bardzo dluga - moze byc przycięta lub zawierać błędy
    dlugosc = len(wynik)
    if dlugosc > 50000:
        log.warning("Bardzo dluga odpowiedz modelu: %d znakow", dlugosc)

    return wynik


def odczytaj_dane(
    strony: list[dict], pola: list[str], opis: str, legenda: dict | None = None
) -> dict:
    """Przebieg 1 - odczyt danych ze skanow."""
    tresc: list[dict] = []
    for strona in strony:
        etykieta = f"[{strona['dokument']}, strona {strona['strona']}"
        if strona.get("fragment"):
            etykieta += f", {strona['fragment']} strony"
        tresc.append({"text": etykieta + "]"})
        if strona.get("png"):
            tresc.append(
                {"image": {"format": "png", "source": {"bytes": strona["png"]}}}
            )
        # Tekst osadzony w pliku jest dokladny - nie pochodzi z rozpoznawania
        # obrazu, wiec ma pierwszenstwo przed tym, co widac na skanie.
        if strona.get("tekst"):
            tresc.append({"text": (
                "Tekst osadzony w tym pliku (dokladny, przepisany wprost z dokumentu, "
                "ma pierwszenstwo przed odczytem z obrazu):\n" + strona["tekst"]
            )})
    pola_pelne = list(pola) + [p for p in prompty.POLA_STALE if p not in pola]
    tresc.append({"text": prompty.polecenie_ekstrakcji(pola_pelne, opis, legenda)})

    surowa = _rozmowa(prompty.EKSTRAKCJA, tresc, max_tokenow=32000)
    wynik = _wczytaj_json(surowa)
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
    rozmowa: list[dict] | None = None,
) -> str:
    """Przebieg 2 - wypelnienie wzoru zwalidowanymi danymi i ustaleniami z rozmowy."""
    tresc = [{"text": prompty.polecenie_generowania(wzor, dane, opis, legenda, rozmowa)}]
    return _oczysc_projekt(_rozmowa(prompty.GENEROWANIE, tresc, max_tokenow=24000))


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
        raise ValueError("Model nie zwrocil poprawnego JSON-a")
    fragment = oczyszczony[poczatek : koniec + 1]

    # Próba 1: normalny parsing
    try:
        return json.loads(fragment)
    except json.JSONDecodeError as e:
        log.warning("Blad parsowania JSON z modelu. Pozycja: linia %d, kolumna %d", e.lineno, e.colno)

        # Próba 2: usuwamy końcowy przecinek przed } lub ]
        # Częsty błąd: {"key": "value",} zamiast {"key": "value"}
        import re
        naprawiony = re.sub(r',(\s*[}\]])', r'\1', fragment)
        if naprawiony != fragment:
            log.info("Probuje naprawic JSON przez usuniecie koncowych przecinkow")
            try:
                return json.loads(naprawiony)
            except json.JSONDecodeError:
                pass

        # Nie logujemy fragmentu odpowiedzi - moglby zawierac dane osobowe.
        log.error(
            "Niepoprawny JSON z modelu: %d znakow, %d linii, blad w linii %d",
            len(fragment), fragment.count("\n"), e.lineno,
        )
        raise ValueError(
            f"Model zwrocil niepoprawny JSON ({e.msg}, linia {e.lineno}). "
            "Jesli odpowiedz byla ucieta, zmniejsz liczbe pol albo stron."
        ) from e


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
        return _rozmowa(prompty.ROZMOWA, ostatnia["content"], max_tokenow=2000, historia=tury)
    if tury[-1]["role"] == "user":
        tury[-1]["content"].append({"text": wiadomosc})
        ostatnia = tury.pop()
        return _rozmowa(prompty.ROZMOWA, ostatnia["content"], max_tokenow=2000, historia=tury)
    return _rozmowa(prompty.ROZMOWA, [{"text": wiadomosc}], max_tokenow=2000, historia=tury)
