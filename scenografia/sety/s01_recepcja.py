"""S01 Recepcja i poczekalnia kancelarii Heleny (lada Basi, poczekalnia, zegar 8:57)."""
import wspolne as w

NAZWA = "Recepcja i poczekalnia"
WARIANTY = ["dzien", "wieczor"]
W, D, H = 5.6, 4.4, 3.2
OKNA = [(0.9, 2.0, 0.85, 2.8)]
RUCH = ("K01_plan_ogolny", (1.2, 1.1, 1.66))


def zbuduj(plan, wariant):
    podloga = w.tekstura("parkiet", "herringbone_parquet", skala=0.9, szorstkosc_mnoz=0.9, sila_normal=0.4)
    sciany = w.kolor("sciana_recepcja", (0.84, 0.82, 0.77), 0.85, polysk=0.25, normal_tex="painted_plaster_wall", skala=0.6, sila_normal=0.15)
    w.pokoj("rec", W, D, H, podloga, sciany,
            otwory={"N": OKNA + [(4.3, 5.2, 0, 2.15)], "S": [(0.4, 1.4, 0, 2.15)], "E": [(0.7, 1.65, 0, 2.15)]})
    w.okno("okno0", "x", D + 0.05, *OKNA[0], strona_wew=-1)
    w.kaloryfer("kal0", "x", D, 1.45, dl=0.9, strona_wew=-1)
    w.drzwi("drzwi_wejscie", "x", 0.0, 0.4, 1.4, otwarte=0, strona_wew=+1,
            mat=w.tekstura("drzwi_wejsciowe", "oak_veneer_01", skala=1.0, odcien=(0.6, 0.42, 0.28)))
    w.drzwi("drzwi_marta", "x", D, 4.3, 5.2, otwarte=-25, strona_wew=-1)
    w.drzwi("drzwi_gabinet", "y", W, 0.7, 1.65, otwarte=0, strona_wew=-1)

    # lada Basi (front w stronę wejścia, czyli -y)
    w.lada("lada", (3.6, 2.2, 0), szer=2.2, gl=0.75)
    w.fotel_biurowy("fotel_basi", (3.4, 2.85, 0), kolor_rgb=(0.2, 0.22, 0.26), patrz_na=(3.4, 2.2))
    w.monitor("monitor_basi", (3.15, 2.3, 0.75), 180)
    w.telefon_biurkowy("telefon", (4.25, 2.15, 0.75), -15)
    w.drukarka("drukarka", (5.25, 3.0, 0.55), -90)
    w.skrzynka("szafka_drukarka", (0.5, 0.6, 0.55), (5.25, 3.0, 0.275), w.kolor("blat_bialy", (0.88, 0.87, 0.84), 0.35), kolekcja="meble")
    w.teczki("teczki_lada", (2.75, 2.15, 0.75), 3, obrot_z=-6)
    w.kartki("kartki_lada", (3.95, 1.78, 1.13), 2, obrot_z=4)
    w.kubek("kubek_basi", (4.0, 2.4, 0.75), (0.08, 0.12, 0.28))
    w.wstaw("potted_plant_04", (2.65, 1.85, 1.13), 0)
    w.regal_akt("regal_rec", 3.0, 4.35, 1.1, wys=2.0, polki=4, wzdluz_x=True, wypelnienie=0.8)

    # poczekalnia przy oknie
    w.wstaw("sofa_02", (0.55, 2.0, 0), nazwa="sofa", patrz_na=(1.35, 2.0))
    w.wstaw("ArmChair_01", (1.35, 3.55, 0), nazwa="fotel_pocz", patrz_na=(1.25, 2.35))
    w.wstaw("coffee_table_round_01", (1.35, 2.35, 0), 0, skala=0.6, nazwa="stolik")
    w.kartki("ulotki", (1.35, 2.35, 0.3), 2, obrot_z=20)
    w.wstaw("potted_plant_01", (0.45, 3.95, 0), 0)
    w.wieszak("wieszak", (2.3, 0.35, 0))
    w.dywan("dywan_pocz", (1.2, 2.5), 2.0, 2.4, odcien=(0.2, 0.22, 0.27))
    w.obraz_na_scianie("obraz_rec", (0.02, 2.0, 1.75), 1.1, 0.75, "E",
                       [(0.06, 0.09, 0.2), (0.75, 0.72, 0.66), (0.62, 0.5, 0.32), (0.2, 0.3, 0.38)], ziarno=7.1)
    w.zegar_scienny("zegar", (W - 0.03, 2.75, 2.25), "W", 8, 57)
    for i, x in enumerate((1.5, 3.8)):
        w.wstaw("modern_ceiling_lamp_01", (x, 2.3, H - 0.95 - 0.22), 0, nazwa=f"lampa{i}")

    if wariant == "dzien":
        w.niebo("urban_street_01", sila=1.4, obrot_z=10, tlo_sila=0.9)
        w.slonce((0.3, -1.0, -0.5), sila=3.0, kolor_k=5300)
        w.portal_okna(plan, "portal0", "x", D, *OKNA[0], strona_wew=-1, moc=280, kolor_k=6800)
        w.lampa_obszar("swietlowka_sufit", (3.6, 2.3, H - 0.02), 1.2, 120, 4200, (0, 0, 0), rozmiar_y=0.6)
        for i, x in enumerate((1.5, 3.8)):
            w.lampa_punkt(f"lampa_sw{i}", (x, 2.3, H - 0.85), 10, 3000)
        w.ekspozycja(1.0)
    else:
        w.niebo("cobblestone_street_night", sila=0.15, tlo_sila=0.6)
        for i, x in enumerate((1.5, 3.8)):
            w.lampa_punkt(f"lampa_sw{i}", (x, 2.3, H - 0.85), 75, 2800, promien=0.12)
        w.lampa_obszar("ekran_poswiata", (3.2, 2.15, 1.0), 0.4, 6, 7000, (90, 0, 0))

    w.kamera(plan, "K01_plan_ogolny", (0.5, 0.45, 1.68), (4.0, 3.0, 1.0), 16, "plan ogólny: poczekalnia, lada, drzwi do gabinetu i pokoju Marty")
    w.kamera(plan, "K02_basia_za_lada", (3.55, 1.1, 1.52), (3.4, 2.85, 1.18), 42, "Basia za ladą (ujęcie mówione)")
    w.kamera(plan, "K03_wejscie_z_lady", (3.4, 2.95, 1.25), (0.9, 0.0, 1.35), 24, "wejście klienta widziane zza lady")
    w.kamera(plan, "K04_poczekalnia", (2.6, 1.0, 1.35), (0.6, 2.9, 0.9), 26, "poczekalnia: sofa i fotel przy oknie")
    w.kamera(plan, "K05_detal_telefon", (4.55, 2.7, 1.35), (4.25, 2.15, 0.76), 40, "detal: dzwoniący telefon i teczki")
    w.kamera(plan, "K06_zegar", (4.2, 2.75, 2.0), (5.57, 2.75, 2.25), 50, "zegar 8:57 (bez cyfr)")
    w.kamera(plan, "K07_dwojka_lada", (1.6, 0.6, 1.5), (3.8, 2.6, 1.25), 30, "dwójka: klient przy ladzie i Basia")

    w.znacznik(plan, "M_Basia_lada", (3.4, 2.85, 1.2), opis="Basia siedzi za ladą, oczy 1,2 m", patrz_na=(3.4, 1.45))
    w.znacznik(plan, "M_klient_przy_ladzie", (3.3, 1.45, 1.62), opis="klient stoi przy ladzie", patrz_na=(3.4, 2.85))
    w.znacznik(plan, "M_wejscie", (0.9, 0.5, 1.62), opis="postać w drzwiach wejściowych", patrz_na=(2.8, 2.2))
    w.znacznik(plan, "M_poczekalnia_sofa", (0.6, 2.0, 1.15), opis="osoba czeka na sofie", patrz_na=(1.35, 2.0))
    w.znacznik(plan, "M_drzwi_gabinetu", (5.0, 1.2, 1.62), opis="Helena wychodzi z gabinetu", patrz_na=(3.6, 1.8))
    w.znacznik(plan, "M_drzwi_marty", (4.75, 3.95, 1.62), opis="Kuba w drzwiach pokoju", patrz_na=(3.6, 2.2))
