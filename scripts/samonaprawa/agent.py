"""Uruchamianie agentow (naprawczego i recenzenta) i bramek w odizolowanym srodowisku.

Zamiast OIDC GitHuba (poswiadczenia.sh): rola CodeBuild przyjmuje osobna role
notarai-samonaprawa-agent z polityka SESJI zawezajaca ja do wywolan modeli
Bedrock. Proces agenta dostaje WYLACZNIE te poswiadczenia sesji: srodowisko
budujemy od zera (nie dziedziczy poswiadczen roli CodeBuild, adresu
AWS_CONTAINER_CREDENTIALS_*, tokenow ani sekretow).

Gdy potok dziala jako root i ustawiono SN_AGENT_UZYTKOWNIK, proces agenta (i testy
bramek) idzie jako ten nieuprzywilejowany uzytkownik: nie przeczyta /proc/<pid>/environ
procesu potoku.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROLA_AGENTA = "arn:aws:iam::127621462971:role/notarai-samonaprawa-agent"
DOMYSLNY_MODEL = "eu.anthropic.claude-opus-4-6-v1"
# Sesja agenta: tylko wywolania modeli (to samo co dawne poswiadczenia.sh agent).
POLITYKA_SESJI = {
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow",
                   "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream",
                              "bedrock:GetInferenceProfile", "bedrock:ListInferenceProfiles"],
                   "Resource": "*"}],
}
NARZEDZIA_ZABRONIONE_NAPRAWA = "WebFetch,WebSearch"
NARZEDZIA_ZABRONIONE_RECENZJA = "WebFetch,WebSearch,Edit,Write,NotebookEdit"
# Zmienne, ktore wolno przekazac z procesu potoku do agenta i bramek (niczego wiecej).
_PRZEPUSZCZANE = ("PATH", "LANG", "LC_ALL")


def sesja_agenta(sts, rola: str = ROLA_AGENTA, nazwa: str = "samonaprawa-agent", sekund: int = 3600) -> dict:
    """assume-role z polityka sesji. Zwraca zmienne srodowiska z poswiadczeniami sesji."""
    odp = sts.assume_role(RoleArn=rola, RoleSessionName=nazwa[:60], DurationSeconds=sekund,
                          Policy=json.dumps(POLITYKA_SESJI))
    k = odp["Credentials"]
    return {"AWS_ACCESS_KEY_ID": k["AccessKeyId"], "AWS_SECRET_ACCESS_KEY": k["SecretAccessKey"],
            "AWS_SESSION_TOKEN": k["SessionToken"]}


def srodowisko_czyste(dom: str, dodatkowe: dict | None = None, bazowe: dict | None = None) -> dict:
    """Srodowisko od zera: PATH/LANG + HOME + to, co jawnie podano. Zadnych AWS_*."""
    zrodlo = os.environ if bazowe is None else bazowe
    env = {k: zrodlo[k] for k in _PRZEPUSZCZANE if k in zrodlo}
    env.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    env.setdefault("LANG", "C.UTF-8")
    env.update({"HOME": dom, "PYTHONDONTWRITEBYTECODE": "1", "AWS_EC2_METADATA_DISABLED": "true",
                "AWS_REGION": "eu-central-1", "AWS_DEFAULT_REGION": "eu-central-1"})
    env.update(dodatkowe or {})
    return env


def srodowisko_agenta(sesja: dict, dom: str, model: str, pliki: dict, bazowe: dict | None = None) -> dict:
    """Poswiadczenia sesji Bedrock + ustawienia Claude Code + sciezki plikow zgloszenia/raportu."""
    return srodowisko_czyste(dom, {
        **sesja, "CLAUDE_CODE_USE_BEDROCK": "1", "ANTHROPIC_MODEL": model,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": model, "ANTHROPIC_SMALL_FAST_MODEL": model,
        "DISABLE_TELEMETRY": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", **pliki}, bazowe)


def _uzytkownik(env: dict) -> dict:
    nazwa = os.environ.get("SN_AGENT_UZYTKOWNIK", "")
    if nazwa and hasattr(os, "geteuid") and os.geteuid() == 0:
        return {"user": nazwa}
    return {}


def uruchom_agenta(polecenie: str, env: dict, cwd: Path, wyjscie: Path, zabronione: str, max_tur: int,
                   limit_minut: int, uruchom=subprocess.run) -> int:
    """claude -p ... Zwraca kod wyjscia (-1 przy przekroczeniu czasu). Wynik JSON do pliku."""
    argumenty = ["claude", "-p", polecenie, "--permission-mode", "bypassPermissions",
                 "--disallowedTools", zabronione, "--max-turns", str(max_tur), "--output-format", "json"]
    with open(wyjscie, "w", encoding="utf-8") as f:
        try:
            return uruchom(argumenty, env=env, cwd=str(cwd), stdout=f, stderr=subprocess.STDOUT,
                           timeout=limit_minut * 60, **_uzytkownik(env)).returncode
        except subprocess.TimeoutExpired:
            return -1


def uruchom_bramki(narzedzia: Path, repo: Path, baza: str, raport: Path, wynik: Path, prosba: bool,
                   env: dict, uruchom=subprocess.run) -> int:
    """bramki.py bez zmian, z kopii narzedzi sprzed agenta; srodowisko bez poswiadczen AWS."""
    argumenty = ["python", str(narzedzia / "bramki.py"), "--repo", str(repo), "--baza", baza,
                 "--raport", str(raport), "--wynik", str(wynik)] + (["--prosba"] if prosba else [])
    try:
        return uruchom(argumenty, env=env, cwd=str(repo), timeout=3 * 3600, **_uzytkownik(env)).returncode
    except subprocess.TimeoutExpired:
        return -1
