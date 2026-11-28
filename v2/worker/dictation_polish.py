"""Dictation read with understanding (owner's decision 28.11.2026).

Speech recognition writes what it heard, word by word: „w rynecie” for RejNET, a sentence started twice, no
commas. Before the text lands in the message box, the assistant reads it once more and writes what the notary
meant, using what this office works with (its programs, the program's own commands, the notary's dictionary).

What the code holds on to, whatever the model returns:
- every number stays as it was heard (dates, amounts, PESEL, land register numbers): if the digits differ,
  the heard text is kept;
- the result may not grow or shrink out of proportion, and may not be empty: otherwise the heard text is kept;
- it runs once, at the end of a dictation, only on short texts, and only when the station's assistant is on.

Names of people go through the usual replacement with placeholders (inference.py), so the model does not see
them and does not "correct" them.
"""
import re

MAX_CHARS = 4000

SYSTEM = (
    "Poprawiasz tekst podyktowany na głos przez notariusza albo pracownika polskiej kancelarii notarialnej do programu "
    "NotarAI. Rozpoznawanie mowy zapisało go dosłownie i mogło przekręcić słowa. Napisz to, co mówiący chciał "
    "powiedzieć:\n"
    "- popraw słowa wyraźnie przesłyszane, zwłaszcza nazwy programów i terminy z listy SŁOWNIK (np. „rynet”, „rajnet”, "
    "„w rynecie” to RejNET; „ka er zet” to KRZ; „ka wu” to KW),\n"
    "- usuń zająknięcia, powtórzenia i wtrącenia bez treści („no”, „kurde”, „wiesz”, „tak?”, „nie?” na końcu zdania),\n"
    "- dodaj interpunkcję i wielkie litery,\n"
    "- gdy zdanie jest poleceniem dla programu, zostaw je poleceniem, krótkim i jednoznacznym.\n"
    "Nazwy ze słownika pisz dokładnie tak, jak w słowniku, bez odmiany („w RejNET”, nie „w RejNecie”). Nazwisko albo "
    "nazwa po słowach „akt”, „akty”, „sprawa” to nazwa tego aktu lub sprawy: nie oddzielaj jej przecinkiem ani "
    "myślnikiem. Nie używaj myślników. Gdy mówiący sam poprawia liczbę („450, nie, 540”), zostaw obie liczby i słowo "
    "„nie” między nimi: o liczbach rozstrzyga człowiek. "
    "Nie dodawaj niczego, czego mówiący nie powiedział. Nie zmieniaj sensu, liczb, dat, kwot, numerów ani nazwisk. "
    "Znaczniki w nawiasach kwadratowych przepisz bez zmian. Gdy nie jesteś pewien, zostaw słowo tak, jak jest. "
    "Odpowiedz WYŁĄCZNIE poprawionym tekstem, bez komentarza i bez cudzysłowu."
)

COMMANDS = ("KRZ, KW, księga wieczysta, RejNET, repertorium, akt notarialny, wypis, odpis, taksa, PESEL, sprawa, strony aktu, "
            "pełnomocnictwo, umowa sprzedaży, darowizna, sprawdź KRZ, sprawdź KW, poznaj program, dziennik agenta, stop, "
            "pokaż przeglądarkę, sprawdź aktualizacje")


def digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def polish(ask, heard: str, glossary=()) -> tuple[str, bool]:
    """(text for the message box, whether it was changed). `ask(system, text)` -> the model's reply."""
    heard = " ".join((heard or "").split())
    if len(heard) < 12 or len(heard) > MAX_CHARS:
        return heard, False
    words = ", ".join(dict.fromkeys([w for w in glossary if w] + [COMMANDS]))[:1500]
    try:
        said = ask(SYSTEM, f"SŁOWNIK (nazwy i terminy tej kancelarii): {words}\n\nTEKST USŁYSZANY:\n{heard}")
    except Exception:
        return heard, False                        # the dictation is worth more than its polish
    said = " ".join(str(said or "").strip().strip("„”\"").split())
    if not said or digits(said) != digits(heard):
        return heard, False                        # a number changed: the heard text stays
    if not 0.4 * len(heard) <= len(said) <= 1.3 * len(heard) + 20:
        return heard, False                        # out of proportion: something was added or lost
    return said, said != heard
