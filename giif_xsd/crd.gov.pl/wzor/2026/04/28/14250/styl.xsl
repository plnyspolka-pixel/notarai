<?xml version="1.0" encoding="UTF-8"?><xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:n1="http://crd.gov.pl/wzor/2026/04/28/14250/" xmlns:n2="http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2018/10/10/giif/typy/" version="1.0">
    <xsl:param name="skrot"/>
    <xsl:param name="plzId"/>
    <xsl:param name="data"/>
    <xsl:template match="/n1:Dokument">
        <html>
            <head>
                <xsl:choose>
                    <xsl:when test="/n1:Dokument/n1:TrescDokumentu/n1:Karta/@korekta = 'true'">
                        <title>Korekta transakcji notarialnej</title>
                    </xsl:when>
                    <xsl:when test="/n1:Dokument/n1:TrescDokumentu/n1:Karta/@korekta = 'false'">
                        <title>Transakcja notarialna</title>
                    </xsl:when>
                    <xsl:otherwise>
                        <title>Formularz GIIF</title>
                    </xsl:otherwise>
                </xsl:choose>
                <style type="text/css">
                    #container.karta {
                        color: black;
                        margin: 0 auto;
                        padding: 1.5rem;
                        display: flex;
                        flex-flow: column;
                        width: 800px;
                        border: solid 1px gray;
                        font-size: 12px;
                        font-family: "Lato", sans-serif !important;
                        word-spacing: 2px;
                    }
                    #container.karta &gt; * {
                        font-family: "Lato", sans-serif !important;
                    }
                    #container.karta .naglowek_tekst {
                        display: block !important;
                    }
                    #container.karta .naglowek_tekst h1 {
                        font-size: 1.5em !important;
                    }
                    #container.karta .naglowek_tekst h2 {
                        font-size: 1.2em !important;
                        font-weight: normal;
                    }
                    #container.karta .row {
                        display: flex;
                        flex-flow: row;
                        padding: 5px 20px;
                        break-inside: avoid;
                        justify-content: space-between;
                    }
                    #container.karta .row &gt; :nth-child(1) {
                        flex-basis: 30%;
                        min-height: 20px;
                        display: flex;
                        align-items: center;
                    }
                    #container.karta .row &gt; :nth-child(2) {
                        flex-basis: 65%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }
                    #container.karta .row .wartosc {
                        border: solid 1px black;
                        padding: 10px;
                        text-align: center;
                        word-break: break-all;
                        break-inside: avoid;
                    }
                    #container.karta .row p {
                        margin: 0 !important;
                    }
                    #container.karta .indent {
                        margin: auto 30px;
                    }
                    #container.karta img {
                        width: 180px;
                    }
                    #container.karta img.logo {
                        margin-left: -15px;
                        margin-top: -10px;
                    }
                    #container.karta .podpis {
                        min-height: 60px;
                    }
                    #container.karta .tekst_bold {
                        font-weight: bold;
                    }
                    #container.karta .tekst_italic {
                        font-style: italic;
                    }
                    #container.karta .tekst_center {
                        text-align: center;
                    }
                    #container.karta .kod {
                        border: solid 1px black;
                        min-height: 70px;
                    }
                    #container.karta .miejscePodpis {
                        border: solid 1px black;
                        min-height: 100px;
                    }
                    #container.karta .przerywnik {
                        text-align: center;
                        font-weight: bold;
                        padding-top: 10px !important;
                        border-top: 0.5px solid lightgray;
                        font-size: 1em !important;
                        text-transform: uppercase;
                        margin-top: 10px !important;
                    }
                    #container.karta .przerywnik.przerywnik-2 {
                        border-top-style: dashed;
                        margin-top: 20px !important;
                    }
                    #container.karta .adresWysylki {
                        text-align: center;
                        width: 600px;
                        margin-right: auto;
                        margin-left: auto;
                    }
                    #container.karta .upo {
                        text-align: center;
                        word-break: break-all;
                        font-size: x-small;
                    }
                    #container.karta .mt-0 {
                        margin-top: 0;
                    }
                    #container.karta .mb-0 {
                        margin-bottom: 0;
                    }
                    
                    .hidden {
                        display: none;
                    }</style>
            </head>
            <body>
                <div id="container" class="karta">
                    <div class="row header">
                        <div class="naglowek">
                            <img class="logo" src="data:image/png;base64,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"/>
                        </div>
                        <div class="naglowek_tekst">
                            <h1>Generalny Inspektor Informacji Finansowej<br/>i Szef Krajowej
                                Administracji Skarbowej</h1>
                            <xsl:choose>
                                <xsl:when test="/n1:Dokument/n1:TrescDokumentu/n1:Karta/@korekta = 'true'">
                                    <h2>Korekta transakcji notarialnej</h2>
                                </xsl:when>
                                <xsl:when test="/n1:Dokument/n1:TrescDokumentu/n1:Karta/@korekta = 'false'">
                                    <h2>Transakcja notarialna</h2>
                                </xsl:when>
                                <xsl:otherwise>
                                    <h2>Formularz GIIF</h2>
                                </xsl:otherwise>
                            </xsl:choose>
                        </div>
                    </div>
                    <div class="row">
                        <div class="tekst">Data wygenerowania dokumentu: </div>
                        <div class="wartosc">
                            <xsl:value-of select="$data"/>
                        </div>
                    </div>
                    <div class="row">
                        <div class="tekst">Numer Identyfikacji Podatkowej<br/>instytucji
                            obowiązanej: </div>
                        <div class="wartosc">
                            <xsl:value-of select="./@nipIO"/>
                        </div>
                    </div>
                    <!-- Ilość zgłaszanych transakcji jeśli więcej niż 1 -->
                    <xsl:if test="count(/n1:Dokument/n1:TrescDokumentu/n1:Karta) &gt; 1">
                        <div class="row">
                            <div class="tekst">
                                <xsl:text>Ilość zgłaszanych transakcji:</xsl:text>
                            </div>
                            <div class="wartosc">
                                <xsl:value-of select="count(/n1:Dokument/n1:TrescDokumentu/n1:Karta)"/>
                            </div>
                        </div>
                    </xsl:if>
                    <xsl:for-each select="/n1:Dokument/n1:TrescDokumentu/n1:Karta">
                        <h3 class="przerywnik">DANE TRANSAKCJI</h3>
                        <xsl:call-template name="danetransakcji">
                            <xsl:with-param name="path1" select="."/>
                        </xsl:call-template>
                    </xsl:for-each>
                </div>
            </body>
        </html>
    </xsl:template>

    <xsl:template name="danetransakcji">
        <xsl:param name="path1"/>
        <div class="row">
            <div class="tekst">Status transakcji:</div>
            <div class="wartosc">
                <xsl:choose>
                    <xsl:when test="$path1/@korekta = 'true'">Korekta transakcji </xsl:when>
                    <xsl:otherwise>Transakcja pierwotna</xsl:otherwise>
                </xsl:choose>
            </div>
        </div>
        <xsl:choose>
            <xsl:when test="$path1/@korekta = 'true'">
                <div class="row">
                    <div class="tekst">Data i czas korekty:</div>
                    <div class="wartosc">
                        <xsl:value-of select="$path1/@dataKorekty"/>
                    </div>
                </div>
            </xsl:when>
        </xsl:choose>
        <div class="row">
            <div class="tekst">Transakcja ponadprogowa:</div>
            <div class="wartosc">
                <xsl:choose>
                    <xsl:when test="$path1/@dlaGIIF = 'true'"> TAK </xsl:when>
                    <xsl:otherwise>NIE</xsl:otherwise>
                </xsl:choose>
            </div>
        </div>
        <xsl:if test="./n1:IdentyfikatorTr/@nrCREWAN">
            <div class="row">
                <div class="tekst">Numer CREWAN (Rep. N.):</div>
                <div class="wartosc">
                    <xsl:value-of select="./n1:IdentyfikatorTr/@nrCREWAN"/>
                </div>
            </div>
        </xsl:if>
        <div class="row">
            <div class="tekst">Data aktu notarialnego:</div>
            <div class="wartosc">
                <xsl:value-of select="./n1:DataDokumentu"/>
            </div>
        </div>
        <div class="row">
            <div class="tekst">Rok repertorium:</div>
            <div class="wartosc">
                <xsl:value-of select="./n1:RokRepertorium"/>
            </div>
        </div>
        <div class="row">
            <div class="tekst">Numer repertorium:</div>
            <div class="wartosc">
                <xsl:value-of select="./n1:IdentyfikatorTr/n1:NumerRepertorium"/>
            </div>
        </div>
        <div class="row">
            <div class="tekst">Numer czynności:</div>
            <div class="wartosc">
                <xsl:value-of select="./n1:IdentyfikatorTr/n1:NumerCzynnosci"/>
            </div>
        </div>
        <div class="row">
            <div class="tekst">Data przeprowadzenia transakcji:</div>
            <div class="wartosc">
                <xsl:value-of select="./n1:DataTr"/>
            </div>
        </div>
        <div class="row">
            <div class="tekst">Kwota transakcji:</div>
            <div class="wartosc">
                <xsl:value-of select="./n1:KwotaTr"/>
            </div>
        </div>
        <div class="row">
            <div class="tekst">Kod waluty transakcji:</div>
            <div class="wartosc">
                <xsl:value-of select="./n1:KodWalutyTr"/>
            </div>
        </div>
        <div class="row">
            <div class="tekst">Kod rodzaju transakcji:</div>
            <div class="wartosc">
                <xsl:value-of select="./n1:KodRodzajuTr"/>
            </div>
        </div>
        <div class="row">
            <div class="tekst">Sposób wydania dyspozycji:</div>
            <div class="wartosc">
                <xsl:value-of select="./n1:SposobWydaniaDysp"/>
            </div>
        </div>
        <div class="row">
            <div class="tekst">Kod tytułu transakcji:</div>
            <div class="wartosc">
                <xsl:value-of select="./n1:TytulTr"/>
            </div>
        </div>
        <xsl:if test="./@czyOdplatna">
            <div class="row">
                <div class="tekst">Odpłatność:</div>
                <div class="wartosc">
                    <xsl:choose>
                        <xsl:when test="./@czyOdplatna = 'true'"> Transakcja odpłatna </xsl:when>
                        <xsl:when test="./@czyOdplatna = 'false'"> Transakcja nieodpłatna
                        </xsl:when>
                    </xsl:choose>
                </div>
            </div>
        </xsl:if>
        <div class="row">
            <div class="tekst">
                <xsl:text>Załącznik:</xsl:text>
            </div>
            <div class="wartosc">
                <xsl:choose>
                    <xsl:when test="not(./n1:TrescDokumentu)"> Nie </xsl:when>
                    <xsl:otherwise> Tak (<xsl:value-of select="./n1:TrescDokumentu/@plikTyp"/>)
                    </xsl:otherwise>
                </xsl:choose>
            </div>
        </div>
        <!-- Ilość zgłaszanych przedmiotów -->
        <div class="row">
            <div class="tekst">
                <xsl:text>Ilość przedmiotów transakcji:</xsl:text>
            </div>
            <div class="wartosc">
                <xsl:value-of select="count(./n1:DanePrzedmiotu)"/>
            </div>
        </div>
        <xsl:for-each select="./n1:DanePrzedmiotu">
            <xsl:call-template name="daneprzedmiotu">
                <xsl:with-param name="path" select="./n1:DanePrzedmiotu"/>
                <xsl:with-param name="waluta" select="./n1:KodWalutyTr"/>
            </xsl:call-template>
        </xsl:for-each>
        <h3 class="przerywnik"/>
        <xsl:if test="$path1/n1:Uwagi">
            <div class="row">
                <div class="tekst">Uwagi:</div>
                <div class="wartosc">
                    <xsl:value-of select="$path1/n1:Uwagi"/>
                </div>
            </div>
        </xsl:if>
    </xsl:template>

    <xsl:template name="daneprzedmiotu">
        <xsl:param name="path"/>
        <xsl:param name="waluta"/>
        <h3 class="przerywnik">PRZEDMIOT TRANSAKCJI #<xsl:value-of select="count(preceding-sibling::n1:DanePrzedmiotu) + 1"/></h3>
        <div class="row">
            <div class="tekst">Kod typu przedmiotu:</div>
            <div class="wartosc">
                <xsl:value-of select="./n1:IdSlPrzedmiotTyp"/>
            </div>
        </div>
        <xsl:if test="./n1:OpisTypInne">
            <div class="row">
                <div class="tekst">Opis typu przedmiotu:</div>
                <div class="wartosc">
                    <xsl:value-of select="./n1:OpisTypInne"/>
                </div>
            </div>
        </xsl:if>
        <div class="row">
            <div class="tekst">Zbywany udział:</div>
            <div class="wartosc">
                <xsl:value-of select="./n1:ZbywanyUdzialLicznik"/> / <xsl:value-of select="./n1:ZbywanyUdzialMianownik"/>
            </div>
        </div>
        <div class="row">
            <div class="tekst">Wartość części zbywanej:</div>
            <div class="wartosc">
                <xsl:value-of select="./n1:WartoscPrzedmiotu"/>
                <xsl:value-of select="$waluta"/>
            </div>
        </div>
        <div class="row">
            <div class="tekst">VAT:</div>
            <div class="wartosc">
                <xsl:choose>
                    <xsl:when test="./n1:CzyVAT = 'true'"> VAT uwzględniony </xsl:when>
                    <xsl:when test="./n1:CzyVAT = 'false'"> VAT nieuwzględniony </xsl:when>
                    <xsl:otherwise>null</xsl:otherwise>
                </xsl:choose>
            </div>
        </div>
        <xsl:if test="./n1:ZwolnienieVAT">
            <div class="row">
                <div class="tekst">Oświadczenie o rezygnacji ze zwolnienia z podatku VAT:</div>
                <div class="wartosc">
                    <xsl:choose>
                        <xsl:when test="./n1:ZwolnienieVAT = 'false'"> Nie, strony nie złożyły
                            oświadczenia o rezygnacji ze zwolnienia z podatku VAT </xsl:when>
                        <xsl:when test="./n1:ZwolnienieVAT = 'true'"> Tak, strony złożyły
                            oświadczenie o rezygnacji ze zwolnienia z podatku VAT </xsl:when>
                        <xsl:otherwise>Brak</xsl:otherwise>
                    </xsl:choose>
                </div>
            </div>
        </xsl:if>
        <!-- ILOŚĆ STRON TRANSAKCJI -->
        <xsl:for-each select="./n1:DanePodmiotu/@charakterPodmiotu[not(. = parent::n1:DanePodmiotu/preceding-sibling::n1:DanePodmiotu/@charakterPodmiotu)]">
            <xsl:variable name="ilosc" select="count(parent::n1:DanePodmiotu/parent::n1:DanePrzedmiotu/n1:DanePodmiotu[@charakterPodmiotu = current()])"/>
            <div class="row">
                <div class="tekst">
                    <xsl:text>Strona transakcji #</xsl:text>
                    <xsl:value-of select="position()"/>
                    <xsl:text>:</xsl:text>
                </div>
                <div class="wartosc">
                    <xsl:value-of select="."/> (ilość podmiotów: <xsl:value-of select="$ilosc"/>)
                </div>
            </div>
        </xsl:for-each>
        <xsl:if test="./n1:Adres">
            <h3 class="przerywnik">Adres przedmiotu</h3>
        </xsl:if>
        <xsl:call-template name="adresPrzedmiotu">
            <xsl:with-param name="apath" select="./n1:Adres"/>
        </xsl:call-template>
        <!-- OPIS NIERUCHOMOŚCI -->
        <xsl:if test="./n1:OpisNieruchomosci">
            <h3 class="przerywnik">Opis nieruchomości</h3>
            <xsl:call-template name="opisnieruchomosci">
                <xsl:with-param name="path" select="./n1:OpisNieruchomosci"/>
            </xsl:call-template>
        </xsl:if>
        <xsl:for-each select="./n1:DanePodmiotu/n1:ZleceniodawcaOsobaFizyczna">
            <div class="indent">
                <h3 class="przerywnik">DANE PODMIOTU - OSOBA FIZYCZNA #<xsl:value-of select="count(parent::node()/preceding-sibling::n1:DanePodmiotu/n1:ZleceniodawcaOsobaFizyczna) + 1"/></h3>
                <div class="row">
                    <div class="tekst">Charakter podmiotu:</div>
                    <div class="wartosc">
                        <xsl:value-of select="../@charakterPodmiotu"/>
                    </div>
                </div>
                <xsl:if test="not(../n1:UdzialLicznik = 0)">
                    <div class="row">
                        <div class="tekst">Udział:</div>
                        <div class="wartosc">
                            <xsl:value-of select="../n1:UdzialLicznik"/> / <xsl:value-of select="../n1:UdzialMianownik"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="./n1:OsFizycznaOsobaUpowazniona">
                    <div class="row">
                        <div class="tekst">Ilość osób upoważnionych:</div>
                        <div class="wartosc">
                            <xsl:value-of select="count(./n1:OsFizycznaOsobaUpowazniona)"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:call-template name="osfizycznaklientio">
                    <xsl:with-param name="path" select="./n1:OsobaFizyczna"/>
                </xsl:call-template>
                <xsl:for-each select="./n1:OsFizycznaOsobaUpowazniona">
                    <xsl:call-template name="osobaupowazniona">
                        <xsl:with-param name="oupath" select="."/>
                    </xsl:call-template>
                </xsl:for-each>
            </div>
        </xsl:for-each>
        <xsl:for-each select="./n1:DanePodmiotu/n1:ZleceniodawcaOsobaPrawna">
            <div class="indent">
                <h3 class="przerywnik">DANE PODMIOTU - OSOBA PRAWNA #<xsl:value-of select="count(parent::node()/preceding-sibling::n1:DanePodmiotu/n1:ZleceniodawcaOsobaPrawna) + 1"/></h3>
                <div class="row">
                    <div class="tekst">Charakter podmiotu:</div>
                    <div class="wartosc">
                        <xsl:value-of select="../@charakterPodmiotu"/>
                    </div>
                </div>
                <xsl:if test="not(../n1:UdzialLicznik = 0)">
                    <div class="row">
                        <div class="tekst">Udział:</div>
                        <div class="wartosc">
                            <xsl:value-of select="../n1:UdzialLicznik"/> / <xsl:value-of select="../n1:UdzialMianownik"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="./n1:OsPrawnaOsobaUpowazniona">
                    <div class="row">
                        <div class="tekst">Ilość osób upoważnionych:</div>
                        <div class="wartosc">
                            <xsl:value-of select="count(./n1:OsPrawnaOsobaUpowazniona)"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:call-template name="osprawnaklientio">
                    <xsl:with-param name="opath" select="./n1:OsobaPrawna"> </xsl:with-param>
                </xsl:call-template>
                <xsl:for-each select="./n1:OsPrawnaOsobaUpowazniona">
                    <xsl:call-template name="osobaupowazniona">
                        <xsl:with-param name="oupath" select="."/>
                    </xsl:call-template>
                </xsl:for-each>
            </div>
        </xsl:for-each>
    </xsl:template>

    <xsl:template name="opisnieruchomosci">
        <xsl:param name="path"/>
        <xsl:if test="$path/n1:NrKsiegiWieczystej">
            <div class="row">
                <div class="tekst">Numer Księgi Wieczystej:</div>
                <div class="wartosc">
                    <xsl:value-of select="$path/n1:NrKsiegiWieczystej"/>
                </div>
            </div>
        </xsl:if>
        <xsl:if test="$path/n1:PowLokalu">
            <div class="row">
                <div class="tekst">Powierzchnia lokalu:</div>
                <div class="wartosc">
                    <xsl:value-of select="$path/n1:PowLokalu"/>
                    <xsl:text> m²</xsl:text>
                </div>
            </div>
        </xsl:if>
        <xsl:if test="$path/n1:PowNieruchZabudowanejDomem">
            <div class="row">
                <div class="tekst">Powierzchnia nieruchomości zabudowanej domem:</div>
                <div class="wartosc">
                    <xsl:value-of select="$path/n1:PowNieruchZabudowanejDomem"/>
                    <xsl:text> m²</xsl:text>
                </div>
            </div>
        </xsl:if>
        <xsl:if test="$path/n1:LiczbaPokoi">
            <div class="row">
                <div class="tekst">Liczba pokoi:</div>
                <div class="wartosc">
                    <xsl:value-of select="$path/n1:LiczbaPokoi"/>
                </div>
            </div>
        </xsl:if>
        <xsl:if test="$path/n1:NrKondygnacjiLokalu">
            <div class="row">
                <div class="tekst">Numer kondygnacji, na której znajduje się lokal:</div>
                <div class="wartosc">
                    <xsl:value-of select="$path/n1:NrKondygnacjiLokalu"/>
                </div>
            </div>
        </xsl:if>
        <xsl:if test="$path/n1:LiczbaKondNadziemnychBudynku">
            <div class="row">
                <div class="tekst">Liczba kondygnacji nadziemnych budynku, w którym znajduje się
                    lokal:</div>
                <div class="wartosc">
                    <xsl:value-of select="$path/n1:LiczbaKondNadziemnychBudynku"/>
                </div>
            </div>
        </xsl:if>
        <xsl:if test="$path/n1:LiczbaKondPodziemnychBudynku">
            <div class="row">
                <div class="tekst">Liczba kondygnacji podziemnych budynku, w którym znajduje się
                    lokal:</div>
                <div class="wartosc">
                    <xsl:value-of select="$path/n1:LiczbaKondPodziemnychBudynku"/>
                </div>
            </div>
        </xsl:if>
        <xsl:if test="$path/n1:DataZakonczeniaRobot">
            <div class="row">
                <div class="tekst">Data zakończenia robót budowlanych:</div>
                <div class="wartosc">
                    <xsl:value-of select="$path/n1:DataZakonczeniaRobot"/>
                </div>
            </div>
        </xsl:if>
    </xsl:template>

    <xsl:template name="osfizycznaklientio">
        <xsl:param name="path"/>
        <div class="row">
            <div class="tekst">Imię:</div>
            <div class="wartosc">
                <xsl:value-of select="$path/n2:ImiePierwsze"/>
            </div>
        </div>
        <xsl:if test="$path/n2:ImieDrugie != ''">
            <div class="row">
                <div class="tekst">Drugie imię:</div>
                <div class="wartosc">
                    <xsl:value-of select="$path/n2:ImieDrugie"/>
                </div>
            </div>
        </xsl:if>
        <div class="row">
            <div class="tekst">Nazwisko:</div>
            <div class="wartosc">
                <xsl:value-of select="$path/n2:Nazwisko"/>
            </div>
        </div>
        <div class="row">
            <div class="tekst">Obywatelstwo:</div>
            <div class="wartosc">
                <xsl:value-of select="$path/n2:Obywatelstwo"/>
            </div>
        </div>
        <xsl:if test="$path/n2:PESEL">
            <div class="row">
                <div class="tekst">PESEL:</div>
                <div class="wartosc">
                    <xsl:value-of select="$path/n2:PESEL"/>
                </div>
            </div>
        </xsl:if>
        <xsl:if test="$path/n2:DataUrodzenia">
            <div class="row">
                <div class="tekst">Data urodzenia:</div>
                <div class="wartosc">
                    <xsl:value-of select="$path/n2:DataUrodzenia"/>
                </div>
            </div>
        </xsl:if>
        <xsl:choose>
            <xsl:when test="$path/n2:KrajUrodzenia">
                <div class="row">
                    <div class="tekst">Państwo urodzenia:</div>
                    <div class="wartosc">
                        <xsl:value-of select="$path/n2:KrajUrodzenia"/>
                    </div>
                </div>
            </xsl:when>
            <xsl:when test="$path/n2:KrajUrodzeniaOsoby">
                <div class="row">
                    <div class="tekst">Państwo urodzenia:</div>
                    <div class="wartosc">
                        <xsl:value-of select="$path/n2:KrajUrodzeniaOsoby"/>
                    </div>
                </div>
            </xsl:when>
        </xsl:choose>
        <xsl:if test="$path/n2:DokumentTozsamosci/n2:KrajDokumentu">
            <div class="row">
                <div class="tekst">Kod kraju wydania dokumentu:</div>
                <div class="wartosc">
                    <xsl:value-of select="$path/n2:DokumentTozsamosci/n2:KrajDokumentu"/>
                </div>
            </div>
        </xsl:if>
        <xsl:if test="$path/n2:DokumentTozsamosci/n2:RodzajDokumentu">
            <div class="row">
                <div class="tekst">Rodzaj dokumentu:</div>
                <div class="wartosc">
                    <xsl:value-of select="$path/n2:DokumentTozsamosci/n2:RodzajDokumentu"/>
                </div>
            </div>
        </xsl:if>
        <xsl:if test="$path/n2:DokumentTozsamosci/n2:SeriaINumerDokumentu">
            <div class="row">
                <div class="tekst">Seria i numer dokumentu:</div>
                <div class="wartosc">
                    <xsl:value-of select="$path/n2:DokumentTozsamosci/n2:SeriaINumerDokumentu"/>
                </div>
            </div>
        </xsl:if>
        <xsl:if test="$path/n2:AdresZamieszkania">
            <h3 class="przerywnik">ADRES OSOBY FIZYCZNEJ</h3>
            <xsl:call-template name="adres">
                <xsl:with-param name="apath" select="$path/n2:AdresZamieszkania"/>
            </xsl:call-template>
        </xsl:if>
        <xsl:if test="$path/n2:DzialalnoscGosp">
            <h3 class="przerywnik">DZIAŁALNOŚĆ GOSPODARCZA OSOBY FIZYCZNEJ</h3>
            <div class="row">
                <div class="tekst">Nazwa firmy:</div>
                <div class="wartosc">
                    <xsl:value-of select="$path/n2:DzialalnoscGosp/n2:NazwaFirmy"/>
                </div>
            </div>
            <xsl:if test="$path/n2:DzialalnoscGosp/n2:NIP">
                <div class="row">
                    <div class="tekst">NIP firmy:</div>
                    <div class="wartosc">
                        <xsl:value-of select="$path/n2:DzialalnoscGosp/n2:NIP"/>
                    </div>
                </div>
            </xsl:if>
            <xsl:if test="$path/n2:DzialalnoscGosp/n2:Adres">
                <h3 class="przerywnik">Adres działalności</h3>
                <xsl:call-template name="adres">
                    <xsl:with-param name="apath" select="$path/n2:DzialalnoscGosp/n2:Adres"/>
                </xsl:call-template>
            </xsl:if>
        </xsl:if>
    </xsl:template>

    <xsl:template name="adres">
        <xsl:param name="apath"/>
        <div class="row">
            <div class="tekst">Państwo:</div>
            <div class="wartosc">
                <xsl:value-of select="$apath/n2:Kraj"/>
            </div>
        </div>
        <xsl:if test="$apath/n2:Miejscowosc">
            <div class="row">
                <div class="tekst">Miejscowość:</div>
                <div class="wartosc">
                    <xsl:value-of select="$apath/n2:Miejscowosc"/>
                </div>
            </div>
        </xsl:if>
        <xsl:if test="$apath/n2:KodPocztowy/n2:KodPL">
            <div class="row">
                <div class="tekst">Kod pocztowy:</div>
                <div class="wartosc">
                    <xsl:value-of select="$apath/n2:KodPocztowy/n2:KodPL"/>
                </div>
            </div>
        </xsl:if>
        <xsl:if test="$apath/n2:KodPocztowy/n2:Kod">
            <div class="row">
                <div class="tekst">Kod pocztowy:</div>
                <div class="wartosc">
                    <xsl:value-of select="$apath/n2:KodPocztowy/n2:Kod"/>
                </div>
            </div>
        </xsl:if>
        <xsl:if test="$apath/n2:Ulica">
            <div class="row">
                <div class="tekst">Ulica i/lub numer:</div>
                <div class="wartosc">
                    <xsl:value-of select="$apath/n2:Ulica"/>
                </div>
            </div>
        </xsl:if>
    </xsl:template>


    <xsl:template name="adresPrzedmiotu">
        <xsl:param name="apath"/>
        <div class="indent">
            <xsl:if test="$apath/n1:Kraj">
                <div class="row">
                    <div class="tekst">Państwo:</div>
                    <div class="wartosc">
                        <xsl:value-of select="$apath/n1:Kraj"/>
                    </div>
                </div>
            </xsl:if>
            <xsl:if test="$apath/n1:AdresNieruchomosc">
                <xsl:if test="$apath/n1:AdresNieruchomosc/n2:Kraj">
                    <div class="row">
                        <div class="tekst">Państwo:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$apath/n1:AdresNieruchomosc/n2:Kraj"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="$apath/n1:AdresNieruchomosc/n2:WOJ">
                    <div class="row">
                        <div class="tekst">Kod województwa:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$apath/n1:AdresNieruchomosc/n2:WOJ"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="$apath/n1:AdresNieruchomosc/n2:POW">
                    <div class="row">
                        <div class="tekst">Kod powiatu:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$apath/n1:AdresNieruchomosc/n2:POW"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="$apath/n1:AdresNieruchomosc/n2:GMI">
                    <div class="row">
                        <div class="tekst">Kod gminy:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$apath/n1:AdresNieruchomosc/n2:GMI"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="$apath/n1:AdresNieruchomosc/n2:RODZ">
                    <div class="row">
                        <div class="tekst">Rodzaj gminy:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$apath/n1:AdresNieruchomosc/n2:RODZ"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="$apath/n1:AdresNieruchomosc/n2:KodPocztowy/n2:KodPL">
                    <div class="row">
                        <div class="tekst">Kod pocztowy:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$apath/n1:AdresNieruchomosc/n2:KodPocztowy/n2:KodPL"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="$apath/n1:AdresNieruchomosc/n2:KodPocztowy/n2:Kod">
                    <div class="row">
                        <div class="tekst">Kod pocztowy:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$apath/n1:AdresNieruchomosc/n2:KodPocztowy/n2:Kod"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="$apath/n1:AdresNieruchomosc/n2:SIMC">
                    <div class="row">
                        <div class="tekst">Kod miejsca:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$apath/n1:AdresNieruchomosc/n2:SIMC"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="$apath/n1:AdresNieruchomosc/n2:ULIC">
                    <div class="row">
                        <div class="tekst">Kod ulicy:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$apath/n1:AdresNieruchomosc/n2:ULIC"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="$apath/n1:AdresNieruchomosc/n2:NrDomu">
                    <div class="row">
                        <div class="tekst">Numer budynku:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$apath/n1:AdresNieruchomosc/n2:NrDomu"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="$apath/n1:AdresNieruchomosc/n2:NrMieszkania">
                    <div class="row">
                        <div class="tekst">Numer mieszkania/lokalu:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$apath/n1:AdresNieruchomosc/n2:NrMieszkania"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="$apath/n1:AdresNieruchomosc/n2:NrArkuszaMapy">
                    <div class="row">
                        <div class="tekst">Numer arkusza mapy:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$apath/n1:AdresNieruchomosc/n2:NrArkuszaMapy"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="$apath/n1:AdresNieruchomosc/n2:NrObrebu">
                    <div class="row">
                        <div class="tekst">Numer obrębu:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$apath/n1:AdresNieruchomosc/n2:NrObrebu"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="$apath/n1:AdresNieruchomosc/n2:NrDzialki">
                    <div class="row">
                        <div class="tekst">Numer działki:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$apath/n1:AdresNieruchomosc/n2:NrDzialki"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="$apath/n1:AdresNieruchomosc/n2:Miejscowosc">
                    <div class="row">
                        <div class="tekst">Miejscowość:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$apath/n1:AdresNieruchomosc/n2:Miejscowosc"/>
                        </div>
                    </div>
                </xsl:if>
                <xsl:if test="$apath/n1:AdresNieruchomosc/n2:Ulica">
                    <div class="row">
                        <div class="tekst">Ulica i/lub numer:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$apath/n1:AdresNieruchomosc/n2:Ulica"/>
                        </div>
                    </div>
                </xsl:if>
            </xsl:if>
        </div>
    </xsl:template>

    <xsl:template name="osobaupowazniona">
        <xsl:param name="oupath"/>
        <div class="niedzilstrony">
            <h3 class="przerywnik">OSOBA DZIAŁAJĄCA W IMIENIU PODMIOTU #<xsl:value-of select="count(preceding-sibling::*[name() = name(.)])"/></h3>
            <div class="row">
                <div class="tekst">Imię:</div>
                <div class="wartosc">
                    <xsl:value-of select="$oupath/n2:ImiePierwsze"/>
                </div>
            </div>
            <xsl:if test="$oupath/n2:ImieDrugie != ''">
                <div class="row">
                    <div class="tekst">Drugie imię:</div>
                    <div class="wartosc">
                        <xsl:value-of select="$oupath/n2:ImieDrugie"/>
                    </div>
                </div>
            </xsl:if>
            <div class="row">
                <div class="tekst">Nazwisko:</div>
                <div class="wartosc">
                    <xsl:value-of select="$oupath/n2:Nazwisko"/>
                </div>
            </div>
            <div class="row">
                <div class="tekst">Obywatelstwo:</div>
                <div class="wartosc">
                    <xsl:value-of select="$oupath/n2:Obywatelstwo"/>
                </div>
            </div>
            <xsl:choose>
                <xsl:when test="$oupath/n2:PESEL">
                    <div class="row">
                        <div class="tekst">PESEL:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$oupath/n2:PESEL"/>
                        </div>
                    </div>
                </xsl:when>
                <xsl:otherwise>
                    <div class="row">
                        <div class="tekst">Data urodzenia:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$oupath/n2:DataUrodzenia"/>
                        </div>
                    </div>
                </xsl:otherwise>
            </xsl:choose>
            <xsl:choose>
                <xsl:when test="$oupath/n2:KrajUrodzenia">
                    <div class="row">
                        <div class="tekst">Państwo urodzenia:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$oupath/n2:KrajUrodzenia"/>
                        </div>
                    </div>
                </xsl:when>
                <xsl:when test="$oupath/n2:KrajUrodzeniaOsoby">
                    <div class="row">
                        <div class="tekst">Państwo urodzenia:</div>
                        <div class="wartosc">
                            <xsl:value-of select="$oupath/n2:KrajUrodzeniaOsoby"/>
                        </div>
                    </div>
                </xsl:when>
            </xsl:choose>
            <div class="row">
                <div class="tekst">Kod kraju wydania dokumentu:</div>
                <div class="wartosc">
                    <xsl:value-of select="$oupath/n2:DokumentTozsamosci/n2:KrajDokumentu"/>
                </div>
            </div>
            <div class="row">
                <div class="tekst">Rodzaj dokumentu:</div>
                <div class="wartosc">
                    <xsl:value-of select="$oupath/n2:DokumentTozsamosci/n2:RodzajDokumentu"/>
                </div>
            </div>
            <div class="row">
                <div class="tekst">Seria i numer dokumentu:</div>
                <div class="wartosc">
                    <xsl:value-of select="$oupath/n2:DokumentTozsamosci/n2:SeriaINumerDokumentu"/>
                </div>
            </div>
        </div>
    </xsl:template>


    <xsl:template name="osprawnaklientio">
        <xsl:param name="opath"/>
        <div class="row">
            <div class="tekst">Nazwa firmy:</div>
            <div class="wartosc">
                <xsl:value-of select="$opath/n2:NazwaPodmiotu"/>
            </div>
        </div>
        <xsl:if test="$opath/n2:FormaOrganizacyjna">
            <div class="row">
                <div class="tekst">Forma organizacyjna:</div>
                <div class="wartosc">
                    <xsl:value-of select="$opath/n2:FormaOrganizacyjna"/>
                </div>
            </div>
        </xsl:if>
        <xsl:choose>
            <xsl:when test="$opath/n2:PodmiotNIP">
                <div class="row">
                    <div class="tekst">NIP:</div>
                    <div class="wartosc">
                        <xsl:value-of select="$opath/n2:PodmiotNIP"/>
                    </div>
                </div>
            </xsl:when>
            <xsl:otherwise>
                <div class="indent">
                    <h3 class="przerywnik">DANE Z REJESTRU</h3>
                    <xsl:if test="$opath/n2:NumerWRejestrze">
                        <div class="row">
                            <div class="tekst">Numer w rejestrze:</div>
                            <div class="wartosc">
                                <xsl:value-of select="$opath/n2:NumerWRejestrze"/>
                            </div>
                        </div>
                    </xsl:if>
                    <xsl:if test="$opath/n2:DataRejestracji">
                        <div class="row">
                            <div class="tekst">Data rejestracji:</div>
                            <div class="wartosc">
                                <xsl:value-of select="$opath/n2:DataRejestracji"/>
                            </div>
                        </div>
                    </xsl:if>
                    <xsl:if test="$opath/n2:NazwaRejestru">
                        <div class="row">
                            <div class="tekst">Nazwa rejestru:</div>
                            <div class="wartosc">
                                <xsl:value-of select="$opath/n2:NazwaRejestru"/>
                            </div>
                        </div>
                    </xsl:if>
                    <xsl:if test="$opath/n2:Kraj">
                        <div class="row">
                            <div class="tekst">Państwo rejestru:</div>
                            <div class="wartosc">
                                <xsl:value-of select="$opath/n2:Kraj"/>
                            </div>
                        </div>
                    </xsl:if>
                </div>
            </xsl:otherwise>
        </xsl:choose>

        <xsl:if test="$opath/n2:AdresPodmiotu">
            <h3 class="przerywnik">Adres osoby prawnej</h3>
            <xsl:call-template name="adres">
                <xsl:with-param name="apath" select="$opath/n2:AdresPodmiotu"/>
            </xsl:call-template>
        </xsl:if>
    </xsl:template>


</xsl:stylesheet>