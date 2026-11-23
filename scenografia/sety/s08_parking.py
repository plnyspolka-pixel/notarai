"""S08 Parking na podwórzu kamienicy z samochodem Marty (auto bez marki, gładka tablica); dzień i noc."""
import wspolne as w

NAZWA = "Parking z samochodem Marty"
WARIANTY = ["noc", "dzien"]
KAMERY_WARIANTU = {"dzien": ["K01_parking_szeroki", "K02_marta_przy_drzwiach", "K04_tyl_auta"]}
RUCH = ("K01_parking_szeroki", (4.2, -5.0, 1.5))


def zbuduj(plan, wariant):
    noc = wariant == "noc"
    asfalt = w.tekstura("asfalt_parking", "asphalt_02", skala=0.5, sila_normal=0.4, szorstkosc_mnoz=0.3 if noc else 1.0, odcien=(0.6, 0.6, 0.62) if noc else None)
    w.skrzynka("plac", (30, 30, 0.1), (0, 0, -0.05), asfalt, kolekcja="ulica")
    linie = w.kolor("linie", (0.85, 0.85, 0.8), 0.7)
    for i in range(6):
        w.skrzynka(f"linia{i}", (0.1, 5.0, 0.005), (-5 + i * 2.6, 2.5, 0.003), linie, kolekcja="ulica")
    sciana = w.tekstura("mur_podworze", "brick_wall_001", skala=0.7, jasnosc=0.8)
    w.skrzynka("mur_tyl", (30, 0.4, 6), (0, 5.6, 3), sciana, kolekcja="ulica")
    tynk = w.tekstura("oficyna", "white_stucco", skala=0.5, odcien=(0.7, 0.68, 0.62))
    w.skrzynka("oficyna_bok", (0.4, 14, 10), (-9.2, 0, 5), tynk, kolekcja="ulica")
    for i in range(4):
        for j in range(3):
            w.skrzynka(f"okno_ofic{i}{j}", (0.05, 1.1, 1.6), (-8.98, -4 + i * 2.6, 1.4 + j * 3.0),
                       w.swiecenie("okno_noc", (1.0, 0.8, 0.55), 1.5) if (noc and (i + j) % 3 == 0) else w.kolor("szyba_fasada", (0.04, 0.05, 0.06), 0.03, polysk=1.0), kolekcja="ulica")
    w.samochod("auto_marty", (1.3, 2.4, 0), -90, (0.06, 0.09, 0.16))
    w.samochod("auto_sasiad", (-3.9, 2.4, 0), -90, (0.55, 0.55, 0.53))
    w.samochod("auto_sasiad2", (6.5, 2.4, 0), -90, (0.25, 0.05, 0.05))
    w.wstaw("street_lamp_01", (-2.6, 5.0, 0), 180, nazwa="latarnia")
    w.wstaw("metal_trash_can", (8.4, 4.9, 0), 0, tylko=["metal_trash_can"], wyklucz=["rust"])

    if not noc:
        w.niebo("suburban_parking_area", sila=1.1, obrot_z=30)
        w.slonce((0.5, 0.6, -0.6), sila=3.0, kolor_k=5400)
        w.ekspozycja(0.2)
    else:
        w.niebo("rooftop_night", sila=0.12, obrot_z=30)
        w.lampa_punkt("latarnia_sw", (-2.55, 4.6, 3.7), 700, 2300, promien=0.15)
        w.lampa_obszar("kinkiet_brama", (5.0, 5.35, 2.6), 0.3, 120, 2600, (-90, 0, 0))

    w.kamera(plan, "K01_parking_szeroki", (3.8, -6.5, 1.6), (1.3, 3.0, 0.9), 26, "plan ogólny: podwórze, auto Marty pod latarnią")
    w.kamera(plan, "K02_marta_przy_drzwiach", (3.4, -0.6, 1.5), (1.0, 1.4, 1.2), 32, "Marta otwiera drzwi kierowcy")
    w.kamera(plan, "K03_przez_szybe", (0.5, -0.4, 1.25), (1.6, 2.4, 1.05), 40, "przez szybę: Marta w środku, telefon odłożony")
    w.kamera(plan, "K04_tyl_auta", (-1.2, -2.5, 1.0), (1.3, 2.4, 0.8), 35, "tył auta, światła stop (montaż: ostre hamowanie)")
    w.kamera(plan, "K05_detal_klamka", (2.4, 0.9, 1.1), (1.6, 1.5, 0.9), 50, "detal: dłoń na klamce drzwi auta")
    w.kamera(plan, "K06_z_gory_oficyna", (-6.0, -6.0, 6.0), (1.3, 2.4, 0.5), 30, "z okna oficyny: ktoś obserwuje parking")

    w.znacznik(plan, "M_Marta_drzwi_kierowcy", (1.0, 1.25, 1.62), 0, "Marta stoi przy drzwiach kierowcy (lewa strona auta)")
    w.znacznik(plan, "M_Marta_za_kierownica", (1.6, 2.0, 1.15), 0, "Marta siedzi za kierownicą (oczy ok. 1,15 m)")
    w.znacznik(plan, "M_obserwator", (-1.5, -1.0, 1.62), 45, "druga postać na podwórzu")
