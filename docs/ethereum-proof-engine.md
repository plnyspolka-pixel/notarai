# Wdrażamy Ethereum — NotarAI (branch `wdrazamy-ethereum`)

## Wykonane
- `proof_engine.py` — SHA-256, salt 32B, kanoniczne JSON (pola podstawowe), domain-separated Merkle trees, private receipt verification, Ethereum Mainnet anchor data and read-only transaction verification.
- `dowody_ethereum.py` — kancelaryjne API dostępu do prawdziwych plików `/api/dowody/*`, wykorzystujące istniejące sprawdzanie logowania i kontekst kancelarii.
- `magazyn.py` — wpis `ethereum_dowody` do istniejącego per-kancelaria storage z atomowym lokalnym zapisem / S3 ETag compare-and-swap.
- `app.py` — router; dostęp przez autoryzację dla prywatnych `/api/*`.
- `test_proof_engine.py` — testy offline integralności.

### API (prywatne, autoryzacja kancelarii)
- `POST /api/dowody/sprawy/{id}/dokument` z `{"plik":"projekt.docx"}` — serwer czyta rzeczywisty plik sprawy, liczy digest i zapisuje poświadczenie z losowym 32-bajtowym salt.
- `POST /api/dowody/partie` z `{"limit":100}` — buduje i zapisuje partię Merkle. Zwraca root i gotowe `calldata` (`FYP1` + root) dla autoryzowanego operatora Ethereum.
- `GET /api/dowody/sprawy/{id}` — prywatne dowody, witness i salt.
- `GET /api/dowody/partie/{batch_id}` — korzeń Merkle i stan partii.
- `POST /api/dowody/weryfikuj` z `{"receipt":{...}}` — sprawdza lokalną integralność. `ethereum_verified=false` dopóki nie istnieje zweryfikowana transakcja.

### Nie jest jeszcze produkcyjnym rejestrem kwalifikowanym
Nie uruchomiono żadnej transakcji na Ethereum. Nie skonfigurowano podpisującego portfela, RPC, periodycznej automatycznej publikacji, retencji WORM, podpisu/pieczęci kwalifikowanej, znacznika czasu QTSP ani procesu certyfikacji eIDAS.

Wpisy JSON są prywatne dla kancelarii, ale nie są kryptograficznie niezmienne **przed** publicznym zakotwiczeniem; administrator infrastruktury może modyfikować plik, a ewentualne poświadczenie musi być powiązane z opublikowanym rootem. Weryfikator pokazuje integralność kryptograficzną załączonego receipt, nie potwierdza zewnętrznie czasu ani autentyczności aktu. To nie zastępuje repertoriów, CREWAN, aktów papierowych ani wymagań ustawy Prawo o notariacie.

Jeżeli kancelaria przechowuje wszystko `u-klienta`, endpoint rejestracji dowodu odmawia działania: dane nie mogą zostać po cichu przeniesione do chmury. Wymagane oddzielne rozwiązanie offline.

### Zachowanie poufności
W Ethereum publikujemy tylko 32 bajty zbiorczego root. Bez PESEL, nazw aktów, danych stron, nawet bez bezpośredniego hasha dokumentu. Payload + salt + proof pozostają wyłącznie w chronionym magazynie kancelarii. Nie należy publicznie wystawiać receipt ani współdzielić ze stronami postronnymi.

### Uruchomienie testów
`pytest -q test_proof_engine.py`

### Przed uruchomieniem na produkcji
1. Wprowadzić kontrolę IAM, archiwum WORM/Object Lock, niezależny backup i ograniczyć możliwość usunięcia dowodów.
2. Rozdzielić pieczęcie/klucze między kancelarie; rozstrzygnąć rotację i eksport.
3. Zbudować bezpieczną infrastrukturę podpisywania transakcji Ethereum w AWS (bez kluczy prywatnych w repo lub env).
4. Ustalić cykl automatycznego seal/publish/verify i obsługę reorgów.
5. Wykonać testy end-to-end w SaaS, w tym RLS/tenant isolation, problemy przy awarii S3 i wielowątkowość.
6. Oddzielnie ocenić wymogi eIDAS 2 / kwalifikowanego rejestru elektronicznego.

## Potwierdzenie Ethereum
- `POST /api/dowody/partie/{batch_id}/potwierdz` z `{"tx_hash":"0x..."}` pobiera potwierdzenie transakcji z ustawionego po stronie operatora `NOTARAI_ETH_RPC_URL` i weryfikuje adresy `NOTARAI_ETH_SENDER`, `NOTARAI_ETH_RECIPIENT`, sieć Mainnet, calldata i 12 potwierdzeń.
- Dopiero pozytywna weryfikacja zmienia stan partii na `confirmed`. To odczyt RPC, nie wysyłka transakcji. Wszystkie trzy zmienne środowiskowe należy konfigurować bez sekretów w repozytorium.
- `.github/workflows/ethereum-proof-tests.yml`: testy modułu kryptograficznego i kompilacja składni Python. Testy nie sprawdzają jeszcze połączenia z AWS S3, KMS i rzeczywistym Ethereum.

**Wymagane przed produkcją**: osobny podpisujący, bezpieczne odtwarzanie danych, reguły retencji i kompletne testy dostępu do dokumentów w trybie wielokancelaryjnym.
