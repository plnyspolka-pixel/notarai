"""Okno pomocnika notarai - lewa polowa ekranu.

Raz ustawiasz i zapominasz. Pierwsze uruchomienie pokazuje kod i samo otwiera
notarai w przegladarce - notariusz klika tam "Polacz" i to wszystko. Zadnego
tokenu do kopiowania. Od tej chwili pomocnik po kazdym uruchomieniu laczy sie
sam, przeczekuje zerwane lacze, a gdy ktos odlaczy komputer w notarai, sam
wraca do ekranu z kodem.

Token tego komputera lezy w %LOCALAPPDATA%\\notarai\\pomocnik.json i nie
wychodzi poza ten komputer. Otwiera wylacznie odbieranie zlecen pomocnika -
spraw kancelarii nim nie obejrzysz.

Dziennik pokazuje czynnosci i liczby, nigdy numerow ani wartosci pol - ten sam
rygor co w logach serwera, bo notariusz pracuje przy ludziach i to okno bywa
widoczne zza biurka.
"""
from __future__ import annotations

import json
import logging
import os
import platform
import queue
import threading
import webbrowser
from pathlib import Path

from pomocnik import klient, przegladarka, zadania

log = logging.getLogger("notarai.pomocnik")

ADRES_DOMYSLNY = "https://app.notarai.pl"


def plik_ustawien() -> Path:
    katalog = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "notarai"
    katalog.mkdir(parents=True, exist_ok=True)
    return katalog / "pomocnik.json"


def wczytaj_ustawienia() -> dict:
    try:
        return json.loads(plik_ustawien().read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def zapisz_ustawienia(adres: str, token: str) -> None:
    plik_ustawien().write_text(
        json.dumps({"adres": adres, "token": token}, ensure_ascii=False), encoding="utf-8")


def adres_notarai(ustawienia: dict) -> str:
    """Adres zmienia tylko wsparcie techniczne - plikiem albo zmienna srodowiska."""
    return (os.environ.get("NOTARAI_ADRES") or ustawienia.get("adres")
            or ADRES_DOMYSLNY).rstrip("/")


def nazwa_komputera() -> str:
    return platform.node() or "Komputer"


def adres_polaczenia(adres: str, kod: str) -> str:
    """Strona notarai, ktora od razu pyta "Polaczyc ten komputer?"."""
    return f"{adres}/#polacz={kod}"


class Sterownik:
    """Caly cykl zycia pomocnika w jednym watku: laczenie, praca, ponowne laczenie.

    Okno tylko wyswietla to, co sterownik wrzuca do kolejki:
      ("stan", "laczenie" | "kod" | "polaczony" | "zatrzymany", tekst)
      ("dziennik", tekst)
    """

    def __init__(self, wydarzenia: queue.Queue, otworz_strone=webbrowser.open,
                 wykonawcy=None, nowy_klient=klient.Notarai):
        self._wydarzenia = wydarzenia
        self._otworz_strone = otworz_strone
        self._wykonawcy = wykonawcy if wykonawcy is not None else zadania.WYKONAWCY
        self._nowy_klient = nowy_klient
        self._stop = threading.Event()
        self._watek: threading.Thread | None = None
        self.adres = ""
        self.ostatni_kod = ""

    def _stan(self, stan: str, tekst: str = "") -> None:
        self._wydarzenia.put(("stan", stan, tekst))

    def _dziennik(self, tekst: str) -> None:
        self._wydarzenia.put(("dziennik", tekst))

    def _dziala(self) -> bool:
        return not self._stop.is_set()

    def _spij(self, sekundy: float) -> None:
        self._stop.wait(sekundy)

    def start(self) -> None:
        if self._watek and self._watek.is_alive():
            return
        self._stop.clear()
        self._watek = threading.Thread(target=self.cykl, daemon=True)
        self._watek.start()

    def stop(self) -> None:
        self._stop.set()

    def otworz_polaczenie(self) -> None:
        if self.ostatni_kod:
            self._otworz_strone(adres_polaczenia(self.adres, self.ostatni_kod))

    def cykl(self) -> None:
        ustawienia = wczytaj_ustawienia()
        self.adres = adres_notarai(ustawienia)
        token = ustawienia.get("token", "")
        while self._dziala():
            if not token:
                token = self._polacz()
                if not token:
                    break
                zapisz_ustawienia(self.adres, token)
                self._dziennik("Komputer połączony z kancelarią.")
            self._stan("polaczony", "Połączony z notarai. Pomocnik działa sam - "
                                    "możesz zminimalizować to okno.")
            try:
                klient.pracuj(self._nowy_klient(adres=self.adres, token=token),
                              self._wykonawcy, dziala=self._dziala, spij=self._spij)
            except klient.BladTokenu:
                self._dziennik("Ten komputer odłączono od kancelarii. "
                               "Pokazuję nowy kod połączenia.")
                token = ""
                zapisz_ustawienia(self.adres, "")
            except Exception as blad:  # noqa: BLE001 - bez tresci zlecen w oknie
                self._dziennik(f"Błąd pomocnika: {type(blad).__name__}. Ponawiam.")
                self._spij(klient.PRZERWA_PO_BLEDZIE_S)
        self._stan("zatrzymany", "Zatrzymany.")

    def _polacz(self) -> str | None:
        self._stan("laczenie", "Łączę się z notarai…")

        def pokaz_kod(kod: str) -> None:
            self.ostatni_kod = kod
            self._stan("kod", kod)
            self._otworz_strone(adres_polaczenia(self.adres, kod))

        return klient.polacz(self._nowy_klient(adres=self.adres), nazwa_komputera(),
                             pokaz_kod, dziala=self._dziala, spij=self._spij)

    def odlacz_ten_komputer(self) -> None:
        """Na zyczenie notariusza: token przestaje dzialac takze w notarai."""
        token = wczytaj_ustawienia().get("token", "")
        if token:
            try:
                self._nowy_klient(adres=self.adres, token=token).odlacz()
            except klient.BladPolaczenia:
                pass  # i tak zapominamy token; w notarai mozna odlaczyc recznie
        zapisz_ustawienia(self.adres, "")
        self._dziennik("Odłączyłem ten komputer od kancelarii.")
        self.stop()


def uruchom() -> None:  # pragma: no cover - warstwa okienkowa
    import tkinter as tk
    from tkinter import messagebox, scrolledtext

    wydarzenia: queue.Queue = queue.Queue()
    sterownik = Sterownik(wydarzenia)

    korzen = tk.Tk()
    korzen.title("notarai - pomocnik")
    szerokosc_ekranu = korzen.winfo_screenwidth()
    wysokosc_ekranu = korzen.winfo_screenheight()
    polowa = max(szerokosc_ekranu // 2, 640)
    korzen.geometry(f"{polowa}x{wysokosc_ekranu - 80}+0+0")

    ramka = tk.Frame(korzen, padx=16, pady=16)
    ramka.pack(fill="both", expand=True)

    tk.Label(ramka, text="notarai – pomocnik", font=("Segoe UI", 16, "bold")).pack(anchor="w")
    tk.Label(ramka, justify="left", wraplength=polowa - 60, fg="#555",
             text="Wykonuje na tym komputerze to, co musi dziać się w Twojej "
                  "przeglądarce: sprawdzenia w rejestrach i wypełnianie formularzy. "
                  "Nigdy nie wysyła, nie składa ani nie podpisuje.").pack(anchor="w", pady=(4, 14))

    stan = tk.Label(ramka, text="Uruchamiam…", fg="#555", font=("Segoe UI", 11, "bold"),
                    justify="left", wraplength=polowa - 60)
    stan.pack(anchor="w")

    # Ekran laczenia: widoczny tylko, dopoki komputer nie jest polaczony.
    laczenie = tk.Frame(ramka)
    kod_etykieta = tk.Label(laczenie, text="", font=("Consolas", 34, "bold"), fg="#c96442")
    kod_etykieta.pack(anchor="w", pady=(6, 4))
    tk.Label(laczenie, justify="left", wraplength=polowa - 60, fg="#555",
             text="Otworzyłem notarai w przeglądarce. Kliknij tam „Połącz” - "
                  "i gotowe, nic więcej nie trzeba wpisywać. Jeśli strona się nie "
                  "otworzyła, wejdź w notarai w menu Pomocnik i wpisz ten kod."
             ).pack(anchor="w")
    tk.Button(laczenie, text="Otwórz notarai jeszcze raz",
              command=sterownik.otworz_polaczenie).pack(anchor="w", pady=(8, 0))

    pasek = tk.Frame(ramka)
    pasek.pack(fill="x", pady=(14, 10))
    tk.Button(pasek, text="Otwórz przeglądarkę do rejestrów",
              command=lambda: otworz_przegladarke()).pack(side="left")
    przycisk_odlacz = tk.Button(pasek, text="Odłącz ten komputer",
                                command=lambda: odlacz())

    widok = scrolledtext.ScrolledText(ramka, height=16, state="disabled", wrap="word")
    widok.pack(fill="both", expand=True)

    def dopisz(wiersz: str) -> None:
        widok.configure(state="normal")
        widok.insert("end", wiersz + "\n")
        widok.see("end")
        widok.configure(state="disabled")

    def otworz_przegladarke() -> None:
        try:
            przegladarka.uruchom(ekran=(szerokosc_ekranu, wysokosc_ekranu))
            dopisz("Otworzyłem przeglądarkę do rejestrów po prawej stronie.")
        except RuntimeError as blad:
            messagebox.showerror("notarai", str(blad))

    def odlacz() -> None:
        if not messagebox.askyesno(
                "notarai", "Odłączyć ten komputer od kancelarii?\n"
                "Pomocnik przestanie odbierać zlecenia, a przy następnym "
                "uruchomieniu poprosi o ponowne połączenie."):
            return
        threading.Thread(target=sterownik.odlacz_ten_komputer, daemon=True).start()

    def pokaz_stan(rodzaj: str, tekst: str) -> None:
        kolory = {"polaczony": "#15803d", "kod": "#1f1e1b", "laczenie": "#555",
                  "zatrzymany": "#b45309"}
        if rodzaj == "kod":
            kod_etykieta.configure(text=tekst)
            stan.configure(text="Połącz ten komputer z kancelarią", fg=kolory["kod"])
            laczenie.pack(anchor="w", fill="x", after=stan)
        else:
            stan.configure(text=tekst, fg=kolory.get(rodzaj, "#555"))
            if rodzaj != "laczenie":
                laczenie.pack_forget()
        if rodzaj == "polaczony":
            przycisk_odlacz.pack(side="left", padx=8)
        else:
            przycisk_odlacz.pack_forget()
        if rodzaj == "zatrzymany":
            dopisz("Pomocnik zatrzymany. Uruchom go ponownie, żeby połączyć komputer.")

    def odswiezaj() -> None:
        while True:
            try:
                wydarzenie = wydarzenia.get_nowait()
            except queue.Empty:
                break
            if wydarzenie[0] == "stan":
                pokaz_stan(wydarzenie[1], wydarzenie[2])
            else:
                dopisz(wydarzenie[1])
        korzen.after(300, odswiezaj)

    korzen.after(300, odswiezaj)
    sterownik.start()
    korzen.mainloop()
