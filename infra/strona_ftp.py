"""Strona notarai.pl na hostingu az.pl - lista, kopia i wysylka plikow przez FTPS.

Haslo przychodzi wylacznie ze zmiennej NOTARAI_FTP_HASLO, ktora uzupelnia
asm-exec z sekretu notarai/strona-ftp (patrz infra/strona.ps1). Skrypt nie
wypisuje hasla i nie zapisuje go nigdzie.

    strona_ftp.py lista [katalog]
    strona_ftp.py kopia <katalog_zdalny> <katalog_lokalny>
    strona_ftp.py wyslij <katalog_lokalny> <katalog_zdalny>
    strona_ftp.py roznice <katalog_lokalny> <katalog_zdalny>
    strona_ftp.py wyslij-zmiany <katalog_lokalny> <katalog_zdalny>

"roznice" i "wyslij-zmiany" porownuja skroty SHA-256 plikow lokalnych ze spisem
zostawionym na serwerze przy poprzedniej publikacji (MANIFEST). Wysylane sa
tylko pliki nowe i zmienione; z serwera nic nie jest usuwane. Uzywa ich
publikacja z GitHuba (.github/workflows/strona.yml).
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


# Spis opublikowanych plikow (sciezka -> SHA-256). Zawiera wylacznie skroty
# plikow publicznych, wiec moze lezec w katalogu strony.
MANIFEST = ".notarai-publikacja.json"


def skroty_lokalne(lokalny):
    """Sciezka wzgledna (z ukosnikami) -> SHA-256, dla plikow, ktore wysyla "wyslij"."""
    wynik = {}
    for korzen, katalogi, pliki in os.walk(lokalny):
        katalogi[:] = sorted(k for k in katalogi if not k.startswith("."))
        for nazwa in sorted(pliki):
            if nazwa.startswith("."):
                continue
            pelna = os.path.join(korzen, nazwa)
            wzgledna = os.path.relpath(pelna, lokalny).replace(os.sep, "/")
            skrot = hashlib.sha256()
            with open(pelna, "rb") as f:
                for kawalek in iter(lambda: f.read(1 << 16), b""):
                    skrot.update(kawalek)
            wynik[wzgledna] = skrot.hexdigest()
    return wynik


def czytaj_manifest(ftp, zdalny):
    """Spis z poprzedniej publikacji; pusty, gdy go nie ma albo jest nieczytelny."""
    czesci = []
    try:
        ftp.retrbinary(f"RETR {posixpath.join(zdalny, MANIFEST)}", czesci.append)
        dane = json.loads(b"".join(czesci).decode("utf-8"))
    except (ftplib.error_perm, OSError, ValueError):
        return {}
    pliki = dane.get("pliki") if isinstance(dane, dict) else None
    if not isinstance(pliki, dict):
        return {}
    return {str(k): str(v) for k, v in pliki.items()}


def zmienione(lokalne, zdalne):
    """Pliki nowe i o innej tresci niz przy poprzedniej publikacji, posortowane."""
    return sorted(sciezka for sciezka, skrot in lokalne.items() if zdalne.get(sciezka) != skrot)


def wyslij_zmiany(ftp, lokalny, zdalny):
    lokalne = skroty_lokalne(lokalny)
    if "index.html" not in lokalne:
        raise RuntimeError("Brak index.html w katalogu do publikacji. Nic nie wyslano.")
    do_wyslania = zmienione(lokalne, czytaj_manifest(ftp, zdalny))
    zalozone = set()
    for sciezka in do_wyslania:
        katalog = posixpath.dirname(sciezka)
        czesc = ""
        for element in [e for e in katalog.split("/") if e]:
            czesc = posixpath.join(czesc, element)
            if czesc in zalozone:
                continue
            try:
                ftp.mkd(posixpath.join(zdalny, czesc))
            except ftplib.error_perm:
                pass
            zalozone.add(czesc)
        with open(os.path.join(lokalny, *sciezka.split("/")), "rb") as f:
            ftp.storbinary(f"STOR {posixpath.join(zdalny, sciezka)}", f)
        print(f"  wyslano {sciezka}")
    # Spis zapisujemy na koncu: przerwana publikacja powtorzy sie od zera roznic.
    if do_wyslania:
        tresc = json.dumps({"pliki": lokalne}, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ftp.storbinary(f"STOR {posixpath.join(zdalny, MANIFEST)}", io.BytesIO(tresc))
    return do_wyslania


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
        elif argv[0] in ("roznice", "wyslij-zmiany") and len(argv) == 3:
            cel = znajdz_katalog_strony(ftp) if argv[2] == "auto" else argv[2]
            if argv[0] == "roznice":
                lista_zmian = zmienione(skroty_lokalne(argv[1]), czytaj_manifest(ftp, cel))
                for sciezka in lista_zmian[:40]:
                    print(f"  do wyslania {sciezka}")
            else:
                lista_zmian = wyslij_zmiany(ftp, argv[1], cel)
            # Ostatni wiersz czyta workflow.
            print(f"ZMIENIONE={len(lista_zmian)}")
        else:
            sys.exit(__doc__)
    finally:
        ftp.quit()


if __name__ == "__main__":
    main(sys.argv[1:])
