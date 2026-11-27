"""Local Bedrock policy: EU-only models, no content logging. Enforced before every call."""
import re
import time

# EU member-state regions only. Zurich (eu-central-2) and London (eu-west-2) are outside the EU.
EU_REGIONS = frozenset({"eu-central-1", "eu-west-1", "eu-west-3", "eu-north-1", "eu-south-1", "eu-south-2"})
PROVIDERS = ("anthropic", "amazon", "mistral", "meta", "cohere")
_MODEL = re.compile(r"^(eu\.)?(%s)\.[a-z0-9][a-z0-9.\-]{1,80}(:\d{1,3})?$" % "|".join(PROVIDERS))
_ARN_REGION = re.compile(r"^arn:aws:bedrock:([a-z0-9-]+):")
_CONTENT_FLAGS = ("textDataDeliveryEnabled", "imageDataDeliveryEnabled",
                  "embeddingDataDeliveryEnabled", "videoDataDeliveryEnabled")
VERIFY_TTL = 900


class PolicyError(PermissionError):
    """Message is safe to show; it never contains prompt or document content."""


def check_static(region: str, model: str) -> None:
    """Checks that need no network: region in the EU, model id is a direct EU model or an `eu.` profile."""
    if region not in EU_REGIONS:
        raise PolicyError("Bedrock jest dozwolony wyłącznie w regionach UE.")
    if not isinstance(model, str) or not _MODEL.fullmatch(model):
        # Rejects ARNs, provisioned endpoints and the `global.` / `us.` cross-region profiles.
        raise PolicyError("Dozwolony jest tylko model UE: bezpośredni albo profil eu.")


def check_logging(control) -> None:
    """Invocation logging may carry metadata (token counts), never prompt or response content."""
    config = control.get_model_invocation_logging_configuration().get("loggingConfig") or {}
    if config and any(config.get(flag, True) for flag in _CONTENT_FLAGS):
        raise PolicyError("Konto AWS zapisuje treść wywołań modeli. Wyłącz zapis treści w Bedrock.")


def check_profile(control, model: str) -> None:
    """An `eu.` profile must route only to EU regions, as reported by the account itself."""
    if not model.startswith("eu."):
        return
    profile = control.get_inference_profile(inferenceProfileIdentifier=model)
    regions = set()
    for entry in profile.get("models") or []:
        match = _ARN_REGION.match(entry.get("modelArn", ""))
        if not match:
            raise PolicyError("Nie udało się potwierdzić regionów profilu modelu.")
        regions.add(match.group(1))
    if not regions or not regions <= EU_REGIONS:
        raise PolicyError("Profil modelu kieruje wywołania poza UE.")


class Policy:
    """Caches a successful account verification for a short time."""

    def __init__(self, region: str, model: str, *, clock=time.monotonic):
        check_static(region, model)
        self.region, self.model = region, model
        self._clock = clock
        self._verified_until = 0.0

    def verify(self, control) -> None:
        if self._clock() < self._verified_until:
            return
        check_logging(control)
        check_profile(control, self.model)
        self._verified_until = self._clock() + VERIFY_TTL
