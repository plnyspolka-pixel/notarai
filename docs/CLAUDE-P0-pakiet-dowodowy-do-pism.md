# P0 dla Claude'a: pakiet dowodowy do pism NotarAI
Audyt rzeczywistego AWS read-only, niezależnie od pilotażu. Kontynuacja GOV-01–11. Fundacja jest operatorem i integratorem; uprawnienia indywidualne notariuszy.

- D01: Stałe publiczne IPv4 wyjściowe test/prod; pomiar z tasków, NAT/EIP/routing, trwałość po wymianie tasku, wszystkie AZ. Nie IP ALB. Brak = blocker i minimalna naprawa/koszt.
- D02: Specyfikacja integratora, wersja produkcyjna i commit, role i uprawnienia per notariusz, status adapterów. Aktualne kontrakty i oficjalne formularze RZNP, e-Doręczenia INT, mObywatel uzupełnione potwierdzonymi danymi; źródło i wersja.
- D03: Diagram przepływu danych, procesorzy, jawne/szyfrowane, retencja i regiony wszystkich faktycznych usług, docelowe regiony cross-region inference, backupy, fallbacki.
- D04: Wszystkie używane modele Bedrock/Anthropic, API, wersje i fallbacki. Aktualne warunki dostawców dla konkretnego modelu, dowody braku retencji/trenowania oraz zakresu dostępu ludzkiego. Zweryfikować wymuszenie data_retention_mode none lub aktualnego odpowiednika, jeżeli dostępny; logging/tracing/cache; syntetyczne testy pozytywne i negatywne. Nie utożsamiać API Anthropic z Bedrock.
- D05: Dowody 3×Zero: rzeczywiste Nitro/attestation, szyfrowanie, wydawanie i odzyskiwanie kluczy, uprawnienia operatora. Testy cross-tenant, serwis/demo/pomocnik, role, rotacja, bezpieczna awaria. Security Manifest: release/hash/data/wyniki/granice oceny. Nie nazywać certyfikatem.
- D06: Załącznik techniczny KRN/MS TECH-12/13: pozytywna argumentacja oparta na faktycznych zabezpieczeniach kryptograficznych, infrastrukturalnych, organizacyjnych i kontraktowych, nie wyłącznie Nitro. Dokumentacja AWS/DPA, procesorzy, materiały do DPIA i art.25/28/32/35 RODO; weryfikacja stanu podpisu kwalifikowanego i statusu zawodowego. Rozróżnić plan od wdrożenia.

## Oddać jeden pakiet
00_PODSUMOWANIE_I_BLOKERY.md; 01_ADRESY_IP_I_SIEC.csv; 02_SPECYFIKACJA_INTEGRATORA.pdf + źródło; 03_PRZEPLYW_DANYCH_I_REGIONY.pdf + diagram; 04_MODELE_RETENCJA.csv + źródła; 05_TESTY_3ZERO_I_KLUCZE.md + manifest; 06_ZALACZNIK_KRN_MS.pdf + edytowalny; 07_FORMULARZE_INTEGRACYJNE; 08_DOKUMENTACJA_RODO_I_DOWODY; 09_INDEKS_DOWODOW.csv (teza, dowód, źródło, data, release, status).

Każdy punkt i pismo: GOTOWE/CZĘŚCIOWE/BLOKER/NIEZWERYFIKOWANE z dowodem lub następnym krokiem. Kod IaC i zielone CI nie dowodzą konfiguracji produkcyjnej. Bez zmian AWS/kosztów/IAM bez odrębnej zgody, bez wysyłania pism, bez podpisów za notariuszy, testy syntetyczne. Publiczne repo: wyłącznie zredagowany status, bez IP infrastruktury, kluczy, sekretów, ID kont, konfiguracji niejawnych, danych klientów. Pakiet pełny prywatnym kanałem z kontrolą dostępu; brak kanału oznaczyć jako blocker. DIP wysyłamy niezależnie od pilotażu i AWS.
