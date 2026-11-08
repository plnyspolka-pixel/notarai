# Testy i integracja frontend/backend NotarAI

## Zasady

- PR #1, #2, #3 i #4 zostały przygotowane na zależnych gałęziach.
- Ta gałąź integracyjna zawiera **ich łączny stan**. Nie należy osobno scalać
  wszystkich czterech PR, jeżeli ten PR został już połączony z `master`.
- Każdy PR jest weryfikowany przez GitHub Actions: kompilacja Python,
  składnia JavaScript (w tym inline w HTML), testy pytest.
- Testy CI używają atrap i nie mają dostępów do realnych kancelarii, AWS
  Secrets Manager, Bedrock ani produkcyjnych danych spraw.

## Ręczny odbiór (obowiązkowy przed publikacją)

1. Konto nowej kancelarii: rejestracja, reset hasła, logowanie, dokumenty.
2. Brak zaakceptowanego powierzenia: brak możliwości pobrania listy spraw.
3. Zwykła kancelaria: wgranie własnego wzoru i skanów, odczyt AI, korekta pól,
   generowanie projektu, pobranie właściwego DOCX.
4. Druga kancelaria: nie widzi ani nie pobiera spraw pierwszej.
5. Wylogowanie przy trwającym pobraniu listy lub sprawy: brak ponownego
   pokazania zawartości poprzedniej sesji.
6. Dwa szybkie kliknięcia różnych spraw: wynik ostatnio wybranej sprawy.
7. Tryb plików lokalnych: uprawnienia folderu, odczyt, zapis projektu DOCX.
8. Panel klienta kancelarii i moduły: kalendarz, kontakty, rejestry, dokumenty
   prawne, abonament, zespół, uprawnienia.
9. Telefon 390 px, tablet, desktop, nawigacja klawiaturą i ciemny motyw.
10. Wdrożenie: staging/nieprodukcyjny adres, logi bez danych osobowych,
    rollback do poprzedniego obrazu ECR; dopiero potem produkcja.

## Status

Automatyczne testy uruchamiają się po wysłaniu PR do GitHuba.
Ich przejście **nie zastępuje** testów E2E z AWS, notariuszem i rzeczywistymi
uprawnieniami. Brak bezpiecznej weryfikacji powyższych punktów oznacza
brak zgody na oznaczenie wdrożenia jako gotowego.
