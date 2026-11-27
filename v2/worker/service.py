"""Service mode: the notary asks for a change of the program in a sentence; the program changes itself.

„popraw program: przycisk Wyślij ma być większy” -> names of every case's parties, numbers and e-mail
addresses are cut out on this computer -> an event (source notarai.v2.serwis) signed with the
workstation's sign-in -> the AWS queue for the self-repair pipeline and an e-mail to the owner. When
an update carrying that change arrives (its wersja.json lists the request ids it closes), the program
says „Twoja zmiana już działa”. Requests are kept here, in the office's home folder, without the
original wording's personal data.
"""
import json
import secrets
import time
from pathlib import Path

from .learning import anonymize


class ServiceError(Exception):
    """Fixed Polish message, safe to show."""


class ServiceDesk:
    def __init__(self, home: Path, vault, account, region: str, station, version, *, send=None, clock=time.time):
        self._path = Path(home) / "zgloszenia.json"
        self._vault, self._account, self._region = vault, account, region
        self._station, self._version, self._send, self._clock = station, version, send, clock

    def requests(self) -> list[dict]:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _save(self, items: list[dict]) -> None:
        self._path.write_text(json.dumps(items[-200:], ensure_ascii=False, indent=1), encoding="utf-8")

    def _names(self) -> list[str]:
        return self._vault.all_parties()

    def ask(self, wording: str) -> dict:
        text = anonymize(" ".join(wording.split())[:3000], self._names())
        if len(text) < 8:
            raise ServiceError("Opisz zmianę jednym, dwoma zdaniami, np. „popraw program: przycisk Wyślij ma być większy”.")
        entry = {"id": "Z-" + secrets.token_hex(3).upper(), "tresc": text, "utworzono": self._clock(),
                 "stanowisko": self._station(), "wersja": self._version() or "?", "stan": "wysylanie"}
        detail = {k: entry[k] for k in ("id", "tresc", "stanowisko", "wersja")}
        try:
            if self._send is not None:
                self._send(detail)
            else:
                account = self._account()
                if account is None:
                    raise ServiceError("Zaloguj stanowisko do NotarAI, żeby wysyłać prośby o zmianę programu.")
                response = account.client_factory(self._region)("events").put_events(Entries=[{
                    "Source": "notarai.v2.serwis", "DetailType": "prosba", "EventBusName": "default",
                    "Detail": json.dumps(detail, ensure_ascii=False)}])
                if response.get("FailedEntryCount"):
                    raise ServiceError("Nie udało się wysłać prośby. Spróbuj za chwilę.")
            entry["stan"] = "wyslane"
        except ServiceError:
            entry["stan"] = "blad"
            self._save(self.requests() + [entry])
            raise
        except Exception as error:
            entry["stan"] = "blad"
            self._save(self.requests() + [entry])
            if error.__class__.__name__ == "LoginError":
                raise
            raise ServiceError("Nie udało się wysłać prośby. Sprawdź internet i spróbuj ponownie.") from None
        self._save(self.requests() + [entry])
        return entry

    def delivered(self, closed: list[dict]) -> list[dict]:
        """Requests an installed update says it closes; each is reported once."""
        done = {str(item.get("id")): str(item.get("opis", "")) for item in closed or []}
        items, news = self.requests(), []
        for item in items:
            if item["id"] in done and item["stan"] != "wdrozone":
                item["stan"], item["opis_zmiany"] = "wdrozone", done[item["id"]]
                news.append(item)
        if news:
            self._save(items)
        return news
