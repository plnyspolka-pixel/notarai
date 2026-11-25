"""Stan samonaprawy w DynamoDB (tabela notarai-samonaprawa) zamiast zgloszen GitHuba.

Zadnych danych osobowych: tylko pola zgloszenia po zgloszenie.oczysc()
(typ bledu, kod AWS, miejsca w kodzie, wersja, opis po maskowaniu).

Rekordy (klucz: pk, sk):
  BLAD#<odcisk> / STAN       - jeden na odcisk bledu: status, proby, historia
                               komentarzy (ostatnie KOMENTARZY_MAX), etykiety,
                               poprawka czekajaca na zatwierdzenie (klucz w S3),
  WDROZENIE / <iso>#<odcisk> - wdrozenia poprawek; z nich limit na dobe,
  NAPRAWA / <iso>#<odcisk>   - REJESTR poprawek wdrozonych na produkcje, ktorych
                               jeszcze nie ma w master (status do_zsynchronizowania).
                               Straznik w wdrozenie.yml stosuje je na kodzie z master,
                               zeby zwykle wdrozenie nie nadpisalo poprawki.

Semantyka decyzji jest ta sama co w github.py (decyzja, wybierz, komentarz,
etykieta, zamknij); zamiast "otwartego pull requestu" liczy sie poprawka
czekajaca na zatwierdzenie albo na zapis w repozytorium.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

TABELA = "notarai-samonaprawa"
ETYKIETA = "samonaprawa"
ETYKIETA_AUTO = "samonaprawa-auto"
ETYKIETA_ESKALACJA = "samonaprawa-eskalacja"
ZNACZNIK_PROBY = "<!-- samonaprawa-proba -->"
# Ile prob naprawy jednego bledu, zanim automat odda go wlascicielowi.
MAX_PROB = 2
# Ile automatycznych wdrozen na dobe - powyzej poprawki czekaja na zatwierdzenie.
MAX_AUTO_NA_DOBE = 3
KOMENTARZY_MAX = 40
DLUGOSC_KOMENTARZA = 4000

# Statusy rekordu bledu.
NOWE = "nowe"
W_NAPRAWIE = "w_naprawie"
CZEKA = "czeka_na_zatwierdzenie"
WDRAZANIE = "wdrazanie"
NAPRAWIONE = "naprawione"
ESKALACJA = "eskalacja"
COFNIETE = "cofniete"
ODRZUCONE = "odrzucone"
# Statusy rejestru poprawek (NAPRAWA).
DO_ZSYNCHRONIZOWANIA = "do_zsynchronizowania"
ZSYNCHRONIZOWANE = "zsynchronizowane"
WYCOFANA = "wycofana"


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class TabelaPamiec:
    """Tabela w pamieci: testy i tryb --na-sucho. Ten sam interfejs co TabelaDynamo."""

    def __init__(self) -> None:
        self.dane: dict[tuple[str, str], dict] = {}

    def pobierz(self, pk: str, sk: str) -> dict | None:
        wpis = self.dane.get((pk, sk))
        return None if wpis is None else _kopia(wpis)

    def zapisz(self, wpis: dict) -> None:
        self.dane[(wpis["pk"], wpis["sk"])] = _kopia(wpis)

    def aktualizuj(self, pk: str, sk: str, pola: dict) -> None:
        wpis = self.dane.setdefault((pk, sk), {"pk": pk, "sk": sk})
        for k, v in pola.items():
            if v is None:
                wpis.pop(k, None)
            else:
                wpis[k] = _kopia(v)

    def zapytaj(self, pk: str, sk_od: str | None = None) -> list[dict]:
        wiersze = [w for (p, s), w in self.dane.items() if p == pk and (sk_od is None or s >= sk_od)]
        return [_kopia(w) for w in sorted(wiersze, key=lambda w: w["sk"])]


def _kopia(v):
    import copy
    return copy.deepcopy(v)


def _odliczba(v):
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, list):
        return [_odliczba(x) for x in v]
    if isinstance(v, dict):
        return {k: _odliczba(x) for k, x in v.items()}
    return v


class TabelaDynamo:
    """Cienka nakladka na boto3 Table (jedna tabela, klucze pk/sk)."""

    def __init__(self, nazwa: str = TABELA, region: str = "eu-central-1", zasob=None) -> None:
        if zasob is None:
            import boto3
            zasob = boto3.resource("dynamodb", region_name=region)
        self.t = zasob.Table(nazwa)

    def pobierz(self, pk: str, sk: str) -> dict | None:
        odp = self.t.get_item(Key={"pk": pk, "sk": sk}, ConsistentRead=True)
        wpis = odp.get("Item")
        return _odliczba(wpis) if wpis else None

    def zapisz(self, wpis: dict) -> None:
        self.t.put_item(Item=wpis)

    def aktualizuj(self, pk: str, sk: str, pola: dict) -> None:
        ustaw = {k: v for k, v in pola.items() if v is not None}
        usun = [k for k, v in pola.items() if v is None]
        wyrazenie = []
        nazwy, wartosci = {}, {}
        for i, (k, v) in enumerate(ustaw.items()):
            nazwy[f"#k{i}"] = k
            wartosci[f":v{i}"] = v
        if ustaw:
            wyrazenie.append("SET " + ", ".join(f"#k{i} = :v{i}" for i in range(len(ustaw))))
        if usun:
            for j, k in enumerate(usun):
                nazwy[f"#d{j}"] = k
            wyrazenie.append("REMOVE " + ", ".join(f"#d{j}" for j in range(len(usun))))
        if not wyrazenie:
            return
        argumenty = {"Key": {"pk": pk, "sk": sk}, "UpdateExpression": " ".join(wyrazenie),
                     "ExpressionAttributeNames": nazwy}
        if wartosci:
            argumenty["ExpressionAttributeValues"] = wartosci
        self.t.update_item(**argumenty)

    def zapytaj(self, pk: str, sk_od: str | None = None) -> list[dict]:
        wynik, start = [], None
        while True:
            argumenty = {"ConsistentRead": True,
                         "KeyConditionExpression": "pk = :p" + (" AND sk >= :s" if sk_od else ""),
                         "ExpressionAttributeValues": {":p": pk} | ({":s": sk_od} if sk_od else {})}
            if start:
                argumenty["ExclusiveStartKey"] = start
            odp = self.t.query(**argumenty)
            wynik += [_odliczba(w) for w in odp.get("Items", [])]
            start = odp.get("LastEvaluatedKey")
            if not start:
                return wynik


class Stan:
    """Logika decyzji samonaprawy nad tabela (DynamoDB albo pamiec)."""

    def __init__(self, tabela, teraz=None) -> None:
        self.t = tabela
        self._teraz = teraz or (lambda: datetime.now(timezone.utc))

    # ------------------------------------------------------------ rekord bledu
    @staticmethod
    def _pk(odcisk: str) -> str:
        return f"BLAD#{odcisk}"

    def pobierz(self, odcisk: str) -> dict | None:
        return self.t.pobierz(self._pk(odcisk), "STAN")

    def _zmien(self, odcisk: str, **pola) -> None:
        self.t.aktualizuj(self._pk(odcisk), "STAN", {**pola, "zaktualizowane": _iso(self._teraz())})

    def _zaloz(self, z: dict) -> dict:
        teraz = _iso(self._teraz())
        wpis = {
            "pk": self._pk(z["odcisk"]), "sk": "STAN", "odcisk": z["odcisk"], "status": NOWE,
            "otwarte": True, "etykiety": [], "proby": 0, "komentarze": [],
            "rodzaj": z.get("rodzaj", ""), "typ": z.get("typ", ""), "kod_aws": z.get("kod_aws", ""),
            "endpoint": z.get("endpoint", ""), "wersja": z.get("wersja", ""),
            "opis": z.get("opis", ""), "miejsca": list(z.get("miejsca") or []),
            "uwagi": z.get("uwagi", ""), "utworzone": teraz, "zaktualizowane": teraz,
        }
        self.t.zapisz(wpis)
        return wpis

    def decyzja(self, z: dict, tryb: str) -> dict:
        """Czy naprawiac, w jakim trybie. Odpowiednik github.decyzja()."""
        wpis = self.pobierz(z["odcisk"])
        nowe = wpis is None
        if nowe:
            wpis = self._zaloz(z)
        elif not wpis.get("otwarte", True):
            # Blad wrocil po zamknieciu (np. po naprawie) - otwieramy ponownie.
            self._zmien(z["odcisk"], otwarte=True, status=NOWE)
            wpis["otwarte"], wpis["status"] = True, NOWE
        etykiety = set(wpis.get("etykiety") or [])
        proby = int(wpis.get("proby", 0))
        wynik = {"odcisk": z["odcisk"], "nowe": nowe, "proby": proby, "tryb": tryb,
                 "dzialanie": "napraw", "powody": []}

        if tryb == "wylaczona":
            wynik.update(dzialanie="tylko_zglos", powody=["samonaprawa wylaczona (parametr /notarai/samonaprawa/tryb)"])
        elif z["rodzaj"] == "przejsciowy":
            wynik.update(dzialanie="tylko_zglos", powody=["blad przejsciowy (AWS/siec) - nie naprawia sie go kodem"])
        elif ETYKIETA_ESKALACJA in etykiety:
            wynik.update(dzialanie="tylko_zglos", powody=["blad oddany wlascicielowi (eskalacja)"])
        elif proby >= MAX_PROB:
            wynik.update(dzialanie="eskaluj", powody=[f"{proby} nieudane proby naprawy"])
        elif self.czeka_poprawka(z["odcisk"], wpis):
            wynik.update(dzialanie="tylko_zglos",
                         powody=["poprawka tego bledu czeka juz na zatwierdzenie albo na zapis w repozytorium"])
        elif tryb == "auto" and self.auto_w_dobie() >= MAX_AUTO_NA_DOBE:
            wynik.update(tryb="pr", powody=[f"limit {MAX_AUTO_NA_DOBE} automatycznych wdrozen na dobe"])
        return wynik

    def czeka_poprawka(self, odcisk: str, wpis: dict | None = None) -> bool:
        """Odpowiednik "otwartego PR": poprawka czeka na zatwierdzenie wlasciciela
        albo jest na produkcji, ale nie zapisana w repozytorium."""
        wpis = wpis if wpis is not None else self.pobierz(odcisk)
        if wpis and wpis.get("status") == CZEKA:
            return True
        return any(p["odcisk"] == odcisk for p in self.poprawki_do_synchronizacji())

    def wybierz(self, kandydaci: list[dict]) -> dict | None:
        """Pierwszy blad z przegladu, ktorym warto sie zajac: bez eskalacji i bez
        czekajacej poprawki. Zamkniety blad z nawrotem bierzemy ponownie."""
        for k in kandydaci:
            wpis = self.pobierz(k["odcisk"])
            if wpis is None:
                return k
            if ETYKIETA_ESKALACJA in (wpis.get("etykiety") or []) or self.czeka_poprawka(k["odcisk"], wpis):
                continue
            return k
        return None

    def komentarz(self, odcisk: str, tresc: str) -> None:
        wpis = self.pobierz(odcisk) or {}
        komentarze = list(wpis.get("komentarze") or [])
        komentarze.append({"czas": _iso(self._teraz()), "tresc": tresc[:DLUGOSC_KOMENTARZA]})
        pola = {"komentarze": komentarze[-KOMENTARZY_MAX:]}
        if ZNACZNIK_PROBY in tresc:
            pola["proby"] = int(wpis.get("proby", 0)) + 1
        self._zmien(odcisk, **pola)

    def etykieta(self, odcisk: str, nazwa: str) -> None:
        wpis = self.pobierz(odcisk) or {}
        etykiety = list(wpis.get("etykiety") or [])
        if nazwa not in etykiety:
            etykiety.append(nazwa)
        pola = {"etykiety": etykiety}
        if nazwa == ETYKIETA_ESKALACJA:
            pola["status"] = ESKALACJA
        self._zmien(odcisk, **pola)

    def zamknij(self, odcisk: str) -> None:
        self._zmien(odcisk, otwarte=False, status=NAPRAWIONE, czas_zamkniecia=_iso(self._teraz()))

    def ustaw(self, odcisk: str, **pola) -> None:
        self._zmien(odcisk, **pola)

    def zamkniete_po(self, odcisk: str, czas_zgloszenia: str) -> bool:
        """Zgloszenie starsze niz ostatnie zamkniecie (np. zdublowane zdarzenie
        po retry EventBridge) - ten blad juz naprawiono."""
        wpis = self.pobierz(odcisk)
        zamkniecie = (wpis or {}).get("czas_zamkniecia", "")
        return bool(czas_zgloszenia and zamkniecie and czas_zgloszenia < zamkniecie)

    # ------------------------------------------------------------ limit na dobe
    def zapisz_wdrozenie(self, odcisk: str, tag: str, tryb: str, wynik: str = "start") -> str:
        teraz = self._teraz()
        sk = f"{_iso(teraz)}#{odcisk}"
        self.t.zapisz({"pk": "WDROZENIE", "sk": sk, "odcisk": odcisk, "tag": tag, "tryb": tryb,
                       "wynik": wynik, "wygasa": int((teraz + timedelta(days=30)).timestamp())})
        return sk

    def wynik_wdrozenia(self, sk: str, wynik: str) -> None:
        self.t.aktualizuj("WDROZENIE", sk, {"wynik": wynik})

    def auto_w_dobie(self) -> int:
        od = _iso(self._teraz() - timedelta(days=1))
        return sum(1 for w in self.t.zapytaj("WDROZENIE", od) if w.get("tryb") == "auto")

    # ------------------------------------------------------------ rejestr poprawek
    def zarejestruj_poprawke(self, odcisk: str, tag: str, tag_bazowy: str, patch_klucz: str,
                             tytul: str = "", galaz_github: str = "") -> str:
        """Poprawka jest na produkcji, a nie w master: wpis do rejestru (do_zsynchronizowania)."""
        sk = f"{_iso(self._teraz())}#{odcisk}"
        self.t.zapisz({"pk": "NAPRAWA", "sk": sk, "id": sk, "odcisk": odcisk, "tag": tag,
                       "tag_bazowy": tag_bazowy, "patch_klucz": patch_klucz, "tytul": tytul[:200],
                       "status": DO_ZSYNCHRONIZOWANIA, "proby_synchronizacji": 0,
                       "utworzone": _iso(self._teraz())})
        return sk

    def poprawki_do_synchronizacji(self) -> list[dict]:
        """W kolejnosci wdrozenia (sk rosnaco). Nigdy nie kasujemy wpisow."""
        return [p for p in self.t.zapytaj("NAPRAWA") if p.get("status") == DO_ZSYNCHRONIZOWANIA]

    def status_poprawki(self, sk: str, status: str, **pola) -> None:
        self.t.aktualizuj("NAPRAWA", sk, {"status": status, **pola, "zaktualizowane": _iso(self._teraz())})

    def poprawka(self, sk: str) -> dict | None:
        return self.t.pobierz("NAPRAWA", sk)
