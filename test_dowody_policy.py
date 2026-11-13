"""Proof endpoint access policy tests. No AWS/Bedrock imports required."""
import ast
from pathlib import Path
import stanowiska

def test_proof_api_requires_notary_privilege_for_every_method():
    for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        for path in ("/api/dowody/sprawy/abc", "/api/dowody/sprawy/abc/dokument",
                     "/api/dowody/partie", "/api/dowody/partie/abc/potwierdz",
                     "/api/dowody/weryfikuj"):
            assert stanowiska.wymagane(method, path) == "kancelaria", (method, path)

def test_support_service_cannot_access_proof_endpoints():
    parsed = ast.parse(Path("autoryzacja.py").read_text(encoding="utf-8"))
    assign = next(node for node in parsed.body if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "_POZA_SERWISEM" for t in node.targets))
    blocked = ast.literal_eval(assign.value)
    assert any("/api/dowody".startswith(prefix) for prefix in blocked)

def test_secretariat_may_not_access_evidence_ledger():
    assert "kancelaria" not in stanowiska.uprawnienia({"rola":"czlonek","stanowisko":"sekretariat"})
    assert "kancelaria" not in stanowiska.uprawnienia({"rola":"czlonek","stanowisko":"aplikant"})
