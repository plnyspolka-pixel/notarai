"""Vision computer-use regression tests without images of actual clients."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from computer_use.fallback_router import AutomationRequest, FallbackRouter, Outcome, Risk
from computer_use.profiles import AppProfile, Element
from computer_use.vision import (
    BedrockVisionModel, Frame, Observation, VisualStrategy,
)

PNG = b"\x89PNG\r\n\x1a\nFAKE_NON_PERSONAL_TEST_FRAME"


class MockDesktop:
    def __init__(self):
        self.frame = Frame(PNG, 800, 600, 120, 40, 101)
        self.calls = []
        self.fail_after_click = False

    def capture(self, app):
        self.calls.append(("capture", app))
        return self.frame

    def click(self, app, frame, x, y):
        self.calls.append(("click", x, y))
        if self.fail_after_click:
            raise RuntimeError("interactive desktop failed")

    def type_literal(self, app, value):
        self.calls.append(("type", value))


class MockVision:
    def __init__(self, *, confidence=0.99, value="FIKCYJNE", loc=(0.5, 0.6), second=None):
        self.calls = []
        self.confidence = confidence
        self.value = value
        self.loc = loc
        self.second = second

    def locate(self, png, target, *, mode, frame_digest):
        self.calls.append((target, mode))
        value = self.second if mode == "verify" and self.second is not None else self.value
        return Observation(value, self.loc[0], self.loc[1], self.confidence, frame_digest)


def request(action="read_field", risk=Risk.READ_ONLY, value=None):
    payload = {"field": "numer"}
    if value is not None:
        payload["value"] = value
    return AutomationRequest(
        job_id="test", tenant_id="fictional_tenant", app_id="test-app",
        risk=risk, action=action, payload=payload,
    )


def profile(*, editable=False, with_uia=False):
    fields = [Element("visual", "Numer repertorium", value_mode="input" if editable else "text",
                      allow_draft_fill=editable)]
    if with_uia:
        fields.append(Element("uia", "RepA"))
    return AppProfile("test-app", windows_app="notepad",
                      fields={"numer": tuple(fields)})


def test_visual_read_requires_double_model_confirmation():
    d, v = MockDesktop(), MockVision()
    out = FallbackRouter([VisualStrategy(profile(), desktop=d, vision=v, enabled=True)]).execute(request())
    assert out.outcome is Outcome.COMPLETED
    assert out.data == {"field": "numer", "value": "FIKCYJNE"}
    assert v.calls == [("Numer repertorium", "read"), ("Numer repertorium", "verify")]
    assert d.calls == [("capture", "notepad")]


def test_visual_read_mismatch_falls_back():
    d, v = MockDesktop(), MockVision(second="SOMETHING_ELSE")
    out = FallbackRouter([VisualStrategy(profile(), desktop=d, vision=v, enabled=True)]).execute(request())
    assert out.outcome is Outcome.UNSUPPORTED


def test_visual_draft_edit_needs_signed_profile_explicit_optin():
    d, v = MockDesktop(), MockVision(value="FIKCYJNE")
    out = FallbackRouter([VisualStrategy(profile(editable=True), desktop=d, vision=v, enabled=True)]).execute(
        request("fill_draft_field", Risk.DRAFT, "FIKCYJNE"))
    assert out.outcome is Outcome.COMPLETED
    assert ("click", .5, .6) in d.calls
    assert ("type", "FIKCYJNE") in d.calls


def test_visual_draft_is_not_used_without_approval_in_profile():
    d, v = MockDesktop(), MockVision()
    out = FallbackRouter([VisualStrategy(profile(), desktop=d, vision=v, enabled=True)]).execute(
        request("fill_draft_field", Risk.DRAFT, "FIKCYJNE"))
    assert out.outcome is Outcome.WAITING_FOR_HUMAN
    assert d.calls == []


def test_image_processing_disabled_by_default():
    d, v = MockDesktop(), MockVision()
    s = VisualStrategy(profile(), desktop=d, vision=v)
    assert s.supports(request()) is False
    assert d.calls == []


def test_low_confidence_does_not_click():
    d, v = MockDesktop(), MockVision(confidence=.5)
    out = FallbackRouter([VisualStrategy(profile(editable=True), desktop=d, vision=v, enabled=True)]).execute(
        request("fill_draft_field", Risk.DRAFT, "FIKCYJNE"))
    assert out.outcome is Outcome.WAITING_FOR_HUMAN
    assert not any(k[0] == "click" for k in d.calls)


def test_unknown_input_effect_does_not_retry():
    d, v = MockDesktop(), MockVision()
    d.fail_after_click = True
    out = FallbackRouter([VisualStrategy(profile(editable=True), desktop=d, vision=v, enabled=True)]).execute(
        request("fill_draft_field", Risk.DRAFT, "FIKCYJNE"))
    assert out.outcome is Outcome.NEEDS_RECONCILIATION


def test_hybrid_needs_uia_metadata():
    d, v = MockDesktop(), MockVision()
    strategy = VisualStrategy(profile(), desktop=d, vision=v, enabled=True, hybrid=True)
    assert strategy.supports(request()) is False
    strategy = VisualStrategy(profile(with_uia=True), desktop=d, vision=v, enabled=True, hybrid=True)
    assert strategy.supports(request()) is True


def test_protected_fields_not_sent_to_model():
    p = AppProfile("test-app", windows_app="notepad",
                   fields={"numer": Element("visual", "PIN do podpisu")})
    d, v = MockDesktop(), MockVision()
    assert VisualStrategy(p, desktop=d, vision=v, enabled=True).supports(request()) is False


def test_bedrock_stays_disabled_without_explicit_consent():
    client = Mock()
    model = BedrockVisionModel(client=client, region="eu-central-1", model_id="eu.test-vision")
    with pytest.raises(PermissionError):
        model.locate(PNG, "test", mode="read", frame_digest="foo")
    client.converse.assert_not_called()


def test_bedrock_converse_uses_in_memory_png_and_validated_json():
    client = Mock()
    client.converse.return_value = {"output": {"message": {"content": [
        {"text": json.dumps({"value":"FIKCYJNE", "x": .5,"y":.5, "confidence":.99})}
    ]}}}
    model = BedrockVisionModel(client=client, region="eu-central-1",
                              model_id="eu.test-vision", expressly_enabled=True)
    o = model.locate(PNG,"Case", mode="read", frame_digest="hash")
    assert o.value == "FIKCYJNE"
    args = client.converse.call_args.kwargs
    assert args["messages"][0]["content"][0]["image"]["source"]["bytes"] == PNG
    assert args["modelId"] == "eu.test-vision"


def test_bedrock_rejects_malformed_model_action():
    client = Mock()
    client.converse.return_value = {"output": {"message": {"content": [
        {"text": '{"value":"ok","x":0.5,"y":0.5,"confidence":0.99,"action":"delete"}'}
    ]}}}
    model = BedrockVisionModel(client=client, region="eu-central-1",
                              model_id="eu.test-vision", expressly_enabled=True)
    with pytest.raises(ValueError, match="schema"):
        model.locate(PNG,"Case",mode="read",frame_digest="hash")


def test_bedrock_non_eu_model_or_region_rejected():
    with pytest.raises(ValueError):
        BedrockVisionModel(client=Mock(), region="us-east-1", model_id="eu.fake")
    with pytest.raises(ValueError):
        BedrockVisionModel(client=Mock(), region="eu-central-1", model_id="us.fake")


def test_frame_and_coordinates_rejected_when_invalid():
    with pytest.raises(ValueError):
        Frame(b"not png",800,600,0,0,1)
    with pytest.raises(ValueError):
        Observation("x",1.5,.5,.99,"abc")
