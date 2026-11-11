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
    ("OCHRONA DANYCH|OSOBOWYCH", "RODO", "art. 28 · 32 · 22"),
    ("AKT O SZTUCZNEJ|INTELIGENCJI", "AI ACT", "nadzór człowieka"),
    ("OCENA SKUTKÓW|ART. 35 RODO", "DPIA", "gotowa w aplikacji"),
    ("UMOWA|POWIERZENIA", "ART. 28", "przy rejestracji"),
    ("TAJEMNICA|NOTARIALNA", "ART. 18", "chroniona algorytmicznie"),
    ("PRZETWARZANIE|TYLKO W UE", "EU", "Frankfurt"),
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


def tarcza(tytul, duzy, opis):
    linie = tytul.split("|")
    zloto = "url(#ps-m-iso)"
    tyt = "".join(
        f'<text class="pt-tytul" x="80" y="{R(31 + i * 10.5)}">{esc(l)}</text>' for i, l in enumerate(linie)
    )
    cx, cy, rr = 80, 96, 35
    gw = "".join(
        f'<path d="{gwiazda(cx + rr * math.cos(math.radians(i * 30 - 90)), cy + rr * math.sin(math.radians(i * 30 - 90)), 3.6)}"/>'
        for i in range(12)
    )
    fs = 18 if len(duzy) <= 4 else 12.5
    rozmiar_opisu = ' font-size="6.1"' if len(opis) > 18 else ""
    return (
        f'<svg class="nx-tarcza" viewBox="-10 0 180 200" role="img" aria-label="{esc(duzy)}: {esc(" ".join(linie).lower())}, zobowiązanie notarai">'
        f'<path d="{ksztalt(1)}" fill="{zloto}"/>'
        f'<path d="{ksztalt(.955)}" fill="#0a2266"/>'
        f'<path d="{ksztalt(.935)}" fill="{zloto}"/>'
        f'<path d="{ksztalt(.9)}" fill="url(#pt-emalia)"/>'
        f'<g clip-path="url(#pt-clip)">'
        f'<use href="#pt-grawer" class="pt-grawer"/>'
        f'<rect x="0" y="0" width="160" height="51" fill="url(#ps-b-eu)"/>'
        f'<path d="M0,51H160" stroke="{zloto}" stroke-width="2"/>'
        f'<path d="M0,54.2H160" stroke="#0a2266" stroke-width=".5" opacity=".5"/>'
        f'</g>'
        f'{tyt}'
        f'<g fill="{zloto}">{gw}</g>'
        f'<text class="pt-duzy" x="{cx}" y="{R(cy + fs * .36)}" font-size="{fs}">{esc(duzy)}</text>'
        f'<text class="pt-opis" x="80" y="148.5"{rozmiar_opisu}>{esc(opis)}</text>'
        f'<path d="{ksztalt(.9)}" fill="url(#pt-blask)"/>'
        # wstęga z zakładkami wychodząca poza tarczę
        f'<path d="M14,163H-6L2,171.5L-6,180H14Z" fill="#001a5c"/>'
        f'<path d="M146,163H166L158,171.5L166,180H146Z" fill="#001a5c"/>'
        f'<path d="M14,180L20,184V176Z M146,180L140,184V176Z" fill="#000d33"/>'
        f'<path d="M14,158Q80,166 146,158V176Q80,184 14,176Z" fill="url(#ps-b-eu)" stroke="{zloto}" stroke-width="1.1"/>'
        f'<text class="pt-marka" fill="{zloto}"><textPath href="#pt-wstega" startOffset="50%">NOTARAI</textPath></text>'
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
        f'      <li>{tarcza(g, d, o)}</li>'
        for g, d, o in ZGODNOSC
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
