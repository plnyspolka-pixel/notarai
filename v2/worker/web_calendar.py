"""The office calendar kept the same in NotarAI 2.0 and in the web version (notarai.pl), both ways.

Owner's decision 27.11.2026. The station talks to the web calendar's own API with the signed-in person's
login (Cognito ID token), so the web version still checks everything (the office, the team, hour
collisions). No other data of the web version is read.

- A web entry W lives here as "w-W" (the same id on every station of the office, so stations agree).
- Changed on the web -> changed here. Gone from the web -> gone here.
- Deleted here -> deleted on the web (a deletion is remembered as a tombstone; the link local id -> web id
  is kept in `kalendarz-web.json`, which holds ids only).
- Added here -> sent to the web by the station that added it ("origin"); an entry from before this
  feature is first claimed by one station, and sent on its next round, so two stations never both send it.
- The web refuses an entry (e.g. the hours are taken): it stays here, is not sent again, and the notary
  is told once.
Nothing about entries is logged. Network trouble: quiet, next round tries again.
"""
import datetime as dt
import hashlib
import json
import secrets
import threading
from pathlib import Path

WEB_FIELDS = ("data", "godzina", "koniec", "tytul", "rodzaj", "rodzaj_inny", "uczestnicy", "telefony", "sprawa", "uwagi")
SOURCE = "notarai.pl"


class WebCalendarError(Exception):
    """Fixed Polish message, safe to show."""


def station_id(home: Path) -> str:
    """A stable random id of this station (not its name: names change)."""
    path = Path(home) / "stanowisko-id.txt"
    try:
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    except OSError:
        pass
    value = secrets.token_hex(8)
    path.write_text(value, encoding="utf-8")
    return value


def http_api(base: str, id_token, *, timeout: float = 20.0):
    """`call(method, path, body) -> (status, json)` against the web version, with a fresh ID token each call."""
    import urllib.error
    import urllib.request

    def call(method: str, path: str, body: dict | None = None):
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
        request = urllib.request.Request(base.rstrip("/") + path, data=data, method=method, headers={
            "Authorization": "Bearer " + id_token(), "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as error:
            try:
                detail = json.loads(error.read() or b"null")
            except ValueError:
                detail = None
            return error.code, detail
    return call


def _sig(web: dict) -> str:
    fields = {k: web.get(k) for k in WEB_FIELDS}
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:32]


def _title(web: dict) -> str:
    kind = web.get("rodzaj_inny") if web.get("rodzaj") == "inne" else web.get("rodzaj")
    head = (web.get("tytul") or kind or "").strip()
    who = (web.get("uczestnicy") or "").strip()
    if who and who.lower() not in head.lower():
        head = f"{head} – {who}" if head else who
    return " ".join(head.split())[:200] or "Termin"


def _local(web: dict) -> dict:
    hour = web.get("godzina") or ""
    return {"start": f"{web['data']}T{hour or '00:00'}", "all_day": not hour, "title": _title(web), "case": None,
            "source": SOURCE, "web": {"id": web["id"], "sig": _sig(web), **{k: web.get(k) for k in WEB_FIELDS}}}


def _detail(body) -> str:
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, list):                               # FastAPI validation errors
        detail = "; ".join(str(d.get("msg", "")) for d in detail if isinstance(d, dict))
    return str(detail or "kalendarz w notarai.pl nie przyjął terminu")[:200]


class WebCalendar:
    def __init__(self, home: Path, vault, me: str, api_factory):
        """`api_factory()` returns `call(method, path, body)` or None when the station is not signed in."""
        self._path = Path(home) / "kalendarz-web.json"
        self._vault, self._me, self._api_factory = vault, me, api_factory
        self._lock = threading.Lock()
        self.last: dict | None = None

    # ------------------------------------------------------------ state (ids only, no personal data)
    def _load(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        data.setdefault("links", {})          # local id -> web id
        data.setdefault("refused", {})        # local id -> reason, told to the notary or not yet
        data.setdefault("told", [])
        return data

    def _save(self, data: dict) -> None:
        self._path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def notices(self) -> list[str]:
        """Entries the web refused, each told once (shown to the notary in the window, never logged)."""
        with self._lock:
            data = self._load()
            fresh = [i for i in data["refused"] if i not in data["told"]]
            if not fresh:
                return []
            titles = {e["id"]: e for e in self._vault.calendar()}
            out = []
            for ident in fresh:
                entry = titles.get(ident)
                if entry:
                    out.append(f"Terminu {entry['start'].replace('T', ' ')} „{entry['title']}” nie dodałem do kalendarza "
                               f"w notarai.pl: {data['refused'][ident]}. Został tylko w NotarAI 2.0.")
            data["told"] = (data["told"] + fresh)[-500:]
            self._save(data)
            return out

    # ------------------------------------------------------------ one round
    def sync(self) -> dict:
        call = self._api_factory()
        if call is None:
            raise WebCalendarError("Zaloguj stanowisko do NotarAI, żeby łączyć kalendarz z notarai.pl.")
        with self._lock:
            return self._sync(call)

    def _sync(self, call) -> dict:
        result = {"pobrano": 0, "zmieniono": 0, "wyslano": 0, "usunieto_tu": 0, "usunieto_w_sieci": 0, "odrzucono": 0}
        try:
            status, web_list = call("GET", "/api/kalendarz", None)
        except Exception:
            raise WebCalendarError("Kalendarz w notarai.pl teraz nie odpowiada. Spróbuję ponownie za chwilę.") from None
        if status in (401, 403):
            raise WebCalendarError("Kalendarz w notarai.pl nie przyjął logowania tego stanowiska. "
                                   "Zaloguj stanowisko kontem kancelarii.")
        if status != 200 or not isinstance(web_list, list):
            raise WebCalendarError("Kalendarz w notarai.pl teraz nie odpowiada. Spróbuję ponownie za chwilę.")
        web = {str(w["id"]): w for w in web_list if isinstance(w, dict) and w.get("id") and w.get("data")}
        data = self._load()
        links = data["links"]
        local = {e["id"]: e for e in self._vault.calendar()}
        for ident, entry in local.items():                    # entries other stations sent are linked here too
            if isinstance(entry.get("web"), dict) and entry["web"].get("id"):
                links[ident] = str(entry["web"]["id"])
        dead = self._vault.tombstoned("calendar")
        dead_web = {links.get(i) or (i[2:] if i.startswith("w-") else None) for i in dead} - {None}

        # 1. deleted here -> deleted on the web
        for web_id in sorted(dead_web & set(web)):
            try:
                status, _ = call("DELETE", f"/api/kalendarz/{web_id}", None)
            except Exception:
                continue
            if status in (200, 204, 404):
                web.pop(web_id, None)
                result["usunieto_w_sieci"] += 1

        # 2. from the web: new or changed
        by_web = {str(e["web"]["id"]): e for e in local.values() if isinstance(e.get("web"), dict) and e["web"].get("id")}
        for web_id, item in web.items():
            mine = by_web.get(web_id)
            if mine is None:
                if web_id in dead_web:
                    continue
                self._vault.calendar_put("w-" + web_id, _local(item), actor="kalendarz-web")
                links["w-" + web_id] = web_id
                result["pobrano"] += 1
            elif mine["web"].get("sig") != _sig(item):
                fresh = _local(item)
                fresh.update({k: mine[k] for k in ("case", "origin") if mine.get(k) is not None})
                fresh["source"] = mine.get("source", SOURCE)
                self._vault.calendar_put(mine["id"], fresh, actor="kalendarz-web")
                result["zmieniono"] += 1

        # 3. gone from the web -> gone here. An empty answer while entries are linked may be a glitch of the
        #    web version: it counts only when the next round says the same.
        empty = not web and bool(by_web)
        confirmed = not empty or data.get("empty_before", False)
        data["empty_before"] = empty
        if confirmed:
            for web_id, mine in by_web.items():
                if web_id not in web and web_id not in dead_web:
                    self._vault.calendar_delete(mine["id"], actor="kalendarz-web")
                    result["usunieto_tu"] += 1

        # 4. added here -> to the web, by the station that added it
        for ident, entry in local.items():
            if entry.get("web") is not None or ident in data["refused"] or ident.startswith("w-"):
                continue
            origin = entry.get("origin")
            if origin is None:                                 # from before this feature: claim, send next round
                self._vault.calendar_put(ident, {**{k: v for k, v in entry.items() if k not in ("id", "updated")},
                                                 "origin": self._me}, actor="kalendarz-web")
                continue
            if origin != self._me:
                continue
            start = dt.datetime.fromisoformat(entry["start"])
            body = {"data": start.date().isoformat(), "godzina": "" if entry.get("all_day") else start.strftime("%H:%M"),
                    "tytul": entry["title"][:200]}
            try:
                status, made = call("POST", "/api/kalendarz", body)
            except Exception:
                continue
            if status == 200 and isinstance(made, dict) and made.get("id"):
                linked = {**{k: v for k, v in entry.items() if k not in ("id", "updated")},
                          "web": {"id": str(made["id"]), "sig": _sig(made), **{k: made.get(k) for k in WEB_FIELDS}}}
                self._vault.calendar_put(ident, linked, actor="kalendarz-web")
                links[ident] = str(made["id"])
                result["wyslano"] += 1
            elif status in (400, 404, 409, 422):
                data["refused"][ident] = _detail(made)
                result["odrzucono"] += 1
        data["links"] = {i: w for i, w in links.items() if i in local or i in dead}
        self._save(data)
        self.last = result
        return result


def summary(result: dict) -> str:
    text = (f"Kalendarz z notarai.pl: pobrano {result['pobrano']}, zmieniono {result['zmieniono']}, "
            f"wysłano {result['wyslano']}, usunięto {result['usunieto_tu'] + result['usunieto_w_sieci']}.")
    if result["odrzucono"]:
        text += f" Nie przyjęto {result['odrzucono']} (powód poniżej)."
    return text
