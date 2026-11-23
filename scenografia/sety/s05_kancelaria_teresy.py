"""S05 Mała kancelaria Teresy: jeden pokój w bloku, biurko Teresy z telefonem, kącik Zosi, dużo papieru."""
import wspolne as w

NAZWA = "Kancelaria Teresy"
WARIANTY = ["dzien", "wieczor"]
W, D, H = 4.2, 3.8, 2.75
OKNA = [(1.3, 2.9, 0.9, 2.45)]
RUCH = ("K02_teresa_przy_biurku", (2.15, 1.35, 1.38))


def zbuduj(plan, wariant):
    podloga = w.tekstura("panele", "laminate_floor_02", skala=0.8, odcien=(0.9, 0.82, 0.72), sila_normal=0.3)
    sciany = w.kolor("sciana_teresa", (0.8, 0.76, 0.66), 0.88, polysk=0.2, normal_tex="painted_plaster_wall", skala=0.7, sila_normal=0.2)
    w.pokoj("ter", W, D, H, podloga, sciany, otwory={"N": OKNA, "S": [(0.3, 1.2, 0, 2.05)]}, gzyms=False)
    w.okno("okno0", "x", D + 0.05, *OKNA[0], strona_wew=-1, szczeble=False)
    w.kaloryfer("kal0", "x", D, 2.1, dl=1.2, strona_wew=-1)
    w.drzwi("drzwi", "x", 0.0, 0.3, 1.2, wys=2.05, otwarte=0, strona_wew=+1)

    ciemny = w.tekstura("blat_ciemny", "dark_wood", skala=1.0, szorstkosc_mnoz=0.7, sila_normal=0.2)
    # biurko Teresy na środku, przodem do drzwi (klient siedzi od strony drzwi)
    w.biurko("biurko_teresy", (2.3, 2.55, 0), 1.6, 0.8, obrot_z=180, mat_blat=ciemny, mat_nogi=ciemny)
    w.fotel_biurowy("fotel_teresy", (2.3, 3.2, 0), 180, (0.07, 0.045, 0.035))
    w.telefon_biurkowy("telefon", (1.75, 2.45, 0.75), 20)
    w.monitor("monitor_teresy", (2.75, 2.75, 0.75), 200, szer=0.5, wys=0.3)
    for i, (x, y, n, r) in enumerate(((2.0, 2.35, 4, 5), (2.3, 2.9, 5, -12), (1.6, 2.85, 3, 30))):
        w.teczki(f"stos{i}", (x, y, 0.75), n, obrot_z=r, kolory=[(0.62, 0.55, 0.42), (0.75, 0.73, 0.66), (0.2, 0.3, 0.45), (0.55, 0.2, 0.15)])
    w.kartki("kartki_ter", (2.5, 2.3, 0.75), 4, obrot_z=-8)
    w.kubek("kubek_ter", (3.0, 2.35, 0.75), (0.8, 0.78, 0.7))
    for i, x in enumerate((1.9, 2.7)):
        w.wstaw("dining_chair_02", (x, 1.55, 0), 0, nazwa=f"krzeslo_klienta{i}")

    # kącik Zosi przy ścianie wschodniej
    w.biurko("biurko_zosi", (W - 0.4, 1.4, 0), 1.1, 0.6, obrot_z=90, szafka=False)
    w.monitor("monitor_zosi", (W - 0.3, 1.4, 0.75), 90, szer=0.5, wys=0.3)
    w.fotel_biurowy("krzeslo_zosi", (W - 0.9, 1.4, 0), 95, (0.1, 0.1, 0.11))
    w.kubek("kubek_zosi", (W - 0.35, 1.85, 0.75), (0.15, 0.35, 0.4))

    # regały i pudła z aktami: ciasno
    w.regal_akt("regal_t1", 0.2, 1.6, 2.0, wys=2.3, polki=6, wzdluz_x=False, wypelnienie=1.0)
    w.wstaw("steel_frame_shelves_02", (W - 0.3, 3.35, 0), 180)
    w.segregatory("seg_stal", (W - 0.55, 3.35, 0.82), True, 6, wys=0.3)
    w.wstaw("cardboard_box_01", (0.55, 3.45, 0), 15)
    w.wstaw("cardboard_box_01", (0.55, 3.45, 0.34), -10)
    w.wstaw("cardboard_box_01", (1.05, 3.5, 0), 40)
    w.wstaw("potted_plant_02", (3.3, 3.6, 0.9), 0, skala=0.6)
    w.wieszak("wieszak", (1.5, 0.3, 0))
    w.zegar_scienny("zegar_t", (0.02, 0.9, 2.1), "E", 16, 40, r=0.14)
    w.lampa_obszar("plafon_obudowa", (2.1, 1.9, H - 0.01), 0.5, 0, 3500)
    w.walec("plafon", 0.28, 0.06, (2.1, 1.9, H - 0.03), w.swiecenie("plafon_swieci", (1.0, 0.92, 0.8), 3.0 if wariant != "dzien" else 0.6))

    if wariant == "dzien":
        w.niebo("suburban_parking_area", sila=1.2, obrot_z=60, tlo_sila=0.5)
        w.slonce((0.2, -1.0, -0.6), sila=3.0, kolor_k=5400)
        w.portal_okna(plan, "portal0", "x", D, *OKNA[0], strona_wew=-1, moc=150, kolor_k=6600)
        w.lampa_obszar("plafon_sw", (2.1, 1.9, H - 0.08), 0.5, 80, 3600, (0, 0, 0), ksztalt="DISK")
        w.lampa_obszar("wypelnienie_od_drzwi", (2.1, 0.4, 1.8), 1.0, 90, 4500, (90, 0, 0))
        w.ekspozycja(0.6)
    else:
        w.niebo("rooftop_night", sila=0.12, tlo_sila=0.6)
        w.lampa_obszar("plafon_sw", (2.1, 1.9, H - 0.08), 0.5, 260, 3000, (0, 0, 0), ksztalt="DISK")
        w.lampa_obszar("lampka_biurko", (1.7, 2.8, 1.2), 0.25, 35, 2800, (0, 0, 0))

    w.kamera(plan, "K01_plan_ogolny", (3.7, 0.4, 1.65), (1.5, 3.0, 0.9), 16, "plan ogólny: ciasny pokój, biurko Teresy, kącik Zosi, regały")
    w.kamera(plan, "K02_teresa_przy_biurku", (2.3, 1.2, 1.35), (2.3, 3.2, 1.15), 32, "Teresa za biurkiem z telefonem (od strony klienta)")
    w.kamera(plan, "K03_teresa_zblizenie", (2.45, 1.75, 1.25), (2.3, 3.2, 1.2), 50, "Teresa, ujęcie mówione")
    w.kamera(plan, "K04_zosia_kacik", (2.6, 1.0, 1.4), (W - 0.95, 1.45, 1.15), 35, "Zosia przy swoim biurku")
    w.kamera(plan, "K05_detal_telefon", (1.5, 2.0, 1.15), (1.75, 2.5, 0.78), 45, "detal: telefon i stosy teczek")
    w.kamera(plan, "K06_od_okna_na_drzwi", (2.9, 3.5, 1.6), (0.75, 0.0, 1.1), 22, "kontrplan zza biurka: drzwi i krzesła klientów")
    w.kamera(plan, "K07_dwojka_teresa_zosia", (1.1, 0.9, 1.55), (3.2, 2.6, 1.1), 24, "dwójka: Teresa za biurkiem i Zosia w kąciku")

    w.znacznik(plan, "M_Teresa_biurko", (2.3, 3.2, 1.18), 180, "Teresa siedzi za biurkiem")
    w.znacznik(plan, "M_Zosia_kacik", (W - 0.95, 1.4, 1.18), 90, "Zosia przy biurku, bokiem do pokoju")
    w.znacznik(plan, "M_klient_L", (1.9, 1.55, 1.15), 0, "klient na krześle")
    w.znacznik(plan, "M_klient_P", (2.7, 1.55, 1.15), 0, "drugi klient")
    w.znacznik(plan, "M_drzwi", (0.75, 0.45, 1.62), 0, "Kuba w drzwiach")
