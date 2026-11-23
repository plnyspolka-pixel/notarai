"""Odbiór wyników przebiegu kodera z Workera notarai-koder i założenie gałęzi agent/* gitem.

Potrzebny, dopóki Worker nie ma własnego GITHUB_TOKEN (wtedy wypycha gałęzie sam). Uruchamiasz
w sesji, która może pushować do repozytorium (np. Claude Code), w katalogu klonu:

  KODER_TOKEN_PLIK=<plik z tokenem> python3 tools/agent_factory/koder/odbierz.py <przebieg> [--push]

Token: ten sam, którym robisz POST /start (token z public.render_tokens, zakres gpu:salad).
Bez --push tylko zakłada gałęzie lokalnie i wypisuje, co zrobił. Nie rusza bieżącej gałęzi
ani drzewa roboczego (commity powstają przez `git commit-tree` na osobnym indeksie).
"""
from __future__ import annotations

import base64
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

WORKER = os.environ.get("KODER_WORKER", "https://notarai-koder.financeyou.workers.dev")


def git(*args: str, env: dict | None = None, wejscie: bytes | None = None) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, input=wejscie,
                          env={**os.environ, **(env or {})}).stdout.decode().strip()


def galaz(nazwa: str, baza: str, pliki: dict, wiadomosc: str, przedrostek: str = "") -> str:
    with tempfile.TemporaryDirectory() as tmp:
        idx = {"GIT_INDEX_FILE": str(Path(tmp) / "index"),
               "GIT_AUTHOR_NAME": "koder (agent)", "GIT_AUTHOR_EMAIL": "koder@users.noreply.github.com",
               "GIT_COMMITTER_NAME": "koder (agent)", "GIT_COMMITTER_EMAIL": "koder@users.noreply.github.com"}
        git("read-tree", baza, env=idx)
        for sciezka, b64 in pliki.items():
            p = przedrostek + sciezka
            if ".." in p.split("/") or p.startswith("/") or ".git" in p.split("/"):
                raise SystemExit(f"zła ścieżka {p}")
            if b64 is None:
                git("update-index", "--force-remove", "--", p, env=idx)
                continue
            blob = git("hash-object", "-w", "--stdin", wejscie=base64.b64decode(b64))
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{p}", env=idx)
        drzewo = git("write-tree", env=idx)
        commit = git("commit-tree", drzewo, "-p", baza, "-m", wiadomosc, env=idx)
        git("update-ref", f"refs/heads/{nazwa}", commit)
        return commit


def main(argv: list[str]) -> int:
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    przebieg, push = argv[0], "--push" in argv
    token = Path(os.environ["KODER_TOKEN_PLIK"]).read_text().strip()
    req = urllib.request.Request(f"{WORKER}/wyniki/{przebieg}", headers={"x-webhook-secret": token, "user-agent": "notarai-koder-odbierz/1"})  # Cloudflare odrzuca domyślny UA urllib
    with urllib.request.urlopen(req, timeout=120) as r:
        dane = json.loads(gzip.decompress(r.read()))
    baza = dane["sha"]
    git("cat-file", "-e", baza + "^{commit}")
    galezie = []
    for g in dane.get("galezie") or []:
        galezie.append((g["galaz"], galaz(g["galaz"], baza, g["pliki"], g["wiadomosc"])))
    wyn = f"agent/{przebieg}-wyniki"
    galezie.append((wyn, galaz(wyn, baza, dane.get("wyniki") or {}, f"koder: wyniki przebiegu {przebieg} ({dane.get('model')})",
                               f"docs/agent-tasks/wyniki/{przebieg}/")))
    for nazwa, sha in galezie:
        print(f"{nazwa} {sha[:10]}")
        if push:
            git("push", "-q", "origin", f"refs/heads/{nazwa}:refs/heads/{nazwa}")
    if dane.get("stan", {}).get("blad"):
        print("BŁĄD węzła:", dane["stan"]["blad"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
