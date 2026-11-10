# Leady dla kancelarii (giełda z oknem godzinnym)

Stan: 08.11.2026. Kod: `leady.py`, `meta_leady.py`, strona `/lead/`
(`seo/lead_strona.py`), giełda w oknie „Zapytania klientów”. Testy: `test_leady.py`.

## Jednostka: lead

Imię, nazwisko, telefon, e-mail, rodzaj sprawy (`leady.SPRAWY`), opis,
miejscowość, a z Meta dodatkowo: kampania, reklama, formularz, platforma
i wszystkie pozostałe odpowiedzi z formularza (doklejane do opisu jako
„Dodatkowo: …”). Lead z teczki niesie też pełne zapytanie z listą dokumentów.

## Źródła

| źródło | droga |
|---|---|
| formularz Meta (FB/IG Lead Ads) | webhook `POST /api/meta/leadgen` -> Graph API -> lead |
| strona: „dowolna kancelaria w miejscowości” | `wizyty.przyjmij` -> giełda (`PIECZAPP_DOWOLNA=gielda`, domyślnie) |
| teczka bez wybranej kancelarii | jw., z pełnym zapytaniem |
| ręcznie / import | `POST /api/admin/leady` |

Zgłoszenie do KONKRETNEJ kancelarii (klient ją wybrał) idzie jak dotąd
wprost do niej, bez giełdy.

## Zasada

1. **Okno (60 min, `PIECZAPP_LEADY_OKNO_MIN`)**: każda kancelaria z wykazu
   w miejscowości klienta (z e-mailem) dostaje mail z rodzajem sprawy,
   opisem i miastem, **bez kontaktu**, oraz jednorazowym linkiem
   `/lead/#token`. Kto odpowie w oknie (link albo aplikacja), widzi kontakt
   klienta, a klient dostaje e-mail z jego odpowiedzią. Odpowiedzieć może
   kilka kancelarii; klient wybiera. Płacący i niepłacący mają te same
   zasady; kolejność wysyłki maili to rotacja dnia.
2. **Archiwum**: po oknie lead z kontaktem widzą tylko kancelarie
   z opłaconym abonamentem, z tej samej izby notarialnej, i mogą na niego
   odpowiedzieć z aplikacji.

## Meta: konfiguracja

1. Aplikacja Meta z produktem Webhooks, subskrypcja `leadgen` dla strony,
   adres `https://app.notarai.pl/api/meta/leadgen`.
2. Sekret `notarai/meta` w Secrets Manager (eu-central-1), JSON:
   `{"verify": "...", "app_secret": "...", "token": "<token strony z leads_retrieval>"}`.
   `infra/3-wdroz-aplikacje.ps1` sam go wykryje i poda do zadania ECS.
3. Wersja Graph API: `PIECZAPP_META_GRAPH` (domyślnie v21.0 – sprawdzić aktualną).
4. Pytania w formularzu: imię i nazwisko, telefon, e-mail, miasto + pytania
   własne z kluczem zawierającym „sprawa” (lista: sprzedaż, darowizna,
   spadek, testament, …) i „opis”. Inne pytania (wartość, termin, kredyt)
   też przejdą, jako „Dodatkowo”.

## Do decyzji / później

- Treść zgody w formularzu Meta i w mailach do kancelarii (prawnie – na koniec).
- Limit i reputacja wysyłki SES przy wielu mailach do kancelarii spoza notarai.
- Rozszerzenie zasięgu, gdy w miejscowości jest mało kancelarii (powiat, okolice).
