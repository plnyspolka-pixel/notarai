"""Szyfrowanie spraw kluczem KMS notarai: szablon infrastruktury i przeszyfrowanie
plikow juz lezacych w buckecie. Bez AWS - atrapa S3."""
from pathlib import Path

import yaml

import magazyn
import szyfrowanie

INFRA = Path(__file__).parent / "infra"


class _Loader(yaml.SafeLoader):
    pass


_Loader.add_multi_constructor("!", lambda l, tag, n: {tag: l.construct_sequence(n) if isinstance(n, yaml.SequenceNode)
                                                      else l.construct_mapping(n) if isinstance(n, yaml.MappingNode)
                                                      else l.construct_scalar(n)})


def _szablon(nazwa):
    return yaml.load((INFRA / nazwa).read_text("utf-8"), Loader=_Loader)


class TestSzablon:
    def test_bucket_szyfrowany_kluczem_kms_z_rotacja(self):
        t = _szablon("notarai-s3.yaml")["Resources"]
        klucz = t["KluczSpraw"]
        assert klucz["Properties"]["EnableKeyRotation"] is True
        assert klucz["DeletionPolicy"] == "Retain", "utrata klucza = utrata spraw"
        zasada = t["BucketSprawy"]["Properties"]["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]
        assert zasada["ServerSideEncryptionByDefault"]["SSEAlgorithm"] == "aws:kms"
        assert zasada["BucketKeyEnabled"] is True

    def test_odszyfrowac_moze_tylko_aplikacja_i_kopia(self):
        zasady = _szablon("notarai-s3.yaml")["Resources"]["KluczSpraw"]["Properties"]["KeyPolicy"]["Statement"]
        zakaz = next(z for z in zasady if z["Sid"] == "OdszyfrowanieTylkoAplikacjaIKopia")
        assert zakaz["Effect"] == "Deny" and "kms:Decrypt" in zakaz["Action"]
        role = zakaz["Condition"]["ArnNotLike"]["aws:PrincipalArn"]
        assert len(role) == 2 and all("RolaAplikacji" in str(r) or "RolaKopii" in str(r) for r in role)

    def test_polityka_bucketa_odrzuca_klucz_s3(self):
        zasady = _szablon("notarai-s3.yaml")["Resources"]["PolitykaBucketa"]["Properties"]["PolicyDocument"]["Statement"]
        zakaz = next(z for z in zasady if z["Sid"] == "TylkoKluczNotarai")
        assert zakaz["Condition"]["StringEquals"]["s3:x-amz-server-side-encryption"] == "AES256"

    def test_aplikacja_szyfruje_kluczem_notarai(self):
        tresc = (INFRA / "notarai-aplikacja.yaml").read_text("utf-8")
        assert "PIECZAPP_KMS_KEY_ID" in tresc and "alias/notarai-sprawy" in tresc


class _Blad(Exception):
    def __init__(self, kod):
        self.response = {"Error": {"Code": kod}}


class _AtrapaS3:
    def __init__(self, obiekty):
        self.obiekty = obiekty          # klucz -> {"sse", "etag", "wersja"}
        self.usuniete = []
        self.zmien_przed_kopia = None

    def get_paginator(self, _):
        atrapa = self

        class P:
            def paginate(self, Bucket, Prefix):
                yield {"Contents": [{"Key": k, "Size": 10} for k in atrapa.obiekty if k.startswith(Prefix)]}
        return P()

    def head_object(self, Bucket, Key):
        o = self.obiekty[Key]
        return {"ServerSideEncryption": o["sse"], "ETag": o["etag"], "VersionId": o["wersja"]}

    def copy_object(self, Bucket, Key, CopySource, CopySourceIfMatch, MetadataDirective, **szyfr):
        if self.zmien_przed_kopia == Key:
            self.obiekty[Key].update(etag="nowy")
        o = self.obiekty[Key]
        if o["etag"] != CopySourceIfMatch:
            raise _Blad("PreconditionFailed")
        assert szyfr["ServerSideEncryption"] == "aws:kms"
        self.obiekty[Key] = {"sse": "aws:kms", "etag": "kms-" + o["etag"], "wersja": o["wersja"] + "+"}

    def delete_object(self, Bucket, Key, VersionId):
        self.usuniete.append((Key, VersionId))


def test_przeszyfrowanie_tylko_starych_plikow_i_bez_ich_starych_wersji(monkeypatch):
    atrapa = _AtrapaS3({"kancelarie/a/sprawy/x/sprawa.json": {"sse": "AES256", "etag": "e1", "wersja": "v1"},
                        "kancelarie/a/sprawy/x/skan.png": {"sse": "aws:kms", "etag": "e2", "wersja": "v2"}})
    monkeypatch.setattr(magazyn, "_s3", atrapa)
    monkeypatch.setattr(magazyn, "KMS_KLUCZ", "alias/notarai-sprawy")
    licz = szyfrowanie.przeszyfruj("kancelarie/")
    assert licz["przeszyfrowano"] == 1 and licz["juz_kms"] == 1 and licz["bledy"] == 0
    assert {o["sse"] for o in atrapa.obiekty.values()} == {"aws:kms"}
    assert atrapa.usuniete == [("kancelarie/a/sprawy/x/sprawa.json", "v1")]
    # drugi przebieg niczego nie rusza
    assert szyfrowanie.przeszyfruj("kancelarie/")["przeszyfrowano"] == 0


def test_swiezy_zapis_aplikacji_nie_jest_nadpisany(monkeypatch):
    atrapa = _AtrapaS3({"kancelarie/a/sprawy/x/sprawa.json": {"sse": "AES256", "etag": "e1", "wersja": "v1"}})
    atrapa.zmien_przed_kopia = "kancelarie/a/sprawy/x/sprawa.json"
    monkeypatch.setattr(magazyn, "_s3", atrapa)
    licz = szyfrowanie.przeszyfruj("kancelarie/")
    assert licz["przeszyfrowano"] == 0 and atrapa.usuniete == []
