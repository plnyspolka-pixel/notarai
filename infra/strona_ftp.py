"""Strona notarai.pl na hostingu az.pl - lista, kopia i wysylka plikow przez FTPS.

Haslo przychodzi wylacznie ze zmiennej NOTARAI_FTP_HASLO, ktora uzupelnia
asm-exec z sekretu notarai/strona-ftp (patrz infra/strona.ps1). Skrypt nie
wypisuje hasla i nie zapisuje go nigdzie.

    strona_ftp.py lista [katalog]
    strona_ftp.py kopia <katalog_zdalny> <katalog_lokalny>
    strona_ftp.py wyslij <katalog_lokalny> <katalog_zdalny>
"""

import ftplib
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
        else:
            sys.exit(__doc__)
    finally:
        ftp.quit()


if __name__ == "__main__":
    main(sys.argv[1:])
