# Skuteczność kanałów pozyskania i sprzedaży produktów cyfrowych (stan na listopad 2026)

Uwagi do całości (czytać przed użyciem liczb):
- Oznaczenia przy każdym punkcie: **[R]** = praca recenzowana, **[P]** = preprint / working paper, **[D]** = dane dostawcy narzędzia lub raport branżowy (nierecenzowane, często z interesem w wyniku).
- Liczby z prac naukowych pochodzą wyłącznie ze streszczeń pobranych z OpenAlex (pełne rekordy w `rejestr_kanaly.jsonl`, 80 prac). Tam, gdzie OpenAlex nie zwrócił streszczenia, nie podaję liczb.
- Prawie żadne badanie recenzowane nie dotyczy wprost kursów, e-booków, szablonów czy newsletterów. Dowody pochodzą z handlu internetowego, usług subskrypcyjnych, gier, bankowości i mediów. Przenoszenie na produkty cyfrowe małego sprzedawcy to wnioskowanie, nie pomiar.
- Benchmarki sprzed 2023 r. (i wszystkie koszty reklamy sprzed ograniczeń śledzenia w iOS z 2021 r. oraz sprzed odpowiedzi AI w wyszukiwarkach) oznaczam jako **[możliwie nieaktualne]**.
- Ograniczenie tej sesji: limit wyszukiwań w sieci wyczerpał się po 9 zapytaniach, a pobieranie stron (on24.com, wordstream.com, klaviyo.com, mailchimp.com, getresponse.com, arxiv.org, pewresearch.org, ahrefs.com, kdp.amazon.com, lennysnewsletter.com, papers.ssrn.com) było zablokowane przez ustawienia sieci. Dane dostawców pochodzą więc z wyników wyszukiwania (streszczeń stron), a nie z pełnych raportów. Braki są wypisane w sekcjach „Gaps”.

## E-mail marketing: ROI, benchmarki, automatyzacje a wysyłki jednorazowe, personalizacja, częstotliwość, powitania, porzucony koszyk

### Takeaway
E-mail ma najlepiej udokumentowany stosunek efektu do kosztu, ale głośne „36 USD z 1 USD” to deklaracja ankietowa z 2020 r., nie pomiar; twarde dowody (eksperymenty) pokazują konkretne dźwignie: imię w temacie (+31% leadów), właściwa częstotliwość (błąd kosztuje 16-32% zysku z klienta) i opóźnienie przypomnienia o koszyku do 1-3 dni. Automatyzacje (powitanie, koszyk) dają według dostawców około 30 razy większy przychód na odbiorcę niż wysyłki masowe, lecz tego porównania nie zweryfikowano eksperymentalnie.

### Cited Findings
- **[R, 2018, eksperyment terenowy]** Dodanie imienia odbiorcy do tematu maila zwiększyło otwarcia o 20% (z 9,05% do 10,80%), leady sprzedażowe o 31% (z 0,39% do 0,51%) i zmniejszyło wypisy o 17% (z 1,2% do 1,0%); eksperymenty z trzema firmami na milionach odbiorców — [Sahni, Wheeler, Chintagunta, Marketing Science](https://doi.org/10.1287/mksc.2017.1066)
- **[R, 2017, dane sprzedawcy + model]** Liczba maili ma nieliniowy wpływ na zysk: wysyłanie 4 (10) maili zamiast optymalnych 7 kosztowało sprzedawcę 32% (16%) zysku z klienta w całym okresie relacji; klienci aktywni w otwieraniu maili nie są koniecznie aktywni w zakupach — [Zhang, Kumar, Cosguner, Journal of Marketing Research](https://doi.org/10.1509/jmr.16.0210)
- **[R, 2020, eksperymenty terenowe]** Przypomnienie o porzuconym koszyku wysłane w ciągu 30-60 minut obniża prawdopodobieństwo zakupu względem braku przypomnienia; przypomnienie po 1-3 dniach ma dodatni efekt przyrostowy (ponad 40 500 klientów e-mail/aplikacja oraz 23 900 klientów SMS) — [Li, Luo, Lu, Moriguchi, Journal of Marketing](https://doi.org/10.1177/0022242920959043)
- **[R, 2023, model + eksperyment]** E-mail napędza sprzedaż wśród obecnych klientów (online i offline), natomiast pozyskanie nowych klientów w tym badaniu dawała poczta tradycyjna; eksperyment dał 6,5% faktycznego wzrostu przychodu (model proponował 13,5% i 9,3%) — [Valenti, Srinivasan, Yildirim, Pauwels, JAMS](https://doi.org/10.1007/s11747-023-00962-2)
- **[R, 2021, 3 eksperymenty, n=1 864]** Maile dopasowane na podstawie danych podanych dobrowolnie przez odbiorcę mają wyższy odsetek odpowiedzi niż personalizowane z danych obserwowanych i niż niedopasowane, ale też najwyższy odsetek wypisów — [Hartemo, Journal of Research in Interactive Marketing](https://doi.org/10.1108/jrim-03-2021-0090)
- **[R, 2016]** Treści własne firmy w mediach społecznościowych działają synergicznie z e-mailem (i telewizją) na wydatki klientów — [Kumar i in., Journal of Marketing](https://doi.org/10.1509/jm.14.0249)
- **[D, 2025, ankieta ok. 500 marketerów; inne źródło podaje 692]** Litmus nie podaje już jednej liczby: na 1 USD wydany na e-mail 35% badanych deklaruje zwrot 10-36 USD, 30% zwrot 36-50 USD, 5% ponad 50 USD; 21% nie zna swojego ROI. „36 USD z 1 USD” to wartość Litmus z 2020 r. **[możliwie nieaktualne]** — [Litmus, The ROI of Email Marketing](https://www.litmus.com/blog/infographic-the-roi-of-email-marketing); [Litmus 2025 State of Email recap](https://www.litmus.com/blog/2025-state-of-email-crossover-recap); [MarTech Zone](https://martech.zone/email-roi/); [MediaPost](https://www.mediapost.com/publications/article/406380/high-on-hiring-marketers-do-better-when-more-peop.html)
- **[D, 2025, e-commerce]** Klaviyo: średni przychód na odbiorcę w automatyzacji „porzucony koszyk” 3,07 USD wobec 0,10 USD w kampaniach masowych (około 30 razy); rok wcześniej 3,65 USD wobec 0,11 USD — [Klaviyo 2025 Benchmark Report](https://resources.klaviyo.com/2025-benchmark-report-us/p/1)
- **[D, 2026, e-commerce]** Klaviyo: automatyzacje mają ponad 3 razy wyższą klikalność niż kampanie (5,58% wobec 1,69%) i według blogu 13 razy wyższy odsetek zamówień; jednocześnie FAQ tego samego dostawcy podaje odsetek zamówień ok. 1,03% (kampanie) i ok. 1,7% (automatyzacje) — liczby są wzajemnie niespójne — [Klaviyo benchmarks](https://klaviyo.com/products/email-marketing/benchmarks); [Klaviyo blog](https://www.klaviyo.com/blog/email-marketing-data)
- **[D, raport 2024, dane 2023]** GetResponse: średnio otwarcia 39,64%, klikalność 3,25%; newslettery 40,08% otwarć; maile wyzwalane 45,38% otwarć i 5,02% klikalności; maile powitalne 83,63% otwarć i 16,6% klikalności — [GetResponse Email Marketing Benchmarks](https://www.getresponse.com/resources/reports/email-marketing-benchmarks); [GetResponse key insights](https://www.getresponse.com/blog/email-marketing-benchmarks-report-key-insights)

### Inferences
- Pierwsza inwestycja małego sprzedawcy to lista mailowa z sekwencją powitalną i przypomnieniem o koszyku: koszt jest stały i niski, a każda z dźwigni (imię, częstotliwość, opóźnienie przypomnienia) ma dowód eksperymentalny.
- Wskaźniki otwarć z raportów dostawców (ok. 40%) są zawyżone przez automatyczne pobieranie treści przez Apple Mail; do decyzji lepiej używać kliknięć i zamówień. (To wniosek z rozbieżności między 9-11% otwarć w eksperymencie Sahni i in. z 2018 r. a ok. 40% w danych dostawców po 2021 r.; samej przyczyny nie potwierdziłem źródłem w tej sesji.)
- Porównanie „automatyzacje 30 razy lepsze” jest obciążone selekcją: mail o koszyku trafia do osób, które już chciały kupić. Badanie Li i in. pokazuje, że część tej sprzedaży i tak by nastąpiła, a zbyt wczesne przypomnienie ją wręcz obniża.
- E-mail jest kanałem domykania i dosprzedaży, nie pozyskiwania zimnych odbiorców (Valenti i in.); listę trzeba zasilać z innego kanału.
- Wynik Li i in. (opóźnić przypomnienie) stoi w sprzeczności z typową poradą dostawców, by wysłać pierwszy mail w ciągu godziny; warto to przetestować u siebie.

### Gaps
- Brak recenzowanego eksperymentu porównującego sekwencję automatyczną z wysyłką jednorazową przy tej samej grupie odbiorców.
- Nie znalazłem wiarygodnej heurystyki „przychód na subskrybenta” dla twórców (raporty Kit, Kajabi, Teachable, Podia nie zostały pobrane — limit wyszukiwań i zablokowane hosty).
- Benchmarki Mailchimp wg branż (w tym edukacja) niepobrane (host zablokowany).
- Praca Sahni, Zou, Chintagunta o 70 eksperymentach z ofertami rabatowymi ([Management Science](https://doi.org/10.1287/mnsc.2016.2450)) i praca o mailach wyzwalanych ([Goić i in.](https://doi.org/10.1016/j.intmar.2021.02.002)) nie mają streszczeń w OpenAlex — liczb nie podaję.

## Płatna reklama (Meta, Google, TikTok, YouTube): inkrementalność, elastyczność, CPA/ROAS, retargeting, kreacja a targetowanie

### Takeaway
Reklama działa słabiej, niż pokazują panele platform: średnia krótkookresowa elastyczność to 0,12, eksperymenty regularnie dają efekty wielokrotnie mniejsze od szacunków obserwacyjnych, a na małym budżecie precyzyjny pomiar ROI jest praktycznie niemożliwy. Jedyny duży eksperymentalny punkt odniesienia dla małych reklamodawców to mediana 38,16 USD za przyrostowego klienta na Meta (z danymi śledzenia) i około 27 USD za lead według danych agencyjnych.

### Cited Findings
- **[R, 2011, metaanaliza]** 751 elastyczności krótko- i 402 długookresowe z 56 badań (1960-2008): średnia krótkookresowa elastyczność reklamy 0,12 (wcześniejsza metaanaliza: 0,22), długookresowa 0,24; elastyczność spada w czasie i jest wyższa na wczesnym etapie życia produktu **[możliwie nieaktualne, głównie media tradycyjne]** — [Sethuraman, Tellis, Briesch, JMR](https://doi.org/10.1509/jmkr.48.3.457)
- **[R, 2021]** 288 marek, telewizja: elastyczności wyraźnie mniejsze niż w literaturze, wiele nieistotnych lub ujemnych; krańcowe ROI ujemne dla ponad 80% marek, a ROI całego planu reklamowego dodatnie tylko dla jednej trzeciej — [Shapiro, Hitsch, Tuchman, Econometrica](https://doi.org/10.3982/ecta17674)
- **[R, 2015, 25 eksperymentów]** 2,8 mln USD wydatków na reklamę cyfrową: mediana przedziału ufności dla ROI ma ponad 100 punktów procentowych szerokości; współczynnik zmienności sprzedaży rzędu 10 jest typowy, więc miarodajny eksperyment może wymagać ponad 10 mln osobotygodni; błąd selekcji „paraliżuje” metody obserwacyjne — [Lewis, Rao, QJE](https://doi.org/10.1093/qje/qjv023)
- **[R, 2019]** Metody obserwacyjne często nie odtwarzają efektów z losowych eksperymentów reklamowych na Facebooku — [Gordon, Zettelmeyer, Bhargava, Chapsky, Marketing Science](https://doi.org/10.1287/mksc.2018.1135); powtórzone na większej skali z dwiema nowoczesnymi metodami — [Gordon, Moakler, Zettelmeyer, Marketing Science 2022](https://doi.org/10.1287/mksc.2022.1413)
- **[P/R, 2024, eksperyment na ponad 70 000 reklamodawców Facebooka i Instagrama]** Mediana kosztu przyrostowego klienta 38,16 USD; bez danych śledzenia poza platformą wzrosłaby do 49,93 USD (+31%); utrata tych danych nieproporcjonalnie szkodzi małym reklamodawcom — [Wernerfelt, Tuchman, Shapiro, Moakler, NBER w32765](https://doi.org/10.3386/w32765); wersja recenzowana: [Marketing Science](https://doi.org/10.1287/mksc.2023.0274)
- **[R, 2015, eBay]** Zwrot z reklamy w wyszukiwarce to ułamek szacunków nieeksperymentalnych; reklamy na frazy z własną marką nie dają mierzalnej krótkookresowej korzyści; frazy niemarkowe działają na nowych i rzadkich kupujących, lecz większość wydatków trafia do stałych klientów, więc średni zwrot jest ujemny — [Blake, Nosko, Tadelis, Econometrica](https://doi.org/10.3982/ecta12423)
- **[R, 2018, Bing, tysiące marek]** Bez konkurentów na frazie markowej reklama własna daje 1-4% dodatkowych kliknięć (mniej dla większych marek) przy wysokim koszcie przyrostowego kliknięcia; gdy marka nie reklamuje się, a konkurenci tak, tracą oni 18-42% kliknięć — wtedy reklama obronna ma silnie dodatni zwrot — [Simonov, Nosko, Rao, Marketing Science](https://doi.org/10.1287/mksc.2017.1065)
- **[R, 2010, detalista + eksperyment]** Wynik organiczny i płatny wzmacniają się; wpływ kliknięć organicznych na płatne jest 3,5 raza silniejszy niż odwrotnie; współzależność podnosi oczekiwany zysk o 4,2-6,15% **[możliwie nieaktualne]** — [Yang, Ghose, Marketing Science](https://doi.org/10.1287/mksc.1090.0552)
- **[R, 2010, mała firma B2B, eksperyment]** Przesunięcie budżetu do kontaktów inicjowanych przez klienta w internecie dało wzrost zysku netto 14 razy większy niż dotychczasowy podział **[możliwie nieaktualne]** — [Wiesel, Pauwels, Arts, Marketing Science](https://doi.org/10.1287/mksc.1100.0612)
- **[R, 2013, eksperyment]** Dynamiczny retargeting (pokazanie oglądanego produktu) jest średnio mniej skuteczny niż ogólna reklama marki; przestaje przegrywać dopiero, gdy klient ma sprecyzowane preferencje (np. odwiedził serwis z recenzjami) — [Lambrecht, Tucker, JMR](https://doi.org/10.1177/002224371305000508)
- **[R, 2019, eksperyment]** Retargeting zwiększył liczbę powracających na stronę o 14,6% w ciągu czterech tygodni; 33% efektu pierwszego tygodnia przypada na pierwszy dzień; reklama w drugim tygodniu działa lepiej, jeśli była też w pierwszym — [Sahni, Narayanan, Kalyanam, JMR](https://doi.org/10.1177/0022243718813987)
- **[R, 2014]** Model z efektami przenoszenia między kanałami wskazuje przypadki, w których retargeting obniża prawdopodobieństwo konwersji — [Li, Kannan, JMR](https://doi.org/10.1509/jmr.13.0050)
- **[R, 2017]** Metoda „ghost ads” obniża koszt i poprawia precyzję eksperymentów reklamowych (podstawa testów lift na platformach) — [Johnson, Lewis, Nubbemeyer, JMR](https://doi.org/10.1509/jmr.15.0297)
- **[R, 2020, przegląd]** Cztery źródła nieefektywności reklamy cyfrowej: pomiar efektu, tarcia między uczestnikami łańcucha, blokowanie reklam, oszustwa reklamowe — [Gordon i in., Journal of Marketing](https://doi.org/10.1177/0022242920913236)
- **[D, 2025, dane agencyjne USA]** WordStream: średni koszt leada na Facebooku 27,66 USD (+21% r/r); późniejsza strona podaje 27,39 USD i współczynnik konwersji kampanii leadowych 8,54%; rozrzut branżowy od 18,17 USD (sztuka i rozrywka) do 76,71 USD (stomatologia). Serwis ppc.land zauważa, że 27,39 USD nie zgadza się arytmetycznie z podanym kosztem kliknięcia i konwersją — [WordStream Facebook Ads Benchmarks 2025](https://www.wordstream.com/blog/facebook-ads-benchmarks-2025); [WordStream 2026](https://www.wordstream.com/blog/facebook-ads-benchmarks-2026); [ppc.land](https://ppc.land/facebook-lead-costs-hold-at-27-39-as-traffic-clicks-drop-to-0-60/)
- **[D, 2026]** WordStream: edukacja i szkolenia to jedna z dwóch branż ze wzrostem kosztu kliknięcia w kampaniach leadowych na Facebooku (+4,24% r/r); w Google Ads edukacja miała jeden z największych wzrostów kosztu leada (+25,87% r/r) — [WordStream Facebook Ads Benchmarks 2026](https://www.wordstream.com/blog/facebook-ads-benchmarks-2026)

### Inferences
- Przy koszcie leada rzędu 27 USD i koszcie przyrostowego klienta rzędu 38-50 USD płatna reklama nie spina się dla produktu za kilkadziesiąt złotych bez dosprzedaży; ma sens dopiero przy wyższej cenie lub udokumentowanej wartości klienta w czasie. (Wyliczenie własne z dwóch powyższych źródeł; rynek USA.)
- Dla nieznanego sprzedawcy reklama na własną nazwę jest zbędna, dopóki konkurenci nie licytują tej frazy (Blake i in. + Simonov i in.).
- Retargeting: włączać od razu po wizycie na stronie (Sahni i in.), ale z ogólnym komunikatem, a nie dokładnie oglądaną ofertą (Lambrecht i Tucker); wyjątek to przypomnienia o koszyku, gdzie natychmiastowość szkodzi (Li i in. 2020). Te trzy wyniki dotyczą różnych sytuacji i nie są sprzeczne.
- Mały budżet testowy nie da statystycznie pewnego ROI (Lewis i Rao). Rozsądny cel testu to koszt leada i jakość leadów, nie ROAS.
- Reklama opłaca się bardziej przy premierze niż stale (wyższa elastyczność na wczesnym etapie życia produktu — Sethuraman i in.).

### Gaps
- Brak pobranych benchmarków CPA/ROAS z Varos i Triple Whale oraz benchmarków Google Ads, TikTok Ads i YouTube Ads (limit wyszukiwań; wordstream.com zablokowany dla pobierania pełnych stron).
- Brak benchmarków kosztu pozyskania specyficznych dla info-produktów (kursy, e-booki); dostępne dane dotyczą leadów ogółem i e-commerce.
- Nie znalazłem recenzowanego rozkładu „kreacja a targetowanie” w efekcie reklamy; znane raporty branżowe na ten temat nie zostały zweryfikowane w tej sesji, więc ich nie cytuję.
- Prace bez streszczeń w OpenAlex (liczb nie podaję): [Johnson, Lewis, Nubbemeyer — 432 eksperymenty display](https://doi.org/10.2139/ssrn.2701578), [Coviello, Gneezy, Goette — eksperyment z reklamą w wyszukiwarce](https://doi.org/10.2139/ssrn.3061698), [Lewis, Reiley — Yahoo](https://doi.org/10.1007/s11129-014-9146-6), [Dai, Kim, Luca — które firmy zyskują na reklamie](https://doi.org/10.1287/mksc.2023.1436).
- Wszystkie eksperymenty dotyczą dużych reklamodawców lub ogółu reklamodawców; brak eksperymentu dla sprzedawcy produktów cyfrowych z budżetem rzędu kilku tysięcy złotych.

## Treści i SEO, długie wideo na YouTube, podcasty, krótkie wideo, sprzedaż na żywo

### Takeaway
Ruch organiczny z wyszukiwarki jest historycznie największym i najtańszym źródłem wejść, a własne treści podnoszą wydatki obecnych klientów, ale dowody na bezpośrednią sprzedaż z krótkiego wideo i podcastów są słabe (zaangażowanie i deklaracje, nie zakupy). Dla transmisji na żywo istnieje dowód quasi-eksperymentalny wzrostu sprzedaży, tyle że z Chin i dla towarów fizycznych.

### Cited Findings
- **[R, 2015, dane z 2012 r.]** Większość ruchu z wyszukiwarek do sklepów pochodzi z wyników organicznych, nie sponsorowanych; jakość strony i rozpoznawalność marki zwiększają kliknięcia organiczne bezpośrednio i pośrednio (lepsza pozycja); 12 000 fraz, 2 mln użytkowników, 759 sprzedawców **[możliwie nieaktualne — sprzed odpowiedzi AI]** — [Baye, De los Santos, Wildenbeest, JEMS](https://doi.org/10.1111/jems.12141)
- **[R, 2013, teoria]** Dodatni poziom SEO może poprawiać jakość rankingu wyszukiwarki, jeśli jakość strony koreluje z jej wartością dla odwiedzających — [Berman, Katona, Marketing Science](https://doi.org/10.1287/mksc.2013.0783)
- **[R, 2016]** Treści własne firmy w mediach społecznościowych mają dodatni, istotny wpływ na wydatki, zakupy krzyżowe i rentowność klientów po uwzględnieniu telewizji i e-maila; efekt większy u klientów obeznanych z technologią — [Kumar i in., Journal of Marketing](https://doi.org/10.1509/jm.14.0249)
- **[R, 2017, eksperyment]** Polubienia strony na Facebooku wpływają na zachowanie klientów tylko wtedy, gdy firma płaci za promowanie postów; przy samym zasięgu organicznym efektu nie stwierdzono — [Mochon, Johnson, Schwartz, Ariely, JMR](https://doi.org/10.1509/jmr.15.0409)
- **[R, 2020, konferencja ICIS, Taobao, różnica w różnicach z dopasowaniem]** Wprowadzenie transmisji na żywo istotnie zwiększa sprzedaż i liczbę opinii sprzedawcy, z dodatnim efektem także dla produktów niepokazanych na żywo — [Hu, Ming, ICIS 2020](https://openalex.org/W3108523601)
- **[R, 2021/2025]** Istnieje badanie łączące krótkie wideo twórców na TikToku ze sprzedażą produktu (słowa kluczowe: przewidywanie zaangażowania, lokowanie produktu); OpenAlex nie zwrócił streszczenia, więc nie podaję wielkości efektu — [Yang, Zhang, Zhang, Marketing Science](https://doi.org/10.1287/mksc.2021.0107)
- **[R, 2023, ankieta n=1 714]** Badanie słuchaczy podcastów (postawy wobec reklam, preferencja reklam czytanych przez prowadzącego); autorka zaznacza, że badań naukowych reklamy w podcastach jest niewiele — [Moe, Journal of Economics and Behavioral Studies](https://doi.org/10.22610/jebs.v14i4(j).3278)
- **[R, 2018/2016]** Badania bramek płatności w mediach (New York Times) mierzą wpływ zamknięcia treści na zaangażowanie czytelników i popyt w innych kanałach — [Pattabhiramaiah, Sriram, Manchanda, Journal of Marketing](https://doi.org/10.1177/0022242918815163); [Aral, Dhillon, Management Science](https://doi.org/10.1287/mnsc.2020.3650)

### Inferences
- Treści organiczne w mediach społecznościowych same nie sprzedają (Mochon i in.); ich rola to zasilanie listy mailowej i wzmacnianie e-maila (Kumar i in.).
- SEO i długie treści to inwestycja o opóźnionym zwrocie; ze względu na odpowiedzi AI w wyszukiwarkach dawne udziały ruchu organicznego należy traktować jako górne oszacowanie (nie udało się pobrać aktualnych pomiarów — patrz Gaps).
- Krótkie wideo ma dobrze udokumentowany zasięg i zaangażowanie, ale nie konwersję do zakupu; rozsądnie traktować je jako górę lejka z wezwaniem do zapisu na listę.
- Wynik z Taobao (efekt rozlewa się na produkty niepokazane) sugeruje, że format na żywo buduje relację ze sprzedawcą; to pośredni argument za webinarem, nie dowód dla kursów online.

### Gaps
- Brak pobranych aktualnych pomiarów wpływu odpowiedzi AI na klikalność wyników organicznych (pewresearch.org i ahrefs.com zablokowane; limit wyszukiwań).
- Brak recenzowanych danych o konwersji z YouTube (długie formy) i z podcastów do zakupu produktów cyfrowych.
- Nie znalazłem recenzowanego badania skuteczności „content marketingu” na sprzedaż o wysokiej jakości (wyniki wyszukiwania w OpenAlex to głównie ankiety o intencji zakupu).
- Dowody na sprzedaż na żywo pochodzą z Chin i dóbr fizycznych; brak danych dla Europy i produktów cyfrowych.

## Influencer marketing i sprzedaż przez twórców

### Takeaway
Najmocniejszy wynik praktyczny: mali twórcy (nano) dają zwrot z inwestycji o rząd wielkości wyższy niż duzi, bo mają bliższą relację z odbiorcami; metaanalizy potwierdzają, że polecenie twórcy działa lepiej niż post marki czy celebryta, a o zakupie decyduje sposób komunikacji twórcy, nie zasięg. Oznaczenie współpracy obniża ocenę marki i wiarygodność, więc efekt trzeba dyskontować.

### Cited Findings
- **[R, 2024, dane o 1 881 533 zakupach + 3 badania terenowe]** Kierowanie do twórców o małej liczbie obserwujących przewyższa kierowanie do dużych „o rząd wielkości” w trzech miarach ROI; mechanizm: zaangażowanie spada wraz z liczbą obserwujących — [Beichert, Bayerl, Goldenberg, Lanz, Journal of Marketing](https://doi.org/10.1177/00222429231217471)
- **[R, 2011, 74 mln zdarzeń dyfuzji, 1,6 mln użytkowników Twittera]** Nie da się wiarygodnie przewidzieć, kto wywoła dużą kaskadę; w szerokim zakresie założeń najbardziej opłacalni są „zwykli influencerzy” o przeciętnym lub mniejszym wpływie — [Bakshy, Hofman, Mason, Watts, WSDM](https://doi.org/10.1145/1935826.1935845)
- **[R, 2022]** Uwzględniając koszty: oryginalność twórcy, liczba obserwujących i widoczność sponsora zwiększają skuteczność; posty ogłaszające premierę nowego produktu ją zmniejszają; aktywność twórcy, dopasowanie obserwujących do marki i pozytywność posta mają efekt w kształcie odwróconego U — [Leung, Gu, Li, Zhang, Palmatier, Journal of Marketing](https://doi.org/10.1177/00222429221102889)
- **[R, 2024, metaanaliza 1 531 efektów z 251 prac]** Dla wyników transakcyjnych (zakup, sprzedaż) najsilniej działa komunikacja twórcy; dla intencji zakupu wartość informacyjna i hedoniczna posta; dla postaw tożsamość społeczna odbiorców; efekty zależą od typu platformy i produktu — [Pan, Blut, Ghiassaleh, Lee, JAMS](https://doi.org/10.1007/s11747-024-01052-7)
- **[R, 2025, metaanaliza 571 efektów ze 135 eksperymentów]** Twórcy istotnie wpływają na zaangażowanie i intencję zakupu i są skuteczniejsi niż posty marki, wirtualni influencerzy i celebryci; mali i średni lepiej budują zaangażowanie, więksi silniej wpływają na intencję zakupu — [Barari, Eisend, Jain, JAMS](https://doi.org/10.1007/s11747-025-01107-3)
- **[R, 2019]** Wiedza ekspercka blogera działa lepiej przy budowaniu świadomości niż przy zachęcie do próby i nie działa na Facebooku; tam lepsza treść hedoniczna; zachęty kampanijne podnoszą zaangażowanie na blogach, a obniżają na Facebooku — [Hughes, Swaminathan, Brooks, Journal of Marketing](https://doi.org/10.1177/0022242919854374)
- **[R, 2020, metaanaliza 61 prac]** Oznaczenie treści sponsorowanych obniża postawę wobec marki, wiarygodność i ocenę źródła, a zwiększa rozpoznanie reklamy i opór — [Eisend, van Reijmersdal, Boerman, Tarrahi, Journal of Advertising](https://doi.org/10.1080/00913367.2020.1765909)
- **[R, 2026, metaanaliza]** W relacjach paraspołecznych postawy (a przez nie intencję zakupu) podnoszą postrzegane podobieństwo, zaangażowanie, wiarygodność i wiarygodność marki; atrakcyjność działa ujemnie; fachowość i oznaczenie sponsoringu bez istotnego efektu — [Nadroo, Vinoi, Shankar, Journal of Service Theory and Practice](https://doi.org/10.1108/jstp-05-2025-0205)
- **[D, 2026, ankieta marketerów]** Influencer Marketing Hub: 65,9% odpowiadających oczekuje zwrotu w ciągu miesiąca; najczęściej wybierany wskaźnik to świadomość marki (55,1%), nie sprzedaż. Dane Collabstr 2026 (rynek 2025): mediana stawki nano 134 USD przy medianie 1 115 wyświetleń, mikro 150 USD przy 989; koszt wyświetlenia mega 0,07 USD wobec 0,13 USD u nano — [Influencer Marketing Hub Benchmark Report](https://influencermarketinghub.com/influencer-marketing-benchmark-report/); [inBeat (Collabstr)](https://inbeat.agency/blog/influencer-marketing-benchmark-report)

### Inferences
- Pozorna sprzeczność: Barari i in. (więksi twórcy silniej wpływają na intencję) kontra Beichert i in. (mali dają wielokrotnie wyższy zwrot). Pierwsze to deklaracje z eksperymentów laboratoryjnych, drugie to faktyczna sprzedaż z uwzględnieniem kosztu; do decyzji budżetowej ważniejszy jest drugi wynik.
- Dane Collabstr (wyświetlenie taniej u dużych) nie przeczą Beichert i in.: tańszy zasięg nie oznacza tańszej sprzedaży.
- Dla sprzedawcy, który sam jest twórcą: sprzedaje więź (podobieństwo, wiarygodność, rozmowa z odbiorcami), nie zasięg ani sama fachowość.
- Model rozliczenia prowizyjnego (kod lub link partnerski) z wieloma małymi twórcami ogranicza ryzyko i jest zgodny z wynikiem Bakshy i in. o celowaniu w efekt średni.
- Briefu „ogłoś premierę” lepiej unikać (Leung i in.); skuteczniejsza jest oryginalna treść twórcy z widoczną marką.

### Gaps
- Raport Influencer Marketing Hub nie podaje (w pobranym zakresie) zwrotu na 1 USD; krążące liczby typu „5,78 USD z 1 USD” nie zostały zweryfikowane i ich nie cytuję.
- Beichert i in. dotyczą firm sprzedających towary bezpośrednio konsumentom na Instagramie; brak repliki dla produktów cyfrowych i dla YouTube/TikTok.
- Brak pobranych danych o stawkach i konwersji twórców na rynku polskim.

## Afiliacja, programy poleceń, premiery partnerskie

### Takeaway
Klienci z poleceń są warci więcej (co najmniej +16% wartości, wyższa retencja; prawie dwa razy większa wartość długookresowa niż klienci z marketingu), a nagrodę najlepiej dzielić z zaproszonym. O skuteczności afiliacji i premier partnerskich (JV) praktycznie nie ma dowodów recenzowanych.

### Cited Findings
- **[R, 2010, ok. 10 000 klientów banku przez prawie 3 lata]** Klienci z polecenia mają wyższą marżę (różnica maleje), wyższą retencję (różnica się utrzymuje) i wartość wyższą o co najmniej 16% niż porównywalni klienci niepoleceni — [Schmitt, Skiera, Van den Bulte, Journal of Marketing](https://doi.org/10.1509/jm.75.1.46)
- **[R, 2018]** Dwa mechanizmy przewagi klientów z poleceń: lepsze dopasowanie klienta do firmy oraz „wzbogacenie społeczne” przez polecającego — [Van den Bulte, Bayer, Skiera, Schmitt, JMR](https://doi.org/10.1509/jmr.14.0653)
- **[R, 2008, firma hostingowa]** Klienci pozyskani marketingiem dają więcej wartości krótkookresowej, ale klienci z poczty pantoflowej prawie dwa razy więcej wartości długookresowej — [Villanueva, Yoo, Hanssens, JMR](https://doi.org/10.1509/jmkr.45.1.48)
- **[R, 2021, 2 eksperymenty w grach mobilnych]** Nagrody prospołeczne (podział 50/50 lub całość dla zaproszonego) dominują nad nagrodą tylko dla zapraszającego, głównie przez większą skłonność zaproszonego do przyjęcia polecenia — [Jung, Bapna, Gupta, Sen, JMIS](https://doi.org/10.1080/07421222.2021.1870384)
- **[R, 2017, eksperymenty laboratoryjne i terenowe]** Przy dalszych znajomych równy podział nagrody działa najlepiej; przy bliskich znajomych równy podział nie poprawia wyników, co sugeruje słabość zachęt pieniężnych przy silnych więziach — [Hong, Pavlou, Shi, Wang, MIS Quarterly](https://doi.org/10.25300/misq/2017/41.3.06)
- **[R, 2001, teoria]** Model optymalnej nagrody za polecenie: nagroda nie zawsze się opłaca względem obniżki ceny lub wyższej jakości — [Biyalogorsky, Gerstner, Libai, Marketing Science](https://doi.org/10.1287/mksc.20.1.82.10195)
- **[R, 2015, usługa telewizji cyfrowej]** Dla porównania: klienci pozyskani darmowym okresem próbnym mają wartość życiową niższą o 59% niż zwykli, ale lepiej reagują na komunikację marketingową — [Datta, Foubert, van Heerde, JMR](https://doi.org/10.1509/jmr.12.0160)
- **[D, 2026]** Udemy płaci twórcy 97% przy sprzedaży z jego kuponu lub linku polecającego i 37% przy pozostałych — to wbudowany w platformę „program partnerski dla samego siebie” — [Udemy Support: Instructor revenue share](https://support.udemy.com/hc/en-us/articles/229605008)
- **[D, 2026, źródło wtórne]** AppSumo: według Freemius partner dostaje 95% przychodu od nowych kupujących, których sam przyprowadzi, i 70% od powracających klientów AppSumo; AppSumo podaje, że stawki są negocjowane, i dodatkowo oferuje prowizję do 100 USD za każdego nowego kupującego przyprowadzonego przez partnera — [Freemius](https://freemius.com/help/documentation/integrations/appsumo-lifetime-deals/); [AppSumo Partner Payments Policy](https://appsumo.com/partner-terms/payment-policy); [AppSumo: revenue share](https://appsumo.com/blog/breaking-down-appsumo-revenue-share)

### Inferences
- Program poleceń warto uruchomić wcześnie, z nagrodą dla zaproszonego (np. rabat) i kierować go do zadowolonych klientów; dowody pochodzą z banku, hostingu i gier, więc wielkość efektu dla kursów jest niepewna.
- Afiliacja ma korzystną strukturę ryzyka (płatność po sprzedaży), ale brak dowodu na jej przyrostowość: część prowizji trafia za sprzedaż, która i tak by nastąpiła (analogia do wyników o reklamie na frazy markowe; wniosek własny).
- Darmowe próbki i okresy próbne przyciągają klientów o znacznie niższej wartości (Datta i in.) — lead magnet trzeba dobrać tak, by przyciągał kupujących, a nie łowców darmowych materiałów.

### Gaps
- Nie znalazłem recenzowanych eksperymentów o przyrostowości afiliacji ani o premierach partnerskich (JV); jedyna trafiona praca o afiliacji jest z 2002 r. i bez streszczenia ([Papatla, Bhatnagar](https://doi.org/10.1080/00913367.2002.10673677)).
- Brak pobranych danych o typowych stawkach prowizji partnerskich dla kursów i e-booków oraz o udziale afiliacji w sprzedaży twórców.
- Dowody o poleceniach pochodzą z branż z długą relacją (bank, hosting); dla jednorazowego zakupu e-booka przewaga retencji nie ma zastosowania.

## Webinary, wydarzenia na żywo, wyzwania, darmowe warsztaty

### Takeaway
To kanał o najsłabszej bazie dowodowej: nie znalazłem żadnego recenzowanego badania skuteczności sprzedażowej webinarów, wyzwań ani darmowych warsztatów. Dostępne są tylko benchmarki dostawców dla webinarów B2B: z rejestracji na obecność przechodzi 57-60% (ON24), przy czym ten sam dostawca podaje ok. 40% jako średnią „dla webinarów ogólnie”.

### Cited Findings
- **[D, raport 2025, dane 2024, B2B]** ON24: średnia konwersja rejestracji na uczestnictwo 57%; raport 2026 podaje 60%; benchmark z 2023 r.: 56% na platformie ON24 wobec 40% średnio dla webinarów ogólnie — [ON24 Webinar Benchmarks Report](https://www.on24.com/resources/asset/webinar-benchmarks-report); [ON24: key takeaways](https://www.on24.com/blog/key-takeaways-from-the-webinar-benchmarks-report/); [MarketingProfs](https://www.marketingprofs.com/charts/2025/52917/b2b-webinar-benchmarks-conversion-attendance-personalization)
- **[R, 2020, Taobao]** Najbliższy dowód naukowy dla formatu „na żywo”: wprowadzenie transmisji istotnie zwiększa sprzedaż sprzedawcy, także produktów niepokazanych — [Hu, Ming, ICIS 2020](https://openalex.org/W3108523601)
- **[R, 2015]** Dowód pośredni na rolę relacji: uczestnictwo w społeczności firmy zwiększa wydatki, silniej u osób aktywnie piszących niż u biernych — [Manchanda, Packard, Pattabhiramaiah, Marketing Science](https://doi.org/10.1287/mksc.2014.0890)

### Inferences
- Liczby ON24 liczą łącznie obecność na żywo i odtworzenia na żądanie na platformie korporacyjnej B2B; dla darmowego webinaru sprzedającego kurs konsumencki należy przyjąć raczej dolną wartość (ok. 40%) lub mniej — to założenie, nie pomiar.
- Skoro brak dowodów zewnętrznych, webinar należy traktować jak eksperyment własny: mierzyć rejestracje, obecność, zakup w 7 dni i porównać z grupą z listy, która nie dostała zaproszenia.
- Mechanizm, który może tłumaczyć skuteczność webinarów (więź z prowadzącym, podobieństwo, interakcja), jest spójny z metaanalizami o twórcach, ale to analogia.

### Gaps
- Brak pobranych benchmarków konwersji webinar → zakup (WebinarJam, GoToWebinar, BigMarker, GetResponse — limit wyszukiwań, hosty zablokowane); krążące w branży „5-20% uczestników kupuje” nie zostało zweryfikowane i nie jest tu cytowane.
- Brak jakichkolwiek danych (naukowych i dostawców) o wyzwaniach (challenge) i płatnych warsztatach jako mechanizmie sprzedaży.
- Brak danych o różnicy konwersji między webinarem na żywo a nagranym (evergreen).

## Społeczności (Discord, Skool, grupy na Facebooku) i społeczności marki

### Takeaway
Dołączenie do społeczności sprzedawcy przyczynowo zwiększa wydatki klientów, a sprzedają głównie wypowiedzi samych członków, nie posty sprzedawcy; w modelu freemium zakup znajomego podnosi szansę zakupu o ponad 60%. Brak danych o nowych platformach (Skool, Discord) i o retencji płatnych społeczności twórców.

### Cited Findings
- **[R, 2015]** Istotny wzrost wydatków przypisywalny dołączeniu do społeczności internetowej sprzedawcy („social dollars”); efekt trwały, głównie w kanale internetowym, większy u piszących niż u biernych i u osób z większą liczbą więzi; źródło raczej społeczne niż informacyjne — [Manchanda, Packard, Pattabhiramaiah, Marketing Science](https://doi.org/10.1287/mksc.2014.0890)
- **[R, 2013, społeczność na Facebooku + dane transakcyjne]** Zaangażowanie w społeczność marki zwiększa wydatki; treści użytkowników działają silniej niż treści sprzedawcy (elastyczność popytu względem bogactwa informacyjnego treści użytkowników 3,140 w komunikacji nieskierowanej; względem wydźwięku treści użytkowników 0,180; względem wydźwięku treści sprzedawcy 0,004) — [Goh, Heng, Lin, Information Systems Research](https://doi.org/10.1287/isre.1120.0469)
- **[R, 2015, eksperyment w sieci freemium]** Wpływ rówieśniczy powoduje ponad 60-procentowy wzrost szans zakupu usługi płatnej, gdy kupił ją znajomy; silniejszy efekt względny u osób z mniejszą liczbą znajomych — [Bapna, Umyarov, Management Science](https://doi.org/10.1287/mnsc.2014.2081)
- **[R, 2016, metaanaliza]** W mediach społecznościowych opinie działają silniej, gdy odbiorca może ocenić swoje podobieństwo do autora — [Babić Rosario i in., JMR](https://doi.org/10.1509/jmr.14.0380)

### Inferences
- Społeczność jest narzędziem zwiększania wartości i retencji obecnych klientów, nie kanałem pozyskania; nadaje się jako element oferty (dostęp w cenie kursu) lub produkt abonamentowy.
- Kluczowy wskaźnik to odsetek członków, którzy piszą i nawiązują kontakty, a nie liczba zapisanych (Manchanda i in.; Goh i in.).
- Widoczność zakupów innych członków („kto ma wersję płatną”) ma dowód eksperymentalny (Bapna i Umyarov).

### Gaps
- Brak badań i wiarygodnych benchmarków dla Skool, Discord, Circle i płatnych grup twórców (konwersja, rezygnacje).
- Oba główne badania dotyczą sprzedawców detalicznych (rozrywka, odzież) i lat 2013-2015; brak replik dla produktów edukacyjnych.
- Samoselekcja: mimo zabiegów autorów część efektu może wynikać z tego, że do społeczności dołączają najbardziej zaangażowani klienci.

## Platformy sprzedażowe (Udemy, Etsy, Gumroad Discover, AppSumo, Amazon KDP) a własny sklep

### Takeaway
Platforma daje ruch, ale zabiera 30-63% ceny przy sprzedaży, którą sama wygenerowała; ten sam produkt sprzedany z własnego linku kosztuje od 3% (Udemy) do kilkunastu procent (Gumroad). Opłaca się więc model mieszany: platforma jako odkrywalność, własna lista i własne linki jako marża.

### Cited Findings
- **[D, 2026]** Udemy: 97% przychodu dla twórcy przy sprzedaży z kuponu lub linku twórcy; 37% przy pozostałej sprzedaży na platformie; udział twórców w puli subskrypcyjnej obniżany do 20% (styczeń 2024), 17,5% (styczeń 2025) i 15% (styczeń 2026) — [Udemy Support](https://support.udemy.com/hc/en-us/articles/229605008); [Udemy: updating subscription terms](https://teach.udemy.com/enabling-investment-subscription-terms-update/)
- **[D, 2026, blogi stron trzecich i konkurentów]** Gumroad: 10% + 0,50 USD od sprzedaży bezpośredniej (łącznie z opłatami za płatność ok. 13-19%); 30% od sprzedaży przez Gumroad Discover; od stycznia 2025 r. Gumroad działa jako sprzedawca rozliczający podatki (merchant of record) — [Sellfy: Gumroad pricing](https://sellfy.com/blog/gumroad-pricing/); [Checkout Page: Gumroad fees](https://checkoutpage.com/blog/gumroad-fees)
- **[D, 2026, blogi stron trzecich]** Etsy (USA): 0,20 USD za wystawienie (odnawiane co 4 miesiące lub po sprzedaży), 6,5% opłaty transakcyjnej, 3% + 0,25 USD za płatność, 12% lub 15% za sprzedaż z reklam zewnętrznych (limit 100 USD na zamówienie; źródła różnią się co do progu 10 000 USD i możliwości rezygnacji); przykład: sprzedaż za 30 USD z reklamą zewnętrzną 15% to ok. 7,80 USD opłat, czyli 26% — [Marmalead: Etsy fees explained](https://blog.marmalead.com/etsy-fees-explained/); [Checkout Page: Etsy fees](https://checkoutpage.com/blog/etsy-fees); [Gelato: Etsy fees](https://www.gelato.com/blog/how-much-does-etsy-take-from-a-sale)
- **[D, 2026]** AppSumo: stawki negocjowane indywidualnie; AppSumo zaprzecza, że zabiera „ponad 70%”; według Freemius 95% dla partnera od kupujących przyprowadzonych przez niego i 70% od klientów platformy; partner zobowiązuje się utrzymać dostęp dożywotni dla kupujących — [AppSumo: myths](https://appsumo.com/blog/appsumo-myths); [AppSumo Partner Terms](https://appsumo.com/partner-terms/); [Freemius](https://freemius.com/help/documentation/integrations/appsumo-lifetime-deals/)
- **[R, 2021]** Model biznesowy platform z kursami (typu Udemy) kształtuje motywacje i strategie twórców — [Cisel, Pontalier, IRRODL](https://doi.org/10.19173/irrodl.v22i3.5459)
- **[R, 2025, teoria]** Model platform z treściami: wybór między odkrywalnością a członkostwem — [Casner, Teh, RAND Journal of Economics](https://doi.org/10.1111/1756-2171.70029)

### Inferences
- Różnica 97% wobec 37% na Udemy oznacza, że sprzedaż „z ruchu platformy” kosztuje twórcę 60 punktów procentowych ceny — to faktyczna cena odkrywalności; analogicznie 30% wobec ok. 10% na Gumroad.
- Malejący udział w puli subskrypcyjnej Udemy (20% → 15% w dwa lata) pokazuje ryzyko uzależnienia: warunki platformy zmieniają się jednostronnie.
- Platforma ma sens jako kanał testu popytu i pozyskania pierwszych opinii oraz jako dodatkowy ruch; marżę i relację z klientem (adres e-mail) daje własny sklep.
- Presji cenowej (częste promocje na Udemy) nie udało się udokumentować liczbami w tej sesji.

### Gaps
- Amazon KDP: stawek tantiem nie pobrałem (kdp.amazon.com zablokowany) — nie podaję.
- Opłaty Etsy i Gumroad pochodzą z blogów stron trzecich (część to konkurenci); wymagają sprawdzenia w oficjalnych cennikach.
- Brak danych o tym, jaki odsetek sprzedaży twórców pochodzi z ruchu platformy, a jaki z własnego, oraz o średnich cenach transakcyjnych na Udemy.
- Brak recenzowanych badań empirycznych porównujących dochód twórcy na platformie i we własnym sklepie.

## Atrybucja wielokanałowa: pułapki i kanały przeceniane przez „ostatnie kliknięcie”

### Takeaway
Atrybucja ostatniego kliknięcia i raporty platform systematycznie przeceniają kanały, po które klient sięga tuż przed zakupem (własna marka w wyszukiwarce, retargeting, e-mail do obecnych klientów, przypomnienia o koszyku), a nie doceniają kanałów budujących popyt. Jedynym wiarygodnym miernikiem jest test z grupą kontrolną lub wyłączenie kanału.

### Cited Findings
- **[R, 2014]** Po uwzględnieniu efektów przenoszenia i rozlewania między kanałami (display, płatne wyszukiwanie, odesłania, e-mail) udziały kanałów w konwersjach istotnie różnią się od tych z powszechnie stosowanych miar; walidacja eksperymentem terenowym — [Li, Kannan, JMR](https://doi.org/10.1509/jmr.13.0050)
- **[R, 2015]** Ponieważ kliknięcia w wyszukiwarce korelują z zamiarem zakupu, zwroty z płatnego wyszukiwania to ułamek szacunków nieeksperymentalnych; reklamy na frazy markowe bez mierzalnego efektu krótkookresowego — [Blake, Nosko, Tadelis, Econometrica](https://doi.org/10.3982/ecta12423)
- **[R, 2019, 2022]** Metody obserwacyjne, także zaawansowane, nie odtwarzają wiarygodnie wyników eksperymentów na Meta — [Gordon i in. 2019](https://doi.org/10.1287/mksc.2018.1135); [Gordon, Moakler, Zettelmeyer 2022](https://doi.org/10.1287/mksc.2022.1413)
- **[R, 2015]** Błąd selekcji wynikający z targetowania „paraliżuje” metody obserwacyjne; przedziały ufności ROI ponad 100 p.p. — [Lewis, Rao, QJE](https://doi.org/10.1093/qje/qjv023)
- **[R, 2020]** Przypomnienie o koszyku w pierwszej godzinie ma ujemny efekt przyrostowy, choć w raportach wyglądałoby na skuteczne (kliknięcia i zakupy „po mailu”) — [Li, Luo, Lu, Moriguchi, Journal of Marketing](https://doi.org/10.1177/0022242920959043)
- **[R, 2010]** Liczne efekty międzykanałowe: działania offline wpływają na wskaźniki lejka online i odwrotnie — [Wiesel, Pauwels, Arts, Marketing Science](https://doi.org/10.1287/mksc.1100.0612)
- **[R, 2018, teoria]** Atrybucja ostatniego kontaktu zniekształca zachęty wydawców i wyceny kanałów — [Berman, Marketing Science](https://doi.org/10.1287/mksc.2018.1104)
- **[R, 2024]** Utrata danych śledzenia poza platformą podnosi koszt przyrostowego klienta na Meta o 31% (mediana) i silniej uderza w małych reklamodawców — [Wernerfelt i in., NBER](https://doi.org/10.3386/w32765)

### Inferences
- Kanały prawdopodobnie przeceniane: reklama na własną markę, retargeting, e-mail do osób już zdecydowanych, linki partnerskie i kody rabatowe używane w ostatniej chwili. Kanały prawdopodobnie niedoceniane: treści, polecenia, twórcy, społeczność. (Zestawienie własne na podstawie powyższych prac; dla afiliacji i twórców to analogia, nie pomiar.)
- Praktyczne minimum pomiarowe dla małego sprzedawcy: (1) losowe wyłączenie części listy z kampanii, (2) okresowe wyłączenie reklamy na markę i retargetingu, (3) pytanie w formularzu zamówienia „skąd o nas wiesz”, (4) osobne kody i linki dla twórców i partnerów.
- Po ograniczeniach śledzenia w iOS dane platform są dodatkowo niepełne, więc własne dane pierwszej strony (lista mailowa, ankieta przy zakupie) zyskują na znaczeniu.

### Gaps
- Brak pobranych aktualnych porównań ROAS raportowanego z ROAS przyrostowym od firm pomiarowych (limit wyszukiwań).
- Prace o atrybucji bez streszczeń w OpenAlex (liczb nie podaję): [de Haan, Wiesel, Pauwels](https://doi.org/10.1016/j.ijresmar.2015.12.001), [Anderl i in.](https://doi.org/10.1016/j.ijresmar.2016.03.001), [Kireyev, Pauwels, Gupta](https://doi.org/10.1016/j.ijresmar.2015.09.007).
- Brak badań atrybucji dla ścieżek obejmujących treści twórców, podcasty i społeczności.

## Poczta pantoflowa i wirusowość: udział poleceń w sprzedaży, realia współczynnika K

### Takeaway
Opinie i polecenia mają wyższą elastyczność sprzedaży niż reklama (0,236 dla liczby opinii wobec 0,12 dla reklamy) i dłuższy efekt, ale prawdziwa wirusowość jest rzadka: popularność prawie zawsze wynika z jednego dużego nadawcy, nie z łańcucha poleceń. Nie znalazłem wiarygodnej liczby mówiącej, jaki odsetek sprzedaży produktów cyfrowych pochodzi z poleceń.

### Cited Findings
- **[R, 2015, metaanaliza 51 badań]** Elastyczność sprzedaży względem liczby opinii w internecie 0,236, względem ich wydźwięku 0,417 — [You, Vadakkepatt, Joshi, Journal of Marketing](https://doi.org/10.1509/jm.14.0169)
- **[R, 2016, metaanaliza 1 532 efektów z 96 badań]** Opinie w internecie korelują dodatnio ze sprzedażą (średnio 0,091); liczba opinii działa silniej niż wydźwięk; opinie negatywne nie zawsze szkodzą, szkodzi duża zmienność ocen — [Babić Rosario, Sotgiu, De Valck, Bijmolt, JMR](https://doi.org/10.1509/jmr.14.0380)
- **[R, 2009, serwis społecznościowy]** Polecenia mają znacznie dłuższy efekt niż tradycyjne działania marketingowe; w streszczeniu towarzyszącym autorzy podają długookresową elastyczność rejestracji względem poleceń 0,53, około 20 razy więcej niż dla wydarzeń marketingowych i 30 razy więcej niż dla wzmianek w mediach **[możliwie nieaktualne]** — [Trusov, Bucklin, Pauwels, Journal of Marketing](https://doi.org/10.1509/jmkg.73.5.90); [streszczenie w GfK MIR](https://doi.org/10.2478/gfkmir-2014-0068)
- **[R, 2015, miliard zdarzeń dyfuzji na Twitterze]** Wirusowość strukturalna jest zwykle niska niezależnie od skali; popularność wynika głównie z wielkości największej pojedynczej emisji — [Goel, Anderson, Hofman, Watts, Management Science](https://doi.org/10.1287/mnsc.2015.2158)
- **[R, 2011, eksperyment, 9 687 użytkowników i 1,4 mln znajomych]** Bierne funkcje wirusowe (automatyczne powiadomienia) zwiększają wpływ rówieśniczy o 246%, dodanie aktywnych, spersonalizowanych zaproszeń tylko o dalsze 98%; zaproszenia osobiste są skuteczniejsze na wiadomość, ale rzadziej używane — [Aral, Walker, Management Science](https://doi.org/10.1287/mnsc.1110.1421)
- **[R, 2011, eksperymenty + kampania na ponad 200 000 klientów]** Najlepsze strategie rozsiewania są do 8 razy skuteczniejsze od innych; najlepiej zaczynać od osób z wieloma kontaktami (chętniej uczestniczą i mają zasięg, choć nie większy wpływ na pojedynczą osobę) — [Hinz, Skiera, Barrot, Becker, Journal of Marketing](https://doi.org/10.1509/jm.10.0088)
- **[R, 2009, test terenowy]** Przy produkcie o niskiej rozpoznawalności najskuteczniejsze sprzedażowo są polecenia od mniej lojalnych klientów i między dalszymi znajomymi, nie przyjaciółmi — [Godes, Mayzlin, Marketing Science](https://doi.org/10.1287/mksc.1080.0444)
- **[R, 2008]** Klienci z poczty pantoflowej wnoszą prawie dwa razy więcej wartości długookresowej niż pozyskani marketingiem — [Villanueva, Yoo, Hanssens, JMR](https://doi.org/10.1509/jmkr.45.1.48)

### Inferences
- Współczynnik K powyżej 1 nie jest realistycznym założeniem planu (Goel i in.); polecenia należy traktować jako mnożnik (np. kilkanaście-kilkadziesiąt procent dodatkowych klientów), a nie silnik wzrostu. Konkretnej wartości K dla produktów cyfrowych nie znalazłem.
- Najtańsza dźwignia o dużej elastyczności to zbieranie dużej liczby opinii i pokazywanie, kim są ich autorzy; ważniejsza liczba niż idealna średnia.
- Mechanizmy udostępniania wbudowane w produkt (certyfikat ukończenia do udostępnienia, automatyczne powiadomienie) mają dowód eksperymentalny, choć z aplikacji na Facebooku z 2011 r.
- **Synteza dla pierwszego budżetu testowego (wnioskowanie z całości materiału, nie pomiar):**

| Kanał | Siła dowodów | Co wiadomo liczbowo | Rola na start |
|---|---|---|---|
| E-mail (lista, powitanie, koszyk) | Eksperymenty + dane dostawców | +31% leadów z imienia w temacie; błąd częstotliwości = 16-32% zysku; przypomnienie po 1-3 dniach | Fundament; wdrożyć przed płatnym ruchem |
| Opinie i polecenia | Metaanalizy + eksperymenty | Elastyczność 0,236 (liczba opinii); klient z polecenia +16% wartości; nagroda dzielona działa lepiej | Wdrożyć od pierwszych klientów; koszt znikomy |
| Mali twórcy (nano), prowizyjnie | Badania terenowe + metaanalizy | Zwrot „o rząd wielkości” wyższy niż u dużych | Pierwszy test płatny; wielu małych zamiast jednego dużego |
| Platforma sprzedażowa | Tylko cenniki | Koszt ruchu platformy 30-63% ceny | Test popytu i opinii, nie główne źródło marży |
| Płatna reklama (Meta, Google) | Najmocniejsze eksperymenty, wynik studzący | Elastyczność 0,12; ok. 27 USD za lead; mediana 38 USD za przyrostowego klienta | Mały test kosztu leada dopiero po zbudowaniu lejka mailowego; nie na własną markę |
| Retargeting | Eksperymenty | +14,6% powrotów; 33% efektu w 1. dniu | Tani dodatek, gdy jest już ruch |
| Treści, SEO, wideo | Obserwacyjne, częściowo stare | Większość ruchu z wyszukiwarki była organiczna (2012) | Inwestycja długoterminowa zasilająca listę |
| Webinar / na żywo | Brak dowodów recenzowanych | 57-60% obecności (B2B, dostawca) | Tani test własny z pomiarem |
| Społeczność | Dowody obserwacyjne | Wzrost wydatków członków; treści członków silniejsze niż sprzedawcy | Retencja i dosprzedaż, nie pozyskanie |

### Gaps
- Nie znalazłem źródła podającego, jaki odsetek sprzedaży kursów, e-booków lub newsletterów pochodzi z poleceń (raporty Kit, Substack, Lenny's Newsletter, First Round, Reforge, Demand Curve niepobrane — limit wyszukiwań i zablokowane hosty).
- Brak pomiarów współczynnika K dla produktów cyfrowych twórców.
- Badania o wirusowości pochodzą z lat 2009-2015 (Facebook, Twitter); zachowanie algorytmów rekomendacji krótkiego wideo może zmieniać obraz, ale nie znalazłem recenzowanego dowodu w tej sesji.
