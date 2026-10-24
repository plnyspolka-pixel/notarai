"""Dokumenty prawne notarai: wersje, HTML i wypelnianie danymi kancelarii.

Zrodlem prawdy sa pliki Markdown w docs/prawne. Z tych samych plikow
powstaja strony notarai.pl (infra/strona_dokumenty.py) i dokumenty w
aplikacji, wiec tresc, ktora kancelaria akceptuje, nie rozjedzie sie z
opublikowana.

Wersja dokumentu to data z linii "Wersja z dnia DD.MM.RRRR." - zmiana tej
daty w pliku oznacza nowa wersje do akceptacji.

Konwerter obsluguje tylko skladnie uzywana w tych plikach: naglowki,
akapity, listy numerowane i punktowane (z zagniezdzeniem), tabele,
pogrubienie, kod i cytaty. Bez zaleznosci spoza biblioteki standardowej.
"""
import html
import re
from functools import lru_cache
from pathlib import Path

KATALOG = Path(__file__).resolve().parent / "docs" / "prawne"

# nazwa w API -> (plik, tytul)
DOKUMENTY = {
    "regulamin": ("02-regulamin.md", "Regulamin"),
    "umowa": ("01-umowa-powierzenia.md", "Umowa powierzenia przetwarzania danych"),
    "prywatnosc": ("03-polityka-prywatnosci.md", "Polityka prywatności"),
    "instrukcja": ("09-instrukcja-ai.md", "Instrukcja korzystania z AI"),
    "dpia": ("07-dpia-dla-kancelarii.md", "Ocena skutków dla ochrony danych"),
    "kancelaria": ("08-dla-kancelarii-checklista.md", "Co robi kancelaria"),
}

# Pole bez wartosci na stronie publicznej: wzor, ktory wypelnia aplikacja.
PUSTE_POLE = "(uzupełnia aplikacja)"

_POLE = re.compile(r"\{\{(\w+)\}\}")
_WERSJA = re.compile(r"Wersja z dnia (\d{2})\.(\d{2})\.(\d{4})")


@lru_cache(maxsize=None)
def tresc(nazwa: str) -> str:
    plik, _ = DOKUMENTY[nazwa]
    return (KATALOG / plik).read_text(encoding="utf-8")


def tytul(nazwa: str) -> str:
    return DOKUMENTY[nazwa][1]


def wersja(nazwa: str) -> str:
    """Wersja jako RRRR-MM-DD. Dokument bez linii wersji to blad w repo."""
    m = _WERSJA.search(tresc(nazwa))
    if not m:
        raise ValueError(f"{nazwa}: brak linii 'Wersja z dnia DD.MM.RRRR.'")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"


def html_dokumentu(nazwa: str, pola: dict | None = None) -> str:
    """Tresc dokumentu jako HTML (bez <html>). Pola {{nazwa}} dostaja
    wartosci z `pola`, a brakujace - PUSTE_POLE.

    Wartosci wstawiamy dopiero do gotowego HTML, po zakodowaniu. Wstawione
    do Markdown przeszlyby przez skladnie odnosnikow - nazwa kancelarii
    w postaci [x](javascript:...) zrobilaby z dokumentu pulapke.
    """
    _, cialo = na_html(tresc(nazwa))
    pola = pola or {}
    return _POLE.sub(lambda m: html.escape(str(pola.get(m.group(1)) or PUSTE_POLE)), cialo)


STYL = """
body{font:15px/1.6 Georgia,'Times New Roman',serif;color:#1d1d1b;background:#fff;
  max-width:820px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:24px;line-height:1.3}h2{font-size:18px;margin-top:28px}h3{font-size:16px}
table{border-collapse:collapse;width:100%;font-size:13px;margin:12px 0}
th,td{border:1px solid #ccc;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f4f2ee}.tabela{overflow-x:auto}
blockquote{margin:12px 0;padding:8px 14px;border-left:3px solid #ccc;color:#444}
code{font-family:Consolas,monospace;font-size:13px}
.zawarcie{border:1px solid #9bb59b;background:#f2f8f2;padding:4px 16px 8px;margin:0 0 24px}
@media print{body{padding:0}.zawarcie{break-inside:avoid}}
"""


def strona(nazwa: str, pola: dict | None = None, przed: str = "") -> str:
    """Samodzielna strona do otwarcia, wydruku albo zapisu jako PDF.
    `przed` to gotowy, juz zakodowany HTML (np. ramka z danymi stron)."""
    return (
        '<!doctype html><html lang="pl"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(tytul(nazwa))} - notarai</title><style>{STYL}</style></head>"
        f"<body>{przed}{html_dokumentu(nazwa, pola)}</body></html>"
    )


# --- Markdown -> HTML ------------------------------------------------------

# Odnosniki tylko do stron, poczty i miejsc wewnatrz dokumentu.
_ODNOSNIK = re.compile(r"\[([^\]]+)\]\(((?:https?://|mailto:|\.\.?/|#)[^)\s]*|[\w./-]+)\)")


def wiersz(tekst: str) -> str:
    t = html.escape(tekst, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = _ODNOSNIK.sub(r'<a href="\2">\1</a>', t)
    t = re.sub(r"(?<![\w/])(kontakt@notarai\.pl)", r'<a href="mailto:\1">\1</a>', t)
    return t


def na_html(md: str) -> tuple[str, str]:
    linie = md.splitlines()
    wynik: list[str] = []
    tytul_md = ""
    stos: list[tuple[int, str]] = []  # (wciecie, "ol"/"ul")
    akapit: list[str] = []
    i = 0

    def zamknij_akapit():
        if akapit:
            wynik.append(f"<p>{wiersz(' '.join(akapit))}</p>")
            akapit.clear()

    def zamknij_listy(do: int = -1):
        while stos and stos[-1][0] > do:
            _, rodzaj = stos.pop()
            wynik.append(f"</li></{rodzaj}>")

    while i < len(linie):
        l = linie[i]
        s = l.strip()
        if not s:
            zamknij_akapit()
            i += 1
            continue
        if s.startswith("#"):
            zamknij_akapit(); zamknij_listy()
            poziom = len(s) - len(s.lstrip("#"))
            tekst = s[poziom:].strip()
            if poziom == 1:
                tytul_md = tekst
                wynik.append(f"<h1>{wiersz(tekst.capitalize() if tekst.isupper() else tekst)}</h1>")
            else:
                wynik.append(f"<h{poziom}>{wiersz(tekst)}</h{poziom}>")
            i += 1
            continue
        if s.startswith("|"):
            zamknij_akapit(); zamknij_listy()
            wiersze = []
            while i < len(linie) and linie[i].strip().startswith("|"):
                wiersze.append([k.strip() for k in linie[i].strip().strip("|").split("|")])
                i += 1
            naglowek, cialo = wiersze[0], [w for w in wiersze[2:]]
            wynik.append('<div class="tabela"><table><thead><tr>'
                         + "".join(f"<th>{wiersz(k)}</th>" for k in naglowek)
                         + "</tr></thead><tbody>"
                         + "".join("<tr>" + "".join(f"<td>{wiersz(k)}</td>" for k in w) + "</tr>" for w in cialo)
                         + "</tbody></table></div>")
            continue
        if s.startswith(">"):
            zamknij_akapit(); zamknij_listy()
            cytat = []
            while i < len(linie) and linie[i].strip().startswith(">"):
                cytat.append(linie[i].strip().lstrip(">").strip())
                i += 1
            wynik.append(f"<blockquote>{wiersz(' '.join(cytat))}</blockquote>")
            continue
        m = re.match(r"^(\s*)(\d+\.|[-*])\s+(.*)$", l)
        if m:
            zamknij_akapit()
            wciecie = len(m.group(1))
            rodzaj = "ol" if m.group(2)[0].isdigit() else "ul"
            if stos and wciecie < stos[-1][0]:
                zamknij_listy(wciecie)
            if not stos or wciecie > stos[-1][0]:
                wynik.append(f"<{rodzaj}><li>")
                stos.append((wciecie, rodzaj))
            else:
                wynik.append("</li><li>")
            tresc_punktu = [m.group(3)]
            i += 1
            # ciag dalszy punktu: wciete linie, ktore nie zaczynaja nowego punktu
            while i < len(linie) and linie[i].strip() and not re.match(r"^\s*(\d+\.|[-*])\s+", linie[i]) \
                    and (len(linie[i]) - len(linie[i].lstrip())) > wciecie and not linie[i].strip().startswith("|"):
                tresc_punktu.append(linie[i].strip())
                i += 1
            wynik.append(wiersz(" ".join(tresc_punktu)))
            continue
        if stos and (len(l) - len(l.lstrip())) == 0:
            zamknij_listy()
        akapit.append(s)
        i += 1
    zamknij_akapit(); zamknij_listy()
    return tytul_md, "\n".join(wynik)
