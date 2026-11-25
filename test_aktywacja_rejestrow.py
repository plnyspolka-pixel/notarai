import threading
import pytest
import aktywacja_rejestrow as ar

OK = dict(integralnosc=True, sciezka_zaufania_ue=True, kwalifikowany=True, nieodwolany=True)

class W:
    def __init__(s): s.kto = "osoba-A"; s.zmien = {}
    def zweryfikuj(s, podpis):
        return ar.DowodPodpisu(**{**OK, **s.zmien}, podpisany_challenge=podpis.decode(), identyfikator_podpisujacego=s.kto) \
            if "challenge" not in s.zmien else ar.DowodPodpisu(**OK, podpisany_challenge=s.zmien["challenge"], identyfikator_podpisujacego=s.kto)
class K:
    czynni = {"osoba-A", "osoba-B"}
    def czynny_notariusz(s, i): return i in s.czynni
class S:
    def __init__(s): s.klucze = {("k1", "a@x", "rznp")}
    def ma_klucz(s, k, e, u): return (k, e, u) in s.klucze

T = [1000.0]
def nowy():
    w, s = W(), S()
    return ar.Aktywacje(w, K(), s, zegar=lambda: T[0]), w, s

def decyzja(do=10**9): return ar.Decyzja("COI", "DEC/1", "2026-11-25", "abc", do)

def zlozony(a, k="k1", e="a@x", u="rznp", sesja="s1"):
    a.przygotuj_wniosek(k, e, u)
    n = a.wystaw_challenge(sesja, k, e, u)
    a.zloz_z_podpisem(sesja, k, e, u, n, n.encode(), True)

def pelny(a):
    zlozony(a); a.przyznaj("k1", "a@x", "rznp", decyzja()); a.skonfigurowano("k1", "a@x", "rznp")

def test_pelna_sciezka_i_brama():
    a, _, _ = nowy(); T[0] = 1000.0
    assert a.moze_uzyc(True, "k1", "a@x", "rznp") == (False, "status_brak")
    pelny(a)
    assert a.moze_uzyc(True, "k1", "a@x", "rznp") == (True, "")

def test_replay_challenge():
    a, _, _ = nowy(); a.przygotuj_wniosek("k1", "a@x", "rznp")
    n = a.wystaw_challenge("s1", "k1", "a@x", "rznp")
    a.zloz_z_podpisem("s1", "k1", "a@x", "rznp", n, n.encode(), True)
    with pytest.raises(ar.BladAktywacji): a.zloz_z_podpisem("s1", "k1", "a@x", "rznp", n, n.encode(), True)

def test_challenge_jednorazowy_rownolegle():
    a, _, _ = nowy(); n = a.wystaw_challenge("s1", "k1", "a@x", "rznp"); w = []
    def f():
        try: a._zuzyj(n, "s1", "k1", "a@x", "rznp"); w.append(1)
        except ar.BladAktywacji: w.append(0)
    t = [threading.Thread(target=f) for _ in range(8)]; [x.start() for x in t]; [x.join() for x in t]
    assert sum(w) == 1

@pytest.mark.parametrize("zmiana", [("s2", "k1", "a@x", "rznp"), ("s1", "k2", "a@x", "rznp"),
                                    ("s1", "k1", "b@x", "rznp"), ("s1", "k1", "a@x", "pesel")])
def test_challenge_zwiazany_z_sesja_kancelaria_osoba_celem(zmiana):
    a, _, _ = nowy(); a.przygotuj_wniosek("k1", "a@x", "rznp")
    n = a.wystaw_challenge("s1", "k1", "a@x", "rznp")
    with pytest.raises(ar.BladAktywacji): a.zloz_z_podpisem(*zmiana[:1], *zmiana[1:], n, n.encode(), True)

def test_ttl():
    a, _, _ = nowy(); T[0] = 1000.0; a.przygotuj_wniosek("k1", "a@x", "rznp")
    n = a.wystaw_challenge("s1", "k1", "a@x", "rznp"); T[0] += 301
    with pytest.raises(ar.BladAktywacji): a.zloz_z_podpisem("s1", "k1", "a@x", "rznp", n, n.encode(), True)
    T[0] = 1000.0

@pytest.mark.parametrize("zm", [{"sciezka_zaufania_ue": False}, {"kwalifikowany": False}, {"nieodwolany": False}, {"integralnosc": False}])
def test_certyfikat_samopodpisany_odwolany_niekwalifikowany(zm):
    a, w, _ = nowy(); w.zmien = zm; a.przygotuj_wniosek("k1", "a@x", "rznp")
    n = a.wystaw_challenge("s1", "k1", "a@x", "rznp")
    with pytest.raises(ar.BladAktywacji): a.zloz_z_podpisem("s1", "k1", "a@x", "rznp", n, n.encode(), True)
    assert a.status("k1", "a@x", "rznp") == ar.WNIOSEK

def test_podpis_innego_challenge():
    a, w, _ = nowy(); w.zmien = {"challenge": "cudzy"}; a.przygotuj_wniosek("k1", "a@x", "rznp")
    n = a.wystaw_challenge("s1", "k1", "a@x", "rznp")
    with pytest.raises(ar.BladAktywacji): a.zloz_z_podpisem("s1", "k1", "a@x", "rznp", n, b"x", True)

def test_brak_wpisu_krn_i_brak_zgody():
    a, w, _ = nowy(); w.kto = "ktos-obcy"; a.przygotuj_wniosek("k1", "a@x", "rznp")
    n = a.wystaw_challenge("s1", "k1", "a@x", "rznp")
    with pytest.raises(ar.BladAktywacji): a.zloz_z_podpisem("s1", "k1", "a@x", "rznp", n, n.encode(), True)
    w.kto = "osoba-A"; n = a.wystaw_challenge("s1", "k1", "a@x", "rznp")
    with pytest.raises(ar.BladAktywacji): a.zloz_z_podpisem("s1", "k1", "a@x", "rznp", n, n.encode(), False)

def test_podszycie_inna_osoba_na_tym_koncie_i_ta_sama_tozsamosc_na_dwoch_kontach():
    a, w, s = nowy(); zlozony(a)
    w.kto = "osoba-B"; a.przygotuj_wniosek("k1", "a@x", "pesel")
    n = a.wystaw_challenge("s1", "k1", "a@x", "pesel")
    with pytest.raises(ar.BladAktywacji): a.zloz_z_podpisem("s1", "k1", "a@x", "pesel", n, n.encode(), True)
    w.kto = "osoba-A"; a.przygotuj_wniosek("k1", "b@x", "rznp")
    n = a.wystaw_challenge("s1", "k1", "b@x", "rznp")
    with pytest.raises(ar.BladAktywacji): a.zloz_z_podpisem("s1", "k1", "b@x", "rznp", n, n.encode(), True)

def test_uzytkownik_nie_ustawi_przyznany_bez_decyzji_i_bez_zlozenia():
    a, _, _ = nowy(); a.przygotuj_wniosek("k1", "a@x", "rznp")
    with pytest.raises(ar.BladAktywacji): a.przyznaj("k1", "a@x", "rznp", decyzja())  # nie złożony
    a2, _, _ = nowy(); zlozony(a2)
    with pytest.raises(ar.BladAktywacji): a2.przyznaj("k1", "a@x", "rznp", ar.Decyzja("", "", "", "", 0))
    with pytest.raises(ar.BladAktywacji): a2.skonfigurowano("k1", "a@x", "rznp")

def test_cross_tenant():
    a, _, s = nowy(); pelny(a); s.klucze.add(("k2", "a@x", "rznp"))
    assert a.moze_uzyc(True, "k2", "a@x", "rznp") == (False, "status_brak")
    assert a.moze_uzyc(True, "k1", "b@x", "rznp") == (False, "status_brak")

def test_demo_serwis_i_nie_chroniona():
    a, _, _ = nowy(); pelny(a)
    assert a.moze_uzyc(False, "k1", "a@x", "rznp") == (False, "tylko_indywidualna_sesja")
    assert a.moze_uzyc(True, "k1", "a@x", "krs")[0] is False

def test_odwolanie_wygasniecie_brak_klucza_rotacja():
    a, _, s = nowy(); T[0] = 1000.0; pelny(a)
    a.rotacja_klucza("k1", "a@x", "rznp")
    s.klucze.clear(); assert a.moze_uzyc(True, "k1", "a@x", "rznp") == (False, "brak_klucza")
    with pytest.raises(ar.BladAktywacji): a.rotacja_klucza("k1", "a@x", "rznp")
    s.klucze.add(("k1", "a@x", "rznp"))
    a.odwolaj("k1", "a@x", "rznp")
    assert a.moze_uzyc(True, "k1", "a@x", "rznp") == (False, "status_odwolany")
    a2, _, _ = nowy(); zlozony(a2); a2.przyznaj("k1", "a@x", "rznp", decyzja(do=T[0] + 50)); a2.skonfigurowano("k1", "a@x", "rznp")
    T[0] += 100
    assert a2.moze_uzyc(True, "k1", "a@x", "rznp") == (False, "status_wygasly")
    T[0] = 1000.0

def test_nie_chroniona_usluga_nie_ma_aktywacji():
    a, _, _ = nowy()
    with pytest.raises(ar.BladAktywacji): a.wystaw_challenge("s", "k", "e", "krs")
