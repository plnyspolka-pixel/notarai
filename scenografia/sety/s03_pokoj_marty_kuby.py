"""S03 Pokój Marty i Kuby: dwa biurka z monitorami (ekrany białe do podmiany), regał, okno."""
import wspolne as w

NAZWA = "Pokój Marty i Kuby"
WARIANTY = ["dzien", "wieczor"]
W, D, H = 4.8, 4.0, 3.2
OKNA = [(1.7, 2.8, 0.85, 2.8)]
RUCH = ("K02_kuba_przez_ramie", (2.65, 1.0, 1.45))


def zbuduj(plan, wariant):
    podloga = w.tekstura("parkiet", "herringbone_parquet", skala=0.9, szorstkosc_mnoz=0.9, sila_normal=0.4)
    sciany = w.kolor("sciana_biuro", (0.82, 0.82, 0.79), 0.85, polysk=0.25, normal_tex="painted_plaster_wall", skala=0.6, sila_normal=0.15)
    w.pokoj("mk", W, D, H, podloga, sciany, otwory={"N": OKNA, "S": [(3.6, 4.5, 0, 2.15)]})
    w.okno("okno0", "x", D + 0.05, *OKNA[0], strona_wew=-1)
    w.kaloryfer("kal0", "x", D, 2.25, dl=0.9, strona_wew=-1)
    w.drzwi("drzwi", "x", 0.0, 3.6, 4.5, otwarte=30, strona_wew=+1)

    blat = w.tekstura("blat_dab_jasny", "oak_veneer_01", skala=1.0, jasnosc=1.05, szorstkosc_mnoz=0.7, sila_normal=0.2)
    # biurko Kuby (przy ścianie zachodniej, twarzą do ściany) i Marty (przy wschodniej)
    w.biurko("biurko_kuby", (0.55, 2.0, 0), 1.5, 0.75, obrot_z=-90, mat_blat=blat)
    w.monitor("monitor_kuby", (0.4, 2.1, 0.75), 90)
    w.fotel_biurowy("fotel_kuby", (1.15, 2.05, 0), patrz_na=(0.55, 2.1))
    w.teczki("teczki_kuby", (0.55, 1.45, 0.75), 2, obrot_z=80)
    w.kubek("kubek_kuby", (0.7, 2.65, 0.75), (0.85, 0.2, 0.15))
    w.biurko("biurko_marty", (W - 0.55, 2.0, 0), 1.5, 0.75, obrot_z=90, mat_blat=blat)
    w.monitor("monitor_marty", (W - 0.4, 1.95, 0.75), -90)
    w.fotel_biurowy("fotel_marty", (W - 1.15, 1.95, 0), kolor_rgb=(0.12, 0.16, 0.24), patrz_na=(W - 0.55, 1.9))
    w.kartki("kartki_marty", (W - 0.55, 2.6, 0.75), 3, obrot_z=10)
    w.wstaw("potted_plant_04", (W - 0.45, 1.35, 0.75), 0)
    w.kubek("kubek_marty", (W - 0.75, 1.45, 0.75))
    w.drukarka("drukarka", (0.45, 0.45, 0.0), 0)
    w.regal_akt("regal_mk", 0.7, D - 0.2, 1.0, wys=2.2, polki=5, wzdluz_x=True, wypelnienie=0.9)
    w.regal_akt("regal_mk2", 3.1, D - 0.2, 1.0, wys=2.2, polki=5, wzdluz_x=True, wypelnienie=0.75)
    w.wstaw("potted_plant_02", (2.25, 3.5, 0), 20)
    w.obraz_na_scianie("obraz_mk", (2.25, 0.02, 1.7), 1.0, 0.7, "N",
                       [(0.04, 0.1, 0.16), (0.55, 0.62, 0.66), (0.86, 0.84, 0.8), (0.72, 0.52, 0.3)], ziarno=11.2)
    w.wstaw("modern_ceiling_lamp_01", (2.4, 2.0, H - 0.95 - 0.22), 0, nazwa="lampa")

    if wariant == "dzien":
        w.niebo("german_town_street", sila=1.4, obrot_z=-20, tlo_sila=0.9)
        w.slonce((-0.25, -1.0, -0.5), sila=3.2, kolor_k=5300)
        w.portal_okna(plan, "portal0", "x", D, *OKNA[0], strona_wew=-1, moc=260, kolor_k=6800)
        w.lampa_obszar("swietlowka", (2.4, 2.0, H - 0.02), 1.2, 110, 4200, (0, 0, 0), rozmiar_y=0.6)
        w.ekspozycja(1.0)
    else:
        w.niebo("modern_buildings_night", sila=0.15, tlo_sila=0.7)
        w.lampa_punkt("lampa_sw", (2.4, 2.0, H - 0.85), 60, 2900, promien=0.12)
        w.lampa_obszar("poswiata_kuby", (0.55, 2.1, 1.0), 0.45, 8, 7000, (0, 90, 0))
        w.lampa_obszar("poswiata_marty", (W - 0.55, 1.95, 1.0), 0.45, 8, 7000, (0, -90, 0))

    w.kamera(plan, "K01_plan_ogolny", (3.9, 0.45, 1.7), (1.4, 3.0, 0.9), 16, "plan ogólny: oba biurka, okno, regały")
    w.kamera(plan, "K02_kuba_przez_ramie", (2.0, 1.55, 1.5), (0.4, 2.1, 0.98), 30, "przez ramię Kuby na biały ekran (ekran do podmiany)")
    w.kamera(plan, "K03_marta_zblizenie", (W - 0.5, 3.05, 1.28), (W - 1.2, 1.95, 1.18), 40, "Marta przy biurku, ujęcie mówione")
    w.kamera(plan, "K04_kuba_zblizenie", (0.5, 0.95, 1.28), (1.2, 2.05, 1.18), 40, "Kuba przy biurku, ujęcie mówione")
    w.kamera(plan, "K05_dwojka", (2.4, 0.55, 1.55), (2.4, 2.6, 1.05), 22, "dwójka: Marta i Kuby tyłem do siebie, rozmowa przez pokój")
    w.kamera(plan, "K06_detal_ekran", (W - 1.35, 1.75, 1.3), (W - 0.42, 1.95, 1.05), 35, "ekran Marty z bliska (cały biały, do podmiany)")
    w.kamera(plan, "K07_drzwi", (1.2, 3.3, 1.6), (4.05, 0.0, 1.2), 24, "ktoś staje w drzwiach (Basia, Helena)")

    w.znacznik(plan, "M_Kuba_biurko", (1.25, 2.05, 1.2), opis="Kuba siedzi przy biurku twarzą do ściany zachodniej", patrz_na=(0.55, 2.1))
    w.znacznik(plan, "M_Marta_biurko", (W - 1.25, 1.95, 1.2), opis="Marta siedzi przy biurku twarzą do ściany wschodniej", patrz_na=(W - 0.55, 1.9))
    w.znacznik(plan, "M_drzwi", (4.05, 0.45, 1.62), opis="postać w drzwiach", patrz_na=(2.4, 2.4))
    w.znacznik(plan, "M_srodek_pokoju", (2.4, 2.4, 1.62), opis="postać stoi na środku", patrz_na=(2.4, 0.5))
