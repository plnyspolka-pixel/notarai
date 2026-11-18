"""Manifest przebiegu i dziennik decyzji kodera (JSONL, bez treści i bez PII).

Wynik zadania zależy od ustawień silnika, których nie widać w karcie („silent
hyperparameters”): wersja vLLM, dtype, kwantyzacja, długość kontekstu, prefix caching,
typ karty GPU. Manifest zapisuje je obok wyniku, żeby przebiegi dało się porównać.

API:
    stan_silnika(sciezka) -> dict          stan z salad_vllm.py (`.agent-forge/salad-koder.json`)
    manifest(plik_karty, stan, repo_root, ukryte=None, env=None) -> dict
    z_trajektorii(sciezka_traj) -> dict    status, kroki, tokeny z pliku mini-swe-agent
    rekord_zadania(id, wynik, powody, manifest, traj=None, sekundy=None, koszt_usd=None) -> dict
    dopisz_dziennik(sciezka, rekord)       jeden wiersz JSONL; brak ścieżki = nic
    sciezka_dziennika(out_dir, env=None)   KODER_DZIENNIK albo <out_dir>/dziennik.jsonl

Zasady: koszt nieznany to `null`, nigdy 0; tokeny nieznane to `null`; w rekordzie są tylko
identyfikatory, kody powodów, liczby i skróty sha256 - żadnych promptów ani treści plików.

CLI (dla zadanie.sh):
    python manifest.py zadanie --karta PLIK --id ID --wynik W [--powod P ...] [--traj F]
        [--sekundy N] [--stan F] [--repo DIR] [--ukryte F ...] [--dziennik F]
    wypisuje rekord JSON i dopisuje go do dziennika.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

WYNIKI = ("zaliczone", "odrzucone", "niepotrzebna")
# Kody powodów odrzucenia używane przez bramki odbioru (lista otwarta, ale jawna).
POWODY = ("nie_zakonczyl", "brak_zmian", "poza_zakresem", "zmienil_testy", "nowa_zaleznosc",
          "test_widoczny", "test_ukryty", "niepotrzebna_niepotwierdzona")
_KWANT_RE = re.compile(r"(?i)(?<![a-z0-9])(int4|int8|awq|gptq|fp8|nvfp4|w4a16|w8a8)(?![a-z0-9])")


def _sha_pliku(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def _flaga(argumenty: str, nazwa: str) -> str | None:
    czesci = argumenty.split()
    for i, c in enumerate(czesci):
        if c == nazwa and i + 1 < len(czesci):
            return czesci[i + 1]
        if c.startswith(nazwa + "="):
            return c.split("=", 1)[1]
    return None


def stan_silnika(sciezka: str | Path | None) -> dict:
    try:
        return json.loads(Path(sciezka).read_text(encoding="utf-8")) if sciezka else {}
    except (OSError, ValueError):
        return {}


def skrot_plikow(repo_root: Path, pliki: list[str] | None) -> str | None:
    """Jeden sha256 po posortowanych (ścieżka, sha256 treści) - np. ukrytych testów."""
    if not pliki:
        return None
    h = hashlib.sha256()
    for p in sorted(pliki):
        h.update(f"{p}\0{_sha_pliku(repo_root / p) or 'brak'}\n".encode())
    return h.hexdigest()


def wersja_harness(repo_root: Path, env: dict) -> str | None:
    try:
        w = subprocess.run(["git", "-c", "safe.directory=*", "-C", str(repo_root), "rev-parse", "HEAD"],
                           capture_output=True, text=True, check=False)
        if w.returncode == 0 and w.stdout.strip():
            return w.stdout.strip()
    except OSError:
        pass
    return env.get("GITHUB_SHA")


def manifest(plik_karty: str | Path, stan: dict | None, repo_root: str | Path,
             ukryte: list[str] | None = None, env: dict | None = None) -> dict:
    env = dict(os.environ) if env is None else env
    stan = stan or {}
    repo_root = Path(repo_root)
    argumenty = str(stan.get("vllm_args") or "")
    model = env.get("KODER_MODEL") or stan.get("model")
    kwant, zrodlo = _flaga(argumenty, "--quantization"), None
    if kwant:
        zrodlo = "flaga"
    elif model and _KWANT_RE.search(model):
        kwant, zrodlo = _KWANT_RE.search(model).group(1).upper(), "nazwa_modelu"
    lista = argumenty.split()
    if "--no-enable-prefix-caching" in lista:
        prefix = False
    elif "--enable-prefix-caching" in lista:
        prefix = True
    else:
        prefix = "domyslne" if stan else None  # vLLM V1 włącza domyślnie; nie zgadujemy
    return {
        "model": model,
        "obraz_vllm": stan.get("image"),
        "wersja_vllm": stan.get("vllm_version"),
        "dtype": (_flaga(argumenty, "--dtype") or "auto") if stan else None,
        "kv_cache_dtype": (_flaga(argumenty, "--kv-cache-dtype") or "auto") if stan else None,
        "kwantyzacja": kwant, "kwantyzacja_zrodlo": zrodlo,
        "max_model_len": stan.get("context"),
        "prefix_caching": prefix,
        "gpu": stan.get("gpu"), "gpu_usd_h": stan.get("usd_h"),
        "wersja_harness": wersja_harness(repo_root, env),
        "sha256_karty": _sha_pliku(Path(plik_karty)),
        "skrot_ukrytych": skrot_plikow(repo_root, ukryte),
    }


def z_trajektorii(sciezka: str | Path | None) -> dict:
    try:
        d = json.loads(Path(sciezka).read_text(encoding="utf-8")) if sciezka else {}
    except (OSError, ValueError):
        d = {}
    info = d.get("info") or {}
    wej = wyj = 0
    znane = False
    for m in d.get("messages") or []:
        uzycie = ((m.get("extra") or {}).get("response") or {}).get("usage") if isinstance(m, dict) else None
        if isinstance(uzycie, dict):
            znane = True
            wej += int(uzycie.get("prompt_tokens") or 0)
            wyj += int(uzycie.get("completion_tokens") or 0)
    return {"exit_status": info.get("exit_status"),
            "kroki": (info.get("model_stats") or {}).get("api_calls"),
            "tokeny_wej": wej if znane else None, "tokeny_wyj": wyj if znane else None}


def rekord_zadania(id_: str, wynik: str, powody: list[str], manifest_: dict,
                   traj: str | Path | None = None, sekundy: int | None = None,
                   koszt_usd: float | None = None, nowe_zaleznosci: list[str] | None = None) -> dict:
    if wynik not in WYNIKI:
        raise ValueError(f"wynik: jedno z {WYNIKI}")
    t = z_trajektorii(traj)
    return {"rodzaj": "zadanie", "id": id_, "wynik": wynik, "powody": list(powody),
            **t, "sekundy": sekundy,
            "koszt_usd": None if koszt_usd is None else float(koszt_usd),  # nieznany = null
            "liczba_nowych_zaleznosci": len(nowe_zaleznosci or []),
            "nowe_zaleznosci": sorted(nowe_zaleznosci or []),  # nazwy modułów, miara K5
            "manifest": manifest_}


def sciezka_dziennika(out_dir: str | Path, env: dict | None = None) -> Path:
    env = os.environ if env is None else env
    return Path(env.get("KODER_DZIENNIK") or Path(out_dir) / "dziennik.jsonl")


def dopisz_dziennik(sciezka: str | Path | None, rekord: dict) -> None:
    if not sciezka:
        return
    sciezka = Path(sciezka)
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    wiersz = json.dumps({"kiedy": datetime.now(timezone.utc).isoformat(timespec="seconds"), **rekord},
                        ensure_ascii=False)
    with open(sciezka, "a", encoding="utf-8") as f:  # jeden zapis na wiersz (O_APPEND)
        f.write(wiersz + "\n")


def main(argv: list[str]) -> int:
    a = argparse.ArgumentParser(prog="manifest.py")
    sub = a.add_subparsers(dest="cmd", required=True)
    z = sub.add_parser("zadanie")
    z.add_argument("--karta", required=True)
    z.add_argument("--id", required=True)
    z.add_argument("--wynik", required=True, choices=WYNIKI)
    z.add_argument("--powod", action="append", default=[])
    z.add_argument("--zaleznosc", action="append", default=[])
    z.add_argument("--traj")
    z.add_argument("--sekundy", type=int)
    z.add_argument("--stan", default=os.environ.get("KODER_MANIFEST"))
    z.add_argument("--repo", default=".")
    z.add_argument("--ukryte", action="append", default=[])
    z.add_argument("--dziennik", default=os.environ.get("KODER_DZIENNIK"))
    o = a.parse_args(argv)
    koszt = os.environ.get("KODER_KOSZT_USD")
    m = manifest(o.karta, stan_silnika(o.stan), o.repo, o.ukryte)
    r = rekord_zadania(o.id, o.wynik, o.powod, m, o.traj, o.sekundy,
                       float(koszt) if koszt else None, o.zaleznosc)
    dopisz_dziennik(o.dziennik, r)
    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
