"""The tour of what NotarAI can do: one slide per ability, with what to say and a "try it" button.

Each slide shows a short example exchange (what the notary says, what NotarAI answers), so the
notary learns the abilities and how to ask for them at the same time. Only abilities the program
really has; those learned by showing say so.
"""

SLIDES = [
    {"icon": "calendar", "title": "Kalendarz kancelarii",
     "text": "Terminy aktów i spotkań mówisz albo piszesz zwykłym zdaniem. Na komputerze kalendarz miesiąca jest zawsze po lewej, "
             "a plan dnia widzisz na powitanie. Terminy usłyszane w rozmowach dopisują się same, do sprawdzenia. Kalendarz jest ten sam co w notarai.pl.",
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
     "text": "Podajesz numer albo program sam znajduje go w dokumentach sprawy. Treść wszystkich działów trafia do "
             "sprawy w 1-4 minuty, a asystent porównuje ją z umową: strony, obciążenia, oznaczenie nieruchomości. "
             "To nie jest odpis urzędowy: porównaj ze źródłem.",
     "you": "sprawdź KW WA1M/00012345/6", "notarai": "Księga WA1M/00012345/6: Dział III brak wpisów, Dział IV hipoteka umowna…",
     "try": "sprawdź księgę"},
    {"icon": "scale", "title": "Krajowy Rejestr Zadłużonych (KRZ)",
     "text": "Program bierze numery PESEL stron z dokumentów sprawy i sprawdza każdą osobę na krz.ms.gov.pl "
             "(dwa wyszukiwania), zapisuje zrzuty do sprawy i maskuje PESEL. Wynik zawsze potwierdzasz na zrzucie.",
     "you": "sprawdź strony w KRZ", "notarai": "4405*******: brak wpisu; 8901*******: brak wpisu. Zrzuty w sprawie.",
     "try": "sprawdź strony w KRZ"},
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
    {"icon": "learn", "title": "Tryb uczenia",
     "text": "Program uczy się Twojej pracy: z poprawek w projektach aktów, z poprawek po dyktowaniu, z Twoich "
             "odpowiedzi na maile i z poleceń „zapamiętaj: …” albo „to było źle: …”. Każdą nową lekcję pokazuje od razu, "
             "całą listę widzisz pod przyciskiem 📘 u góry i możesz z niej usunąć wszystko. Nazwiska i liczby są wycinane.",
     "you": "zapamiętaj: akty podpisujemy w gabinecie nr 2", "notarai": "📘 Zapamiętałem: akty podpisujemy w gabinecie nr 2",
     "try": "tryb uczenia"},
    {"icon": "plug", "title": "Tryb serwisowy: program zmienia się sam",
     "text": "Coś Ci przeszkadza albo czegoś brakuje? Napisz albo powiedz „popraw program: …”. Prośba bez nazwisk "
             "i numerów trafia do samonaprawy NotarAI; zmiana przychodzi jako aktualizacja, a program mówi „Twoja zmiana już działa”.",
     "you": "popraw program: kalendarz ma pokazywać cały tydzień", "notarai": "Przyjąłem prośbę Z-3F2A1C. Gdy zadziała, powiem Ci o tym tutaj.",
     "try": "tryb serwisowy"},
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
