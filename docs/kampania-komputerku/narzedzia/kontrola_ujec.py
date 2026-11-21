#!/usr/bin/env python3
"""Bramka kontroli ujęć: zanim klip (albo klatka startowa) trafi dalej, ogląda go OCR (lokalnie, 0 USD)
i Claude na Bedrock eu-central-1 (obraz; Sonnet 4.6 ≈ 0,01 USD/klatkę, Haiku 4.5 ≈ 0,003 USD, ale gorzej widzi drobny tekst).

Co sprawdza w każdej klatce:
  tekst      litery, cyfry, etykiety, nagłówki, pseudo-pismo wygenerowane w obrazie (zasada ZERO TEKSTU;
             wyjątek: `dozwolony_tekst` ujęcia, ≤ 8 znaków, np. „1 XII" – musi być rozpoznany dokładnie)
  dokument   czy papiery wyglądają jak polskie dokumenty biurowe, czy jak bełkot
  artefakt   dłonie, palce, zlewające się przedmioty, podwójne obiekty
Werdykt ujęcia = najgorsza klatka; do każdego problemu dochodzi zalecenie z torem poprawek (poprawki.py) i szacunkiem kosztu.

Wejście:  wyjscie/EPxx/klipy/*.mp4 albo --plik (mp4/png/jpg); odcinki/EPxx.json (typ ujęcia, dozwolony_tekst)
Wyjście:  wyjscie/EPxx/kontrola.json  + wpis kosztu w narzedzia/koszty_log.csv
Użycie:   kontrola_ujec.py EP04 [--ujecia u2,u9] [--klatki 2|3] [--model sonnet|haiku] [--plik sciezka --ujecie u2]
Wymaga:   ffmpeg, boto3 ≥ 1.40 (AWS_BEARER_TOKEN_BEDROCK albo zwykłe poświadczenia AWS); rapidocr_onnxruntime opcjonalnie.
Do logów nie trafia nic poza nazwą pliku i werdyktem (brak danych osobowych w kadrach z definicji – obsada fikcyjna).
"""
import argparse
import csv
import datetime
import io
import json
import os
import re
import subprocess
import sys
import time

TU = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(TU, ".."))
REGION = "eu-central-1"
MODELE = {"sonnet": ("eu.anthropic.claude-sonnet-4-6", 3.0, 15.0),
          "haiku": ("eu.anthropic.claude-haiku-4-5-20251001-v1:0", 1.0, 5.0)}
KOSZT = {"klatka": 0.03, "i2v_5s": 0.21, "awatar_s": 0.056}
RANGA = {"ok": 0, "poprawic": 1, "odrzucic": 2}
CZYTELNE = re.compile(r"wydruk|dokument|odczyt|zestawien|rubryk|dat[aęy]|etykiet|notatk|napis|printout|document|extract|"
                      r"label|note|date|text|header|highlight", re.I)

SYSTEM = (
    "Kontrola jakości klatek z polskiego mikroserialu o kancelarii notarialnej. Oceniasz wyłącznie to, co widać. "
    "Szukasz: (1) KAŻDEGO tekstu lub pseudo-tekstu wygenerowanego w obrazie: napisy, litery, cyfry, etykiety, odręczne bazgroły "
    "udające pismo, nagłówki dokumentów, także drobne; (2) dokumentów: czy wyglądają jak prawdziwe polskie dokumenty biurowe "
    "(polskie słowa, sensowny układ), czy jak bełkot albo pseudo-angielski; (3) artefaktów generatywnych: zniekształcone dłonie "
    "i palce, zlewające się przedmioty, podwójne obiekty, nielogiczna fizyka. Lampa, kubek, meble, rośliny to zwykłe rekwizyty, "
    "nie artefakty. Jeśli podano DOZWOLONY TEKST, sprawdź, czy widoczny napis to dokładnie on (wtedy czytelny=true i zgodny=true). "
    "Odpowiadasz wyłącznie zwięzłym JSON bez markdown: {\"tekst\": [{\"opis\": str (do 12 słów), \"czytelny\": bool, "
    "\"odczyt\": str, \"zgodny\": bool, \"boks_proc\": [x0,y0,x1,y1]}], \"dokumenty\": \"brak\"|\"wiarygodne\"|\"niewiarygodne\", "
    "\"artefakty\": [str (do 12 słów)], \"ocena\": \"ok\"|\"poprawic\"|\"odrzucic\", \"powod\": str (jedno zdanie)}. "
    "boks_proc to procenty szerokości i wysokości obrazu (0-100), ciasno wokół tekstu."
)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"błąd {cmd[0]}: {r.stderr[-800:]}")
    return r.stdout


def czas_trwania(p):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).strip()
    return float(out) if out else 0.0


def klatki(plik, ile, tmp):
    """Lista (czas_s, png). Obraz → jedna klatka; wideo → 2 (początek, koniec) albo 3 (+ środek)."""
    if plik.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return [(0.0, plik)]
    d = czas_trwania(plik)
    czasy = [0.4, max(0.4, d - 0.4)] if ile == 2 else [0.4, d / 2, max(0.4, d - 0.4)]
    wynik = []
    for i, t in enumerate(czasy):
        p = os.path.join(tmp, f"{os.path.splitext(os.path.basename(plik))[0]}_k{i}.png")
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", plik, "-frames:v", "1", p])
        wynik.append((round(t, 2), p))
    return wynik


_OCR = None


def ocr(png):
    """RapidOCR (lokalnie). Zwraca listę {odczyt, boks_proc, pewnosc}; [] gdy brak silnika."""
    global _OCR
    try:
        if _OCR is None:
            from rapidocr_onnxruntime import RapidOCR
            _OCR = RapidOCR()
        from PIL import Image
        W, H = Image.open(png).size
        res, _ = _OCR(png)
    except Exception:
        return []
    out = []
    for box, txt, conf in (res or []):
        xs, ys = [q[0] for q in box], [q[1] for q in box]
        out.append({"odczyt": txt, "pewnosc": round(float(conf), 2),
                    "boks_proc": [round(min(xs) / W * 100, 1), round(min(ys) / H * 100, 1),
                                  round(max(xs) / W * 100, 1), round(max(ys) / H * 100, 1)]})
    return out


def jpeg_do_modelu(png, dl=1568):
    from PIL import Image
    im = Image.open(png).convert("RGB")
    im.thumbnail((dl, dl))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def parsuj(txt):
    txt = re.sub(r"^```\w*\s*|\s*```$", "", txt.strip(), flags=re.M).strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", txt, re.S)
        return json.loads(m.group(0)) if m else {"ocena": "poprawic", "powod": "model nie zwrócił JSON", "tekst": [], "artefakty": []}


def ocen_klatke(bedrock, model_id, jpg, dozwolony=""):
    pytanie = "Oceń tę klatkę." + (f" DOZWOLONY TEKST: „{dozwolony}”." if dozwolony else " Dozwolony tekst: żaden.")
    for proba in range(4):
        try:
            r = bedrock.converse(
                modelId=model_id, system=[{"text": SYSTEM}],
                messages=[{"role": "user", "content": [{"image": {"format": "jpeg", "source": {"bytes": jpg}}}, {"text": pytanie}]}],
                inferenceConfig={"maxTokens": 700, "temperature": 0})
            return parsuj(r["output"]["message"]["content"][0]["text"]), r["usage"]
        except Exception as e:  # throttling / 5xx – krótki odstęp i jeszcze raz
            if proba == 3 or "Throttl" not in str(e) and "ServiceUnavailable" not in str(e) and "502" not in str(e):
                raise
            time.sleep(3 * (proba + 1))


def podobne(a, b):
    """OCR myli pojedyncze znaki („1 XI" vs „1 XII") – tolerujemy odległość edycyjną 1 i prefiksy."""
    a, b = re.sub(r"\s+", "", a).upper(), re.sub(r"\s+", "", b).upper()
    if a == b or (len(a) >= 2 and (a in b or b in a)):
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    k, d = (a, b) if len(a) < len(b) else (b, a)
    return any(d[:i] + d[i + 1:] == k for i in range(len(d)))


def pole(b):
    return max(0.0, (b[2] - b[0]) / 100) * max(0.0, (b[3] - b[1]) / 100)


def werdykt_ujecia(oceny, dozwolony=""):
    """Scala oceny klatek: (werdykt, problemy[])."""
    problemy, najgorsza = [], "ok"
    for t_s, oc, ocr_boksy in oceny:
        for t in oc.get("tekst") or []:
            if dozwolony and t.get("zgodny"):
                continue
            problemy.append({"typ": "tekst", "klatka_s": t_s, "opis": t.get("opis", ""), "odczyt": t.get("odczyt", ""),
                             "boks_proc": t.get("boks_proc") or [0, 0, 0, 0]})
        if oc.get("dokumenty") == "niewiarygodne":
            problemy.append({"typ": "dokument", "klatka_s": t_s, "opis": oc.get("powod", "")})
        for a in oc.get("artefakty") or []:
            problemy.append({"typ": "artefakt", "klatka_s": t_s, "opis": a})
        for b in ocr_boksy:
            if not (dozwolony and podobne(b["odczyt"], dozwolony)):
                problemy.append({"typ": "tekst", "klatka_s": t_s, "opis": "OCR: " + b["odczyt"], "odczyt": b["odczyt"],
                                 "boks_proc": b["boks_proc"], "zrodlo": "ocr"})
        if RANGA.get(oc.get("ocena"), 1) > RANGA[najgorsza]:
            najgorsza = oc.get("ocena")
    if dozwolony:
        widziany = any(t.get("zgodny") for _, oc, _ in oceny for t in (oc.get("tekst") or []))
        if not widziany:
            problemy.append({"typ": "tekst", "klatka_s": 0, "opis": f"brak dozwolonego tekstu „{dozwolony}” (nie rozpoznany)"})
    if problemy and najgorsza == "ok":
        najgorsza = "poprawic"
    return najgorsza, problemy


def zalecenie(u, werdykt, problemy):
    """Najtańsza metoda, która rozwiązuje problem (szczegóły: poprawki.py)."""
    if werdykt == "ok":
        return {"metoda": "brak", "koszt_usd": 0.0}
    typy = {p["typ"] for p in problemy}
    pow_tekst = sum(pole(p["boks_proc"]) for p in problemy if p["typ"] == "tekst" and p.get("boks_proc"))
    czas = float(u.get("czas_s") or 5)
    typ_u = u.get("typ")
    opis = " ".join(str(u.get(k, "")) for k in ("klatka_startowa", "prompt_delta"))
    if typ_u == "bez_mowy":
        if CZYTELNE.search(opis) and ("tekst" in typy or "dokument" in typy):
            return {"metoda": "dokument", "koszt_usd": 0.0,
                    "dlaczego": "widz ma coś przeczytać – warstwę czytelną renderujemy sami (dokumenty.py)"}
        if "dokument" in typy or pow_tekst > 0.06 or werdykt == "odrzucic":
            return {"metoda": "klatka", "koszt_usd": KOSZT["klatka"] + KOSZT["i2v_5s"],
                    "dlaczego": "tekst/bełkot zajmuje dużą część kadru – nowa klatka startowa z promptem BEZ TEKSTU, QC klatki przed wideo"}
        if "tekst" in typy:
            return {"metoda": "rozmyj", "koszt_usd": 0.0, "dlaczego": "drobny tekst na rekwizycie w tle – rozmycie boksów"}
        return {"metoda": "zostaw", "koszt_usd": 0.0, "dlaczego": "drobny artefakt; do decyzji redaktora"}
    if typ_u == "mowiace":
        teksty = [p for p in problemy if p["typ"] == "tekst" and p.get("boks_proc") and any(p["boks_proc"])]
        if teksty and all(p["boks_proc"][1] >= 70 for p in teksty):
            return {"metoda": "kadruj", "koszt_usd": 0.0,
                    "dlaczego": "pseudo-napisy przy dolnej krawędzi (model „dorobił” napisy) – przycięcie kadru od dołu i powrót do 9:16"}
        if werdykt == "odrzucic":
            return {"metoda": "awatar", "koszt_usd": round(KOSZT["awatar_s"] * czas, 2), "dlaczego": "poważny artefakt w ujęciu mówiącym"}
        if "tekst" in typy and pow_tekst <= 0.03:
            return {"metoda": "rozmyj", "koszt_usd": 0.0, "dlaczego": "drobna etykieta na rekwizycie – rozmycie boksów"}
        if "tekst" in typy:
            return {"metoda": "awatar", "koszt_usd": round(KOSZT["awatar_s"] * czas, 2),
                    "dlaczego": "duży tekst w ujęciu mówiącym – nowa klatka startowa bez tekstu i ponowny awatar"}
        return {"metoda": "zostaw", "koszt_usd": 0.0, "dlaczego": "drobny artefakt; do decyzji redaktora"}
    return {"metoda": "zostaw", "koszt_usd": 0.0}


def zapisz_koszt(ep, pozycja, usd, zrodlo):
    p = os.path.join(TU, "koszty_log.csv")
    nowy = not os.path.exists(p)
    with open(p, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nowy:
            w.writerow(["data", "odcinek", "pozycja", "usd", "zrodlo"])
        w.writerow([datetime.date.today().isoformat(), ep, pozycja, f"{usd:.4f}", zrodlo])


def klient():
    import boto3
    return boto3.client("bedrock-runtime", region_name=REGION)


def sprawdz_plik(bedrock, model, plik, u, ile_klatek, tmp):
    """Pełna kontrola jednego pliku dla ujęcia u. Zwraca (wpis, usage_sum)."""
    model_id, c_we, c_wy = MODELE[model]
    dozwolony = str(u.get("dozwolony_tekst") or "")
    oceny, we, wy = [], 0, 0
    for t_s, png in klatki(plik, ile_klatek, tmp):
        oc, uz = ocen_klatke(bedrock, model_id, jpeg_do_modelu(png), dozwolony)
        we += uz.get("inputTokens", 0); wy += uz.get("outputTokens", 0)
        oceny.append((t_s, oc, ocr(png)))
    werdykt, problemy = werdykt_ujecia(oceny, dozwolony)
    usd = (we * c_we + wy * c_wy) / 1e6
    wpis = {"plik": os.path.relpath(plik, ROOT), "typ": u.get("typ"), "werdykt": werdykt, "problemy": problemy,
            "zalecenie": zalecenie(u, werdykt, problemy), "klatki": len(oceny), "model": model_id,
            "koszt_kontroli_usd": round(usd, 4), "oceny_klatek": [{"czas_s": t, **oc} for t, oc, _ in oceny]}
    return wpis, usd


def main():
    ap = argparse.ArgumentParser(description="Bramka kontroli ujęć (tekst, dokumenty, artefakty)")
    ap.add_argument("odcinek")
    ap.add_argument("--ujecia", help="np. u2,u9 (domyślnie wszystkie klipy w wyjscie/EPxx/klipy)")
    ap.add_argument("--klatki", type=int, choices=(2, 3), help="ile klatek z klipu (domyślnie 2 dla ≤5,5 s, 3 dla dłuższych)")
    ap.add_argument("--model", choices=tuple(MODELE), default="sonnet")
    ap.add_argument("--plik", help="jeden plik (mp4/png/jpg) zamiast katalogu klipów")
    ap.add_argument("--ujecie", help="id ujęcia dla --plik (żeby znać typ i dozwolony_tekst)")
    ap.add_argument("--bez-zapisu", action="store_true", help="nie nadpisuj kontrola.json, tylko wypisz")
    a = ap.parse_args()
    ep = a.odcinek.upper()
    odc = json.load(open(os.path.join(ROOT, "odcinki", f"{ep}.json"), encoding="utf-8"))
    ujecia = {u["id"]: u for u in odc["ujecia"]}
    baza = os.path.join(ROOT, "wyjscie", ep)
    tmp = os.path.join(baza, "tmp", "kontrola"); os.makedirs(tmp, exist_ok=True)
    sciezka_raportu = os.path.join(baza, "kontrola.json")
    raport = json.load(open(sciezka_raportu, encoding="utf-8")) if os.path.exists(sciezka_raportu) else {}
    bedrock = klient()
    zadania = []
    if a.plik:
        if not a.ujecie:
            sys.exit("--plik wymaga --ujecie")
        zadania.append((a.ujecie, a.plik))
    else:
        wybrane = set(a.ujecia.split(",")) if a.ujecia else None
        klipy = os.path.join(baza, "klipy")
        for f in sorted(os.listdir(klipy)):
            if not f.endswith(".mp4"):
                continue
            uid = f.split("_")[0]
            if uid in ujecia and (not wybrane or uid in wybrane):
                zadania.append((uid, os.path.join(klipy, f)))
    razem = 0.0
    print(f"{'ujęcie':7}{'werdykt':10}{'zalecenie':10}{'koszt':8} problemy")
    for uid, plik in zadania:
        u = ujecia.get(uid, {"id": uid, "typ": "bez_mowy"})
        ile = a.klatki or (2 if plik.lower().endswith(".mp4") and czas_trwania(plik) <= 5.5 else 3)
        wpis, usd = sprawdz_plik(bedrock, a.model, plik, u, ile, tmp)
        razem += usd
        raport[uid] = wpis
        z = wpis["zalecenie"]
        krotko = "; ".join(f"{p['typ']}: {p['opis'][:50]}" for p in wpis["problemy"][:3])
        print(f"{uid:7}{wpis['werdykt']:10}{z['metoda']:10}{z['koszt_usd']:<8.2f}{krotko}")
    if not a.bez_zapisu:
        json.dump(raport, open(sciezka_raportu, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n→ {sciezka_raportu}")
    if razem:
        zapisz_koszt(ep, f"Kontrola klatek Bedrock ({a.model}), {len(zadania)} plików", razem, "bedrock")
    print(f"koszt kontroli: {razem:.3f} USD")


if __name__ == "__main__":
    main()
