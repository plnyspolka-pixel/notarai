# Teczka sprawy klienta (przygotowanie zapytania do notariusza)

Stan: 08.11.2026. Kod: `teczka.py`, strona `seo/teczka_strona.py` ->
`/przygotuj-sprawe/`, testy `test_teczka.py`.

## Jak to działa dla klienta

1. Klient wchodzi na `/przygotuj-sprawe/` (z karty kancelarii na stronie
   miasta: przycisk „Przygotuj sprawę”, albo z okienka „Umów wizytę”).
2. Opisuje sprawę zwykłymi słowami w czacie i/lub wgrywa dokumenty
   (PDF, JPG, PNG, do 10 MB, do 12 plików).
3. Obok rozmowy na żywo widzi:
   - jaką czynność ustaliliśmy,
   - listę dokumentów z katalogu kancelarii (`taksa.DOKUMENTY`) z tym,
     skąd je wziąć i czy są potrzebne zawsze, czy „jeśli dotyczy”;
     może zaznaczyć „mam / nie mam”,
   - czego jeszcze brakuje,
   - gotowy tekst zapytania do kancelarii z szacunkiem kosztów.
4. Gdy nie ma braków wymaganych (czynność, miejscowość, a przy
   nieruchomości numer KW albo adres), pokazuje się formularz wysyłki:
   imię, telefon/e-mail, zgoda. Zapytanie trafia zwykłym torem zgłoszeń
   (`wizyty.przyjmij`): do wybranej kancelarii albo z kolejki „dowolna
   kancelaria w miejscowości”.

## Podział pracy model / kod

| co | kto |
|---|---|
| rozmowa, pytania, wyjaśnienia | model (Bedrock EU, profil kalkulatora, `PIECZAPP_TECZKA_MODEL`) |
| ustalenia (czynność, KW, adres, nabycie, wartość, kredyt, strony, miejsce) | model proponuje JSON, kod waliduje: id z katalogu, cyfra kontrolna KW, miejscowość z wykazu |
| lista dokumentów, warunki („przy spadku zaświadczenie z US”), braki | wyłącznie kod |
| rozpoznanie wgranego pliku | model czyta do 3 stron (obraz + warstwa tekstowa), zwraca rodzaj dokumentu, KW, adres, rodzaj nieruchomości, sposób nabycia; kod przyjmuje tylko pola, które przejdą walidację; treść pliku nie może zmienić czynności ani zasad |
| szacunek kosztów | `taksa.oblicz` |

## Dane osobowe

- Teczka bez konta: losowy token w przeglądarce, na serwerze tylko skrót
  SHA-256 jako nazwa katalogu (`kancelarie/_administracja/teczki/<skrót>/`
  w S3, szyfrowane, eu-central-1).
- Nie prosimy o PESEL ani numery dowodów (asystent ma to w zasadach,
  strona mówi to wprost).
- Klient może usunąć teczkę z plikami przyciskiem. Niewysłane teczki
  aplikacja kasuje po 30 dniach; reguła S3 `teczki-klientow-30-dni`
  (`infra/notarai-s3.yaml`, wymaga ponownego wdrożenia stosu
  `notarai-s3`) kasuje wszystko po 31 dniach.
- Treści rozmów i plików nie trafiają do logów (test to sprawdza).

## Następne kroki (nie zbudowane)

1. (zrobione) Kancelaria pobiera pliki klienta i sprawdza KW w EKW w oknie „Zapytania klientów”.
2. Sprawdzenie KW w EKW (`ekw.py`) po podaniu numeru: właściciel, obciążenia,
   hipoteki, rozbieżności z opisem klienta.
3. Szablony pytań dla trudniejszych spraw (spadek z kilkoma
   spadkobiercami, spółka, służebność).
