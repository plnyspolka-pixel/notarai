"""Signed, bounded, multi-screen skills for the universal Computer Use agent.

The model never supplies executable code or a fresh selector. A reviewed,
tenant-bound skill references named fields of an approved application profile.
All steps execute under one OS session mutex. No loops, shell, signing or send.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from .fallback_router import AutomationRequest, Outcome, Risk

_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,79}$")
_ACTIONS = frozenset({"read_field", "navigate_to", "fill_draft_field"})


@dataclass(frozen=True)
class Step:
    action: str
    field: str
    expected_field: str | None = None
    value_from: str | None = None

    def __post_init__(self):
        if self.action not in _ACTIONS or not _ID.fullmatch(self.field):
            raise ValueError("unsupported_step")
        if self.action == "navigate_to":
            if not isinstance(self.expected_field, str) or not _ID.fullmatch(self.expected_field):
                raise ValueError("missing_navigation_postcondition")
        elif self.expected_field is not None:
            raise ValueError("unexpected_postcondition")
        if self.action == "fill_draft_field":
            if not isinstance(self.value_from, str) or not _ID.fullmatch(self.value_from):
                raise ValueError("missing_value_binding")
        elif self.value_from is not None:
            raise ValueError("unexpected_value_binding")


@dataclass(frozen=True)
class VerifiedSkill:
    tenant_id: str
    app_id: str
    skill_id: str
    revision: int
    steps: tuple[Step, ...]


def load_signed_skill(raw: bytes, signature: str, key: bytes,
                      *, bound_tenant: str, bound_app: str) -> VerifiedSkill:
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= 16 * 1024:
        raise ValueError("invalid_skill_bytes")
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("invalid_skill_signing_key")
    if not isinstance(signature, str) or len(signature) != 64:
        raise ValueError("invalid_skill_signature")
    if not hmac.compare_digest(hmac.new(key, raw, hashlib.sha256).hexdigest(), signature):
        raise ValueError("skill_signature_mismatch")
    try:
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict) or set(data) != {
            "tenant_id", "app_id", "skill_id", "revision", "steps"
        }:
            raise ValueError("invalid_skill_schema")
        if data["tenant_id"] != bound_tenant or data["app_id"] != bound_app:
            raise ValueError("skill_outside_tenant")
        if not _ID.fullmatch(data["skill_id"]) or type(data["revision"]) is not int or data["revision"] < 1:
            raise ValueError("invalid_skill_identity")
        if not isinstance(data["steps"], list) or not 1 <= len(data["steps"]) <= 12:
            raise ValueError("invalid_skill_length")
        steps = []
        for d in data["steps"]:
            if not isinstance(d, dict) or not set(d).issubset(
                    {"action", "field", "expected_field", "value_from"}):
                raise ValueError("invalid_skill_step")
            steps.append(Step(**d))
    except (KeyError, TypeError, AttributeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_skill_document") from exc
    return VerifiedSkill(bound_tenant, bound_app, data["skill_id"],
                         data["revision"], tuple(steps))


@dataclass(frozen=True)
class WorkflowResult:
    outcome: Outcome
    steps_completed: int
    results: Mapping[str, Any]
    reason: str | None = None


class WorkflowRunner:
    def __init__(self, *, worker, bound_tenant: str, app_profile):
        self.worker = worker
        self.tenant_id = bound_tenant
        self.profile = app_profile

    def run(self, *, job_id: str, skill: VerifiedSkill,
            input_values: Mapping[str, str] | None = None,
            before_each=None) -> WorkflowResult:
        if skill.tenant_id != self.tenant_id or skill.app_id != self.profile.app_id:
            return WorkflowResult(Outcome.DENIED, 0, {}, "workflow_tenant_or_app_mismatch")
        values = input_values or {}
        requests = []
        for step in skill.steps:
            # Every field and postcondition must belong to the reviewed profile.
            if step.field not in self.profile.fields or (
                    step.expected_field and step.expected_field not in self.profile.fields):
                return WorkflowResult(Outcome.DENIED, 0, {}, "unapproved_workflow_field")
            payload = {"field": step.field}
            if step.expected_field is not None:
                payload["expected_field"] = step.expected_field
            if step.action == "fill_draft_field":
                text = values.get(step.value_from)
                if not isinstance(text, str) or not text or len(text) > 2000:
                    return WorkflowResult(Outcome.DENIED, 0, {}, "missing_workflow_input")
                payload["value"] = text
            requests.append(AutomationRequest(
                job_id=job_id,
                tenant_id=self.tenant_id,
                app_id=skill.app_id,
                action=step.action,
                risk=Risk.READ_ONLY if step.action == "read_field" else Risk.DRAFT,
                approval_id=job_id,
                payload=payload,
            ))

        try:
            outcomes = self.worker.execute_sequence(requests, before_each=before_each)
        except Exception:
            # A previous step could already have acted. Never retry the plan.
            return WorkflowResult(Outcome.NEEDS_RECONCILIATION, 0, {},
                                  "workflow_interrupted_unknown_effect")
        successful = 0
        output = {}
        state_changed = False
        for step, result in zip(skill.steps, outcomes):
            if result.outcome is not Outcome.COMPLETED:
                if state_changed:
                    return WorkflowResult(Outcome.NEEDS_RECONCILIATION, successful, output,
                                          "partial_workflow_needs_review")
                return WorkflowResult(result.outcome, successful, output, result.reason)
            successful += 1
            if step.action != "read_field":
                state_changed = True
            if step.action == "read_field":
                output[step.field] = result.data
        if successful != len(skill.steps):
            return WorkflowResult(Outcome.NEEDS_RECONCILIATION, successful, output,
                                  "workflow_incomplete")
        return WorkflowResult(Outcome.COMPLETED, successful, output)
