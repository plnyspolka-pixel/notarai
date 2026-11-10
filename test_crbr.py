"""CRBR - koperta SOAP, parsowanie odpowiedzi, maskowanie PESEL. Bez sieci:
bramke udaje httpx.MockTransport."""
import httpx

import crbr

ODPOWIEDZ_OK = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
<soap:Body>
<ns:PobierzInformacjeOSpolkachIBeneficjentachOdpowiedz xmlns:ns="http://www.mf.gov.pl/uslugiBiznesowe/uslugiESB/AP/ApiPrzegladoweCRBR/2022/12/01" xmlns:ns1="http://www.mf.gov.pl/schematy/AP/ApiPrzegladoweCRBR/2022/12/01">
<PobierzInformacjeOSpolkachIBeneficjentachOdpowiedzDane>
<ns1:Status>IstniejaInformacje</ns1:Status>
<ns1:IdentyfikatorWniosku>W-123</ns1:IdentyfikatorWniosku>
<ns1:DataICzasZlozeniaWniosku>2026-11-07T10:00:00</ns1:DataICzasZlozeniaWniosku>
<ns1:ListaInformacjiOSpolkachIBeneficjentach>
 <ns1:SpolkaIBeneficjenci>
  <ns1:NIP>5261040828</ns1:NIP><ns1:KRS>0000012345</ns1:KRS><ns1:Nazwa>PRZYKLAD SP. Z O.O.</ns1:Nazwa>
  <ns1:OpisFormyOrganizacyjnej>spolka z ograniczona odpowiedzialnoscia</ns1:OpisFormyOrganizacyjnej>
  <ns1:KodPocztowy>00-001</ns1:KodPocztowy><ns1:Miejscowosc>Warszawa</ns1:Miejscowosc>
  <ns1:Ulica>Prosta</ns1:Ulica><ns1:NrDomu>1</ns1:NrDomu><ns1:NrLokalu>2</ns1:NrLokalu>
  <ns1:ListaBeneficjentowRzeczywistych>
   <ns1:BeneficjentRzeczywisty>
    <ns1:PierwszeImie>Jan</ns1:PierwszeImie><ns1:KolejneImiona>Maria</ns1:KolejneImiona>
    <ns1:Nazwisko>Kowalski</ns1:Nazwisko><ns1:PESEL>%PESEL%</ns1:PESEL>
    <ns1:DataUrodzenia>1980-05-05</ns1:DataUrodzenia>
    <ns1:Obywatelstwo><ns1:Nazwa>Polska</ns1:Nazwa></ns1:Obywatelstwo>
    <ns1:KrajZamieszkania><ns1:Nazwa>Polska</ns1:Nazwa></ns1:KrajZamieszkania>
    <ns1:ListaInformacjiOUdzialach><ns1:InformacjaOUdzialach>
      <ns1:UprawnieniaWlascicielskieBezposrednie>udzialy 60 proc.</ns1:UprawnieniaWlascicielskieBezposrednie>
    </ns1:InformacjaOUdzialach></ns1:ListaInformacjiOUdzialach>
   </ns1:BeneficjentRzeczywisty>
  </ns1:ListaBeneficjentowRzeczywistych>
  <ns1:ListaZglaszajacych>
   <ns1:Zglaszajacy><ns1:PierwszeImie>Anna</ns1:PierwszeImie><ns1:Nazwisko>Nowak</ns1:Nazwisko>
    <ns1:ListaFunkcjiZglaszajacego><ns1:Funkcja><ns1:Opis>prezes zarzadu</ns1:Opis></ns1:Funkcja></ns1:ListaFunkcjiZglaszajacego>
   </ns1:Zglaszajacy>
  </ns1:ListaZglaszajacych>
 </ns1:SpolkaIBeneficjenci>
</ns1:ListaInformacjiOSpolkachIBeneficjentach>
</PobierzInformacjeOSpolkachIBeneficjentachOdpowiedzDane>
</ns:PobierzInformacjeOSpolkachIBeneficjentachOdpowiedz>
</soap:Body></soap:Envelope>"""

ODPOWIEDZ_BRAK = """<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body>
<PobierzInformacjeOSpolkachIBeneficjentachOdpowiedz><PobierzInformacjeOSpolkachIBeneficjentachOdpowiedzDane>
<Status>BrakInformacji</Status><IdentyfikatorWniosku>W-2</IdentyfikatorWniosku>
</PobierzInformacjeOSpolkachIBeneficjentachOdpowiedzDane></PobierzInformacjeOSpolkachIBeneficjentachOdpowiedz>
</soap:Body></soap:Envelope>"""

FAULT = """<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body>
<soap:Fault><soap:Code><soap:Value>soap:Sender</soap:Value></soap:Code>
<soap:Reason><soap:Text xml:lang="pl">Niepoprawny NIP</soap:Text></soap:Reason></soap:Fault>
</soap:Body></soap:Envelope>"""

PESEL = "80050512345"


def odpowiedz_ok():
    return ODPOWIEDZ_OK.replace("%PESEL%", PESEL)


class TestNormalizacja:
    def test_nip_i_krs(self):
        assert crbr.normalizuj_nip("526-104-08-28") == "5261040828"
        assert crbr.normalizuj_nip("123") is None
        assert crbr.normalizuj_krs("12345") == "0000012345"
        assert crbr.normalizuj_krs("abc") is None

    def test_koperta_ma_operacje_i_kryterium(self):
        k = crbr.koperta("NIP", "5261040828")
        assert "PobierzInformacjeOSpolkachIBeneficjentach" in k
        assert "<ns1:NIP>5261040828</ns1:NIP>" in k
        assert "<" not in crbr.koperta("Nazwa", "A<B")[crbr.koperta("Nazwa", "A<B").index("ns1:Nazwa>") + 10:].split("<")[0]


class TestParsowanie:
    def test_ok_z_beneficjentami_i_maska_pesel(self):
        w = crbr.parsuj_odpowiedz(odpowiedz_ok(), "NIP", "5261040828")
        assert w.status == "ok"
        assert w.spolka.nazwa == "PRZYKLAD SP. Z O.O." and w.spolka.krs == "0000012345"
        assert w.spolka.adres == "Prosta 1/2, 00-001 Warszawa"
        b = w.beneficjenci[0]
        assert b.imie_nazwisko == "Jan Maria Kowalski" and b.data_urodzenia == "1980-05-05"
        assert b.pesel_maska == "8005*******" and PESEL not in str(w.slownik())
        assert b.uprawnienia == "udzialy 60 proc." and b.obywatelstwa == ["Polska"]
        assert w.zglaszajacy[0].funkcja == "prezes zarzadu"
        assert w.identyfikator_wniosku == "W-123"

    def test_brak_informacji(self):
        w = crbr.parsuj_odpowiedz(ODPOWIEDZ_BRAK, "NIP", "1")
        assert w.status == "brak" and w.identyfikator_wniosku == "W-2"

    def test_fault(self):
        w = crbr.parsuj_odpowiedz(FAULT)
        assert w.status == "blad" and w.kod == "SOAP_FAULT" and "Niepoprawny NIP" in w.komunikat

    def test_smieci(self):
        assert crbr.parsuj_odpowiedz("<nie>xml").kod == "PARSE_ERROR"
        assert crbr.parsuj_odpowiedz("<a/>").kod == "UNEXPECTED_RESPONSE"

    def test_opis_dla_sladu_bez_pesel(self):
        opis = crbr.opis_dla_sladu(crbr.parsuj_odpowiedz(odpowiedz_ok(), "NIP", "5261040828"))
        assert "Jan Maria Kowalski" in opis and "prezes zarzadu" in opis and PESEL not in opis

    def test_dopasowanie_stron(self):
        w = crbr.parsuj_odpowiedz(odpowiedz_ok(), "NIP", "5261040828")
        wynik = crbr.dopasuj_osoby(["Jan Kowalski", "Zofia Wiśniewska"], w.beneficjenci)
        assert wynik == {"Jan Kowalski": True, "Zofia Wiśniewska": False}


class TestZapytanie:
    def test_bledne_dane_bez_sieci(self):
        assert crbr.sprawdz(nazwa="ab").status == "bledne_dane"

    def test_wywolanie_przez_atrape(self):
        widziane = {}

        def obsluga(zadanie: httpx.Request):
            widziane["url"] = str(zadanie.url)
            widziane["cialo"] = zadanie.content.decode("utf-8")
            return httpx.Response(200, text=odpowiedz_ok())

        klient = httpx.Client(transport=httpx.MockTransport(obsluga))
        w = crbr.sprawdz(nip="526 104 08 28", klient=klient)
        assert w.status == "ok" and widziane["url"] == crbr.ADRES
        assert "<ns1:NIP>5261040828</ns1:NIP>" in widziane["cialo"]

    def test_krs_gdy_brak_nip(self):
        klient = httpx.Client(transport=httpx.MockTransport(lambda z: httpx.Response(200, text=ODPOWIEDZ_BRAK)))
        assert crbr.sprawdz(krs="12345", klient=klient).status == "brak"

    def test_http_500(self):
        klient = httpx.Client(transport=httpx.MockTransport(lambda z: httpx.Response(500, text="awaria")))
        w = crbr.sprawdz(nip="5261040828", klient=klient)
        assert w.status == "blad" and w.kod == "HTTP_500"

    def test_timeout(self):
        def obsluga(z):
            raise httpx.ReadTimeout("za dlugo")
        klient = httpx.Client(transport=httpx.MockTransport(obsluga))
        assert crbr.sprawdz(nip="5261040828", klient=klient).kod == "TIMEOUT"
