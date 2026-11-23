"""S04 Klatka schodowa kamienicy i drzwi wejściowe kancelarii (półpiętro, lamperia, bieg w górę i w dół)."""
import math

import wspolne as w

NAZWA = "Klatka schodowa i drzwi kancelarii"
WARIANTY = ["dzien", "wieczor"]
W, D, H = 4.2, 6.0, 4.4
Y0 = 3.4  # krawędź podestu: stąd bieg w górę (zachód) i w dół (wschód)
RUCH = ("K03_ze_schodow_na_drzwi", (1.6, 3.3, 2.05))


def zbuduj(plan, wariant):
    import bpy

    terrazzo = w.tekstura("terrazzo", "terrazzo_tiles", skala=1.0, sila_normal=0.2, szorstkosc_mnoz=0.6)
    gorna = w.kolor("sciana_klatka", (0.82, 0.78, 0.68), 0.85, polysk=0.25, normal_tex="rough_plaster_03", skala=0.8, sila_normal=0.25)
    w.pokoj("kl", W, D, H, terrazzo, gorna, otwory={"N": [(1.6, 2.6, 0, 2.3)], "E": [(4.3, 5.25, 0, 2.15)], "S": [(1.55, 2.65, 2.4, 3.9)]}, gzyms=False, cokol=False)
    bpy.data.objects.remove(bpy.data.objects["kl_podloga"])
    w.skrzynka("podest", (W, D - Y0, 0.12), (W / 2, (D + Y0) / 2, -0.06), terrazzo)
    w.skrzynka("dno_klatki", (W, Y0, 0.1), (W / 2, Y0 / 2, -3.2), w.kolor("dno", (0.3, 0.29, 0.27), 0.8))
    for n, os_, st in (("S", "x", -0.1), ("W", "y", -0.1), ("E", "y", W + 0.1)):
        if os_ == "x":
            w.sciana(f"dolna_{n}", os_, st, -0.2, W + 0.2, 3.2, gorna, z0=-3.2)
        else:
            w.sciana(f"dolna_{n}", os_, st, 0, Y0, 3.2, gorna, z0=-3.2)
    # lamperia olejna do 1,5 m nad podestem
    lamp = w.kolor("lamperia", (0.16, 0.24, 0.2), 0.28, polysk=0.7)
    pasek = w.kolor("pasek_lamperii", (0.55, 0.42, 0.25), 0.4)
    for n, roz, pos in (("N1", (1.6, 0.01, 1.5), (0.8, D - 0.005, 0.75)), ("N2", (1.6, 0.01, 1.5), (3.4, D - 0.005, 0.75)),
                        ("W", (0.01, D - Y0, 1.5), (0.005, (D + Y0) / 2, 0.75)), ("E", (0.01, 0.9, 1.5), (W - 0.005, Y0 + 0.45, 0.75))):
        w.skrzynka(f"lamperia_{n}", roz, pos, lamp)
        w.skrzynka(f"pasek_{n}", (max(roz[0], 0.012), max(roz[1], 0.012), 0.03), (pos[0], pos[1], 1.5), pasek)
    # bieg w górę (zachód) na półpiętro z oknem, bieg w dół (wschód)
    w.schody("bieg_gora", 0.1, 1.35, Y0, -1, 0.0, 9, wznios=0.175, glebokosc=0.28, porecz_x=1.38)
    w.schody("bieg_dol", 2.85, 4.1, Y0, -1, 0.0, 9, wznios=-0.175, glebokosc=0.28, porecz_x=2.82)
    w.skrzynka("polpietro", (W, Y0 - 9 * 0.28, 0.14), (W / 2, (Y0 - 9 * 0.28) / 2, 1.575 - 0.07), terrazzo)
    w.skrzynka("polpietro_dolne", (1.25, Y0 - 9 * 0.28, 0.14), (3.475, (Y0 - 9 * 0.28) / 2, -1.575 - 0.07), terrazzo)
    zel = w.kolor("tralki", (0.06, 0.06, 0.06), 0.4, metal=0.7)
    for i in range(12):
        w.skrzynka(f"bal_podest_{i}", (0.02, 0.02, 0.92), (1.4 + i * 0.13, Y0, 0.46), zel, kolekcja="schody")
    w.skrzynka("porecz_podest", (1.5, 0.06, 0.05), (2.1, Y0, 0.94), w.tekstura("porecz", "dark_wood", skala=2.0, szorstkosc_mnoz=0.6), kolekcja="schody")
    # drzwi kancelarii (bez tabliczki z napisem) i drzwi sąsiada
    w.drzwi("drzwi_kancelarii", "x", D, 1.6, 2.6, wys=2.3, strona_wew=-1,
            mat=w.tekstura("drzwi_dab", "oak_veneer_01", skala=1.0, odcien=(0.55, 0.36, 0.22), szorstkosc_mnoz=0.7))
    w.skrzynka("dzwonek", (0.06, 0.02, 0.09), (2.8, D - 0.11, 1.4), w.kolor("mosiadz", (0.75, 0.6, 0.35), 0.25, metal=1.0))
    w.drzwi("drzwi_sasiada", "y", W, 4.3, 5.25, wys=2.15, strona_wew=-1, mat=w.kolor("drzwi_brazowe", (0.3, 0.18, 0.1), 0.45))
    w.wstaw("potted_plant_02", (0.45, 5.55, 0), 0, skala=0.9)
    w.okno("okno_klatka", "x", -0.05, 1.55, 2.65, 2.4, 3.9, strona_wew=+1, parapet=True)
    # kinkiet
    w.walec("kinkiet", 0.12, 0.08, (0.6, D - 0.06, 2.4), w.swiecenie("kinkiet_sw", (1.0, 0.85, 0.65), 4.0 if wariant != "dzien" else 1.0))

    if wariant == "dzien":
        w.niebo("courtyard", sila=1.3, obrot_z=120, tlo_sila=0.9)
        w.slonce((0.2, 1.0, -0.6), sila=2.5, kolor_k=5400)
        w.portal_okna(plan, "portal_klatka", "x", -0.1, 1.55, 2.65, 2.4, 3.9, strona_wew=+1, moc=320, kolor_k=6800)
        w.lampa_punkt("kinkiet_l", (0.6, D - 0.2, 2.4), 25, 3000)
        w.ekspozycja(1.0)
    else:
        w.niebo("cobblestone_street_night", sila=0.1, tlo_sila=0.5)
        w.lampa_punkt("kinkiet_l", (0.6, D - 0.2, 2.4), 90, 2700, promien=0.1)
        w.lampa_punkt("swiatlo_pietro_wyzej", (0.8, 0.4, 3.6), 40, 2700)

    w.kamera(plan, "K01_podest_szeroki", (3.6, 3.6, 1.65), (1.2, 5.9, 1.1), 18, "podest: drzwi kancelarii, bieg w górę, balustrada")
    w.kamera(plan, "K02_drzwi_frontalnie", (2.1, 4.2, 1.55), (2.1, D, 1.3), 30, "klient przed drzwiami kancelarii, dzwoni")
    w.kamera(plan, "K03_ze_schodow_na_drzwi", (0.75, 1.6, 2.9), (2.1, 5.6, 1.2), 22, "z biegu w górę: ktoś wchodzi na podest")
    w.kamera(plan, "K04_detal_klamka", (2.9, 5.35, 1.25), (2.45, D - 0.1, 1.1), 45, "detal: klamka i dzwonek")
    w.kamera(plan, "K05_w_dol_klatki", (2.2, 3.7, 1.75), (3.45, 1.2, -1.2), 22, "spojrzenie w dół klatki (ktoś schodzi)")
    w.kamera(plan, "K06_z_polpietra_dolnego", (3.45, 0.45, -0.95), (2.0, 5.0, 1.0), 20, "z dolnego półpiętra w górę na podest")
    w.kamera(plan, "K07_okno_polpietro", (2.1, 4.3, 1.9), (2.1, -0.2, 2.9), 24, "okno na półpiętrze, sylwetka pod światło")

    w.znacznik(plan, "M_przed_drzwiami", (2.1, 5.45, 1.62), opis="postać stoi przed drzwiami kancelarii, przodem do drzwi", patrz_na=(2.1, 6.0))
    w.znacznik(plan, "M_podest_srodek", (2.1, 4.3, 1.62), opis="postać na podeście", patrz_na=(2.1, 3.0))
    w.znacznik(plan, "M_na_schodach_w_gore", (0.72, 2.0, 1.62 + 0.8), opis="postać na biegu w górę", patrz_na=(0.72, 1.0))
    w.znacznik(plan, "M_na_schodach_w_dol", (3.45, 2.0, 1.62 - 0.8), opis="postać schodzi w dół", patrz_na=(3.45, 1.0))
    w.znacznik(plan, "M_polpietro_okno", (2.1, 0.5, 1.575 + 1.62), opis="postać na półpiętrze przy oknie", patrz_na=(2.1, 1.5))
