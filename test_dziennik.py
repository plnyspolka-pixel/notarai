"""Opis bledu w logach: miejsce i kod AWS, bez danych osobowych."""
import logging

from botocore.exceptions import ClientError

import dziennik

# Fikcyjne dane - takie moglyby siedziec w tresci wyjatku.
PESEL = "85031512337"
PLIK_SKANU = "Sobczak Jan - Pawlak Anna - Zalesie.pdf"


def _wyjatek(blad: Exception) -> Exception:
    try:
        raise blad
    except Exception as zlapany:  # noqa: BLE001
        return zlapany


def test_opis_pomija_tresc_zwyklego_wyjatku():
    opis = dziennik.opis_bledu(_wyjatek(ValueError(f"strona 3 pliku {PLIK_SKANU}, PESEL {PESEL}")))
    assert opis.startswith("ValueError")
    assert "test_dziennik.py:" in opis and "_wyjatek" in opis
    assert PESEL not in opis and "Sobczak" not in opis


def test_opis_podaje_kod_i_komunikat_aws():
    blad = ClientError({"Error": {"Code": "ValidationException",
                                  "Message": "messages.0.content: too many images"}},
                       "ConverseStream")
    opis = dziennik.opis_bledu(_wyjatek(blad))
    assert "ValidationException: messages.0.content: too many images" in opis


def test_opis_wskazuje_typ_przyczyny_bez_jej_tresci():
    try:
        try:
            raise KeyError(PESEL)
        except KeyError as przyczyna:
            raise RuntimeError("cos") from przyczyna
    except RuntimeError as blad:
        opis = dziennik.opis_bledu(blad)
    assert "przyczyna: KeyError" in opis and PESEL not in opis


def test_nieobsluzony_blad_trafia_do_dziennika_bez_tresci(caplog):
    import asyncio

    from starlette.requests import Request

    import app as aplikacja

    zadanie = Request({"type": "http", "method": "POST", "path": "/api/sprawy",
                       "headers": [], "query_string": b""})
    blad = _wyjatek(RuntimeError(f"PESEL {PESEL}"))
    with caplog.at_level(logging.ERROR, logger="pieczapp"):
        odp = asyncio.run(aplikacja._nieobsluzony(zadanie, blad))
    assert odp.status_code == 500
    assert PESEL not in odp.body.decode()
    wpisy = [r.getMessage() for r in caplog.records if "nieobsluzony" in r.getMessage()]
    assert wpisy and wpisy[0].startswith("POST /api/sprawy: nieobsluzony blad (RuntimeError")
    assert PESEL not in wpisy[0]


# --- maskowanie kazdego wpisu logu

def test_maskuj_pesel_email_i_nazwy_plikow():
    tekst = dziennik.maskuj(
        f"PESEL {PESEL}, jan.sobczak@example.pl, skan C:\\skany\\Pawlak.PDF, wzor=wzor.docx")
    assert tekst == "PESEL [PESEL], [e-mail], skan C:\\skany\\[plik], wzor=wzor.docx"


def test_argument_z_nazwa_pliku_znika_w_calosci():
    # Nazwa skanu ze spacjami - z samego tekstu nie da sie jej wyciac.
    assert dziennik._maskuj_argument(PLIK_SKANU) == "[plik]"
    assert dziennik._maskuj_argument("wzor.docx") == "wzor.docx"
    assert dziennik._maskuj_argument(33) == 33


def test_aplikacja_maskuje_kazdy_logger(caplog):
    import app  # noqa: F401 - import wlacza maskowanie

    with caplog.at_level(logging.WARNING):
        # Tak wygladal wpis, ktory 23.10.2026 trafil do CloudWatch.
        logging.getLogger("pieczapp.bedrock").warning(
            "paczka %s/%d (%d str.): limit zapytan, czekam (%d)", PLIK_SKANU, 33, 4, 1)
        logging.getLogger("uvicorn.error").warning("klient %s, PESEL %s", "jan@example.pl", PESEL)
    tekst = "\n".join(r.getMessage() for r in caplog.records)
    assert "paczka [plik]/33 (4 str.): limit zapytan, czekam (1)" in tekst
    assert "klient [e-mail], PESEL [PESEL]" in tekst
    assert "Sobczak" not in tekst and PESEL not in tekst


def test_traceback_zamienia_sie_w_opis_bez_tresci(caplog):
    import app  # noqa: F401

    blad = _wyjatek(ValueError(f"nie przepisano strony pliku {PLIK_SKANU}"))
    with caplog.at_level(logging.ERROR):
        logging.getLogger("uvicorn.error").error("Exception in ASGI application", exc_info=blad)
    rekord = caplog.records[-1]
    assert rekord.exc_info is None
    assert rekord.getMessage().startswith("Exception in ASGI application (ValueError | test_dziennik.py:")
    assert "Sobczak" not in caplog.text


def test_maskowanie_wlaczone_raz():
    dziennik.wlacz_maskowanie()
    fabryka = logging.getLogRecordFactory()
    dziennik.wlacz_maskowanie()
    assert logging.getLogRecordFactory() is fabryka
