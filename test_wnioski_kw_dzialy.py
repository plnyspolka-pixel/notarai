def test_dzialy_klucze():
    from wnioski_kw import DZIALY
    assert set(DZIALY) == {"I-O", "I-Sp", "II", "III", "IV"}


def test_dzialy_wartosci():
    from wnioski_kw import DZIALY
    for klucz, wartosc in DZIALY.items():
        assert wartosc.startswith("Dział " + klucz)
