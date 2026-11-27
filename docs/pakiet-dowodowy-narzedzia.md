# Narzędzia P0: RZNP i indeks dowodów

## RZNP — etap offline
Oficjalna strona: https://www.gov.pl/web/cyfryzacja/udostepnianie-danych-z-rejestru-zastrzezen-numerow-pesel
Oficjalne archiwum (17.04.2024): https://www.gov.pl/attachment/e9b8d838-ebdc-4fd7-a254-83f101d991b9
Strona wymienia kontrakt OpenAPI rejestr-zastrzezen-proxy-contract.yml oraz emulator 2.0.8. Pobranie ZIP w środowisku autora nie powiodło się; nie potwierdzono zawartości ani hash oficjalnego pliku.
Po pobraniu archiwum do prywatnego katalogu:
```sh
python scripts/rznp_kontrakt_audyt.py /private/rznp.zip --out /private/rznp_inventory.json
```
Skrypt nie rozpakowuje i nie uruchamia JAR. Sprawdza limity, nazwy, sumy SHA-256 i obecność dokładnie jednego kontraktu. INVENTORY_ONLY nie oznacza walidacji OpenAPI, autentyczności, zgodności z emulatorem ani połączenia produkcyjnego. Przekazać autorowi kodu sam publiczny kontrakt, bez sekretów, aby przygotował adapter zgodny z jego rzeczywistą strukturą.

## Indeks materiałów D01–D06
W prywatnym katalogu umieścić dowody, a w osobnym JSON listę dokładnie sześciu wpisów D01–D06, przykładowo:
```json
[
  {"id":"D01","status":"BLOKER","files":[],"next_step":"Ustalić trwałe egress IP"},
  {"id":"D02","status":"NIEZWERYFIKOWANE","files":[],"next_step":"Potwierdzić wdrożenie"},
  {"id":"D03","status":"NIEZWERYFIKOWANE","files":[],"next_step":"Ustalić regiony"},
  {"id":"D04","status":"NIEZWERYFIKOWANE","files":[],"next_step":"Uruchomić audyt Bedrock"},
  {"id":"D05","status":"NIEZWERYFIKOWANE","files":[],"next_step":"Wykonać testy 3Zero"},
  {"id":"D06","status":"NIEZWERYFIKOWANE","files":[],"next_step":"Przygotować załącznik"}
]
```
```sh
python scripts/pakiet_dowodowy_indeks.py --root /private/evidence --plan /private/status.json --out /private/index.json
```
GOTOWE wymaga pliku dowodowego; status deklaruje człowiek. Pozostałe wymagają następnego kroku. Kod wyjścia 2 oznacza nierozwiązane punkty. Indeks nie jest podpisanym certyfikatem ani dowodem zgodności. Nie publikować raportów ani inwentarza infrastruktury w repo.

Testy niezależne od AWS:
```sh
python -m pytest -q test_rznp_kontrakt_audyt.py test_pakiet_dowodowy_indeks.py test_audyt_bedrock_dowody.py
```
Claude: odczyty AWS i środowiska z przyznanymi dostępami; autor kodu: integracje offline, testy, generatory. Nie wstrzymywać DIP na pilotaż.
