import hashlib
import json
from datetime import datetime, timedelta, timezone

import prawo_datadonkey as p

NOW = datetime(2026,11,28,12,tzinfo=timezone.utc)

def row(**changes):
    text = "Przykładowy fikcyjny przepis dotyczący sprzedaży nieruchomości."
    result = {"jurisdiction":"PL","act_id":"fixture","title":"Ustawa testowa",
              "provision":"art. 1","text":text,"source_url":"https://example.org/fixture",
              "raw_sha256":"a"*64,"text_sha256":hashlib.sha256(text.encode()).hexdigest(),
              "git_commit":"b"*40,"verified_on":"2026-11-28",
              "valid_from":"2026-01-01","valid_to":None,
              "review_status":"approved","keywords":["sprzedaż","nieruchomość"]}
    result.update(changes)
    return result

def bundle(tmp_path,monkeypatch,rows,generated=NOW):
    path=tmp_path/"law.json"
    data=json.dumps({"schema":p.SCHEMA,"generated_at":generated.isoformat(),"provisions":rows},ensure_ascii=False).encode()
    path.write_bytes(data)
    monkeypatch.setenv("PIECZAPP_PRAWO_SNAPSHOT",str(path))
    monkeypatch.setenv("PIECZAPP_PRAWO_SHA256",hashlib.sha256(data).hexdigest())
    p._load.cache_clear()
    return path

def test_retrieval(tmp_path,monkeypatch):
    bundle(tmp_path,monkeypatch,[row()])
    result=p.szukaj("sprzedaż nieruchomości",teraz=NOW)
    assert result["status"]=="ok"
    assert result["results"][0]["git_commit"]=="b"*40
    assert p.szukaj("sprzedaż",jurysdykcja="DE",teraz=NOW)["status"]=="no_match"

def test_historical_exclusive_end(tmp_path,monkeypatch):
    bundle(tmp_path,monkeypatch,[row(valid_to="2026-05-01")])
    assert p.szukaj("sprzedaż",na_dzien="2026-04-30",teraz=NOW)["status"]=="ok"
    assert p.szukaj("sprzedaż",na_dzien="2026-05-01",teraz=NOW)["status"]=="no_match"

def test_tampered(tmp_path,monkeypatch):
    path=bundle(tmp_path,monkeypatch,[row()])
    path.write_bytes(path.read_bytes()+b" ")
    assert p.szukaj("sprzedaż",teraz=NOW)["status"]=="unavailable"

def test_stale(tmp_path,monkeypatch):
    bundle(tmp_path,monkeypatch,[row()],NOW-timedelta(days=3))
    assert p.szukaj("sprzedaż",teraz=NOW)["status"]=="stale"

def test_conflicting_versions(tmp_path,monkeypatch):
    bundle(tmp_path,monkeypatch,[row(),row(valid_from="2026-06-01")])
    assert p.szukaj("sprzedaż",teraz=NOW)["status"]=="ambiguous_version"

def test_future(tmp_path,monkeypatch):
    bundle(tmp_path,monkeypatch,[row()])
    assert p.szukaj("sprzedaż",na_dzien="2026-12-01",teraz=NOW)["status"]=="unverified_future"

def test_disabled(monkeypatch):
    monkeypatch.delenv("PIECZAPP_PRAWO_SNAPSHOT",raising=False)
    assert p.kontekst("sprawa")==""

def test_draft_and_case_chat(monkeypatch):
    import bedrock
    monkeypatch.setattr(p,"kontekst",lambda _: "TEST PUBLICZNYCH PRZEPISÓW")
    calls=[]
    def fake(system,content,**kwargs):
        calls.append((system,content))
        return "AKT"
    monkeypatch.setattr(bedrock,"_rozmowa",fake)
    bedrock.sporzadz_projekt("WZOR",[],"sprzedaż")
    bedrock.rozmawiaj("kontekst",[],"sprzedaż")
    assert len(calls)==2
    for system,content in calls:
        assert p.INSTRUKCJA in system
        assert any(x.get("text")=="TEST PUBLICZNYCH PRZEPISÓW" for x in content)
