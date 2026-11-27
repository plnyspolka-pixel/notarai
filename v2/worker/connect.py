"""Local integration routing. No arbitrary shell, no remote execution endpoint."""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

class State(str, Enum):
    UNAVAILABLE = "unavailable"  # probe only; no action attempted
    VERIFIED = "verified"
    UNCERTAIN = "uncertain"

@dataclass(frozen=True)
class Result:
    state: State
    backend: str
    data: object = None

class Adapter(Protocol):
    name: str
    def supports(self, operation: str) -> bool: ...
    def execute(self, operation: str, args: dict) -> Result: ...

class Router:
    """An attempted action never falls through to another backend."""
    def __init__(self, adapters):
        self.adapters = tuple(adapters)
    def run(self, operation, args):
        # This milestone permits inspection only. No model-generated writes.
        if operation not in {"inspect_window", "list_windows"}:
            raise PermissionError("operation not enabled")
        for adapter in self.adapters:
            try:
                if not adapter.supports(operation):
                    continue
            except Exception:
                continue  # capability probe must be side-effect-free
            try:
                result = adapter.execute(operation, args)
                if not isinstance(result, Result) or result.backend != adapter.name:
                    return Result(State.UNCERTAIN, adapter.name)
                # Even if backend reports unavailable after invocation, do not retry.
                return result if result.state == State.VERIFIED else Result(State.UNCERTAIN, adapter.name)
            except Exception:
                return Result(State.UNCERTAIN, adapter.name)
        return Result(State.UNAVAILABLE, "none")
