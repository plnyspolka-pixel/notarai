"""Model kodujący (vLLM) na wynajętym GPU SaladCloud + lokalny pośrednik dla runnera.

Polecenia:
  check                 karty, ceny i nasze grupy (nic nie kosztuje)
  up --pay              utwórz grupę z vLLM (płatne od chwili stanu `running`)
  status                stan grupy i tego, czy model już odpowiada
  proxy                 127.0.0.1:PORT -> brama Salad (dokleja klucz); po terminie usuwa grupę
Całość bez komputera operatora uruchamia workflow .github/workflows/koder.yml.
  down                  usuń grupę (zawsze na koniec)

Zasady: węzły Salad to cudze komputery poza UE -> wyłącznie kod z publicznego repo i dane
syntetyczne, nigdy `dane/`, `.env` ani nic o klientach. Klucz Salad tylko ze środowiska albo
z pliku wskazanego w NOTARAI_SALAD_ENV (poza repo); nie trafia do logów ani do kontenera.
Narzędzie rusza wyłącznie grupy o nazwie zaczynającej się od `notarai-koder`.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

API_HOST = "api.salad.com"
API_BASE = "/api/public"
LABEL = "notarai-koder"
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,61}[a-z0-9]$")
DNS_RE = re.compile(r"^[a-z0-9.-]+\.salad\.cloud$", re.I)
STATE = Path(__file__).resolve().parents[2] / ".agent-forge" / "salad-koder.json"

# Domyślny model: Qwen3.8-27B w 4 bitach (19,5 GB wag, Apache 2.0, bez bramki) - najmocniejszy
# otwarty model do pracy agentowej mieszczący się na jednej karcie 32 GB (przegląd 16.11.2026).
# Zapas dla kart 24 GB: cyankiwi/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit z parserem qwen3_xml.
DEFAULT_MODEL = "RedHatAI/Qwen3.8-27B-INT4"
DEFAULT_PARSER = "qwen3_coder"  # wg recipes.vllm.ai/Qwen/Qwen3.8-27B
DEFAULT_VLLM_ARGS = "--kv-cache-dtype fp8 --language-model-only --enforce-eager --reasoning-parser qwen3"
DEFAULT_IMAGE = "vllm/vllm-openai:latest"
SERVED_NAME = "koder"
PORT = 8000
HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te",
       "trailers", "transfer-encoding", "upgrade", "host", "content-length"}


class SaladError(RuntimeError):
    pass


def load_keys() -> dict[str, str]:
    keys = {k: os.environ.get(k, "") for k in ("SALAD_API_KEY", "SALAD_ORG", "SALAD_PROJECT")}
    path = os.environ.get("NOTARAI_SALAD_ENV")
    if path and Path(path).is_file():
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            m = re.match(r"^(SALAD_API_KEY|SALAD_ORG|SALAD_PROJECT)=(.*)$", line.strip())
            if m and not keys[m.group(1)]:
                keys[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    keys["SALAD_PROJECT"] = keys["SALAD_PROJECT"] or "default"
    if not keys["SALAD_API_KEY"]:
        raise SaladError("Brak SALAD_API_KEY (środowisko albo plik z NOTARAI_SALAD_ENV)")
    for k in ("SALAD_ORG", "SALAD_PROJECT"):
        if not NAME_RE.fullmatch(keys[k]):
            raise SaladError(f"Zła albo pusta wartość {k}")
    return keys


def api(keys: dict, method: str, path: str, body: dict | None = None, allow404: bool = False):
    conn = http.client.HTTPSConnection(API_HOST, timeout=30)
    try:
        headers = {"Salad-Api-Key": keys["SALAD_API_KEY"], "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        conn.request(method, API_BASE + path, body=data, headers=headers)
        res = conn.getresponse()
        text = res.read().decode("utf-8", "replace")
        if res.status == 404 and allow404:
            return None
        if res.status >= 300:
            raise SaladError(f"Salad HTTP {res.status} {method} {path}: {text[:300]}")
        try:
            return json.loads(text) if text else {}
        except ValueError:
            return {}
    finally:
        conn.close()


def groups_path(keys: dict) -> str:
    return f"/organizations/{keys['SALAD_ORG']}/projects/{keys['SALAD_PROJECT']}/containers"


def group_path(keys: dict, name: str) -> str:
    if not NAME_RE.fullmatch(name) or not name.startswith(LABEL):
        raise SaladError(f"Grupa {name} nie jest nasza - nie ruszam")
    return f"{groups_path(keys)}/{name}"


def our_groups(keys: dict) -> list[dict]:
    items = (api(keys, "GET", groups_path(keys)) or {}).get("items") or []
    return [g for g in items if str(g.get("name", "")).startswith(LABEL)]


def gpu_classes(keys: dict, priority: str) -> list[dict]:
    items = (api(keys, "GET", f"/organizations/{keys['SALAD_ORG']}/gpu-classes") or {}).get("items") or []
    out = []
    for c in items:
        m = re.search(r"\((\d+)\s*GB\)", str(c.get("name", "")))
        price = next((float(p["price"]) for p in c.get("prices") or []
                      if p.get("priority") == priority), None)
        if m and price is not None:
            out.append({"id": c["id"], "name": c["name"], "vram": int(m.group(1)), "usd_h": price})
    return sorted(out, key=lambda x: (-x["vram"], x["usd_h"]))


def create_body(name: str, gpu_id: str, args, deadline: datetime) -> dict:
    # `timeout` w kontenerze: drugi bezpiecznik - po terminie vLLM kończy pracę sam, nawet
    # gdyby nikt nie usunął grupy (restart_policy=never).
    seconds = max(60, int((deadline - datetime.now(timezone.utc)).total_seconds()) + 900)
    command = [
        "timeout", str(seconds), "vllm", "serve", args.model,
        "--host", "::", "--port", str(PORT),  # brama Salad łączy się po IPv6
        "--served-model-name", SERVED_NAME,
        "--max-model-len", str(args.context),
        "--gpu-memory-utilization", "0.90",
        "--enable-auto-tool-choice", "--tool-call-parser", args.parser,
        *args.vllm_args.split(),
    ]
    return {
        "name": name,
        "display_name": name,
        "container": {
            "image": args.image,
            "command": command,
            "priority": args.priority,
            "resources": {
                "cpu": 8, "memory": 32 * 1024, "gpu_classes": [gpu_id],
                "storage_amount": 50 * 1024 ** 3,
            },
            "environment_variables": {"KODER_DEADLINE": deadline.isoformat()},
        },
        "autostart_policy": True,
        "restart_policy": "never",
        "replicas": 1,
        "networking": {
            "protocol": "http", "port": PORT, "auth": True,
            "load_balancer": "round_robin", "single_connection_limit": False,
            "client_request_timeout": 100000, "server_response_timeout": 100000,
        },
    }


def save_state(data: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_state() -> dict:
    if not STATE.is_file():
        raise SaladError("Brak zapisanej grupy - najpierw `up --pay`")
    return json.loads(STATE.read_text(encoding="utf-8"))


def describe(keys: dict, name: str) -> dict | None:
    g = api(keys, "GET", group_path(keys, name), allow404=True)
    if g is None:
        return None
    inst = ((api(keys, "GET", group_path(keys, name) + "/instances", allow404=True) or {})
            .get("instances") or [{}])[0]
    dns = str((g.get("networking") or {}).get("dns") or "").replace("https://", "").strip("/")
    return {
        "name": name,
        "state": inst.get("state") or (g.get("current_state") or {}).get("status") or "pending",
        "dns": dns if DNS_RE.fullmatch(dns) else None,
        "deadline": ((g.get("container") or {}).get("environment_variables") or {}).get("KODER_DEADLINE"),
    }


def model_ready(keys: dict, dns: str) -> bool:
    conn = http.client.HTTPSConnection(dns, timeout=20)
    try:
        conn.request("GET", "/v1/models", headers={"Salad-Api-Key": keys["SALAD_API_KEY"]})
        res = conn.getresponse()
        body = res.read(4096)
        return res.status == 200 and SERVED_NAME.encode() in body
    except (OSError, http.client.HTTPException):
        return False
    finally:
        conn.close()


# ---------------------------------------------------------------- polecenia

def cmd_check(keys: dict, args) -> int:
    gpus = gpu_classes(keys, args.priority)
    names = [g["name"] for g in our_groups(keys)]
    if getattr(args, "json", False):
        payload = {"gpu": [{"name": c["name"], "vram": c["vram"], "usd_h": c["usd_h"]} for c in gpus],
                   "groups": names}
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    for c in gpus:
        print(f"{c['name']:<28}{c['usd_h']:.3f} USD/h")
    print("Nasze grupy:", ", ".join(names) or "brak")
    return 0


def cmd_up(keys: dict, args) -> int:
    if our_groups(keys):
        raise SaladError("Nasza grupa już istnieje - `status` albo `down`")
    offers = [c for c in gpu_classes(keys, args.priority)
              if c["vram"] >= args.min_vram and c["usd_h"] <= args.max_hourly]
    if not offers:
        raise SaladError("Brak karty spełniającej --min-vram / --max-hourly")
    offer = offers[0]
    minutes = min(args.minutes, int(args.max_usd / offer["usd_h"] * 60))
    if minutes < 20:
        raise SaladError("Budżet nie starcza na 20 minut pracy")
    print(f"Plan: {offer['name']} {offer['usd_h']:.2f} USD/h, do {minutes} min, "
          f"najwyżej {minutes / 60 * offer['usd_h']:.2f} USD; model {args.model}")
    if not args.pay:
        print("PLAN (bez --pay nic nie tworzę).")
        return 0
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(minutes=minutes)
    name = f"{LABEL}-{now:%Y%m%dt%H%M}"
    api(keys, "POST", groups_path(keys), create_body(name, offer["id"], args, deadline))
    save_state({"name": name, "deadline": deadline.isoformat(), "usd_h": offer["usd_h"],
                "gpu": offer["name"], "model": args.model, "created": now.isoformat()})
    print(f"Utworzono {name}; termin {deadline:%H:%M} UTC. Dalej: status, potem proxy.")
    return 0


def cmd_status(keys: dict, args) -> int:
    st = read_state()
    d = describe(keys, st["name"])
    if d is None:
        print("Grupy już nie ma.")
        return 1
    ready = bool(d["dns"]) and d["state"] == "running" and model_ready(keys, d["dns"])
    print(json.dumps({**d, "model_ready": ready}, indent=2))
    return 0 if ready else 3


def cmd_down(keys: dict, args) -> int:
    names = [g["name"] for g in our_groups(keys)]
    for name in names:
        api(keys, "DELETE", group_path(keys, name), allow404=True)
        print(f"Usunięto {name}")
    if not names:
        print("Nie było czego usuwać.")
    if STATE.is_file():
        st = read_state()
        try:
            mins = (datetime.now(timezone.utc) - datetime.fromisoformat(st["created"])).total_seconds() / 60
            print(f"Czas od utworzenia: {mins:.0f} min, górna granica kosztu "
                  f"{mins / 60 * st['usd_h']:.2f} USD (Salad nalicza tylko stan running).")
        except (KeyError, ValueError):
            pass
        STATE.unlink()
    return 0


def make_handler(keys: dict, dns: str):
    class Proxy(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *a):  # ścieżka i kod, bez treści żądań
            sys.stderr.write("proxy %s %s\n" % (self.command, fmt % a))

        def _forward(self):
            if not self.path.startswith("/v1/"):
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length > 8 * 1024 * 1024:
                self.send_error(413)
                return
            body = self.rfile.read(length) if length else None
            headers = {k: v for k, v in self.headers.items()
                       if k.lower() not in HOP and k.lower() != "authorization"}
            headers["Salad-Api-Key"] = keys["SALAD_API_KEY"]
            conn = http.client.HTTPSConnection(dns, timeout=130)
            try:
                conn.request(self.command, self.path, body=body, headers=headers)
                res = conn.getresponse()
                self.send_response(res.status)
                for k, v in res.getheaders():
                    if k.lower() not in HOP:
                        self.send_header(k, v)
                self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Connection", "close")
                self.end_headers()
                while True:
                    chunk = res.read1(65536)
                    if not chunk:
                        break
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
            except (OSError, http.client.HTTPException) as exc:
                sys.stderr.write(f"proxy błąd: {type(exc).__name__}\n")
                try:
                    self.send_error(502)
                except OSError:
                    pass
            finally:
                conn.close()
                self.close_connection = True

        do_GET = do_POST = _forward

    return Proxy


def cmd_proxy(keys: dict, args) -> int:
    st = read_state()
    deadline = datetime.fromisoformat(st["deadline"])
    print(f"Czekam na model w grupie {st['name']} (termin {deadline:%H:%M} UTC)...")
    last = ""
    dns = None
    while datetime.now(timezone.utc) < deadline:
        d = describe(keys, st["name"])
        if d is None:
            raise SaladError("Grupa zniknęła")
        if d["state"] != last:
            print("... Salad:", d["state"], flush=True)
            last = d["state"]
        if d["dns"] and d["state"] == "running" and model_ready(keys, d["dns"]):
            dns = d["dns"]
            break
        time.sleep(15)
    if not dns:
        cmd_down(keys, args)
        raise SaladError("Model nie wstał przed terminem - grupa usunięta")
    server = ThreadingHTTPServer((args.bind, args.port), make_handler(keys, dns))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"GOTOWE: http://{args.bind}:{args.port}/v1 (model `{SERVED_NAME}`)", flush=True)
    try:
        while datetime.now(timezone.utc) < deadline:
            time.sleep(5)
        print("Termin minął - usuwam grupę.")
    except KeyboardInterrupt:
        print("Przerwano - usuwam grupę.")
    finally:
        server.shutdown()
        cmd_down(keys, args)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="vLLM na SaladCloud dla agenta kodującego")
    p.add_argument("--priority", default="high", choices=["high", "medium", "low", "batch"])
    sub = p.add_subparsers(dest="cmd", required=True)
    ch = sub.add_parser("check")
    ch.add_argument("--json", action="store_true", help="wypisz wynik jako jeden obiekt JSON")
    up = sub.add_parser("up")
    up.add_argument("--pay", action="store_true")
    up.add_argument("--model", default=DEFAULT_MODEL)
    up.add_argument("--parser", default=DEFAULT_PARSER)
    up.add_argument("--image", default=DEFAULT_IMAGE)
    up.add_argument("--vllm-args", default=DEFAULT_VLLM_ARGS, help="dodatkowe flagi vllm serve")
    up.add_argument("--context", type=int, default=65536)
    up.add_argument("--minutes", type=int, default=120)
    up.add_argument("--max-usd", type=float, default=2.0)
    up.add_argument("--max-hourly", type=float, default=1.0)
    up.add_argument("--min-vram", type=int, default=32)
    sub.add_parser("status")
    px = sub.add_parser("proxy")
    px.add_argument("--port", type=int, default=8000)
    px.add_argument("--bind", default="127.0.0.1",
                    help="0.0.0.0 tylko w kontenerze-bramie w wewnętrznej sieci Dockera")
    sub.add_parser("down")
    args = p.parse_args(argv)
    try:
        keys = load_keys()
        return {"check": cmd_check, "up": cmd_up, "status": cmd_status,
                "proxy": cmd_proxy, "down": cmd_down}[args.cmd](keys, args)
    except (SaladError, OSError, http.client.HTTPException) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
