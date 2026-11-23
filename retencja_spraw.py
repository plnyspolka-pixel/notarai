"""Jak dlugo kopie spraw leza na serwerze notarai - wybiera notariusz.

Ustawienia kancelarii (ustawienia_kancelarii.py):
  - przechowywanie_spraw: bez_limitu | 30_dni | ... | 5_lat - liczone od
    ostatniej zmiany w sprawie (nie od zalozenia: sprawa, ktora czeka na
    dokumenty, nie zniknie w polowie pracy),
  - usuwanie_spraw: "przypominaj" - sprawa po terminie jest oznaczona na
    liscie spraw, usuwa ja notariusz; "automatycznie" - serwer usuwa ja sam.

Usuniecie automatyczne robi dokladnie to, co przycisk "Usun sprawe": kasuje
pliki z dysku i z S3 razem ze starszymi wersjami, zdejmuje wskazania sprawy
z kalendarza i ksiag przesylek. Kopia zapasowa (AWS Backup) wygasa sama
najpozniej po DniPrzechowania (infra/notarai-kopia.yaml, 21 dni).

Bezpieczniki:
  - karencja (ustawienia_kancelarii.KARENCJA_DNI): po wlaczeniu albo
    zaostrzeniu automatycznego usuwania pierwsze sprawy znikaja dopiero po
    tylu dniach; do tego czasu lista spraw mowi, co i kiedy zniknie,
  - kancelaria, ktora trzyma pliki u siebie, nie ma nic na serwerze - pomijamy,
  - przy bledzie odczytu ustawien nie usuwamy niczego (wczytaj() daje wtedy
    domyslne "bez_limitu").

Kiedy to sie dzieje: przy otwarciu listy spraw (najwyzej raz na kilka godzin
na kancelarie) i w watku w tle raz na dobe dla wszystkich kancelarii
(PIECZAPP_RETENCJA=true, w chmurze). Kilka kopii aplikacji naraz nie szkodzi:
usuniecie jest idempotentne.

Zero danych osobowych w logach: identyfikatory spraw i liczby.
"""
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Request

import config
import kalendarz
import magazyn
import przesylki
import ustawienia_kancelarii

log = logging.getLogger("pieczapp.retencja")

ODSTEP_SPRZATANIA_S = 6 * 3600
_ostatnie_sprzatanie: dict[str, float] = {}
_BLOKADA = threading.Lock()


def usun_sprawe(identyfikator: str, katalog: Path | None = None) -> int:
    """Pelne usuniecie sprawy (to samo dla przycisku i dla retencji)."""
    katalog = katalog or (config.SPRAWY / identyfikator)
    usuniete = magazyn.usun_sprawe(katalog)
    kalendarz.usun_sprawe(identyfikator)
    przesylki.usun_sprawe(identyfikator)
    return usuniete


def terminy(baza: Path | None = None, teraz: datetime | None = None) -> dict:
    """{id sprawy: {"ostatnia_zmiana", "usuniecie", "po_terminie", "usunie_serwer"}}.

    Puste, gdy kancelaria nie ustawila limitu albo trzyma pliki u siebie.
    "usuniecie" to dzien, od ktorego sprawa jest po terminie (przy
    automatycznym usuwaniu: kiedy najwczesniej zniknie - z karencja).
    """
    if magazyn.u_klienta():
        return {}
    ustawienia = ustawienia_kancelarii.wczytaj()
    dni = ustawienia_kancelarii.dni_przechowania(ustawienia)
    if dni is None:
        return {}
    teraz = teraz or datetime.now()
    automatycznie = ustawienia["usuwanie_spraw"] == "automatycznie"
    od = ustawienia_kancelarii.usuwanie_od(ustawienia)
    wynik = {}
    for id_sprawy, chwila in magazyn.daty_zmian_spraw(baza or config.SPRAWY).items():
        zmiana = datetime.fromtimestamp(chwila)
        termin = zmiana + timedelta(days=dni)
        kiedy = max(termin, od) if (automatycznie and od) else termin
        wynik[id_sprawy] = {
            "ostatnia_zmiana": zmiana.isoformat(timespec="seconds"),
            "usuniecie": kiedy.isoformat(timespec="seconds"),
            "po_terminie": termin <= teraz,
            "usunie_serwer": automatycznie,
        }
    return wynik


def sprzataj(baza: Path | None = None, teraz: datetime | None = None) -> list[str]:
    """Usuwa sprawy po terminie, gdy kancelaria wybrala usuwanie automatyczne.

    Zwraca identyfikatory usunietych spraw biezacej kancelarii."""
    if magazyn.u_klienta():
        return []
    ustawienia = ustawienia_kancelarii.wczytaj()
    od = ustawienia_kancelarii.usuwanie_od(ustawienia)
    teraz = teraz or datetime.now()
    if od is None or teraz < od:
        return []   # usuwanie reczne, bez limitu albo jeszcze trwa karencja
    usuniete = []
    baza = baza or config.SPRAWY
    for id_sprawy, termin in terminy(baza, teraz).items():
        if not termin["po_terminie"] or not id_sprawy.isalnum():
            continue
        try:
            obiektow = usun_sprawe(id_sprawy, baza / id_sprawy)
        except Exception as blad:  # noqa: BLE001 - nastepna proba przy kolejnym sprzataniu
            log.warning("retencja: sprawa %s nieusunieta (%s)", id_sprawy, type(blad).__name__)
            continue
        usuniete.append(id_sprawy)
        log.info("retencja: sprawa %s usunieta po terminie przechowania, obiektow w S3: %d",
                 id_sprawy, obiektow)
    if usuniete:
        log.info("retencja: kancelaria %s - usunieto %d spraw po terminie", magazyn.kancelaria(), len(usuniete))
    return usuniete


def sprzataj_co_jakis_czas() -> list[str]:
    """Wywolywane przy liscie spraw: najwyzej raz na ODSTEP_SPRZATANIA_S."""
    k = magazyn.kancelaria()
    with _BLOKADA:
        if time.time() - _ostatnie_sprzatanie.get(k, 0.0) < ODSTEP_SPRZATANIA_S:
            return []
        _ostatnie_sprzatanie[k] = time.time()
    try:
        return sprzataj()
    except Exception as blad:  # noqa: BLE001 - lista spraw musi sie otworzyc
        log.warning("retencja: sprzatanie przy liscie spraw nieudane (%s)", type(blad).__name__)
        return []


def sprzataj_wszystkie() -> dict:
    """Przechodzi po wszystkich kancelariach z rejestru (tryb wielu kancelarii)."""
    import autoryzacja
    wynik = {"kancelarii": 0, "usunieto": 0}
    for wpis in autoryzacja._wczytaj_rejestr().values():
        if wpis.get("przechowywanie", "chmura") == "u-klienta":
            continue
        zk = magazyn.kancelaria_var.set(wpis["id"])
        zp = magazyn.przechowywanie_var.set("chmura")
        try:
            wynik["kancelarii"] += 1
            wynik["usunieto"] += len(sprzataj())
        except Exception as blad:  # noqa: BLE001 - jedna kancelaria nie zatrzymuje reszty
            log.warning("retencja: kancelaria %s pominieta (%s)", wpis["id"], type(blad).__name__)
        finally:
            magazyn.kancelaria_var.reset(zk)
            magazyn.przechowywanie_var.reset(zp)
    log.info("retencja: przejrzano %d kancelarii, usunieto %d spraw", wynik["kancelarii"], wynik["usunieto"])
    return wynik


def uruchom_w_tle() -> threading.Event | None:
    """Petla raz na dobe, gdy PIECZAPP_RETENCJA=true (w chmurze)."""
    if os.getenv("PIECZAPP_RETENCJA", "").lower() != "true":
        return None
    stop = threading.Event()

    def petla():
        if stop.wait(300):      # nie na starcie - sonda /zdrowie ma pierwszenstwo
            return
        while True:
            try:
                sprzataj_wszystkie()
            except Exception as blad:  # noqa: BLE001
                log.warning("retencja: przebieg nieudany (%s)", type(blad).__name__)
            if stop.wait(24 * 3600):
                return

    threading.Thread(target=petla, daemon=True, name="retencja-spraw").start()
    return stop


router_admina = APIRouter(prefix="/api/admin/retencja", tags=["admin"])


@router_admina.post("")
def sprzataj_teraz(request: Request):
    """Reczne uruchomienie przebiegu z panelu administratora."""
    import autoryzacja
    autoryzacja._wymagaj_admina(request)
    return sprzataj_wszystkie()
