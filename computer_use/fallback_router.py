"""Policy-gated, capability-aware orchestration for NotarAI Computer Use.

This is the routing core, not a Windows agent or an API integration.
Providers implement Strategy against approved application interfaces.

Design invariant: no automatic failover after a potentially committed action
unless the provider can attest the previous attempt left a clean state.
Neither LLM decisions nor arbitrary GUI contents can override that rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence


# Canonical priority: least intervention/configuration and highest stability first.
# A provider may be omitted if its capability probe is negative.
DEFAULT_ORDER: tuple[str, ...] = (
    "native_api",
    "web_dom",
    "windows_uia",
    "uia_vision",
    "visual_computer_use",
    "guided_demonstration",
    "human_handoff",
)


class Risk(str, Enum):
    READ_ONLY = "read_only"
    DRAFT = "draft"
    WRITE = "write"
    EXTERNAL = "external"  # sending, signing, purchasing, submissions


class Outcome(str, Enum):
    COMPLETED = "completed"
    UNSUPPORTED = "unsupported"
    WAITING_FOR_HUMAN = "waiting_for_human"
    NEEDS_RECONCILIATION = "needs_reconciliation"
    DENIED = "denied"
    FAILED = "failed"


class AttemptStatus(str, Enum):
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"       # definitive lack of capability
    RECOVERABLE_FAILURE = "recoverable_failure"
    HUMAN_REQUIRED = "human_required"
    POLICY_DENIED = "policy_denied"
    UNKNOWN_EFFECT = "unknown_effect"  # a write may already have happened


@dataclass(frozen=True)
class AutomationRequest:
    job_id: str
    action: str
    app_id: str
    risk: Risk
    # Authoritative server-side tenant context; never filled by an LLM.
    tenant_id: str
    # Approval ID supplied by a trusted authorization system, not an LLM.
    approval_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not all((self.job_id, self.action, self.app_id, self.tenant_id)):
            raise ValueError("job_id, action, app_id, tenant_id are required")
        if not isinstance(self.risk, Risk):
            raise ValueError("risk must be a Risk enum")


@dataclass(frozen=True)
class StrategyResult:
    status: AttemptStatus
    # SUCCESS requires postcondition_verified, never trust "click returned OK".
    postcondition_verified: bool = False
    # True ONLY if no externally visible or persistent effect took place AND
    # the UI/transaction state is safe for a different strategy to continue.
    clean_state_confirmed: bool = False
    # Data stays in the authorized request/response channel, never in audit.
    data: Any = None
    diagnostic_code: str | None = None


@dataclass(frozen=True)
class Attempt:
    strategy: str
    status: str
    diagnostic_code: str | None = None


@dataclass(frozen=True)
class AutomationResponse:
    outcome: Outcome
    strategy: str | None = None
    data: Any = None
    attempts: tuple[Attempt, ...] = ()
    reason: str | None = None


class StrategyUnavailable(Exception):
    """A strategy could not safely start; it guarantees no side effects."""


class Strategy(Protocol):
    name: str

    def supports(self, request: AutomationRequest) -> bool:
        """Read-only capability check. Do not change application state."""

    def perform(self, request: AutomationRequest) -> StrategyResult:
        """Execute a policy-approved action and verify its postcondition."""


class ApprovalVerifier(Protocol):
    def is_authorized(self, request: AutomationRequest) -> bool:
        """Validate tenant/user/action/bound approval on trusted server."""


class FallbackRouter:
    def __init__(
        self,
        strategies: Sequence[Strategy],
        *,
        approval_verifier: ApprovalVerifier | None = None,
        order: Sequence[str] = DEFAULT_ORDER,
    ) -> None:
        names = [s.name for s in strategies]
        if len(set(names)) != len(names):
            raise ValueError("Duplicate strategy name")
        if len(set(order)) != len(order):
            raise ValueError("Duplicate strategy in priority order")
        self._strategies = {s.name: s for s in strategies}
        self._order = tuple(order)
        self._verifier = approval_verifier

    def execute(self, request: AutomationRequest) -> AutomationResponse:
        # Never automatically run formal operations, even with an approval.
        if request.risk is Risk.EXTERNAL:
            return AutomationResponse(
                outcome=Outcome.WAITING_FOR_HUMAN,
                reason="external_or_formal_action_requires_human",
            )
        if request.risk is Risk.WRITE:
            if (not request.approval_id or self._verifier is None or
                    not self._verifier.is_authorized(request)):
                return AutomationResponse(
                    outcome=Outcome.DENIED, reason="verified_approval_required"
                )

        attempts: list[Attempt] = []
        for name in self._order:
            strategy = self._strategies.get(name)
            if strategy is None:
                continue

            # A broken capability probe must not crash the whole route,
            # but only a typed no-side-effect failure can be skipped.
            try:
                if not strategy.supports(request):
                    attempts.append(Attempt(name, "not_supported"))
                    continue
            except StrategyUnavailable:
                attempts.append(Attempt(name, "unavailable"))
                continue
            except Exception:
                attempts.append(Attempt(name, "probe_error"))
                return AutomationResponse(
                    Outcome.FAILED, attempts=tuple(attempts), reason="untrusted_probe_error"
                )

            try:
                result = strategy.perform(request)
            except StrategyUnavailable:
                attempts.append(Attempt(name, "unavailable"))
                continue
            except Exception:
                # Unknown exception may occur AFTER a GUI interaction or write.
                attempts.append(Attempt(name, "unhandled_exception"))
                return AutomationResponse(
                    Outcome.NEEDS_RECONCILIATION,
                    strategy=name, attempts=tuple(attempts),
                    reason="exception_effect_unknown",
                )

            attempts.append(Attempt(name, result.status.value, result.diagnostic_code))
            if result.status is AttemptStatus.SUCCESS:
                if result.postcondition_verified:
                    return AutomationResponse(
                        Outcome.COMPLETED, strategy=name,
                        data=result.data, attempts=tuple(attempts)
                    )
                # On read-only tasks a failed postcondition may safely fall back.
                # For every potentially state-changing request require clean proof.
                if request.risk is Risk.READ_ONLY or result.clean_state_confirmed:
                    continue
                return AutomationResponse(
                    Outcome.NEEDS_RECONCILIATION, strategy=name,
                    attempts=tuple(attempts), reason="postcondition_unverified",
                )

            if result.status is AttemptStatus.HUMAN_REQUIRED:
                return AutomationResponse(
                    Outcome.WAITING_FOR_HUMAN, strategy=name, attempts=tuple(attempts),
                    reason="operator_intervention_required",
                )
            if result.status is AttemptStatus.POLICY_DENIED:
                return AutomationResponse(
                    Outcome.DENIED, strategy=name, attempts=tuple(attempts),
                    reason="policy_denied",
                )
            if result.status is AttemptStatus.UNKNOWN_EFFECT:
                return AutomationResponse(
                    Outcome.NEEDS_RECONCILIATION, strategy=name, attempts=tuple(attempts),
                    reason="unknown_side_effect",
                )
            if result.status in (AttemptStatus.RECOVERABLE_FAILURE, AttemptStatus.UNAVAILABLE):
                if request.risk is Risk.READ_ONLY or result.clean_state_confirmed:
                    continue
                return AutomationResponse(
                    Outcome.NEEDS_RECONCILIATION, strategy=name,
                    attempts=tuple(attempts), reason="clean_state_not_confirmed",
                )

        if request.risk is Risk.READ_ONLY:
            return AutomationResponse(
                Outcome.UNSUPPORTED, attempts=tuple(attempts),
                reason="all_supported_strategies_exhausted",
            )
        return AutomationResponse(
            Outcome.WAITING_FOR_HUMAN, attempts=tuple(attempts),
            reason="no_verified_safe_strategy",
        )
