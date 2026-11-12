# RzPESEL – wniosek Fundacji dla systemu NotarAI

Data: 2026-11-12. Status: do podpisu/weryfikacji, **nic nie zostało wysłane**.

## Odrębny wnioskodawca
**FUNDACJA KRZEWIENIA EDUKACJI FINANSOWEJ IM. PIECZAKA**
- KRS: 0001140846
- NIP: 9462747637
- REGON: 540280180
- adres: ul. Wilhelma Orlika Ruckemana 4/18, 20-244 Lublin
- nazwa systemu: **NotarAI**

**To nie jest formularz Finance You.** Obie organizacje składają samodzielne dokumenty, z własnymi podpisami i kluczami API.

## Dokumenty do przygotowania
1. Oryginalny PDF „Wniosek dostępowy do RzPESEL”: środowisko **testowe**, **wydanie nowego klucza API**, nazwa NotarAI i dane Fundacji. Wymagane do uzupełnienia: osoba odpowiedzialna za integrację (imię i nazwisko), jej służbowy telefon do hasła SMS, służbowy e-mail do klucza, e-mail do powiadomień, faktyczny publiczny IPv4 egress i model pośredniczenia.
2. Oryginalny PDF **wniosku formalnego do Ministra Cyfryzacji**, przygotowany **na Fundację**, oraz osobna specyfikacja NotarAI.
3. Wniosek produkcyjny do COI wyłącznie po otrzymaniu zgody MC.

Oficjalne materiały: https://www.gov.pl/web/cyfryzacja/udostepnianie-danych-z-rejestru-zastrzezen-numerow-pesel

## Granica uprawnień
Fundacja nie jest notariuszem. Art. 23m ust. 1 pkt 4 ustawy o ewidencji ludności wymienia notariuszy, a nie dowolnego operatora systemu dla notariuszy. Wniosek Fundacji powinien wskazywać **własną rzeczywistą podstawę / interes faktyczny** (do oceny pod kątem art. 23m ust. 1 pkt 2 i art. 46 ust. 2 pkt 1). Gdy NotarAI działa jako **system pośredniczący** dla kancelarii, trzeba zweryfikować wymogi indywidualnych kluczy poszczególnych notariuszy oraz umowy z kancelariami; **klucz Fundacji nie jest automatycznie zbiorczym uprawnieniem wszystkich kancelarii**.

## Wymogi techniczne
- Wydzielone sekrety Fundacji i wszystkich uprawnionych kancelarii, bez przenikania tenantów.
- Serwerowy adapter do faktycznego kontraktu OpenAPI udostępnianego przez MC; bez zgadywania endpointów.
- Stały publiczny IPv4 egress zgodny ze wskazanym we wniosku.
- Ograniczenie dostępu do uprawnionego użytkownika i konkretnej czynności, polityka celu, identyfikator sprawy, operatora, chwili zapytania i wyniku; nie logować niepotrzebnie pełnego PESEL.
- Błędy/timeout/brak klucza oznaczają **nieustalony**, nigdy niezastrzeżony.
- Testy stubem MC, regresja, kontrola uprawnień i separacji między kancelariami.

## Repozytoria i integracje
- NotarAI: https://github.com/plnyspolka-pixel/notarai
- Finance You (drugi **niezależny** podmiot): https://github.com/plnyspolka-pixel/finyou/pull/370
- Wspólny adapter techniczny jest możliwy, ale nie wspólne uprawnienie, produkcyjny klucz API lub wniosek.
