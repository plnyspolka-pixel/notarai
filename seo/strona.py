"""Wspolne kawalki stron notarai.pl generowanych z kodu: szkielet HTML,
przyklady kosztow z taksa.py, prosty Markdown -> HTML (blog).

Strony lacza /style.css z glownej witryny, zeby wygladac jak reszta.
"""
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KORZEN))

import taksa  # noqa: E402

STRONA = "https://notarai.pl"
APLIKACJA = "https://app.notarai.pl"
KATALOG_STRONY = KORZEN / "strona"


def esc(tekst) -> str:
    return html.escape(str(tekst if tekst is not None else ""), quote=True)


def odmiana(n: int, jeden: str, kilka: str, wiele: str) -> str:
    """1 kancelaria, 2-4 kancelarie, 5+ kancelarii (z regula dla 12-14, 22-24...)."""
    if n == 1:
        return f"{n} {jeden}"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} {kilka}"
    return f"{n} {wiele}"


def zl(x) -> str:
    return taksa.zl(x).replace(" ", " ")


def szkielet(tytul: str, opis: str, tresc: str, sciezka: str, jsonld: list | None = None,
             css: str = "", menu_aktywne: str = "") -> str:
    """Pelna strona HTML w ukladzie notarai.pl. `sciezka` to adres wzgledny ("/notariusz/lublin/")."""
    kanoniczny = STRONA + sciezka
    skrypty = "".join(
        f'<script type="application/ld+json">{json.dumps(d, ensure_ascii=False)}</script>\n'
        for d in (jsonld or []))
    return f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(tytul)}</title>
<meta name="description" content="{esc(opis)}">
<link rel="canonical" href="{esc(kanoniczny)}">
<meta property="og:title" content="{esc(tytul)}">
<meta property="og:description" content="{esc(opis)}">
<meta property="og:url" content="{esc(kanoniczny)}">
<meta property="og:type" content="website">
<meta property="og:locale" content="pl_PL">
<link rel="icon" type="image/svg+xml" href="/logo-mark.svg">
<link rel="stylesheet" href="/style.css">
<style>
/* Tokeny marki NotarAI wspolne z witryna i kalkulatorem. */
:root {{ --tlo:#f6f9ff; --tlo2:#edf4ff; --karta:#fff; --linia:#d8e5f6;
  --tekst:#102a58; --tekst2:#566b8c; --tekst3:#8497af;
  --akcent:#1e5cc3; --akcent2:#079bd1; --akcent-tlo:#e9f3ff;
  --serif:Montserrat,"Segoe UI",Arial,sans-serif;
  --sans:Montserrat,"Segoe UI",Arial,sans-serif; color-scheme:light; }}
body {{background:linear-gradient(165deg,#f7fbff,#fff 60%,#edf5ff);color:var(--tekst);}}
.naglowek {{ background:rgba(255,255,255,.97);border-bottom:1px solid #d8e7f7; }}
.naglowek .marka {{color:#0a2758;font-weight:800;letter-spacing:-.045em;}}
.naglowek .marka strong {{color:#0b9bd6;}}
.hero {{ background:radial-gradient(circle at 82% 12%,#dcecff,#f8fbff 70%); }}
.hero h1 {{font-weight:800;letter-spacing:-.035em;}}
.kanc article, .wpisy article {{box-shadow:0 12px 35px -29px rgba(13,61,129,.22);border-color:#d9e6f5;}}
.przycisk {{background:linear-gradient(110deg,#293cb8,#138ac9);border:0;color:#fff;}}
.przycisk.drugi {{background:#fff;color:#255bb6;border:1px solid #c7dff7;}}
.okruszki {{ font-size: .88rem; color: var(--tekst3); margin: 20px 0 0; }}
.okruszki a {{ color: var(--tekst3); }}
.sekcja-w {{ padding: 44px 0; border-top: 1px solid var(--linia); }}
.sekcja-w h2 {{ font-size: clamp(1.4rem, 2.6vw, 1.8rem); }}
.kanc {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-top: 20px; }}
.kanc article {{ background: var(--karta); border: 1px solid var(--linia); border-radius: var(--r); padding: 18px 20px; display: flex; flex-direction: column; gap: 6px; }}
.kanc h3 {{ margin: 0; font-size: 1.05rem; }}
.kanc p {{ margin: 0; color: var(--tekst2); font-size: .95rem; }}
.kanc .tel a {{ color: var(--tekst); text-decoration: none; font-weight: 600; }}
.kanc .akcje {{ margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
.kanc .przycisk {{ padding: 8px 14px; font-size: .92rem; }}
.kanc .brak {{ color: var(--tekst3); font-size: .88rem; }}
.kanc article.klient {{ border-color: var(--akcent); }}
.tabela-k {{ overflow-x: auto; margin: 18px 0; border: 1px solid var(--linia); border-radius: 10px; background: var(--karta); }}
.tabela-k table {{ border-collapse: collapse; width: 100%; font-size: .95rem; }}
.tabela-k th, .tabela-k td {{ text-align: left; padding: 10px 14px; border-bottom: 1px solid var(--linia); vertical-align: top; }}
.tabela-k th {{ background: var(--tlo2); font-weight: 600; }}
.tabela-k td:last-child, .tabela-k th:last-child {{ text-align: right; white-space: nowrap; }}
.tabela-k tr:last-child td {{ border-bottom: 0; }}
.faq details {{ border-bottom: 1px solid var(--linia); padding: 12px 0; }}
.faq summary {{ cursor: pointer; font-weight: 600; }}
.faq p {{ margin: 8px 0 0; color: var(--tekst2); }}
.okolice {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }}
.okolice a {{ background: var(--karta); border: 1px solid var(--linia); border-radius: 999px; padding: 6px 12px; font-size: .9rem; text-decoration: none; color: var(--tekst); }}
.okolice a:hover {{ border-color: var(--akcent); color: var(--akcent); }}
.kroki-u {{ counter-reset: k; list-style: none; padding: 0; margin: 18px 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
.kroki-u li {{ background: var(--karta); border: 1px solid var(--linia); border-radius: var(--r); padding: 18px; color: var(--tekst2); font-size: .95rem; }}
.kroki-u li b {{ display: block; color: var(--tekst); margin-bottom: 4px; }}
.kroki-u li::before {{ counter-increment: k; content: counter(k); display: inline-grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--akcent-tlo); color: var(--akcent); font-weight: 700; margin-bottom: 8px; }}
dialog.umow {{ border: 1px solid var(--linia); border-radius: var(--r); background: var(--karta); color: var(--tekst); width: min(560px, 94vw); padding: 24px; }}
dialog.umow::backdrop {{ background: rgba(0,0,0,.4); }}
dialog.umow h2 {{ margin: 0 0 6px; font-size: 1.3rem; }}
dialog.umow label {{ display: block; font-size: .9rem; color: var(--tekst2); margin: 12px 0 0; }}
dialog.umow label span {{ display: block; margin-bottom: 4px; }}
dialog.umow input, dialog.umow select, dialog.umow textarea {{ width: 100%; padding: 9px 11px; border: 1px solid var(--linia2, var(--linia)); border-radius: 8px; background: var(--tlo); color: var(--tekst); font: inherit; font-size: .95rem; }}
dialog.umow .chk {{ display: flex; gap: 8px; align-items: flex-start; color: var(--tekst); margin-top: 14px; }}
dialog.umow .chk input {{ width: auto; margin-top: 4px; }}
dialog.umow .dwie {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
dialog.umow .akcje {{ display: flex; gap: 10px; margin-top: 18px; flex-wrap: wrap; }}
dialog.umow .wynik {{ margin-top: 12px; padding: 12px 14px; border-radius: 10px; background: var(--ok-tlo, #eaf3ec); color: var(--tekst); }}
dialog.umow .wynik.blad {{ background: var(--alarm-tlo, #fbeceb); }}
.pulapka {{ position: absolute; left: -9999px; width: 1px; height: 1px; opacity: 0; }}
.szukaj-m {{ width: 100%; max-width: 480px; padding: 12px 14px; border: 1px solid var(--linia); border-radius: 10px; font: inherit; background: var(--karta); color: var(--tekst); margin: 18px 0; }}
.izba {{ margin-top: 28px; }}
.izba h3 {{ margin-bottom: 8px; }}
.miasta {{ display: flex; flex-wrap: wrap; gap: 8px 10px; }}
.miasta a {{ text-decoration: none; color: var(--tekst); font-size: .95rem; }}
.miasta a small {{ color: var(--tekst3); }}
.artykul {{ max-width: 760px; }}
.artykul h2 {{ margin-top: 1.8em; font-size: 1.5rem; }}
.artykul h3 {{ margin-top: 1.4em; }}
.artykul p, .artykul li {{ color: var(--tekst2); font-size: 1.05rem; line-height: 1.65; }}
.artykul strong {{ color: var(--tekst); }}
.artykul blockquote {{ margin: 0 0 1em; padding: 12px 18px; border-left: 3px solid var(--akcent); color: var(--tekst2); }}
.artykul .meta {{ color: var(--tekst3); font-size: .9rem; }}
.wpisy {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; margin-top: 24px; }}
.wpisy article {{ background: var(--karta); border: 1px solid var(--linia); border-radius: var(--r); padding: 22px; }}
.wpisy h3 {{ margin: 0 0 8px; }}
.wpisy h3 a {{ color: var(--tekst); text-decoration: none; }}
.wpisy p {{ color: var(--tekst2); margin: 0; font-size: .95rem; }}
.cta-pasek {{ background: var(--akcent-tlo); border-radius: var(--r); padding: 22px 26px; margin: 28px 0 0; display: flex; gap: 16px; align-items: center; justify-content: space-between; flex-wrap: wrap; }}
.cta-pasek p {{ margin: 0; max-width: 620px; }}
@media (max-width: 760px) {{ .kanc, .kroki-u, .wpisy {{ grid-template-columns: 1fr; }} dialog.umow .dwie {{ grid-template-columns: 1fr; }} }}
{css}
</style>
</head>
<body>

<header class="naglowek">
  <div class="szer naglowek-w">
    <a class="marka" href="/"><img src="/logo-mark.svg" alt="" width="32" height="32"><span>notar<strong>ai</strong></span></a>
    <nav class="menu" aria-label="Sekcje strony">
      <a href="/notariusz/"{' aria-current="page"' if menu_aktywne == "notariusz" else ""}>Notariusze</a>
      <a href="/kalkulator/">Kalkulator kosztów</a>
      <a href="/blog/"{' aria-current="page"' if menu_aktywne == "blog" else ""}>Blog</a>
      <a href="/#cennik">Dla kancelarii</a>
    </nav>
    <a class="przycisk maly" href="{APLIKACJA}">Zaloguj się</a>
  </div>
</header>

<main>
{tresc}
</main>

<footer class="stopka">
  <div class="szer stopka-w">
    <p>notarai.pl prowadzi Fundacja Krzewienia Edukacji Finansowej im. Pieczaka, ul.&nbsp;Wilhelma Orlika Ruckemana 4/18, 20-244 Lublin, KRS 0001140846, NIP 9462747637. Wykaz kancelarii: dane.gov.pl i izby notarialne, stan na 31.12.2025. Kwoty szacunkowe według stawek maksymalnych; nie stanowią porady prawnej ani oferty.</p>
    <p><a href="/kalkulator/">Kalkulator kosztów</a> · <a href="/notariusz/">Notariusze</a> · <a href="/blog/">Blog</a> · <a href="/regulamin/">Regulamin</a> · <a href="/prywatnosc/">Polityka prywatności</a> · <a href="mailto:kontakt@notarai.pl">kontakt@notarai.pl</a></p>
  </div>
</footer>
{skrypty}</body>
</html>
"""


# ---------------------------------------------------------------- przyklady kosztow

PRZYKLADY = [
    ("Zakup mieszkania za 400 000 zł z rynku wtórnego, kredyt 300 000 zł",
     {"czynnosci": [{"rodzaj": "sprzedaz_lokalu", "wartosc": 400000, "opis": "zakup mieszkania"}],
      "hipoteka": {"kwota": 300000, "kredyt_mieszkaniowy": True}}),
    ("Zakup domu za 800 000 zł bez kredytu",
     {"czynnosci": [{"rodzaj": "sprzedaz_domu", "wartosc": 800000, "opis": "zakup domu"}]}),
    ("Darowizna mieszkania o wartości 350 000 zł od rodziców",
     {"czynnosci": [{"rodzaj": "darowizna_lokalu_grupa1", "wartosc": 350000, "opis": "darowizna mieszkania"}], "grupa1": True}),
    ("Zakup działki budowlanej za 150 000 zł",
     {"czynnosci": [{"rodzaj": "sprzedaz_dzialki_budowlanej", "wartosc": 150000, "opis": "zakup działki"}]}),
    ("Testament (1 wypis)", {"stale": [{"id": "testament", "wypisy": 1, "strony": 2}]}),
    ("Pełnomocnictwo do jednej czynności (1 wypis)", {"stale": [{"id": "pelnomocnictwo_jedna", "wypisy": 1, "strony": 2}]}),
    ("Akt poświadczenia dziedziczenia z protokołem (2 wypisy)",
     {"stale": [{"id": "protokol_dziedziczenia", "wypisy": 0}, {"id": "apd", "wypisy": 2, "strony": 3}]}),
]


def przyklady_kosztow() -> list[dict]:
    """[{opis, razem, taksa, pcc, sad}] - policzone przez taksa.py na dzis."""
    wynik = []
    for opis, parametry in PRZYKLADY:
        w = taksa.oblicz(parametry)
        wynik.append({"opis": opis, "razem": w["razem"], "taksa": w["sumy"]["taksa_brutto"] + w["sumy"]["wypisy"],
                      "pcc": w["sumy"]["pcc"], "sad": w["sumy"]["sad"], "tekst": w["tekst"]})
    return wynik


def tabela_kosztow(przyklady: list[dict]) -> str:
    wiersze = "".join(
        f"<tr><td>{esc(p['opis'])}</td><td>{esc(zl(p['taksa']))}</td><td>{esc(zl(p['pcc'] + p['sad']))}</td>"
        f"<td><b>{esc(zl(p['razem']))}</b></td></tr>" for p in przyklady)
    return (f'<div class="tabela-k"><table><thead><tr><th>Czynność</th><th>Notariusz (taksa i wypisy, z VAT)</th>'
            f'<th>Podatek i sąd</th><th>Razem</th></tr></thead><tbody>{wiersze}</tbody></table></div>')


def stawki_etykieta() -> str:
    return taksa.tabela()["etykieta"]


# ---------------------------------------------------------------- Markdown (blog)

_INLINE = [
    (re.compile(r"\*\*(.+?)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)"), r"<em>\1</em>"),
    (re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+|/[^\s)]*)\)"), r'<a href="\2">\1</a>'),
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
]


def _inline(tekst: str) -> str:
    tekst = esc(tekst)
    for wzor, zamiana in _INLINE:
        tekst = wzor.sub(zamiana, tekst)
    return tekst


def markdown(tekst: str) -> str:
    """Podzbior Markdown wystarczajacy na artykul: naglowki, akapity, listy,
    cytaty, tabele, pogrubienie, kursywa, odnosniki."""
    linie = tekst.replace("\r\n", "\n").split("\n")
    wynik: list[str] = []
    akapit: list[str] = []
    lista: str | None = None
    tabela: list[list[str]] = []

    def zamknij():
        nonlocal akapit, lista, tabela
        if akapit:
            wynik.append(f"<p>{_inline(' '.join(akapit))}</p>")
            akapit = []
        if lista:
            wynik.append(f"</{lista}>")
            lista = None
        if tabela:
            naglowek, *reszta = tabela
            wynik.append('<div class="tabela-k"><table><thead><tr>' + "".join(f"<th>{_inline(k)}</th>" for k in naglowek)
                         + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{_inline(k)}</td>" for k in w) + "</tr>" for w in reszta)
                         + "</tbody></table></div>")
            tabela = []

    for linia in linie:
        s = linia.strip()
        if not s:
            zamknij()
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            zamknij()
            poziom = min(len(m.group(1)) + 0, 4)
            wynik.append(f"<h{poziom}>{_inline(m.group(2))}</h{poziom}>")
            continue
        if s.startswith("|"):
            komorki = [k.strip() for k in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", k) for k in komorki):
                continue
            if akapit or lista:
                zamknij()
            tabela.append(komorki)
            continue
        elif tabela:
            zamknij()
        m = re.match(r"^(?:[-*•]|\d+[.)])\s+(.*)$", s)
        if m:
            rodzaj = "ol" if s[0].isdigit() else "ul"
            if akapit:
                zamknij()
            if lista != rodzaj:
                if lista:
                    wynik.append(f"</{lista}>")
                wynik.append(f"<{rodzaj}>")
                lista = rodzaj
            wynik.append(f"<li>{_inline(m.group(1))}</li>")
            continue
        if s.startswith(">"):
            zamknij()
            wynik.append(f"<blockquote>{_inline(s.lstrip('> '))}</blockquote>")
            continue
        if lista and not akapit:
            zamknij()
        akapit.append(s)
    zamknij()
    return "\n".join(wynik)


def data_pl(iso: str) -> str:
    miesiace = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
                "września", "października", "listopada", "grudnia"]
    try:
        d = date.fromisoformat(iso[:10])
    except ValueError:
        return iso
    return f"{d.day} {miesiace[d.month - 1]} {d.year}"
