"""Klucz kancelarii: sprawy w S3 zaszyfrowane kluczem, ktorego nie mamy.

Minimalne 3 x ZERO (docs/3zero-minimum.md):
  - klucz (128 bitow) losuje przegladarka wlasciciela i pokazuje go jako kod
    do zapisania; serwer nigdy go nie zapisuje (ani w S3, ani w logach,
    ani w Secrets Manager),
  - przegladarka dokleja kod do kazdego zadania (naglowek X-Klucz-Kancelarii);
    serwer trzyma go tylko w pamieci na czas zadania (ContextVar),
  - kazdy plik sprawy idzie do S3 jako AES-256-GCM; dane uwierzytelniajace
    (AAD) to klucz obiektu w S3, wiec pliku nie da sie przeniesc do innej
    sprawy ani kancelarii bez wykrycia,
  - w rejestrze kancelarii lezy tylko KCV (HMAC znanej stalej): pozwala
    odroznic zly kod od uszkodzonego pliku, a klucza z niego nie odtworzymy.

Czego to NIE daje (uczciwie): w trakcie zadania plaintext i klucz sa
w pamieci kontenera, bo model w Bedrock musi przeczytac dokument. Operator,
ktory podmieni kod aplikacji, moglby je przechwycic. Przed tym chronia
procedury (wdrozenie wylacznie z GitHub Actions, brak ECS Exec, CloudTrail),
a nie kryptografia. Etap z atestacja Nitro jest opcjonalny i osobny.
"""
import base64
import hashlib
import hmac
import os
import secrets
from contextvars import ContextVar

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NAGLOWEK = "X-Klucz-Kancelarii"
_MAGIA = b"NAI1"          # format pliku: MAGIA | nonce(12) | szyfrogram+tag(16)
_DLUGOSC_KLUCZA = 16      # 128 bitow losowosci; kod ma 26 znakow base32
_ALFABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


class BrakKlucza(RuntimeError):
    """Kancelaria szyfruje sprawy, a zadanie nie przynioslo kodu."""


class ZlyKlucz(RuntimeError):
    """Kod nie pasuje do kancelarii albo plik zostal zmieniony."""


# None             - kancelaria nie szyfruje (dotychczasowe zachowanie),
# _BEZ_KLUCZA      - szyfruje, ale zadanie nie ma kodu: odczyt/zapis spraw odmowi,
# bytes (32)       - klucz AES tego zadania.
_BEZ_KLUCZA = object()
stan_var: ContextVar[object] = ContextVar("szyfrowanie_kancelarii", default=None)


# --- kod <-> bajty -----------------------------------------------------------


def nowy_kod() -> str:
    """Losowy kod kancelarii (uzywany w testach; w produkcji losuje przegladarka)."""
    return _na_kod(secrets.token_bytes(_DLUGOSC_KLUCZA))


def _na_kod(surowe: bytes) -> str:
    tekst = base64.b32encode(surowe).decode("ascii").rstrip("=")
    return "-".join(tekst[i:i + 4] for i in range(0, len(tekst), 4))


def z_kodu(kod: str) -> bytes:
    """Kod wpisany przez czlowieka -> 16 bajtow. Myslniki, spacje i wielkosc
    liter nie maja znaczenia; 0/1/8 to czeste pomylki z O/I/B."""
    czysty = "".join(z for z in (kod or "").upper() if z not in "- \t")
    czysty = czysty.translate(str.maketrans("018", "OIB"))
    if len(czysty) != 26 or any(z not in _ALFABET for z in czysty):
        raise ZlyKlucz("Kod kancelarii ma 26 znaków (litery A-Z i cyfry 2-7).")
    try:
        surowe = base64.b32decode(czysty + "======")
    except ValueError as blad:
        raise ZlyKlucz("Nieprawidłowy kod kancelarii.") from blad
    if len(surowe) != _DLUGOSC_KLUCZA:
        raise ZlyKlucz("Nieprawidłowy kod kancelarii.")
    return surowe


def _pochodny(surowe: bytes, cel: bytes) -> bytes:
    """HKDF-SHA256 (RFC 5869) z jednym blokiem wyjscia: osobny klucz do plikow
    i osobny do KCV, wiec KCV nie mowi nic o kluczu szyfrujacym."""
    prk = hmac.new(b"notarai-kancelaria-v1", surowe, hashlib.sha256).digest()
    return hmac.new(prk, cel + b"\x01", hashlib.sha256).digest()


def kcv(kod: str) -> str:
    """Wartosc kontrolna kodu do rejestru kancelarii."""
    return _pochodny(z_kodu(kod), b"kcv").hex()[:32]


# --- stan zadania --------------------------------------------------------------


def ustaw_dla_zadania(kcv_kancelarii: str | None, kod: str | None):
    """Wywolywane przez middleware. Zwraca token do reset().
    ZlyKlucz, gdy kod podany, ale nie pasuje do kancelarii."""
    if not kcv_kancelarii:
        return stan_var.set(None)
    if not kod:
        return stan_var.set(_BEZ_KLUCZA)
    if not hmac.compare_digest(kcv(kod), kcv_kancelarii):
        raise ZlyKlucz("Ten kod nie pasuje do kancelarii. Sprawdź, czy przepisałeś go bez błędu.")
    return stan_var.set(_pochodny(z_kodu(kod), b"pliki-spraw"))


def aktywne() -> bool:
    return stan_var.get() is not None


def _klucz() -> bytes:
    stan = stan_var.get()
    if stan is None or stan is _BEZ_KLUCZA:
        raise BrakKlucza("Sprawy tej kancelarii są zaszyfrowane jej kodem. Wpisz kod kancelarii.")
    return stan  # type: ignore[return-value]


def szyfruj(dane: bytes, adres: str) -> bytes:
    """Plaintext -> plik do S3. `adres` (klucz obiektu S3) wchodzi do AAD."""
    nonce = os.urandom(12)
    return _MAGIA + nonce + AESGCM(_klucz()).encrypt(nonce, dane, adres.encode("utf-8"))


def odszyfruj(surowe: bytes, adres: str) -> bytes:
    klucz = _klucz()
    if not surowe.startswith(_MAGIA) or len(surowe) < len(_MAGIA) + 12 + 16:
        # Kancelaria z wlaczonym szyfrowaniem nie ma prawa miec jawnych plikow:
        # nie podsuwamy ich modelowi ani notariuszowi.
        raise ZlyKlucz("Plik sprawy nie jest zaszyfrowany kluczem kancelarii - odmawiam odczytu.")
    nonce = surowe[len(_MAGIA):len(_MAGIA) + 12]
    try:
        return AESGCM(klucz).decrypt(nonce, surowe[len(_MAGIA) + 12:], adres.encode("utf-8"))
    except Exception as blad:  # noqa: BLE001 - InvalidTag: zly klucz albo zmieniony plik
        raise ZlyKlucz("Pliku sprawy nie da się odszyfrować: zmieniony plik albo inny klucz.") from blad
