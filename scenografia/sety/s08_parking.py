"""S08 Parking na podwórzu kamienicy z samochodem Marty (auto bez marki, gładka tablica, tylko fragmenty w kadrze); dzień i noc."""
import wspolne as w

NAZWA = "Parking z samochodem Marty"
WARIANTY = ["noc", "dzien"]
KAMERY_WARIANTU = {"dzien": ["K01_podworze_szeroki", "K02_marta_przy_drzwiach", "K03_marta_idzie_do_auta"]}
RUCH = ("K01_podworze_szeroki", (-3.5, -2.8, 1.6))


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
    # tylko auto Marty; kadry pokazują je na krawędzi albo rozmyte (płytka ostrość), nigdy całej bryły z bliska,
    # bo auto jest proceduralne (brak modelu CC0 auta bez marki). Przód auta = -y (od muru), drzwi kierowcy od strony +x.
    w.samochod("auto_marty", (1.3, 2.4, 0), -90, (0.06, 0.09, 0.16))
    # sąsiednie auta: model CC0 Poly Haven "covered_car" (auto pod plandeką - realistyczne, bez marki)
    w.wstaw("covered_car", (-3.9, 2.5, 0), 3, nazwa="auto_sasiad_plandeka")
    w.wstaw("covered_car", (6.5, 2.4, 0), -4, nazwa="auto_sasiad_plandeka2")
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

    w.kamera(plan, "K01_podworze_szeroki", (-4.0, -4.5, 1.6), (-2.9, 4.5, 1.6), 24, "plan ogólny podwórza: mur, latarnia, auta pod plandeką; auto Marty poza kadrem")
    w.kamera(plan, "K02_marta_przy_drzwiach", (4.4, 0.6, 1.6), (2.75, 2.35, 1.55), 85, "zbliżenie: Marta przy drzwiach kierowcy; auto za nią mocno rozmyte", przyslona=1.8)
    w.kamera(plan, "K03_marta_idzie_do_auta", (-2.6, -3.2, 1.5), (-1.9, 4.0, 1.4), 35, "Marta idzie przez podwórze (jej auto poza kadrem z prawej)")
    w.kamera(plan, "K04_latarnia_mur", (0.5, -1.5, 1.2), (-2.6, 5.0, 2.6), 28, "przebitka: latarnia przy murze (noc: plama światła na mokrym asfalcie)")
    w.kamera(plan, "K05_okna_oficyny", (-4.5, 1.0, 1.5), (-9.0, 0.5, 6.0), 24, "żabia perspektywa na okna oficyny (ktoś patrzy z góry)")
    w.kamera(plan, "K06_z_gory_oficyna", (-8.5, -3.0, 6.0), (-3.5, 3.5, 0.0), 30, "z okna oficyny: ktoś obserwuje podwórze, auto na krawędzi kadru")
    w.znacznik(plan, "M_Marta_idzie", (-1.6, -0.4, 1.62), opis="Marta w drodze do auta", patrz_na=(1.3, 2.4))

    w.znacznik(plan, "M_Marta_drzwi_kierowcy", (2.75, 2.35, 1.62), opis="Marta stoi przy drzwiach kierowcy, przodem do auta", patrz_na=(1.3, 2.35))
    w.znacznik(plan, "M_Marta_za_kierownica", (1.75, 2.45, 1.15), opis="Marta siedzi za kierownicą (oczy ok. 1,15 m), patrzy przed siebie", patrz_na=(1.75, -2.0))
    w.znacznik(plan, "M_obserwator", (-1.5, -1.0, 1.62), opis="druga postać na podwórzu", patrz_na=(1.3, 2.4))
