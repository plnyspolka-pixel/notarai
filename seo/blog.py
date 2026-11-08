"""Blog notarai.pl: artykuly pisane przez model na podstawie faktow z taksa.py.

    py -3 seo\\blog.py fakty                  -> wypisuje blok FAKTY (to dostaje model)
    py -3 seo\\blog.py generuj "temat"        -> seo/blog/szkice/<slug>.md
    py -3 seo\\blog.py tematy                 -> szkice dla tematow z seo/tematy.txt, ktorych jeszcze nie ma
    py -3 seo\\blog.py zbuduj                 -> strona/blog/<slug>/index.html + strona/blog/index.html

Model dostaje tylko fakty policzone przez taksa.py (stawki, przyklady,
dokumenty), zeby nie wymyslal kwot. Artykul laduje w seo/blog/szkice/ -
czlowiek go czyta, a do publikacji przenosi do seo/blog/. zbuduj renderuje
tylko seo/blog/*.md. Plik: naglowek miedzy "---" (tytul, opis, data, temat,
model) i tresc w Markdown.
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KORZEN))

from seo import baza as moduł_bazy  # noqa: E402
from seo.strona import (KATALOG_STRONY, STRONA, data_pl, esc, markdown,  # noqa: E402
                        przyklady_kosztow, szkielet, zl)

import taksa  # noqa: E402

KATALOG_ARTYKULOW = Path(__file__).resolve().parent / "blog"
KATALOG_SZKICOW = KATALOG_ARTYKULOW / "szkice"
PLIK_TEMATOW = Path(__file__).resolve().parent / "tematy.txt"


# ---------------------------------------------------------------- fakty dla modelu

def fakty() -> str:
    linie = ["FAKTY (sprawdzone w Dzienniku Ustaw; stan na " + date.today().isoformat() + ")", "",
             "Podstawa: rozporzadzenie Ministra Sprawiedliwosci z 28.06.2004 r. w sprawie maksymalnych stawek "
             "taksy notarialnej (t.j. Dz.U. 2024 poz. 1566), zmienione rozporzadzeniem z 13.10.2026 r. "
             "(Dz.U. 2026 poz. 1370), ktore obowiazuje od 5 listopada 2026 r. Rozporzadzenie okresla stawki "
             "MAKSYMALNE; notariusz moze policzyc mniej. Do taksy i wypisow dolicza sie VAT 23 %.",
             "Zmiany od 5.11.2026: testament 50 -> 200 zl netto, testament z zapisem/poleceniem 150 -> 300 zl, "
             "z zapisem windykacyjnym 200 -> 400 zl, odwolanie testamentu 30 -> 50 zl, pelnomocnictwo 30/100 -> 100/200 zl, "
             "oswiadczenie o przyjeciu lub odrzuceniu spadku 50 -> 100 zl, akt poswiadczenia dziedziczenia 50 -> 200 zl, "
             "protokol dziedziczenia 100 -> 200 zl, wypisy 6 zl/strone -> 12 zl (strony 1-10), 10 zl (11-20), 8 zl (od 21), "
             "wniosek o wpis w ksiedze wieczystej 200 -> 300 zl, czynnosc niewymieniona 200 -> 400 zl, "
             "nowy prog dla wartosci powyzej 5 mln zl (14 270 zl + 0,15 %) i limit taksy 10 000 -> 25 000 zl "
             "(w I grupie podatkowej 7500 -> 15 000 zl).",
             "",
             "Stawka od wartosci (§ 3, netto): do 3000 zl - 100 zl; 3000-10 000 - 100 zl + 3 % nadwyzki ponad 3000; "
             "10 000-30 000 - 310 zl + 2 % ponad 10 000; 30 000-60 000 - 710 zl + 1 % ponad 30 000; "
             "60 000-1 000 000 - 1010 zl + 0,4 % ponad 60 000; 1-2 mln - 4770 zl + 0,2 % ponad 1 mln; "
             "2-5 mln - 6770 zl + 0,25 % ponad 2 mln; powyzej 5 mln - 14 270 zl + 0,15 % ponad 5 mln.",
             "Polowa stawki (§ 6): sprzedaz lokalu mieszkalnego, domu jednorodzinnego, dzialki budowlanej, "
             "spoldzielczego wlasnosciowego prawa do lokalu, umowa deweloperska, umowa przedwstepna/warunkowa, "
             "darowizna lokalu w I grupie podatkowej z ulga mieszkaniowa, ustanowienie hipoteki (inne niz ponizej). "
             "Cwierc stawki (§ 7): hipoteka zabezpieczajaca kredyt mieszkaniowy lub na dzialalnosc, projekt aktu.",
             "I grupa podatkowa: malzonek, zstepni, wstepni, rodzenstwo, pasierb, ojczym, macocha, ziec, synowa, tesciowie.",
             "PCC: 2 % wartosci przy sprzedazy z rynku wtornego (placi kupujacy, pobiera notariusz); brak PCC gdy "
             "sprzedaz jest z VAT (np. deweloper); darowizna nie podlega PCC (podlega podatkowi od spadkow i darowizn, "
             "w najblizszej rodzinie z mozliwym zwolnieniem, ktore ocenia notariusz/urzad); hipoteka: 19 zl PCC; "
             "umowa spolki: 0,5 %; odplatna sluzebnosc/uzytkowanie: 1 %.",
             "Oplaty sadowe (ustawa o kosztach sadowych): wpis wlasnosci, hipoteki lub ograniczonego prawa 200 zl; "
             "wpis roszczenia 150 zl; wpis po dziedziczeniu/dziale spadku 150 zl; zalozenie ksiegi wieczystej 100 zl; "
             "wykreslenie hipoteki 100 zl.",
             "Placa minimalna 2026: 4806 zl (1/4 przy przeniesieniu wlasnosci lokalu ze spoldzielni, "
             "1/10 przy oswiadczeniu o poddaniu sie egzekucji przy najmie okazjonalnym).",
             "", "PRZYKLADY POLICZONE PRZEZ KALKULATOR (brutto, stawki maksymalne, domyslnie 6 wypisow po 6 stron):"]
    for p in przyklady_kosztow():
        linie.append(f"- {p['opis']}: razem {zl(p['razem'])}, w tym notariusz (taksa i wypisy z VAT) {zl(p['taksa'])}, "
                     f"podatek PCC {zl(p['pcc'])}, oplaty sadowe {zl(p['sad'])}")
    linie += ["", taksa.opis_dla_modelu(), "", "DOKUMENTY, O KTORE ZWYKLE PROSI KANCELARIA:"]
    grupy: dict[str, list[str]] = {}
    for grupa, nazwa in taksa.DOKUMENTY.values():
        grupy.setdefault(grupa, []).append(nazwa)
    for grupa, nazwy in grupy.items():
        linie.append(f"- {grupa}: " + "; ".join(nazwy))
    return "\n".join(linie)


# ---------------------------------------------------------------- generowanie

def generuj(temat: str, model: str | None = None) -> Path:
    import bedrock
    import prompty
    zadanie = f"TEMAT ARTYKULU: {temat}\n\n{fakty()}"
    odpowiedz = bedrock._rozmowa(prompty.BLOG, [{"text": zadanie}], max_tokenow=8000, myslenie=False, model=model)
    dane = bedrock._wczytaj_json(odpowiedz)
    return zapisz_szkic(dane, temat, model or "domyslny")


def zapisz_szkic(dane: dict, temat: str, model: str = "") -> Path:
    slug = moduł_bazy.slug(str(dane.get("slug") or dane.get("tytul") or temat))[:80]
    if not slug:
        raise ValueError("Brak slugu w odpowiedzi modelu")
    KATALOG_SZKICOW.mkdir(parents=True, exist_ok=True)
    plik = KATALOG_SZKICOW / f"{slug}.md"
    naglowek = {"tytul": str(dane.get("tytul") or temat).strip(), "opis": str(dane.get("opis") or "").strip(),
                "data": date.today().isoformat(), "temat": temat, "model": model}
    tresc = str(dane.get("tresc") or "").strip()
    plik.write_text("---\n" + "".join(f"{k}: {v}\n" for k, v in naglowek.items()) + "---\n\n" + tresc + "\n",
                    encoding="utf-8")
    return plik


def wczytaj_artykul(plik: Path) -> dict:
    tekst = plik.read_text("utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", tekst, re.S)
    if not m:
        raise ValueError(f"{plik}: brak naglowka ---")
    meta = {}
    for linia in m.group(1).splitlines():
        if ":" in linia:
            k, v = linia.split(":", 1)
            meta[k.strip()] = v.strip()
    return {"slug": plik.stem, "tytul": meta.get("tytul", plik.stem), "opis": meta.get("opis", ""),
            "data": meta.get("data", date.today().isoformat()), "temat": meta.get("temat", ""),
            "tresc": m.group(2).strip()}


def _artykuly() -> list[dict]:
    pliki = sorted(KATALOG_ARTYKULOW.glob("*.md"))
    return sorted((wczytaj_artykul(p) for p in pliki), key=lambda a: a["data"], reverse=True)


def strona_artykulu(a: dict, inne: list[dict]) -> str:
    sciezka = f"/blog/{a['slug']}/"
    powiazane = "".join(f'<article><h3><a href="/blog/{esc(i["slug"])}/">{esc(i["tytul"])}</a></h3><p>{esc(i["opis"])}</p></article>'
                        for i in inne[:3])
    jsonld = [
        {"@context": "https://schema.org", "@type": "Article", "headline": a["tytul"], "description": a["opis"],
         "datePublished": a["data"], "dateModified": a["data"], "inLanguage": "pl-PL",
         "mainEntityOfPage": STRONA + sciezka,
         "author": {"@type": "Organization", "name": "notarai", "url": STRONA},
         "publisher": {"@type": "Organization", "name": "notarai", "url": STRONA}},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "notarai", "item": STRONA + "/"},
            {"@type": "ListItem", "position": 2, "name": "Blog", "item": STRONA + "/blog/"},
            {"@type": "ListItem", "position": 3, "name": a["tytul"], "item": STRONA + sciezka}]},
    ]
    tresc = f"""
<section class="hero" style="padding-bottom:20px">
  <div class="szer artykul">
    <p class="okruszki"><a href="/">notarai</a> › <a href="/blog/">Blog</a></p>
    <h1>{esc(a["tytul"])}</h1>
    <p class="meta">{esc(data_pl(a["data"]))} · stawki obowiązujące od 5 listopada 2026 r. · artykuł przygotowany z pomocą AI na podstawie rozporządzenia o taksie notarialnej i kalkulatora notarai, sprawdzony przed publikacją</p>
  </div>
</section>
<section class="sekcja-w">
  <div class="szer artykul">
    {markdown(a["tresc"])}
    <div class="cta-pasek"><p><strong>Policz swoją sprawę.</strong> Kalkulator notarai liczy taksę, PCC i opłaty sądowe według aktualnych stawek i pokazuje, co zabrać do kancelarii.</p><a class="przycisk" href="/kalkulator/">Otwórz kalkulator</a></div>
    <div class="cta-pasek" style="background:var(--tlo2)"><p><strong>Szukasz notariusza?</strong> Wykaz kancelarii w {esc(str(_liczba_miejscowosci()))} miejscowościach z umawianiem wizyty online.</p><a class="przycisk drugi" href="/notariusz/">Znajdź kancelarię</a></div>
    <p class="przypis">Artykuł ma charakter informacyjny i nie jest poradą prawną. Kwoty są szacunkowe, liczone według stawek maksymalnych; ostateczny koszt ustala notariusz.</p>
  </div>
</section>
{f'<section class="sekcja-w tlo2"><div class="szer"><h2>Czytaj też</h2><div class="wpisy">{powiazane}</div></div></section>' if powiazane else ''}
"""
    return szkielet(a["tytul"], a["opis"], tresc, sciezka, jsonld, menu_aktywne="blog")


def _liczba_miejscowosci() -> int:
    try:
        return len(moduł_bazy.wczytaj_json()["miejscowosci"])
    except Exception:  # noqa: BLE001
        return 600


def strona_indeksu(artykuly: list[dict]) -> str:
    wpisy = "".join(
        f'<article><h3><a href="/blog/{esc(a["slug"])}/">{esc(a["tytul"])}</a></h3><p>{esc(a["opis"])}</p>'
        f'<p class="przypis" style="margin-top:8px">{esc(data_pl(a["data"]))}</p></article>' for a in artykuly)
    tytul = "Blog notarai: koszty u notariusza, dokumenty, taksa 2026"
    opis = ("Praktyczne odpowiedzi dla klientów kancelarii notarialnych: ile kosztuje akt, testament, darowizna, "
            "co zabrać do notariusza, jak zmieniła się taksa od 5 listopada 2026 r.")
    tresc = f"""
<section class="hero" style="padding-bottom:20px">
  <div class="szer">
    <p class="okruszki"><a href="/">notarai</a> › Blog</p>
    <h1>Blog notarai: <em>ile kosztuje notariusz</em> i co przygotować</h1>
    <p class="wstep">Odpowiedzi na pytania, z którymi klienci przychodzą do kancelarii. Kwoty liczone kalkulatorem notarai według stawek obowiązujących od 5 listopada 2026 r.</p>
  </div>
</section>
<section class="sekcja-w">
  <div class="szer">
    <div class="wpisy">{wpisy or '<p class="wstep">Pierwsze artykuły już wkrótce.</p>'}</div>
    <div class="cta-pasek"><p><strong>Policz swoją sprawę.</strong> Opisz ją zwykłym językiem, a kalkulator poda taksę, podatek i opłaty sądowe.</p><a class="przycisk" href="/kalkulator/">Otwórz kalkulator</a></div>
  </div>
</section>
"""
    return szkielet(tytul, opis, tresc, "/blog/", menu_aktywne="blog")


def zbuduj(cel: Path = KATALOG_STRONY) -> int:
    artykuly = _artykuly()
    katalog = cel / "blog"
    katalog.mkdir(parents=True, exist_ok=True)
    for a in artykuly:
        inne = [i for i in artykuly if i["slug"] != a["slug"]]
        (katalog / a["slug"]).mkdir(exist_ok=True)
        (katalog / a["slug"] / "index.html").write_text(strona_artykulu(a, inne), encoding="utf-8")
    (katalog / "index.html").write_text(strona_indeksu(artykuly), encoding="utf-8")
    return len(artykuly)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    polecenie = argv[1]
    model = None
    if "--model" in argv:
        model = argv[argv.index("--model") + 1]
    if polecenie == "fakty":
        print(fakty())
    elif polecenie == "generuj":
        print(generuj(argv[2], model))
    elif polecenie == "tematy":
        istniejace = {p.stem for p in list(KATALOG_ARTYKULOW.glob("*.md")) + list(KATALOG_SZKICOW.glob("*.md"))}
        gotowe = {wczytaj_artykul(p)["temat"] for p in list(KATALOG_ARTYKULOW.glob("*.md")) + list(KATALOG_SZKICOW.glob("*.md"))}
        for temat in PLIK_TEMATOW.read_text("utf-8").splitlines():
            temat = temat.strip()
            if temat and temat not in gotowe and moduł_bazy.slug(temat)[:80] not in istniejace:
                print("piszę:", temat)
                print("  ->", generuj(temat, model))
    elif polecenie == "zbuduj":
        print(f"artykuły: {zbuduj()}")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
