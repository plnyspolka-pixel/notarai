"""Ethereum root publisher using a nonexportable AWS KMS secp256k1 key.

EIP-1559, chain-allowlisted, capped gas and fees, zero-value transfer
to the KMS signer address itself with 0x46595031||Merkle-root calldata.

Defaults to offline/dry-run and Sepolia. NO raw private key in env/repo.
Do not run on real user funds or Mainnet without separate approval.
"""
from __future__ import annotations
import argparse
import json
import os
import re
from dataclasses import dataclass
from typing import Callable, Any

import rlp
from eth_utils import keccak, to_checksum_address
from eth_keys.keys import Signature
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils

ORDER=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
HEX32=re.compile(r"^[a-fA-F0-9]{64}$")
ALLOWED_CHAINS={11155111:"Sepolia",31337:"Local",1:"Ethereum Mainnet"}
PREFIX=bytes.fromhex("46595031")


class PublisherError(RuntimeError): pass


def hex32(root:str)->bytes:
    if not HEX32.fullmatch(root):raise PublisherError("Invalid 32-byte Merkle root")
    return bytes.fromhex(root)


def kms_public_address(kms_client:Any,key_id:str) -> tuple[str,bytes]:
    pub=kms_client.get_public_key(KeyId=key_id)
    obj=serialization.load_der_public_key(pub["PublicKey"])
    if not isinstance(obj,ec.EllipticCurvePublicKey) or not isinstance(obj.curve,ec.SECP256K1):
        raise PublisherError("KMS key must be asymmetric ECC_SECG_P256K1")
    if "ECDSA_SHA_256" not in pub.get("SigningAlgorithms",["ECDSA_SHA_256"]):
        raise PublisherError("KMS key is not enabled for ECDSA digest signing")
    uncompressed=obj.public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    address=to_checksum_address("0x"+keccak(uncompressed[1:])[-20:].hex())
    return address,uncompressed[1:]


def sign_digest_kms(kms_client:Any,key_id:str,digest:bytes,public64:bytes)->tuple[int,int,int]:
    if len(digest)!=32 or len(public64)!=64:raise PublisherError("Invalid digest or signer public key")
    der=kms_client.sign(KeyId=key_id,Message=digest,MessageType="DIGEST",
                        SigningAlgorithm="ECDSA_SHA_256")["Signature"]
    r,s=utils.decode_dss_signature(der)
    if not (1<=r<ORDER and 1<=s<ORDER):
        raise PublisherError("Invalid secp256k1 signature")
    s=min(s,ORDER-s)
    for parity in (0,1):
        recovered=Signature(vrs=(parity,r,s)).recover_public_key_from_msg_hash(digest)
        if recovered.to_bytes()==public64:return parity,r,s
    raise PublisherError("Signature recovery does not match the KMS public key")


def int_hex(value:str)->int:
    if not isinstance(value,str) or not re.fullmatch(r"0x[0-9a-fA-F]+",value):
        raise PublisherError("Ethereum RPC returned invalid hex quantity")
    return int(value,16)


def checked_chain(chain:int,allow_mainnet:bool=False)->None:
    if chain not in ALLOWED_CHAINS:raise PublisherError("Unapproved Ethereum chain")
    if chain==1 and not (allow_mainnet and os.getenv("ETHEREUM_MAINNET_EXPLICIT_APPROVAL")=="YES"):
        raise PublisherError("Mainnet is disabled without explicit two-factor operator approval")


def make_signed_transaction(*,root:str,chain_id:int,nonce:int,priority_wei:int,
                            max_fee_wei:int,gas:int,public64:bytes,
                            signing_fn:Callable[[bytes,bytes],tuple[int,int,int]],
                            allow_mainnet:bool=False)->dict:
    checked_chain(chain_id,allow_mainnet)
    for number in (nonce,priority_wei,max_fee_wei,gas):
        if not isinstance(number,int) or number<0:raise PublisherError("Invalid EIP-1559 integer")
    if gas<21_000 or gas>50_000 or max_fee_wei<priority_wei:
        raise PublisherError("Invalid gas configuration")
    recipient=keccak(public64)[-20:]
    data=PREFIX+hex32(root)
    # calldata contains *only* the root and 4-byte protocol marker; no PII.
    unsigned=[chain_id,nonce,priority_wei,max_fee_wei,gas,recipient,0,data,[]]
    digest=keccak(b"\x02"+rlp.encode(unsigned))
    y,r,s=signing_fn(digest,public64)
    if y not in (0,1) or not 1<=r<ORDER or not 1<=s<=ORDER//2:
        raise PublisherError("Signer must return canonical low-S signature")
    raw=b"\x02"+rlp.encode(unsigned+[y,r,s])
    txid="0x"+keccak(raw).hex()
    return {"raw":"0x"+raw.hex(),"hash":txid,"chainId":chain_id,
            "gas":gas,"maxFeeWei":max_fee_wei,
            "sender":to_checksum_address("0x"+recipient.hex()),
            "recipient":to_checksum_address("0x"+recipient.hex()),
            "data":"0x"+data.hex()}


def rpc_call(session,endpoint:str,method:str,params:list)->Any:
    if not endpoint.startswith("https://"):
        raise PublisherError("Only HTTPS Ethereum RPC is allowed")
    reply=session.post(endpoint,json={"jsonrpc":"2.0","id":1,"method":method,"params":params},timeout=15)
    reply.raise_for_status()
    out=reply.json()
    if "error" in out:raise PublisherError("Ethereum RPC rejected "+method)
    return out.get("result")


def publish_kms_root(*,root:str,chain_id:int,kms_key_id:str,endpoint:str,
                     kms_client:Any,rpc_session:Any,broadcast:bool=False,
                     allow_mainnet:bool=False,max_gas_price_gwei:int=100,
                     max_total_fee_wei:int=3_000_000_000_000_000)->dict:
    checked_chain(chain_id,allow_mainnet)
    if not kms_key_id:raise PublisherError("Missing KMS key identifier")
    rpc_chain=int_hex(rpc_call(rpc_session,endpoint,"eth_chainId",[]))
    if rpc_chain!=chain_id:raise PublisherError("RPC returned different chain")
    sender,public64=kms_public_address(kms_client,kms_key_id)
    nonce=int_hex(rpc_call(rpc_session,endpoint,"eth_getTransactionCount",[sender,"pending"]))
    block=rpc_call(rpc_session,endpoint,"eth_getBlockByNumber",["latest",False])
    if not isinstance(block,dict) or "baseFeePerGas" not in block:
        raise PublisherError("EIP-1559 base fee is unavailable")
    base_fee=int_hex(block["baseFeePerGas"])
    try:
        priority=int_hex(rpc_call(rpc_session,endpoint,"eth_maxPriorityFeePerGas",[]))
    except PublisherError:
        priority=1_000_000_000
    max_fee=2*base_fee+priority
    if max_fee>max_gas_price_gwei*1_000_000_000 or max_fee*25_000>max_total_fee_wei:
        raise PublisherError("Gas price or total cost exceeds the configured hard cap")
    tx=make_signed_transaction(root=root,chain_id=chain_id,nonce=nonce,
                               priority_wei=priority,max_fee_wei=max_fee,gas=25_000,
                               public64=public64,
                               signing_fn=lambda digest,pub:sign_digest_kms(kms_client,kms_key_id,digest,pub),
                               allow_mainnet=allow_mainnet)
    if broadcast:
        txid=rpc_call(rpc_session,endpoint,"eth_sendRawTransaction",[tx["raw"]])
        if not isinstance(txid,str) or txid.lower()!=tx["hash"].lower():
            raise PublisherError("RPC returned unexpected transaction hash")
        tx["broadcast"]=True
    else:
        tx["broadcast"]=False
    # Don't leak signed raw tx into log/stdout: logs include only hash and metadata.
    tx.pop("raw")
    return tx


def main(argv=None)->int:
    import boto3,requests
    parser=argparse.ArgumentParser(description="KMS-backed Ethereum Merkle anchor, dry-run by default")
    parser.add_argument("--root",required=True)
    parser.add_argument("--chain-id",type=int,default=11155111)
    parser.add_argument("--rpc",required=True)
    parser.add_argument("--kms-key-id",required=True)
    parser.add_argument("--broadcast",action="store_true")
    parser.add_argument("--allow-mainnet",action="store_true")
    args=parser.parse_args(argv)
    try:
        result=publish_kms_root(root=args.root,chain_id=args.chain_id,
            kms_key_id=args.kms_key_id,endpoint=args.rpc,
            kms_client=boto3.client("kms"),rpc_session=requests.Session(),
            broadcast=args.broadcast,allow_mainnet=args.allow_mainnet)
        print(json.dumps(result,sort_keys=True))
        return 0
    except Exception:
        print("Ethereum anchoring failed; no secret or raw transaction is logged.")
        return 1

if __name__=="__main__":
    raise SystemExit(main())
