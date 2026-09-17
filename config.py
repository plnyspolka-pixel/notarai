"""Konfiguracja pieczapp.

Wszystkie sciezki sa lokalne. Zadne dane nie opuszczaja tego katalogu
poza pojedynczym wywolaniem Bedrock, ktore nie jest nigdzie zapisywane.
"""
import os
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
    "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
)

# Profil AWS - dla izolacji uprawnien pomiędzy projektami
PROFIL_AWS = os.getenv("PIECZAPP_AWS_PROFILE", "pieczapp")

# Serwer slucha wylacznie na petli lokalnej.
# Zmiana na 0.0.0.0 wystawia aplikacje na siec - rob to swiadomie.
HOST = os.getenv("PIECZAPP_HOST", "127.0.0.1")
PORT = int(os.getenv("PIECZAPP_PORT", "8000"))

# Rozdzielczosc renderowania stron PDF. 200 dpi to dobry kompromis
# miedzy czytelnoscia pieczatek a rozmiarem obrazu.
DPI = int(os.getenv("PIECZAPP_DPI", "220"))

# Najdluzszy bok obrazu strony wysylanego do modelu. Odreczne formularze
# (dowod, oswiadczenia) sa nieczytelne ponizej ~2000 px.
MAX_BOK = int(os.getenv("PIECZAPP_MAX_BOK", "2400"))

# Maksymalna liczba stron wysylanych do modelu w jednej analizie.
MAX_STRON = int(os.getenv("PIECZAPP_MAX_STRON", "40"))

if not MODEL.startswith("eu."):
    raise RuntimeError(
        f"Model '{MODEL}' nie jest profilem EU. "
        "Uzyj identyfikatora zaczynajacego sie od 'eu.', "
        "inaczej zapytania moga wyjsc poza Unie Europejska."
    )
