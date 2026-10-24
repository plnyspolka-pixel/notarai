"""Logi (CloudWatch) bez danych osobowych.

Dwie warstwy:
- opis_bledu() - typ wyjatku, kod i komunikat AWS (opisuja zadanie, nie jego
  tresc) oraz miejsca w kodzie. Sama nazwa wyjatku nie wystarcza, zeby po
  fakcie ustalic, co sie stalo, a pelna tresc moze zawierac dane klienta.
- wlacz_maskowanie() - kazdy wpis logu, z naszego kodu i z bibliotek, przed
  zapisem traci nazwy plikow (nazwa skanu to czesto nazwiska stron), numery
  PESEL i adresy e-mail, a traceback zamienia sie w opis_bledu(). To siatka
  bezpieczenstwa: 23.10.2026 nazwy skanow trafily do CloudWatch z ostrzezen
  o ponawianiu odczytu i trzeba bylo kasowac strumienie logow.
"""
import logging
import re
import traceback
from pathlib import Path

from botocore.exceptions import ClientError

import config

# Ile ostatnich ramek stosu pokazac - wystarczy, zeby trafic w miejsce bledu.
RAMEK = 6


def opis_bledu(blad: BaseException) -> str:
    """Typ, kod AWS i miejsce bledu, bez tresci wyjatku spoza AWS."""
    opis = type(blad).__name__
    if isinstance(blad, ClientError):
        b = blad.response.get("Error", {})
        opis += f" {b.get('Code', '?')}: {b.get('Message', '')}"
    ramki = traceback.extract_tb(blad.__traceback__)
    # Ramki z naszego kodu mowia wiecej niz te z FastAPI i anyio.
    nasze = [r for r in ramki if Path(r.filename).resolve().is_relative_to(config.KORZEN.resolve())
             and ".venv" not in Path(r.filename).parts]
    ramki = (nasze or ramki)[-RAMEK:]
    if ramki:
        opis += " | " + " < ".join(
            f"{Path(r.filename).name}:{r.lineno} {r.name}" for r in reversed(ramki))
    przyczyna = blad.__cause__ or blad.__context__
    if przyczyna is not None and przyczyna is not blad:
        opis += f" | przyczyna: {type(przyczyna).__name__}"
    return opis


_ROZSZERZENIA = r"pdf|png|jpe?g|tiff?|heic|bmp|gif|webp|docx?|odt|rtf|txt|mp3|m4a|wav|ogg|webm"
_PLIK = re.compile(rf"\.(?:{_ROZSZERZENIA})\b", re.IGNORECASE)
_PLIK_W_TEKSCIE = re.compile(rf"[^\s/\\:()\[\]'\"=]+\.(?:{_ROZSZERZENIA})\b", re.IGNORECASE)
# Wzor sprawy zawsze zapisujemy jako "wzor.<rozszerzenie>" - to nie dane klienta.
_WZOR = re.compile(r"wzor\.\w+")
_PESEL = re.compile(r"(?<!\d)\d{11}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def maskuj(tekst: str) -> str:
    """Zakrywa PESEL, e-mail i nazwy plikow (poza wzor.*) w tekscie."""
    tekst = _PESEL.sub("[PESEL]", tekst)
    tekst = _EMAIL.sub("[e-mail]", tekst)
    return _PLIK_W_TEKSCIE.sub(lambda m: m.group(0) if _WZOR.fullmatch(m.group(0)) else "[plik]", tekst)


def _maskuj_argument(arg):
    if isinstance(arg, (int, float)) or arg is None:
        return arg
    tekst = str(arg)
    # Caly argument, bo nazwa pliku ze spacjami nie da sie wyciac z tekstu.
    if _PLIK.search(tekst) and not _WZOR.fullmatch(tekst):
        return "[plik]"
    return maskuj(tekst)


def _maskuj_rekord(rekord: logging.LogRecord) -> logging.LogRecord:
    if isinstance(rekord.args, tuple):
        rekord.args = tuple(_maskuj_argument(a) for a in rekord.args)
    elif isinstance(rekord.args, dict):
        rekord.args = {k: _maskuj_argument(v) for k, v in rekord.args.items()}
    if isinstance(rekord.msg, str):
        rekord.msg = maskuj(rekord.msg)
    if rekord.exc_info and rekord.exc_info[1] is not None:
        opis = opis_bledu(rekord.exc_info[1])
        if rekord.args:
            opis = opis.replace("%", "%%")  # opis idzie do formatu msg % args
        rekord.msg = f"{rekord.msg} ({opis})" if isinstance(rekord.msg, str) else opis
        rekord.exc_info = None
        rekord.exc_text = None
    return rekord


def wlacz_maskowanie() -> None:
    """Maskowanie dla wszystkich loggerow w procesie. Wywolanie ponowne nic nie zmienia."""
    fabryka = logging.getLogRecordFactory()
    if getattr(fabryka, "_maskuje", False):
        return

    def nowa(*args, **kwargs):
        return _maskuj_rekord(fabryka(*args, **kwargs))

    nowa._maskuje = True
    logging.setLogRecordFactory(nowa)
