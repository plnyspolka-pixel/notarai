"""Isolated tests: no Windows, external integrations, or client data required."""
import unittest

from computer_use.fallback_router import (
    AttemptStatus, AutomationRequest, FallbackRouter,
    Outcome, Risk, StrategyResult,
)


class StubStrategy:
    def __init__(self, name, supported, result=None, error=None):
        self.name = name
        self.supported = supported
        self.result = result
        self.error = error
        self.calls = 0

    def supports(self, request):
        return self.supported

    def perform(self, request):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def req(risk=Risk.READ_ONLY, approval_id=None):
    return AutomationRequest(
        job_id="j-1", action="find_case", app_id="unknown_app",
        tenant_id="trusted-tenant-context", risk=risk, approval_id=approval_id,
    )


class Approved:
    def is_authorized(self, request):
        return request.tenant_id == "trusted-tenant-context" and request.approval_id == "ok"


class FallbackTests(unittest.TestCase):
    def test_skips_unavailable_and_falls_back_to_uia(self):
        api = StubStrategy("native_api", False)
        web = StubStrategy("web_dom", True, StrategyResult(AttemptStatus.RECOVERABLE_FAILURE))
        uia = StubStrategy("windows_uia", True, StrategyResult(
            AttemptStatus.SUCCESS, postcondition_verified=True, data={"found": True}))
        out = FallbackRouter([uia, api, web]).execute(req())
        self.assertEqual(out.outcome, Outcome.COMPLETED)
        self.assertEqual(out.strategy, "windows_uia")
        self.assertEqual((api.calls, web.calls, uia.calls), (0, 1, 1))
        self.assertEqual([a.strategy for a in out.attempts], ["native_api", "web_dom", "windows_uia"])

    def test_no_unapproved_write(self):
        api = StubStrategy("native_api", True, StrategyResult(AttemptStatus.SUCCESS, True))
        out = FallbackRouter([api], approval_verifier=Approved()).execute(req(Risk.WRITE))
        self.assertEqual(out.outcome, Outcome.DENIED)
        self.assertEqual(api.calls, 0)

    def test_human_required_for_external_even_with_approval(self):
        api = StubStrategy("native_api", True, StrategyResult(AttemptStatus.SUCCESS, True))
        out = FallbackRouter([api], approval_verifier=Approved()).execute(req(Risk.EXTERNAL, "ok"))
        self.assertEqual(out.outcome, Outcome.WAITING_FOR_HUMAN)
        self.assertEqual(api.calls, 0)

    def test_write_requires_clean_state_before_fallback(self):
        api = StubStrategy("native_api", True, StrategyResult(AttemptStatus.RECOVERABLE_FAILURE))
        uia = StubStrategy("windows_uia", True, StrategyResult(AttemptStatus.SUCCESS, True))
        out = FallbackRouter([api, uia], approval_verifier=Approved()).execute(req(Risk.WRITE, "ok"))
        self.assertEqual(out.outcome, Outcome.NEEDS_RECONCILIATION)
        self.assertEqual(uia.calls, 0)

    def test_write_can_fallback_if_rollback_verified(self):
        api = StubStrategy("native_api", True, StrategyResult(
            AttemptStatus.RECOVERABLE_FAILURE, clean_state_confirmed=True))
        uia = StubStrategy("windows_uia", True, StrategyResult(AttemptStatus.SUCCESS, True))
        out = FallbackRouter([api, uia], approval_verifier=Approved()).execute(req(Risk.WRITE, "ok"))
        self.assertEqual(out.outcome, Outcome.COMPLETED)
        self.assertEqual(uia.calls, 1)

    def test_unverified_write_requires_reconciliation(self):
        api = StubStrategy("native_api", True, StrategyResult(AttemptStatus.SUCCESS))
        out = FallbackRouter([api], approval_verifier=Approved()).execute(req(Risk.WRITE, "ok"))
        self.assertEqual(out.outcome, Outcome.NEEDS_RECONCILIATION)

    def test_exception_does_not_trigger_blind_fallback(self):
        api = StubStrategy("native_api", True, error=RuntimeError("no client data"))
        uia = StubStrategy("windows_uia", True, StrategyResult(AttemptStatus.SUCCESS, True))
        out = FallbackRouter([api, uia]).execute(req())
        self.assertEqual(out.outcome, Outcome.NEEDS_RECONCILIATION)
        self.assertEqual(uia.calls, 0)

    def test_explicit_denial_stops_all_strategies(self):
        api = StubStrategy("native_api", True, StrategyResult(AttemptStatus.POLICY_DENIED))
        uia = StubStrategy("windows_uia", True, StrategyResult(AttemptStatus.SUCCESS, True))
        out = FallbackRouter([api, uia]).execute(req())
        self.assertEqual(out.outcome, Outcome.DENIED)
        self.assertEqual(uia.calls, 0)

    def test_human_fallback_can_finish_with_handoff(self):
        api = StubStrategy("native_api", False)
        human = StubStrategy("human_handoff", True, StrategyResult(AttemptStatus.HUMAN_REQUIRED))
        out = FallbackRouter([api, human]).execute(req())
        self.assertEqual(out.outcome, Outcome.WAITING_FOR_HUMAN)
        self.assertEqual(out.strategy, "human_handoff")

    def test_draft_does_not_fallback_after_unverified_effect(self):
        uia = StubStrategy("windows_uia", True, StrategyResult(AttemptStatus.RECOVERABLE_FAILURE))
        vision = StubStrategy("uia_vision", True, StrategyResult(AttemptStatus.SUCCESS, True))
        out = FallbackRouter([uia, vision]).execute(req(Risk.DRAFT))
        self.assertEqual(out.outcome, Outcome.NEEDS_RECONCILIATION)
        self.assertEqual(vision.calls, 0)

    def test_unsupported_read_only(self):
        out = FallbackRouter([StubStrategy("native_api", False)]).execute(req())
        self.assertEqual(out.outcome, Outcome.UNSUPPORTED)

    def test_duplicate_strategy_rejected(self):
        with self.assertRaises(ValueError):
            FallbackRouter([StubStrategy("web_dom", False), StubStrategy("web_dom", True)])

    def test_result_data_absent_from_attempts(self):
        sensitive = "FAKE-CLIENT-DATA"
        api = StubStrategy("native_api", True, StrategyResult(AttemptStatus.SUCCESS, True, data=sensitive))
        out = FallbackRouter([api]).execute(req())
        self.assertEqual(out.data, sensitive)
        self.assertNotIn(sensitive, str(out.attempts))


if __name__ == "__main__":
    unittest.main()
