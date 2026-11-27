"""Local worker for browser tests: real vault and API, fake Bedrock. Prints one JSON line when ready."""
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


def main():
    home = Path(tempfile.mkdtemp(prefix="notarai-e2e-")) / "home"
    backups = home.parent / "usb"
    backups.mkdir()
    initialize(home)
    bedrock = Bedrock()
    inference = Inference(Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6"), lambda s: bedrock, UsageLedger(home))
    app = create_app(home, inference=inference, opener=lambda path: None,
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
            "backups": str(backups), "home": str(home),
        }), flush=True)
        uvicorn.Server(uvicorn.Config(app, access_log=False, log_level="warning")).run(sockets=[listener])


if __name__ == "__main__":
    main()
