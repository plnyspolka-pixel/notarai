"""Przebieg kodera na samym węźle GPU (SaladCloud): vLLM + agenci + ocena w jednym kontenerze.

Uruchamia go Worker Cloudflare `notarai-koder` (tools/agent_factory/koder/cloudflare/) jako
polecenie grupy kontenerów na obrazie vllm/vllm-openai. Nic nie idzie przez GitHub Actions.

Na węźle NIE MA żadnych kluczy: kod repozytorium pobieramy publicznie (KODER_REPO@KODER_SHA),
gałęzie agent/* wypycha dopiero Worker (albo `odbierz.py`) z paczki wyników, którą ten skrypt
wystawia przez bramę kontenera Salad (port 8000, uwierzytelnienie bramy Salad):

  GET /stan     faza przebiegu i postęp (JSON, bez treści plików)
  GET /wyniki   paczka wyników (JSON w gzip), gdy faza = gotowe

vLLM słucha tylko na 127.0.0.1:8001. Izolacja zamiast Dockera (na Salad nie ma Dockera
w kontenerze): repozytorium zaufane, ukryte testy i wyniki leżą w katalogach roota (0700);
każdy agent pracuje jako osobny użytkownik bez uprawnień we własnej kopii plików, bez .git
i bez ukrytych testów; testy oceny uruchamia osobny użytkownik `ocena`. Po zakończeniu agenta
wszystkie jego procesy są zabijane. Ruch agenta do internetu kierujemy na martwy pośrednik
(HTTP(S)_PROXY) - to utrudnienie, nie zapora; dlatego na węzeł trafia wyłącznie publiczny kod.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

BAZA = Path("/koder")
REPO = BAZA / "repo"          # zaufany klon (root, 0700)
TMP = BAZA / "tmp"            # work/ (agenci), zaufane/, wyniki/ (root)
OUT = TMP / "wyniki"
ZMIANY = TMP / "zmiany"
VENV = Path("/opt/agent")
CFG = Path("/opt/koder-cfg")
STAN_PLIK = BAZA / "stan-silnika.json"
VLLM = "http://127.0.0.1:8001"

stan = {"faza": "start", "od": datetime.now(timezone.utc).isoformat(), "zadania": 0,
        "zrobione": 0, "blad": None, "dziennik": []}
paczka: bytes | None = None
blokada = threading.Lock()


def env(nazwa: str, domyslna: str = "") -> str:
    return os.environ.get(nazwa, domyslna)


def loguj(tekst: str) -> None:
    linia = f"{datetime.now(timezone.utc):%H:%M:%S} {tekst}"
    print(linia, flush=True)
    with blokada:
        stan["dziennik"] = (stan["dziennik"] + [linia[:300]])[-40:]


def faza(nazwa: str) -> None:
    with blokada:
        stan["faza"] = nazwa
    loguj(f"faza: {nazwa}")


def sh(cmd: list[str] | str, **kw) -> int:
    return subprocess.run(cmd, shell=isinstance(cmd, str), **kw).returncode


# ------------------------------------------------------------------ serwer stanu

class Stan(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        pass

    def _wyslij(self, kod: int, tresc: bytes, typ: str) -> None:
        self.send_response(kod)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(tresc)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(tresc)

    def do_GET(self):
        if self.path.startswith("/stan"):
            with blokada:
                s = dict(stan)
            s["zrobione"] = len([p for p in OUT.glob("*.json") if p.name.count(".") == 1]) if OUT.is_dir() else 0
            self._wyslij(200, json.dumps(s, ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/wyniki"):
            if paczka is None:
                self._wyslij(409, b'{"error":"jeszcze_nie"}', "application/json")
            else:
                self._wyslij(200, paczka, "application/gzip")
        else:
            self._wyslij(404, b"{}", "application/json")


def serwer() -> None:
    class Serwer(ThreadingHTTPServer):
        address_family = __import__("socket").AF_INET6
    srv = Serwer(("::", 8000), Stan)  # brama Salad łączy się po IPv6
    threading.Thread(target=srv.serve_forever, daemon=True).start()


# ------------------------------------------------------------------ przygotowanie

def termin() -> datetime:
    return datetime.fromisoformat(env("KODER_DEADLINE").replace("Z", "+00:00"))


def straznik_terminu() -> None:
    """Drugi bezpiecznik obok Workera: po terminie kontener kończy się sam."""
    while True:
        if datetime.now(timezone.utc) > termin():
            loguj("termin minął - kończę kontener")
            os._exit(0)
        time.sleep(20)


def start_vllm() -> subprocess.Popen:
    sekundy = max(60, int((termin() - datetime.now(timezone.utc)).total_seconds()))
    cmd = ["timeout", str(sekundy), "vllm", "serve", env("KODER_MODEL"),
           "--host", "127.0.0.1", "--port", "8001", "--served-model-name", "koder",
           "--max-model-len", env("KODER_CONTEXT", "65536"), "--gpu-memory-utilization", "0.90",
           "--enable-auto-tool-choice", "--tool-call-parser", env("KODER_PARSER", "qwen3_coder"),
           *env("KODER_VLLM_ARGS").split()]
    log = open(BAZA / "vllm.log", "ab")
    return subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)


def instaluj() -> None:
    if not shutil.which("git"):
        sh("apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git > /dev/null")
    if not (VENV / "bin" / "python").exists():
        if sh([sys.executable, "-m", "venv", str(VENV)]) != 0:
            if shutil.which("uv"):
                sh(["uv", "venv", "--seed", "--python", sys.executable, str(VENV)])
            if not (VENV / "bin" / "python").exists():
                sh("apt-get install -y -qq python3-venv > /dev/null")
                sh([sys.executable, "-m", "venv", str(VENV)])
    req = [l for l in (REPO / "requirements.txt").read_text(encoding="utf-8").splitlines()
           if not l.startswith(("faster-whisper", "playwright"))]
    (BAZA / "req.txt").write_text("\n".join(req) + "\n", encoding="utf-8")
    pip = [str(VENV / "bin" / "python"), "-m", "pip", "install", "-q", "--no-cache-dir"]
    if sh([*pip, "-r", str(BAZA / "req.txt"), "mini-swe-agent==2.4.6"]) != 0:
        raise RuntimeError("instalacja zależności agenta nie powiodła się")
    if sh("id ocena > /dev/null 2>&1 || useradd -M -s /bin/bash ocena") != 0:
        raise RuntimeError("useradd ocena")
    # Nakładka mini.yaml: model z lokalnego vLLM zamiast bramy z sieci Dockera.
    CFG.mkdir(parents=True, exist_ok=True)
    mini = (REPO / "tools/agent_factory/koder/mini.yaml").read_text(encoding="utf-8")
    (CFG / "mini.yaml").write_text(mini.replace("http://brama:8000/v1", f"{VLLM}/v1"), encoding="utf-8")
    os.chmod(CFG, 0o755)
    os.chmod(CFG / "mini.yaml", 0o644)


def pobierz_repo() -> None:
    REPO.mkdir(parents=True, exist_ok=True)
    os.chmod(BAZA, 0o711)
    os.chmod(REPO, 0o700)
    url = f"https://github.com/{env('KODER_REPO')}.git"
    for cmd in (["git", "init", "-q"], ["git", "fetch", "-q", "--depth", "1", url, env("KODER_SHA")],
                ["git", "checkout", "-q", "FETCH_HEAD"]):
        if sh(cmd, cwd=REPO) != 0:
            raise RuntimeError(f"pobranie repozytorium nie powiodło się: {cmd[1]}")


def czekaj_na_model(proc: subprocess.Popen) -> str | None:
    while datetime.now(timezone.utc) < termin():
        if proc.poll() is not None:
            ogon = (BAZA / "vllm.log").read_text(errors="replace")[-1500:]
            raise RuntimeError("vLLM zakończył się przed startem: " + ogon.replace("\n", " | ")[-600:])
        try:
            with urllib.request.urlopen(f"{VLLM}/v1/models", timeout=10) as r:
                if b"koder" in r.read(4096):
                    try:
                        with urllib.request.urlopen(f"{VLLM}/version", timeout=10) as v:
                            return str(json.loads(v.read(4096)).get("version"))[:40]
                    except Exception:
                        return None
        except Exception:
            pass
        time.sleep(10)
    raise RuntimeError("model nie wstał przed terminem")


# ------------------------------------------------------------------ paczka wyników

def zbuduj_paczke() -> bytes:
    wyniki = {}
    if OUT.is_dir():
        for p in sorted(OUT.rglob("*")):
            if p.is_file() and not p.is_symlink():
                wyniki[str(p.relative_to(OUT))] = base64.b64encode(p.read_bytes()).decode()
    galezie = []
    for p in sorted(ZMIANY.glob("*.json")) if ZMIANY.is_dir() else []:
        try:
            galezie.append(json.loads(p.read_text(encoding="utf-8")))
        except ValueError:
            pass
    with blokada:
        s = {k: v for k, v in stan.items()}
    dane = {"przebieg": env("KODER_RUN"), "sha": env("KODER_SHA"), "model": env("KODER_MODEL"),
            "stan": s, "wyniki": wyniki, "galezie": galezie}
    return gzip.compress(json.dumps(dane, ensure_ascii=False).encode("utf-8"))


def main() -> int:
    global paczka
    BAZA.mkdir(parents=True, exist_ok=True)
    serwer()
    threading.Thread(target=straznik_terminu, daemon=True).start()
    try:
        faza("vllm")
        vllm = start_vllm()
        faza("instalacja")
        pobierz_repo()
        instaluj()
        faza("model")
        wersja = czekaj_na_model(vllm)
        STAN_PLIK.write_text(json.dumps({
            "name": env("KODER_GROUP"), "deadline": env("KODER_DEADLINE"), "usd_h": float(env("KODER_USD_H", "0") or 0),
            "gpu": env("KODER_GPU"), "model": env("KODER_MODEL"), "created": stan["od"],
            "image": env("KODER_IMAGE"), "context": int(env("KODER_CONTEXT", "65536")),
            "vllm_args": env("KODER_VLLM_ARGS"), "parser": env("KODER_PARSER"), "vllm_version": wersja,
        }), encoding="utf-8")
        loguj(f"model gotowy (vLLM {wersja})")
        faza("zadania")
        for d in (TMP, TMP / "work"):
            d.mkdir(parents=True, exist_ok=True)
            os.chmod(d, 0o711)
        srodowisko = {**os.environ, "KODER_TRYB": "wezel", "KODER_RUN": env("KODER_RUN"), "KODER_TMP": str(TMP),
                      "KODER_STAN": str(STAN_PLIK), "KODER_PYTHON": str(VENV / "bin" / "python"),
                      "KODER_CFG": str(CFG), "KODER_ZMIANY": str(ZMIANY),
                      "PATH": f"{VENV / 'bin'}:{os.environ.get('PATH', '')}"}
        karty = [p for p in (REPO / "docs/agent-tasks/kolejka").glob("*.md")]
        stan["zadania"] = len([p for p in karty if not env("KODER_KARTY") or p.stem in env("KODER_KARTY").split(",")])
        with open(BAZA / "przebieg.log", "ab") as log:
            rc = subprocess.run(["bash", "tools/agent_factory/koder/przebieg.sh"], cwd=REPO, env=srodowisko,
                                stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL).returncode
        loguj(f"przebieg zakończony (kod {rc})")
        for linia in (BAZA / "przebieg.log").read_text(errors="replace").splitlines()[-25:]:
            loguj(linia)
    except Exception as exc:  # błąd też zwracamy w paczce, żeby Worker usunął kartę od razu
        with blokada:
            stan["blad"] = str(exc)[:800]
        loguj(f"BŁĄD: {exc}")
    paczka = zbuduj_paczke()
    faza("gotowe")
    while True:  # czekamy, aż Worker odbierze paczkę i usunie grupę (albo minie termin)
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
