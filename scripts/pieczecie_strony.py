#!/usr/bin/env python3
"""Generator pieczęci SVG strony notarai.pl (strona/index.html).

Uruchom po zmianie list SCIANA, ZGODNOSC lub PASEK:
    python scripts/pieczecie_strony.py strona/index.html

Pieczęcie są własnym projektem, nie oryginalnymi znakami ISO/AICPA/BSI/CSA:
certyfikaty posiada dostawca infrastruktury, a ich znaków nie wolno używać
jako własnych. Dolny napis każdej pieczęci mówi, czyje to jest.
"""
import math, re, sys

R = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")

# Rodziny: tło pasma (ciemne -> jasne), tarcza, metal
RODZINY = {
    "iso":  dict(b1="#06153a", b2="#173f97", t1="#0b2463", t2="#1e4fb8", m=("#fff3b0", "#e2b93b", "#8c6510")),
    "soc":  dict(b1="#14181f", b2="#3b4558", t1="#1f2633", t2="#4a566d", m=("#ffffff", "#c9d2df", "#6c7889")),
    "c5":   dict(b1="#2a0408", b2="#8f1520", t1="#4a0a10", t2="#b21f2b", m=("#fff3b0", "#e2b93b", "#8c6510")),
    "csa":  dict(b1="#03282d", b2="#0f6c75", t1="#06404a", t2="#13909b", m=("#ffffff", "#bfe3e6", "#5f8a8f")),
    "eu":   dict(b1="#001a5c", b2="#003399", t1="#00267a", t2="#0a49c4", m=("#fff3b0", "#ffcc00", "#9c7a00")),
}


def gwiazda(cx, cy, r):
    pkt = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * .42
        pkt.append(f"{R(cx + rr * math.cos(a))},{R(cy + rr * math.sin(a))}")
    return "M" + "L".join(pkt) + "Z"


def sprite():
    zeby = 72
    p = []
    for i in range(zeby * 2):
        a = i * math.pi / zeby
        r = 99 if i % 2 == 0 else 94.5
        p.append(f"{R(r * math.cos(a))},{R(r * math.sin(a))}")
    brzeg = "M" + "L".join(p) + "Z"
    gil = "".join(
        f'<ellipse rx="57" ry="19" transform="rotate({R(i * 7.5)})"/>' for i in range(24)
    ) + "".join(
        f'<ellipse rx="38" ry="11" transform="rotate({R(i * 15 + 7.5)})"/>' for i in range(12)
    )
    gwiazdy = "".join(
        f'<path d="{gwiazda(53 * math.cos(math.radians(i * 30 - 90)), 53 * math.sin(math.radians(i * 30 - 90)), 3.7)}"/>'
        for i in range(12)
    )
    gr = []
    for k, c in RODZINY.items():
        gr.append(
            f'<linearGradient id="ps-b-{k}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c["b2"]}"/><stop offset="1" stop-color="{c["b1"]}"/></linearGradient>'
            f'<radialGradient id="ps-t-{k}" cx=".38" cy=".3" r=".85"><stop offset="0" stop-color="{c["t2"]}"/><stop offset="1" stop-color="{c["t1"]}"/></radialGradient>'
            f'<linearGradient id="ps-m-{k}" x1="0" y1="0" x2=".9" y2="1"><stop offset="0" stop-color="{c["m"][0]}"/><stop offset=".45" stop-color="{c["m"][1]}"/><stop offset=".75" stop-color="{c["m"][2]}"/><stop offset="1" stop-color="{c["m"][1]}"/></linearGradient>'
        )
    return (
        '<svg class="nx-seal-defs" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false"><defs>'
        + "".join(gr)
        + '<radialGradient id="ps-blask" cx=".3" cy=".22" r=".7"><stop offset="0" stop-color="#fff" stop-opacity=".38"/><stop offset=".55" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        + f'<path id="ps-brzeg" d="{brzeg}"/>'
        + f'<g id="ps-gilosz" fill="none" stroke-width=".55">{gil}</g>'
        + f'<g id="ps-gwiazdy">{gwiazdy}</g>'
        + '<path id="ps-luk-g" d="M-69,0A69,69 0 0 1 69,0"/>'
        + '<path id="ps-luk-d" d="M-78.5,0A78.5,78.5 0 0 0 78.5,0"/>'
        + '<clipPath id="ps-tarcza-clip"><circle r="60"/></clipPath>'
        + '<path id="pt-wstega" d="M18,170.5Q80,178.5 142,170.5" fill="none"/>'
        + f'<clipPath id="pt-clip"><path d="{ksztalt(.9)}"/></clipPath>'
        + '<linearGradient id="pt-zloto" x1="0" y1="0" x2=".85" y2="1"><stop offset="0" stop-color="#fff7cf"/><stop offset=".18" stop-color="#f3d466"/><stop offset=".38" stop-color="#b98a2b"/><stop offset=".52" stop-color="#7c5413"/><stop offset=".68" stop-color="#e2bb52"/><stop offset=".84" stop-color="#fff0ad"/><stop offset="1" stop-color="#a7771f"/></linearGradient>'
        + '<radialGradient id="pt-kopula" cx=".42" cy=".34" r=".78"><stop offset="0" stop-color="#ffffff"/><stop offset=".45" stop-color="#f3f7fd"/><stop offset=".8" stop-color="#dbe5f4"/><stop offset="1" stop-color="#bccbe4"/></radialGradient>'
        + '<linearGradient id="pt-glowica" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2d5fd8"/><stop offset=".5" stop-color="#0b3aa8"/><stop offset="1" stop-color="#061f66"/></linearGradient>'
        + '<linearGradient id="pt-wstega-g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2f62d8"/><stop offset=".3" stop-color="#0d3aa4"/><stop offset=".75" stop-color="#062474"/><stop offset="1" stop-color="#020f3d"/></linearGradient>'
        + '<linearGradient id="pt-pas" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".75"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        # relief metalu: rozproszone światło (cień na zboczach) + odbłysk z lewej góry
        + '<filter id="pt-relief" x="-15%" y="-15%" width="130%" height="130%" color-interpolation-filters="sRGB">'
          '<feGaussianBlur in="SourceAlpha" stdDeviation="1.3" result="b"/>'
          '<feDiffuseLighting in="b" surfaceScale="3" diffuseConstant="1.15" lighting-color="#fff" result="d"><feDistantLight azimuth="225" elevation="48"/></feDiffuseLighting>'
          '<feComposite in="SourceGraphic" in2="d" operator="arithmetic" k1="1.1" k2="0" k3="0" k4="0" result="lit"/>'
          '<feSpecularLighting in="b" surfaceScale="3.5" specularConstant="1.2" specularExponent="20" lighting-color="#fff" result="s"><feDistantLight azimuth="225" elevation="40"/></feSpecularLighting>'
          '<feComposite in="s" in2="SourceAlpha" operator="in" result="s2"/>'
          '<feComposite in="lit" in2="s2" operator="arithmetic" k1="0" k2="1" k3=".9" k4="0"/></filter>'
        # drobny relief dla gwiazd i liści
        + '<filter id="pt-relief-maly" x="-30%" y="-30%" width="160%" height="160%" color-interpolation-filters="sRGB">'
          '<feGaussianBlur in="SourceAlpha" stdDeviation=".55" result="b"/>'
          '<feSpecularLighting in="b" surfaceScale="2" specularConstant="1.1" specularExponent="16" lighting-color="#fff" result="s"><feDistantLight azimuth="225" elevation="42"/></feSpecularLighting>'
          '<feComposite in="s" in2="SourceAlpha" operator="in" result="s2"/>'
          '<feComposite in="SourceGraphic" in2="s2" operator="arithmetic" k1="0" k2="1" k3=".8" k4="0" result="j"/>'
          '<feDropShadow in="j" dx=".35" dy=".6" stdDeviation=".35" flood-color="#2a1a00" flood-opacity=".55"/></filter>'
        # napis wytłoczony w emalii: ciemna krawędź u góry, jasna u dołu
        + '<filter id="pt-wytlocz" x="-10%" y="-30%" width="120%" height="160%">'
          '<feDropShadow dx="0" dy=".7" stdDeviation=".15" flood-color="#fff" flood-opacity=".95" result="j"/>'
          '<feDropShadow in="j" dx="0" dy="-.45" stdDeviation=".25" flood-color="#000a2e" flood-opacity=".45"/></filter>'
        # wewnętrzny cień kopuły emalii
        + '<filter id="pt-cien-wew" x="-5%" y="-5%" width="110%" height="110%"><feGaussianBlur stdDeviation="3.2"/></filter>'
        + '<filter id="pt-cien-tekstu" x="-10%" y="-40%" width="120%" height="180%"><feDropShadow dx="0" dy=".8" stdDeviation=".5" flood-color="#000820" flood-opacity=".7"/></filter>'
        + '<linearGradient id="pt-emalia" x1="0" y1="0" x2=".4" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".6" stop-color="#f1f5fc"/><stop offset="1" stop-color="#dfe8f6"/></linearGradient>'
        + '<linearGradient id="pt-blask" x1="0" y1="0" x2="1" y2=".9"><stop offset="0" stop-color="#fff" stop-opacity=".5"/><stop offset=".35" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        + '<g id="pt-grawer" fill="none" stroke-width=".4">' + "".join(
            f'<ellipse cx="80" cy="99" rx="{R(30 + i * 5)}" ry="{R(30 + i * 5)}"/>' for i in range(14)) + "".join(
            f'<path d="M80,99L{R(80 + 120 * math.cos(math.radians(i * 7.5)))},{R(99 + 120 * math.sin(math.radians(i * 7.5)))}"/>' for i in range(48)) + '</g>'
        + "</defs></svg>"
    )


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;")


def rozmiar_luku(tekst, dl):
    # szerokość znaku wersalikiem ~0.72em + odstęp 1.6
    # łuk 180 stopni; tekst zajmuje najwyżej ~150, żeby nie wejść na gwiazdki
    return min(11.5, dl * 0.76 / (len(tekst) * 0.86))


def pieczec(rod, gora, dol, maly, duzy, opis, etykieta, gwiazdy=False):
    m = f"url(#ps-m-{rod})"
    fg = R(rozmiar_luku(gora, 217))
    fd = R(rozmiar_luku(dol, 247)) if dol else 0
    if gwiazdy:
        fs = 24 if len(duzy) <= 4 else 17
        y_duzy = 5
    else:
        fs = 30 if len(duzy) <= 4 else (26 if len(duzy) == 5 else 20)
        y_duzy = 8
    srodek = []
    if maly:
        srodek.append(f'<text class="ps-maly" y="-17" fill="{m}">{esc(maly)}</text>')
    srodek.append(f'<text class="ps-duzy" y="{y_duzy}" font-size="{fs}">{esc(duzy)}</text>')
    if opis:
        srodek.append(f'<text class="ps-opis" y="{20 if gwiazdy else 24}"' + (' font-size="6"' if gwiazdy else '') + f'>{esc(opis)}</text>')
    dolny = (f'<text class="ps-luk" font-size="{fd}" fill="{m}"><textPath href="#ps-luk-d" startOffset="50%">{esc(dol)}</textPath></text>'
             if dol else "")
    linia = '' if gwiazdy else f'<circle r="54" fill="none" stroke="{m}" stroke-width=".6" opacity=".7"/>'
    gw = f'<use href="#ps-gwiazdy" fill="{m}" opacity=".95"/>' if gwiazdy else ""
    return (
        f'<svg class="nx-pieczec nx-pieczec--{rod}" viewBox="-100 -100 200 200" role="img" aria-label="{esc(etykieta)}">'
        f'<use href="#ps-brzeg" fill="{m}"/>'
        f'<circle r="91" fill="url(#ps-b-{rod})"/>'
        f'<circle r="88" fill="none" stroke="{m}" stroke-width="1.3"/>'
        f'<circle r="86" fill="none" stroke="{m}" stroke-width=".5" stroke-dasharray="1.2 2.2"/>'
        f'<text class="ps-luk" font-size="{fg}" fill="{m}"><textPath href="#ps-luk-g" startOffset="50%">{esc(gora)}</textPath></text>'
        f'{dolny}'
        f'<path d="{gwiazda(-75, 0, 4.2)}" fill="{m}"/><path d="{gwiazda(75, 0, 4.2)}" fill="{m}"/>'
        f'<circle r="62.5" fill="{m}"/>'
        f'<circle r="60" fill="url(#ps-t-{rod})"/>'
        f'<g clip-path="url(#ps-tarcza-clip)" stroke="{m}" opacity=".33"><use href="#ps-gilosz"/></g>'
        f'{linia}'
        f'{gw}'
        f'<g class="ps-srodek">{"".join(srodek)}</g>'
        f'<circle r="91" fill="url(#ps-blask)"/>'
        "</svg>"
    )


def mini(rod, znak, etykieta=""):
    m = f"url(#ps-m-{rod})"
    fs = 64 if len(znak) <= 2 else (50 if len(znak) == 3 else 40)
    return (
        f'<svg class="nx-mini" viewBox="-100 -100 200 200" aria-hidden="true">'
        f'<use href="#ps-brzeg" fill="{m}"/>'
        f'<circle r="88" fill="url(#ps-b-{rod})"/>'
        f'<circle r="74" fill="{m}"/><circle r="69" fill="url(#ps-t-{rod})"/>'
        f'<text class="ps-duzy" y="{R(fs * .36)}" font-size="{fs}" fill="{m}">{esc(znak)}</text>'
        f'<circle r="88" fill="url(#ps-blask)"/></svg>'
    )


DOL_CERT = "DOSTAWCA INFRASTRUKTURY"
SCIANA = [
    ("iso", "INFORMATION SECURITY", "ISO/IEC", "27001", "bezpieczeństwo informacji"),
    ("iso", "CLOUD SECURITY", "ISO/IEC", "27017", "bezpieczeństwo chmury"),
    ("iso", "PII IN THE CLOUD", "ISO/IEC", "27018", "dane osobowe w chmurze"),
    ("iso", "PRIVACY MANAGEMENT", "ISO/IEC", "27701", "zarządzanie prywatnością"),
    ("iso", "QUALITY MANAGEMENT", "ISO", "9001", "jakość"),
    ("iso", "BUSINESS CONTINUITY", "ISO", "22301", "ciągłość działania"),
    ("soc", "TRUST SERVICES · TYPE II", "AICPA", "SOC 2", "raport audytowy"),
    ("c5", "CLOUD COMPLIANCE", "BSI", "C5", "katalog chmury, Niemcy"),
    ("csa", "SECURITY TRUST ASSURANCE", "CSA", "STAR", "rejestr bezpieczeństwa"),
    ("eu", "DATA PROTECTION CODE", "CISPE", "GDPR", "kodeks ochrony danych"),
]
# Zgodność z prawem: celowo INNY język wizualny niż pieczęcie certyfikatów
# (jasna płaska tarcza herbowa zamiast okrągłej metalowej pieczęci), żeby
# zobowiązań notarai nie dało się pomylić z certyfikatami dostawcy.
ZGODNOSC = [
    # (tytuł w głowicy, duży napis, akt prawny drobnym drukiem, opis, podpis pod tarczą: nagłówek, zdanie)
    ("OCHRONA DANYCH|OSOBOWYCH", "RODO", "rozporządzenie (UE) 2016/679", "art. 22 · 28 · 32 RODO",
     "RODO bez papierologii", "Umowa powierzenia, rejestr czynności i klauzula informacyjna gotowe w aplikacji."),
    ("AKT O SZTUCZNEJ|INTELIGENCJI", "AI ACT", "rozporządzenie (UE) 2024/1689", "nadzór człowieka",
     "AI pod kontrolą notariusza", "Instrukcja AI dla całego zespołu. Każdą decyzję podejmuje notariusz."),
    ("OCENA SKUTKÓW|DLA DANYCH", "DPIA", "art. 35 RODO", "gotowa w aplikacji",
     "Ocena skutków w 1 klik", "Wypełniona danymi kancelarii. Przyjmujesz ją jednym kliknięciem."),
    ("UMOWA|POWIERZENIA", "ART. 28", "RODO", "przy rejestracji",
     "Umowa powierzenia od ręki", "Zawierasz ją przy rejestracji, bez podpisów i wysyłania dokumentów."),
    ("TAJEMNICA|NOTARIALNA", "ART. 18", "ustawy Prawo o notariacie", "chroniona algorytmicznie",
     "Tajemnica nienaruszona", "Treść spraw czyta wyłącznie algorytm. Żaden człowiek nie ma wglądu."),
    ("PRZETWARZANIE|TYLKO W UE", "EU", "rozdział V RODO", "Frankfurt · Irlandia · Paryż",
     "Dane nie wyjeżdżają z Unii", "Pliki i model AI wyłącznie w regionach UE. Spoza UE aplikacja nie ruszy."),
]

# Kształt tarczy: lekko wcięta góra, ostro zakończony dół. Liczby to pary x,y.
_TARCZA = [("M", 80, 6), ("C", 102, 15, 128, 16, 150, 13), ("V", 94),
           ("C", 150, 140, 121, 171, 80, 190), ("C", 39, 171, 10, 140, 10, 94),
           ("V", 13), ("C", 32, 16, 58, 15, 80, 6)]


def ksztalt(skala):
    """Tarcza przeskalowana względem środka (80,100) - kolejne warstwy obwódki."""
    out = []
    for cmd, *liczby in _TARCZA:
        if cmd == "V":
            out.append(f"V{R((liczby[0] - 100) * skala + 100)}")
            continue
        pary = [f"{R((liczby[i] - 80) * skala + 80)},{R((liczby[i + 1] - 100) * skala + 100)}"
                for i in range(0, len(liczby), 2)]
        out.append(cmd + " ".join(pary))
    return "".join(out) + "Z"


def laur(strona):
    """Złota gałązka laurowa wzdłuż boku tarczy (strona -1 lewa, 1 prawa).

    Łuk liczony dla lewej strony (kąt 90 = dół, 180 = lewo), prawą odbijamy lustrzanie.
    """
    cx, cy, r = 80, 104, 94
    katy = [100 + i * 8.5 for i in range(14)]

    def xy(k, dr=0):
        a = math.radians(k)
        x, y = cx + (r + dr) * math.cos(a), cy + (r + dr) * math.sin(a)
        return (2 * cx - x if strona == 1 else x), y

    def kat(k, odchyl):
        # kierunek wzrostu gałązki = styczna do łuku (rosnące k), plus odchylenie liścia
        t = math.degrees(math.atan2(math.cos(math.radians(k)), -math.sin(math.radians(k)))) + odchyl
        return 180 - t if strona == 1 else t

    x0, y0 = xy(katy[0])
    x1, y1 = xy(katy[-1])
    czesci = [f'<path d="M{R(x0)},{R(y0)}A{r},{r} 0 0 {1 if strona == -1 else 0} {R(x1)},{R(y1)}" '
              f'fill="none" stroke-width="1.5" stroke-linecap="round"/>']
    for i, k in enumerate(katy[1:], 1):
        dl = 7.6 - i * .2
        for bok in (-1, 1):
            x, y = xy(k, bok * 5)
            czesci.append(f'<ellipse cx="{R(x)}" cy="{R(y)}" rx="{R(dl)}" ry="{R(dl * .4)}" '
                          f'transform="rotate({R(kat(k, -bok * 32))} {R(x)} {R(y)})"/>')
    x, y = xy(katy[-1] + 5)
    czesci.append(f'<ellipse cx="{R(x)}" cy="{R(y)}" rx="5.5" ry="2.2" transform="rotate({R(kat(katy[-1], 0))} {R(x)} {R(y)})"/>')
    return "".join(czesci)


def tarcza(tytul, duzy, akt, opis):
    linie = tytul.split("|")
    zloto = "url(#pt-zloto)"
    tyt = "".join(
        f'<text class="pt-tytul" x="80" y="{R(32 + i * 10.5)}">{esc(l)}</text>' for i, l in enumerate(linie)
    )
    cx, cy, rr = 80, 93, 31
    gw = "".join(
        f'<path d="{gwiazda(cx + rr * math.cos(math.radians(i * 30 - 90)), cy + rr * math.sin(math.radians(i * 30 - 90)), 3.4)}"/>'
        for i in range(12)
    )
    fs = 17 if len(duzy) <= 4 else 12
    rozmiar_opisu = ' font-size="5.9"' if len(opis) > 20 else ""
    return (
        f'<svg class="nx-tarcza" viewBox="-26 -16 212 222" role="img" aria-label="{esc(duzy)} ({esc(akt)}): {esc(" ".join(linie).lower())}, zobowiązanie notarai">'
        f'<g class="pt-laur" fill="{zloto}" stroke="{zloto}" filter="url(#pt-relief-maly)">{laur(-1)}{laur(1)}</g>'
        # metalowa rama: dwie złote obręcze w reliefie, między nimi granatowa emalia
        f'<g filter="url(#pt-relief)">'
        f'<path d="{ksztalt(1)}" fill="{zloto}"/>'
        f'<path d="{ksztalt(.955)}" fill="#071a52"/>'
        f'<path d="{ksztalt(.935)}" fill="{zloto}"/>'
        f'</g>'
        # emalia jako wypukła kopuła
        f'<path d="{ksztalt(.9)}" fill="url(#pt-kopula)"/>'
        f'<g clip-path="url(#pt-clip)">'
        f'<use href="#pt-grawer" class="pt-grawer"/>'
        f'<rect x="0" y="0" width="160" height="52" fill="url(#pt-glowica)"/>'
        f'<use href="#pt-grawer" class="pt-grawer-glowica"/>'
        f'<rect x="0" y="0" width="160" height="22" fill="#fff" opacity=".1"/>'
        f'<path d="M0,52H160" stroke="{zloto}" stroke-width="2.6" filter="url(#pt-relief-maly)"/>'
        f'<path d="{ksztalt(.9)}" fill="none" stroke="#06184d" stroke-width="9" opacity=".38" filter="url(#pt-cien-wew)"/>'
        f'<g transform="rotate(18 80 100)"><rect class="pt-blysk-pas" x="-70" y="-30" width="34" height="260" fill="url(#pt-pas)"/></g>'
        f'</g>'
        f'<g filter="url(#pt-cien-tekstu)">{tyt}</g>'
        f'<g fill="{zloto}" filter="url(#pt-relief-maly)">{gw}</g>'
        f'<text class="pt-duzy" x="{cx}" y="{R(cy + fs * .36)}" font-size="{fs}" filter="url(#pt-wytlocz)">{esc(duzy)}</text>'
        f'<text class="pt-akt" x="80" y="135">{esc(akt)}</text>'
        f'<text class="pt-opis" x="80" y="146"{rozmiar_opisu}>{esc(opis)}</text>'
        f'<path d="{ksztalt(.9)}" fill="url(#pt-blask)"/>'
        # medalion z gwiazdą: wypukły, w reliefie
        f'<g filter="url(#pt-relief)">'
        f'<circle cx="80" cy="5" r="13" fill="{zloto}"/>'
        f'<circle cx="80" cy="5" r="10.2" fill="url(#pt-glowica)"/>'
        f'</g>'
        f'<path d="{gwiazda(80, 5.5, 6.6)}" fill="{zloto}" filter="url(#pt-relief-maly)"/>'
        f'<ellipse cx="76" cy="0" rx="5" ry="2.4" fill="#fff" opacity=".35"/>'
        # wstęga: końce w cieniu, fałdy, przód z połyskiem
        f'<path d="M14,163H-8L1,171.5L-8,180H14Z" fill="#021245"/>'
        f'<path d="M146,163H168L159,171.5L168,180H146Z" fill="#021245"/>'
        f'<path d="M14,163H-8L1,171.5L-8,180H14Z M146,163H168L159,171.5L168,180H146Z" fill="url(#pt-wstega-g)" opacity=".55"/>'
        f'<path d="M14,180L20,185V176Z M146,180L140,185V176Z" fill="#000a2a"/>'
        f'<path d="M14,157Q80,165 146,157V176Q80,184 14,176Z" fill="url(#pt-wstega-g)"/>'
        f'<path d="M14,157Q80,165 146,157V176Q80,184 14,176Z" fill="none" stroke="{zloto}" stroke-width="1.4" filter="url(#pt-relief-maly)"/>'
        f'<path d="M16,160Q80,168 144,160" fill="none" stroke="#fff" stroke-width=".8" opacity=".35"/>'
        f'<text class="pt-marka" fill="{zloto}" filter="url(#pt-cien-tekstu)"><textPath href="#pt-wstega" startOffset="50%">NOTARAI</textPath></text>'
        "</svg>"
    )


# Pasek: (fragment nazwy w <b>) -> (rodzina, znak)
PASEK = {
    "RODO / GDPR": ("eu", "★"), "ISO/IEC 27001": ("iso", "ISO"), "AI Act": ("eu", "AI"),
    "ISO/IEC 27017": ("iso", "ISO"), "Dane tylko w UE": ("eu", "EU"), "ISO/IEC 27018": ("iso", "ISO"),
    "DPIA": ("eu", "§"), "ISO/IEC 27701": ("iso", "ISO"), "Tajemnica notarialna": ("eu", "§"),
    "SOC 1 · SOC 2 · SOC 3": ("soc", "SOC"), "Art. 22 RODO": ("eu", "§"), "BSI C5": ("c5", "C5"),
    "CISPE": ("eu", "EU"), "ISO 9001 · 22301": ("iso", "ISO"), "EU-U.S. DPF": ("csa", "DPF"),
    "AES-256 · TLS": ("soc", "256"), "CSA STAR": ("csa", "CSA"), "Zero trenowania": ("eu", "0"),
}


def main(sciezka):
    s = open(sciezka, encoding="utf-8").read()
    # 1. sprite pieczęci zaraz po sprite ikon
    s = re.sub(r'<svg class="nx-seal-defs".*?</svg>\n', "", s, flags=re.S)
    s = s.replace("</svg>\n\n<header", "</svg>\n" + sprite() + "\n\n<header", 1)

    # 2. ściana certyfikatów
    sciana = "\n".join(
        f'      <li>{pieczec(r, g, DOL_CERT, ml, d, o, f"{ml} {d}: certyfikat dostawcy infrastruktury technicznej")}</li>'
        for r, g, ml, d, o in SCIANA
    )
    s = re.sub(r'(<ul class="nx-wall">\n).*?(\n    </ul>)', lambda m: m.group(1) + sciana + m.group(2), s, flags=re.S)

    # 3. zgodność
    zg = "\n".join(
        f'      <li>{tarcza(g, d, akt, o)}<b>{esc(nag)}</b><span>{esc(zd)}</span></li>'
        for g, d, akt, o, nag, zd in ZGODNOSC
    )
    s = re.sub(r'(<ul class="nx-law">\n).*?(\n    </ul>)', lambda m: m.group(1) + zg + m.group(2), s, flags=re.S)

    # 4. pasek: ikonka -> mini pieczęć
    def podmien(m):
        nazwa = m.group(2)
        rod, znak = PASEK[nazwa]
        return f'{m.group(1)}{mini(rod, znak)}<span><b>{nazwa}</b>'
    s = re.sub(r'(<li class="nx-seal[^"]*">)(?:<span class="nx-seal__ico">[^<]*</span>|<svg class="nx-mini".*?</svg>)<span><b>([^<]*)</b>', podmien, s)
    open(sciezka, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    main(sys.argv[1])
