"""S06 Kawiarnia: stolik przy oknie wystawowym (Kuba i Zosia), lada, kilka stolików, ulica za szybą."""
import wspolne as w

NAZWA = "Kawiarnia, stolik przy oknie"
WARIANTY = ["dzien", "wieczor"]
KAMERY_WARIANTU = {"wieczor": ["K01_przy_oknie_dwojka", "K02_kuba_przez_ramie_zosi", "K03_zosia_przez_ramie_kuby", "K04_plan_ogolny"]}
W, D, H = 6.0, 5.0, 3.4
WITRYNA = [(0.5, 2.9, 0.45, 2.8), (3.3, 5.5, 0.45, 2.8)]
RUCH = ("K01_przy_oknie_dwojka", (1.85, 2.55, 1.25))


def zbuduj(plan, wariant):
    podloga = w.tekstura("deski_kawiarnia", "dark_wood", skala=0.8, szorstkosc_mnoz=0.8, sila_normal=0.3)
    sciany = w.kolor("sciana_kawiarnia", (0.55, 0.42, 0.33), 0.8, polysk=0.25, normal_tex="rough_plaster_brick", skala=0.5, sila_normal=0.25)
    w.pokoj("kaw", W, D, H, podloga, sciany, otwory={"N": WITRYNA}, gzyms=False)
    for i, o in enumerate(WITRYNA):
        w.okno(f"witryna{i}", "x", D + 0.05, *o, strona_wew=-1, szczeble=False, parapet=False,
               mat_rama=w.kolor("rama_czarna", (0.04, 0.04, 0.04), 0.35, metal=0.5))
    w.skrzynka("parapet_lada", (W - 0.6, 0.35, 0.04), (W / 2, D - 0.18, 1.0), w.tekstura("blat_dab", "oak_veneer_01", skala=1.0, odcien=(0.6, 0.4, 0.25)))

    # stolik przy oknie (dla Kuby i Zosi) i trzy inne
    w.stolik_bistro("stolik_okno", (1.7, 4.15, 0))
    w.krzeslo_bistro("krzeslo_kuby", (1.15, 4.15, 0), patrz_na=(1.7, 4.15))
    w.krzeslo_bistro("krzeslo_zosi", (2.25, 4.15, 0), patrz_na=(1.7, 4.15))
    w.kubek("kubek_k", (1.55, 4.1, 0.75), (0.95, 0.95, 0.93))
    w.kubek("kubek_z", (1.85, 4.22, 0.75), (0.95, 0.95, 0.93))
    for i, (x, y) in enumerate(((4.3, 4.15), (1.7, 2.4), (4.2, 2.3))):
        w.stolik_bistro(f"stolik{i}", (x, y, 0))
        w.krzeslo_bistro(f"krzeslo{i}a", (x - 0.55, y, 0), patrz_na=(x, y))
        w.krzeslo_bistro(f"krzeslo{i}b", (x + 0.55, y, 0), patrz_na=(x, y))
    # lada z ekspresem (bez marki) i półki z kubkami
    w.lada("lada_kaw", (3.8, 0.75, 0), szer=3.2, gl=0.7, obrot_z=180,
           mat=w.tekstura("lada_ciemna", "dark_wood", skala=1.0), mat_blat=w.kolor("marmur_jasny", (0.86, 0.85, 0.82), 0.18, polysk=0.6))
    w.skrzynka("ekspres", (0.6, 0.45, 0.45), (4.2, 0.45, 0.735 + 0.225), w.kolor("stal", (0.6, 0.6, 0.62), 0.25, metal=1.0), kolekcja="rekwizyty_wlasne", fazka=0.03)
    for i in range(3):
        w.skrzynka(f"polka_kubki{i}", (2.6, 0.25, 0.03), (4.1, 0.13, 1.55 + i * 0.4), w.tekstura("polka_dab", "oak_veneer_01", skala=1.0), kolekcja="meble")
        for j in range(8):
            w.kubek(f"kubek_p{i}_{j}", (3.0 + j * 0.3, 0.13, 1.565 + i * 0.4), [(0.92, 0.9, 0.86), (0.2, 0.25, 0.3), (0.75, 0.55, 0.35)][(i + j) % 3])
    for p, x in (("potted_plant_01", 0.4), ("potted_plant_02", 5.6)):
        w.wstaw(p, (x, 4.7, 0), 0)
    for i, (x, y) in enumerate(((1.7, 4.15), (4.3, 4.15), (1.7, 2.4), (4.2, 2.3))):
        w.wstaw("modern_ceiling_lamp_01", (x, y, H - 0.95 - 0.5), 0, skala=0.8, nazwa=f"lampa{i}")
    w.obraz_na_scianie("obraz_kaw", (0.02, 2.4, 1.8), 1.0, 1.3, "E", [(0.45, 0.2, 0.12), (0.85, 0.72, 0.5), (0.15, 0.2, 0.22)], ziarno=21.0)

    if wariant == "dzien":
        w.niebo("german_town_street", sila=1.3, obrot_z=180, tlo_sila=0.6)
        w.slonce((-0.3, -1.0, -0.55), sila=2.8, kolor_k=5400)
        for i, o in enumerate(WITRYNA):
            w.portal_okna(plan, f"portal{i}", "x", D, *o, strona_wew=-1, moc=220, kolor_k=6800)
        for i, (x, y) in enumerate(((1.7, 4.15), (4.3, 4.15), (1.7, 2.4), (4.2, 2.3))):
            w.lampa_punkt(f"lampa_sw{i}", (x, y, H - 1.25), 8, 2800)
        w.ekspozycja(0.9)
    else:
        w.niebo("cobblestone_street_night", sila=0.18, obrot_z=180, tlo_sila=0.9)
        for i, (x, y) in enumerate(((1.7, 4.15), (4.3, 4.15), (1.7, 2.4), (4.2, 2.3))):
            w.lampa_punkt(f"lampa_sw{i}", (x, y, H - 1.25), 45, 2600, promien=0.1)
        w.lampa_obszar("lada_podswietlenie", (4.1, 0.3, 2.5), 2.6, 80, 2700, (0, 0, 0), rozmiar_y=0.3)

    w.kamera(plan, "K01_przy_oknie_dwojka", (1.7, 2.85, 1.3), (1.7, 4.4, 1.05), 28, "dwójka z boku: Kuba i Zosia przy stoliku, ulica w tle")
    w.kamera(plan, "K02_kuba_przez_ramie_zosi", (2.6, 3.95, 1.3), (1.15, 4.15, 1.12), 50, "Kuba mówi (przez ramię Zosi)")
    w.kamera(plan, "K03_zosia_przez_ramie_kuby", (0.8, 3.95, 1.3), (2.25, 4.15, 1.12), 50, "Zosia mówi (przez ramię Kuby)")
    w.kamera(plan, "K04_plan_ogolny", (5.4, 0.6, 1.75), (1.8, 4.2, 0.9), 18, "plan ogólny: lada, stoliki, witryna")
    w.kamera(plan, "K05_detal_kubki", (1.35, 3.75, 1.0), (1.7, 4.15, 0.76), 50, "detal: dwa kubki na stoliku, dłonie")
    w.kamera(plan, "K06_wejscie_od_lady", (4.0, 1.4, 1.45), (0.5, 4.6, 1.2), 26, "z lady na salę i stolik przy oknie")

    w.znacznik(plan, "M_Kuba_stolik", (1.15, 4.15, 1.15), opis="Kuba siedzi przy stoliku przy oknie", patrz_na=(2.25, 4.15))
    w.znacznik(plan, "M_Zosia_stolik", (2.25, 4.15, 1.15), opis="Zosia siedzi naprzeciw", patrz_na=(1.15, 4.15))
    w.znacznik(plan, "M_barista", (4.0, 0.35, 1.62), opis="osoba za ladą", patrz_na=(4.0, 2.5))
