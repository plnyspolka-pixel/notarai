import threading
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import edoreczenia_auth as ea
import edoreczenia_wysylka as ew

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
PUB = KEY.public_key()
ADE = "AE:PL-97075-47631-STVJH-19"

def idp(rej, ttl=300, status=200):
    def f(r):
        rej.append(r)
        return httpx.Response(status, json={"access_token": f"tok{len(rej)}", "expires_in": ttl, "token_type": "Bearer"})
    return f

def kl(rej, zegar, **kw):
    return ea.KlientTokenu(ADE, "NotarAI", lambda: PEM, "int", client=httpx.Client(transport=httpx.MockTransport(idp(rej, **kw))), zegar=zegar)

def test_asercja_i_zapytanie():
    rej, t = [], [1000.0]
    k = kl(rej, lambda: t[0])
    assert k.token() == "tok1"
    r = rej[0]
    assert r.url.params["login_hint"] == ADE and r.url.host == "int-ow.edoreczenia.gov.pl"
    from urllib.parse import parse_qs
    f = parse_qs(r.content.decode())
    assert f["grant_type"] == ["client_credentials"] and "jwt-bearer" in f["client_assertion_type"][0]
    c = jwt.decode(f["client_assertion"][0], PUB, algorithms=["RS256"], audience=ea.AUDIENCE["int"], options={"verify_exp": False, "verify_nbf": False, "verify_iat": False})
    assert c["iss"] == c["sub"] == f"{ADE}.SYSTEM.NotarAI" and c["exp"] - c["iat"] == 300 and c["jti"]

def test_token_nie_jest_pobierany_ponownie_przed_wygasnieciem():
    rej, t = [], [1000.0]
    k = kl(rej, lambda: t[0])
    k.token(); t[0] += 200; k.token()
    assert len(rej) == 1
    t[0] += 100
    assert k.token() == "tok2" and len(rej) == 2
    assert k.naglowki()["Authorization"] == "Bearer tok2"

@pytest.mark.parametrize("kw", [{"status": 401}, {"ttl": 0}])
def test_bledy_tokenu(kw):
    with pytest.raises(ea.BladUwierzytelnienia):
        kl([], lambda: 1.0, **kw).token()

def test_domyslnie_wylaczone_prod_i_klucz_jako_funkcja():
    with pytest.raises(ValueError): ea.KlientTokenu(ADE, "S", lambda: PEM, None)
    with pytest.raises(ValueError): ea.KlientTokenu(ADE, "S", lambda: PEM, "prod")
    with pytest.raises(ValueError): ea.KlientTokenu(ADE, "S", PEM.decode(), "int")
    with pytest.raises(ValueError): ea.KlientTokenu("zly", "S", lambda: PEM, "int")
    k = ea.KlientTokenu(ADE, "S", lambda: PEM, "int")
    assert "PRIVATE" not in repr(k)

class T:
    def __init__(s, wynik=None): s.w, s.n, s.klucze = wynik, 0, []
    def wyslij(s, p, klucz):
        s.n += 1; s.klucze.append(klucz)
        if isinstance(s.w, Exception): raise s.w
        return "dost-1"

def zatw(sk, k="k1"):
    p = sk.szkic(k, "a@x", "AE:PL-1", "Tytuł", "Treść")
    sk.zatwierdz(k, p, "n@x", True)
    return p

def test_wysylka_wymaga_zatwierdzenia_i_jest_jednorazowa():
    t = T(); sk = ew.Skrzynka(t)
    p = sk.szkic("k1", "a@x", "AE:PL-1", "T", "R")
    with pytest.raises(ew.BladPrzesylki): sk.wyslij("k1", p)
    with pytest.raises(ew.BladPrzesylki): sk.zatwierdz("k1", p, "a@x", False)
    sk.zatwierdz("k1", p, "n@x", True)
    assert sk.wyslij("k1", p) == "dost-1" and sk.stan("k1", p) == ew.WYSLANY
    with pytest.raises(ew.BladPrzesylki): sk.wyslij("k1", p)
    assert t.n == 1

def test_zmiana_tresci_cofa_zatwierdzenie():
    t = T(); sk = ew.Skrzynka(t); p = zatw(sk)
    sk.zmien("k1", p, tresc="Inna")
    assert sk.stan("k1", p) == ew.SZKIC
    with pytest.raises(ew.BladPrzesylki): sk.wyslij("k1", p)

def test_timeout_to_nieznany_bez_automatycznego_ponowienia():
    t = T(TimeoutError()); sk = ew.Skrzynka(t); p = zatw(sk)
    with pytest.raises(ew.BladPrzesylki): sk.wyslij("k1", p)
    assert sk.stan("k1", p) == ew.NIEZNANY
    with pytest.raises(ew.BladPrzesylki): sk.wyslij("k1", p)
    with pytest.raises(ew.BladPrzesylki): sk.ponow("k1", p)
    assert t.n == 1
    sk.uzgodnij("k1", p, wyslano=True, dostawca_id="x")
    assert sk.stan("k1", p) == ew.WYSLANY

def test_odrzucenie_pozwala_ponowic_z_nowym_kluczem():
    t = T(ew.Odrzucone()); sk = ew.Skrzynka(t); p = zatw(sk)
    with pytest.raises(ew.BladPrzesylki): sk.wyslij("k1", p)
    sk.ponow("k1", p); sk.zatwierdz("k1", p, "n@x", True)
    t.w = None; sk.wyslij("k1", p)
    assert t.klucze[0] != t.klucze[1] and sk.stan("k1", p) == ew.WYSLANY

def test_izolacja_kancelarii():
    sk = ew.Skrzynka(T()); p = zatw(sk, "k1")
    for op in (lambda: sk.stan("k2", p), lambda: sk.wyslij("k2", p), lambda: sk.zmien("k2", p, tresc="x"),
               lambda: sk.zatwierdz("k2", p, "n", True), lambda: sk.stan("k1", "brak")):
        with pytest.raises(ew.BladPrzesylki) as e: op()
        assert str(e.value) == "Nie ma takiej przesyłki."

def test_rownolegla_wysylka_tylko_raz():
    t = T(); sk = ew.Skrzynka(t); p = zatw(sk)
    wyn = []
    def run():
        try: sk.wyslij("k1", p); wyn.append("ok")
        except ew.BladPrzesylki: wyn.append("blad")
    th = [threading.Thread(target=run) for _ in range(8)]
    [x.start() for x in th]; [x.join() for x in th]
    assert t.n == 1 and wyn.count("ok") == 1
