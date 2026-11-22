"""No production secrets or customer data. Run: pytest -q test_confidential.py."""
import asyncio
import base64

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import serialization

from confidential.attested_kms import AttestationRequired, AttestedKMSUnwrapper
from confidential.envelope import Envelope, InvalidEnvelope
from confidential.form_engine import BlockedAction, TrustedForm, fill_form


ARN = "arn:aws:kms:eu-central-1:111122223333:key/12345678-abcd"


def make_document():
    private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    key = bytes(range(32))
    nonce = bytes(range(12))
    wrapped = private.public_key().encrypt(key, padding.OAEP(
        mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None
    ))
    identity = "notarai-v1|test_tenant|test_case|scan01".encode()
    cipher = AESGCM(key).encrypt(nonce, b"FICTITIOUS NOTARIAL DOCUMENT", identity)
    return private, key, {
        "version": 1, "algorithm": "AES-256-GCM+RSA-OAEP-SHA256",
        "tenant_id": "test_tenant", "case_id": "test_case", "object_id": "scan01",
        "kms_key_arn": ARN,
        "nonce": base64.b64encode(nonce).decode(),
        "wrapped_dek": base64.b64encode(wrapped).decode(),
        "ciphertext": base64.b64encode(cipher).decode(),
    }


class FakeProvider:
    def __init__(self, key):
        self.key = key

    def signed_document(self):
        return b"TEST ONLY: NOT A REAL NITRO ATTESTATION"

    def unwrap_recipient_cms(self, cms_der):
        assert cms_der == b"fake-cms"
        return self.key


class FakeKMS:
    def __init__(self, plaintext=False):
        self.plaintext = plaintext
        self.calls = []

    def decrypt(self, **kwargs):
        self.calls.append(kwargs)
        if self.plaintext:
            return {"Plaintext": b"should never be accepted"}
        return {"CiphertextForRecipient": b"fake-cms"}


def test_envelope_roundtrip_and_kms_recipient():
    _, key, payload = make_document()
    kms = FakeKMS()
    provider = FakeProvider(key)
    envelope = Envelope.parse(payload)
    unwrap = AttestedKMSUnwrapper(kms, provider, ARN)
    assert envelope.open_inside_attested_task(unwrap) == b"FICTITIOUS NOTARIAL DOCUMENT"
    assert kms.calls[0]["Recipient"]["AttestationDocument"].startswith(b"TEST ONLY")
    assert kms.calls[0]["EncryptionAlgorithm"] == "RSAES_OAEP_SHA_256"
    assert "EncryptionContext" not in kms.calls[0]


def test_envelope_rejects_tampering_and_unsafe_inputs():
    _, key, payload = make_document()
    with pytest.raises(InvalidEnvelope):
        Envelope.parse({**payload, "case_id": "other"}).open_inside_attested_task(
            AttestedKMSUnwrapper(FakeKMS(), FakeProvider(key), ARN)
        )
    with pytest.raises(InvalidEnvelope):
        Envelope.parse({**payload, "tenant_id": "../secret"})
    with pytest.raises(InvalidEnvelope):
        Envelope.parse({**payload, "nonce": "%%%"})
    with pytest.raises(InvalidEnvelope):
        Envelope.parse({**payload, "version": True})
    with pytest.raises(InvalidEnvelope):
        Envelope.parse({**payload, "unknown": "extra"})


def test_kms_fail_closed_for_plaintext_or_wrong_key():
    _, key, payload = make_document()
    env = Envelope.parse(payload)
    with pytest.raises(AttestationRequired):
        env.open_inside_attested_task(AttestedKMSUnwrapper(FakeKMS(plaintext=True), FakeProvider(key), ARN))
    with pytest.raises(AttestationRequired):
        env.open_inside_attested_task(AttestedKMSUnwrapper(FakeKMS(), FakeProvider(key),
                              "arn:aws:kms:eu-west-1:111122223333:key/different"))


class Route:
    def __init__(self, url, method="GET"):
        self.request = type("Request", (), {"url": url, "method": method})()
        self.action = None

    async def abort(self):
        self.action = "abort"

    async def continue_(self):
        self.action = "continue"


class Locator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    async def fill(self, value, timeout):
        self.page.fills.append((self.selector, value))

    async def click(self, timeout):
        self.page.clicks.append(self.selector)


class FakeContext:
    def __init__(self, page):
        self.page = page
        self.websocket_filter = None
        self.init_script = None

    async def route(self, pattern, callback):
        self.page.filter = callback

    async def route_web_socket(self, pattern, callback):
        self.websocket_filter = callback

    async def add_init_script(self, *, script):
        self.init_script = script


class Page:
    def __init__(self):
        self.url = ""
        self.fills = []
        self.clicks = []
        self.filter = None
        self.context = FakeContext(self)

    async def route(self, pattern, callback):
        self.filter = callback

    async def goto(self, url, **kwargs):
        self.url = url

    def locator(self, selector):
        return Locator(self, selector)


def form():
    return TrustedForm(
        "fixture", "https://forms.example.test/app",
        ("https://forms.example.test",), {"name": "#name"}, "#submit",
    )


def test_form_fill_preview_and_network_allowlist():
    async def run():
        page = Page()
        result = await fill_form(page, form(), {"name": "Fictional Tester"}, job_id="job-1")
        assert result.filled_fields == 1 and result.submitted is False
        assert result.origin == "https://forms.example.test"
        assert page.fills == [("#name", "Fictional Tester")] and not page.clicks
        good, bad = Route("https://forms.example.test/script.js"), Route("http://169.254.169.254/latest")
        await page.filter(good)
        await page.filter(bad)
        assert good.action == "abort" and bad.action == "abort"
    asyncio.run(run())


def test_form_submit_requires_external_approval_and_restricts_fields():
    async def run():
        page = Page()
        with pytest.raises(BlockedAction):
            await fill_form(page, form(), {"name": "Fictional"}, job_id="job-2", submit=True)
        assert not page.clicks
        async def approve(job, form_id, digest, origin):
            return (job == "job-2" and form_id == "fixture" and
                    len(digest) == 64 and origin == "https://forms.example.test")
        result = await fill_form(page, form(), {"name": "Fictional"}, job_id="job-2",
                                 submit=True, approve=approve, execution_mode="supervised")
        assert result.submitted and page.clicks == ["#submit"]
        with pytest.raises(BlockedAction):
            await fill_form(Page(), form(), {"admin": "abuse"}, job_id="job-2")
    asyncio.run(run())


def test_form_blocks_unauthorized_origins_and_insecure_http():
    with pytest.raises(BlockedAction):
        TrustedForm("x", "https://evil.example/a", ("https://safe.example",), {"a": "#a"}).validate()
    with pytest.raises(BlockedAction):
        TrustedForm("x", "http://safe.example/a", ("http://safe.example",), {"a": "#a"}).validate()
