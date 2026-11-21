"""Raport dostepu: ktore operacje z sladu CloudTrail otwieraja droge do tresci spraw."""
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "raport_dostepu", Path(__file__).parent / "infra" / "raport_dostepu.py")
raport = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(raport)

ROLA = "arn:aws:iam::111122223333:role/notarai-ecs-zadanie"


def z(zrodlo, nazwa, parametry=None, kto=None, **reszta):
    return {"eventSource": f"{zrodlo}.amazonaws.com", "eventName": nazwa, "eventTime": "2026-11-20T10:00:00Z",
            "requestParameters": parametry or {}, "userIdentity": kto or {"type": "IAMUser", "arn": "arn:aws:iam::1:user/x"},
            **reszta}


@pytest.mark.parametrize("zdarzenie, rodzaj", [
    (z("s3", "PutBucketPolicy", {"bucketName": "notarai-sprawy"}), "zabezpieczenia_bucketa"),
    (z("s3", "DeleteBucketPolicy", {"bucketName": "notarai-sprawy"}), "zabezpieczenia_bucketa"),
    (z("s3", "PutBucketPolicy", {"bucketName": "inny-bucket"}), None),
    (z("ecs", "ExecuteCommand", {"cluster": "notarai"}), "wejscie_do_kontenera"),
    (z("iam", "PutRolePolicy", {"roleName": "notarai-ecs-zadanie"}), "zmiana_roli"),
    (z("iam", "UpdateAssumeRolePolicy", {"roleName": "notarai-kopia"}), "zmiana_roli"),
    (z("iam", "PutRolePolicy", {"roleName": "inna-rola"}), None),
    (z("sts", "AssumeRole", {"roleArn": ROLA}), "przyjecie_roli"),
    (z("sts", "AssumeRole", {"roleArn": ROLA},
       {"type": "AWSService", "invokedBy": "ecs-tasks.amazonaws.com"}), None),
    (z("sts", "AssumeRole", {"roleArn": ROLA},
       {"type": "AWSService", "invokedBy": "lambda.amazonaws.com"}), "przyjecie_roli"),
    (z("sts", "AssumeRole", {"roleArn": "arn:aws:iam::1:role/notarai-kopia"},
       {"type": "AWSService", "invokedBy": "backup.amazonaws.com"}), None),
    (z("cloudtrail", "StopLogging"), "zmiana_sladu"),
    (z("backup", "StartRestoreJob"), "odtworzenie_kopii"),
    (z("ecs", "UpdateService"), "wdrozenie"),
    (z("ecs", "RunTask"), "wdrozenie"),
    (z("bedrock", "PutModelInvocationLoggingConfiguration"), "zapis_zapytan_modelu"),
    (z("logs", "DeleteLogStream", {"logGroupName": "/ecs/notarai"}), "zmiana_logow_aplikacji"),
    (z("logs", "DeleteLogStream", {"logGroupName": "/aws/codebuild/notarai-obraz"}), None),
    (z("s3", "PutBucketPolicy", {"bucketName": "notarai-sprawy"}, errorCode="AccessDenied"), None),
    (z("ec2", "DescribeInstances"), None),
])
def test_klasyfikacja_zdarzen(zdarzenie, rodzaj):
    assert raport.klasyfikuj(zdarzenie) == rodzaj


def test_zbior_oddziela_wdrozenia_i_nie_niesie_adresow_ip():
    zdarzenia = [
        z("ecs", "RegisterTaskDefinition", {"containerDefinitions": [{"image": "repo:abc1234"}]},
          sourceIPAddress="203.0.113.7"),
        z("ecs", "ExecuteCommand", sourceIPAddress="203.0.113.7"),
        z("ec2", "DescribeInstances"),
    ]
    otwarcia, wdrozenia, razem = raport.zbierz(zdarzenia)
    assert razem == 3
    assert [w["rodzaj"] for w in otwarcia] == ["wejscie_do_kontenera"]
    assert wdrozenia[0]["obraz"] == ["repo:abc1234"]
    assert "203.0.113.7" not in str(otwarcia) + str(wdrozenia)


def test_lista_operacji_zgodna_z_regulami_nadzoru():
    szablon = (Path(__file__).parent / "infra" / "notarai-nadzor.yaml").read_text("utf-8")
    for nazwa in ("PutBucketPolicy", "DeleteBucketPolicy", "PutBucketAcl", "ExecuteCommand",
                  "StopLogging", "DeleteTrail", "UpdateTrail", "PutEventSelectors"):
        assert f"- {nazwa}" in szablon, nazwa
        assert raport.klasyfikuj is not None
    assert {"PutBucketPolicy", "DeleteBucketPolicy", "PutBucketAcl"} <= raport.ZABEZPIECZENIA_BUCKETA


# --- dostep serwisowy: swiadkowie z logow aplikacji -----------------------------


def _swiadkowie(tmp_path, monkeypatch, caplog, ile=4):
    """Prawdziwe wpisy dziennika serwisu i ich wiersze w logu aplikacji."""
    import config
    import dziennik_serwisu
    monkeypatch.setattr(config, "DANE", tmp_path)
    dziennik_serwisu._zeruj()
    rodzaje = ["wlaczono", "wejscie", "zakres", "odwolano"]
    with caplog.at_level("INFO", logger="pieczapp.serwis"):
        wpisy = [dziennik_serwisu.dopisz(rodzaje[i % 4], "kancelaria-a", kto="serwis@fundacja.test")
                 for i in range(ile)]
    dziennik_serwisu._zeruj()
    wiersze = ["2026-11-20 10:00:00 INFO pieczapp.serwis " + r.getMessage() for r in caplog.records]
    return wpisy, wiersze


def test_swiadek_z_logu_zgadza_sie_z_wpisem_dziennika(tmp_path, monkeypatch, caplog):
    wpisy, wiersze = _swiadkowie(tmp_path, monkeypatch, caplog)
    odczytane = [raport.swiadek(w) for w in wiersze]
    assert [o["skrot"] for o in odczytane] == [w["skrot"] for w in wpisy]
    assert [o["rodzaj"] for o in odczytane] == ["wlaczono", "wejscie", "zakres", "odwolano"]
    assert raport.swiadek("zwykly wiersz logu") is None
    assert raport.sprawdz_swiadkow(odczytane)["lancuch_ciagly"] is True


def test_swiadek_przechodzi_przez_maskowanie_logow(tmp_path, monkeypatch, caplog):
    """Skrot z 11 cyframi pod rzad nie moze zostac zamaskowany jako PESEL."""
    import dziennik
    import dziennik_serwisu
    skrot = "ab12345678901cd" + "0" * 49
    zapis = dziennik_serwisu.bez_cyfr(skrot)
    wiersz = dziennik.maskuj(f"serwis-dziennik nr=7 rodzaj=wejscie kancelaria=k skrot={zapis} poprzedni={zapis}")
    assert raport.swiadek(wiersz)["skrot"] == skrot


def test_usuniety_albo_podmieniony_wpis_zrywa_lancuch(tmp_path, monkeypatch, caplog):
    _, wiersze = _swiadkowie(tmp_path, monkeypatch, caplog)
    odczytane = [raport.swiadek(w) for w in wiersze]
    bez_wejscia = [odczytane[0], odczytane[2], odczytane[3]]
    assert raport.sprawdz_swiadkow(bez_wejscia)["lancuch_ciagly"] is False
    podmieniony = [dict(o) for o in odczytane]
    podmieniony[1]["skrot"] = "f" * 64
    assert raport.sprawdz_swiadkow(podmieniony)["lancuch_ciagly"] is False
    # okres zaczynajacy sie w srodku dziennika jest w porzadku
    assert raport.sprawdz_swiadkow(odczytane[2:])["lancuch_ciagly"] is True
    assert raport.sprawdz_swiadkow([])["lancuch_ciagly"] is True
