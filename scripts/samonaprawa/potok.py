"""Potok samonaprawy w AWS (CodeBuild notarai-samonaprawa) - zamiast workflow GitHub Actions.

  zdarzenie EventBridge / przeglad co 30 min / zatwierdzenie wlasciciela
    -> decyzja (stan w DynamoDB) -> zrodla WERSJI Z PRODUKCJI (paczka z S3, bez GitHuba)
    -> agent naprawczy -> bramki (bramki.py bez zmian) -> niezalezny recenzent
    -> werdykt: auto (wdrozenie + 20 min obserwacji + cofniecie przy nawrocie),
                pr (patch w S3 + mail: czeka na zatwierdzenie wlasciciela),
                odrzuc (komentarz w rekordzie bledu, po 2 probach eskalacja)
    -> rejestr poprawek NAPRAWA (zeby zwykle wdrozenie z GitHuba jej nie nadpisalo)
    -> best effort: zapis poprawki w repozytorium GitHub (synchronizacja.py).

Opis calosci: docs/samonaprawa.md. Wszystkie wywolania zewnetrzne sa w obiekcie
Zaleznosci, wiec orkiestracje da sie testowac bez sieci (test_samonaprawa_aws.py).

Wejscie: zmienna SN_LADUNEK (JSON albo base64 JSON): {"zdarzenie": "zgloszenie"|"przeglad"|
"zatwierdzenie", ...}. SN_TEST_WDROZENIA=1: nieszkodliwa zmiana w docs/, bez agentow.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).parent))
import stan as stan_mod  # noqa: E402
import zgloszenie as zgl  # noqa: E402
from stan import ETYKIETA_ESKALACJA, ZNACZNIK_PROBY  # noqa: E402

PROBA_OBSERWACJI_MIN = 20
TEMAT_ALARMOW = "arn:aws:sns:eu-central-1:127621462971:notarai-alarmy"
PLIK_TESTU = "docs/samonaprawa-testy-wdrozenia.md"
_POMIJANE_KATALOGI = {".git", "__pycache__", "node_modules", ".pytest_cache", ".venv"}
RECENZJE = ("przepusc", "do_wlasciciela", "odrzuc")
BRAMKI = ("auto", "pr", "odrzuc")


# ---------------------------------------------------------------- czyste funkcje

def odkoduj_ladunek(tekst: str) -> dict:
    """SN_LADUNEK: JSON albo base64 JSON (tak go buduje szablon wejscia EventBridge)."""
    tekst = (tekst or "").strip()
    try:
        wynik = json.loads(tekst)
    except ValueError:
        wynik = json.loads(base64.b64decode(tekst, validate=True).decode("utf-8"))
    if not isinstance(wynik, dict):
        raise ValueError("ladunek nie jest obiektem")
    return wynik


def werdykt(naprawione: bool, bramki: str, recenzja: str, tryb: str, baza_zmieniona: bool) -> str:
    """Ta sama tabela co krok "Werdykt" w dawnym workflow."""
    if not naprawione or bramki == "odrzuc" or recenzja == "odrzuc":
        return "odrzuc"
    if bramki == "pr" or recenzja != "przepusc" or tryb != "auto":
        return "pr"
    if baza_zmieniona:
        return "pr"      # produkcja zmienila sie w trakcie naprawy - testy szly na starej bazie
    return "auto"


def opis_werdyktu(raport: dict, bramki: dict, recenzja: dict, naprawione: bool, przebieg: str) -> str:
    probne = (not naprawione or bramki.get("werdykt") == "odrzuc" or recenzja.get("werdykt") == "odrzuc")
    linie = [
        ZNACZNIK_PROBY if probne else "",
        f"### Próba samonaprawy (przebieg {przebieg})",
        "",
        "**Dla właściciela:** " + (raport.get("dla_wlasciciela") or recenzja.get("dla_wlasciciela") or "-"),
        "",
        f"- **Przyczyna:** {raport.get('przyczyna', '-')}",
        f"- **Poprawka:** {raport.get('poprawka', '-')}",
        f"- **Test regresji:** {', '.join(raport.get('testy_regresji') or []) or '-'}",
        f"- **Ryzyko wg agenta:** {raport.get('ryzyko', '-')} - {raport.get('uzasadnienie_ryzyka', '')}",
        f"- **Bramki:** {bramki.get('werdykt', '-')}",
        *[f"  - odrzucenie: {p}" for p in bramki.get("odrzucenie", [])],
        *[f"  - tylko PR: {p}" for p in bramki.get("tylko_pr", [])],
        f"- **Recenzent:** {recenzja.get('werdykt', '-')}",
        *[f"  - {p}" for p in recenzja.get("powody", [])],
        "",
        f"Sprawdź w aplikacji: {raport.get('sprawdz_w_aplikacji', '-')}",
    ]
    return "\n".join(linie)


def hash_drzewa(korzen: Path) -> str:
    """Skrot tresci plikow drzewa (bez .git): wykrywa zmiany bez uruchamiania gita w katalogu agenta."""
    h = hashlib.sha256()
    for sciezka in sorted(p for p in korzen.rglob("*") if not (set(p.relative_to(korzen).parts) & {".git"})):
        rel = sciezka.relative_to(korzen).as_posix()
        if sciezka.is_symlink():
            h.update(f"L {rel} {os.readlink(sciezka)}\n".encode())
        elif sciezka.is_file():
            h.update(f"F {rel} ".encode() + hashlib.sha256(sciezka.read_bytes()).digest())
    return h.hexdigest()


def _pliki(korzen: Path) -> dict[str, Path]:
    wynik = {}
    for dirpath, dirnames, nazwy in os.walk(korzen):
        dirnames[:] = [d for d in dirnames if d not in _POMIJANE_KATALOGI]
        for n in nazwy:
            p = Path(dirpath) / n
            if p.is_symlink() or p.is_file():
                wynik[p.relative_to(korzen).as_posix()] = p
    return wynik


def przenies_zmiany(zrodlo: Path, cel: Path) -> None:
    """Pliki z katalogu agenta do czystego repozytorium (bez .git agenta: nie wykonujemy
    jako root zadnych hakow ani filtrow, ktore agent mogl wpisac do konfiguracji gita)."""
    z, c = _pliki(zrodlo), _pliki(cel)
    for rel in set(c) - set(z):
        c[rel].unlink()
    for rel, p in z.items():
        docelowy = cel / rel
        docelowy.parent.mkdir(parents=True, exist_ok=True)
        if docelowy.is_symlink() or docelowy.exists():
            docelowy.unlink()
        if p.is_symlink():
            os.symlink(os.readlink(p), docelowy)
        else:
            shutil.copy2(p, docelowy)


def git(katalog: Path, *argumenty: str, sprawdz: bool = True, wejscie: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "user.name=notarai-samonaprawa", "-c", "user.email=samonaprawa@notarai.pl",
                           "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", *argumenty],
                          cwd=katalog, capture_output=True, text=True, check=sprawdz, input=wejscie)


# ---------------------------------------------------------------- zaleznosci

@dataclass
class Zaleznosci:
    stan: object
    wdroz: object
    powiadom: Callable[[str, str], None]
    postep: Callable[..., None]            # (odcisk, etap, opis="", wlacz=None)
    s3_wyslij: Callable[[str, str], None]
    s3_pobierz: Callable[[str], str]
    tryb: Callable[[], str]
    sesja_agenta: Callable[[str], dict]
    uruchom_agenta: Callable[..., int]     # (rodzaj, env, cwd, wyjscie, polecenie) -> kod
    uruchom_bramki: Callable[..., int]     # (repo, baza, raport, wynik, prosba) -> kod
    uruchom_testy: Callable[[Path], int]
    obserwuj: Callable[[str, str, int], dict]
    kandydaci: Callable[[int], list]
    historia: Callable[[str], dict]
    synchronizuj: Callable[[], list]
    zainstaluj: Callable[[Path], None]
    daj_agentowi: Callable[[Path], None]
    sn: Path
    model: str = "eu.anthropic.claude-opus-4-6-v1"
    bucket_wlasny: str = ""
    przebieg: str = ""
    teraz: Callable[[], float] = time.time
    zip_bazy: Path | None = None
    tag_start: str = ""
    obserwacja_min: int = PROBA_OBSERWACJI_MIN
    dziennik: list = field(default_factory=list)


class Potok:
    def __init__(self, d: Zaleznosci, test: bool = False) -> None:
        self.d, self.test = d, test
        self.sn = d.sn
        self.sn.mkdir(parents=True, exist_ok=True)

    def log(self, tekst: str) -> None:
        self.d.dziennik.append(tekst)
        print(tekst, flush=True)

    # ------------------------------------------------------------ wejscie
    def uruchom(self, ladunek: dict) -> dict:
        rodzaj = str(ladunek.get("zdarzenie") or "zgloszenie")
        if rodzaj == "przeglad":
            return self.przeglad()
        if rodzaj == "zatwierdzenie":
            return self.zatwierdzenie(str(ladunek.get("odcisk", "")))
        return self.zgloszenie(zgl.oczysc(ladunek if not ladunek.get("ladunek_b64") else
                                          odkoduj_ladunek(ladunek["ladunek_b64"])))

    def przeglad(self) -> dict:
        self._synchronizuj()
        kandydaci = [zgl.oczysc(w) | {"wystapien": w["wystapien"]} for w in self.d.kandydaci(40)]
        if not kandydaci:
            self.log("Brak nowych bledow kodu - nic do zrobienia.")
            return {"dzialanie": "brak"}
        wybrany = self.d.stan.wybierz(kandydaci)
        if not wybrany:
            self.log("Wszystkie bledy sa juz w obsludze albo u wlasciciela.")
            return {"dzialanie": "brak"}
        return self.zgloszenie(wybrany)

    # ------------------------------------------------------------ zgloszenie
    def zgloszenie(self, z: dict) -> dict:
        d, odcisk = self.d, z["odcisk"]
        if d.stan.zamkniete_po(odcisk, z.get("czas", "")):
            self.log(f"Zgloszenie {odcisk} jest starsze niz ostatnia naprawa - pomijam (duplikat zdarzenia).")
            return {"dzialanie": "brak", "odcisk": odcisk}
        try:
            z["historia"] = d.historia(odcisk)
        except Exception as e:  # noqa: BLE001 - historia to dodatek
            self.log(f"Brak historii z CloudWatch ({type(e).__name__})")
        tryb = "auto" if self.test else d.tryb()
        dec = d.stan.decyzja(z, tryb)
        dec.setdefault("odcisk", odcisk)
        if dec["dzialanie"] == "napraw":
            d.postep(odcisk, "przyjete")
        elif dec["dzialanie"] == "eskaluj":
            d.postep(odcisk, "do_decyzji", "zespół notarai zajmie się tym ręcznie")
        if dec["dzialanie"] != "napraw":
            self._bez_naprawy(z, dec)
            return dec
        wynik = self._naprawa(z, dec)
        return dec | wynik

    def _bez_naprawy(self, z: dict, dec: dict) -> None:
        d, odcisk = self.d, z["odcisk"]
        powody = "; ".join(dec["powody"])
        if dec["dzialanie"] == "eskaluj":
            d.stan.etykieta(odcisk, ETYKIETA_ESKALACJA)
            d.stan.komentarz(odcisk, f"**Samonaprawa oddaje ten błąd właścicielowi.** {powody}\n\n"
                                     "Automat nie umiał go naprawić. Potrzebny człowiek albo sesja z Claude Code.\n")
            d.powiadom("notarai: samonaprawa potrzebuje czlowieka",
                       f"Blad {odcisk} nie zostal naprawiony automatycznie ({powody}). "
                       f"Szczegoly: tabela notarai-samonaprawa, rekord BLAD#{odcisk}.")
        elif dec["nowe"]:
            d.powiadom("notarai: nowy blad na produkcji",
                       f"Nowy blad {odcisk} - bez automatycznej naprawy: {powody}. "
                       f"Szczegoly: tabela notarai-samonaprawa, rekord BLAD#{odcisk}.")
        self.log(f"Samonaprawa: {dec['dzialanie']} ({powody})")

    # ------------------------------------------------------------ zrodla
    def _przygotuj_zrodla(self, tag_bazowy: str) -> tuple[Path, str]:
        """Drzewo wersji z produkcji: paczka z S3, git init, commit BAZA. Zwraca (katalog, sha BAZY)."""
        d = self.d
        zrodlo = self.sn / "zrodlo"
        if zrodlo.exists():
            shutil.rmtree(zrodlo)
        if d.zip_bazy and d.zip_bazy.exists():
            zip_sciezka = d.zip_bazy          # paczka pobrana juz przez buildspec (ten sam tag)
        else:
            zip_sciezka = self.sn / "baza.zip"
            d.wdroz.pobierz_zrodla(tag_bazowy, zip_sciezka, d.bucket_wlasny)
        with zipfile.ZipFile(zip_sciezka) as z:
            z.extractall(zrodlo)
        # Kopia paczki w buckecie samonaprawy: paczki budowania wygasaja.
        if d.bucket_wlasny:
            try:
                d.s3_wyslij(f"zrodla/{tag_bazowy}.zip", str(zip_sciezka))
            except Exception as e:  # noqa: BLE001
                self.log(f"Nie zapisano kopii paczki zrodel ({type(e).__name__})")
        git(zrodlo, "init", "-q", "-b", "baza")
        git(zrodlo, "add", "-A")
        git(zrodlo, "commit", "-q", "-m", f"BAZA {tag_bazowy}")
        return zrodlo, git(zrodlo, "rev-parse", "HEAD").stdout.strip()

    def _narzedzia(self, zrodlo: Path) -> Path:
        """Narzedzia bramek i agentow z drzewa BAZY, zanim agent zacznie (agent ich nie podmieni)."""
        narz = self.sn / "narzedzia"
        if narz.exists():
            shutil.rmtree(narz)
        shutil.copytree(zrodlo / "scripts" / "samonaprawa", narz)
        shutil.copy2(zrodlo / "infra" / "notarai-aplikacja.yaml", self.sn / "szablon-baza.yaml")
        return narz

    def _kopia(self, zrodlo: Path, nazwa: str, agentowi: bool) -> Path:
        cel = self.sn / nazwa
        if cel.exists():
            shutil.rmtree(cel)
        shutil.copytree(zrodlo, cel, symlinks=True)
        if agentowi:
            self.d.daj_agentowi(cel)
        return cel

    # ------------------------------------------------------------ naprawa
    def _naprawa(self, z: dict, dec: dict) -> dict:
        d, odcisk = self.d, z["odcisk"]
        tag_bazowy = d.tag_start or d.wdroz.aktualny_tag()
        zrodlo, baza = self._przygotuj_zrodla(tag_bazowy)
        narz = self._narzedzia(zrodlo)
        wymiana = self.sn / "agent"
        if wymiana.exists():
            shutil.rmtree(wymiana)
        wymiana.mkdir()
        d.daj_agentowi(wymiana)
        zgl_plik, raport_plik = wymiana / "zgloszenie.json", wymiana / "raport.json"
        zgl_plik.write_text(json.dumps(z, ensure_ascii=False, indent=2), encoding="utf-8")
        d.stan.ustaw(odcisk, status=stan_mod.W_NAPRAWIE, tag_bazowy=tag_bazowy)

        if self.test:
            kandydat, glowa, raport = self._test_wdrozenia(zrodlo, z)
            naprawione, bramki, recenzja, tryb_wynik = True, {"werdykt": "auto"}, {"werdykt": "przepusc"}, "auto"
            wer = "auto"
            md = (f"### Test ścieżki wdrożenia (przebieg {d.przebieg})\n\n"
                  "Nieszkodliwa zmiana w `docs/` - sprawdzamy wdrożenie, obserwację i cofnięcie.\n")
        else:
            d.zainstaluj(zrodlo)
            d.postep(odcisk, "analiza")
            praca = self._kopia(zrodlo, "praca", agentowi=True)
            raport = self._agent_naprawczy(z, praca, zgl_plik, raport_plik, narz)
            naprawione = bool(raport.get("naprawione"))
            kandydat = self.sn / "kandydat"
            glowa = ""
            bramki, recenzja = {"werdykt": "odrzuc"}, {"werdykt": "do_wlasciciela", "powody": ["brak recenzji"]}
            if naprawione:
                d.postep(odcisk, "kontrola", wlacz=self._wlacz(raport))
                glowa = self._zatwierdz_kandydata(zrodlo, praca, kandydat, z, raport)
                bramki = self._bramki(kandydat, baza, raport_plik, narz, z)
                if bramki["werdykt"] != "odrzuc":
                    d.postep(odcisk, "recenzja", wlacz=self._wlacz(raport))
                    recenzja = self._recenzent(kandydat, baza, zgl_plik, narz)
            baza_zmieniona = self._baza_zmieniona(tag_bazowy)
            wer = werdykt(naprawione, bramki["werdykt"], recenzja.get("werdykt", "do_wlasciciela"),
                          dec["tryb"], baza_zmieniona)
            md = opis_werdyktu(raport, bramki, recenzja, naprawione, d.przebieg)
            if baza_zmieniona and wer == "pr":
                md += "\n\nprodukcja zmienila sie w trakcie naprawy - poprawka czeka na zatwierdzenie\n"
        self.log(f"Samonaprawa {odcisk}: {wer}")

        if wer == "odrzuc":
            d.stan.komentarz(odcisk, md)
            d.stan.ustaw(odcisk, status=stan_mod.ODRZUCONE)
            d.postep(odcisk, "do_decyzji", "automat nie znalazł bezpiecznej zmiany - zespół notarai zajmie się tym"
                     if not naprawione else "zmiana nie przeszła kontroli - zespół notarai sprawdzi ją ręcznie")
            return {"werdykt": "odrzuc"}
        klucz = self._zapisz_patch(kandydat, glowa, odcisk)
        if wer == "pr":
            return self._czeka_na_zatwierdzenie(odcisk, md, raport, klucz, tag_bazowy)
        wynik = self._wdroz(odcisk, kandydat, glowa, tag_bazowy, klucz, md, raport, "auto")
        return {"werdykt": "auto"} | wynik

    def _wlacz(self, raport: dict):
        u = raport.get("ustawienie")
        return {"klucz": str(u.get("klucz")), "wartosc": str(u.get("wartosc"))} if isinstance(u, dict) else None

    def _test_wdrozenia(self, zrodlo: Path, z: dict):
        """Tryb testu: nieszkodliwa zmiana w docs/ - bez agentow i bramek, reszta sciezki jak naprawde."""
        kandydat = self._kopia(zrodlo, "kandydat", agentowi=False)
        plik = kandydat / PLIK_TESTU
        plik.parent.mkdir(parents=True, exist_ok=True)
        with open(plik, "a", encoding="utf-8") as f:
            f.write(f"- {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(self.d.teraz()))} przebieg {self.d.przebieg}: "
                    "test sciezki wdrozenia (AWS)\n")
        git(kandydat, "checkout", "-q", "-b", f"samonaprawa/{z['odcisk']}")
        git(kandydat, "add", PLIK_TESTU)
        git(kandydat, "commit", "-q", "-m", f"Samonaprawa: test sciezki wdrozenia (przebieg {self.d.przebieg})")
        raport = {"naprawione": True, "przyczyna": "test sciezki wdrozenia", "poprawka": f"wpis w {PLIK_TESTU}",
                  "ryzyko": "niskie",
                  "dla_wlasciciela": "Test: nieszkodliwa zmiana w dokumentacji przeszla wdrozenie na produkcje i obserwacje.",
                  "sprawdz_w_aplikacji": "nic - aplikacja dziala jak wczesniej"}
        return kandydat, git(kandydat, "rev-parse", "HEAD").stdout.strip(), raport

    def _agent_naprawczy(self, z: dict, praca: Path, zgl_plik: Path, raport_plik: Path, narz: Path) -> dict:
        d = self.d
        env = {"SAMONAPRAWA_ZGLOSZENIE": str(zgl_plik), "SAMONAPRAWA_RAPORT": str(raport_plik)}
        kod = d.uruchom_agenta("naprawa", env, praca, self.sn / "agent.json", (narz / "polecenie.md").read_text(encoding="utf-8"))
        if kod != 0:
            self.log(f"agent naprawczy zakonczyl sie kodem {kod}")
        return self._czytaj_json(raport_plik, {"naprawione": False, "przyczyna": "agent nie zapisal raportu"})

    def _zatwierdz_kandydata(self, zrodlo: Path, praca: Path, kandydat: Path, z: dict, raport: dict) -> str:
        """Czyste repozytorium (kopia BAZY) + pliki z katalogu agenta = commit kandydata."""
        if kandydat.exists():
            shutil.rmtree(kandydat)
        shutil.copytree(zrodlo, kandydat, symlinks=True)
        git(kandydat, "checkout", "-q", "-b", f"samonaprawa/{z['odcisk']}")
        przenies_zmiany(praca, kandydat)
        git(kandydat, "add", "-A")
        git(kandydat, "commit", "-q", "--allow-empty", "-m", f"Samonaprawa {z['odcisk']}: "
            f"{str(raport.get('przyczyna') or 'poprawka')[:150]}", "-m", str(raport.get("poprawka") or "")[:2000])
        return git(kandydat, "rev-parse", "HEAD").stdout.strip()

    def _bramki(self, kandydat: Path, baza: str, raport_plik: Path, narz: Path, z: dict) -> dict:
        d = self.d
        testy = self._kopia(kandydat, "testy", agentowi=True)
        wynik = self.sn / "agent" / "bramki.json"
        kod = d.uruchom_bramki(testy, baza, raport_plik, wynik, z.get("rodzaj") == "reczne")
        b = self._czytaj_json(wynik, {"werdykt": "odrzuc", "odrzucenie": [f"bramki nie zapisaly wyniku (kod {kod})"]})
        if b.get("werdykt") not in BRAMKI:
            b = {"werdykt": "odrzuc", "odrzucenie": ["niepoprawny wynik bramek"]}
        return b

    def _recenzent(self, kandydat: Path, baza: str, zgl_plik: Path, narz: Path) -> dict:
        d = self.d
        kopia = self._kopia(kandydat, "recenzja", agentowi=True)
        wynik = self.sn / "agent" / "recenzja.json"
        przed = hash_drzewa(kopia)
        env = {"SAMONAPRAWA_ZGLOSZENIE": str(zgl_plik), "SAMONAPRAWA_RECENZJA": str(wynik), "SAMONAPRAWA_BAZA": baza}
        kod = d.uruchom_agenta("recenzja", env, kopia, self.sn / "recenzent.json", (narz / "recenzja.md").read_text(encoding="utf-8"))
        if kod != 0:
            self.log(f"recenzent zakonczyl sie kodem {kod}")
        rec = self._czytaj_json(wynik, {"werdykt": "do_wlasciciela", "powody": ["recenzent nie zapisal wyniku"]})
        # Recenzent nie moze niczego zmienic - zmiany w drzewie = recenzja niewazna.
        if hash_drzewa(kopia) != przed:
            return {"werdykt": "do_wlasciciela", "powody": ["recenzent zmienial pliki - recenzja niewazna"]}
        if rec.get("werdykt") not in RECENZJE:
            return {"werdykt": "do_wlasciciela", "powody": ["niepoprawny wynik recenzji"]}
        return rec

    @staticmethod
    def _czytaj_json(sciezka: Path, domyslny: dict) -> dict:
        try:
            wynik = json.loads(sciezka.read_text(encoding="utf-8"))
            return wynik if isinstance(wynik, dict) else domyslny
        except (OSError, ValueError):
            return domyslny

    def _baza_zmieniona(self, tag_bazowy: str) -> bool:
        try:
            return self.d.wdroz.aktualny_tag() != tag_bazowy
        except Exception:  # noqa: BLE001 - nie wiemy = nie ryzykujemy automatu
            return True

    # ------------------------------------------------------------ patch i zatwierdzenie
    def _zapisz_patch(self, kandydat: Path, glowa: str, odcisk: str) -> str:
        patch = git(kandydat, "format-patch", "-1", "--stdout", "--binary", glowa).stdout
        klucz = f"poprawki/{odcisk}/{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(self.d.teraz()))}.patch"
        plik = self.sn / "poprawka.patch"
        plik.write_text(patch, encoding="utf-8")
        self.d.s3_wyslij(klucz, str(plik))
        return klucz

    def _czeka_na_zatwierdzenie(self, odcisk: str, md: str, raport: dict, klucz: str, tag_bazowy: str) -> dict:
        d = self.d
        d.stan.ustaw(odcisk, status=stan_mod.CZEKA, patch_klucz=klucz, tag_bazowy=tag_bazowy,
                     zatwierdzone=False, tytul=str(raport.get("przyczyna") or "poprawka")[:200])
        d.stan.komentarz(odcisk, md + f"\n\nPoprawka czeka na zatwierdzenie: s3://{d.bucket_wlasny}/{klucz}\n")
        d.postep(odcisk, "do_decyzji", "zmiana gotowa, czeka na zatwierdzenie przez zespół notarai")
        d.powiadom("notarai: poprawka bledu czeka na decyzje",
                   f"{raport.get('dla_wlasciciela') or 'Poprawka bledu czeka na zatwierdzenie.'}\n\n"
                   f"Poprawka (patch): s3://{d.bucket_wlasny}/{klucz}\n"
                   f"Zeby wdrozyc, uruchom: python scripts/samonaprawa/zatwierdz.py {odcisk}\n"
                   f"(albo komendy aws z docs/samonaprawa.md). Zeby odrzucic: nic nie rob.")
        return {"werdykt": "pr"}

    def zatwierdzenie(self, odcisk: str) -> dict:
        """Wlasciciel zatwierdzil patch (flaga w DynamoDB ustawiona przez zatwierdz.py)."""
        d = self.d
        rec = d.stan.pobierz(odcisk) or {}
        if rec.get("status") != stan_mod.CZEKA or not rec.get("zatwierdzone") or not rec.get("patch_klucz"):
            self.log(f"Zatwierdzenie {odcisk} odrzucone: brak flagi zatwierdzenia albo poprawki w kolejce.")
            return {"dzialanie": "brak", "odcisk": odcisk}
        d.postep(odcisk, "wdrazanie")
        tag_bazowy = d.tag_start or d.wdroz.aktualny_tag()
        zrodlo, baza = self._przygotuj_zrodla(tag_bazowy)
        self._narzedzia(zrodlo)
        patch = self.sn / "zatwierdzony.patch"
        patch.write_text(d.s3_pobierz(rec["patch_klucz"]), encoding="utf-8")
        kandydat = self._kopia(zrodlo, "kandydat", agentowi=False)
        if git(kandydat, "am", "--3way", str(patch), sprawdz=False).returncode != 0:
            git(kandydat, "am", "--abort", sprawdz=False)
            d.stan.ustaw(odcisk, status="konflikt")
            d.postep(odcisk, "do_decyzji", "zmiana nie pasuje do obecnej wersji - zespół notarai zajmie się tym")
            d.powiadom("notarai: zatwierdzona poprawka nie pasuje do obecnej wersji",
                       f"Poprawka bledu {odcisk} nie daje sie nalozyc na wersje z produkcji ({tag_bazowy}). "
                       "Trzeba ja przygotowac recznie. Patch zostaje w S3.")
            return {"dzialanie": "konflikt", "odcisk": odcisk}
        d.zainstaluj(kandydat)
        testy = self._kopia(kandydat, "testy", agentowi=True)
        if d.uruchom_testy(testy) != 0:
            d.stan.ustaw(odcisk, status="testy_nieudane")
            d.postep(odcisk, "do_decyzji", "po zatwierdzeniu testy nie przeszły - zespół notarai sprawdzi zmianę")
            d.powiadom("notarai: zatwierdzona poprawka nie przeszla testow",
                       f"Poprawka bledu {odcisk} jest zatwierdzona, ale pelny zestaw testow na wersji z produkcji "
                       "jest czerwony - nie wdrazam.")
            return {"dzialanie": "testy_nieudane", "odcisk": odcisk}
        glowa = git(kandydat, "rev-parse", "HEAD").stdout.strip()
        md = f"Wdrożenie poprawki zatwierdzonej przez właściciela (przebieg {d.przebieg})."
        # Swiezy patch wzgledem wersji z produkcji (rejestr poprawek i straznik stosuja go na master).
        klucz = self._zapisz_patch(kandydat, glowa, odcisk)
        wynik = self._wdroz(odcisk, kandydat, glowa, tag_bazowy, klucz, md,
                            {"dla_wlasciciela": "Poprawka zatwierdzona przez zespół notarai została wdrożona."}, "zatwierdzone")
        return {"dzialanie": "zatwierdzone", "odcisk": odcisk} | wynik

    # ------------------------------------------------------------ wdrozenie, obserwacja, cofniecie
    def _wdroz(self, odcisk: str, kandydat: Path, glowa: str, tag_bazowy: str, klucz: str, md: str,
               raport: dict, tryb: str) -> dict:
        d, w = self.d, self.d.wdroz
        tag = f"sn-{glowa[:12]}"
        d.postep(odcisk, "wdrazanie", wlacz=self._wlacz(raport))
        if not w.czekaj_na_stos(75):
            return self._nie_wdrozono(odcisk, md, raport, klucz, tag_bazowy, "stos aplikacji trwa w zmianie dluzej niz 75 min")
        if w.aktualny_tag() != tag_bazowy:
            return self._nie_wdrozono(odcisk, md, raport, klucz, tag_bazowy,
                                      "produkcja zmienila sie w trakcie naprawy - poprawka idzie do zatwierdzenia")
        poprzedni = w.tag_stosu()
        zip_sciezka = self.sn / "kandydat.zip"
        git(kandydat, "archive", "--format=zip", "-o", str(zip_sciezka), glowa)
        try:
            w.zbuduj_obraz(tag, zip_sciezka, d.bucket_wlasny)
        except Exception as e:  # noqa: BLE001
            return self._niepowodzenie(odcisk, md, f"budowanie obrazu: {str(e)[:300]}", None, None, poprzedni)
        # Ostatnie sprawdzenie tuz przed wdrozeniem: nikt nie wdrozyl innej wersji w miedzyczasie.
        if w.aktualny_tag() != tag_bazowy or w.tag_stosu() != poprzedni:
            return self._nie_wdrozono(odcisk, md, raport, klucz, tag_bazowy, "ktos wdrozyl inna wersje tuz przed wdrozeniem poprawki")
        wdr = d.stan.zapisz_wdrozenie(odcisk, tag, tryb)
        wynik = w.wdroz(tag, kandydat / "infra" / "notarai-aplikacja.yaml", kandydat)
        d.stan.wynik_wdrozenia(wdr, wynik["wynik"])
        if wynik["wynik"] == "wyprzedzone":
            d.stan.komentarz(odcisk, f"Wdrożenie {tag} wyprzedzone: {wynik['powod']}")
            d.powiadom("notarai: wdrozenie poprawki wyprzedzone innym wdrozeniem",
                       f"W trakcie wdrazania poprawki bledu {odcisk} ktos wdrozyl inna wersje ({wynik['powod']}). "
                       "Nie cofam niczego w ciemno. Poprawka NIE jest na produkcji; zglosze blad ponownie, jesli wroci.")
            d.stan.ustaw(odcisk, status=stan_mod.NOWE)
            return {"wdrozenie": "wyprzedzone"}
        if wynik["wynik"] != "success":
            return self._niepowodzenie(odcisk, md, wynik["powod"], tag, poprzedni, poprzedni)
        pid = d.stan.zarejestruj_poprawke(odcisk, tag, tag_bazowy, klucz, str(raport.get("przyczyna") or "")[:200])
        d.stan.ustaw(odcisk, status=stan_mod.WDRAZANIE, tag=tag)
        d.postep(odcisk, "obserwacja", wlacz=self._wlacz(raport))
        obs = d.obserwuj(odcisk, tag, wynik["koniec_ms"])
        if obs.get("werdykt") != "ok":
            powody = "; ".join(obs.get("powody") or []) or "obserwacja: blad wrocil"
            d.stan.status_poprawki(pid, stan_mod.WYCOFANA, powod=powody[:300])
            return self._cofnij(odcisk, tag, poprzedni, powody)
        d.postep(odcisk, "gotowe", wlacz=self._wlacz(raport))
        d.stan.komentarz(odcisk, f"✅ **Naprawione i wdrożone** ({tag}). Po {d.obserwacja_min} minutach obserwacji błąd nie wrócił.\n")
        d.stan.zamknij(odcisk)
        temat = "notarai: test wdrozenia samonaprawy udany" if self.test else "notarai: blad naprawiony automatycznie"
        d.powiadom(temat, f"{raport.get('dla_wlasciciela') or 'Blad naprawiony.'}\n\n"
                          f"Sprawdz: {raport.get('sprawdz_w_aplikacji') or '-'}\n"
                          f"Szczegoly: tabela notarai-samonaprawa, rekord BLAD#{odcisk}, wersja {tag}\n")
        self._synchronizuj()
        return {"wdrozenie": "success", "tag": tag}

    def _nie_wdrozono(self, odcisk: str, md: str, raport: dict, klucz: str, tag_bazowy: str, powod: str) -> dict:
        """Poprawka przeszla bramki, ale nie wdrozylismy jej sami: zostaje do zatwierdzenia."""
        self.log(f"Nie wdrazam automatycznie: {powod}")
        res = self._czeka_na_zatwierdzenie(odcisk, md + f"\n\n{powod}\n", raport, klucz, tag_bazowy)
        return res | {"wdrozenie": "nie_wdrozono", "powod": powod}

    def _niepowodzenie(self, odcisk: str, md: str, powod: str, tag: str | None, poprzedni: str | None, _p) -> dict:
        d = self.d
        if tag and poprzedni:
            return self._cofnij(odcisk, tag, poprzedni, f"wdrozenie: {powod}")   # komentarz z licznikiem prob dodaje _cofnij
        d.stan.komentarz(odcisk, ZNACZNIK_PROBY + f"\n**Wdrożenie poprawki nie powiodło się:** {powod}\n")
        d.stan.ustaw(odcisk, status=stan_mod.COFNIETE)
        d.postep(odcisk, "do_decyzji", "wdrożenie się nie udało - zespół notarai to sprawdzi")
        d.powiadom("notarai: wdrozenie poprawki nie powiodlo sie",
                   f"Poprawka bledu {odcisk} nie zostala wdrozona ({powod}). Aplikacja dziala na poprzedniej wersji.")
        return {"wdrozenie": "blad", "powod": powod}

    def _cofnij(self, odcisk: str, tag: str, poprzedni: str, powody: str) -> dict:
        """Cofniecie = to samo wdrozenie z poprzednim tagiem (obraz jest w ECR). Bez git revert."""
        d, w = self.d, self.d.wdroz
        d.postep(odcisk, "cofniete", "zmiana wycofana automatycznie, bo coś nie działało - zespół notarai to sprawdzi")
        d.stan.komentarz(odcisk, ZNACZNIK_PROBY + f"\n**Cofnięto automatycznie** poprawkę ({tag}): {powody}\n")
        d.stan.ustaw(odcisk, status=stan_mod.COFNIETE)
        try:
            biezacy = w.tag_stosu()
        except Exception:  # noqa: BLE001
            biezacy = tag
        if biezacy != tag:
            d.powiadom("notarai: samonaprawa - cofniecie pominiete, produkcja zmieniona",
                       f"Poprawka bledu {odcisk} powinna zostac cofnieta ({powody}), ale na produkcji dziala juz inna wersja "
                       f"({biezacy}), wdrozona w miedzyczasie. Nie cofam w ciemno - sprawdz recznie. Poprawka jest oznaczona "
                       "jako wycofana w rejestrze, wiec straznik wdrozen jej wiecej nie dolacza.")
            return {"wdrozenie": "cofniecie_pominiete"}
        wynik = w.wdroz(poprzedni, self.sn / "szablon-baza.yaml", self.sn / "zrodlo")
        if wynik["wynik"] != "success":
            d.powiadom("notarai: samonaprawa - COFNIECIE NIE POWIODLO SIE",
                       f"Poprawka bledu {odcisk} ({tag}) miala byc cofnieta do {poprzedni}, ale cofniecie sie nie udalo "
                       f"({wynik['powod']}). Wymagana pilna reczna interwencja: stos notarai-aplikacja, parametr TagObrazu={poprzedni}.")
            return {"wdrozenie": "cofniecie_nieudane", "powod": wynik["powod"]}
        d.powiadom("notarai: samonaprawa cofnieta",
                   f"Poprawka bledu {odcisk} zostala wdrozona i automatycznie cofnieta ({powody}). "
                   f"Aplikacja wraca do poprzedniej wersji ({poprzedni}). Szczegoly: tabela notarai-samonaprawa, BLAD#{odcisk}.")
        return {"wdrozenie": "cofnieto", "powod": powody}

    def _synchronizuj(self) -> None:
        try:
            self.d.synchronizuj()
        except Exception as e:  # noqa: BLE001 - synchronizacja nigdy nie psuje potoku
            self.log(f"synchronizacja z GitHub nieudana ({type(e).__name__})")


# ---------------------------------------------------------------- uruchomienie w CodeBuild

def skrypt_postepu(narz: Path) -> Path:
    """postep.sh z kopii narzedzi, a gdy kopii jeszcze nie ma (zgloszenie "przyjete", test
    wdrozenia, przeglad) - z tej samej paczki wersji produkcyjnej, z ktorej dziala potok."""
    kopia = narz / "postep.sh"
    return kopia if kopia.exists() else Path(__file__).resolve().parent / "postep.sh"

def zbuduj_zaleznosci() -> Zaleznosci:  # pragma: no cover - laczy rzeczywiste uslugi AWS
    import boto3
    import agent as ag
    import obserwacja
    import synchronizacja as sync
    from wdroz import Wdrozenie

    region = os.environ.get("AWS_REGION", "eu-central-1")
    sn = Path(os.environ.get("SN_KATALOG", "/tmp/sn"))
    tabela = os.environ.get("SN_TABELA", stan_mod.TABELA)
    bucket = os.environ.get("SN_BUCKET", "")
    temat = os.environ.get("SN_TEMAT", TEMAT_ALARMOW)
    przebieg = os.environ.get("CODEBUILD_BUILD_ID", "")
    s3, sns, ssm = (boto3.client(n, region_name=region) for n in ("s3", "sns", "ssm"))
    stan = stan_mod.Stan(stan_mod.TabelaDynamo(tabela, region))
    narz = sn / "narzedzia"
    dom = sn / "dom-agenta"
    dom.mkdir(parents=True, exist_ok=True)

    def powiadom(temat_wiadomosci: str, tresc: str) -> None:
        try:
            sns.publish(TopicArn=temat, Subject=temat_wiadomosci[:100], Message=tresc[:20000])
        except Exception as e:  # noqa: BLE001
            print(f"powiadomienie nieudane ({type(e).__name__})", flush=True)

    def postep(odcisk: str, etap: str, opis: str = "", wlacz=None) -> None:
        env = dict(os.environ, ODCISK=odcisk, PRZEBIEG=przebieg, WLACZ=json.dumps(wlacz) if wlacz else "")
        subprocess.run(["bash", str(skrypt_postepu(narz)), etap, opis], env=env, check=False)

    def parametr(nazwa: str, domyslna: str) -> str:
        try:
            return ssm.get_parameter(Name=nazwa)["Parameter"]["Value"].strip() or domyslna
        except Exception:  # noqa: BLE001
            return domyslna

    def tryb() -> str:
        w = parametr("/notarai/samonaprawa/tryb", "auto")
        return w if w in ("auto", "pr", "wylaczona") else "auto"

    model = parametr("/notarai/samonaprawa/model", ag.DOMYSLNY_MODEL)

    def uruchom_agenta(rodzaj: str, env_pliki: dict, cwd: Path, wyjscie: Path, polecenie: str) -> int:
        sesja = ag.sesja_agenta(boto3.client("sts", region_name=region), os.environ.get("SN_ROLA_AGENTA", ag.ROLA_AGENTA),
                                f"samonaprawa-{rodzaj}")
        env = ag.srodowisko_agenta(sesja, str(dom), model, env_pliki)
        zabronione = ag.NARZEDZIA_ZABRONIONE_NAPRAWA if rodzaj == "naprawa" else ag.NARZEDZIA_ZABRONIONE_RECENZJA
        return ag.uruchom_agenta(polecenie, env, cwd, wyjscie, zabronione, 120 if rodzaj == "naprawa" else 60,
                                 45 if rodzaj == "naprawa" else 25)

    def uruchom_bramki(repo, baza, raport, wynik, prosba) -> int:
        return ag.uruchom_bramki(narz, repo, baza, raport, wynik, prosba, ag.srodowisko_czyste(str(dom)))

    def uruchom_testy(repo: Path) -> int:
        return subprocess.run(["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=repo,
                              env=ag.srodowisko_czyste(str(dom)), timeout=3600,
                              **ag._uzytkownik({})).returncode

    def obserwuj(odcisk: str, tag: str, od_ms: int) -> dict:
        plik = sn / "obserwacja.json"
        subprocess.run([sys.executable, str(narz / "obserwacja.py"), "--odcisk", odcisk, "--wersja", tag,
                        "--od", str(od_ms), "--minut", str(PROBA_OBSERWACJI_MIN), "--wynik", str(plik)], check=False)
        return Potok._czytaj_json(plik, {"werdykt": "cofnij", "powody": ["obserwacja nie zapisala wyniku"]})

    def zainstaluj(drzewo: Path) -> None:
        wymagania = [l for l in (drzewo / "requirements.txt").read_text(encoding="utf-8").splitlines()
                     if l.strip() and not l.startswith(("faster-whisper", "playwright"))]
        plik = sn / "req.txt"
        plik.write_text("\n".join(wymagania), encoding="utf-8")
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "-r", str(plik)], check=True)

    def daj_agentowi(sciezka: Path) -> None:
        uzytkownik = os.environ.get("SN_AGENT_UZYTKOWNIK", "")
        if uzytkownik and os.geteuid() == 0:
            subprocess.run(["chown", "-R", f"{uzytkownik}:{uzytkownik}", str(sciezka)], check=True)

    def s3_wyslij(klucz: str, plik: str) -> None:
        s3.upload_file(plik, bucket, klucz)

    def s3_pobierz(klucz: str) -> str:
        return s3.get_object(Bucket=bucket, Key=klucz)["Body"].read().decode("utf-8")

    def synchronizuj() -> list:
        sm = boto3.client("secretsmanager", region_name=region)

        def fabryka():
            token = sync.token_z_sekretu(sm)
            return sync.Github(token, os.environ.get("SN_REPOZYTORIUM", sync.REPOZYTORIUM)) if token else None
        return sync.synchronizuj_wszystkie(stan, s3_pobierz, fabryka, powiadom)

    zip_bazy = os.environ.get("SN_ZIP_BAZY")
    return Zaleznosci(
        stan=stan, wdroz=Wdrozenie(region), powiadom=powiadom, postep=postep, s3_wyslij=s3_wyslij,
        s3_pobierz=s3_pobierz, tryb=tryb, sesja_agenta=lambda r: {}, uruchom_agenta=uruchom_agenta,
        uruchom_bramki=uruchom_bramki, uruchom_testy=uruchom_testy, obserwuj=obserwuj,
        kandydaci=lambda minut: zgl.kandydaci(minut), historia=zgl.historia, synchronizuj=synchronizuj,
        zainstaluj=zainstaluj, daj_agentowi=daj_agentowi, sn=sn, model=model, bucket_wlasny=bucket,
        przebieg=przebieg, zip_bazy=Path(zip_bazy) if zip_bazy else None,
        tag_start=os.environ.get("SN_TAG_START", ""))


def main() -> int:  # pragma: no cover
    try:
        ladunek = odkoduj_ladunek(os.environ.get("SN_LADUNEK", ""))
    except Exception as e:  # noqa: BLE001
        print(f"Zly SN_LADUNEK: {type(e).__name__}", flush=True)
        return 1
    zal = zbuduj_zaleznosci()
    try:
        wynik = Potok(zal, test=os.environ.get("SN_TEST_WDROZENIA") == "1").uruchom(ladunek)
        print(json.dumps({k: v for k, v in wynik.items() if isinstance(v, (str, int, bool))}, ensure_ascii=False))
        return 0
    except Exception as e:  # noqa: BLE001 - mail bez danych: tylko typ wyjatku
        zal.powiadom("notarai: potok samonaprawy sie wywrocil",
                     f"Potok samonaprawy (CodeBuild notarai-samonaprawa, {zal.przebieg}) zakonczyl sie bledem {type(e).__name__}. "
                     "Szczegoly w logach /aws/codebuild/notarai-samonaprawa. Aplikacja nie zostala zmieniona, chyba ze mail "
                     "o cofnieciu mowi inaczej.")
        raise


if __name__ == "__main__":
    sys.exit(main())
