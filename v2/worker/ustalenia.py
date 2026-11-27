"""Local extraction of explicitly spoken calendar dates and follow-up items."""
import re
from datetime import datetime

_DATA = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{4})(?!\d)")
_MIESIACE = ("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
             "lipca", "sierpnia", "września", "października", "listopada", "grudnia")
_DATA_SLOWNA = re.compile(r"(?<!\d)(\d{1,2})\s+(" + "|".join(_MIESIACE) + r")\s+(\d{4})(?!\d)", re.I)
_GODZINA = re.compile(r"(?<!\d)([01]?\d|2[0-3])[:.]([0-5]\d)(?!\d)")
_SPOTKANIE = re.compile(r"spotkani|wizyt|termin|odczyt|podpis|um[oó]w", re.I)
_DOKUMENT = re.compile(r"dosł|dostarc|brakuj|przynie|załącz|potrzebuj", re.I)
_USTALENIE = re.compile(r"ustal|uzgodni|zobowiąz|potwierdz", re.I)


def propozycje(segmenty):
    wynik = []
    for segment in segmenty:
        tekst = segment["tekst"].strip()
        data = _DATA.search(tekst)
        data_slowna = _DATA_SLOWNA.search(tekst)
        godzina = _GODZINA.search(_DATA.sub("", tekst))
        termin = None
        if (data or data_slowna) and godzina and _SPOTKANIE.search(tekst):
            try:
                if data:
                    zapis = data[1].replace("/", ".")
                    format_daty = "%Y-%m-%d" if "-" in zapis else "%d.%m.%Y"
                    dzien = datetime.strptime(zapis, format_daty)
                else:
                    dzien = datetime(int(data_slowna[3]), _MIESIACE.index(data_slowna[2].lower()) + 1, int(data_slowna[1]))
                termin = dzien.replace(
                    hour=int(godzina[1]), minute=int(godzina[2])
                ).isoformat(timespec="minutes")
            except ValueError:
                pass
        rodzaj = ("termin" if termin else "dokument" if _DOKUMENT.search(tekst)
                  else "ustalenie" if _USTALENIE.search(tekst) or _SPOTKANIE.search(tekst) else None)
        if rodzaj:
            wynik.append({"rodzaj": rodzaj, "tekst": tekst, "termin": termin, "sekunda": segment["sekunda"]})
    return wynik
