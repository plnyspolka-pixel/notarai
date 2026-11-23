"""S10 Mieszkanie Ireny: pokój dzienny (sofa, fotel, herbata, firanki) i obok klatka schodowa bez windy (strome, stare schody)."""
import wspolne as w

NAZWA = "Mieszkanie Ireny i klatka bez windy"
WARIANTY = ["dzien", "wieczor"]
W, D, H = 5.0, 4.2, 2.9
OKNA = [(1.2, 2.6, 0.85, 2.55)]
KX = 7.0  # klatka schodowa obok, przesunięta w osi x
RUCH = ("K01_pokoj_szeroki", (3.4, 1.1, 1.5))


def zbuduj(plan, wariant):
    dzien = wariant == "dzien"
    podloga = w.tekstura("parkiet_stary", "herringbone_parquet", skala=0.9, odcien=(0.75, 0.62, 0.5), szorstkosc_mnoz=1.1, sila_normal=0.5)
    tapeta = w.kolor("tapeta", (0.78, 0.72, 0.6), 0.85, polysk=0.2, normal_tex="fabric_pattern_05", skala=2.0, sila_normal=0.12)
    w.pokoj("ir", W, D, H, podloga, tapeta, otwory={"N": OKNA, "S": [(3.8, 4.7, 0, 2.05)]}, gzyms=False)
    w.okno("okno0", "x", D + 0.05, *OKNA[0], strona_wew=-1)
    w.firanka("firanka0", "x", D, *OKNA[0], strona_wew=-1)
    w.kaloryfer("kal0", "x", D, 1.9, dl=1.0, strona_wew=-1)
    w.drzwi("drzwi_pokoj", "x", 0.0, 3.8, 4.7, wys=2.05, otwarte=8, strona_wew=+1, mat=w.kolor("drzwi_kremowe", (0.85, 0.8, 0.68), 0.45))
    w.wstaw("Sofa_01", (1.0, 1.0, 0), 0, nazwa="sofa")
    w.wstaw("throw_pillows_01", (1.0, 1.05, 0.42), 0, skala=0.8)
    w.wstaw("ArmChair_01", (2.7, 1.9, 0), 120, nazwa="fotel")
    w.wstaw("coffee_table_round_01", (1.3, 2.0, 0), 0, skala=0.55, nazwa="lawa")
    w.wstaw("tea_set_01", (1.3, 2.0, 0.27), 20, tylko=["teapot_01", "cup_small_01", "saucer_circular_04", "sugar_cup_01"], skala=0.9)
    w.dywan("dywan_ir", (1.6, 1.8), 2.4, 1.9, odcien=(0.35, 0.12, 0.1))
    w.wstaw("wooden_display_shelves_01", (4.6, 2.4, 0), -90, nazwa="witryna")
    for i, (x, y, z) in enumerate(((4.62, 2.1, 1.0), (4.62, 2.6, 1.0), (4.62, 2.35, 1.4))):
        w.wstaw("ceramic_vase_01", (x, y, z), i * 40, skala=0.6)
    w.wstaw("side_table_tall_01", (3.3, 3.7, 0), 0)
    w.wstaw("potted_plant_02", (3.3, 3.7, 0.76), 10, skala=0.7)
    w.wstaw("side_table_01", (0.3, 2.9, 0), 90)
    w.telefon_biurkowy("telefon_ir", (0.3, 2.9, 0.55), 70)
    for i, (y, z, k) in enumerate(((1.0, 1.75, [(0.5, 0.4, 0.3), (0.82, 0.78, 0.66), (0.3, 0.38, 0.3)]), (2.2, 1.6, [(0.2, 0.25, 0.32), (0.75, 0.7, 0.6)]))):
        w.obraz_na_scianie(f"obraz_ir{i}", (0.02, y, z), 0.55 if i else 0.9, 0.45 if i else 0.6, "E", k, ziarno=31.0 + i)
    lampa_sw = w.swiecenie("abazur", (1.0, 0.85, 0.6), 3.0 if not dzien else 0.4)
    w.walec("lampa_stojaca_noga", 0.015, 1.4, (3.4, 0.55, 0.7), w.kolor("mosiadz", (0.75, 0.6, 0.35), 0.25, metal=1.0))
    w.walec("lampa_stojaca_abazur", 0.2, 0.28, (3.4, 0.55, 1.5), lampa_sw)

    # klatka schodowa bez windy: wąski bieg, lamperia, drzwi mieszkania
    terrazzo = w.tekstura("terrazzo_stare", "terrazzo_tiles", skala=1.0, odcien=(0.85, 0.8, 0.72), sila_normal=0.3)
    sc_kl = w.kolor("sciana_klatka_ir", (0.8, 0.76, 0.64), 0.85, polysk=0.25, normal_tex="rough_plaster_03", skala=0.8, sila_normal=0.3)
    w.skrzynka("kl_podest", (2.4, 1.6, 0.12), (KX + 1.2, 3.4, -0.06), terrazzo)
    w.skrzynka("kl_dol", (2.4, 2.8, 0.1), (KX + 1.2, 1.2, -2.6), terrazzo)
    w.sciana("kl_scW", "y", KX - 0.1, -0.2, 4.4, H + 2.6, sc_kl, z0=-2.6)
    w.sciana("kl_scE", "y", KX + 2.5, -0.2, 4.4, H + 2.6, sc_kl, z0=-2.6)
    w.sciana("kl_scN", "x", 4.3, KX - 0.2, KX + 2.6, H + 2.6, sc_kl, otwory=[(KX + 0.5, KX + 1.4, 2.6, 4.65)], z0=-2.6)
    w.sciana("kl_scS", "x", -0.1, KX - 0.2, KX + 2.6, H + 2.6, sc_kl, z0=-2.6)
    w.skrzynka("kl_sufit", (2.8, 4.6, 0.1), (KX + 1.2, 2.1, H + 0.05), sc_kl)
    lamp = w.kolor("lamperia_ir", (0.42, 0.3, 0.18), 0.3, polysk=0.7)
    w.skrzynka("kl_lamperia_W", (0.01, 4.4, 1.4), (KX - 0.0, 2.1, 0.7), lamp)
    w.skrzynka("kl_lamperia_E", (0.01, 4.4, 4.0), (KX + 2.4, 2.1, -0.6), lamp)
    w.schody("kl_bieg", KX + 1.1, KX + 2.35, 2.6, -1, 0.0, 13, wznios=-0.2, glebokosc=0.2, porecz_x=KX + 1.08,
             mat=w.tekstura("stopnie_drewno", "stair_planks", skala=1.5, odcien=(0.7, 0.55, 0.4)))
    w.drzwi("drzwi_mieszkania", "x", 4.3, KX + 0.5, KX + 1.4, wys=2.05, strona_wew=-1, mat=w.kolor("drzwi_brazowe_ir", (0.32, 0.2, 0.12), 0.45))
    w.walec("kl_zarowka", 0.06, 0.1, (KX + 1.2, 2.5, H - 0.1), w.swiecenie("zarowka", (1.0, 0.82, 0.55), 6.0))

    if dzien:
        w.niebo("urban_street_01", sila=1.2, obrot_z=40, tlo_sila=0.7)
        w.slonce((0.3, -1.0, -0.45), sila=3.0, kolor_k=5000)
        w.portal_okna(plan, "portal0", "x", D, *OKNA[0], strona_wew=-1, moc=240, kolor_k=6500)
        w.lampa_punkt("kl_zarowka_sw", (KX + 1.2, 2.5, H - 0.25), 40, 2700)
        w.ekspozycja(0.9)
    else:
        w.niebo("modern_buildings_night", sila=0.12, tlo_sila=0.5)
        w.lampa_punkt("abazur_sw", (3.4, 0.55, 1.5), 90, 2600, promien=0.18)
        w.lampa_punkt("kl_zarowka_sw", (KX + 1.2, 2.5, H - 0.25), 60, 2600)

    w.kamera(plan, "K01_pokoj_szeroki", (4.5, 0.75, 1.6), (1.0, 3.0, 0.9), 18, "pokój Ireny: sofa, fotel, okno z firanką")
    w.kamera(plan, "K02_irena_na_sofie", (2.3, 2.6, 1.15), (1.0, 1.0, 1.0), 40, "Irena na sofie (ujęcie mówione)")
    w.kamera(plan, "K03_dwojka_sofa_fotel", (0.4, 3.6, 1.45), (2.2, 1.3, 0.95), 26, "dwójka: Irena na sofie, Paweł w fotelu")
    w.kamera(plan, "K04_detal_herbata", (1.6, 2.45, 0.8), (1.3, 2.0, 0.3), 45, "detal: herbata na ławie")
    w.kamera(plan, "K05_okno_firanka", (2.6, 1.2, 1.4), (1.9, 4.2, 1.6), 28, "Irena przy oknie za firanką")
    w.kamera(plan, "K06_klatka_z_dolu", (KX + 1.7, 0.3, -1.0), (KX + 1.0, 3.6, 1.2), 22, "klatka bez windy: z dołu na strome schody")
    w.kamera(plan, "K07_klatka_podest_drzwi", (KX + 2.0, 2.4, 1.6), (KX + 0.95, 4.3, 1.1), 26, "podest przed drzwiami mieszkania, zadyszka po schodach")

    w.znacznik(plan, "M_Irena_sofa", (1.0, 1.0, 1.1), 0, "Irena siedzi na sofie (oczy ok. 1,1 m)")
    w.znacznik(plan, "M_Pawel_fotel", (2.7, 1.9, 1.1), 120, "Paweł siedzi w fotelu")
    w.znacznik(plan, "M_przy_oknie", (1.9, 3.7, 1.6), 0, "postać przy oknie, tyłem do pokoju")
    w.znacznik(plan, "M_klatka_schody", (KX + 1.7, 1.6, 1.6 - 1.2), 0, "Irena wchodzi po schodach (w połowie biegu)")
    w.znacznik(plan, "M_klatka_podest", (KX + 0.95, 3.6, 1.6), 0, "postać przed drzwiami mieszkania")
