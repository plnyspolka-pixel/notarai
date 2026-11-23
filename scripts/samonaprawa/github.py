"""GitHub dla samonaprawy: zgloszenia (issues), limity, pull requesty, wdrozenie.

Token: GH_TOKEN (token samonaprawy z Secrets Manager albo GITHUB_TOKEN).
Repozytorium: GITHUB_REPOSITORY.

Podkomendy:
  decyzja   --zgloszenie z.json --wynik d.json [--tryb auto|pr|wylaczona]
  komentarz --issue N --plik tresc.md
  etykieta  --issue N --dodaj nazwa
  zamknij   --issue N
  pr        --galaz G --tytul T --opis-plik o.md [--etykieta e]...   -> numer PR
  scal      --pr N --sha SHA                                          -> sha scalenia
  wdrozenie --sha SHA [--minut 60]                                    -> JSON {wynik, koniec_ms}
  wyzwol    --workflow plik.yml
  wybierz   --kandydaci k.json --wynik w.json                         -> odcisk albo pusto
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://api.github.com"
ETYKIETA = "samonaprawa"
ETYKIETA_AUTO = "samonaprawa-auto"
ETYKIETA_ESKALACJA = "samonaprawa-eskalacja"
ZNACZNIK_PROBY = "<!-- samonaprawa-proba -->"
# Ile prob naprawy jednego bledu, zanim automat odda go wlascicielowi.
MAX_PROB = 2
# Ile automatycznych wdrozen na dobe - powyzej poprawki ida jako pull requesty.
MAX_AUTO_NA_DOBE = 3


def _repo() -> str:
    return os.environ["GITHUB_REPOSITORY"]


def api(metoda: str, sciezka: str, dane: dict | None = None):
    zadanie = urllib.request.Request(
        API + sciezka, method=metoda,
        data=json.dumps(dane).encode() if dane is not None else None,
        headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(zadanie, timeout=30) as odp:
            tresc = odp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub {metoda} {sciezka}: HTTP {e.code} {e.read()[:300]!r}") from None
    return json.loads(tresc) if tresc else None


def tytul_zgloszenia(odcisk: str) -> str:
    return f"[samonaprawa] {odcisk}"


def znajdz_zgloszenie(odcisk: str) -> dict | None:
    wynik = api("GET", f"/repos/{_repo()}/issues?labels={ETYKIETA}&state=all&per_page=100")
    for issue in wynik or []:
        if "pull_request" not in issue and issue["title"].startswith(tytul_zgloszenia(odcisk)):
            return issue
    return None


def _opis_zgloszenia(z: dict) -> str:
    historia = z.get("historia") or {}
    return "\n".join([
        f"Błąd wykryty automatycznie na produkcji (samonaprawa, `{z['odcisk']}`).",
        "",
        f"- **Rodzaj:** {z['rodzaj']}",
        f"- **Błąd:** `{z['typ']}` {('`' + z['kod_aws'] + '`') if z['kod_aws'] else ''}",
        f"- **Gdzie:** {z.get('endpoint') or '-'}",
        f"- **Wersja:** `{z['wersja']}`",
        f"- **Wystąpień (7 dni):** {historia.get('wystapien_7_dni', '?')}",
        "",
        "Miejsca w kodzie:",
        *[f"- `{m}`" for m in z["miejsca"]],
        "",
        "Opis (bez danych klientów):",
        f"```\n{z['opis']}\n```",
        *([f"\nUwagi zgłaszającego:\n> {z['uwagi']}"] if z.get("uwagi") else []),
        "",
        "Przebieg naprawy: komentarze poniżej. Zasady: `docs/samonaprawa.md`.",
    ])


def _etykiety() -> None:
    for nazwa, kolor in ((ETYKIETA, "0e8a16"), (ETYKIETA_AUTO, "1d76db"), (ETYKIETA_ESKALACJA, "d93f0b")):
        try:
            api("POST", f"/repos/{_repo()}/labels", {"name": nazwa, "color": kolor})
        except RuntimeError:
            pass   # juz jest


def decyzja(z: dict, tryb: str) -> dict:
    """Czy naprawiac, w jakim trybie i w ktorym zgloszeniu (issue)."""
    _etykiety()
    issue = znajdz_zgloszenie(z["odcisk"])
    nowe = issue is None
    if nowe:
        issue = api("POST", f"/repos/{_repo()}/issues", {
            "title": f"{tytul_zgloszenia(z['odcisk'])} {z['typ']} {z.get('endpoint', '')}".strip()[:200],
            "body": _opis_zgloszenia(z), "labels": [ETYKIETA]})
    elif issue["state"] == "closed":
        # Blad wrocil po zamknieciu (np. po naprawie) - otwieramy ponownie.
        api("PATCH", f"/repos/{_repo()}/issues/{issue['number']}", {"state": "open"})
    numer = issue["number"]
    etykiety = {e["name"] for e in issue.get("labels", [])}
    komentarze = api("GET", f"/repos/{_repo()}/issues/{numer}/comments?per_page=100") or []
    proby = sum(1 for k in komentarze if ZNACZNIK_PROBY in (k.get("body") or ""))
    wynik = {"issue": numer, "nowe": nowe, "proby": proby, "tryb": tryb, "dzialanie": "napraw", "powody": []}

    if tryb == "wylaczona":
        wynik.update(dzialanie="tylko_zglos", powody=["samonaprawa wylaczona (zmienna SAMONAPRAWA)"])
    elif z["rodzaj"] == "przejsciowy":
        wynik.update(dzialanie="tylko_zglos", powody=["blad przejsciowy (AWS/siec) - nie naprawia sie go kodem"])
    elif ETYKIETA_ESKALACJA in etykiety:
        wynik.update(dzialanie="tylko_zglos", powody=["blad oddany wlascicielowi (eskalacja)"])
    elif proby >= MAX_PROB:
        wynik.update(dzialanie="eskaluj", powody=[f"{proby} nieudane proby naprawy"])
    elif _otwarty_pr(z["odcisk"]):
        wynik.update(dzialanie="tylko_zglos", powody=["poprawka tego bledu czeka juz jako pull request"])
    elif tryb == "auto" and _auto_w_dobie() >= MAX_AUTO_NA_DOBE:
        wynik.update(tryb="pr", powody=[f"limit {MAX_AUTO_NA_DOBE} automatycznych wdrozen na dobe"])
    return wynik


def _otwarty_pr(odcisk: str) -> bool:
    prs = api("GET", f"/repos/{_repo()}/pulls?state=open&per_page=100") or []
    return any(p["head"]["ref"].startswith(f"samonaprawa/{odcisk}-") for p in prs)


def _auto_w_dobie() -> int:
    od = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    prs = api("GET", f"/repos/{_repo()}/pulls?state=closed&sort=updated&direction=desc&per_page=50") or []
    return sum(1 for p in prs if p.get("merged_at") and p["merged_at"] >= od
               and any(e["name"] == ETYKIETA_AUTO for e in p.get("labels", [])))


def wybierz(kandydaci: list[dict]) -> dict | None:
    """Pierwszy blad z przegladu, ktorym warto sie zajac: bez eskalacji i bez
    czekajacej poprawki. Zamkniete zgloszenie z nawrotem bledu bierzemy ponownie."""
    for k in kandydaci:
        issue = znajdz_zgloszenie(k["odcisk"])
        if issue is None:
            return k
        etykiety = {e["name"] for e in issue.get("labels", [])}
        if ETYKIETA_ESKALACJA in etykiety or _otwarty_pr(k["odcisk"]):
            continue
        return k
    return None


def utworz_pr(galaz: str, tytul: str, opis: str, etykiety: list[str]) -> int:
    pr = api("POST", f"/repos/{_repo()}/pulls",
             {"title": tytul[:250], "head": galaz, "base": "master", "body": opis})
    if etykiety:
        api("POST", f"/repos/{_repo()}/issues/{pr['number']}/labels", {"labels": etykiety})
    return pr["number"]


def scal(pr: int, sha: str) -> str:
    wynik = api("PUT", f"/repos/{_repo()}/pulls/{pr}/merge",
                {"merge_method": "merge", "sha": sha,
                 "commit_title": f"Samonaprawa: scalenie #{pr} (automatycznie, po bramkach)"})
    return wynik["sha"]


def czekaj_na_wdrozenie(sha: str, minut: int) -> dict:
    """Czeka na workflow wdrozenia dla commita na master. Wynik i czas konca."""
    koniec = time.time() + minut * 60
    while time.time() < koniec:
        przebiegi = api("GET", f"/repos/{_repo()}/actions/workflows/wdrozenie.yml/runs"
                               f"?branch=master&head_sha={sha}&per_page=10") or {}
        for p in przebiegi.get("workflow_runs", []):
            if p["status"] == "completed" and p["conclusion"] != "skipped":
                kiedy = datetime.strptime(p["updated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                return {"wynik": p["conclusion"], "koniec_ms": int(kiedy.timestamp() * 1000),
                        "url": p["html_url"]}
        time.sleep(30)
    return {"wynik": "timeout", "koniec_ms": int(time.time() * 1000), "url": ""}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="komenda", required=True)
    p = sub.add_parser("decyzja"); p.add_argument("--zgloszenie", required=True)
    p.add_argument("--wynik", required=True); p.add_argument("--tryb", default="auto")
    p = sub.add_parser("komentarz"); p.add_argument("--issue", type=int, required=True)
    p.add_argument("--plik", required=True)
    p = sub.add_parser("etykieta"); p.add_argument("--issue", type=int, required=True)
    p.add_argument("--dodaj", required=True)
    p = sub.add_parser("zamknij"); p.add_argument("--issue", type=int, required=True)
    p = sub.add_parser("pr"); p.add_argument("--galaz", required=True); p.add_argument("--tytul", required=True)
    p.add_argument("--opis-plik", required=True); p.add_argument("--etykieta", action="append", default=[])
    p = sub.add_parser("scal"); p.add_argument("--pr", type=int, required=True); p.add_argument("--sha", required=True)
    p = sub.add_parser("wdrozenie"); p.add_argument("--sha", required=True); p.add_argument("--minut", type=int, default=60)
    p = sub.add_parser("wyzwol"); p.add_argument("--workflow", required=True)
    p = sub.add_parser("wybierz"); p.add_argument("--kandydaci", required=True)
    p.add_argument("--wynik", required=True)
    a = parser.parse_args()

    if a.komenda == "decyzja":
        tryb = a.tryb if a.tryb in ("auto", "pr", "wylaczona") else "auto"
        wynik = decyzja(json.loads(Path(a.zgloszenie).read_text(encoding="utf-8")), tryb)
        Path(a.wynik).write_text(json.dumps(wynik, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(wynik, ensure_ascii=False))
    elif a.komenda == "komentarz":
        api("POST", f"/repos/{_repo()}/issues/{a.issue}/comments",
            {"body": Path(a.plik).read_text(encoding="utf-8")[:60000]})
    elif a.komenda == "etykieta":
        api("POST", f"/repos/{_repo()}/issues/{a.issue}/labels", {"labels": [a.dodaj]})
    elif a.komenda == "zamknij":
        api("PATCH", f"/repos/{_repo()}/issues/{a.issue}", {"state": "closed", "state_reason": "completed"})
    elif a.komenda == "pr":
        print(utworz_pr(a.galaz, a.tytul, Path(a.opis_plik).read_text(encoding="utf-8"), a.etykieta))
    elif a.komenda == "scal":
        print(scal(a.pr, a.sha))
    elif a.komenda == "wdrozenie":
        print(json.dumps(czekaj_na_wdrozenie(a.sha, a.minut)))
    elif a.komenda == "wybierz":
        wybrany = wybierz(json.loads(Path(a.kandydaci).read_text(encoding="utf-8")))
        Path(a.wynik).write_text(json.dumps(wybrany or {}, ensure_ascii=False), encoding="utf-8")
        print(wybrany["odcisk"] if wybrany else "")
    elif a.komenda == "wyzwol":
        api("POST", f"/repos/{_repo()}/actions/workflows/{a.workflow}/dispatches", {"ref": "master"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
