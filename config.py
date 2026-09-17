"""Konfiguracja pieczapp.

Wszystkie sciezki sa lokalne. Zadne dane nie opuszczaja tego katalogu
poza pojedynczym wywolaniem Bedrock, ktore nie jest nigdzie zapisywane.
"""
import os
import re
from pathlib import Path

KORZEN = Path(__file__).parent
DANE = KORZEN / "dane"
WZORY = DANE / "wzory"

for katalog in (DANE, WZORY):
    katalog.mkdir(parents=True, exist_ok=True)


def __getattr__(nazwa: str):
    """PEP 562: config.SPRAWY jest wyliczane per zadanie.

    W trybie lokalnym (kancelaria "lokalna") zwraca dokladnie dawne
    dane/sprawy, wiec caly istniejacy kod i testy dzialaja bez zmian.
    W trybie SaaS zwraca katalog spraw kancelarii z tokenu.
    """
    if nazwa == "SPRAWY":
        import magazyn
        return magazyn.sprawy_dir(DANE)
    raise AttributeError(nazwa)

# Region i model - musza byc profilami EU (prefiks "eu.")
REGION = os.getenv("AWS_REGION", "eu-central-1")
MODEL = os.getenv(
    "PIECZAPP_MODEL",
    # Najnowszy profil, do ktorego konto ma wlaczony dostep w Bedrock.
    # Modele od wersji 4.7 wzwyz czytaja obraz w wyzszej rozdzielczosci
    # (patrz MAX_BOK) - po wlaczeniu im dostepu wystarczy podmienic te wartosc.
    "eu.anthropic.claude-sonnet-4-6",
)

# Modele, ktore widza obraz w wyzszej rozdzielczosci: dluzszy bok 2576 px
# zamiast 1568. Dla A4 to roznica miedzy ~220 a ~134 dpi, czyli miedzy
# czytelna a nieczytelna pieczatka.
_WYSOKA_ROZDZIELCZOSC = re.compile(
    r"(claude-opus-(4-7|4-8|5)|claude-sonnet-5|claude-fable-5)"
)


def wysoka_rozdzielczosc(model: str = "") -> bool:
    return bool(_WYSOKA_ROZDZIELCZOSC.search(model or MODEL))

# Profil AWS. Pusto (domyslnie) = zwykly lancuch poswiadczen boto3:
# lokalnie profil [default] z ~/.aws, w chmurze rola instancji App Runner
# albo rola zadania ECS. Nazwe profilu podaj tylko wtedy, gdy swiadomie
# chcesz innego niz default - w kontenerze zadne profile nie istnieja
# i wymuszenie nazwy wywrocilo by start aplikacji.
PROFIL_AWS = os.getenv("PIECZAPP_AWS_PROFILE", "")

# Serwer slucha wylacznie na petli lokalnej.
# Zmiana na 0.0.0.0 wystawia aplikacje na siec - rob to swiadomie.
HOST = os.getenv("PIECZAPP_HOST", "127.0.0.1")
PORT = int(os.getenv("PIECZAPP_PORT", "8000"))

# Rozdzielczosc renderowania stron PDF. 300 dpi daje zapas nad docelowym
# rozmiarem obrazu, wiec pomniejszenie tylko wyostrza, zamiast gubic szczegol.
DPI = int(os.getenv("PIECZAPP_DPI", "300"))

# Najdluzszy bok obrazu strony wysylanego do modelu. Wyzej niz widzi model
# nie ma sensu: nadmiar i tak zostanie pomniejszony po jego stronie, a my
# zaplacimy za przeslanie. Stad wartosc zalezna od modelu.
MAX_BOK = int(os.getenv("PIECZAPP_MAX_BOK", "0")) or (
    2576 if wysoka_rozdzielczosc() else 1568
)

# Maksymalna liczba stron wysylanych do modelu w jednej analizie.
MAX_STRON = int(os.getenv("PIECZAPP_MAX_STRON", "40"))

if not MODEL.startswith("eu."):
    raise RuntimeError(
        f"Model '{MODEL}' nie jest profilem EU. "
        "Uzyj identyfikatora zaczynajacego sie od 'eu.', "
        "inaczej zapytania moga wyjsc poza Unie Europejska."
    )
