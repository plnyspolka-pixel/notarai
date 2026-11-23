"""S02 Gabinet Heleny: pokój czynności w kamienicy (stół na 6 osób, regał akt, dwa okna)."""
import wspolne as w

NAZWA = "Gabinet Heleny (pokój czynności)"
WARIANTY = ["dzien", "wieczor"]
W, D, H = 5.2, 4.6, 3.2
OKNA = [(1.0, 2.1, 0.85, 2.8), (3.1, 4.2, 0.85, 2.8)]
RUCH = ("K02_dwojka_przez_stol", (1.35, 1.35, 1.32))


def zbuduj(plan, wariant):
    podloga = w.tekstura("parkiet", "herringbone_parquet", skala=0.9, szorstkosc_mnoz=0.9, sila_normal=0.4)
    sciany = w.kolor("sciana_ciepla_biel", (0.86, 0.83, 0.78), 0.85, polysk=0.25, normal_tex="painted_plaster_wall", skala=0.6, sila_normal=0.15)
    w.pokoj("gab", W, D, H, podloga, sciany, otwory={"N": OKNA, "S": [(0.4, 1.35, 0, 2.15)]})
    for i, (a, b, dol, gora) in enumerate(OKNA):
        w.okno(f"okno{i}", "x", D + 0.05, a, b, dol, gora, strona_wew=-1)
        w.kaloryfer(f"kal{i}", "x", D, (a + b) / 2, dl=0.9, strona_wew=-1)
    w.drzwi("drzwi", "x", 0.0, 0.4, 1.35, otwarte=15, strona_wew=+1)

    # stół do czynności i krzesła
    w.wstaw("dining_table", (2.5, 2.25, 0), 0, wyklucz=["cloth"], nazwa="stol",
            mat_nadpisz=w.tekstura("blat_orzech", "oak_veneer_01", skala=0.8, odcien=(0.55, 0.36, 0.22), szorstkosc_mnoz=0.6, sila_normal=0.2, polysk=0.6))
    w.dywan("dywan", (2.5, 2.25), 3.6, 2.7, odcien=(0.23, 0.17, 0.16))
    krzesla = [(3.78, 2.25), (1.2, 2.25), (2.0, 1.45), (3.0, 1.45), (2.0, 3.05), (3.0, 3.05)]
    for i, (x, y) in enumerate(krzesla):  # każde krzesło przodem do stołu (prostopadle do krawędzi)
        cel = (2.5, 2.25) if y == 2.25 else (x, 2.25)
        w.wstaw("dining_chair_02", (x, y, 0), nazwa=f"krzeslo{i}", patrz_na=cel)
    w.teczki("teczki_stol", (3.25, 2.25, 0.79), 3, obrot_z=8)
    w.kartki("kartki_stol", (2.55, 1.85, 0.79), 3, obrot_z=-5)
    w.kartki("kartki_stol2", (2.45, 2.62, 0.79), 2, obrot_z=175)
    w.kubek("kubek_h", (3.45, 2.6, 0.79))
    w.wstaw("jug_01", (2.2, 2.75, 0.79), 30)
    # więcej rekwizytów na stole (bez napisów): szklanki, długopisy, skórzana teczka, podkładka, miseczka
    szklo = w.szyba("szklo_szklanki")
    for i, (x, y) in enumerate(((2.0, 1.95), (3.0, 1.95), (2.9, 2.62), (3.55, 2.05))):
        w.walec(f"szklanka{i}", 0.035, 0.1, (x, y, 0.84), szklo, 24)
    for i, (x, y, r) in enumerate(((2.7, 1.82, 15), (2.35, 1.9, -20), (3.6, 2.42, 80))):
        d = w.walec(f"dlugopis{i}", 0.005, 0.14, (x, y, 0.797), w.kolor("dlugopis", (0.03, 0.04, 0.08), 0.3, metal=0.4), 12)
        d.rotation_euler = (1.5708, 0, w.math.radians(r))
    w.skrzynka("teczka_skorzana", (0.36, 0.27, 0.02), (3.45, 2.1, 0.80), w.kolor("skora_bordo", (0.22, 0.05, 0.05), 0.45, polysk=0.4), obrot_z=-4, kolekcja="rekwizyty_wlasne", fazka=0.006)
    w.skrzynka("podkladka_heleny", (0.5, 0.36, 0.006), (3.45, 2.6, 0.793), w.kolor("podkladka_skora", (0.08, 0.06, 0.05), 0.5), obrot_z=90, kolekcja="rekwizyty_wlasne")
    w.walec("miseczka_spinacze", 0.05, 0.03, (2.75, 2.75, 0.805), w.kolor("ceramika_biala", (0.9, 0.89, 0.86), 0.25, polysk=0.7), 32)

    # regał akt przy ścianie zachodniej i komoda przy wschodniej
    w.regal_akt("regal", 0.22, 0.6, 2.6, wys=2.3, polki=5, wzdluz_x=False)
    w.wstaw("modern_wooden_cabinet", (W - 0.3, 2.3, 0), 90, nazwa="komoda")
    w.wstaw("ceramic_vase_01", (W - 0.3, 1.6, 0.68), 0)
    w.wstaw("potted_plant_02", (W - 0.3, 3.05, 0.68), 40)
    for i, (c, t) in enumerate((((0.2, 0.25, 0.3), 0.04), ((0.6, 0.5, 0.36), 0.035))):
        w.skrzynka(f"ksiazki_komoda{i}", (0.26, 0.19, t), (W - 0.3, 2.0, 0.68 + t / 2 + i * 0.041), w.kolor(f"ksiazka_{c}", c, 0.6), obrot_z=90 + i * 8, kolekcja="rekwizyty_wlasne", fazka=0.003)
    w.walec("miska_komoda", 0.11, 0.07, (W - 0.3, 2.7, 0.715), w.kolor("ceramika_szara", (0.55, 0.53, 0.5), 0.35, polysk=0.6), 32)
    w.obraz_na_scianie("obraz", (W - 0.02, 2.3, 1.85), 1.0, 0.6, "W",
                       [(0.32, 0.33, 0.22), (0.55, 0.48, 0.3), (0.3, 0.36, 0.42), (0.78, 0.76, 0.7), (0.55, 0.64, 0.72)], styl="pejzaz")
    w.wstaw("potted_plant_01", (0.55, 4.05, 0), 10)
    w.regal_akt("regal2", 4.55, 4.35, 0.62, wys=2.3, polki=5, wzdluz_x=True, wypelnienie=0.7)

    # lampy sufitowe nad stołem
    for i, x in enumerate((1.9, 3.1)):
        w.wstaw("modern_ceiling_lamp_01", (x, 2.25, H - 0.95 - 0.22), 0, nazwa=f"lampa{i}")

    if wariant == "dzien":
        w.niebo("courtyard", sila=1.4, obrot_z=40, tlo_sila=0.9)
        w.podworze_za_oknem("oficyna", "x", D, -1, OKNA[0][0], OKNA[-1][1], odl=7.0)
        w.slonce((0.35, -1.0, -0.55), sila=3.5, kolor_k=5200)
        w.ekspozycja(1.0)
        for i, (a, b, dol, gora) in enumerate(OKNA):
            w.portal_okna(plan, f"portal{i}", "x", D, a, b, dol, gora, strona_wew=-1, moc=260, kolor_k=6800)
        for i, x in enumerate((1.9, 3.1)):
            w.lampa_punkt(f"lampa_sw{i}", (x, 2.25, H - 0.85), 8, 3000)
    else:
        w.niebo("cobblestone_street_night", sila=0.15, tlo_sila=0.6)
        w.podworze_za_oknem("oficyna", "x", D, -1, OKNA[0][0], OKNA[-1][1], odl=7.0)
        for i, x in enumerate((1.9, 3.1)):
            w.lampa_punkt(f"lampa_sw{i}", (x, 2.25, H - 0.85), 70, 2800, promien=0.12)
        w.lampa_obszar("kinkiet_regal", (0.6, 1.9, 2.6), 0.8, 60, 2900, (0, 0, 0))
        w.lampa_obszar("swiatlo_z_korytarza", (0.9, -0.3, 1.2), 0.9, 40, 3200, (90, 0, 0))

    # kamery 9:16
    w.kamera(plan, "K01_plan_ogolny", (4.85, 0.35, 1.72), (1.9, 3.1, 0.95), 16, "plan ogólny od drzwi: stół, regał, okna")
    w.kamera(plan, "K02_dwojka_przez_stol", (1.05, 1.05, 1.35), (3.5, 2.55, 1.05), 28, "dwójka: Helena u szczytu i klient z przodu")
    w.kamera(plan, "K03_helena_zblizenie", (1.55, 2.2, 1.12), (3.78, 2.25, 1.12), 50, "Helena u szczytu stołu na wprost, krawędź stołu na pierwszym planie")
    w.kamera(plan, "K04_klienci_od_heleny", (4.35, 2.55, 1.42), (2.1, 1.75, 1.0), 32, "kontrplan zza Heleny na klientów")
    w.kamera(plan, "K05_detal_stol", (2.95, 1.5, 1.22), (3.2, 2.3, 0.79), 40, "detal: teczki i kartki na stole (do warstwy dokumentu)")
    w.kamera(plan, "K06_na_drzwi", (3.6, 3.7, 1.62), (0.85, 0.0, 1.15), 24, "wejście klienta / Basia w drzwiach")
    w.kamera(plan, "K07_okno_sylwetka", (2.6, 0.9, 1.5), (2.6, 4.6, 1.5), 26, "postać przy oknie, światło z tyłu")

    w.znacznik(plan, "M_Helena_szczyt", (3.78, 2.25, 1.2), opis="Helena siedzi u szczytu stołu, oczy ok. 1,2 m", patrz_na=(2.5, 2.25))
    w.znacznik(plan, "M_klient_przod_L", (2.0, 1.45, 1.18), opis="klient siedzi przodem do okien", patrz_na=(2.0, 2.25))
    w.znacznik(plan, "M_klient_przod_P", (3.0, 1.45, 1.18), opis="drugi klient obok", patrz_na=(3.0, 2.25))
    w.znacznik(plan, "M_klient_tyl_L", (2.0, 3.05, 1.18), opis="klient tyłem do okien", patrz_na=(2.0, 2.25))
    w.znacznik(plan, "M_klient_tyl_P", (3.0, 3.05, 1.18), opis="klient tyłem do okien", patrz_na=(3.0, 2.25))
    w.znacznik(plan, "M_wejscie", (0.9, 0.55, 1.62), opis="postać stoi w drzwiach, oczy 1,62 m", patrz_na=(2.5, 2.25))
    w.znacznik(plan, "M_przy_oknie", (2.6, 3.95, 1.62), opis="postać stoi przy oknie", patrz_na=(2.6, 2.0))
