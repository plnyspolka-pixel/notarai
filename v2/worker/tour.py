"""The tour of what NotarAI can do: one slide per ability, with what to say and a "try it" button.

Each slide shows a short example exchange (what the notary says, what NotarAI answers), so the
notary learns the abilities and how to ask for them at the same time. Only abilities the program
really has; those learned by showing say so.
"""

SLIDES = [
    {"icon": "calendar", "title": "Kalendarz kancelarii",
     "text": "Terminy aktów i spotkań mówisz albo piszesz zwykłym zdaniem. Na komputerze kalendarz miesiąca jest zawsze po lewej, "
             "a plan dnia widzisz na powitanie. Terminy usłyszane w rozmowach dopisują się same, do sprawdzenia.",
     "you": "termin w piątek 10:00 podpisanie aktu Kowalski", "notarai": "Zapisałem w kalendarzu: pt 10:00, podpisanie aktu Kowalski.",
     "try": "co mam jutro"},
    {"icon": "mic", "title": "Dyktowanie zamiast pisania",
     "text": "Dotknij 🎤 i mów: tekst pojawia się w polu na bieżąco. Poprawiasz i wysyłasz, albo wysyłasz od razu ↑. "
             "Mowę przepisuje Frankfurt albo, jeśli tak wybierzesz, ten komputer.",
     "you": "🎤 „Klient przyniesie odpis z księgi wieczystej w piątek”", "notarai": "(tekst pojawia się w polu, gdy mówisz)",
     "try": None},
    {"icon": "deed", "title": "Projekty aktów w stylu kancelarii",
     "text": "Z dokumentów sprawy przygotuję projekt aktu sformułowaniami Twojej kancelarii, wyuczonymi z dotychczasowych aktów. "
             "Nic nie zapisuję bez Twojego zatwierdzenia; zasady kancelarii sprawdza kod przy każdym zapisie.",
     "you": "przygotuj umowę sprzedaży lokalu", "notarai": "Projekt gotowy. Przeczytaj go; zapiszę dopiero to, co zatwierdzisz.",
     "try": "rodzaje aktów"},
    {"icon": "files", "title": "Pliki i pytania o sprawę",
     "text": "Przeciągnij pliki do okna, wklej albo zrób zdjęcie telefonem. Od razu streszczam, szukam błędów "
             "i odpowiadam na pytania o sprawę na podstawie jej dokumentów (DOCX, PDF, e-mail, nagrania).",
     "you": "kto jest sprzedającym i czy zgadza się numer księgi?", "notarai": "Sprzedającym jest Jan Kowalski. Numer KW w umowie przedwstępnej różni się od odpisu: …",
     "try": "dokumenty"},
    {"icon": "book", "title": "Księgi wieczyste (EKW)",
     "text": "Pokaż raz, jak sprawdzasz księgę w przeglądarce NotarAI. Potem program sam otwiera księgę po numerze, "
             "przepisuje potrzebne działy do sprawy i porównuje je z dokumentami.",
     "you": "sprawdź księgę WA1M/00012345/6", "notarai": "Otwieram księgę w przeglądarce NotarAI i wpisuję numer…",
     "try": "dodaj czynność Sprawdzenie księgi wieczystej (EKW)"},
    {"icon": "scale", "title": "Krajowy Rejestr Zadłużonych (KRZ)",
     "text": "Strony sprawy sprawdzane w KRZ przed aktem: pokazujesz raz, potem program wyszukuje każdą stronę sam "
             "i zapisuje wynik w sprawie.",
     "you": "sprawdź strony w KRZ", "notarai": "Sprawdzam Jana Kowalskiego i Annę Nowak w KRZ…",
     "try": "dodaj czynność Sprawdzenie stron w Krajowym Rejestrze Zadłużonych (KRZ)"},
    {"icon": "form", "title": "Wnioski i formularze urzędowe",
     "text": "Wniosek o wpis w KW, PCC-3, zawiadomienia: program wypełnia pola sam z danych sprawy, na stronach "
             "i w programach Windows. Wysłanie albo podpis zawsze dopiero po Twoim zatwierdzeniu, jednym naciśnięciem.",
     "you": "wypełnij wniosek o wpis w KW", "notarai": "Wpisałem 14 pól. Sprawdź podgląd; wyślę po Twoim zatwierdzeniu.",
     "try": "czynności"},
    {"icon": "plug", "title": "Programy kancelaryjne (RejNET i inne)",
     "text": "Repertorium, rejestry i każdy inny program Windows: nagrywasz raz ekran z komentarzem, program uczy się "
             "pól i od drugiego razu wpisuje dane sam. Przy pierwszym uruchomieniu sam wykrywa, co masz zainstalowane.",
     "you": "wpisz akt do repertorium", "notarai": "Wpisałem dane aktu w RejNET. Zatwierdzić zapis?",
     "try": "rozpoznaj komputer"},
    {"icon": "mail", "title": "Poczta",
     "text": "Outlook albo Thunderbird: wiadomości od klientów, załączniki do sprawy jednym zdaniem, streszczenia.",
     "you": "maile od Kowalskiego", "notarai": "3 wiadomości od Jana Kowalskiego. Dodać załączniki do sprawy?",
     "try": "poczta"},
    {"icon": "coins", "title": "Taksa i koszty",
     "text": "Taksa notarialna, VAT i opłaty policzone przez kod (nie przez AI), z rozbiciem do pokazania klientowi.",
     "you": "policz taksę od sprzedaży lokalu za 500 tys.", "notarai": "Taksa, VAT, opłaty sądowe i podatek z rozbiciem na pozycje… RAZEM …",
     "try": "policz taksę od sprzedaży lokalu za 500 tys."},
    {"icon": "phone", "title": "Telefon: NotarAI Pocket",
     "text": "Ta sama rozmowa na telefonie, szyfrowana do komputera kancelarii: kalendarz, dyktowanie, zdjęcia "
             "dokumentów do sprawy. Paruje się raz kodem QR.",
     "you": "dodaj telefon", "notarai": "Zeskanuj ten kod aparatem telefonu…",
     "try": "dodaj telefon"},
    {"icon": "ear", "title": "Nasłuch: stenopisy i notatki z rozmów",
     "text": "Tablet albo telefon na ładowarce w gabinecie lub sekretariacie. Odczytany akt staje się stenopisem sprawy, "
             "rozmowy z klientami i telefony notatkami z terminem i kontaktem. Dźwięk nie jest przechowywany.",
     "you": "notatki z rozmów", "notarai": "Rozmowa telefoniczna 10:12: klient prosi o przesunięcie aktu na wtorek…",
     "try": "nasłuch"},
    {"icon": "rules", "title": "Twarde zasady kancelarii",
     "text": "Zasady wpisane zdaniem pilnuje kod przy każdym zapisie i wysyłce, nie da się ich obejść poleceniem.",
     "you": "zasada: każdy akt musi zawierać „Notariusz pouczył strony”", "notarai": "Dodałem zasadę nr 1. Sprawdzam ją przy każdym zapisie.",
     "try": "zasady"},
    {"icon": "shield", "title": "Bezpieczeństwo",
     "text": "Dokumenty w zaszyfrowanym sejfie na tym komputerze, kod odzyskiwania tylko u Ciebie, AI i mowa wyłącznie "
             "we Frankfurcie, bez uczenia na danych kancelarii. Nic nie wychodzi w Twoim imieniu bez zatwierdzenia.",
     "you": "gdzie są dane", "notarai": "Dokumenty, notatki i nagrania: zawsze w zaszyfrowanym sejfie na tym komputerze…",
     "try": "gdzie są dane"},
]


def slides() -> list[dict]:
    return [dict(slide) for slide in SLIDES]
