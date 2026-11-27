"""The single path from the worker to a model: policy, pseudonymisation, metering.

Nothing here logs prompt or response text. Errors are reduced to fixed messages.
"""
from dataclasses import dataclass

from .policy import Policy, PolicyError
from .pseudonym import Pseudonymizer
from .usage import UsageLedger

MAX_INPUT_CHARS = 600_000


class InferenceError(Exception):
    """Fixed, content-free message for the operator."""


@dataclass(frozen=True)
class Answer:
    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str
    pseudonymized: int
    unknown_placeholders: tuple[str, ...] = ()


class Inference:
    def __init__(self, policy: Policy | None, client_factory, ledger: UsageLedger):
        """`policy=None` means inference is switched off. `client_factory(service)` returns a boto3 client."""
        self._policy, self._clients, self._ledger = policy, client_factory, ledger

    @property
    def enabled(self) -> bool:
        return self._policy is not None

    def ask(self, *, purpose: str, system: str, text: str, names=(), max_tokens: int = 4096) -> Answer:
        if self._policy is None:
            raise PolicyError("AI jest wyłączone na tym stanowisku.")
        if not text or len(text) + len(system) > MAX_INPUT_CHARS or not 1 <= max_tokens <= 64000:
            raise InferenceError("Zapytanie jest puste albo za duże.")
        pseudonyms = Pseudonymizer(names)
        try:
            hidden = pseudonyms.hide(text)
        except ValueError:
            raise InferenceError("Tekst zawiera znaczniki zastrzeżone dla NotarAI.") from None
        self._policy.verify(self._clients("bedrock"))
        runtime = self._clients("bedrock-runtime")
        try:
            response = runtime.converse(
                modelId=self._policy.model,
                system=[{"text": system}] if system else [],
                messages=[{"role": "user", "content": [{"text": hidden}]}],
                inferenceConfig={"maxTokens": max_tokens},
            )
            usage = response.get("usage") or {}
            parts = response["output"]["message"]["content"]
            raw = "".join(part.get("text", "") for part in parts)
        except PolicyError:
            raise
        except Exception:
            self._ledger.record(self._policy.model, purpose, 0, 0, ok=False)
            raise InferenceError("Model nie odpowiedział. Spróbuj ponownie za chwilę.") from None
        self._ledger.record(self._policy.model, purpose, usage.get("inputTokens", 0), usage.get("outputTokens", 0))
        revealed, unknown = pseudonyms.reveal(raw)
        return Answer(
            revealed, int(usage.get("inputTokens", 0)), int(usage.get("outputTokens", 0)),
            str(response.get("stopReason", "")), pseudonyms.replaced, tuple(unknown),
        )
