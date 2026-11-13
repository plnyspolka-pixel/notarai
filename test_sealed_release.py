import json
from pathlib import Path
from sealed_release import keygen,manifest,sign,verify,stable_json

PASSWORD="Fictional offline release key password 2026"

def test_offline_release_signing_and_artifact_hash(tmp_path):
    binary=tmp_path/"notarai-sealed-v2.exe"
    binary.write_bytes(b"fictional artifact, not a real executable")
    doc=manifest([binary])
    secret,pub=keygen(PASSWORD)
    sig=sign(doc,secret,PASSWORD)
    assert verify(doc,sig,pub,tmp_path)
    binary.write_bytes(b"tampered artifact")
    assert not verify(doc,sig,pub,tmp_path)

def test_rejects_forged_signature_and_tampered_manifest(tmp_path):
    artifact=tmp_path/"notarai-sealed-v2.exe"
    artifact.write_bytes(b"fictional")
    m=manifest([artifact])
    secret,pub=keygen(PASSWORD)
    sig=sign(m,secret,PASSWORD)
    secret2,foreignpub=keygen(PASSWORD)
    assert not verify(m,sig,foreignpub,tmp_path)
    altered=json.loads(stable_json(m))
    altered["files"][0]["size"]+=1
    assert not verify(altered,sig,pub,tmp_path)
    assert not verify(m,b"invalid",pub,tmp_path)

def test_rejects_extra_path_or_symlink(tmp_path):
    artifact=tmp_path/"notarai-sealed-v2.exe"
    artifact.write_bytes(b"fictional")
    m=manifest([artifact])
    secret,pub=keygen(PASSWORD)
    sig=sign(m,secret,PASSWORD)
    artifact.unlink()
    outside=tmp_path.parent/"external-test-release.bin"
    outside.write_bytes(b"fictional")
    artifact.symlink_to(outside)
    assert not verify(m,sig,pub,tmp_path)
    outside.unlink()
