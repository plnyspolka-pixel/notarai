# Intro serii „Kancelaria pod Siódemką” (5 wariantów, 9:16)

Stan: 12.11.2026. Każde intro trwa 6 s, ma format 1080x1920 i 30 kl./s, dźwięk AAC 48 kHz normalizowany do -16 LUFS.
Materiały wyłącznie z pakietu kampanii: scenografia v2 (`pakiet/09_scenografia_v2`, K1–K9), obsada v2
(`pakiet/10_obsada_v2`), tokeny marki, oryginalny sygnet i warstwa logo ze znaczkiem „AI” (bez belki „treść AI”, zgodnie z decyzją z 12.11).

| Plik | Pomysł |
|---|---|
| `INTRO_1_siodemka_9x16.mp4` | Najazd na drzwi kancelarii (K7). Na drzwiach rysuje się siódemka w gradiencie marki, potem od dołu wjeżdża panel z tytułem. |
| `INTRO_2_obsada_9x16.mp4` | Cztery szybkie ujęcia postaci (Helena, Marta, Basia, Kuba) z kartami imion, przejścia ukośnym pasem marki, na końcu plansza z czterema twarzami i tytułem. |
| `INTRO_3_komputerku_9x16.mp4` | Marta przy stole roboczym mówi „Komputerku…”. Dymek przechodzi przez stany z biblii wizualnej („Komputerku…”, „Już sprawdzam…”, „Gotowe do sprawdzenia”), potem plansza z hasłem „Decyzję zawsze podejmuje notariusz”. |
| `INTRO_4_plan_9x16.mp4` | Rzut kancelarii rysuje się liniami marki, kamera K1 „wjeżdża” w prawdziwe wnętrze (plan ogólny), na dole tytuł. |
| `INTRO_5_poranek_9x16.mp4` | Poranek w kancelarii: 8:00 okno (K8), 8:05 biurko z kawą (K9), 8:15 sekretariat (K3), potem szklana karta tytułowa na rozmytym planie ogólnym. |

Dźwięk: ambience kancelarii (`glosy_v2/zrodla/ambience_kancelaria_22s.mp3`), krótki akord przy tytule, świsty przejść
i „blipy” syntetyzowane w ffmpeg (bez licencji zewnętrznych). Intro 3 ma głos Marty „Komputerku…”
(`glosy_v2/zrodla/komputerku_marta_intro.mp3`, ElevenLabs `eleven_v3`, voice_id obsady v2).

## Ponowny render (np. inny odcinek)

```bash
EPIZOD="Odcinek 2 · Tytuł odcinka" node narzedzia/render_intro.js <katalog_fontow_montserrat> intro [1 2 3 4 5]
```

Fonty: `@fontsource/montserrat@5.1.0` (`npm pack`, katalog `package/files`), tak samo jak w `render_plansz.js`.
`EPIZOD=""` daje intro bez podtytułu odcinka.
