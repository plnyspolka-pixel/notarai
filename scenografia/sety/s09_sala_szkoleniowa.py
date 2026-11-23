"""S09 Sala szkoleniowa samorządu notarialnego (neutralna, bez godła i emblematów): rzędy stołów, ekran, mównica."""
import wspolne as w

NAZWA = "Sala szkoleniowa (szkolenie aplikantów)"
WARIANTY = ["dzien"]
W, D, H = 9.0, 7.0, 3.4
OKNA = [(1.0, 2.3, 0.9, 2.9), (3.6, 4.9, 0.9, 2.9), (6.2, 7.5, 0.9, 2.9)]
RUCH = ("K01_z_tylu_sali", (4.5, 1.6, 1.65))


def zbuduj(plan, wariant):
    podloga = w.tekstura("wykladzina", "concrete_floor", skala=0.6, odcien=(0.42, 0.44, 0.48), sila_normal=0.2)
    sciany = w.kolor("sciana_sala", (0.86, 0.86, 0.84), 0.85, polysk=0.2, normal_tex="painted_plaster_wall", skala=0.6, sila_normal=0.12)
    w.pokoj("sala", W, D, H, podloga, sciany, otwory={"E": [(a, b, d, g) for a, b, d, g in OKNA[:2]], "S": [(0.4, 1.4, 0, 2.15)]}, gzyms=False)
    for i, (a, b, d, g) in enumerate(OKNA[:2]):
        w.okno(f"okno{i}", "y", W + 0.05, a, b, d, g, strona_wew=-1)
    w.drzwi("drzwi_sala", "x", 0.0, 0.4, 1.4, otwarte=0, strona_wew=+1)
    blat = w.kolor("blat_sala", (0.85, 0.84, 0.8), 0.4)
    # front sali przy ścianie N: ekran i mównica (bez emblematów)
    w.wstaw("projector_screen", (W / 2, D - 0.5, 0), 180, skala=1.4)
    mown = w.tekstura("mownica", "oak_veneer_01", skala=1.0)
    w.skrzynka("mownica", (0.6, 0.45, 1.1), (1.9, D - 1.2, 0.55), mown, kolekcja="meble", fazka=0.01)
    w.biurko("stol_prowadzacy", (6.5, D - 1.3, 0), 1.8, 0.75, obrot_z=180, mat_blat=blat, szafka=False)
    w.fotel_biurowy("krzeslo_prow", (6.5, D - 0.7, 0), 180)
    # rzędy stołów dla uczestników (przodem do N)
    for r in range(4):
        y = 1.6 + r * 1.15
        for k, x in enumerate((1.8, 4.5, 7.2)):
            w.biurko(f"stol_{r}_{k}", (x, y + 0.35, 0), 2.0, 0.55, obrot_z=180, mat_blat=blat, szafka=False)
            for s_i, dx in enumerate((-0.5, 0.5)):
                w.wstaw("SchoolChair_01", (x + dx, y - 0.1, 0), 180, nazwa=f"krzeslo_{r}_{k}_{s_i}")
                if (r + k + s_i) % 3 == 0:
                    w.kartki(f"kartki_{r}_{k}_{s_i}", (x + dx, y + 0.35, 0.75), 2, obrot_z=(r * 7 + k * 13) % 20 - 10)
    w.kubek("kubek_kuba", (4.05, 2.85, 0.75), (0.85, 0.2, 0.15))
    w.wstaw("potted_plant_01", (8.5, D - 0.45, 0), 0)
    for i, x in enumerate((2.2, 4.5, 6.8)):
        for j, y in enumerate((2.2, 4.8)):
            w.skrzynka(f"panel_led_{i}{j}", (1.2, 0.6, 0.03), (x, y, H - 0.02), w.swiecenie("panel_led", (1.0, 0.97, 0.92), 5.0), kolekcja="swiatlo")

    w.niebo("potsdamer_platz", sila=1.2, obrot_z=-60, tlo_sila=0.8)
    w.slonce((-1.0, -0.2, -0.5), sila=2.5, kolor_k=5400)
    for i, (a, b, d, g) in enumerate(OKNA[:2]):
        w.portal_okna(plan, f"portal{i}", "y", W, a, b, d, g, strona_wew=-1, moc=220, kolor_k=6800)
    for i, x in enumerate((2.2, 4.5, 6.8)):
        for j, y in enumerate((2.2, 4.8)):
            w.lampa_obszar(f"led_sw_{i}{j}", (x, y, H - 0.05), 1.2, 90, 4300, (0, 0, 0), rozmiar_y=0.6)
    w.ekspozycja(0.8)

    w.kamera(plan, "K01_z_tylu_sali", (4.5, 0.4, 1.75), (4.5, D, 1.2), 20, "z tyłu sali: rzędy, ekran, prowadzący")
    w.kamera(plan, "K02_kuba_i_zosia_lawka", (6.1, 3.5, 1.35), (4.5, 2.75, 1.1), 32, "dwójka: Kuba i Zosia obok siebie w rzędzie (retrospekcja)")
    w.kamera(plan, "K03_zosia_zblizenie", (3.55, 3.5, 1.3), (4.0, 2.75, 1.15), 45, "Zosia mówi (z ukosa)")
    w.kamera(plan, "K04_kuba_zblizenie", (5.45, 3.5, 1.3), (5.0, 2.75, 1.15), 45, "Kuba mówi (z ukosa)")
    w.kamera(plan, "K05_od_ekranu_na_sale", (4.5, D - 1.0, 1.9), (4.5, 1.0, 1.0), 22, "od strony prowadzącego na salę")
    w.kamera(plan, "K06_wyjscie", (6.5, 4.0, 1.6), (0.9, 0.0, 1.2), 24, "Zosia wychodzi w pół zdania (drzwi sali)")

    w.znacznik(plan, "M_Zosia_lawka", (4.0, 2.75, 1.15), 180, "Zosia siedzi w drugim rzędzie, środkowy stół, lewe miejsce")
    w.znacznik(plan, "M_Kuba_lawka", (5.0, 2.75, 1.15), 180, "Kuba obok Zosi")
    w.znacznik(plan, "M_prowadzacy", (6.5, D - 0.7, 1.2), 180, "prowadzący szkolenie")
    w.znacznik(plan, "M_drzwi", (0.9, 0.5, 1.62), 0, "postać w drzwiach sali")
