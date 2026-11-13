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
- Poprawka dźwięku sc. 08–09 (uwaga użytkownika: od 33 s rozmowy bez głosu, potem cisza): tło biura przegenerowane i wyrównane,
  rozmowy przez telefon słyszalne. Głosy `odc01_s09_basia-1bbd0769`, `s09_kuba-929ba7c4`, `s09_helena-a6ee12c5`;
  HeyGen: Basia 1ee5913c842d4919a8e40f942d9e0857, Kuba 73328c0962da44438de980eae4bb5169, Helena 47dc9d6210c340a5915c75d96d183918.

# Część 4 (sc. 10–12 + outro)

- Kadry: T9 Helena z wydrukiem `TTHHkzt_0BRnEnQQ7p2Ts` (szeroki `edM7Xf0mdN6YZY0jyv6rz`), T10 Marta w gabinecie `9cMuQuoJUXimYOI4s6m2O`,
  T11 Basia w drzwiach `i_5BZ3PI1llbdP2MHGv0n`, B13 długopis `ZFTtgkW58_aloypyblJ97`.
- Głosy: s10 Marta `3cda8c3b`, s10 Kuba `74615429`, s11 Helena 1 `8b4d9f4f`, s11 Marta `ed4c7028`, s11 Helena 2 `8a3926e0`,
  s12 Basia 1 `8a05eda4`, s12 Helena `6961549d`, s12 Basia 2 `basia_2b-88d330a8` („bez sena” w `basia_2-12e42ede` odrzucone).
- HeyGen: s10 Marta 16a71f398f6d4f128595c9b52ca8bca7, s10 Kuba 5ef4454b3f1d4e3f9ccefbf4ed1cf30a, s11 Helena 1 8fae1a793ee74867826aa5f0250f2505,
  s11 Marta f4fd5ec2836446bdaf7cd3a335861098, s11 Helena 2 2d8b6247f6404aa6993f2b47f171bdb6, s12 Basia 1 b527819c37894f5b8b81e5614e6bf591,
  s12 Helena 6a9cd589294d447f821ae15059a5c3b2, s12 Basia 2 7b57394856814273ace7b000394f78e1.
- Kling: długopis 01a1d0f1-5869-71f3-9e58-cae786f7a41c; część 3: Marta z dokumentami 01a1d0ee-8e21-7c01-97cb-478dbf0afe93, uśmiechy 01a1d0ee-8e15-7883-abe9-0925454280f4.
- HeyGen s12 Helena „Oczywiście”: pierwsze podejście 6a9cd589… nieudane (za krótkie nagranie); ponownie z ciszą na końcach d6c2ef4b21554821a0ca82caffa15182.
- Ekrany: `czesc3_ekrany/plan_cz4.json` → `czesc4_wideo/G1–G4` (powiadomienie, projekt, WYBÓR/BRAK, Pobierz jako Word).
- Tło gabinetu: gwar recepcji przytłumiony filtrem (wygenerowane tło pokoju było nieme). Napis końcowy: warstwa `outro_napis.png`.
- Montaż: `narzedzia/montaz_odc01_cz4.py` → `podglady/odc01_czesc4.mp4` (51,8 s). Część 3 przemontowana z klipami Kling (uśmiechy, Marta z dokumentami).
- Renderer warstw: fonty przez `goto` do pliku (przez `setContent` Montserrat się nie ładował); karty imion do ponownego użycia w pełnym montażu.

# Zmiana 12.11 wieczorem: EKW w sc. 06 (decyzja użytkownika)
- Kuba pobiera treść KW z EKW (prawdziwa karta „Księga wieczysta z EKW”, serwer demo `--atrapa-ekw`: księga fikcyjna, bez połączenia z EKW)
  i dopisuje w „Rozmowie o sprawie”: działy III i IV bez wpisów. Projekt sporządzony ponownie (Bedrock) z tą rozmową.
- Sc. 11: Helena zatrzymuje się przy § 5 (termin wydania lokalu) zamiast § 2.
- Głosy: Kuba `s06_kuba_ekw_1b-cd7e9fca` („z e-ka-wu”; wersja `ekw_1-ecd65c67` czytała „z KW”), `s06_kuba_ekw_2-aa6b640a`, Helena `s11_helena_1b-1f78aae6`.
- HeyGen: Kuba EKW 1 588ec89120784a6bb84e40c1d0ed0420, Kuba EKW 2 90af25d780d74637a8bd2f57120696a4, Helena § 5 dc5d165531bd4d5693c7955df18b177f.
- Poprawka (decyzja użytkownika): bez ręcznego dopisywania. Kuba: „Dział trzeci i czwarty bez wpisów. Projekt sam to uwzględni.” (`s06_kuba_ekw_2b-03781af1`,
  HeyGen a8dd8c3009074c85a479b94d90bfb895); ujęcie „Rozmowa o sprawie” usunięte z montażu. Funkcję w kodzie robi sesja
  session_015k5XGBVzUU48yKskLFFgRm („Projekt aktu z treścią księgi pobranej z EKW”); po wdrożeniu nagrać projekt ponownie bez dopisku w rozmowie.

# Poprawki dźwięku i zapowiedź odc. 02 (12.11 wieczorem)
- Długopis: z pliku SFX tylko sam klik (bez szumu tła, który był podbity 4×). Sc. 01: dwa dzwonki telefonu (drugi ciszej, przytłumiony, w tle ujęcia z Pawłem).
- Muzyka: `czesc4_wideo/muz_intryga.mp3` (ElevenLabs compose, fortepian i smyczki) od wahania Basi przed „bez syna” do czerni; `muz_zapowiedz_wolniej.mp3` (rosnące napięcie, 0,8×) pod zapowiedzią.
- Zapowiedź odc. 02 „Proszę nie przy nim”: plansza „W następnym odcinku” na ujęciu Pawła pod drzwiami (fal `fu-dBUQBs0BebaKwIBhsN`, Kling 01a1d156-5d8e-7a03-868b-74657656c0a1),
  Helena „Pani Ireno… jakiego terminu pani naprawdę chce?” (`odc02_zapowiedz_helena-b37425d0`, HeyGen 209c977f267b4dc9be26ebb5b9244e0f), plansza tytułu `zap_tytul.png`. Irena tylko poza kadrem.

# Poprawki ciągłości (13.11)
- Basia przy komputerze: klawiatura była przed drukarką. Nowe kadry: T4b `5EyGHeQaLrUPNYB07fjJG` (monitor i klawiatura przed nią, drukarka z boku),
  T5b `trg_HxP7ELKrSTIb79Thq`. HeyGen s03 Basia 65d7a939ca3543df87abe187f9370f5d, Kling t5 01a1d243-129d-7be0-afd4-b0d72f65372a.
- Helena sc. 07: okulary jednocześnie na twarzy i w dłoni. Kadr T8b `CJLSYNYhttUeJH5Jqts7W` (okulary tylko w dłoni);
  HeyGen s07 Helena 1 38a4bf53bc7147c6838a9023517a5e7c, Helena 2 0e3170ad037643769ab5e1c11ba962b7.
- Zapowiedź: Helena miała „zdjąć okulary”, a okulary zostały na twarzy. Nowe ujęcie bez tego gestu 468f680e7617458aa456f048fee954f9.
