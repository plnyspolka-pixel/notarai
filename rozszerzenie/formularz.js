/* Wypelnianie formularza urzedowego - zlecenie "formularz" z kolejki.

   Zlecenie przychodzi z notarai gotowe: adres formularza, selektory pol i
   wartosci. Rozszerzenie mimo to sprawdza je po swojemu, bo to ono siedzi przy
   zalogowanej sesji notariusza. Serwer moze sie pomylic albo mapowanie moze
   byc zle - ostatnie slowo ma ta strona. Te same zasady co w
   pomocnik/wykonanie.py i docs/formularze.md:

     - wypelniamy pola i zatrzymujemy sie przed wyslaniem; zlecenie, ktore
       celuje w przycisk wysylki, odrzucamy W CALOSCI,
     - tryb podgladu jest domyslny, faktyczny wymaga jawnego zadania,
     - mapowanie w statusie "szkic" nie wpisuje niczego,
     - strona musi byc ta, o ktorej mowi zlecenie, i musi byc juz otwarta -
       notariusz loguje sie sam,
     - do pola hasla ani PIN-u nie wpisujemy nigdy.

   W raporcie nie ma wartosci pol. */

const POLA_ZLECENIA = ["system", "adres", "gotowosc", "przycisk_wysylki", "kroki"];
const CZAS_NA_FORMULARZ_S = 15;

export class OdmowaWykonania extends Error {}

const maWartosc = (krok) => String(krok.wartosc ?? "").trim() !== "";

export function sprawdzKsztalt(tresc) {
  const brak = POLA_ZLECENIA.filter(p => !tresc[p] || (Array.isArray(tresc[p]) && !tresc[p].length));
  if (brak.length) throw new OdmowaWykonania("Zlecenie niekompletne: brak " + brak.join(", "));
  if (!Array.isArray(tresc.kroki)) throw new OdmowaWykonania("Zlecenie niekompletne: kroki nie są listą");
  // Samo "https://" (niedokonczone mapowanie) pasowaloby do kazdej strony.
  if (!/^(https:\/\/|http:\/\/(localhost|127\.0\.0\.1)[:/])[^/]+/.test(String(tresc.adres))) {
    throw new OdmowaWykonania("Zlecenie nie podaje pełnego adresu formularza.");
  }
}

/* Najwazniejsza kontrola: zadne pole nie moze wskazywac przycisku wysylki. */
export function sprawdzPrzyciskWysylki(tresc) {
  const wysylka = String(tresc.przycisk_wysylki).trim();
  for (const krok of tresc.kroki) {
    if (String(krok.selektor || "").trim() === wysylka) {
      throw new OdmowaWykonania(
        `Odmowa: zlecenie każe działać na przycisku wysyłki (${krok.pole || "?"}).`);
    }
  }
}

/* Co zostaloby zrobione. Nie dotyka strony. */
export function plan(tresc) {
  return (tresc.kroki || []).map(krok => ({
    pole: krok.pole || "", wykonano: false,
    uwaga: maWartosc(krok) ? "" : "brak wartości",
  }));
}

/* strona: Strona z strona.js, juz na karcie z formularzem (albo null, gdy
   takiej karty nie ma). Zwraca { kroki, bledy } - bez wartosci pol. */
export async function wykonajFormularz(zlecenie, strona) {
  const tresc = zlecenie.tresc || {};
  let raport = { kroki: [], bledy: [] };
  try {
    sprawdzKsztalt(tresc);
    sprawdzPrzyciskWysylki(tresc);
    raport.kroki = plan(tresc);
    if (tresc.tryb !== "faktyczny") return raport;
    if (tresc.status_mapowania !== "gotowe") {
      throw new OdmowaWykonania("Mapowanie ma status 'szkic' - tryb faktyczny zablokowany");
    }
    if (!strona || !(await strona.adres()).startsWith(String(tresc.adres))) {
      throw new OdmowaWykonania("Otwarta strona nie jest formularzem tego rejestru. " +
                                "Zaloguj się i otwórz właściwy formularz.");
    }
    if (await strona.ramkaZSelektorem(tresc.gotowosc, CZAS_NA_FORMULARZ_S) === null) {
      throw new OdmowaWykonania("Formularz nie jest gotowy - nie widzę pola, które powinno na nim być.");
    }
  } catch (blad) {
    raport.bledy.push(blad instanceof OdmowaWykonania ? blad.message
      : "Nie mam dostępu do strony formularza.");
    return raport;
  }

  for (const [i, krok] of tresc.kroki.entries()) {
    if (!maWartosc(krok)) continue;
    const wpis = raport.kroki[i];
    const wartosc = String(krok.wartosc).trim();
    try {
      const ramka = await strona.ramkaZSelektorem(String(krok.selektor || ""), 5);
      if (ramka === null) throw new Error("Nie znalazłem pola na stronie.");
      const el = { ramka, selektor: String(krok.selektor) };
      const typ = krok.typ || "tekst";
      if (typ === "tekst") await strona.wpisz(el, wartosc);          // pole hasla odrzuca strona.js
      else if (typ === "lista") await strona.wybierz(el, wartosc);
      else if (typ === "pole_wyboru") await strona.zaznacz(el, ["tak", "true", "1"].includes(wartosc.toLowerCase()));
      else throw new Error(`Nieznany typ pola: ${typ}`);
      wpis.wykonano = true;
    } catch (blad) {
      wpis.uwaga = String(blad && blad.message || "błąd");
      raport.bledy.push(`${wpis.pole}: ${wpis.uwaga}`);
    }
  }
  return raport;
}
