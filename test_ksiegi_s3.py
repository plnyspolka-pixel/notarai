"""Ksiegi w trybie SaaS: S3 z zapisem warunkowym, dwie kopie aplikacji, dwie kancelarie.

Numer w repertorium musi byc unikalny takze wtedy, gdy dwie kopie aplikacji
dopisuja czynnosc w tej samej chwili (magazyn ponawia zmiane na nowszej wersji).
"""
import pytest

from test_osoby import s3  # noqa: F401 - fixture S3 z zapisem warunkowym


def _wpis(dzien="2026-11-03", tresc="Umowa"):
    return {"data_czynnosci": dzien, "tresc": tresc, "strony": "Jan Sobczak"}


def test_rownoczesne_wpisy_dostaja_rozne_numery(s3):  # noqa: F811
    magazyn, atrapa = s3
    import ksiegi_notarialne as k
    k.dodaj("repertorium_a", _wpis(tresc="pierwsza"))
    # W chwili zapisu drugiej czynnosci "inna kopia aplikacji" dopisuje trzecia.
    atrapa.przed_zapisem = lambda: k.dodaj("repertorium_a", _wpis(tresc="rownolegla"))
    drugi = k.dodaj("repertorium_a", _wpis(tresc="druga"))
    wpisy = k.lista("repertorium_a", 2026)
    assert [w["numer"] for w in wpisy] == [1, 2, 3]
    assert drugi["numer"] == 3 and {w["tresc"] for w in wpisy} == {"pierwsza", "rownolegla", "druga"}


def test_kancelarie_nie_widza_swoich_ksiag(s3):  # noqa: F811
    magazyn, _ = s3
    import ksiegi_notarialne as k
    k.dodaj("repertorium_a", _wpis())
    znacznik = magazyn.kancelaria_var.set("kancelaria-b")
    try:
        assert k.lista("repertorium_a") == []
        assert k.dodaj("repertorium_a", _wpis())["oznaczenie"] == "Rep. A nr 1/2026"
    finally:
        magazyn.kancelaria_var.reset(znacznik)
    assert len(k.lista("repertorium_a")) == 1


def test_pliki_u_klienta_nie_zapisuja_ksiag(s3):  # noqa: F811
    magazyn, _ = s3
    import ksiegi_notarialne as k
    znacznik = magazyn.przechowywanie_var.set("u-klienta")
    try:
        with pytest.raises(RuntimeError):
            k.dodaj("repertorium_a", _wpis())
    finally:
        magazyn.przechowywanie_var.reset(znacznik)
