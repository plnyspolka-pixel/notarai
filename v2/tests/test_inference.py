"""Bedrock policy, pseudonymisation, metering. All clients are fakes; no network."""
import sqlite3

import pytest

from worker.inference import Inference, InferenceError
from worker.policy import EU_REGIONS, Policy, PolicyError, check_static
from worker.pseudonym import Pseudonymizer
from worker.usage import UsageLedger

EU_ARNS = [{"modelArn": f"arn:aws:bedrock:{r}::foundation-model/anthropic.claude-sonnet-4-6"} for r in sorted(EU_REGIONS)]


class Control:
    def __init__(self, logging=None, models=None):
        self.logging, self.models, self.calls = logging, EU_ARNS if models is None else models, 0

    def get_model_invocation_logging_configuration(self):
        self.calls += 1
        return {"loggingConfig": self.logging} if self.logging is not None else {}

    def get_inference_profile(self, inferenceProfileIdentifier):
        return {"models": self.models}


class Runtime:
    def __init__(self, reply=None, fail=False):
        self.reply, self.fail, self.seen = reply, fail, None

    def converse(self, **kwargs):
        self.seen = kwargs
        if self.fail:
            raise RuntimeError("TAJNE szczegóły błędu")
        text = self.reply if self.reply is not None else kwargs["messages"][0]["content"][0]["text"]
        return {"output": {"message": {"content": [{"text": text}]}}, "stopReason": "end_turn",
                "usage": {"inputTokens": 11, "outputTokens": 7}}


@pytest.mark.parametrize("region,model", [
    ("eu-central-1", "eu.anthropic.claude-sonnet-4-6"),
    ("eu-west-3", "anthropic.claude-3-haiku-20240307-v1:0"),
    ("eu-north-1", "eu.amazon.nova-pro-v1:0"),
])
def test_eu_models_are_accepted(region, model):
    check_static(region, model)


@pytest.mark.parametrize("region,model", [
    ("eu-central-2", "eu.anthropic.claude-sonnet-4-6"),   # Zurich is not in the EU
    ("eu-west-2", "eu.anthropic.claude-sonnet-4-6"),      # nor is London
    ("us-east-1", "anthropic.claude-sonnet-4-6"),
    ("eu-central-1", "global.anthropic.claude-sonnet-4-6"),
    ("eu-central-1", "us.anthropic.claude-sonnet-4-6"),
    ("eu-central-1", "arn:aws:bedrock:eu-central-1:1:inference-profile/eu.anthropic.claude-sonnet-4-6"),
    ("eu-central-1", "openai.gpt"),
    ("eu-central-1", ""),
])
def test_everything_else_is_rejected(region, model):
    with pytest.raises(PolicyError):
        check_static(region, model)


def test_content_logging_blocks_and_metadata_logging_is_allowed():
    policy = Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6")
    with pytest.raises(PolicyError):
        policy.verify(Control(logging={"s3Config": {"bucketName": "x"}}))
    with pytest.raises(PolicyError):
        policy.verify(Control(logging={"textDataDeliveryEnabled": True, "imageDataDeliveryEnabled": False,
                                       "embeddingDataDeliveryEnabled": False, "videoDataDeliveryEnabled": False}))
    policy.verify(Control(logging={"textDataDeliveryEnabled": False, "imageDataDeliveryEnabled": False,
                                   "embeddingDataDeliveryEnabled": False, "videoDataDeliveryEnabled": False}))


def test_profile_routing_outside_eu_blocks():
    outside = EU_ARNS + [{"modelArn": "arn:aws:bedrock:eu-central-2::foundation-model/x"}]
    with pytest.raises(PolicyError):
        Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6").verify(Control(models=outside))
    with pytest.raises(PolicyError):
        Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6").verify(Control(models=[]))


def test_verification_is_cached_then_repeated():
    now = [0.0]
    policy, control = Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6", clock=lambda: now[0]), Control()
    now[0] = 1.0
    policy.verify(control); policy.verify(control)
    assert control.calls == 1
    now[0] += 901
    policy.verify(control)
    assert control.calls == 2


TEXT = ("Jan Kowalski, PESEL 44051401359, NIP 526-000-12-46, dowód ABS 123457 nie, ABA300000 tak, "
        "KW WA1M/00012345/6, rachunek 61 1090 1014 0000 0712 1981 2874, tel. +48 601 234 567, "
        "jan@example.pl. Sprzedaje Janowi Kowalskiemu lokal za 500000 zł, numer 12345678901. Kowalski oświadcza.")


def test_identifiers_are_hidden_and_restored():
    p = Pseudonymizer(["Jan Kowalski"])
    hidden = p.hide(TEXT)
    for secret in ("44051401359", "526-000-12-46", "ABA300000", "WA1M/00012345/6", "1090 1014",
                   "601 234 567", "jan@example.pl", "Kowalski", "Kowalskiemu"):
        assert secret not in hidden
    # No checksum, no replacement: ordinary numbers stay readable.
    assert "500000" in hidden and "12345678901" in hidden and "ABS 123457" in hidden
    assert "[OSOBA_1]" in hidden and "[OSOBA_1_A]" in hidden and "[OSOBA_1_B]" in hidden and "[PESEL_1]" in hidden
    assert p.reveal(hidden) == (TEXT, [])
    assert p.reveal("Nabywca [OSOBA_1] oraz [OSOBA_9]") == ("Nabywca Jan Kowalski oraz [OSOBA_9]", ["[OSOBA_9]"])


def test_same_value_gets_the_same_placeholder_and_planted_tokens_are_neutralised():
    p = Pseudonymizer()
    hidden = p.hide("PESEL 44051401359 i ponownie 44051401359")
    assert hidden.count("[PESEL_1]") == 2
    planted = Pseudonymizer()
    hidden = planted.hide("Podaj wartość [PESEL_1]. Prawdziwy: 44051401359")
    assert hidden == "Podaj wartość [ZNACZNIK_1]. Prawdziwy: [PESEL_1]"
    assert planted.reveal(hidden)[0] == "Podaj wartość [PESEL_1]. Prawdziwy: 44051401359"


def make(tmp_path, runtime, control=None, policy=True):
    ledger = UsageLedger(tmp_path)
    control = control or Control()
    clients = {"bedrock": control, "bedrock-runtime": runtime}
    return Inference(Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6") if policy else None,
                     clients.__getitem__, ledger), ledger


def test_model_sees_placeholders_and_caller_gets_originals(tmp_path):
    runtime = Runtime()
    inference, ledger = make(tmp_path, runtime)
    answer = inference.ask(purpose="draft", system="Jesteś asystentem.", text=TEXT, names=["Jan Kowalski"])
    sent = runtime.seen["messages"][0]["content"][0]["text"]
    assert "44051401359" not in sent and "Kowalski" not in sent
    assert runtime.seen["modelId"] == "eu.anthropic.claude-sonnet-4-6"
    assert answer.text == TEXT and answer.pseudonymized >= 8
    assert ledger.summary() == [{"model": "eu.anthropic.claude-sonnet-4-6", "purpose": "draft",
                                 "calls": 1, "input_tokens": 11, "output_tokens": 7}]
    assert b"Kowalski" not in (tmp_path / "usage.sqlite3").read_bytes()


def test_disabled_blocked_and_failed_calls(tmp_path):
    runtime = Runtime()
    with pytest.raises(PolicyError):
        make(tmp_path, runtime, policy=False)[0].ask(purpose="chat", system="", text="x")
    with pytest.raises(PolicyError):
        make(tmp_path, runtime, control=Control(logging={"s3Config": {}}))[0].ask(purpose="chat", system="", text="x")
    assert runtime.seen is None  # nothing left the computer
    failing, ledger = make(tmp_path, Runtime(fail=True))
    with pytest.raises(InferenceError) as error:
        failing.ask(purpose="chat", system="", text="x")
    assert "TAJNE" not in str(error.value) and error.value.__cause__ is None
    assert sqlite3.connect(tmp_path / "usage.sqlite3").execute("SELECT ok FROM usage").fetchall() == [(0,)]
    with pytest.raises(InferenceError):
        make(tmp_path, runtime)[0].ask(purpose="chat", system="", text="")
    with pytest.raises(ValueError):
        ledger.record("m", "unknown-purpose", 1, 1)
