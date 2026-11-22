# SEC-04 — [SEC-04] Zero Knowledge: izolacja AI/LLM, inference i wyników

**Status: PLANNED, not implemented.** Priorytet: P0
**Zależności:** SEC-01, SEC-03, #65

## Zakres
1. Zinwentaryzuj wszystkie ścieżki model inference (AWS Bedrock, zewnętrzne API, embeddings, OCR, logging, traces, support, cache). Sporządź precyzyjną mapę kto i kiedy może zobaczyć plaintext.
2. Domyślnie zabroń wysyłania decrypted plaintext poza atestowany Nitro. Jeśli model poza Nitro ma przetworzyć treść, to jawnie zdefiniuj osobny trust boundary i ustaw wynik ZK=UNVERIFIED; nie ukrywaj go w definicjach.
3. Wprowadź gateway polityki AI: pinned model/provider, region UE, allowlist operacji, data minimization, zerowy logging treści, osobne zgody gdy wymagane. Nie dopuszczaj fallbacku do publicznego API.
4. Przetestuj negatywne scenariusze prompt injection, ukryte URL/requests, egress do niezatwierdzonego dostawcy, retencję w logs/traces, eksfiltrację poprzez odpowiedzi modelu.

## Kryteria odbioru
- [ ] Maszynowo egzekwowana polityka 'plaintext stays in enclave' albo jawna odmowa ZK.
- [ ] Testy ujawnienia danych przez model, logi, podwykonawcę i zmieniony provider.
- [ ] Raport czego brakuje do confidential inference, zamiast deklarowania, że zwykły Bedrock = ZK.

## Zasady pracy w nowej konwersacji
To jest **PR planistyczny**. Na tym etapie nie ma implementacji ani działającego dowodu. Nowa konwersacja ma zrealizować zadanie na **tej konkretnej gałęzi PR**, nie zakładać kolejnego zbędnego PR. Najpierw przeczytaj kod i aktualny stan #57, #60, #61, #62, #65 oraz sprawdź ich SHA. Nie edytuj cudzych gałęzi i nie scalać bez integracyjnego przeglądu.

Reguły: test wyłącznie pilot01/pilot02 i fikcyjne dane; AWS eu-central-1; produkcja wyłączona; AUTO preview nie wysyła, nie podpisuje i nie składa wniosków. Nie podnoś operatorowi uprawnień custody, nie loguj PII/plaintext/sekretów i nie wprowadzaj sieciowego 0.0.0.0/0 dla guest. Każdą własność security potwierdź testami pozytywnymi i **negatywnymi**; brak konta/narzędzi oznacz BLOCKED, a nie PASS. Sama dokumentacja lub CI nie stanowi dowodu sprzętowego. Zapisz kod + testy + wyniki + wymaganą niezależną atestację w PR.

**Definition of done:** zmiana możliwa do niezależnego review, testy CI zielone, brak funkcji submit, wszystkie pozostałe ograniczenia podane jawnie, bez twierdzenia 'Zero Operator Access / Zero Knowledge verified' przed dowodami.
