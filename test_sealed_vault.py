"""Isolated Sealed Vault POC tests: no AWS, no actual office data."""
import ast
from pathlib import Path

import pytest

def test_sealed_backend_cannot_decrypt_or_call_bedrock():
    tree = ast.parse(Path("sealed_vault.py").read_text("utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    assert "bedrock" not in modules
    assert "cryptography" not in modules
    assert "secrets" not in modules
    text=Path("sealed_vault.py").read_text("utf-8")
    assert "password:" not in text and "passphrase:" not in text

def test_sealed_routes_require_notary_permissions():
    import stanowiska
    for method in ("GET","POST","PUT","DELETE"):
        for path in ("/api/sealed/context","/api/sealed/documents",
                     "/api/sealed/documents/00000000-0000-4000-8000-000000000001"):
            assert stanowiska.wymagane(method,path)=="kancelaria"

def test_service_operator_is_blocked_from_sealed():
    auth=ast.parse(Path("autoryzacja.py").read_text("utf-8"))
    block=next(node for node in auth.body if isinstance(node,ast.Assign)
               and any(isinstance(t,ast.Name) and t.id=="_POZA_SERWISEM" for t in node.targets))
    prefixes=ast.literal_eval(block.value)
    assert any("/api/sealed".startswith(prefix) for prefix in prefixes)
