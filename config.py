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

# Limity modelu (sprawdzone wywolaniem Bedrock dla Opus 4.6):
#  - 128 000 tokenow odpowiedzi to twardy limit, wyzej Bedrock odrzuca zadanie,
#  - kontekst 1M tokenow,
#  - myslenie adaptacyjne z wysilkiem "max".
MAX_WYJSCIE = int(os.getenv("PIECZAPP_MAX_WYJSCIE", "128000"))
WYSILEK = os.getenv("PIECZAPP_WYSILEK", "max")  # low | medium | high | max
MYSLENIE = os.getenv("PIECZAPP_MYSLENIE", "1") != "0"
# Cache promptu w Bedrock (punkty cachePoint stawia bedrock.py): "0" wylacza.
# Opus 4.6 i Haiku 4.5 zapisuja w cache prefiks od 4096 tokenow, Sonnet 4.6 od
# 1024; krotszy prefiks jest po cichu ignorowany (bez bledu i bez kosztu).
# Odczyt z cache kosztuje ok. 10% ceny wejscia, zapis 125% (tokenomia.py).
CACHE_PROMPTU = os.getenv("PIECZAPP_CACHE_PROMPTU", "1") != "0"

# Zasady kancelarii: projekt naruszajacy zasade nieprzekraczalna dostaje jedna
# ture poprawki przez model, a wytyczne opisowe - kontrole przez model. To do
# dwoch dodatkowych zapytan Bedrock na projekt (tylko gdy sa potrzebne).
# "0" wylacza oba; zostaje kontrola regulami i autonaprawa bez modelu.
POPRAWA_ZASAD = os.getenv("PIECZAPP_POPRAWA_ZASAD", "1") != "0"

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

# Najwieksza powierzchnia obrazu, ktora model widzi bez pomniejszania.
# Cala strona A4 w jednym obrazie to dla modeli do 4.6 ok. 90 dpi - za malo
# na drobny druk tabel, dlatego strony ida dodatkowo w poziomych pasach.
# Dla 4.7+ wartosc szacunkowa (proporcjonalna do dluzszego boku).
MAX_PIKSELI = int(os.getenv("PIECZAPP_MAX_PIKSELI", "0")) or (
    3100000 if wysoka_rozdzielczosc() else 1150000
)

# Limit stron w jednej sprawie. Strony czytane sa paczkami, wiec liczba
# stron nie pogarsza jakosci odczytu - ogranicza ja kontekst koncowego
# zestawienia (1M tokenow, ok. 2 tys. na strone).
MAX_STRON = int(os.getenv("PIECZAPP_MAX_STRON", "400"))

# Konto AWS ma limit zapytan do Bedrock na minute (w 2026 r. 5/min), wspolny
# dla wszystkich kancelarii. Dlatego strony ida paczkami: kilka kolejnych
# stron w jednym zapytaniu (do 20 obrazow - pelna strona + pasy kazdej).
STRON_W_PACZCE = int(os.getenv("PIECZAPP_STRON_W_PACZCE", "4"))
ROWNOLEGLE = int(os.getenv("PIECZAPP_ROWNOLEGLE", "2"))

if not MODEL.startswith("eu."):
    raise RuntimeError(
        f"Model '{MODEL}' nie jest profilem EU. "
        "Uzyj identyfikatora zaczynajacego sie od 'eu.', "
        "inaczej zapytania moga wyjsc poza Unie Europejska."
    )
