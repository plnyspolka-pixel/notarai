"""Opt-in live check against Amazon Bedrock in the EU with synthetic text only.

Run from v2/:  python tests/live_bedrock.py [model]
Uses the ambient AWS credentials of whoever runs it; never part of the automated suite.
Verifies the account-side policy checks for real (profile routing, no content logging),
then sends one synthetic request through the full path with pseudonymisation.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import boto3  # noqa: E402

from worker.inference import Inference  # noqa: E402
from worker.policy import Policy  # noqa: E402
from worker.usage import UsageLedger  # noqa: E402

REGION = "eu-central-1"
SYNTHETIC = ("To jest test na danych fikcyjnych. Sprzedający Jan Testowy, PESEL 44051401359, "
             "zbywa lokal. Odpowiedz jednym zdaniem: kto sprzedaje i jaki ma PESEL? Przepisz znaczniki bez zmian.")


def main() -> int:
    model = sys.argv[1] if len(sys.argv) > 1 else "eu.anthropic.claude-sonnet-4-6"
    seen = []

    def factory(service):
        client = boto3.client(service, region_name=REGION)
        if service == "bedrock-runtime":
            original = client.converse

            def converse(**kwargs):
                seen.append(kwargs["messages"][0]["content"][0]["text"])
                return original(**kwargs)
            client.converse = converse
        return client

    with tempfile.TemporaryDirectory() as home:
        ledger = UsageLedger(Path(home))
        answer = Inference(Policy(REGION, model), factory, ledger).ask(
            purpose="smoke", system="Odpowiadaj po polsku, krótko.", text=SYNTHETIC, names=["Jan Testowy"], max_tokens=200)
        assert "44051401359" not in seen[0] and "Testowy" not in seen[0], "identifier left the machine"
        print("sent to the model :", seen[0][:140], "…")
        print("answer (restored) :", answer.text)
        print("tokens            :", answer.input_tokens, "in /", answer.output_tokens, "out;",
              "placeholders hidden:", answer.pseudonymized, "; invented:", list(answer.unknown_placeholders))
        print("ledger            :", ledger.summary())
        assert "Jan Testowy" in answer.text and "44051401359" in answer.text, "placeholders were not restored"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
