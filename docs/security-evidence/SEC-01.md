# SEC-01 — Raport odbioru (wyłącznie dane syntetyczne)

**Data:** 2026-11-22 UTC  
**PR:** https://github.com/plnyspolka-pixel/notarai/pull/66  
**Środowisko:** tylko repozytorium/testy lokalne GitHub Actions. **Nie wykonano atestacji sprzętowej AWS, decrypt KMS ani niezależnego audytu.**

## Materiały do samodzielnej kontroli

- `docs/security-claims/policy.json`: cztery twierdzenia, wszystkie w statusie `UNVERIFIED`; 12 scenariuszy TH-01…TH-12, każdemu przypisany właściciel i test odmowy.
- `confidential/security_claims.py`: walidacja ścisłego schematu, minimum wymaganych typów dowodów oraz pełnej macierzy TH, zegara, tenanta, digestu i podpisów ECDSA.
- `scripts/audit_confidential_claims.py`: bez AWS, bez dowodów wyświetla cztery `UNVERIFIED`; `--require-all-pass` musi zakończyć się kodem 2.
- `test_confidential_security_claims.py`: testy poprawnych podpisów i negatywne przypadki: brak, expiry/future, podmiana tenanta i SHA obrazu, fałszywe podpisy, klucz niezaufany, replay, brak custodian evidence, zaniżenie polityki, podmiana JS/LLM przez zmianę wymaganych pól.
- `docs/security-threat-model.md`: aktorzy i granice zaufania, pełna macierz ataków oraz precyzyjne definicje Zero Trust / Zero Operator Access / *ograniczonego* Zero Knowledge.
- `.github/workflows/confidential-browser.yml`: uruchamia nowy test i sprawdza brak fałszywego `PASS` przy pustym rejestrze.

## K1–K6

| Warunek | Stan implementacji | Dowód |
|---|---|---|
| K1 — cztery kompletne twierdzenia, walidacja schematu | Zaimplementowano; oczekuje ostatecznego CI | `test_k1_*` |
| K2 — 4/4 UNVERIFIED bez dowodów, mock/CI nie promuje | Zaimplementowano; oczekuje ostatecznego CI | `test_k2_*` oraz CLI `--require-all-pass` |
| K3 — 12 ataków i przypisanie testów odmowy | Zaimplementowano; oczekuje ostatecznego CI | `test_k3_*` i `policy.json` |
| K4 — negatywne testy podpisu, expiracji, tenant/image | Zaimplementowano; oczekuje ostatecznego CI | `test_k4_*`, `test_operator_cannot_downgrade_*` |
| K5 — jawne ograniczenia Zero Knowledge | Zaimplementowano; oczekuje ostatecznego CI | `test_k5_*`, `docs/security-threat-model.md` |
| K6 — brak automatycznych czynności prawnych | Zaimplementowano; oczekuje ostatecznego CI | `test_k6_*`; istniejące testy AUTO no-submit |

## Bramka końcowa

```sh
python -m pytest -q test_confidential_security_claims.py
python scripts/audit_confidential_claims.py
python scripts/audit_confidential_claims.py --require-all-pass  # powinien zwrócić 2
```

**PENDING:** wpisanie URL zielonego CI **na finalnym HEAD SHA** wraz z dokładną liczbą `passed/failed/skipped`. Do tego czasu PR nie spełnia całego wspólnego warunku zamknięcia i powinien pozostawać otwarty/draft.

### Co nie jest udowodnione przez SEC-01

Zero Trust, brak jednostronnego dostępu operatora, sprzętowa atestacja Nitro, faktyczne wydawanie klucza KMS wyłącznie do guest, brak eksfiltracji oraz pełne Zero Knowledge **nie uzyskały statusu PASS**. Do ich udowodnienia służą kolejne SEC-02…SEC-13 i niezależny audyt. Nawet syntetyczne dowody z valid signature nie dają prawa do claimów komercyjnych.
