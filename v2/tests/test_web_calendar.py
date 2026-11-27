"""The calendar kept the same here and in the web version (notarai.pl), both ways."""
import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient

from worker.api import create_app
from worker.terminarz import Calendar
from worker.vault import Vault
from worker.web_calendar import WebCalendar, WebCalendarError, station_id


class FakeWeb:
    """The web calendar API (app.py /api/kalendarz) with its hour-collision check."""

    def __init__(self):
        self.entries: dict[str, dict] = {}
        self.calls: list[tuple] = []
        self.down = False
        self.status = 200

    def add(self, **fields):
        ident = uuid.uuid4().hex[:12]
        self.entries[ident] = {"id": ident, "data": "2026-12-01", "godzina": "", "koniec": "", "tytul": "", "rodzaj": "",
                               "rodzaj_inny": "", "uczestnicy": "", "telefony": [], "sprawa": "", "uwagi": "", **fields}
        return ident

    def __call__(self, method, path, body):
        self.calls.append((method, path))
        if self.down:
            raise OSError("no network")
        if self.status != 200:
            return self.status, {"detail": "Brak dostępu"}
        if method == "GET":
            return 200, list(self.entries.values())
        if method == "POST":
            for other in self.entries.values():
                if body.get("godzina") and other["data"] == body["data"] and other["godzina"] == body["godzina"]:
                    return 400, {"detail": f"Godziny {other['godzina']}-{other['godzina']} są już zajęte"}
            ident = self.add(**{k: body.get(k, "") for k in ("data", "godzina", "tytul")})
            return 200, self.entries[ident]
        ident = path.rsplit("/", 1)[-1]
        if method == "DELETE":
            return (200, {"ok": True}) if self.entries.pop(ident, None) else (404, {"detail": "Nie ma takiego terminu"})
        raise AssertionError(method)


@pytest.fixture
def office(tmp_path):
    vault = Vault(tmp_path, b"K" * 32)
    web = FakeWeb()
    now = lambda: dt.datetime(2026, 11, 30, 9, 0)
    calendar = Calendar(vault, now, origin=lambda: "A")
    sync = WebCalendar(tmp_path, vault, "A", lambda: web)
    return vault, web, calendar, sync


def changes(result):
    return {k: v for k, v in result.items() if v}


def test_web_entries_come_here_once_and_all_day_has_no_hour(office):
    vault, web, calendar, sync = office
    first = web.add(data="2026-12-01", godzina="10:00", koniec="11:00", rodzaj="sprzedaż", uczestnicy="Kowalski, Nowak")
    web.add(data="2026-12-02", tytul="dzień odrzuceń spadków")
    assert changes(sync.sync()) == {"pobrano": 2}
    items = {e["id"]: e for e in calendar.upcoming(30)}
    assert items["w-" + first]["title"] == "sprzedaż – Kowalski, Nowak" and items["w-" + first]["start"] == "2026-12-01T10:00"
    all_day = next(e for e in items.values() if e["all_day"])
    assert all_day["label"].endswith("cały dzień") and "0:00" not in all_day["label"]
    assert changes(sync.sync()) == {}                                   # idempotent
    assert [c for c in web.calls if c[0] != "GET"] == []


def test_changed_on_the_web_changes_here_and_deleted_on_the_web_goes(office):
    vault, web, calendar, sync = office
    ident = web.add(data="2026-12-01", godzina="10:00", tytul="Podpisanie")
    sync.sync()
    web.entries[ident]["godzina"] = "12:30"
    assert changes(sync.sync()) == {"zmieniono": 1}
    assert calendar.upcoming(30)[0]["start"] == "2026-12-01T12:30"
    del web.entries[ident]
    assert changes(sync.sync()) == {}                                   # an empty calendar: checked once more
    assert changes(sync.sync()) == {"usunieto_tu": 1}
    assert calendar.upcoming(30) == []
    assert changes(sync.sync()) == {}


def test_deleted_here_is_deleted_on_the_web_and_not_brought_back(office):
    vault, web, calendar, sync = office
    ident = web.add(data="2026-12-01", godzina="10:00", tytul="Podpisanie")
    sync.sync()
    calendar.delete("w-" + ident)
    assert changes(sync.sync()) == {"usunieto_w_sieci": 1}
    assert ident not in web.entries and calendar.upcoming(30) == []
    assert changes(sync.sync()) == {}


def test_added_here_goes_to_the_web_once_and_its_deletion_follows(office):
    vault, web, calendar, sync = office
    mine = calendar.add(dt.datetime(2026, 12, 3, 9, 30), "Odbiór wypisu")
    assert changes(sync.sync()) == {"wyslano": 1}
    (sent,) = web.entries.values()
    assert (sent["data"], sent["godzina"], sent["tytul"]) == ("2026-12-03", "09:30", "Odbiór wypisu")
    assert changes(sync.sync()) == {}                                   # not sent twice, not imported back
    assert len(calendar.upcoming(30)) == 1
    calendar.delete(mine["id"])                                          # the id the notary saw stays valid
    assert changes(sync.sync()) == {"usunieto_w_sieci": 1}
    assert web.entries == {}


def test_only_the_station_that_added_an_entry_sends_it(tmp_path, office):
    vault, web, calendar, sync = office
    other = Calendar(vault, origin=lambda: "B")
    other.add(dt.datetime(2026, 12, 4, 8, 0), "Z drugiego stanowiska")
    assert changes(sync.sync()) == {}
    assert web.entries == {}


def test_entries_from_before_are_claimed_then_sent_next_round(office):
    vault, web, calendar, sync = office
    vault.calendar_put("stary1", {"start": "2026-12-05T11:00", "title": "Dawny termin", "case": None, "source": "notariusz"})
    assert changes(sync.sync()) == {}                                   # claimed: other stations see the claim first
    assert next(e for e in vault.calendar() if e["id"] == "stary1")["origin"] == "A"
    assert changes(sync.sync()) == {"wyslano": 1}


def test_refused_by_the_web_stays_here_is_told_once_and_not_retried(office):
    vault, web, calendar, sync = office
    web.add(data="2026-12-03", godzina="09:30", tytul="Zajęte")
    calendar.add(dt.datetime(2026, 12, 3, 9, 30), "Kolizja")
    result = sync.sync()
    assert result["odrzucono"] == 1 and result["pobrano"] == 1
    posts = [c for c in web.calls if c[0] == "POST"]
    (notice,) = sync.notices()
    assert "Kolizja" in notice and "zajęte" in notice
    assert sync.notices() == []
    sync.sync()
    assert [c for c in web.calls if c[0] == "POST"] == posts
    assert any(e["title"] == "Kolizja" for e in calendar.upcoming(30))


def test_network_trouble_changes_nothing(office):
    vault, web, calendar, sync = office
    web.add(data="2026-12-01", tytul="X")
    sync.sync()
    web.down = True
    with pytest.raises(WebCalendarError):
        sync.sync()
    web.down, web.status = False, 401
    with pytest.raises(WebCalendarError) as error:
        sync.sync()
    assert "Zaloguj" in str(error.value)
    web.status = 200
    assert len(calendar.upcoming(30)) == 1


def test_an_empty_answer_does_not_wipe_the_calendar(office):
    vault, web, calendar, sync = office
    web.add(data="2026-12-01", tytul="X")
    sync.sync()
    saved = dict(web.entries)
    web.entries.clear()
    sync.sync()
    assert len(calendar.upcoming(30)) == 1
    web.entries.update(saved)
    sync.sync()
    web.entries.clear()
    sync.sync()                                                         # one glitch again: still nothing lost
    assert len(calendar.upcoming(30)) == 1


def test_not_signed_in(tmp_path):
    vault = Vault(tmp_path, b"K" * 32)
    with pytest.raises(WebCalendarError) as error:
        WebCalendar(tmp_path, vault, station_id(tmp_path), lambda: None).sync()
    assert "Zaloguj" in str(error.value)
    assert station_id(tmp_path) == station_id(tmp_path)


def test_the_notary_asks_for_it_in_the_chat(tmp_path):
    (tmp_path / "vault.key").write_bytes(b"K" * 32)
    (tmp_path / "api.token").write_text("t" * 48)
    web = FakeWeb()
    web.add(data=(dt.date.today() + dt.timedelta(days=1)).isoformat(), godzina="10:00", tytul="Akt Kowalski")
    client = TestClient(create_app(tmp_path, web_calendar_api=lambda: web))
    admin = {"Authorization": "Bearer " + "t" * 48}
    blocks = client.post("/v2/chat", headers=admin, json={"text": "synchronizuj kalendarz"}).json()["blocks"]
    said = " ".join(b.get("text", "") for b in blocks)
    assert "pobrano 1" in said and "wysłano 0" in said
    items = client.get("/v2/calendar", headers=admin).json()["items"]
    assert [e["title"] for e in items] == ["Akt Kowalski"]
