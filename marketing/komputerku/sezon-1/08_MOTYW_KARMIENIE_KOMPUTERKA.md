# Kanon motywu: „Trzeba nakarmić komputerka”

Status: ustalenie fabularne dla S1 i S2. Nie jest to deklaracja dostępności doładowań w produkcji.

## Sens żartu
Kancelaria żyje w pośpiechu; ludzie zapominają o własnych obiadach, ale regularnie pamiętają, żeby „nakarmić komputerka”. Znaczy to: zasilić konto kredytami na operacje płatne (wywołania AI i wybrane źródła danych). Fraza dojrzewa od prywatnego dowcipu Basi do pełnoprawnej tradycji obu kancelarii.

**Powracająca kwestia:** „A komputerka ktoś nakarmił?”. Nigdy nie jest to polecenie automatycznego pobierania pieniędzy. Nie tworzyć osobnego logotypu, maskotki ani komediowego głosu programu.

## Zasady serialowe
- Najwyżej jeden krótki beat na odcinek, czasem wyłącznie spojrzenie lub puenta wizualna. W momentach prawnej powagi i rozmów z klientami żart zanika.
- Pierwsza frazy używa Basia. Kuba bierze ją dosłownie. Marta prostuje, że chodzi o kredyty. Helena długo odmawia użycia tego określenia, ale w finale sezonu spontanicznie je wypowiada.
- Zosia z drugiej kancelarii początkowo uważa żart za głupi. Ciocia Teresa traktuje go jak praktyczne pytanie o koszty i ciągłość pracy.
- Gag zawsze przedstawia potrzebę opłacenia faktycznie płatnej operacji AI; nie sugeruje, że za opłatą odbywa się obowiązek prawny, decyzja notariusza, podpisanie aktu czy przechowywanie tajemnicy.
- Nie budować sztucznego kryzysu „brak kredytów pięć sekund przed czynnością notarialną”. Żaden klient nie czeka na doładowanie w chwili czynności.
- Nie podawać w dialogach stałych cen ani liczby kredytów; aktualne warunki muszą zgadzać się z cennikiem.
- To jest komedia charakterów, nie cennik w przebraniu.

## Sezon 1 — osiem powrotów
| EP | Kto | Sytuacja i puenta | Znaczenie |
|---|---|---|---|
| 01 „Poniedziałek, 8:57” | Basia / Kuba | Basia pyta „A komputerka ktoś nakarmił?”. Kuba odruchowo patrzy na roślinę w sekretariacie. Basia nie ma czasu tłumaczyć. | Po raz pierwszy słyszymy hasło. |
| 02 „Proszę nie przy nim” | Kuba | W zapleczu biura Kuba pyta, czy komputerek „jeszcze jest głodny”. Krótkie spojrzenie Basi, bez ingerencji w rozmowę Ireny. | Żart zaczyna żyć poza jednym dialogiem. |
| 03 „U nas się tak nie pisze” | Marta / Helena | Po uwagach do projektu Marta sugeruje „może trzeba go dokarmić?”. Helena: „Najpierw trzeba go nauczyć pisać”. | Profesjonalizm Heleny; funkcja stylu kancelarii. |
| 04 „Wczoraj tego nie było” | Basia | Kuba mówi, że komputerek „jest głodny informacji”. Basia: „Informacji to on ma aż nadto”. | Dwie znaczeniowe warstwy metafory. |
| 05 „Przyszło mailem” | Zosia / Kuba | Zosia słyszy powiedzenie. „Wy tu naprawdę karmicie komputer?” Kuba próbuje wytłumaczyć jej kredyty. Ona nie daje się uwieść technologiczną gadką. | Pierwsza iskra romantyczna. |
| 06 „Kto ma tę sprawę?” | ciocia Teresa | Teresa całkiem rzeczowo pyta: „A ile on miesięcznie zjada?”. Basia rozumie, że chodzi o kontrolę kosztów. | Przygotowanie wejścia NotarAI do małej kancelarii. |
| 07 „Pokaż mi to na komputerze” | Zosia / Kuba | Zosia przypomina Kubie, że oni sami nie mieli dziś czasu zjeść. Po pracy po raz pierwszy idą razem na spokojny posiłek. | Relacja romantyczna bez produktowego wykładu. |
| 08 „To moja decyzja” | Helena | Po opanowaniu dnia Helena odruchowo pyta: „A komputerka nakarmiliście na jutro?”. Zespół milknie i wymienia spojrzenia. | Emocjonalna puenta i przemiana Heleny. |

Wykorzystaj istniejące scenariusze EP01–EP08 jako osnowę: dopisać pojedyncze momenty przy kolejnym przeglądzie dialogów, nie regenerować gotowego pilota tylko z powodu żartu.

## Sezon 2 — wizytacja
- S2E01: Teresa pakuje dokumenty i upewnia się, czy „komputerek ma co jeść”.
- S2E03: Kuba i Zosia wreszcie jedzą razem; ktoś wspomina o karmieniu trzeciego uczestnika ich spotkań.
- S2E05–S2E07: żart **znika** podczas poważnych ustaleń w zakresie obiegu dokumentów i tajemnicy notarialnej.
- S2E08: żart wraca po rzetelnym zakończeniu wizytacji jako sygnał odzyskanego spokoju.

## Reuse bez nowych tokenów
GAG-01: reakcja Basi w recepcji (istniejący kadr K3); GAG-02: spojrzenie Kuby (K6); GAG-03: dłonie i kubek na biurku; GAG-04: reakcja Heleny (K2); GAG-05: istniejący ekran salda tylko po realnym teście. Większość efektu uzyskujemy montażem, cięciami i dogrywką głosu, nie nowymi renderami.

## Bramki produktowe
Kod tokenomia.py i docs/tokenomia.md opisują kredyty kancelarii, pule abonamentowe, pakiety, portfel i zakup przez Stripe. **Domyślnie PIECZAPP_TOKENOMIA=false**. Nie sugerować, że jest to obecnie włączone na app.notarai.pl. Pokazanie autentycznego ekranu doładowania wymaga włączenia, sprawdzenia ceny i testu płatności na koncie demonstracyjnym. Sam żart słowny nie wymaga takiego ujęcia.
