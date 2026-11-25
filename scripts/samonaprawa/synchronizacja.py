"""Zapis poprawki z produkcji w repozytorium GitHub (best effort, nigdy twarda zaleznosc).

GitHub zostaje magazynem kodu, ale potok dziala bez niego. Po wdrozeniu i obserwacji
poprawka (format-patch z rejestru NAPRAWA) laduje w master tak:
  1. pliki z naglowkow patcha pobieramy z aktualnego master (API tresci),
  2. w katalogu tymczasowym: `git apply --check --reverse` zdrowy = poprawka JUZ jest w master,
     inaczej `git apply --index --3way` (nie przechodzi = zostaje w rejestrze, mail),
  3. blobs/tree/commit na aktualnym master (Git Data API, bez protokolu git),
  4. galaz samonaprawa/<odcisk>-<ts>, pull request z etykieta, scalenie; komunikat
     scalenia zawiera [skip ci], zeby nie wyzwolic drugiego wdrozenia (poprawka jest
     juz na produkcji).
Token z sekretu notarai/samonaprawa-github (klucz token); brak lub "brak" = nie synchronizujemy.
Bledy tylko do logu i rejestru. Wpisy rejestru nigdy nie sa kasowane przy porazce.
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPOZYTORIUM = "plnyspolka-pixel/notarai"
API = "https://api.github.com"
SKIP_CI = "[skip ci]"
_NAGLOWEK = re.compile(r"^diff --git a/(.+?) b/(.+)$", re.M)


def token_z_sekretu(klient_sm, sekret: str = "notarai/samonaprawa-github") -> str:
    """Token z Secrets Manager (wartosc nigdy do logu). Pusty, gdy brak albo znacznik "brak"."""
    try:
        tresc = klient_sm.get_secret_value(SecretId=sekret)["SecretString"]
        token = str(json.loads(tresc).get("token", "")).strip()
    except Exception:  # noqa: BLE001 - brak sekretu/uprawnien = brak synchronizacji
        return ""
    return token if token.startswith(("github_pat_", "ghp_", "ghs_")) else ""


class Github:
    def __init__(self, token: str, repozytorium: str = REPOZYTORIUM, zadanie=None) -> None:
        self.token, self.repo = token, repozytorium
        self._zadanie = zadanie or self._http

    def _http(self, metoda: str, sciezka: str, dane: dict | None = None):
        zadanie = urllib.request.Request(
            API + sciezka, method=metoda, data=json.dumps(dane).encode() if dane is not None else None,
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(zadanie, timeout=30) as odp:
                tresc = odp.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"GitHub {metoda} {sciezka}: HTTP {e.code}") from None
        return json.loads(tresc) if tresc else None

    def api(self, metoda: str, sciezka: str, dane: dict | None = None):
        return self._zadanie(metoda, f"/repos/{self.repo}{sciezka}", dane)


def sciezki_z_patcha(patch: str) -> list[str]:
    wynik: list[str] = []
    for a, b in _NAGLOWEK.findall(patch):
        for s in (a, b):
            if s not in wynik:
                wynik.append(s)
    return wynik


def _git(katalog: Path, *argumenty: str, sprawdz: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "user.name=notarai-samonaprawa", "-c", "user.email=samonaprawa@notarai.pl",
                           *argumenty], cwd=katalog, capture_output=True, text=True, check=sprawdz)


def zastosuj_patch(katalog: Path, patch: str) -> str:
    """"juz" (poprawka jest w tych plikach), "ok" (zastosowano do indeksu) albo "konflikt"."""
    plik = katalog.parent / f"{katalog.name}.patch"
    plik.write_text(patch, encoding="utf-8")
    if _git(katalog, "apply", "--check", "--reverse", str(plik), sprawdz=False).returncode == 0:
        return "juz"
    if _git(katalog, "apply", "--index", "--3way", str(plik), sprawdz=False).returncode == 0:
        return "ok"
    return "konflikt"


def synchronizuj_poprawke(gh: Github, poprawka: dict, patch: str, teraz=time.time, ma_sie_polaczyc: bool = True) -> dict:
    """Jedna poprawka z rejestru -> master. {"wynik": "zsynchronizowane"|"juz"|"pr_otwarty"|"blad", ...}"""
    odcisk = poprawka["odcisk"]
    if poprawka.get("pr"):
        # Pull request z poprzedniej proby: nie zakladamy drugiego.
        try:
            pr = gh.api("GET", f"/pulls/{poprawka['pr']}")
            if pr.get("merged"):
                return {"wynik": "zsynchronizowane", "pr": poprawka["pr"]}
            if pr.get("state") == "open":
                gh.api("PUT", f"/pulls/{poprawka['pr']}/merge",
                       {"merge_method": "squash", "commit_title": f"Samonaprawa {odcisk} {SKIP_CI}", "commit_message": SKIP_CI})
                return {"wynik": "zsynchronizowane", "pr": poprawka["pr"]}
        except RuntimeError as e:
            return {"wynik": "pr_otwarty", "pr": poprawka["pr"], "powod": str(e)[:200]}
    ref = gh.api("GET", "/git/ref/heads/master")["object"]["sha"]
    komit = gh.api("GET", f"/git/commits/{ref}")
    with tempfile.TemporaryDirectory() as tmp:
        kat = Path(tmp) / "master"
        kat.mkdir()
        _git(kat, "init", "-q")
        for sciezka in sciezki_z_patcha(patch):
            try:
                tresc = gh.api("GET", f"/contents/{sciezka}?ref={ref}")
            except RuntimeError:
                continue    # plik nowy w poprawce - w master go nie ma
            cel = kat / sciezka
            cel.parent.mkdir(parents=True, exist_ok=True)
            cel.write_bytes(base64.b64decode(tresc["content"]))
        _git(kat, "add", "-A")
        _git(kat, "commit", "-q", "--allow-empty", "-m", "master")
        stan = zastosuj_patch(kat, patch)
        if stan == "juz":
            return {"wynik": "juz"}
        if stan != "ok":
            return {"wynik": "blad", "powod": "poprawka nie pasuje do obecnego master (konflikt)"}
        wpisy = []
        for linia in _git(kat, "diff", "--cached", "--name-status").stdout.splitlines():
            status, *nazwy = linia.split("\t")
            sciezka = nazwy[-1]
            if status.startswith("R"):
                wpisy.append({"path": nazwy[0], "mode": "100644", "type": "blob", "sha": None})
            if status == "D":
                wpisy.append({"path": sciezka, "mode": "100644", "type": "blob", "sha": None})
                continue
            tryb = _git(kat, "ls-files", "-s", "--", sciezka).stdout.split()[0]
            blob = gh.api("POST", "/git/blobs", {"content": base64.b64encode((kat / sciezka).read_bytes()).decode(),
                                                 "encoding": "base64"})["sha"]
            wpisy.append({"path": sciezka, "mode": tryb, "type": "blob", "sha": blob})
    drzewo = gh.api("POST", "/git/trees", {"base_tree": komit["tree"]["sha"], "tree": wpisy})["sha"]
    tytul = f"Samonaprawa {odcisk}: {poprawka.get('tytul') or 'poprawka bledu'}"[:200]
    wiadomosc = f"{tytul}\n\nPoprawka jest juz na produkcji (tag {poprawka.get('tag', '')}). {SKIP_CI}"
    nowy = gh.api("POST", "/git/commits", {"message": wiadomosc, "tree": drzewo, "parents": [ref]})["sha"]
    galaz = f"samonaprawa/{odcisk}-{time.strftime('%Y%m%d%H%M%S', time.gmtime(teraz()))}"
    gh.api("POST", "/git/refs", {"ref": f"refs/heads/{galaz}", "sha": nowy})
    pr = gh.api("POST", "/pulls", {"title": tytul, "head": galaz, "base": "master",
                                    "body": wiadomosc + "\n\nSamonaprawa notarai (docs/samonaprawa.md)."})
    numer = pr["number"]
    for etykieta in ("samonaprawa", "samonaprawa-auto"):
        try:
            gh.api("POST", f"/issues/{numer}/labels", {"labels": [etykieta]})
        except RuntimeError:
            pass
    if not ma_sie_polaczyc:
        return {"wynik": "pr_otwarty", "pr": numer, "galaz": galaz}
    try:
        gh.api("PUT", f"/pulls/{numer}/merge", {"merge_method": "squash", "commit_title": tytul + " " + SKIP_CI,
                                                 "commit_message": SKIP_CI})
    except RuntimeError as e:
        return {"wynik": "pr_otwarty", "pr": numer, "galaz": galaz, "powod": str(e)[:200]}
    return {"wynik": "zsynchronizowane", "pr": numer, "galaz": galaz}


def synchronizuj_wszystkie(stan, s3_pobierz, gh_fabryka, powiadom, teraz=time.time) -> list[dict]:
    """Rejestr NAPRAWA po kolei. Po pierwszej porazce stop (kolejne poprawki bywaja od niej zalezne).

    gh_fabryka() -> Github | None (None = brak tokenu); s3_pobierz(klucz) -> tresc patcha.
    """
    wyniki: list[dict] = []
    oczekujace = stan.poprawki_do_synchronizacji()
    if not oczekujace:
        return wyniki
    gh = gh_fabryka()
    for p in oczekujace:
        proby = int(p.get("proby_synchronizacji", 0)) + 1
        if gh is None:
            wynik = {"wynik": "blad", "powod": "brak tokenu GitHub w sekrecie notarai/samonaprawa-github"}
        else:
            try:
                wynik = synchronizuj_poprawke(gh, p, s3_pobierz(p["patch_klucz"]), teraz)
            except Exception as e:  # noqa: BLE001 - synchronizacja nigdy nie psuje potoku
                wynik = {"wynik": "blad", "powod": f"{type(e).__name__}: {str(e)[:200]}"}
        wyniki.append({"id": p["id"], **wynik})
        if wynik["wynik"] in ("zsynchronizowane", "juz"):
            stan.status_poprawki(p["id"], "zsynchronizowane", pr=wynik.get("pr", 0), wynik_synchronizacji=wynik["wynik"])
            continue
        stan.status_poprawki(p["id"], "do_zsynchronizowania", proby_synchronizacji=proby,
                             powod_synchronizacji=wynik.get("powod", wynik["wynik"]), pr=wynik.get("pr", 0))
        if proby == 1 or proby % 48 == 0:
            powiadom("notarai: poprawka na produkcji, ale nie zapisana w repozytorium",
                     f"Poprawka bledu {p['odcisk']} (wersja {p.get('tag', '')}) jest na produkcji, ale nie zapisana "
                     f"w repozytorium ({wynik.get('powod') or 'wymaga scalenia pull requestu ' + str(wynik.get('pr', ''))}). "
                     "Zwykle wdrozenia z GitHuba i tak dokladaja ja przez straznika, ale zapisz ja w repozytorium: "
                     "scal pull request z etykieta samonaprawa albo napisz do zespolu notarai. Rejestr: tabela "
                     "notarai-samonaprawa, rekord NAPRAWA.")
        break
    return wyniki
