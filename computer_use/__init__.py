"""NotarAI universal computer-use primitives (no provider SDK dependencies)."""

from .fallback_router import (
    Attempt,
    AttemptStatus,
    AutomationRequest,
    AutomationResponse,
    FallbackRouter,
    Outcome,
    Risk,
    Strategy,
    StrategyResult,
    StrategyUnavailable,
)

__all__ = [
    "Attempt", "AttemptStatus", "AutomationRequest", "AutomationResponse",
    "FallbackRouter", "Outcome", "Risk", "Strategy", "StrategyResult",
    "StrategyUnavailable",
]
