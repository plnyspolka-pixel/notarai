"""Testy backendów AWS na moto (bez realnego konta) + pełna ścieżka aktywacji na DynamoDB."""
import boto3
import pytest
from moto import mock_aws
import aktywacja_rejestrow as ar
import aktywacja_aws as aws
from test_aktywacja_rejestrow import W, K

@pytest.fixture
def ddb():
    with mock_aws():
        c = boto3.client("dynamodb", region_name="eu-central-1")
        c.create_table(TableName="notarai-rejestry", BillingMode="PAY_PER_REQUEST",
                       AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}],
                       KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}])
        yield c

def _a(ddb, sm=None):
    sejf = aws.SejfSecretsManager(klient=sm or boto3.client("secretsmanager", region_name="eu-central-1"))
    return ar.Aktywacje(W(), K(), sejf, magazyn=aws.DynamoMagazyn(klient=ddb)), sejf

def test_pelna_sciezka_na_dynamodb_i_sejfie(ddb):
    a, sejf = _a(ddb)
    assert a.moze_uzyc(True, "k1", "a@x", "rznp") == (False, "status_brak")
    a.przygotuj_wniosek("k1", "a@x", "rznp")
    n = a.wystaw_challenge("s1", "k1", "a@x", "rznp")
    a.zloz_z_podpisem("s1", "k1", "a@x", "rznp", n, n.encode(), True)
    a.przyznaj("k1", "a@x", "rznp", ar.Decyzja("COI", "D/1", "2026-11-25", "h", 10**11))
    with pytest.raises(ar.BladAktywacji): a.skonfigurowano("k1", "a@x", "rznp")   # brak klucza
    sejf.zapisz_klucz("k1", "a@x", "rznp", "tajny-klucz")
    a.skonfigurowano("k1", "a@x", "rznp")
    assert a.moze_uzyc(True, "k1", "a@x", "rznp") == (True, "")
    assert sejf.klucz("k1", "a@x", "rznp") == "tajny-klucz"
    assert a.moze_uzyc(True, "k2", "a@x", "rznp")[0] is False        # inna kancelaria
    a.odwolaj("k1", "a@x", "rznp")
    assert a.moze_uzyc(True, "k1", "a@x", "rznp") == (False, "status_odwolany")

def test_challenge_jednorazowy_i_skrot_w_bazie(ddb):
    a, _ = _a(ddb)
    n = a.wystaw_challenge("s1", "k1", "a@x", "rznp")
    pk = [i["pk"]["S"] for i in ddb.scan(TableName="notarai-rejestry")["Items"]]
    assert all(n not in x for x in pk)
    assert a._m.zuzyj_challenge(n) is not None and a._m.zuzyj_challenge(n) is None

def test_brak_emaili_w_bazie_i_nazwach_sekretow(ddb):
    a, sejf = _a(ddb); a.przygotuj_wniosek("k1", "ala@kancelaria.pl", "rznp")
    sejf.zapisz_klucz("k1", "ala@kancelaria.pl", "rznp", "x")
    blob = str(ddb.scan(TableName="notarai-rejestry")["Items"])
    assert "ala@" not in blob and "ala@" not in sejf.nazwa("k1", "ala@kancelaria.pl", "rznp")

def test_konflikt_wersji(ddb):
    m = aws.DynamoMagazyn(klient=ddb)
    m.zapisz("k", "e", "rznp", {"status": "x"}, 0)
    with pytest.raises(ar.Konflikt): m.zapisz("k", "e", "rznp", {"status": "y"}, 0)
    m.zapisz("k", "e", "rznp", {"status": "y"}, 1)
    assert m.czytaj("k", "e", "rznp") == ({"status": "y"}, 2)

def test_tozsamosc_wszystko_albo_nic(ddb):
    m = aws.DynamoMagazyn(klient=ddb)
    assert m.zwiaz_tozsamosc("k", "a", "T1") and m.zwiaz_tozsamosc("k", "a", "T1")
    assert not m.zwiaz_tozsamosc("k", "a", "T2") and not m.zwiaz_tozsamosc("k", "b", "T1")
    assert m.zwiaz_tozsamosc("k", "b", "T2")

def test_sejf_usuniety_to_brak_klucza(ddb):
    a, sejf = _a(ddb); sejf.zapisz_klucz("k", "e", "rznp", "x"); assert sejf.ma_klucz("k", "e", "rznp")
    sejf.usun_klucz("k", "e", "rznp"); assert not sejf.ma_klucz("k", "e", "rznp")
    with pytest.raises(ValueError): sejf.nazwa("k", "e", "../x")
