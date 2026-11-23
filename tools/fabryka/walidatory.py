"""Bramka automatyczna scenariusza odcinka V6 (BIBLIA_V6 §3, §4, §5).

Każda reguła zwraca listę problemów (pusta = zaliczone). `sprawdz()` zbiera wszystko; scenariusz
przechodzi do planu produkcji dopiero bez problemów. Reguły mierzalne liczymy z danych, a punkty
listy thrillera, których nie da się policzyć, muszą mieć w scenariuszu uzasadnienie.
"""
from __future__ import annotations

import re

PLANSZA_KONCOWA = "Na motywach prawdziwych spraw z polskich sądów. Osoby i szczegóły zmienione."

OBSADA = {
    "helena", "marta", "basia", "kuba", "irena", "pawel", "joanna", "robert",
    "zosia", "teresa", "sowa", "klient", "klientka", "lektor",
}
TYPY_UJEC = {"mowiace", "bez_mowy", "dokument", "ekran", "plansza"}
ROLE = ["zimne_otwarcie", "tytul", "swiat", "zwrot1", "praca", "szczyt", "zawieszenie", "plansza_koncowa"]
TYPY_OTWARCIA = {"A", "B", "C"}
MUZYKA = {"brak", "ciepla", "dzwieki_kancelarii"}

# Kotwice wykluczone na stałe (zarzuty wobec notariuszy, H17) i P01 dopiero od sezonu 2.
WYKLUCZONE = {f"P{i:02d}" for i in range(5, 21)} | {"H17"}
TYLKO_OD_SEZONU_2 = {"P01"}

LISTA_THRILLERA = [
    "czynnosc_jako_rama", "odkrycie_z_lektury", "dokument_w_kadrze", "widz_zna_ryzyko",
    "wynik_niepewny_bez_przemocy", "jeden_szczyt", "nic_spoza_swiata", "ekran_poza_szczytem",
    "zgodnie_z_prawem", "sprawiedliwosc_proceduralna", "prawdziwa_sprawa_bez_danych", "final_domyka",
]

# Słowa, które w promptach obrazu wywołują wypalony tekst (METODYKA ai-clip) albo łamią zasadę zero tekstu.
ZAKAZANE_W_PROMPCIE = re.compile(
    r"\b(text|caption|captions|subtitle|subtitles|logo|label|labels|headline|napis\w*|letters?)\b", re.I)
SYGNATURA = re.compile(r"\b(I{1,3}|IV|V|VI{0,3})\s+(ACa|AKa|C|Ca|Cz|CZP|CSK|Ns|K|GC|AGa|UK|ZP)\s+\d+/\d{2}\b")
PESEL = re.compile(r"\b\d{11}\b")
SMIECH = re.compile(r"(śmiech z taśmy|laugh ?track|canned laughter|śmiech publiczności)", re.I)
TAG_V3 = re.compile(r"^\s*\[[^\]]+\]")
OKNO_SZCZYTU_S = 5.0


def _ujecia(sc: dict):
    for scena in sc.get("sceny", []):
        for u in scena.get("ujecia", []):
            yield scena, u


def _osie_czasu(sc: dict) -> list[tuple[float, float, dict, dict]]:
    """(od, do, scena, ujęcie) z sumowania czasów ujęć po kolei."""
    t = 0.0
    wynik = []
    for scena, u in _ujecia(sc):
        d = float(u.get("czas_s") or 0)
        wynik.append((t, t + d, scena, u))
        t += d
    return wynik


def dlugosc(sc: dict) -> float:
    o = _osie_czasu(sc)
    return o[-1][1] if o else 0.0


def r_struktura(sc: dict, **_) -> list[str]:
    p = []
    for k in ("id", "sezon", "odcinek", "tytul", "sprawa_kotwica", "prowadzi", "typ_otwarcia", "sceny"):
        if not sc.get(k):
            p.append(f"brak pola `{k}`")
    if sc.get("typ_otwarcia") and sc["typ_otwarcia"] not in TYPY_OTWARCIA:
        p.append("`typ_otwarcia` musi być A, B albo C")
    role = [s.get("rola") for s in sc.get("sceny", [])]
    if role and role[0] != "zimne_otwarcie":
        p.append("pierwsza scena musi być zimnym otwarciem")
    if role and role[-1] != "plansza_koncowa":
        p.append("ostatnia scena musi być planszą końcową")
    if role.count("szczyt") != 1:
        p.append(f"musi być dokładnie jedna scena `szczyt` (jest {role.count('szczyt')})")
    nieznane = [r for r in role if r not in ROLE]
    if nieznane:
        p.append(f"nieznane role scen: {nieznane}")
    if not 7 <= len(role) <= 10:
        p.append(f"scen powinno być 7–9 (+ plansza końcowa); jest {len(role)}")
    return p


def r_dlugosc(sc: dict, **_) -> list[str]:
    d = dlugosc(sc)
    return [] if 60 <= d <= 90 else [f"długość {d:.1f} s poza zakresem 60–90 s"]


def r_otwarcie(sc: dict, poprzedni_typ_otwarcia: str | None = None, **_) -> list[str]:
    p = []
    for od, do, scena, u in _osie_czasu(sc):
        if od >= 3:
            break
        if u.get("typ") in {"plansza", "ekran", "dokument"}:
            p.append(f"{u.get('id')}: w pierwszych 3 s nie może być planszy, logo, ekranu ani dokumentu")
    if poprzedni_typ_otwarcia and sc.get("typ_otwarcia") == poprzedni_typ_otwarcia:
        p.append("ten sam typ otwarcia co w poprzednim odcinku")
    glosy = {u.get("postac") for od, do, s, u in _osie_czasu(sc) if od < 10 and u.get("typ") == "mowiace"}
    if len(glosy) < 2:
        p.append("w pierwszych 10 s muszą paść dwa głosy")
    return p


def r_szczyt_i_ekran(sc: dict, **_) -> list[str]:
    p = []
    osie = _osie_czasu(sc)
    szczyt = [(od, do) for od, do, s, u in osie if s.get("rola") == "szczyt"]
    if not szczyt:
        return p
    s_od, s_do = min(a for a, _ in szczyt), max(b for _, b in szczyt)
    for od, do, s, u in osie:
        if u.get("typ") == "ekran" and do > s_od - OKNO_SZCZYTU_S and od < s_do + OKNO_SZCZYTU_S:
            p.append(f"{u.get('id')}: ekran programu w oknie szczytu (±{OKNO_SZCZYTU_S:.0f} s)")
        if u.get("typ") == "ekran" and not (u.get("ekran") or {}).get("funkcja"):
            p.append(f"{u.get('id')}: ekran bez wskazanej funkcji programu")
    if not any(u.get("typ") == "dokument" for _, _, _, u in osie):
        p.append("brak ujęcia `dokument` (konkretny dokument w kadrze, punkt 3 listy)")
    return p


def r_przerwania(sc: dict, **_) -> list[str]:
    """Punkt 7: poza planszą tytułową i końcową nic spoza świata (plansze) nie przerywa akcji."""
    return [f"{u.get('id')}: plansza w środku odcinka" for s, u in _ujecia(sc)
            if u.get("typ") == "plansza" and s.get("rola") not in {"tytul", "plansza_koncowa"}]


def r_plansza_koncowa(sc: dict, **_) -> list[str]:
    ost = (sc.get("sceny") or [{}])[-1]
    teksty = [u.get("tekst", "") for u in ost.get("ujecia", [])]
    return [] if any(PLANSZA_KONCOWA in t for t in teksty) else ["plansza końcowa bez wymaganego zdania"]


def r_bity(sc: dict, **_) -> list[str]:
    p = []
    zart = [u for _, u in _ujecia(sc) if u.get("zart")]
    romans = [u for _, u in _ujecia(sc) if u.get("romans")]
    if len(zart) > 1:
        p.append("najwyżej jeden żart na odcinek")
    if len(romans) > 1:
        p.append("najwyżej jeden beat romansu na odcinek")
    for _, u in _ujecia(sc):
        if u.get("zart") and u.get("postac") in {"irena", "pawel", "joanna", "robert", "klient", "klientka"}:
            p.append(f"{u.get('id')}: żart kosztem klienta")
    return p


def r_mowa(sc: dict, **_) -> list[str]:
    p = []
    for _, u in _ujecia(sc):
        if u.get("typ") == "mowiace":
            if u.get("postac") not in OBSADA:
                p.append(f"{u.get('id')}: postać spoza obsady `{u.get('postac')}`")
            if not u.get("kwestia") or not TAG_V3.match(u.get("kwestia_v3") or ""):
                p.append(f"{u.get('id')}: kwestia bez wersji z tagiem ElevenLabs v3 (np. `[calm] …`)")
    return p


def r_zero_tekstu(sc: dict, **_) -> list[str]:
    p = []
    for _, u in _ujecia(sc):
        if u.get("typ") in {"mowiace", "bez_mowy"}:
            pr = " ".join(str(u.get(k) or "") for k in ("prompt_ruchu", "prompt_delta"))
            if ZAKAZANE_W_PROMPCIE.search(pr):
                p.append(f"{u.get('id')}: prompt obrazu zawiera słowo wywołujące tekst/logo")
            dt = u.get("dozwolony_tekst")
            if dt and len(dt) > 8:
                p.append(f"{u.get('id')}: `dozwolony_tekst` dłuższy niż 8 znaków")
    return p


def r_dane_i_nazwiska(sc: dict, **_) -> list[str]:
    """Punkt 11 i zakaz nazwiska notariusza: bez sygnatur, PESEL, odwołań do SAOS w treści odcinka."""
    p = []
    tekst = " ".join(str(u.get(k) or "") for _, u in _ujecia(sc) for k in ("kwestia", "tekst", "prompt_delta"))
    tekst += " " + str(sc.get("tytul", "")) + " " + str(sc.get("pytanie_koncowe", ""))
    if SYGNATURA.search(tekst):
        p.append("w treści jest sygnatura akt")
    if PESEL.search(tekst):
        p.append("w treści jest numer w formacie PESEL")
    if re.search(r"saos|sygn\.", tekst, re.I):
        p.append("w treści jest odwołanie do źródła orzeczenia")
    if (sc.get("konsultant") or {}).get("nazwisko"):
        p.append("nazwisko konsultanta/notariusza nie może się pojawić (zakaz reklamy notariuszy)")
    return p


def r_dzwiek(sc: dict, **_) -> list[str]:
    p = []
    m = sc.get("muzyka") or {}
    if m.get("typ") and m["typ"] not in MUZYKA:
        p.append(f"muzyka `{m['typ']}` spoza dozwolonych {sorted(MUZYKA)}")
    if SMIECH.search(str(sc)):
        p.append("śmiech z taśmy jest zakazany")
    return p


def r_kotwica(sc: dict, uzyte_w_sezonie: set[str] | None = None, **_) -> list[str]:
    p = []
    k = str(sc.get("sprawa_kotwica") or "")
    ids = re.findall(r"[A-Z]\d{2}", k)
    if not ids:
        return ["brak kotwicy w prawdziwej sprawie"]
    for i in ids:
        if i in WYKLUCZONE:
            p.append(f"kotwica {i} jest wykluczona na stałe")
        if i in TYLKO_OD_SEZONU_2 and int(sc.get("sezon") or 1) < 2:
            p.append(f"kotwica {i} dopiero od sezonu 2")
        if uzyte_w_sezonie and i in uzyte_w_sezonie and "motyw" not in k and "echo" not in k and "wariant" not in k:
            p.append(f"kotwica {i} była już użyta w tym sezonie")
    return p


def r_lista_thrillera(sc: dict, **_) -> list[str]:
    lt = sc.get("lista_kontrolna") or {}
    p = []
    for k in LISTA_THRILLERA:
        w = lt.get(k)
        if k == "final_domyka" and int(sc.get("odcinek") or 0) % 40 != 0:
            continue  # dotyczy tylko finału sezonu
        if not isinstance(w, dict) or w.get("ok") is not True or not str(w.get("jak", "")).strip():
            p.append(f"lista thrillera: punkt `{k}` bez potwierdzenia i uzasadnienia")
    return p


def r_scenografia(sc: dict, scenografia: dict | None = None, **_) -> list[str]:
    """Plan, kamera i znacznik muszą istnieć w opis.json danego planu (gdy katalog jest dostępny)."""
    if not scenografia:
        return []
    p = []
    for scena in sc.get("sceny", []):
        if scena.get("rola") in {"tytul", "plansza_koncowa"}:
            continue
        plan = scenografia.get(scena.get("plan"))
        if plan is None:
            p.append(f"scena {scena.get('id')}: nieznany plan `{scena.get('plan')}`")
            continue
        kamery = {k["nazwa"] for k in plan.get("kamery", [])}
        znaczniki = {z["nazwa"] for z in plan.get("znaczniki", [])}
        for u in scena.get("ujecia", []):
            kam = u.get("kamera") or scena.get("kamera")
            if u.get("typ") in {"mowiace", "bez_mowy"} and kam not in kamery:
                p.append(f"{u.get('id')}: kamera `{kam}` nie istnieje w planie {scena.get('plan')}")
            if u.get("typ") == "mowiace" and u.get("znacznik") and u["znacznik"] not in znaczniki:
                p.append(f"{u.get('id')}: znacznik `{u['znacznik']}` nie istnieje w planie {scena.get('plan')}")
    return p


REGULY = [r_struktura, r_dlugosc, r_otwarcie, r_szczyt_i_ekran, r_przerwania, r_plansza_koncowa, r_bity,
          r_mowa, r_zero_tekstu, r_dane_i_nazwiska, r_dzwiek, r_kotwica, r_lista_thrillera, r_scenografia]


def sprawdz(sc: dict, **kontekst) -> list[str]:
    wynik = []
    for r in REGULY:
        wynik += r(sc, **kontekst)
    return wynik
