"""Default autonomous preparation contract for NotarAI Confidential Browser.

AUTO is the only API-exposed mode in the pilot. It can prepare/inspect a
draft but cannot authorize, sign, submit, dispatch external writes, or
override a human decision. Changing a UI setting never relaxes this policy.
The entire confidential feature remains disabled in production until the
existing explicit feature flag and independent AWS readiness gates are met.
"""
from __future__ import annotations

from dataclasses import dataclass


class UnsafeAutoRequest(ValueError):
    """Explicit fail-closed validation error: never echo request content."""


@dataclass(frozen=True)
class AutoPolicy:
    mode: str = "auto"
    thinking_enabled: bool = False
    can_submit: bool = False
    can_sign: bool = False
    external_writes_enabled: bool = False
    requires_human_for_external_effect: bool = True

    def public(self) -> dict:
        return {
            "version": 1,
            "mode": self.mode,
            "thinking_enabled": self.thinking_enabled,
            "can_submit": self.can_submit,
            "can_sign": self.can_sign,
            "external_writes_enabled": self.external_writes_enabled,
            "requires_human_for_external_effect":
                self.requires_human_for_external_effect,
            "automatic_stages": [
                "read_encrypted_input_in_nitro",
                "validate_document",
                "prepare_form",
                "fill_form",
                "preview_result",
            ],
            "blocked_stages": [
                "submit_form",
                "sign_document",
                "send_application",
                "make_binding_declaration",
            ],
        }


DEFAULT_AUTO = AutoPolicy()


def validate_preview_options(query_params, *, has_body: bool) -> AutoPolicy:
    """Reject submit/approval flags and unknown params instead of ignoring them.

    Caller must verify request body is strictly empty; no JSON boolean can
    silently authorize actions, even for a signed-in notary.
    """
    if has_body:
        raise UnsafeAutoRequest("preview request body not allowed")
    items = list(query_params.multi_items())
    if items not in ([], [("mode", "auto")]):
        raise UnsafeAutoRequest("only default AUTO preparation is available")
    return DEFAULT_AUTO
