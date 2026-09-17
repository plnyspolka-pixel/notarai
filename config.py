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
    # Najmocniejszy profil, do ktorego konto ma wlaczony dostep w Bedrock.
    # Modele od wersji 4.7 wzwyz sa na tym koncie zablokowane po stronie AWS
    # (odmowa takze dla konta glownego) - po odblokowaniu wystarczy podmienic
    # te wartosc, reszta ustawien dostosuje sie sama.
    "eu.anthropic.claude-opus-4-6-v1",
)

# Modele od wersji 4.7 wzwyz. Dwie rzeczy zalezne od tej granicy:
#  - czytaja obraz w wyzszej rozdzielczosci: dluzszy bok 2576 px zamiast 1568,
#    czyli dla A4 okolo 220 zamiast 134 dpi,
#  - nie przyjmuja juz parametru temperature; wyslanie go konczy sie bledem.
_NOWA_GENERACJA = re.compile(
    r"(claude-opus-(4-7|4-8|5)|claude-sonnet-5|claude-fable-5)"
)


def wysoka_rozdzielczosc(model: str = "") -> bool:
    return bool(_NOWA_GENERACJA.search(model or MODEL))


def przyjmuje_temperature(model: str = "") -> bool:
    return not _NOWA_GENERACJA.search(model or MODEL)

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
