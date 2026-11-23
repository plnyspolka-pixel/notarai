#!/usr/bin/env python3
"""Twarda reguła: ŻADNEGO renderu na GitHub Actions (rolki, Komputerku / Kancelaria pod Siódemką,
scenografia, głos, klipy GPU). Rendery idą wyłącznie przez Cloudflare (finyou-render) i
wynajęte GPU zlecane spoza GitHuba (brama salad-brama). Decyzja właściciela z 23.11.2026.

Skrypt sprawdza każdy plik w .github/workflows/ i kończy się kodem 1, jeśli którykolwiek
uruchamia narzędzia renderujące albo generujące media. Uruchamiany przez
.github/workflows/zakaz-renderu-gha.yml na każdym pushu (każda gałąź) i w każdym PR.

    python3 -I tools/zakaz_renderu_gha.py            # sprawdzenie repo
    python3 -I tools/zakaz_renderu_gha.py --test     # samotest wzorców

Wyjątków nie ma. Jeśli coś tu blokuje, przenieś to na Cloudflare, nie dopisuj wyjątku.
"""
from __future__ import annotations

import pathlib
import re
import sys

# Wzorce szukane w treści workflow (po usunięciu komentarzy), bez rozróżniania wielkości liter.
ZAKAZANE: dict[str, str] = {
    r"\bffmpeg\b|\bffprobe\b": "montaż/transkodowanie wideo (ffmpeg)",
    r"\bblender\b|\bbpy\b|scenografia/(zbuduj|sety)": "render 3D (Blender)",
    r"\bremotion\b": "render wideo (Remotion)",
    r"comfyui|\bcomfy\b": "generacja obrazu/wideo (ComfyUI)",
    r"ai-clip(\.mjs)?\s+(run|open)\b|ai-clip/ai-clip\.mjs\s+(run|open)": "klipy AI na GPU (ai-clip run/open)",
    r"odcinek-cf|rolki/[\w./-]*\.mjs|montaz|montaż": "montaż odcinków i rolek",
    r"tools[./]fabryka|fabryka\s+(dzien|render|glosy|gpu)": "fabryka odcinków",
    r"infinitetalk|\bltx[-_]?\d|qwen-image|wan2|flux": "modele wideo/obrazu",
    r"salad-brama|salad\.com/api|api\.salad\.com|portal\.salad": "wynajem GPU (Salad)",
    r"elevenlabs|text-to-speech|\btts\b": "generacja głosu",
    r"heygen|fal\.ai|fal-ai|replicate\.com|runwayml": "zewnętrzne generatory mediów",
    r"finyou-render\.[\w.-]+/zadanie": "zlecanie renderu Cloudflare z GitHuba",
}

# Nazwy plików workflow, które same w sobie oznaczają render.
ZAKAZANE_NAZWY = re.compile(r"render|ai-clip\.ya?ml$|klip|rolk|montaz|scenograf|wideo|video|odcin|fabryk", re.I)

# Ten plik i workflow strażnika wolno nazywać i opisywać renderem.
WLASNE = {"zakaz-renderu-gha.yml"}


def bez_komentarzy(tekst: str) -> str:
    wiersze = []
    for w in tekst.splitlines():
        s = w.lstrip()
        if s.startswith("#"):
            continue
        # komentarz na końcu wiersza (spacja + #), poza wyrażeniami ${{ }}
        w = re.sub(r"\s#\s.*$", "", w)
        wiersze.append(w)
    return "\n".join(wiersze)


def sprawdz_tekst(nazwa: str, tekst: str) -> list[str]:
    bledy = []
    if nazwa in WLASNE:
        return bledy
    if ZAKAZANE_NAZWY.search(nazwa):
        bledy.append(f"{nazwa}: nazwa wskazuje na render")
    czysty = bez_komentarzy(tekst)
    for wzor, opis in ZAKAZANE.items():
        m = re.search(wzor, czysty, re.I)
        if m:
            nr = czysty[: m.start()].count("\n") + 1
            bledy.append(f"{nazwa}:{nr}: {opis} ({m.group(0)!r})")
    return bledy


def sprawdz_repo(korzen: pathlib.Path) -> list[str]:
    katalog = korzen / ".github" / "workflows"
    bledy: list[str] = []
    if not katalog.is_dir():
        return bledy
    for p in sorted(katalog.iterdir()):
        if p.suffix.lower() in {".yml", ".yaml"}:
            bledy += sprawdz_tekst(p.name, p.read_text(encoding="utf-8", errors="replace"))
    return bledy


def samotest() -> None:
    zle = {
        "a.yml": "jobs:\n  x:\n    steps:\n      - run: sudo apt-get install -y ffmpeg\n",
        "b.yml": "steps:\n  - run: blender -b -P zbuduj.py\n",
        "c.yml": "steps:\n  - run: node services/ai-clip/ai-clip.mjs run job.json --pay\n",
        "d.yml": "steps:\n  - run: python -m tools.fabryka dzien\n",
        "e.yml": "steps:\n  - run: curl -X POST https://finyou-render.financeyou.workers.dev/zadanie\n",
        "scenografia-render.yml": "on: push\n",
        "f.yml": "steps:\n  - run: npx remotion render\n",
    }
    dobre = {
        "ci.yml": "# kiedyś tu był ffmpeg\nsteps:\n  - run: pytest\n",
        "zakaz-renderu-gha.yml": "steps:\n  - run: python3 tools/zakaz_renderu_gha.py  # blender ffmpeg\n",
        "deploy.yml": "steps:\n  - run: grep -E '\\.(png|mp4|webm)$' lista.txt\n",
    }
    for n, t in zle.items():
        assert sprawdz_tekst(n, t), f"samotest: {n} powinien być zablokowany"
    for n, t in dobre.items():
        assert not sprawdz_tekst(n, t), f"samotest: {n} nie powinien być zablokowany: {sprawdz_tekst(n, t)}"
    print("samotest OK")


def main() -> int:
    if "--test" in sys.argv:
        samotest()
        return 0
    korzen = pathlib.Path(__file__).resolve().parents[1]
    bledy = sprawdz_repo(korzen)
    if bledy:
        print("ZAKAZ RENDERU NA GITHUB ACTIONS: rendery tylko przez Cloudflare (finyou-render).")
        for b in bledy:
            print(f"::error::{b}")
        return 1
    print("OK: żaden workflow nie renderuje na GitHub Actions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
