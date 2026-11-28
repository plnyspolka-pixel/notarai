"""Public registers for a case: land registers (EKW) and the debtors' register (KRZ).

EKW: the text of a land register comes from the AWS function notarai-v2-rejestry, which runs
V1's ekw.py (Finance You or Apify); the provider's key never reaches this computer. The call is
signed with the workstation's own sign-in. KRZ: V1's portal knowledge (krz_portal.py) searches
krz.ms.gov.pl in the NotarAI browser on this computer, two searches per PESEL, screenshots into
the case. Both are read-only and done one at a time, on the notary's request.

The result is not an official copy: the notary compares it with the source.
"""
import json
import re
import tempfile
import time
from pathlib import Path

from . import domain

FUNCTION = "notarai-v2-rejestry"
PESEL = re.compile(r"(?<!\d)(\d{11})(?!\d)")
KW = re.compile(r"\b([A-Z0-9]{4}/\d{8}/\d)\b", re.I)


class RegisterError(Exception):
    """Fixed Polish message, safe to show."""


def land_register_numbers(text: str) -> list[str]:
    return list(dict.fromkeys(n.upper() for n in KW.findall(text or "")))


def pesels_in(text: str) -> list[str]:
    return [p for p in dict.fromkeys(PESEL.findall(text or "")) if domain.valid_pesel(p)[0]]


class Registers:
    def __init__(self, account, region: str, *, invoke=None, browser=None, visible_browser=None,
                 function: str = FUNCTION):
        """`account()` -> the signed-in workstation account; `browser()` -> the hidden browser for KRZ (owner's
        decision 27.11.2026: KRZ is searched in the background, no window); `visible_browser()` -> the NotarAI
        window, used only when the notary asks for it after the hidden search failed."""
        self._account, self._region, self._function = account, region, function
        self._invoke = invoke
        self._browser = browser
        self._visible = visible_browser

    # ------------------------------------------------------------ land registers
    def land_register(self, number: str) -> dict:
        number = re.sub(r"\s+", "", number or "").upper()
        good, why = domain.valid_land_register(number)
        if not good:
            raise RegisterError(f"Numer księgi {number or '(pusty)'} jest nieprawidłowy: {why}.")
        payload = {"rejestr": "kw", "numer": number}
        answer = self._call(payload, "Zaloguj stanowisko do NotarAI, żeby pobierać księgi wieczyste.",
                            "Nie udało się połączyć z usługą ksiąg wieczystych. Spróbuj ponownie.")
        if not isinstance(answer, dict) or not answer.get("ok"):
            message = (answer or {}).get("komunikat") if isinstance(answer, dict) else None
            raise RegisterError(_polish(message) or "Księgi nie udało się pobrać.")
        return answer

    def debtors_api(self, pesel: str) -> dict:
        """KRZ through Apify, in the AWS function (owner's decision 28.11.2026: first; the browser is the fallback).
        Raises RegisterError when Apify does not answer, so the caller can fall back to the browser."""
        answer = self._call({"rejestr": "krz", "pesel": pesel}, "Zaloguj stanowisko do NotarAI, żeby sprawdzać KRZ przez Apify.",
                            "Nie udało się połączyć z usługą rejestrów.")
        if not isinstance(answer, dict) or not answer.get("ok"):
            raise RegisterError(_polish((answer or {}).get("komunikat") if isinstance(answer, dict) else None)
                                or "Apify nie odpowiedziało.")
        return answer

    def _call(self, payload: dict, not_signed: str, no_link: str) -> dict:
        if self._invoke is not None:
            answer = self._invoke(payload)
        else:
            account = self._account()
            if account is None:
                raise RegisterError(not_signed)
            from botocore.config import Config

            import boto3

            current = account.credentials()
            client = boto3.client("lambda", region_name=self._region, aws_access_key_id=current["access_key"],
                                  aws_secret_access_key=current["secret_key"], aws_session_token=current["token"],
                                  config=Config(read_timeout=320, retries={"max_attempts": 0}))
            try:
                response = client.invoke(FunctionName=self._function, Payload=json.dumps(payload).encode())
                answer = json.loads(response["Payload"].read())
            except Exception as error:
                if error.__class__.__name__ == "LoginError":
                    raise
                raise RegisterError(no_link) from None
        return answer

    # ------------------------------------------------------------ debtors' register
    def debtors(self, pesel: str, label: str = "", *, visible: bool = False, seen=None, told=None) -> dict:
        """Two searches for one PESEL in KRZ; screenshots returned as (name, bytes). `seen(jpeg)` gets what the
        page shows after each search, for the live view in the NotarAI window."""
        opener = self._visible if visible and self._visible is not None else self._browser
        if opener is None:
            raise RegisterError("Sprawdzanie w KRZ działa na komputerze kancelarii.")
        portal = domain.krz_portal()
        browser = opener()
        if visible and hasattr(browser, "show"):
            browser.show()
        failure = {}

        def search(page):
            try:
                with tempfile.TemporaryDirectory() as scratch:
                    shots = Path(scratch)

                    def shot(name):
                        if seen is not None:
                            try:
                                seen(page.screenshot(type="jpeg", quality=45))
                            except Exception:
                                pass
                        return shots / name
                    stop = _screencast(page, seen)
                    try:
                        result = portal.przebieg(_Told(portal.StronaPlaywright(page), told, pesel), pesel, label,
                                                 zrzut_do=shot)
                    finally:
                        stop()
                    result["zrzuty"] = [(p.name, p.read_bytes()) for p in sorted(shots.glob("*.png"))]
                    return result
            except Exception as error:            # the real cause, without the PESEL, instead of „no answer”
                failure["why"] = re.sub(r"\d", "•", f"{type(error).__name__}: {error}")[:160]
                raise
        try:
            return browser.on_page(search, timeout=240)
        except Exception as error:
            if failure.get("why"):
                raise RegisterError(f"Strona KRZ: {failure['why']}") from None
            raise RegisterError(str(error) or "Przeglądarka nie odpowiedziała.") from None


class _Told:
    """The KRZ page, saying each move in the conversation: what it opens, which tab, what it types, what it clicks."""

    def __init__(self, page, told, pesel):
        self._page, self._told = page, told or (lambda line: None)
        self._masked = pesel[:4] + "*******"

    def otworz(self):
        self._told("Otwieram krz.ms.gov.pl w przeglądarce NotarAI.")
        return self._page.otworz()

    def wybierz_zakladke(self, nazwa):
        self._told(f"Klikam zakładkę „{nazwa}”.")
        return self._page.wybierz_zakladke(nazwa)

    def wpisz_identyfikator(self, wartosc):
        self._told(f"Wpisuję PESEL {self._masked} w pole „Identyfikator”.")
        return self._page.wpisz_identyfikator(wartosc)

    def wyszukaj(self):
        self._told("Klikam „Wyszukaj”.")
        return self._page.wyszukaj()

    def wyczysc(self):
        self._told("Czyszczę formularz.")
        return self._page.wyczysc()

    def tekst_wyniku(self):
        self._told("Czytam wynik wyszukiwania.")
        return self._page.tekst_wyniku()

    def zrzut(self, cel):
        return self._page.zrzut(cel)

    def __getattr__(self, name):
        return getattr(self._page, name)


def _screencast(page, seen):
    """A picture of the page about once a second while the search runs, for the NotarAI window (memory only)."""
    if seen is None:
        return lambda: None
    import base64 as _b64
    import time as _time

    try:
        session = page.context.new_cdp_session(page)
    except Exception:
        return lambda: None
    last = {"at": 0.0}

    def frame(event):
        try:
            session.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})
            if _time.monotonic() - last["at"] >= 1.0:
                last["at"] = _time.monotonic()
                seen(_b64.b64decode(event["data"]))
        except Exception:
            pass
    try:
        session.on("Page.screencastFrame", frame)
        session.send("Page.startScreencast", {"format": "jpeg", "quality": 40, "maxWidth": 1100, "everyNthFrame": 2})
    except Exception:
        return lambda: None

    def stop():
        try:
            session.send("Page.stopScreencast")
            session.detach()
        except Exception:
            pass
    return stop


def _polish(message: str | None) -> str | None:
    """V1 messages are written without Polish letters; put the common ones back for the notary."""
    if not message:
        return None
    for plain, proper in (("Ksiegi", "Księgi"), ("ksiegi", "księgi"), ("Bledna", "Błędna"), ("sprobuj", "spróbuj"),
                          ("pozniej", "później"), ("odpowiedzial", "odpowiedział"), ("Wyczerpany", "Wyczerpany"),
                          ("bezplatnego", "bezpłatnego"), ("dzialu", "działu"), ("Dzial", "Dział"),
                          ("calosci", "całości"), ("oddal", "oddał"), ("polaczenia", "połączenia")):
        message = message.replace(plain, proper)
    return message.rstrip(".") + "."
