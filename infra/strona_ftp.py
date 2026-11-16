"""Strona notarai.pl na hostingu az.pl - lista, kopia i wysylka plikow przez FTPS.

Haslo przychodzi wylacznie ze zmiennej NOTARAI_FTP_HASLO, ktora uzupelnia
infra/strona.ps1 (na komputerze) albo workflow .github/workflows/strona.yml
(GitHub Actions) z sekretu notarai/strona-ftp w AWS Secrets Manager. Skrypt nie
wypisuje hasla i nie zapisuje go nigdzie.

    strona_ftp.py lista [katalog]
    strona_ftp.py kopia <katalog_zdalny> <katalog_lokalny>
    strona_ftp.py wyslij <katalog_lokalny> <katalog_zdalny>
    strona_ftp.py wyslij-zmiany <katalog_lokalny> <katalog_zdalny> [katalog_kopii]
"""

import ftplib
import hashlib
import io
import json
import os
import posixpath
import sys

HOST = "hosting2699662.online.pro"
# az.pl wymaga loginu z domena, mimo ze konto dziala we wszystkich domenach.
LOGIN = os.environ.get("NOTARAI_FTP_LOGIN", "notaraistrona@notarai.pl")


def polacz():
    haslo = os.environ.get("NOTARAI_FTP_HASLO", "")
    if not haslo or haslo.startswith("{{resolve:"):
        sys.exit("Brak hasla FTP - uruchamiaj przez infra/strona.ps1 (asm-exec).")
    ftp = ftplib.FTP_TLS(HOST, timeout=60)
    ftp.login(LOGIN, haslo)
    ftp.prot_p()
    return ftp


def wpisy(ftp, katalog):
    """Zwraca liste (nazwa, czy_katalog)."""
    try:
        return [(n, f.get("type") == "dir")
                for n, f in ftp.mlsd(katalog, facts=["type"])
                if n not in (".", "..")]
    except ftplib.error_perm:
        wynik = []
        for sciezka in ftp.nlst(katalog):
            nazwa = posixpath.basename(sciezka)
            if nazwa in (".", ".."):
                continue
            try:
                ftp.cwd(posixpath.join(katalog, nazwa))
                wynik.append((nazwa, True))
            except ftplib.error_perm:
                wynik.append((nazwa, False))
            finally:
                ftp.cwd("/")
        return wynik


def lista(ftp, katalog="/", glebokosc=2, wciecie=""):
    for nazwa, czy_kat in sorted(wpisy(ftp, katalog)):
        print(f"{wciecie}{nazwa}{'/' if czy_kat else ''}")
        if czy_kat and glebokosc > 1:
            lista(ftp, posixpath.join(katalog, nazwa), glebokosc - 1, wciecie + "  ")


def kopia(ftp, zdalny, lokalny):
    os.makedirs(lokalny, exist_ok=True)
    for nazwa, czy_kat in wpisy(ftp, zdalny):
        z = posixpath.join(zdalny, nazwa)
        l = os.path.join(lokalny, nazwa)
        if czy_kat:
            kopia(ftp, z, l)
        else:
            with open(l, "wb") as f:
                ftp.retrbinary(f"RETR {z}", f.write)
            print(f"  pobrano {z}")


def wyslij(ftp, lokalny, zdalny):
    for korzen, katalogi, pliki in os.walk(lokalny):
        katalogi[:] = [k for k in katalogi if not k.startswith(".")]
        wzgledna = os.path.relpath(korzen, lokalny).replace(os.sep, "/")
        cel = zdalny if wzgledna == "." else posixpath.join(zdalny, wzgledna)
        try:
            ftp.mkd(cel)
        except ftplib.error_perm:
            pass
        for nazwa in pliki:
            if nazwa.startswith("."):
                continue
            with open(os.path.join(korzen, nazwa), "rb") as f:
                ftp.storbinary(f"STOR {posixpath.join(cel, nazwa)}", f)
            print(f"  wyslano {posixpath.join(cel, nazwa)}")


MANIFEST = "notarai-manifest.json"


def pliki_lokalne(lokalny):
    """{sciezka_wzgledna: sha256} dla plikow strony (bez ukrytych)."""
    wynik = {}
    for korzen, katalogi, pliki in os.walk(lokalny):
        katalogi[:] = sorted(k for k in katalogi if not k.startswith("."))
        for nazwa in sorted(pliki):
            if nazwa.startswith(".") or nazwa == MANIFEST:
                continue
            sciezka = os.path.join(korzen, nazwa)
            wzgledna = os.path.relpath(sciezka, lokalny).replace(os.sep, "/")
            with open(sciezka, "rb") as f:
                wynik[wzgledna] = hashlib.sha256(f.read()).hexdigest()
    return wynik


def pobierz_manifest(ftp, zdalny):
    czesci = []
    try:
        ftp.retrbinary(f"RETR {posixpath.join(zdalny, MANIFEST)}", czesci.append)
    except ftplib.error_perm:
        return {}
    try:
        dane = json.loads(b"".join(czesci).decode("utf-8"))
    except ValueError:
        return {}
    return dane if isinstance(dane, dict) else {}


def do_wyslania(lokalne, zdalne):
    """Pliki nowe albo zmienione wzgledem manifestu z serwera."""
    return sorted(p for p, h in lokalne.items() if zdalne.get(p) != h)


def _zapisz_manifest(ftp, zdalny, stan):
    ftp.storbinary(f"STOR {posixpath.join(zdalny, MANIFEST)}",
                   io.BytesIO(json.dumps(stan, indent=0, sort_keys=True).encode("utf-8")))


def _wyslij_plik(ftp, lokalny, zdalny, wzgledna, kopia_dir):
    cel = posixpath.join(zdalny, wzgledna)
    if kopia_dir:
        lok = os.path.join(kopia_dir, *wzgledna.split("/"))
        os.makedirs(os.path.dirname(lok), exist_ok=True)
        try:
            with open(lok, "wb") as f:
                ftp.retrbinary(f"RETR {cel}", f.write)
        except ftplib.error_perm:
            os.remove(lok)  # pliku jeszcze nie bylo na serwerze
    with open(os.path.join(lokalny, *wzgledna.split("/")), "rb") as f:
        ftp.storbinary(f"STOR {cel}", f)
    return cel


def wyslij_zmiany(ftp, lokalny, zdalny, kopia_dir=None, polacz_fn=None,
                  watki=1, co_ile=50):
    """Wysyla tylko pliki, ktorych skrot rozni sie od manifestu na serwerze.

    Przed nadpisaniem pobiera dotychczasowa wersje pliku do kopia_dir
    (jesli podano). Manifest zapisywany jest co `co_ile` plikow i na koncu,
    wiec przerwana wysylka rusza przy nastepnym uruchomieniu od miejsca
    przerwania. Przy watki > 1 kazdy watek ma wlasne polaczenie z polacz_fn.
    Plikow usunietych lokalnie nie kasuje na serwerze.
    """
    lokalne = pliki_lokalne(lokalny)
    zdalne = pobierz_manifest(ftp, zdalny)
    zmienione = do_wyslania(lokalne, zdalne)
    print(f"  plikow strony: {len(lokalne)}, do wyslania: {len(zmienione)}", flush=True)

    # Katalogi zakladamy z gory, na glownym polaczeniu.
    katalogi = set()
    for wzgledna in zmienione:
        czesci = [c for c in posixpath.dirname(posixpath.join(zdalny, wzgledna)).split("/") if c]
        for i in range(1, len(czesci) + 1):
            katalogi.add("/" + "/".join(czesci[:i]))
    for sciezka in sorted(katalogi, key=lambda k: (k.count("/"), k)):
        try:
            ftp.mkd(sciezka)
        except ftplib.error_perm:
            pass

    stan = dict(zdalne)
    od_zapisu = 0

    def gotowe(wzgledna, cel):
        nonlocal od_zapisu
        stan[wzgledna] = lokalne[wzgledna]
        od_zapisu += 1
        print(f"  wyslano {cel}", flush=True)
        if od_zapisu >= co_ile:
            _zapisz_manifest(ftp, zdalny, stan)
            od_zapisu = 0

    if watki <= 1 or polacz_fn is None or len(zmienione) < 2:
        for wzgledna in zmienione:
            gotowe(wzgledna, _wyslij_plik(ftp, lokalny, zdalny, wzgledna, kopia_dir))
    else:
        import queue
        import threading
        kolejka = queue.Queue()
        for wzgledna in zmienione:
            kolejka.put(wzgledna)
        wyniki = queue.Queue()

        def pracownik():
            polaczenie = None
            try:
                polaczenie = polacz_fn()
                while True:
                    try:
                        wzgledna = kolejka.get_nowait()
                    except queue.Empty:
                        return
                    try:
                        wyniki.put((wzgledna, _wyslij_plik(polaczenie, lokalny, zdalny,
                                                           wzgledna, kopia_dir), None))
                    except Exception as blad:  # noqa: BLE001 - przekazujemy dalej
                        wyniki.put((wzgledna, None, blad))
                        return
            except Exception as blad:  # noqa: BLE001
                wyniki.put((None, None, blad))
            finally:
                wyniki.put(None)
                if polaczenie is not None:
                    try:
                        polaczenie.quit()
                    except (OSError, ftplib.Error, EOFError):
                        pass

        n = min(watki, len(zmienione))
        watki_lista = [threading.Thread(target=pracownik, daemon=True) for _ in range(n)]
        for w in watki_lista:
            w.start()
        bledy = []
        zakonczone = 0
        while zakonczone < n:
            wpis = wyniki.get()
            if wpis is None:
                zakonczone += 1
            elif wpis[2] is not None:
                bledy.append(wpis[2])
            else:
                gotowe(wpis[0], wpis[1])
        if bledy:
            _zapisz_manifest(ftp, zdalny, stan)  # zachowaj postep
            raise bledy[0]

    if stan != lokalne or zdalne != lokalne:
        _zapisz_manifest(ftp, zdalny, lokalne)
    return zmienione


def znajdz_katalog_strony(ftp):
    """Znajdz katalog publikacji notarai.pl bez zakladania, ze to root FTPS.

    Nie publikujemy na podstawie samej nazwy domeny: wymagamy realnej
    strony z linkiem do app.notarai.pl i arkuszem brand-site.css.
    """
    katalogi = ["", "public_html", "www", "htdocs", "httpdocs", "html",
                "notarai.pl", "notarai.pl/public_html", "notarai.pl/www",
                "domains/notarai.pl/public_html"]
    try:
        for nazwa, czy_katalog in wpisy(ftp, "/"):
            if not czy_katalog or "/" in nazwa or "\\" in nazwa or nazwa.startswith("."):
                continue
            if len(nazwa) > 100:
                continue
            katalogi.extend([nazwa, f"{nazwa}/public_html", f"{nazwa}/www"])
    except (OSError, ftplib.error_perm):
        pass

    for katalog in dict.fromkeys(katalogi):
        bazowy = "/" + katalog.strip("/") if katalog else ""
        indeks = posixpath.join(bazowy, "index.html")
        css = posixpath.join(bazowy, "brand-site.css")
        czesci = []
        try:
            ftp.retrbinary(f"RETR {indeks}", czesci.append)
            html = b"".join(czesci).lower()
            if b"notarai" not in html or b"app.notarai.pl" not in html:
                continue
            # Pusty plik CSS tez potwierdza sciezke, ale jego brak wyklucza.
            ftp.retrbinary(f"RETR {css}", lambda _: None)
            return bazowy or "/"
        except (ftplib.error_perm, OSError):
            continue
    raise RuntimeError(
        "Nie rozpoznano katalogu domeny notarai.pl na FTPS. "
        "Nic nie wyslano i nie pobrano. Sprawdz konfiguracje hostingu."
    )


def main(argv):
    if not argv:
        sys.exit(__doc__)
    ftp = polacz()
    try:
        if argv[0] == "lista":
            lista(ftp, argv[1] if len(argv) > 1 else "/")
        elif argv[0] == "kopia" and len(argv) == 3:
            zrodlo = znajdz_katalog_strony(ftp) if argv[1] == "auto" else argv[1]
            kopia(ftp, zrodlo, argv[2])
        elif argv[0] == "wyslij" and len(argv) == 3:
            cel = znajdz_katalog_strony(ftp) if argv[2] == "auto" else argv[2]
            wyslij(ftp, argv[1], cel)
        elif argv[0] == "wyslij-zmiany" and len(argv) in (3, 4):
            cel = znajdz_katalog_strony(ftp) if argv[2] == "auto" else argv[2]
            watki = int(os.environ.get("NOTARAI_FTP_WATKI", "4"))
            wyslij_zmiany(ftp, argv[1], cel, argv[3] if len(argv) == 4 else None,
                          polacz_fn=polacz, watki=watki)
        else:
            sys.exit(__doc__)
    finally:
        ftp.quit()


if __name__ == "__main__":
    main(sys.argv[1:])
