"""Local worker for browser tests: real vault and API, fake Bedrock. Prints one JSON line when ready."""
import os
os.environ.setdefault("NOTARAI_ALWAYS_CONFIRM", "1")
import json
import socket
import sys
import tempfile
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from worker.api import create_app  # noqa: E402
from worker.devices import DeviceRegistry  # noqa: E402
from worker.inference import Inference  # noqa: E402
from worker.init_vault import initialize  # noqa: E402
from worker.policy import EU_REGIONS, Policy  # noqa: E402
from worker.usage import UsageLedger  # noqa: E402


class Bedrock:
    @staticmethod
    def _reply(text):
        return {"output": {"message": {"content": [{"text": text}]}}, "stopReason": "end_turn",
                "usage": {"inputTokens": 10, "outputTokens": 5}}

    def get_model_invocation_logging_configuration(self):
        return {}

    def get_inference_profile(self, inferenceProfileIdentifier):
        return {"models": [{"modelArn": f"arn:aws:bedrock:{r}::foundation-model/x"} for r in EU_REGIONS]}

    def converse(self, **kwargs):
        content = kwargs["messages"][0]["content"]
        prompt = content[-1]["text"]
        if "KOMENTARZ NOTARIUSZA" in prompt:
            images = sum(1 for part in content if "image" in part)
            return self._reply(json.dumps({"program": f"Portal testowy ({images} ujęć)", "cel": "Wniosek o wpis", "kroki": [
                {"pole": "PESEL wnioskodawcy", "zrodlo": "PESEL sprzedającego z notatki", "dlaczego": "sąd identyfikuje wnioskodawcę"},
                {"pole": "Numer lokalu", "zrodlo": "numer lokalu z notatki", "dlaczego": ""},
                {"pole": "Numer księgi", "zrodlo": "numer KW", "dlaczego": ""}]}, ensure_ascii=False))
        if "=== PROCEDURA" in prompt:
            return self._reply(json.dumps({"wartosci": [
                {"pole": "PESEL wnioskodawcy", "wartosc": "[PESEL_1]" if "[PESEL_1]" in prompt else "WYCIEK", "skad": "notatka"},
                {"pole": "Numer lokalu", "wartosc": "5", "skad": "notatka"},
                {"pole": "Numer księgi", "wartosc": ""}]}, ensure_ascii=False))
        if "PYTANIE NOTARIUSZA" in prompt:
            text = "Sprzedającym jest [OSOBA_1]." if "[OSOBA_1]" in prompt else "BRAK ZNACZNIKA"
        else:
            text = "# UMOWA SPRZEDAŻY\n\n[OSOBA_1], PESEL [PESEL_1], sprzedaje lokal.\nCena: [DO UZUPEŁNIENIA: cena]."
        leaked = "44051401359" in prompt or "Kowalski" in prompt
        return {"output": {"message": {"content": [{"text": "WYCIEK" if leaked else text}]}},
                "stopReason": "end_turn", "usage": {"inputTokens": 10, "outputTokens": 5}}


FORM = """<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>Portal testowy</title></head><body>
<form action="/przyjeto.html" method="get"><h1>Wniosek o wpis (fikcyjny portal)</h1>
<label for="p">PESEL wnioskodawcy</label> <input id="p" name="pesel">
<p>Numer lokalu</p><input name="lokal">
<label>Numer księgi <input name="kw"></label>
<button type="submit">Wyślij wniosek</button></form></body></html>"""


def form_site():
    import threading
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    root = Path(tempfile.mkdtemp(prefix="notarai-form-"))
    (root / "wniosek.html").write_text(FORM, encoding="utf-8")
    (root / "przyjeto.html").write_text("<!doctype html><meta charset=utf-8><title>Przyjęto</title><p>Wniosek przyjęto.</p>",
                                        encoding="utf-8")
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}/wniosek.html"


def main():
    home = Path(tempfile.mkdtemp(prefix="notarai-e2e-")) / "home"
    backups = home.parent / "usb"
    backups.mkdir()
    initialize(home)
    bedrock = Bedrock()
    inference = Inference(Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6"), lambda s: bedrock, UsageLedger(home))
    from worker.web_fill import Browser

    browser = Browser(home.parent / "przegladarka", headless=True)     # a real browser, without a window
    def dictation(source, on_text):
        """Stands in for Transcribe streaming: one more word for every piece of sound that arrives."""
        words = "Klient przyniesie odpis z księgi wieczystej w piątek".split()
        heard = 0
        while True:
            piece = source.get(timeout=30)
            if piece is None:
                break
            heard += 1
            on_text([], " ".join(words[:min(len(words), heard)]))
        on_text([" ".join(words)], "")

    app = create_app(home, inference=inference, opener=lambda path: None, fill_targets={"strona": lambda: browser},
                     dictation_stream=dictation,
                     transcriber=lambda audio: "Wpisuję PESEL wnioskodawcy, bo sąd identyfikuje go po numerze, potem numer lokalu.")   # no editor on a test machine
    registry = DeviceRegistry(home)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        print(json.dumps({
            "url": f"http://127.0.0.1:{port}/v2",
            "write": registry.invite("telefon", "write")["code"],
            "write2": registry.invite("telefon 2", "write")["code"],
            "read": registry.invite("tablet", "read", cases=["sprawa-1"])["code"],
            "admin": registry.invite("panel", "admin", allow_admin=True)["code"],
            "backups": str(backups), "home": str(home), "form": form_site(),
        }), flush=True)
        uvicorn.Server(uvicorn.Config(app, access_log=False, log_level="warning")).run(sockets=[listener])


if __name__ == "__main__":
    main()
