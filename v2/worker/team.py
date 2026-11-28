"""People of the office and what each may do (owner's decision 27.11.2026).

Accounts: the notary creates, blocks and unblocks the logins of the office's people from the chat. The AWS
function `notarai-v2-zespol` (stack in infra/) does it in Cognito after checking, with the caller's own access
token, that the caller is a notary (group notarai-v2-notariusz) and that the person belongs to the same office.
The new person gets an e-mail with a temporary password and sets their own at the first sign-in on a station.

Permissions: what each person may do, kept in the office's vault (so every station of the office sees the
same list) and enforced by code on every command of the person signed in on the station. Default for a
new person: everything except accounts and permissions, which are the notary's alone.
"""
import json
import re
import threading
import time

from .rules import CASE

NAME = "uprawnienia-osob.json"
FUNCTION = "notarai-v2-zespol"

PERMISSIONS = {                 # key -> (what it covers, word stems the notary may use for it)
    "sprawy": ("sprawy i dokumenty", ("spraw", "dokument", "projekt")),
    "kalendarz": ("kalendarz i komunikator", ("kalendar", "termin", "komunikator", "wiadomosc")),
    "poczta": ("wysyłanie poczty", ("poczt", "mail")),
    "wnioski": ("wnioski, formularze i praca agenta na komputerze", ("wniosk", "wnios", "formularz", "agent", "komputer")),
    "zatwierdzanie": ("zatwierdzanie aktów", ("zatwierdz", "akty", "aktow")),
    "ustawienia": ("zasady i ustawienia kancelarii", ("ustawien", "zasad")),
}
DEFAULT = {key: True for key in PERMISSIONS}
EMAIL = re.compile(r"[^@\s,;:„”\"']{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}")


class TeamError(Exception):
    """Fixed Polish message, safe to show."""


def permission_of(words: str) -> str | None:
    for key, (_, names) in PERMISSIONS.items():
        if any(name in words for name in names):
            return key
    return None


class Team:
    def __init__(self, vault, account, region: str, *, invoke=None, clock=time.monotonic):
        """`account()` -> the station's Account or None. `invoke(payload)` replaces the AWS call in tests."""
        self._vault, self._account, self._region = vault, account, region
        self._invoke, self._clock = invoke, clock
        self._lock = threading.Lock()
        self._who: tuple[float, dict] | None = None

    # ------------------------------------------------------------ the AWS function
    def _call(self, action: str, **fields) -> dict:
        account = self._account()
        if account is None or not account.signed_in:
            raise TeamError("Zaloguj stanowisko, żeby zarządzać kontami osób.")
        payload = {"akcja": action, **fields}
        try:
            if self._invoke is not None:
                answer = self._invoke({**payload, "token": "test"})
            else:
                payload["token"] = account.access_token()
                client = account.client_factory(self._region)("lambda")
                raw = client.invoke(FunctionName=FUNCTION, Payload=json.dumps(payload).encode())["Payload"].read()
                answer = json.loads(raw)
        except TeamError:
            raise
        except Exception as error:
            if error.__class__.__name__ == "LoginError":
                raise TeamError(str(error)) from None
            raise TeamError("Nie udało się połączyć z kontami kancelarii. Sprawdź internet i spróbuj ponownie.") from None
        if not isinstance(answer, dict) or not answer.get("ok"):
            raise TeamError(str((answer or {}).get("komunikat") or "Nie udało się."))
        return answer

    def whoami(self, *, fresh=False) -> dict:
        """{"email", "notariusz"} of the person signed in here; cached for 10 minutes (offline: last known)."""
        with self._lock:
            if not fresh and self._who and self._clock() - self._who[0] < 600:
                return self._who[1]
        try:
            who = self._call("kto")
            who = {"email": str(who.get("email", "")).lower(), "notariusz": bool(who.get("notariusz"))}
        except TeamError:
            with self._lock:
                if self._who:
                    return self._who[1]
            account = self._account()
            try:
                email = account.email() if account is not None and account.signed_in else ""
            except Exception:
                email = ""
            who = {"email": email, "notariusz": False}
            with self._lock:                      # offline: ask the function again in a minute, not on every command
                self._who = (self._clock() - 540, who)
            return who
        with self._lock:
            self._who = (self._clock(), who)
        return who

    def people(self) -> list[dict]:
        return self._call("lista")["osoby"]

    def add(self, email: str) -> bool:
        return bool(self._call("dodaj", email=email.lower()).get("nowe"))

    def block(self, email: str) -> None:
        self._call("zablokuj", email=email.lower())

    def unblock(self, email: str) -> None:
        self._call("odblokuj", email=email.lower())

    # ------------------------------------------------------------ permissions (in the office's vault)
    def _document(self):
        return next((d for d in self._vault.summaries({CASE}) if d["name"] == NAME), None)

    def all_permissions(self) -> dict:
        found = self._document()
        if found is None:
            return {}
        _, _, data = self._vault.get(found["id"], actor="uprawnienia")
        return json.loads(data)

    def permissions(self, email: str) -> dict:
        return {**DEFAULT, **self.all_permissions().get(email.lower(), {})}

    def set_permission(self, email: str, key: str, allowed: bool, actor: str) -> dict:
        if key not in PERMISSIONS:
            raise TeamError("Nie znam takiego uprawnienia.")
        with self._lock:
            everything = self.all_permissions()
            person = {**DEFAULT, **everything.get(email.lower(), {}), key: allowed}
            everything[email.lower()] = person
            data = json.dumps(everything, ensure_ascii=False, indent=1).encode()
            found = self._document()
            if found is None:
                self._vault.put(None, 0, NAME, data, actor=actor, case=CASE)
            else:
                self._vault.put(found["id"], found["version"], NAME, data, actor=actor)
        return person

    def may(self, key: str) -> bool:
        """May the person signed in on this station do `key`? Notaries and stations nobody signed in to
        (local use without AI) may; a person the notary limited may not."""
        account = self._account()
        if account is None or not account.signed_in:
            return True
        who = self.whoami()
        if who["notariusz"] or not who["email"]:
            return True
        return bool(self.permissions(who["email"]).get(key, True))
