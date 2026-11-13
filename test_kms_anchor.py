"""Offline EIP-1559 and AWS KMS signer tests using synthetic local ECDSA keys."""
from __future__ import annotations
import os

import pytest
import rlp
from eth_utils import keccak
from eth_keys import keys
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec,utils
from kms_anchor import (
    ORDER,PublisherError,checked_chain,hex32,make_signed_transaction,
    kms_public_address,sign_digest_kms
)
PASS_ROOT="ab"*32

class FakeKMS:
    def __init__(self):
        self.private=ec.generate_private_key(ec.SECP256K1())
    def get_public_key(self,KeyId):
        return {"PublicKey":self.private.public_key().public_bytes(
            serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo),
            "SigningAlgorithms":["ECDSA_SHA_256"]}
    def sign(self,KeyId,Message,MessageType,SigningAlgorithm):
        assert MessageType=="DIGEST"
        assert len(Message)==32
        # Crypto test signs *provided* digest (no second hash).
        result=self.private.sign(Message,ec.ECDSA(utils.Prehashed(hashes.SHA256())))
        return {"Signature":result}

def test_kms_signature_uses_public_key_recovery_and_low_s():
    kms=FakeKMS()
    address,pub=kms_public_address(kms,"mock")
    digest=keccak(b"proof-event")
    y,r,s=sign_digest_kms(kms,"mock",digest,pub)
    assert s<=ORDER//2
    assert keys.Signature(vrs=(y,r,s)).recover_public_key_from_msg_hash(digest).to_bytes()==pub
    assert address.startswith("0x")

def test_signed_root_is_single_36_byte_calldata_and_zero_value():
    kms=FakeKMS()
    addr,pub=kms_public_address(kms,"mock")
    tx=make_signed_transaction(root=PASS_ROOT,chain_id=11155111,
        nonce=4,priority_wei=1_000_000_000,max_fee_wei=5_000_000_000,
        gas=25_000,public64=pub,
        signing_fn=lambda d,p:sign_digest_kms(kms,"mock",d,p))
    assert tx["sender"]==addr and tx["recipient"]==addr
    raw=bytes.fromhex(tx["raw"][2:])
    assert raw[:1]==b"\x02"
    fields=rlp.decode(raw[1:])
    assert int.from_bytes(fields[0],"big")==11155111
    assert fields[6]==b"" # no ETH is sent
    assert fields[7]==bytes.fromhex("46595031"+PASS_ROOT)
    assert tx["hash"]=="0x"+keccak(raw).hex()

def test_mainnet_needs_explicit_flag_and_environment(monkeypatch):
    with pytest.raises(PublisherError):checked_chain(1)
    with pytest.raises(PublisherError):checked_chain(1,True)
    monkeypatch.setenv("ETHEREUM_MAINNET_EXPLICIT_APPROVAL","YES")
    checked_chain(1,True)
    with pytest.raises(PublisherError):checked_chain(10,True)

def test_rejects_invalid_root_and_excessive_gas():
    kms=FakeKMS()
    _,pub=kms_public_address(kms,"mock")
    kw=dict(root=PASS_ROOT,chain_id=11155111,nonce=0,
        priority_wei=1,max_fee_wei=3,gas=25_000,public64=pub,
        signing_fn=lambda d,p:sign_digest_kms(kms,"mock",d,p))
    with pytest.raises(PublisherError):make_signed_transaction(**{**kw,"root":"not-a-hash"})
    with pytest.raises(PublisherError):make_signed_transaction(**{**kw,"gas":1_000_000})
