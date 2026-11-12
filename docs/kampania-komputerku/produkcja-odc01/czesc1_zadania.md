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
