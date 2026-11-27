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
    def __init__(self, account, region: str, *, invoke=None, browser=None, function: str = FUNCTION):
        """`account()` -> the signed-in workstation account; `browser()` -> the NotarAI browser."""
        self._account, self._region, self._function = account, region, function
        self._invoke = invoke
        self._browser = browser

    # ------------------------------------------------------------ land registers
    def land_register(self, number: str) -> dict:
        number = re.sub(r"\s+", "", number or "").upper()
        good, why = domain.valid_land_register(number)
        if not good:
            raise RegisterError(f"Numer księgi {number or '(pusty)'} jest nieprawidłowy: {why}.")
        payload = {"rejestr": "kw", "numer": number}
        if self._invoke is not None:
            answer = self._invoke(payload)
        else:
            account = self._account()
            if account is None:
                raise RegisterError("Zaloguj stanowisko do NotarAI, żeby pobierać księgi wieczyste.")
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
                raise RegisterError("Nie udało się połączyć z usługą ksiąg wieczystych. Spróbuj ponownie.") from None
        if not isinstance(answer, dict) or not answer.get("ok"):
            message = (answer or {}).get("komunikat") if isinstance(answer, dict) else None
            raise RegisterError(_polish(message) or "Księgi nie udało się pobrać.")
        return answer

    # ------------------------------------------------------------ debtors' register
    def debtors(self, pesel: str, label: str = "") -> dict:
        """Two searches for one PESEL in KRZ; screenshots returned as (name, bytes)."""
        if self._browser is None:
            raise RegisterError("Sprawdzanie w KRZ działa na komputerze kancelarii, w przeglądarce NotarAI.")
        portal = domain.krz_portal()
        browser = self._browser()

        def search(page):
            with tempfile.TemporaryDirectory() as scratch:
                shots = Path(scratch)
                result = portal.przebieg(portal.StronaPlaywright(page), pesel, label, zrzut_do=lambda name: shots / name)
                result["zrzuty"] = [(p.name, p.read_bytes()) for p in sorted(shots.glob("*.png"))]
                return result
        return browser.on_page(search, timeout=240)


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
