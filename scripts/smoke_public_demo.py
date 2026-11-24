"""Non-mutating production smoke check for public NotarAI demo.

Only public demo credentials and synthetic fixture routes are used.
Never print tokens or production response bodies.
"""
import json
import urllib.error
import urllib.request

BASE = "https://app.notarai.pl"


def request(path, method="GET", payload=None, token=None):
    headers = {"Accept": "application/json", "Cache-Control": "no-cache"}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    # Don't forward credentials to another origin via redirects.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=25) as res:
            return res.status, res.read(1024 * 1024)
    except urllib.error.HTTPError as err:
        return err.code, b""


def check():
    status, page = request("/")
    assert status == 200 and b'id="pole-email"' in page, "Main login form unavailable"
    status, body = request("/api/logowanie", "POST", {"email":"test","haslo":"test"})
    assert status == 200, f"Public demo login HTTP {status}"
    session = json.loads(body)
    assert session.get("demo") is True and session.get("token"), "Not a demo session"
    token = session["token"]
    status, body = request("/api/ustawienia", token=token)
    assert status == 200 and json.loads(body).get("kancelaria") == "notarai-demo-public"
    status, body = request("/api/sprawy", token=token)
    assert status == 200 and [x["id"] for x in json.loads(body)] == ["DEMO001"]
    status, body = request("/api/sprawy/DEMO001", token=token)
    assert status == 200 and "DEMO" in json.loads(body)["projekt"]
    status, _ = request("/api/logowanie", "POST", {"email":"test","haslo":"invalid-demo-password"})
    assert status == 401, "Wrong password accepted"
    status, _ = request("/api/admin/kancelarie", token=token)
    assert status == 403, "Demo admin access not denied"
    status, _ = request("/api/sprawy/DEMO-NONEXISTENT", token=token)
    assert status == 403, "Non-demo case access not denied"
    print("Production demo smoke: login, fixtures, wrong password and access denial OK.")


if __name__ == "__main__":
    check()
