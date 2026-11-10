"""Taksonomia dokumentow notarialnych i klasyfikator bez udzialu modelu.

Trzy drzewa kategorii, ktorych notariusz nigdy nie wybiera recznie -
system dopasowuje je sam z tresci:

  RODZAJE  - rodzaj czynnosci / dokumentu (sprzedaz, darowizna, testament...),
  CZESCI   - czesc aktu, do ktorej nalezy klauzula (komparycja, pouczenia...),
  OBSZARY  - czego dotyczy zasada kancelarii (slownictwo, kwoty, daty...).

Klasyfikacja jest deterministyczna: punkty za slowa kluczowe na tekscie
bez polskich znakow i bez wielkich liter. Dzieki temu dziala offline,
w testach i bez kosztu wywolania Bedrock, a wynik da sie wytlumaczyc
("rozpoznane po: sprzedaje, cena, kupujacy").

Dodanie kategorii = dopisanie wpisu do slownika; reszta (UI, zasady,
profil stylu) bierze liste stad.
"""
import re
import unicodedata

_ZAMIANY = str.maketrans({"ł": "l", "Ł": "L"})


def bez_ogonkow(tekst: str) -> str:
    """'Stawający ŁĄKA' -> 'stawajacy laka'. Do porownan, nigdy do wyswietlania."""
    tekst = (tekst or "").translate(_ZAMIANY)
    tekst = unicodedata.normalize("NFKD", tekst)
    return "".join(z for z in tekst if not unicodedata.combining(z)).lower()


# ---------------------------------------------------------------------------
# Rodzaje czynnosci. Slowa kluczowe: (wzorzec na tekscie bez ogonkow, waga).
# Wzorce sa rdzeniami - "sprzeda" lapie sprzedaje, sprzedazy, sprzedajacy.
# ---------------------------------------------------------------------------
RODZAJE: dict[str, dict] = {
    "sprzedaz": {
        "nazwa": "Umowa sprzedaży",
        "slowa": [(r"umow\w* sprzedazy", 6), (r"\bsprzeda", 3), (r"\bkupuj", 3),
                  (r"\bcen[aeyi]\b", 2), (r"\bnabywc", 1), (r"\bzbywc", 1)],
    },
    "sprzedaz_rolna": {
        "nazwa": "Sprzedaż nieruchomości rolnej",
        "slowa": [(r"ksztaltowaniu ustroju rolnego", 6), (r"nieruchomosc\w* roln", 5),
                  (r"rolnik\w* indywidualn", 4), (r"gospodarstw\w* roln", 3),
                  (r"krajow\w* osrod\w* wsparcia rolnictwa|\bkowr\b", 4), (r"prawo pierwokupu", 2)],
    },
    "darowizna": {
        "nazwa": "Umowa darowizny",
        "slowa": [(r"umow\w* darowizny", 6), (r"\bdaruj", 4), (r"\bdarowizn", 3),
                  (r"\bobdarowan", 3), (r"\bdarczyn", 3), (r"grupy podatkowej", 2)],
    },
    "zamiana": {
        "nazwa": "Umowa zamiany",
        "slowa": [(r"umow\w* zamiany", 6), (r"\bzamieni\w* sie", 3), (r"w zamian za", 1)],
    },
    "przedwstepna": {
        "nazwa": "Umowa przedwstępna",
        "slowa": [(r"przedwstepn", 6), (r"umowy przyrzeczonej|umowe przyrzeczon", 4),
                  (r"\bzadatk|\bzadatek", 2), (r"zobowiazuj\w* sie zawrzec", 3)],
    },
    "deweloperska": {
        "nazwa": "Umowa deweloperska",
        "slowa": [(r"deweloper", 6), (r"mieszkaniow\w* rachun\w* powierniczy", 5),
                  (r"deweloperski\w* fundusz\w* gwarancyjn", 4), (r"prospekt\w* informacyjn", 3)],
    },
    "odrebna_wlasnosc": {
        "nazwa": "Ustanowienie odrębnej własności lokalu",
        "slowa": [(r"ustanowi\w* odrebn\w* wlasnosc", 6), (r"wlasnosci lokali", 3),
                  (r"samodzielnosci lokalu", 4), (r"czesci wspolnej nieruchomosci", 2)],
    },
    "sluzebnosc": {
        "nazwa": "Ustanowienie służebności",
        "slowa": [(r"sluzebnos", 6), (r"przesylu", 2), (r"drogi koniecznej", 3),
                  (r"nieruchomosc\w* wladnac", 4), (r"nieruchomosc\w* obciazon", 2)],
    },
    "hipoteka": {
        "nazwa": "Ustanowienie hipoteki",
        "slowa": [(r"ustanawia\w* hipotek|ustanowieni\w* hipotek", 6), (r"\bhipotek", 2),
                  (r"\bwierzyciel", 2), (r"zabezpieczeni\w* wierzytelnosci", 3)],
    },
    "poddanie_egzekucji": {
        "nazwa": "Poddanie się egzekucji",
        "slowa": [(r"poddaj\w* sie egzekucji|poddani\w* sie egzekucji", 7),
                  (r"art\.? ?777", 6), (r"tytulu wykonawcz", 2)],
    },
    "pelnomocnictwo": {
        "nazwa": "Pełnomocnictwo",
        "slowa": [(r"\bpelnomocnictw", 6), (r"\bupowaznia", 3), (r"\bmocodawc", 4),
                  (r"\bpelnomocnik", 2), (r"do dokonywania w (jego|jej|ich) imieniu", 3)],
    },
    "testament": {
        "nazwa": "Testament",
        "slowa": [(r"\btestament", 7), (r"\bspadkobierc", 2), (r"powoluj\w* do (calego )?spadku", 5),
                  (r"\bzapis\w* windykacyjn", 4), (r"na wypadek (mojej )?smierci", 4),
                  (r"\bodwoluj\w*.{0,30}testament", 3)],
    },
    "poswiadczenie_dziedziczenia": {
        "nazwa": "Akt poświadczenia dziedziczenia",
        "slowa": [(r"poswiadczeni\w* dziedziczenia", 8), (r"protokol\w* dziedziczenia", 6),
                  (r"\bspadkodawc", 3), (r"\bspadkobierc", 2), (r"dziedzicz", 2)],
    },
    "dzial_spadku": {
        "nazwa": "Dział spadku",
        "slowa": [(r"dzia\w* spadku", 7), (r"\bspadk", 1), (r"\bsplat", 1), (r"\bdoplat", 2)],
    },
    "zniesienie_wspolwlasnosci": {
        "nazwa": "Zniesienie współwłasności",
        "slowa": [(r"znies\w* wspolwlasnosci", 7), (r"\bwspolwlasnosc", 1)],
    },
    "podzial_majatku": {
        "nazwa": "Podział majątku wspólnego",
        "slowa": [(r"podzia\w* majatku wspolnego", 7), (r"ustani\w* wspolnosci majatkowej", 3),
                  (r"\brozwod", 2), (r"\bseparacj", 2)],
    },
    "intercyza": {
        "nazwa": "Umowa majątkowa małżeńska",
        "slowa": [(r"umow\w* majatkow\w* malzensk", 7), (r"\bintercyz", 6),
                  (r"rozdzielnosc\w* majatkow", 5), (r"wylaczeni\w* wspolnosci", 3),
                  (r"\b47 ?(\^|1)? kodeksu rodzinnego|art\.? ?47", 2)],
    },
    "dozywocie": {
        "nazwa": "Umowa dożywocia",
        "slowa": [(r"\bdozywoci", 7), (r"\bdozywotnik", 5), (r"dozywotniej opieki|pomoc i pielegnacj", 3)],
    },
    "spolka": {
        "nazwa": "Umowa spółki / sprawy korporacyjne",
        "slowa": [(r"umow\w* spolki", 6), (r"z ograniczona odpowiedzialnoscia|sp\.? z o\.?o", 4),
                  (r"kapital\w* zakladow", 4), (r"\budzial\w* o wartosci nominalnej", 4),
                  (r"\bzarzad\w* spolki", 2), (r"spolk\w* akcyjn|spolk\w* komandytow", 4)],
    },
    "protokol": {
        "nazwa": "Protokół (zgromadzenia, walnego)",
        "slowa": [(r"\bprotokol\b|\bprotokolu\b", 3), (r"nadzwyczajn\w* zgromadzeni|walne\w* zgromadzeni", 6),
                  (r"\buchwal", 3), (r"porzadk\w* obrad", 4), (r"przewodnicz\w* zgromadzeni", 4)],
    },
    "oswiadczenie": {
        "nazwa": "Oświadczenie (przyjęcie / odrzucenie spadku, zgoda)",
        "slowa": [(r"odrzuc\w* spadek|odrzuceni\w* spadku", 7), (r"przyj\w* spadek|przyjeci\w* spadku", 6),
                  (r"dobrodziejstwem inwentarza", 4), (r"wyraz\w* zgod", 2)],
    },
}

RODZAJ_INNY = "inny"
NAZWA_INNEGO = "Inny dokument"

# ---------------------------------------------------------------------------
# Czesci aktu. Kolejnosc slownika = typowa kolejnosc w akcie notarialnym.
# ---------------------------------------------------------------------------
CZESCI: dict[str, dict] = {
    "naglowek": {
        "nazwa": "Nagłówek i oznaczenie aktu",
        "slowa": [(r"\brepertorium\b|\brep\.? ?a\b", 6), (r"akt notarialny", 6),
                  (r"przed notariusz\w*", 4), (r"w kancelarii notarialnej", 3)],
    },
    "komparycja": {
        "nazwa": "Komparycja (stawający)",
        "slowa": [(r"stawil\w* sie|stawiaj|stawaj", 5), (r"\bpesel\b", 3), (r"dowod\w* osobist", 3),
                  (r"\bzamieszkal", 3), (r"\b(syn|corka)\b", 2), (r"tozsamosc", 4),
                  (r"dzialaj\w* w imieniu|reprezentuj", 2), (r"\bpaszport", 2)],
    },
    "stan_prawny": {
        "nazwa": "Stan prawny i przedmiot",
        "slowa": [(r"ksieg\w* wieczyst|\bkw\b", 3), (r"\bdzial\w* (i|ii|iii|iv)\b", 3),
                  (r"jest wlascicielem|sa wlascicielami|przysluguje", 4), (r"\bdzialk", 2),
                  (r"\bobreb", 2), (r"rejestru gruntow|wypis\w* z rejestru", 3), (r"lokal\w* mieszkaln", 2),
                  (r"\bwolna od\b|nie jest obciazon|obciazon", 2), (r"powierzchni", 1)],
    },
    "oswiadczenia": {
        "nazwa": "Oświadczenia stron",
        "slowa": [(r"\boswiadcz", 4), (r"\bzapewni", 2), (r"nie toczy sie|nie jest przedmiotem", 2),
                  (r"stanu cywilnego|pozostaj\w* w (ustroju|zwiazku)", 3), (r"wspolnosci ustawowej", 2)],
    },
    "czynnosc": {
        "nazwa": "Czynność (sprzedaż, darowizna, ustanowienie...)",
        "slowa": [(r"\bsprzedaje\b|\bsprzedaja\b|\bdaruje\b|\bdaruja\b", 6), (r"\bkupuje\b|\bkupuja\b", 4),
                  (r"\bprzyjmuje\b|\bprzyjmuja\b", 3), (r"\bustanawia", 4), (r"\bprzenosi\b|\bprzenosza\b", 4),
                  (r"\budziela\b|\bpowoluje\b|\bzamieniaj", 4), (r"na rzecz\b", 1)],
    },
    "cena_zaplata": {
        "nazwa": "Cena, wartość i zapłata",
        "slowa": [(r"\bcen[aeyi]\b", 3), (r"\bzaplac|\bzaplat", 3), (r"\bslownie\b", 2),
                  (r"\bprzelew", 3), (r"\bgotowk", 3), (r"rachun\w* bankow", 2), (r"\bwartosc", 2),
                  (r"\bzadatk|\bzaliczk", 2), (r"\d[\d .]*(,\d{2})? ?zl\b", 1)],
    },
    "wydanie": {
        "nazwa": "Wydanie i posiadanie",
        "slowa": [(r"\bwydani\w*|\bwyda(je|ja|ny|na)\b", 4), (r"w posiadani|objeci\w* w posiadanie", 4),
                  (r"\bkluczy|\bklucze", 2), (r"z dniem dzisiejszym", 1), (r"ciezar\w* i pozytk", 3)],
    },
    "podatki": {
        "nazwa": "Podatki",
        "slowa": [(r"podat\w* od czynnosci cywilnoprawnych|\bpcc\b", 6), (r"podat\w* od spadkow i darowizn", 6),
                  (r"\bpodat", 3), (r"\bplatnik", 3), (r"zwolnion\w* od podatku", 3), (r"urzad\w* skarbow", 2)],
    },
    "wnioski_kw": {
        "nazwa": "Wnioski wieczystoksięgowe",
        "slowa": [(r"\bwnios\w*", 2), (r"wydzia\w* ksiag wieczystych", 5), (r"o wpis\w*|o dokonanie wpisu", 4),
                  (r"o zalozenie ksiegi|o odlaczenie|o wykreslenie", 4), (r"\bwpis\w* w dziale", 3)],
    },
    "koszty": {
        "nazwa": "Koszty, taksa i opłaty",
        "slowa": [(r"\btaks\w* notarial", 6), (r"\bpobrano\b", 4), (r"oplat\w* sadow", 4),
                  (r"\bvat\b|podatek od towarow", 3), (r"rozporzadzeni\w* ministra sprawiedliwosci", 3),
                  (r"\bkoszt\w*", 2), (r"wynagrodzeni\w* za wypis", 4)],
    },
    "pouczenia": {
        "nazwa": "Pouczenia notariusza",
        "slowa": [(r"\bpouczy|\bpouczon|\bpouczeni", 7), (r"zwrocil\w* uwage", 3),
                  (r"\bpoinformowa", 2), (r"\bskutk\w* prawn", 2), (r"tresc\w* art\w*", 2)],
    },
    "rodo": {
        "nazwa": "Ochrona danych osobowych",
        "slowa": [(r"danych osobowych|\brodo\b", 6), (r"administrator\w* danych", 5),
                  (r"przetwarzani\w* danych", 4)],
    },
    "wypisy": {
        "nazwa": "Wypisy i doręczenia",
        "slowa": [(r"\bwypis\w* (tego|niniejszego)? ?aktu", 6), (r"\bwypisy\b", 4), (r"\bwydawac\b", 2),
                  (r"\bnalezy wydac|mozna wydawac", 3)],
    },
    "zamkniecie": {
        "nazwa": "Odczytanie, przyjęcie i podpisy",
        "slowa": [(r"\bodczytan", 5), (r"przyjet\w* i podpisan", 6), (r"\bpodpisan", 2),
                  (r"\bpodpis\w*", 1), (r"\bnotariusz\b", 1)],
    },
}

CZESC_INNA = "inna"
NAZWA_INNEJ = "Pozostałe postanowienia"

# ---------------------------------------------------------------------------
# Obszary zasad kancelarii - do grupowania i opisu zasad w UI.
# Przypisuje je modul zasady.py po typie zasady; slowa sluza wytycznym,
# ktorych typu nie da sie ustalic (wtedy obszar rozpoznajemy z tresci).
# ---------------------------------------------------------------------------
OBSZARY: dict[str, dict] = {
    "slownictwo": {"nazwa": "Słownictwo i sformułowania", "ikona": "Aa",
                   "slowa": [(r"\bslow|\bzwrot|\bsformulowan|\bwyrazen|\bpisz|\buzywa|\bskrot", 2)]},
    "kwoty": {"nazwa": "Zapis kwot", "ikona": "zł",
              "slowa": [(r"\bkwot|\bcen[aeyi]\b|\bzl\b|\bzlot|\bgrosz|\bslownie", 3)]},
    "daty": {"nazwa": "Zapis dat", "ikona": "📅",
             "slowa": [(r"\bdat[aeyi]?\b|\bdnia\b|\brok\w*\b|\bmiesi", 3)]},
    "osoby": {"nazwa": "Strony i komparycja", "ikona": "👤",
              "slowa": [(r"\bkomparycj|\bstaw|\bpesel|\bnazwisk|\bimion|\bdowod|\bstron\w*\b|\bmalzon", 3)]},
    "struktura": {"nazwa": "Budowa aktu", "ikona": "§",
                  "slowa": [(r"\bparagraf|\bkolejnos|\bnumeracj|\bczesc|\bustep|\bnaglow|\bpunkt", 3)]},
    "pouczenia": {"nazwa": "Pouczenia i obowiązki notariusza", "ikona": "⚖",
                  "slowa": [(r"\bpoucz|\bart\.|\bobowiaz|\bustaw", 2)]},
    "oplaty": {"nazwa": "Opłaty, taksa i podatki", "ikona": "%",
               "slowa": [(r"\btaks|\boplat|\bpodat|\bpcc\b|\bvat\b|\bkoszt", 3)]},
    "typografia": {"nazwa": "Typografia i forma zapisu", "ikona": "¶",
                   "slowa": [(r"\bspacj|\bcudzyslow|\bwielk\w* liter|\bwersalik|\bmyslnik|\bkropk|\bprzecink", 3)]},
    "dane_osobowe": {"nazwa": "Ochrona danych", "ikona": "🔒",
                     "slowa": [(r"\brodo\b|danych osobowych|\bpesel\w* (nie|bez)", 4)]},
    "tresc": {"nazwa": "Treść obowiązkowa", "ikona": "✓",
              "slowa": [(r"\bmusi\b|\bmusza\b|\bzawsze\b.{0,30}\b(zawier|umieszcz|dodaw|wpisyw)", 2)]},
    "inne": {"nazwa": "Inne wytyczne", "ikona": "•", "slowa": []},
}

_SKOMPILOWANE: dict[int, list] = {}


def _wzorce(slownik: dict) -> list[tuple[str, list[tuple[re.Pattern, int]]]]:
    klucz = id(slownik)
    if klucz not in _SKOMPILOWANE:
        _SKOMPILOWANE[klucz] = [
            (nazwa, [(re.compile(w), waga) for w, waga in wpis.get("slowa", [])])
            for nazwa, wpis in slownik.items()
        ]
    return _SKOMPILOWANE[klucz]


def _punktuj(tekst: str, slownik: dict, limit_trafien: int = 3) -> list[tuple[str, int, list[str]]]:
    """[(kategoria, punkty, trafione slowa)], malejaco. Kazdy wzorzec liczy
    sie najwyzej `limit_trafien` razy, zeby jedno powtarzane slowo
    ("sprzedaz" x 40) nie zagluszylo reszty."""
    plaski = bez_ogonkow(tekst)
    wyniki = []
    for nazwa, wzorce in _wzorce(slownik):
        punkty, trafione = 0, []
        for wzorzec, waga in wzorce:
            ile = len(wzorzec.findall(plaski))
            if ile:
                punkty += waga * min(ile, limit_trafien)
                pierwsze = wzorzec.search(plaski)
                trafione.append(pierwsze.group(0).strip())
        if punkty:
            wyniki.append((nazwa, punkty, trafione))
    wyniki.sort(key=lambda w: -w[1])
    return wyniki


def _pewnosc(punkty: int, prog: int) -> float:
    return round(min(1.0, punkty / (punkty + prog)) if punkty else 0.0, 2)


def klasyfikuj_dokument(tekst: str, ile: int = 3) -> list[dict]:
    """Najbardziej prawdopodobne rodzaje dokumentu.

    Zwraca [{"rodzaj", "nazwa", "pewnosc", "po"}]. Pierwszy wpis jest glownym
    rodzajem; kolejne tylko wtedy, gdy maja co najmniej 40% punktow lidera
    (np. sprzedaz + sprzedaz nieruchomosci rolnej). Brak trafien = "inny".
    """
    wyniki = _punktuj(tekst, RODZAJE)
    if not wyniki or wyniki[0][1] < 4:
        return [{"rodzaj": RODZAJ_INNY, "nazwa": NAZWA_INNEGO, "pewnosc": 0.0, "po": []}]
    lider = wyniki[0][1]
    return [
        {"rodzaj": nazwa, "nazwa": RODZAJE[nazwa]["nazwa"], "pewnosc": _pewnosc(punkty, 8), "po": trafione[:4]}
        for nazwa, punkty, trafione in wyniki[:ile]
        if punkty >= 0.4 * lider
    ]


def rodzaje_dokumentu(tekst: str) -> list[str]:
    return [w["rodzaj"] for w in klasyfikuj_dokument(tekst)]


def klasyfikuj_czesc(tekst: str, poprzednia: str | None = None) -> tuple[str, float]:
    """Czesc aktu dla jednej klauzuli. `poprzednia` to czesc klauzuli
    wczesniejszej - krotki dopisek bez slow kluczowych (np. "2. drugi z
    malzonkow ...") dziedziczy ja zamiast trafiac do "pozostalych"."""
    wyniki = _punktuj(tekst, CZESCI, limit_trafien=2)
    if not wyniki or wyniki[0][1] < 3:
        if poprzednia and poprzednia != CZESC_INNA:
            return poprzednia, 0.3
        return CZESC_INNA, 0.0
    nazwa, punkty, _ = wyniki[0]
    return nazwa, _pewnosc(punkty, 6)


def obszar_z_tresci(tekst: str) -> str:
    wyniki = _punktuj(tekst, OBSZARY)
    return wyniki[0][0] if wyniki else "inne"


def rodzaje_w_zdaniu(tekst: str) -> list[str]:
    """Rodzaje czynnosci WYMIENIONE w zdaniu zasady ("w umowach sprzedazy",
    "przy darowiznach"). Tu wystarczy jedno trafienie silnego slowa -
    zdanie jest krotkie i mowi o zakresie wprost."""
    plaski = bez_ogonkow(tekst)
    znalezione = []
    for nazwa, wzorzec in _ZAKRES_RODZAJOW:
        if wzorzec.search(plaski):
            znalezione.append(nazwa)
    return znalezione


def czesci_w_zdaniu(tekst: str) -> list[str]:
    plaski = bez_ogonkow(tekst)
    return [nazwa for nazwa, wzorzec in _ZAKRES_CZESCI if wzorzec.search(plaski)]


# Krotsze wzorce do odczytania zakresu ze zdania zasady.
_ZAKRES_RODZAJOW = [(n, re.compile(w)) for n, w in [
    ("sprzedaz_rolna", r"roln"),
    ("sprzedaz", r"sprzeda"),
    ("darowizna", r"darowiz|darowan"),
    ("zamiana", r"zamian(y|ach|ie)\b"),
    ("przedwstepna", r"przedwstepn"),
    ("deweloperska", r"deweloper"),
    ("odrebna_wlasnosc", r"odrebn\w* wlasnosc"),
    ("sluzebnosc", r"sluzebnos"),
    ("hipoteka", r"hipote"),
    ("poddanie_egzekucji", r"egzekucj|\b777\b"),
    ("pelnomocnictwo", r"pelnomocnict"),
    ("testament", r"testament"),
    ("poswiadczenie_dziedziczenia", r"poswiadcz\w* dziedzicz|apd\b"),
    ("dzial_spadku", r"dzia\w* spadk"),
    ("zniesienie_wspolwlasnosci", r"zniesieni\w* wspolwlasn"),
    ("podzial_majatku", r"podzia\w* majatk"),
    ("intercyza", r"intercyz|majatkow\w* malzensk|rozdzielnos"),
    ("dozywocie", r"dozywoc"),
    ("spolka", r"spolk|spolek"),
    ("protokol", r"protokol|zgromadzen|uchwal"),
    ("oswiadczenie", r"(odrzuceni|przyjeci)\w* spadk"),
]]

_ZAKRES_CZESCI = [(n, re.compile(w)) for n, w in [
    ("naglowek", r"naglowk|repertorium"),
    ("komparycja", r"komparycj|stawajac|stawiajac"),
    ("stan_prawny", r"stan\w* prawn|opis\w* nieruchomos"),
    ("oswiadczenia", r"oswiadczeni\w* stron"),
    ("cena_zaplata", r"\bcen(y|ie|a)\b|zaplat"),
    ("wydanie", r"wydani\w* (przedmiotu|nieruchomosci|lokalu)"),
    ("podatki", r"podat"),
    ("wnioski_kw", r"wnios\w* (wieczysto|do ksiegi|kw)|wieczystoksieg"),
    ("koszty", r"taks|koszt"),
    ("pouczenia", r"poucze"),
    ("rodo", r"\brodo\b|danych osobowych"),
    ("wypisy", r"wypis"),
    ("zamkniecie", r"odczytani|podpis"),
]]


def nazwa_rodzaju(rodzaj: str) -> str:
    return RODZAJE.get(rodzaj, {}).get("nazwa", NAZWA_INNEGO)


def nazwa_czesci(czesc: str) -> str:
    return CZESCI.get(czesc, {}).get("nazwa", NAZWA_INNEJ)


def nazwa_obszaru(obszar: str) -> str:
    return OBSZARY.get(obszar, OBSZARY["inne"])["nazwa"]


def slownik_dla_ui() -> dict:
    """Etykiety wszystkich kategorii - UI nie trzyma wlasnej kopii nazw."""
    return {
        "rodzaje": {k: v["nazwa"] for k, v in RODZAJE.items()} | {RODZAJ_INNY: NAZWA_INNEGO},
        "czesci": {k: v["nazwa"] for k, v in CZESCI.items()} | {CZESC_INNA: NAZWA_INNEJ},
        "obszary": {k: {"nazwa": v["nazwa"], "ikona": v["ikona"]} for k, v in OBSZARY.items()},
    }
