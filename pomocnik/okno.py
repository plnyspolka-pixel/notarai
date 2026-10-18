"""Okno pomocnika notarai - lewa polowa ekranu.

Jedno okno, trzy rzeczy: czy pomocnik jest polaczony, przycisk do otwarcia
przegladarki do rejestrow i dziennik tego, co sie wydarzylo. Token kancelarii
wklejasz raz; lezy w %LOCALAPPDATA%\\notarai\\pomocnik.json i nie wychodzi
poza ten komputer.

Dziennik pokazuje czynnosci i liczby, nigdy numerow ani wartosci pol - ten sam
rygor co w logach serwera, bo notariusz pracuje przy ludziach i to okno bywa
widoczne zza biurka.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
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


class Pomocnik:
    """Petla pomocnika w osobnym watku, zeby okno nie zamarzalo."""

    def __init__(self, dziennik: queue.Queue):
        self._watek: threading.Thread | None = None
        self._stop = threading.Event()
        self._dziennik = dziennik

    @property
    def dziala(self) -> bool:
        return bool(self._watek and self._watek.is_alive())

    def start(self, adres: str, token: str) -> None:
        if self.dziala:
            return
        self._stop.clear()
        notarai = klient.Notarai(adres=adres, token=token)

        def pracuj():
            self._dziennik.put("Połączony. Czekam na zlecenia z notarai.")
            try:
                klient.pracuj(notarai, zadania.WYKONAWCY,
                              dziala=lambda: not self._stop.is_set())
            except Exception as blad:  # noqa: BLE001 - bez tresci zlecen w oknie
                self._dziennik.put(f"Zatrzymany: {type(blad).__name__}")
            else:
                self._dziennik.put("Zatrzymany.")

        self._watek = threading.Thread(target=pracuj, daemon=True)
        self._watek.start()

    def stop(self) -> None:
        self._stop.set()


def uruchom() -> None:  # pragma: no cover - warstwa okienkowa
    import tkinter as tk
    from tkinter import messagebox, scrolledtext

    ustawienia = wczytaj_ustawienia()
    dziennik: queue.Queue[str] = queue.Queue()
    pomocnik = Pomocnik(dziennik)

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

    tk.Label(ramka, text="Adres notarai").pack(anchor="w")
    pole_adresu = tk.Entry(ramka)
    pole_adresu.insert(0, ustawienia.get("adres") or ADRES_DOMYSLNY)
    pole_adresu.pack(fill="x", pady=(0, 10))

    tk.Label(ramka, text="Token kancelarii").pack(anchor="w")
    pole_tokenu = tk.Entry(ramka, show="•")
    pole_tokenu.insert(0, ustawienia.get("token") or "")
    pole_tokenu.pack(fill="x", pady=(0, 10))

    stan = tk.Label(ramka, text="Nie połączony", fg="#b45309", font=("Segoe UI", 10, "bold"))
    stan.pack(anchor="w", pady=(0, 10))

    pasek = tk.Frame(ramka)
    pasek.pack(fill="x", pady=(0, 10))
    przycisk_polacz = tk.Button(pasek, text="Połącz")
    przycisk_polacz.pack(side="left")
    tk.Button(pasek, text="Otwórz przeglądarkę do rejestrów",
              command=lambda: otworz_przegladarke()).pack(side="left", padx=8)

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

    def przelacz() -> None:
        if pomocnik.dziala:
            pomocnik.stop()
            przycisk_polacz.configure(text="Połącz")
            stan.configure(text="Nie połączony", fg="#b45309")
            return
        adres = pole_adresu.get().strip()
        token = pole_tokenu.get().strip()
        if not token:
            messagebox.showwarning("notarai", "Wklej token kancelarii z notarai.")
            return
        zapisz_ustawienia(adres, token)
        pomocnik.start(adres, token)
        przycisk_polacz.configure(text="Rozłącz")
        stan.configure(text="Połączony", fg="#15803d")

    przycisk_polacz.configure(command=przelacz)

    def odswiezaj() -> None:
        while True:
            try:
                dopisz(dziennik.get_nowait())
            except queue.Empty:
                break
        if not pomocnik.dziala and przycisk_polacz["text"] == "Rozłącz":
            przycisk_polacz.configure(text="Połącz")
            stan.configure(text="Nie połączony", fg="#b45309")
        korzen.after(500, odswiezaj)

    dopisz("Wklej token kancelarii i kliknij Połącz.")
    korzen.after(500, odswiezaj)
    korzen.mainloop()
