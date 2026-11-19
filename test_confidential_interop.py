"""Browser WebCrypto -> Python decrypt interoperability, using only fictitious data."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from confidential.envelope import Envelope


def test_webcrypto_encrypts_a_document_the_confidential_guest_can_read():
    if not shutil.which("node"):
        pytest.skip("Node.js is not installed (GitHub CI has Node 22)")
    private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")
    payload = {
        "pem": pem,
        "tenant": "fixture_tenant",
        "case": "fixture_case",
        "object": "test01",
        "arn": "arn:aws:kms:eu-central-1:111122223333:key/mock-key",
        "text": "FICTIONAL TEST DOCUMENT / no customer data",
    }
    js = r"""
import { webcrypto } from 'node:crypto';
import { readFile } from 'node:fs/promises';
const source = await readFile(process.env.MODULE_PATH, 'utf8');
const module = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const args = JSON.parse(process.env.TEST_INPUT);
const pin = await module.sha256PublicKey(args.pem);
const bytes = new TextEncoder().encode(args.text);
const e = await module.encryptForConfidentialTask({
 bytes, tenantId: args.tenant, caseId: args.case, objectId: args.object,
 kmsKeyArn: args.arn, publicKeyPem: args.pem, pinnedKeySha256: pin
});
console.log(JSON.stringify(e));
"""
    env = os.environ.copy()
    env["TEST_INPUT"] = json.dumps(payload)
    env["MODULE_PATH"] = str(Path(__file__).parent / "static" / "confidential-crypto.js")
    output = subprocess.run(
        ["node", "--input-type=module", "-"],
        input=js, capture_output=True, text=True, env=env, timeout=30, check=True
    )
    envelope = Envelope.parse(json.loads(output.stdout))
    dek = private.decrypt(envelope.wrapped_dek, padding.OAEP(
        mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None,
    ))
    plain = AESGCM(dek).decrypt(envelope.nonce, envelope.ciphertext, envelope.associated_data())
    assert plain.decode("utf-8") == payload["text"]


def test_mismatched_key_fingerprint_fails_before_encryption():
    if not shutil.which("node"):
        pytest.skip("Node.js is not installed")
    js = r"""
import { webcrypto } from 'node:crypto';
import { readFile } from 'node:fs/promises';
const source = await readFile(process.env.MODULE_PATH, 'utf8');
const module = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const key = await crypto.subtle.generateKey(
 {name:'RSA-OAEP', modulusLength:3072, publicExponent:new Uint8Array([1,0,1]), hash:'SHA-256'},
 true, ['encrypt','decrypt']);
const der = await crypto.subtle.exportKey('spki', key.publicKey);
const pem = '-----BEGIN PUBLIC KEY-----\n' + Buffer.from(der).toString('base64') + '\n-----END PUBLIC KEY-----';
try {
 await module.encryptForConfidentialTask({
  bytes:new TextEncoder().encode('test'), tenantId:'t', caseId:'c', objectId:'o',
  kmsKeyArn:'arn:aws:kms:eu-central-1:111122223333:key/mock',
  publicKeyPem:pem, pinnedKeySha256:'wrong-fingerprint'
 });
 throw new Error('fingerprint pin was bypassed');
} catch(e) {
 if (e.message !== 'KMS public key fingerprint mismatch') throw e;
}
"""
    env = os.environ.copy()
    env["MODULE_PATH"] = str(Path(__file__).parent / "static" / "confidential-crypto.js")
    subprocess.run(
        ["node", "--input-type=module", "-"],
        input=js, capture_output=True, text=True, env=env, timeout=30, check=True,
    )
