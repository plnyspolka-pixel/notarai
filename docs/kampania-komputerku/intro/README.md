# Intro serii „Kancelaria pod Siódemką” — wersja ciepła (v2)

> **Wybrane przez właściciela (12.11.2026): `INTRO_5_komputerku_9x16.mp4`** — obowiązujące intro serii. Pozostałe cztery zostają jako warianty.
> **Outro serii (decyzja 12.11.2026): `OUTRO_siodemka_9x16.mp4`**: intro 1 „Siódemka” z pierwszej serii (v1), z podtytułem `notarai.pl` zamiast tytułu odcinka (wymóg biblii: plansza końcowa zawiera notarai.pl). Zastępuje dawną planszę `OUTRO_komputerku.png`.
> Render: `EPIZOD="notarai.pl" node narzedzia/render_intro.js <fonty> <wyjscie> 1`.
> Podgląd odcinka 1: intro 5, odcinek bez starej planszy, outro „Siódemka”: `../podglady/odc1_podglad_v2_z_intro.mp4` (40,6 s, 720x1280).

Stan: 12.11.2026. Pięć intro 9:16 (1080x1920, 30 kl./s), 7,6–9 s, dźwięk -16 LUFS.
Założenie: **ciepło i powitanie** — postacie same witają widza, złote światło z okna, miękkie przenikania,
ciepła muzyka. Marka tylko jako oryginalne logo i znaczek „AI” (warstwa `narzedzia/warstwy/warstwa_logo_ai.png`).
Wersja v1 (chłodna, graficzna) odrzucona przez właściciela; zostaje w `v1_chlodne/` jako archiwum.

| Plik | Co się dzieje |
|---|---|
| `INTRO_1_zaproszenie_9x16.mp4` | Wchodzimy przez drzwi (K7), Helena podnosi wzrok: „Dzień dobry. Zapraszamy do kancelarii pod Siódemką.” |
| `INTRO_2_kawa_9x16.mp4` | Para nad filiżanką na biurku (K9), Basia odwraca się od drukarki: „Proszę, proszę, zapraszamy. Kawa już się parzy.” |
| `INTRO_3_zespol_9x16.mp4` | Każdy wita się po swojemu: Helena „Dzień dobry”, Marta „Witamy serdecznie!”, Kuba „Dzień dobry! Zapraszamy!”, Basia o kawie; na końcu cztery twarze i tytuł. |
| `INTRO_4_poranek_9x16.mp4` | Słońce przez okno (K8), kawa (K9), Kuba w bibliotece: „Dzień dobry! Zapraszamy!” |
| `INTRO_5_komputerku_9x16.mp4` | Marta: „Komputerku… przywitaj się z Państwem.” — w dymku pisze się „Dzień dobry! Miło Państwa widzieć.” |

## Źródła (`zrodla_cieple/`)

- Ujęcia mówione: HeyGen Avatar 6 Model API (`POST /v3/models/avatars`, `model: heygen-avatar-6`) z kadrów obsady-v2
  (`kadr_K2m/K3m/K5m/K6m`, adresy `fal_url` z `postac.json`) i głosów ElevenLabs v2 (`eleven_v3`, voice_id z obsady-v2).
  video_id: helena `952e8c7032594bda9cff3bb017d4ece4`, basia `c3693f8cce354d09bc7e1321f4c882a3`,
  kuba `ecf6e20d799741d1ace03558f2ec7b10`, marta `12e3dcb2399e4aa580130f6933f1ad44`, marta_witamy `97ad2497eaef475d96d03447a234e767`. Koszt ok. 1 USD.
- Muzyka: ElevenLabs Music (panel fu `compose_music`, 12 s; pianino, gitara, smyczki pizzicato).
- Ambience: `glosy_v2/zrodla/ambience_kancelaria_22s.mp3`.

## Ponowny render

```bash
EPIZOD="Odcinek 2 · Tytuł" node narzedzia/render_intro_cieple.js <fonty_montserrat> intro/zrodla_cieple intro [1 2 3 4 5]
```

Fonty: `@fontsource/montserrat@5.1.0` (`npm pack`, katalog `package/files`). `EPIZOD=""` = bez podtytułu.
