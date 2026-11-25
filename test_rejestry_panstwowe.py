import httpx
import pytest
import rejestry_panstwowe as rp

def klient(fn):
    return httpx.Client(transport=httpx.MockTransport(fn))

def test_uldk():
    def handler(r):
        assert r.url.host=="uldk.gugik.gov.pl"
        assert r.url.params["request"]=="GetParcelById"
        return httpx.Response(200,text="0\n141201_1.0001.6509|6509|powiat|gmina|obręb|województwo|WFS")
    with klient(handler) as c:
        assert rp.dzialka("141201_1.0001.6509",c)["dane"]["datasource"]=="WFS"

@pytest.mark.parametrize("body",["-1\nBłąd","0\ninna|1|2|3|4|5|6","0\nza mało"])
def test_uldk_blad(body):
    with klient(lambda r:httpx.Response(200,text=body)) as c:
        with pytest.raises(rp.Niedostepny):
            rp.dzialka("141201_1.0001.6509",c)

def test_krs():
    def handler(r):
        assert r.url.path=="/api/krs/OdpisAktualny/0000000001"
        return httpx.Response(200,json={"odpis":{"naglowek":{}}})
    with klient(handler) as c:
        assert "odpis" in rp.krs("0000000001",c)["dane"]

def test_vat():
    with klient(lambda r:httpx.Response(200,json={"result":{"subject":None,"requestId":"test"}})) as c:
        assert rp.vat("1234567890","2020-01-01",c)["dane"]["subject"] is None

def test_walidacja_i_przekierowania():
    with klient(lambda r:httpx.Response(302,headers={"Location":"https://example.com"})) as c:
        with pytest.raises(rp.Niedostepny):
            rp.krs("0000000001",c)
        with pytest.raises(ValueError):
            rp.dzialka("https://example.com/",c)
        with pytest.raises(ValueError):
            rp.vat("1234567890","9999-01-01",c)

def test_katalog():
    d={r["id"]:r for r in rp.katalog()}
    assert d["rsc"]["sciezka"]=="wymaga_potwierdzenia"
    assert d["rznp"]["sciezka"]=="wymaga_dostepu"
    assert len(d)==len(rp.KATALOG)

def test_router_odrzuca_serwis_i_brak_potwierdzenia(monkeypatch):
    from types import SimpleNamespace as NS
    from fastapi import HTTPException
    import rejestry_panstwowe_router as route
    monkeypatch.setattr(route.autoryzacja,"MULTI",True)
    monkeypatch.setattr(route.autoryzacja,"_osoba_w_kancelarii",lambda k,e:{"stanowisko":"notariusz"})
    with pytest.raises(HTTPException) as ex:
        route.katalog(NS(state=NS(serwis=True,kancelaria="a",email="a@example.org")))
    assert ex.value.status_code==403
    with pytest.raises(HTTPException) as ex:
        route.publiczne("krs",route.Zapytanie(identyfikator="0000000001"),NS(state=NS(kancelaria="a",email="a@example.org")))
    assert ex.value.status_code==400
