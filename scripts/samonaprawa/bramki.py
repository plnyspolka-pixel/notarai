"""Bramki samonaprawy - deterministyczna kontrola poprawki agenta.

Decyduje, co dalej z poprawka (docs/samonaprawa.md):
  "auto"   - wszystkie bramki zielone: scalenie i wdrozenie bez czlowieka,
  "pr"     - poprawka moze byc dobra, ale dotyka strefy zakazanej albo jest
             za duza: zostaje jako pull request z opisem dla wlasciciela,
  "odrzuc" - poprawka nie dowodzi naprawy (brak testu regresji, czerwone
             testy, wyciszone albo usuniete testy): bez pull requestu.

Agent nie moze zmienic tego pliku (strefa zakazana), wiec nie oslabi bramek.

Uzycie: python scripts/samonaprawa/bramki.py --baza <sha> --raport raport.json --wynik bramki.json
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Repozytorium z poprawka. Workflow uruchamia bramki z kopii sprzed zmian
# agenta (agent nie podmieni skryptu), wiec katalog podajemy jawnie.
KORZEN = Path(os.getenv("SAMONAPRAWA_REPO") or Path(__file__).resolve().parents[2])

# Decyzja wlasciciela 23.11.2026: logowanie i platnosci sa CALKOWICIE poza
# samonaprawa - zmiana tam = odrzucenie (bez pull requestu). Zmiany kodu w tych
# miejscach robi tylko zespol notarai.
STREFY_WYKLUCZONE = [
    "autoryzacja.py", "logowanie.py", "rejestracja.py", "urzadzenia.py",
    "platnosci.py", "tokenomia.py",
]
# Tresc prawna, taksa i dane osobowe: notariusz moze je zmieniac swoja prosba
# (asystent kancelarii) - wtedy wchodza automatycznie. Poprawka bledu, o ktora
# nikt nie prosil, idzie tu jako pull request do wlasciciela.
STREFY_NOTARIUSZA = [
    "prompty.py", "zasady.py", "styl.py", "personalizacja.py", "klauzule.py", "taksa.py",
    "kalkulator.py", "dokumenty_prawne.py", "formularze/*", "giif.py", "giif_xml.py", "giif_xsd/*",
    "aml*.py", "osoby.py", "walidacja.py", "poswiadczenia.py",
]
# Zawsze pull request: sama samonaprawa (agent nie oslabia wlasnych bramek),
# zabezpieczenia RODO (maskowanie logow, magazyn danych) i infrastruktura.
STREFY_ZAKAZANE = [
    "scripts/samonaprawa/*", "samonaprawa.py", ".github/*", "conftest.py", "pytest.ini",
    "test_zgodnosc_sdk.py", "test_samonaprawa.py", "CLAUDE.md",
    "dziennik.py", "dziennik_serwisu.py", "magazyn.py",
    "infra/*", "Dockerfile", ".dockerignore", "confidential/*", ".env*",
]
MAX_PLIKOW = 10
MAX_LINII = 400
# Wyciszanie testow zamiast naprawy.
_WYCISZANIE = re.compile(
    r"pytest\.mark\.(skip|skipif|xfail)|pytest\.(skip|xfail|importorskip)\(|unittest\.skip|"
    r"#\s*noqa:\s*samonaprawa|except\s+Exception\s*:\s*pass")
_TEST = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w+)", re.M)


def _git(*argumenty: str, cwd: Path | None = None) -> str:
    return subprocess.run(["git", *argumenty], cwd=cwd or KORZEN, check=True,
                          capture_output=True, text=True).stdout


def zmienione(baza: str) -> list[tuple[str, str]]:
    """[(status, sciezka)] miedzy baza a HEAD (A/M/D/R...)."""
    wynik = []
    for linia in _git("diff", "--name-status", "-M", baza, "HEAD").splitlines():
        czesci = linia.split("\t")
        status = czesci[0][0]
        wynik.append((status, czesci[-1]))
        if status == "R":
            wynik.append(("D", czesci[1]))
    return wynik


def _pasuje(sciezka: str, wzorce: list[str]) -> bool:
    return any(fnmatch.fnmatch(sciezka, wzor) for wzor in wzorce)


def w_strefie_zakazanej(sciezka: str) -> bool:
    return _pasuje(sciezka, STREFY_ZAKAZANE)


def w_strefie_wykluczonej(sciezka: str) -> bool:
    return _pasuje(sciezka, STREFY_WYKLUCZONE)


def w_strefie_notariusza(sciezka: str) -> bool:
    return _pasuje(sciezka, STREFY_NOTARIUSZA)


def _plik_w(baza: str, sciezka: str) -> str | None:
    try:
        return _git("show", f"{baza}:{sciezka}")
    except subprocess.CalledProcessError:
        return None


def _czy_test(sciezka: str) -> bool:
    nazwa = Path(sciezka).name
    return nazwa.startswith("test_") and nazwa.endswith(".py")


def kontrola_testow(baza: str, pliki: list[tuple[str, str]]) -> list[str]:
    """Usuniete testy albo dopisane wyciszenia - powody odrzucenia."""
    powody = []
    for status, sciezka in pliki:
        if not _czy_test(sciezka):
            continue
        przed = _plik_w(baza, sciezka) or ""
        po = "" if status == "D" else (KORZEN / sciezka).read_text(encoding="utf-8")
        brakuje = set(_TEST.findall(przed)) - set(_TEST.findall(po))
        if brakuje:
            powody.append(f"usuniete testy w {sciezka}: {', '.join(sorted(brakuje))}")
    dopisane = [l[1:] for l in _git("diff", "-U0", baza, "HEAD").splitlines()
                if l.startswith("+") and not l.startswith("+++")]
    for linia in dopisane:
        if _WYCISZANIE.search(linia):
            powody.append(f"dopisane wyciszenie: {linia.strip()[:120]}")
    return powody


def rozmiar(baza: str) -> tuple[int, int]:
    pliki, linie = 0, 0
    for wiersz in _git("diff", "--numstat", baza, "HEAD").splitlines():
        dodane, usuniete, _ = wiersz.split("\t", 2)
        pliki += 1
        linie += (int(dodane) if dodane.isdigit() else 0) + (int(usuniete) if usuniete.isdigit() else 0)
    return pliki, linie


def _pytest(argumenty: list[str], cwd: Path, czas: int = 1500) -> int:
    srodowisko = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proces = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *argumenty],
                            cwd=cwd, env=srodowisko, timeout=czas)
    return proces.returncode


def dowod_regresji(baza: str, testy: list[str], pliki: list[tuple[str, str]]) -> list[str]:
    """Test regresji: czerwony na kodzie bazowym (z nowymi testami), zielony po poprawce.

    Kod pytest 1 = testy oblane. Blad zbierania (2), brak testow (5) itp. nie
    dowodzi, ze test odtwarza zgloszony blad.
    """
    if not testy:
        return ["brak testu regresji w raporcie agenta"]
    zle = [t for t in testy if not re.fullmatch(r"[\w./-]+\.py(::[\w\[\]-]+)+", t)]
    if zle:
        return [f"niepoprawny identyfikator testu: {zle[0][:80]}"]
    if any(not _czy_test(t.split("::")[0]) for t in testy):
        return ["test regresji musi byc w pliku test_*.py"]
    if _pytest(testy, KORZEN) != 0:
        return ["test regresji nie przechodzi po poprawce"]
    powody = []
    with tempfile.TemporaryDirectory() as tmp:
        stary = Path(tmp) / "baza"
        _git("worktree", "add", "--detach", str(stary), baza)
        try:
            # Do starego kodu przenosimy tylko testy (nowe i zmienione).
            for status, sciezka in pliki:
                if status != "D" and _czy_test(sciezka):
                    cel = stary / sciezka
                    cel.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(KORZEN / sciezka, cel)
            kod = _pytest(testy, stary)
            if kod != 1:
                powody.append(f"test regresji nie oblewa kodu sprzed poprawki (pytest={kod}) - "
                              "nie dowodzi, ze odtwarza zgloszony blad")
        finally:
            _git("worktree", "remove", "--force", str(stary))
    return powody


def ocen(baza: str, raport: dict, pelne_testy: bool = True, prosba: bool = False) -> dict:
    """`prosba` = zmiana na prosbe notariusza (asystent kancelarii)."""
    pliki = zmienione(baza)
    odrzuc, tylko_pr = [], []
    if not pliki:
        odrzuc.append("agent nie zmienil zadnego pliku")
    wykluczone = sorted({s for _, s in pliki if w_strefie_wykluczonej(s)})
    if wykluczone:
        odrzuc.append("logowanie i platnosci sa poza samonaprawa (zmienia je tylko zespol notarai): "
                      + ", ".join(wykluczone))
    odrzuc += kontrola_testow(baza, pliki)
    if not odrzuc:
        odrzuc += dowod_regresji(baza, list(raport.get("testy_regresji") or []), pliki)
    if not odrzuc and pelne_testy and _pytest([], KORZEN) != 0:
        odrzuc.append("pelny zestaw testow nie przechodzi")
    zakazane = sorted({s for _, s in pliki if w_strefie_zakazanej(s)})
    if zakazane:
        tylko_pr.append("strefa zakazana: " + ", ".join(zakazane))
    notariusza = sorted({s for _, s in pliki if w_strefie_notariusza(s)})
    if notariusza and not prosba:
        tylko_pr.append("tresc prawna / taksa / dane osobowe bez prosby notariusza: " + ", ".join(notariusza))
    ile_plikow, ile_linii = rozmiar(baza) if pliki else (0, 0)
    if ile_plikow > MAX_PLIKOW or ile_linii > MAX_LINII:
        tylko_pr.append(f"poprawka za duza do automatu ({ile_plikow} plikow, {ile_linii} linii)")
    ryzyko = str(raport.get("ryzyko", "")).lower()
    if ryzyko not in ("niskie", "low"):
        tylko_pr.append(f"agent ocenia ryzyko jako: {ryzyko or 'brak oceny'}")
    werdykt = "odrzuc" if odrzuc else ("pr" if tylko_pr else "auto")
    return {"werdykt": werdykt, "odrzucenie": odrzuc, "tylko_pr": tylko_pr,
            "pliki": [s for _, s in pliki], "linie": ile_linii}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baza", required=True)
    parser.add_argument("--raport", required=True)
    parser.add_argument("--wynik", required=True)
    parser.add_argument("--bez-pelnych-testow", action="store_true")
    parser.add_argument("--repo", help="katalog repozytorium (domyslnie SAMONAPRAWA_REPO)")
    parser.add_argument("--prosba", action="store_true", help="zmiana na prosbe notariusza")
    args = parser.parse_args()
    global KORZEN
    if args.repo:
        KORZEN = Path(args.repo).resolve()
    try:
        raport = json.loads(Path(args.raport).read_text(encoding="utf-8"))
        if not isinstance(raport, dict):
            raise ValueError("raport nie jest obiektem")
    except (OSError, ValueError) as e:
        raport = {}
        wynik = {"werdykt": "odrzuc", "odrzucenie": [f"brak lub zly raport agenta ({type(e).__name__})"],
                 "tylko_pr": [], "pliki": [], "linie": 0}
    else:
        wynik = ocen(args.baza, raport, pelne_testy=not args.bez_pelnych_testow, prosba=args.prosba)
    Path(args.wynik).write_text(json.dumps(wynik, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(wynik, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
