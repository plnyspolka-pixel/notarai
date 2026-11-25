from types import SimpleNamespace as NS
import base64
import pytest
from fastapi import HTTPException
import aktywacja_router as r
import aktywacja_rejestrow as ar
from test_aktywacja_rejestrow import W, K, S

def req(k="k1", e="a@x", serwis=False, komputer=None, auth="Bearer t1"):
    return NS(state=NS(kancelaria=k, email=e, serwis=serwis, komputer=komputer), headers={"authorization": auth})

@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(r.autoryzacja, "MULTI", True)
    monkeypatch.setattr(r.autoryzacja, "_osoba_w_kancelarii", lambda k, e: {"stanowisko": "notariusz"})
    s = S(); s.klucze = set()
    w = W()
    m = ar.Pamiec()
    monkeypatch.setattr(r, "_ak", ar.Aktywacje(w, ar.KrnReczne(m), s, magazyn=m))
    monkeypatch.setattr(r, "_sejf", NS(zapisz_klucz=lambda k, e, u, v: s.klucze.add((k, e, u))))
    monkeypatch.setattr(r.autoryzacja, "_wymagaj_admina", lambda request: None)
    return NS(w=w, s=s, m=m)

def test_pelny_przeplyw_http(setup):
    q = req()
    assert r.status("rznp", q)["status"] == ar.BRAK
    r.wniosek("rznp", q)
    n = r.challenge("rznp", q)["challenge"]
    setup.m.krn_potwierdz(ar._h("osoba-A"))
    r.zloz("rznp", r.Zlozenie(challenge=n, podpis_base64=base64.b64encode(n.encode()).decode(), zgoda_na_zakres=True), q)
    with pytest.raises(HTTPException) as e: r.wgraj_klucz("rznp", r.Klucz(wartosc="12345678"), q)
    assert e.value.status_code == 400                                       # jeszcze nie przyznano
    r.przyznaj(r.Przyznanie(kancelaria="k1", email="a@x", usluga="rznp", instytucja="COI", numer_decyzji="1",
                            data_decyzji="2026-11-25", hash_dokumentu="a" * 64, wazna_do_epoch=1e11), q)
    assert r.wgraj_klucz("rznp", r.Klucz(wartosc="12345678"), q)["status"] == ar.SKONFIGUROWANY
    assert r._ak.moze_uzyc(True, "k1", "a@x", "rznp") == (True, "")

@pytest.mark.parametrize("q", [req(serwis=True), req(komputer="pc1"), req(k=None), req(e=None)])
def test_tylko_indywidualna_sesja(q):
    with pytest.raises(HTTPException) as e: r.status("rznp", q)
    assert e.value.status_code in (401, 403)

def test_nieznana_usluga_i_brak_weryfikatora(setup, monkeypatch):
    with pytest.raises(HTTPException) as e: r.status("krs", req())
    assert e.value.status_code == 404
    monkeypatch.setattr(r, "_ak", ar.Aktywacje(r._WeryfikatorProxy(), ar.KrnReczne(setup.m), setup.s, magazyn=setup.m))
    r.wniosek("rznp", req()); n = r.challenge("rznp", req())["challenge"]
    with pytest.raises(HTTPException) as e:
        r.zloz("rznp", r.Zlozenie(challenge=n, podpis_base64="QUJDREVGR0g=", zgoda_na_zakres=True), req())
    assert e.value.status_code == 503

def test_przyznanie_i_krn_tylko_dla_admina(monkeypatch):
    def nie(request): raise HTTPException(401, "Brak uprawnien administratora")
    monkeypatch.setattr(r.autoryzacja, "_wymagaj_admina", nie)
    p = r.Przyznanie(kancelaria="k1", email="a@x", usluga="rznp", instytucja="COI", numer_decyzji="1",
                     data_decyzji="2026-11-25", hash_dokumentu="a" * 64, wazna_do_epoch=1e11)
    with pytest.raises(HTTPException) as e: r.przyznaj(p, req())
    assert e.value.status_code == 401
    with pytest.raises(HTTPException) as e: r.krn(r.Krn(identyfikator_podpisujacego="osoba-A"), req())
    assert e.value.status_code == 401
    assert not any(rt.path.endswith("/przyznaj") for rt in r.router.routes if "admin" not in rt.path)
