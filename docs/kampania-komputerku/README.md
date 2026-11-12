# Kampania „Komputerku…” — koncepcja produkcji powtarzalnej

> **Aktualne (12.11.2026): kancelaria-v2 / obsada-v2.** Scenografia z jednego źródła prawdy (plan, materiały, 9 stałych kamer) i powtarzalny proces wprowadzania postaci: [`KANCELARIA_I_POSTACIE.md`](KANCELARIA_I_POSTACIE.md), narzędzie `narzedzia/kancelaria.py`. Silniki awatarów i koszty: [`awatary.md`](awatary.md). Obsada v1 (`pakiet/08_obsada_v1`) zostaje jako archiwum.

Stan: 11.11.2026. Pakiet graficzny: `pakiet/` (start: `pakiet/README_START_TUTAJ.md`).
Scenariusze sezonu 1: `scenariusze.md`. Szablon odcinka: `odcinek-szablon.json`.
Render plansz: `narzedzia/render_plansz.js`.

## 1. Założenie

Seria krótkich mikrofabuł (30–40 s, 9:16) z czterema stałymi postaciami
(Helena, Marta, Basia, Kuba) w jednej kancelarii. Produkcja ma iść **tym samym
torem co rolki Finance You** w Studiu publikacji (`finyou`: ElevenLabs →
HeyGen → wypalanie napisów na Fly.io / Remotion → kolejka publikacji),
rozszerzonym o dwie rzeczy, których rolki dziś nie mają:

1. **kilka postaci w jednym filmie**, każda z własną, stałą twarzą i głosem,
2. **ujęcia sceniczne** (plan ogólny, reakcje, rekwizyty) generowane w fal.ai
   z tych samych klatek wzorcowych.

Prawdziwe ekrany NotarAI zawsze z nagrania `app.notarai.pl` na koncie demo
i danych testowych — nigdy generowane.

## 2. Jak trzymamy jednolite postacie i głosy

Zasada: **tożsamość tworzymy raz, potem tylko ją wskazujemy**. Nic, co
definiuje postać, nie jest generowane od nowa w odcinku.

| Element | Ustalamy raz (wersja „obsada-v1”) | W odcinku |
|---|---|---|
| Twarz i strój | 4 zdjęcia wzorcowe (`pakiet/02_bohaterowie/*_ref.jpg`) + arkusz postaci: przód, ¾, profil, 3 emocje — wygenerowany raz w fal (Nano Banana Pro edit z referencją) i **zatwierdzony przez człowieka** | tylko wskazanie pliku wzorca |
| Scenografia | 6–8 **klatek wzorcowych pokoju** (plan ogólny przy biurku Heleny, Basia przy drukarce, Marta przez ramię z laptopem, Kuba z teczką, detal rekwizytu) według `plan_kancelarii.svg` | klatka startowa ujęcia = jedna z nich albo jej edycja (gest, rekwizyt) |
| Głos | 4 głosy ElevenLabs zaprojektowane raz (Voice Design z opisu: wiek, barwa, tempo, polszczyzna) i zapisane jako stałe `voice_id` + stałe ustawienia (stability, similarity, style, speed) i jeden model (`eleven_v3`) | tylko `voice_id`; tekst kwestii z tagami emocji v3 (np. `[ironicznie]`) |
| Awatar mówiący | każda postać = osobny **HeyGen talking photo** z jej zdjęcia wzorcowego (jak dziś „domyślne awatary” Studia) | identyfikator awatara z katalogu |
| Prompt | stały prompt bazowy + negatyw z `PROMPTY_PRODUKCYJNE.md`; zmienia się tylko opis akcji | doklejany automatycznie |
| Grafika | PNG z `pakiet/03_plansze_video` i `04_grafika_systemowa`, tekst z `render_plansz.js` | podmiana tytułu odcinka i ponowny render |

Wszystko powyżej trzymamy w jednym pliku konfiguracji obsady (`obsada-v1`):
`postac → {zdjecie_wzorcowe, arkusz, heygen_talking_photo_id, elevenlabs_voice_id,
ustawienia_glosu}`. Zmiana czegokolwiek = nowa wersja obsady (`obsada-v2`),
nigdy cicha podmiana w trakcie sezonu.

Kontrola spójności przed publikacją: siatka 10 pytań z
`pakiet/05_biblia_produkcji/BIBLIA_WIZUALNA.md` + porównanie kadru z arkuszem
postaci (człowiek, 1–2 min na odcinek).

## 3. Tor produkcji jednego odcinka

```
scenariusz (scenariusze.md → odcinek.json)
  │
  ├─ 1. Głosy ─ ElevenLabs, eleven_v3, stałe voice_id ─────────────┐
  │     każda kwestia osobno /with-timestamps (jak Studio)         │ audio + czasy znaków
  │                                                                │
  ├─ 2. Klatki ujęć ─ fal: Nano Banana Pro edit                    │
  │     wejście: klatka wzorcowa pokoju + zdjęcie wzorcowe postaci │
  │                                                                ▼
  ├─ 3a. Ujęcia mówiące ─ HeyGen talking photo (audio z kroku 1)
  │      albo fal: Kling AI Avatar v2 Pro / OmniHuman 1.5 (klatka + audio)
  ├─ 3b. Ujęcia bez mowy (reakcje, rekwizyty) ─ fal: Kling 2.5 Turbo Pro image-to-video
  ├─ 3c. Ekran NotarAI ─ nagranie app.notarai.pl (Playwright, konto demo)
  │
  └─ 4. Montaż i wykończenie ─ Remotion Lambda (eu-central-1) albo caption-burner (Fly.io, waw)
        sklejka ujęć + intro/outro + grafika systemowa + napisy z czasów lektora
        + znaczek „AI” + logo  →  9:16, potem 16:9 i 1:1
        → kolejka publikacji Studia (YouTube Shorts, Reels, TikTok)
```

Dlaczego tak, a nie jednym modelem „tekst → film”: modele generujące całą
scenę z dźwiękiem (Veo 3.1, Happy Horse, Kling O3 reference) dają własne głosy
i drobne różnice twarzy między ujęciami. Rozdzielenie **głos (ElevenLabs) →
twarz (stała klatka) → ruch ust (awatar)** daje powtarzalność, a koszt
pojedynczej poprawki to jedno ujęcie, nie cały film.

Kiedy HeyGen, a kiedy fal w kroku 3a:
- **HeyGen talking photo** — gdy postać mówi do kamery w zbliżeniu (B, 85 mm).
  To już działa w Studiu i ma najpewniejszy ruch ust po polsku.
- **fal (Kling AI Avatar / OmniHuman)** — gdy postać mówi w ujęciu z planu
  (A, C), bo animuje całą klatkę ze scenografią, nie tylko twarz.

## 4. Oznaczenie treści AI

Tak jak w rolkach Finance You: **tylko mały znaczek „AI”** w prawym górnym
rogu pod paskiem aplikacji, przez cały film (wzór `AI_BADGE` w
`finyou/src/lib/caption-style.ts`, warstwa `OVERLAY_TRANSPARENT.png`).
Belki „Treść wygenerowana przez AI” ani dopisków o postaciach generowanych
przez AI na planszach **nie używamy** (decyzja właściciela 12.11.2026).
Przy publikacji można dodatkowo zaznaczyć etykietę „treść AI” w ustawieniach
platformy (Meta, TikTok, YouTube).

## 5. Koszt jednego odcinka (35 s)

Ceny sprawdzone 11.11.2026: fal — z cennika konta (`get_pricing`), ElevenLabs —
elevenlabs.io/pricing/api, HeyGen — blog HeyGen z 20.10.2026 (oficjalny cennik
API jest za logowaniem w platform.heygen.com, **do potwierdzenia**), Fly.io —
docs.fly.io/about/pricing. Kurs przyjęty orientacyjnie: 1 USD ≈ 3,7 zł.

Założenia odcinka 35 s (jak odc. 1): ok. 24 s mówionych (14 s zbliżeń, 10 s
w planie), 4 s reakcji bez mowy, 7 s ekranu NotarAI (nagranie, 0 zł),
3 s outro (plansza, 0 zł); ok. 400 znaków dialogu; **każde ujęcie liczone
w 2 podejściach**, klatki w 3.

### Wariant zalecany: ElevenLabs + HeyGen + fal

| Krok | Wyliczenie | USD |
|---|---|---|
| Klatki ujęć (fal Nano Banana Pro edit, $0,15/obraz) | 5 klatek × 3 próby | 2,25 |
| Głosy (ElevenLabs eleven_v3, $0,08/1000 znaków) | 400 zn. × 3 podejścia | 0,10 |
| Zbliżenia mówiące (HeyGen Avatar IV, ~$0,05/s) | 14 s × 2 | 1,40 |
| Mówiące w planie (fal Kling AI Avatar v2 Pro, $0,115/s) | 10 s × 2 | 2,30 |
| Reakcje bez mowy (fal Kling 2.5 Turbo Pro i2v, $0,07/s, klip min. 5 s) | 2 klipy × 5 s × 2 | 1,40 |
| Scenariusz/plan ujęć (LLM) | — | ~0,05 |
| Montaż Remotion Lambda | szacunek | ~0,10 |
| Fly.io caption-burner (~$0,0000016/s) | kilka minut pracy | <0,01 |
| **Razem** | | **≈ 7,70 USD ≈ 29 zł** |
| **Z zapasem na poprawki (×1,5)** | | **≈ 12 USD ≈ 43 zł** |

### Porównanie wariantów (jeden odcinek, z zapasem ×1,5)

| Wariant | Co robi ruch ust | Koszt | Uwagi |
|---|---|---|---|
| **A. HeyGen + fal (zalecany)** | HeyGen w zbliżeniach, Kling Avatar w planie | **≈ 40–45 zł** | używa tego, co już działa w Studiu |
| B. Tylko fal | OmniHuman 1.5 ($0,16/s) wszędzie | ≈ 65 zł | jeden dostawca, droższy ruch ust |
| C. Jeden model całej sceny | Veo 3.1 z dźwiękiem ($0,40/s × 35 s × 2) | ≈ 105 zł | własne głosy modelu ≠ stałe głosy ElevenLabs — **odpada** dla spójności |

### Koszty stałe i jednorazowe

- **Obsada-v1 (raz na sezon):** arkusze 4 postaci (~70 obrazów prób) + 8 klatek
  pokoju (~32 próby) w fal ≈ $15; Voice Design ≈ grosze (płaci się tylko za
  podgląd); 4 talking photo w HeyGen — cena przez API niepotwierdzona
  (źródła zewnętrzne: ok. $1 za sztukę). **Razem ≈ $20–25 ≈ 90 zł.**
- **ElevenLabs:** plan Creator $22/mies. (275 tys. znaków API) wystarcza
  na kilkaset odcinków; licencja komercyjna od planu Starter.
- **HeyGen API:** portfel przedpłacony (od $5), bez abonamentu; Avatar IV
  zużywa saldo za sekundę.
- **fal:** przedpłata na koncie (to samo konto co Finance You).
- **Fly.io:** usługa usypia się bez ruchu — praktycznie 0 zł.
- **Czas człowieka:** 30–60 min na odcinek (przegląd ujęć, siatka kontrolna,
  akceptacja notariusza). To dziś największy koszt, nie API.

**Sezon 1 (6 odcinków w 9:16): ≈ 6 × 43 zł + 90 zł ≈ 350 zł** za
generowanie, plus abonament ElevenLabs. Wersje 16:9 i 1:1 to osobny montaż;
według biblii nie są mechanicznym kadrowaniem, więc ujęcia w planie trzeba
wygenerować drugi raz w poziomie — doliczyć ok. +50% na odcinek, jeśli
poziomy format jest potrzebny.

## 6. Co trzeba zrobić, żeby ruszyć

1. **Obsada-v1 (jednorazowo):** arkusze 4 postaci + 6–8 klatek pokoju (fal),
   4 głosy (ElevenLabs Voice Design), 4 talking photo (HeyGen). Akceptacja
   człowieka, zapis identyfikatorów w konfiguracji obsady.
2. ~~Studio: typ zadania „odcinek serii”~~ — **infrastruktura ujęć gotowa** w `finyou` (11.11.2026): `docs/seria-odcinkow.md`, narzędzia MCP `seria_*`; brakuje jeszcze montażu odcinka. Pierwotny opis: typ zadania „odcinek serii” w `finyou` — wejście
   `odcinek.json`, ujęcia renderowane równolegle, każde z własną postacią
   i głosem; reszta (napisy, Remotion/caption-burner, kolejka publikacji) już
   istnieje.
3. **Nagrania ekranów** NotarAI: skrypt Playwright na koncie demo, jeden
   klip na funkcję (przesyłki, kalkulator, AML, wniosek KW, teczka).
   Tryb „Komputerku” nagrywać dopiero z wersji, w której działa.
4. **Pilot:** odcinek 1 w 9:16, przegląd z notariuszem, potem reszta sezonu.
