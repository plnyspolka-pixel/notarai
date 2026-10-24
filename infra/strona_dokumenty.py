"""Buduje strony dokumentow na notarai.pl z docs/prawne.

    py -3 infra/strona_dokumenty.py

Zrodlem prawdy sa pliki Markdown w docs/prawne; strony HTML generuje sie od
nowa przy kazdej zmianie, zeby tresc na stronie nie rozjechala sie z
dokumentem, ktory kancelaria akceptuje w aplikacji. Konwerter jest wspolny
z aplikacja (dokumenty_prawne.py).
"""
import sys
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KORZEN))

import dokumenty_prawne  # noqa: E402

# (dokument, katalog na stronie)
STRONY = [
    ("regulamin", "regulamin"),
    ("prywatnosc", "prywatnosc"),
    ("umowa", "umowa-powierzenia"),
    ("instrukcja", "instrukcja-ai"),
]

STOPKA = " · ".join([
    '<a href="../regulamin/">Regulamin</a>',
    '<a href="../umowa-powierzenia/">Umowa powierzenia</a>',
    '<a href="../instrukcja-ai/">Instrukcja AI</a>',
    '<a href="../prywatnosc/">Polityka prywatności</a>',
    '<a href="mailto:kontakt@notarai.pl">kontakt@notarai.pl</a>',
])

SZABLON = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{tytul} - notarai</title>
<link rel="icon" href="../favicon.png">
<link rel="stylesheet" href="../style.css">
</head>
<body>
<header class="naglowek">
  <div class="szer naglowek-w rozsun">
    <a class="marka" href="../">
      <img src="../favicon.png" alt="" width="32" height="32">
      <span>notarai</span>
    </a>
    <a class="przycisk maly" href="https://app.notarai.pl/rejestracja">Załóż konto</a>
  </div>
</header>
<main class="szer dokument">
{tresc}
</main>
<footer class="stopka">
  <div class="szer stopka-w">
    <p>notarai.pl prowadzi Fundacja Krzewienia Edukacji Finansowej im. Pieczaka, ul.&nbsp;Wilhelma Orlika Ruckemana 4/18, 20-244 Lublin, KRS 0001140846, NIP 9462747637.</p>
    <p>{stopka}</p>
  </div>
</footer>
</body>
</html>
"""


def main():
    for nazwa, katalog in STRONY:
        plik = KORZEN / "strona" / katalog / "index.html"
        plik.parent.mkdir(parents=True, exist_ok=True)
        plik.write_text(SZABLON.format(tytul=dokumenty_prawne.tytul(nazwa),
                                       tresc=dokumenty_prawne.html_dokumentu(nazwa),
                                       stopka=STOPKA),
                        encoding="utf-8", newline="\n")
        print(f"{dokumenty_prawne.DOKUMENTY[nazwa][0]} -> strona/{katalog}/index.html")


if __name__ == "__main__":
    main()
