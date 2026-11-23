"""S07 Ulica przed kancelarią: fasada kamienicy (parter + 3 piętra), brama, chodnik, jezdnia; dzień i noc z mokrym asfaltem."""
import wspolne as w

NAZWA = "Ulica przed kancelarią (fasada kamienicy)"
WARIANTY = ["dzien", "noc"]
KAMERY_WARIANTU = {"noc": ["K01_przez_ulice", "K02_brama", "K03_okna_kancelarii", "K05_chodnik_w_glab"]}
SZER = 16.0  # szerokość fasady (oś x), fasada w płaszczyźnie y = 0, ulica po stronie -y
RUCH = ("K02_brama", (8.0, -3.2, 1.6))


def _okno_fasady(nazwa, x, z, s=1.3, h=2.0, swieci=False, mat_rama=None):
    rama = mat_rama or w.kolor("rama_fasada", (0.88, 0.87, 0.84), 0.35)
    szk = w.kolor("szyba_fasada", (0.04, 0.05, 0.06), 0.03, polysk=1.0) if not swieci else w.swiecenie("okno_swieci", (1.0, 0.78, 0.5), 2.2)
    w.skrzynka(f"{nazwa}_wneka", (s, 0.25, h), (x, 0.12, z + h / 2), szk, kolekcja="fasada")
    for n, roz, pos in (("d", (s + 0.16, 0.08, 0.08), (x, -0.04, z)), ("g", (s + 0.16, 0.08, 0.08), (x, -0.04, z + h)),
                        ("l", (0.08, 0.08, h), (x - s / 2 - 0.04, -0.04, z + h / 2)), ("p", (0.08, 0.08, h), (x + s / 2 + 0.04, -0.04, z + h / 2)),
                        ("s", (0.06, 0.06, h), (x, -0.01, z + h / 2)), ("pz", (s, 0.06, 0.06), (x, -0.01, z + h * 0.72))):
        w.skrzynka(f"{nazwa}_{n}", roz, pos, rama, kolekcja="fasada")
    w.skrzynka(f"{nazwa}_parapet", (s + 0.3, 0.22, 0.06), (x, -0.1, z - 0.04), w.kolor("parapet_zew", (0.5, 0.5, 0.48), 0.6), kolekcja="fasada")
    w.skrzynka(f"{nazwa}_nadproze", (s + 0.4, 0.12, 0.18), (x, -0.06, z + h + 0.2), w.kolor("tynk_detal", (0.78, 0.72, 0.6), 0.8), kolekcja="fasada", fazka=0.02)


def zbuduj(plan, wariant):
    noc = wariant == "noc"
    tynk = w.tekstura("tynk_fasada", "white_stucco", skala=0.5, odcien=(0.86, 0.76, 0.6), sila_normal=0.6)
    detal = w.kolor("tynk_detal", (0.78, 0.72, 0.6), 0.8, normal_tex="white_stucco", skala=0.5, sila_normal=0.4)
    cokol = w.tekstura("cokol_granit", "granite_tile", skala=0.6, jasnosc=0.7)
    # fasada z otworami na bramę i okna (okna wstawione jako wnęki przed ścianą)
    w.skrzynka("fasada", (SZER, 0.3, 15.0), (SZER / 2, 0.45, 7.5), tynk, kolekcja="fasada")
    w.skrzynka("cokol", (SZER, 0.1, 0.9), (SZER / 2, 0.25, 0.45), cokol, kolekcja="fasada")
    for i, z in enumerate((3.6, 7.0, 10.4)):
        w.skrzynka(f"gzyms{i}", (SZER, 0.18, 0.16), (SZER / 2, 0.21, z - 0.25), detal, kolekcja="fasada", fazka=0.03)
    w.skrzynka("gzyms_wienczacy", (SZER, 0.45, 0.4), (SZER / 2, 0.1, 13.8), detal, kolekcja="fasada", fazka=0.06)
    # brama (podwójne drzwi drewniane) na środku
    brama = w.tekstura("brama_drewno", "dark_wood", skala=1.0, szorstkosc_mnoz=0.6)
    w.skrzynka("brama_wneka", (2.2, 0.3, 3.2), (8.0, 0.4, 1.6), w.kolor("ciemnosc", (0.01, 0.01, 0.01), 0.9), kolekcja="fasada")
    for i, x in enumerate((7.47, 8.53)):
        w.skrzynka(f"brama_skrzydlo{i}", (1.02, 0.08, 2.9), (x, 0.26, 1.45), brama, kolekcja="fasada", fazka=0.01)
        for j, (z, h) in enumerate(((0.65, 0.9), (1.95, 1.2))):
            w.skrzynka(f"brama_plycina{i}{j}", (0.72, 0.06, h), (x, 0.21, z), brama, kolekcja="fasada", fazka=0.02)
    w.skrzynka("brama_nadswietle", (2.1, 0.05, 0.55), (8.0, 0.25, 3.05), w.kolor("szyba_fasada", (0.04, 0.05, 0.06), 0.03, polysk=1.0), kolekcja="fasada")
    w.skrzynka("brama_luk", (2.6, 0.2, 0.25), (8.0, 0.2, 3.45), detal, kolekcja="fasada", fazka=0.04)
    # okna parteru i pięter; okna kancelarii na I piętrze (x 9.5–14) świecą nocą
    for x in (2.0, 4.5, 11.5, 14.0):
        _okno_fasady(f"o_p_{x}", x, 1.1, 1.4, 2.0)
    for p_i, z in enumerate((4.1, 7.5, 10.9)):
        for x in (2.0, 4.5, 6.6, 9.4, 11.5, 14.0):
            sw = noc and ((p_i == 0 and x >= 9.4) or (p_i == 2 and x == 4.5))
            _okno_fasady(f"o_{p_i}_{x}", x, z, 1.3, 2.1, swieci=sw)
    # chodnik, krawężnik, jezdnia
    chodnik = w.tekstura("chodnik", "rectangular_paving", skala=0.8, sila_normal=0.5, szorstkosc_mnoz=0.5 if noc else 1.0)
    w.skrzynka("chodnik", (SZER + 10, 3.4, 0.15), (SZER / 2, -1.7, -0.075), chodnik, kolekcja="ulica")
    w.skrzynka("kraweznik", (SZER + 10, 0.15, 0.17), (SZER / 2, -3.45, -0.065), w.kolor("granit_kraw", (0.5, 0.5, 0.5), 0.6, normal_tex="granite_tile", skala=1.0), kolekcja="ulica")
    asfalt = w.tekstura("asfalt", "asphalt_02", skala=0.5, sila_normal=0.4, szorstkosc_mnoz=0.25 if noc else 1.0, odcien=(0.6, 0.6, 0.62) if noc else None)
    w.skrzynka("jezdnia", (SZER + 40, 14.0, 0.1), (SZER / 2, -10.5, -0.2), asfalt, kolekcja="ulica")
    w.wstaw("street_lamp_01", (3.0, -3.1, 0), 90, nazwa="latarnia1")
    w.wstaw("street_lamp_01", (13.5, -3.1, 0), 90, nazwa="latarnia2")
    w.wstaw("planter_box_01", (5.6, -0.5, 0), 0)
    w.wstaw("planter_box_01", (10.4, -0.5, 0), 0)
    w.wstaw("metal_trash_can", (12.6, -2.9, 0), 0, tylko=["metal_trash_can"], wyklucz=["rust"])

    if not noc:
        w.niebo("german_town_street", sila=1.2, obrot_z=200)
        w.slonce((0.4, 0.8, -0.6), sila=3.2, kolor_k=5400)
        w.ekspozycja(0.3)
    else:
        w.niebo("cobblestone_street_night", sila=0.25, obrot_z=200)
        for i, x in enumerate((3.0, 13.5)):
            w.lampa_punkt(f"latarnia_sw{i}", (x - 0.05, -2.7, 3.7), 900, 2400, promien=0.15)
        w.lampa_punkt("brama_kinkiet", (8.0, -0.3, 3.2), 60, 2600)
        w.ekspozycja(0.4)

    w.kamera(plan, "K01_przez_ulice", (8.0, -14.0, 1.6), (8.0, 0.0, 4.8), 24, "przez ulicę: cała kamienica z bramą (ujęcie lokalizacyjne)")
    w.kamera(plan, "K02_brama", (8.0, -4.6, 1.55), (8.0, 0.2, 1.6), 30, "postać wchodzi do bramy / wychodzi z kancelarii")
    w.kamera(plan, "K03_okna_kancelarii", (9.0, -5.5, 1.3), (11.5, 0.0, 5.2), 35, "żabia perspektywa na okna kancelarii na I piętrze")
    w.kamera(plan, "K04_detal_brama", (7.3, -1.2, 1.2), (8.3, 0.2, 1.3), 40, "detal: dłoń na skrzydle bramy")
    w.kamera(plan, "K05_chodnik_w_glab", (1.0, -2.0, 1.55), (14.0, -1.2, 1.2), 35, "chodnik wzdłuż fasady: ktoś idzie do bramy")
    w.kamera(plan, "K06_z_jezdni_na_brame", (12.5, -6.0, 1.45), (8.0, 0.0, 1.6), 30, "z przeciwnej strony ulicy, ukosem na bramę")

    w.znacznik(plan, "M_przed_brama", (8.0, -1.2, 1.62), opis="postać przed bramą, przodem do ulicy", patrz_na=(8.0, -6.0))
    w.znacznik(plan, "M_chodnik", (4.0, -1.6, 1.62), opis="postać idzie chodnikiem w stronę bramy", patrz_na=(8.0, -1.6))
    w.znacznik(plan, "M_przy_kraweznik", (11.0, -3.0, 1.62), opis="postać czeka przy krawężniku", patrz_na=(11.0, 0.0))
