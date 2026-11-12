# Część 1: identyfikatory zadań (do odzyskania wyników)

| Ujęcie | Model | request_id |
|---|---|---|
| B1 zegar | fal-ai/wan-25-preview/image-to-video | 01a1d041-490f-7862-8cf4-fe9ef6c1e2e4 |
| B2 telefon | fal-ai/wan-25-preview/image-to-video | 01a1d041-492c-7c62-b313-aa2c90aa3bd1 |
| B4 drukarka | fal-ai/wan-25-preview/image-to-video | 01a1d041-4992-7cf0-94eb-c65a6b54fb7c |
| B3 Pan Zenon w drzwiach | fal-ai/kling-video/v2.5-turbo/pro/image-to-video | 01a1d041-495c-7ae0-bef2-4a01bf51c730 |
| B5 Basia „chwileczkę” | fal-ai/kling-video/v2.5-turbo/pro/image-to-video | 01a1d041-497f-7691-b90d-1437674f6e3a |

## HeyGen Avatar 6 (Model API, `GET /v3/models/videos/{id}`)

| Ujęcie | Kwestia | video_id |
|---|---|---|
| T1 Basia | „Tak, jutro o jedenastej trzydzieści…” | f4dbc8f278624d1ead33668230bb5249 |
| T1 Basia | „Dzień dobry. Już się panem zajmuję.” | 1f2ce7995d3947e89c9bb7eb91333def |
| T1 Basia | „Już sprawdzam.” | e7f69996f0df4268ae007e8c7c413dee |
| T2 Pan Zenon | „Dzień dobry. Ja tylko na chwilę…” | 30a07333631a4dea90b4329ebdebdff5 |
| T3 Marta | „Basiu, sprawa pani Ireny?” | 4de22acdafdd4e35af112153b905201e |

## Głosy (ElevenLabs eleven_v3, Storage studio-media/mcp/tts/2026-11/)

Kuba `odc01_s01_kuba-04424a07.mp3` (zza kadru), Basia `odc01_s02_basia_1-67b22a41`, `_2-5f89c6ee`, `_3-46979760`,
Pan Zenon: kwestia do ponownego nagrania głosem 1 `xu17wWrBQRmEysbBcctv` z konkretnym dokumentem (wersja z `dE7Z…` odrzucona), Marta `odc01_s02_marta-3fa22250`.

## Zmiana obsady (kanon 12.11)
- Paweł Nowak zamiast Pana Zenona: kadr K3 `tzjaWLhC5JZ84cuhfIunp` (T2_pawel_K3_2), K7 `ke4o9xVB7uoO-YPY_RmUV` (B3_pawel_K7_1).
- Wejście Pawła (Kling): 01a1d063-f75d-7e63-99a8-dc364dca263a. Paweł mówi (HeyGen Avatar 6): 9477270ab803470eb1f1aae552be94ef, głos `7KAMhhzp05frisJC5L7o`, nagranie `odc01_s02_pawel_c-09d45a32.mp3`.
- Odrzucone (archiwum, nie używać): Pan Zenon B3 01a1d041-495c-7ae0-bef2-4a01bf51c730, HeyGen 30a07333631a4dea90b4329ebdebdff5.

## Montaż
`narzedzia/montaz_odc01_cz1.sh` → `podglady/odc01_czesc1.mp4` (31,4 s): sc. 01 (7,5 s) → intro 5 (8 s) → sc. 02 (15,9 s).
Warstwy: `narzedzia/render_warstwy_odc.js` (karty imion, „Poniedziałek 8:57”). Efekty: ElevenLabs SFX (telefon, drzwi, drukarka, gwar recepcji).

# Część 2 (sc. 03–05)

- Ekrany: prawdziwa aplikacja z gałęzi `claude/odcinek-01-ekrany`, dane demo poprawione pod kanon (sprawa „NOWAK — KACZMAREK”, S-041-2026,
  kupujący Kaczmarkowie, Paweł jako kontakt, 56,40 m², 640 000 zł, akt 17.11 11:30; pola „wymagają uwagi”: sposób zapłaty, termin wydania, data aktu).
  Nagranie: `narzedzia/nagraj_ekrany_odc01_cz2.js` (zrzuty 2×/3× + ramki elementów), sztuczna kamera = fikcyjne zaświadczenie D08.
  Animacja: `narzedzia/render_ekrany_odc.js` + `czesc2_ekrany/plan.json`. Podpis „Prawdziwy ekran NotarAI · dane demonstracyjne”.
- Kadry (fal): T4 Basia przy monitorze `9ROXn_wlT2Slaqx4_iwjS`, T5 Marta za Basią `1ajZAqsVE2o2c7RSNJpMa`, T6 Basia z kartką i telefonem `yxoltoSD3LNDEPLijZUjg`,
  B6 zdjęcie telefonem `gmW501fg86qyvHQsy_LH7`, B7 Kuba czeka `GxgmQAIJhF61elFLGCyAZ`.
- HeyGen Avatar 6: s03 Basia 6e1e59751029468796849168836036b2, s04 Paweł 258faf4c35b0492cb64960001e151dab, s04 Basia 91f99b0bed0e47638c1e951ace644a21,
  s05 Marta b75235f02b534a579e0956b9c1294d01, s05 Basia 2f8d855cd15d4033837662f9cd4f7b00.
- Kling: Marta podchodzi 01a1d07b-f679-7990-b949-bebec8514f28, zdjęcie telefonem 01a1d07b-f625-7163-a7ea-dc877c2657fe, Kuba czeka 01a1d07b-f60e-7ac0-ab0e-442fbe3fd94d.
- Montaż: `narzedzia/montaz_odc01_cz2.py` → `podglady/odc01_czesc2.mp4` (38,5 s). Pauza strategiczna: po „…z następną sprawą” gwar cichnie, 0,9 s ciszy, potem telefon.

# Część 3 — prawdziwy projekt z Bedrock (NA-7)

- Dostęp: klucz API Amazon Bedrock (eu-central-1) zapisany jako sekret sieciowy środowiska „pieczapp”, wstrzykiwany przez pośrednika
  tylko do `bedrock-runtime.eu-central-1.amazonaws.com`; w procesie `AWS_BEARER_TOKEN_BEDROCK=proxy-injected` (zaślepka), boto3 ≥ 1.40.
- Model: `eu.anthropic.claude-opus-4-6-v1` (profil EU). **Czas sporządzenia projektu: 153 s** (1 wywołanie, we 4594 / wy 13652 tokenów, koszt 1,48 zł).
- Projekt v1 (`czesc3_ekrany/projekt_NOWAK_KACZMAREK_v1.docx`, tekst `projekt_tekst.txt`): zgodny z kanonem — Helena Radecka, Kaczmarkowie,
  56,40 m², 640 000 zł; `<<BRAK>>`: data aktu, sposób zapłaty ceny, termin wydania lokalu; `<<WYBOR>>` w § 2 (stan działów III/IV).
- Zrzuty stanów sc. 06–10 (W1–W10) do animacji: `czesc3_ekrany/`, skrypt `narzedzia/nagraj_ekrany_odc01_cz3.js`.

# Część 3 (sc. 06–09)

- Kadry (fal nano-banana-pro/edit): T7 Kuba przy stole `LHR2puHRhfdDL` (1), `QKaozzIERvygUw` (2); B8 Marta i Kuba `dDD7yluCUPzvIh15ZAvps`;
  T8 Helena z okularami `A6_V0a8VjKanVqCyygv6w`; B9 Kuba dzwoni `eu6QvDcODP5KgR0T-bvZx`; B10 Marta z dokumentami `Jqo20bOq2Tyhg`;
  B11 Helena przy telefonie `Dj7njE2LmrPs81WatPCyU`. Zegar 9:24 (nano-banana/edit) odrzucony: wskazówki źle, przeskok czasu kartą „9:24”.
- Głosy: `odc01_s06_kuba_1-353c2f05`, `s06_marta_1-e00e426f`, `s06_marta_2-9c0976e8`, `s06_kuba_2-906f2990`, `s07_helena_1-fd0d85f6`,
  `s07_marta-96d239a6`, `s07_helena_2-b492e934`, `s08_marta-37e70e1a` (transkrypcja zgodna).
- HeyGen Avatar 6: s06 Kuba 1 819ed00ede8b4a748e776d63ece766ca, s06 Marta 1 cb42dd6b3140486bbabc0cf5c64f4c6c, s06 Marta 2 0ef6f5777926408c8a1af2686d42daf8,
  s06 Kuba 2 966d6c1480324a51b1223fc8112f507f, s07 Helena 1 d2f5f78957f84730851d68beadba0181, s07 Marta f0a4df9736cb45ffaa1dc8cd69a9a927,
  s07 Helena 2 8b6068a04b4d4b8dbf0c0f4f157533cb, s08 Marta 6110609869e249bcbd5a01f66d3a8b26.
- Ekrany: `czesc3_ekrany/plan.json` → `czesc3_wideo/F1–F5` (weryfikacja, „Wymagają uwagi”, Sporządź projekt, Sporządzam projekt…, kalendarz w trakcie).
- Sc. 09 bez ruchu (kadry z powolnym najazdem): Kling niewykonany, fal bez środków (12.11). Do wymiany: B9, B10, B11, B8 (uśmiechy).
- Montaż: `narzedzia/montaz_odc01_cz3.py` → `podglady/odc01_czesc3.mp4` (47,8 s). Gwar cichnie na pauzie przed „komputerku”, sc. 09 spokojne biuro, karta „9:24”.
