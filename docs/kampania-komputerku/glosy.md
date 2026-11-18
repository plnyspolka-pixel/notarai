# Głosy serii „Komputerku…” — przepis (obsada głosowa v2)

Stan: 12.11.2026. Konto ElevenLabs Finance You (plan Creator), z którego korzysta aplikacja.
Głosy v1 zostają na koncie bez zmian (pole `elevenlabs_voice_id_odrzucone` w obsadzie).

## 1. Co zmieniliśmy i dlaczego

Głosy v1 brzmiały płasko, „lektorsko”. Miały trzy przyczyny:

1. **Opisy Voice Design były krótkie.** Mówiły „kto” (wiek, zawód), ale nie „jak mówi”: brakowało tempa, pauz, mikroekspresji, akustyki pokoju i zakazu tonu lektora.
2. **Głosy wybierano na ślepo.** Za każdym razem brano pierwszy z 3 podglądów, bez odsłuchu i bez kontroli.
3. **Każdą kwestię generowano osobno.** Szła przez HeyGen z domyślnymi ustawieniami, bez kontekstu sceny, więc nie było reakcji, pauz ani westchnień.

W v2:

- **Opisy:** dłuższe, z charakterem mówienia (sekcja 2).
- **Wybór głosu:** 2 serie po 3 podglądy na postać. Każdy podgląd pobrany i zmierzony (tempo, rozpiętość melodii, pauzy), faworyci sprawdzeni transkrypcją Scribe.
- **Scena:** nagrana jednym wywołaniem **Text to Dialogue** z reżyserią w tagach, potem pocięta na kwestie po czasach słów.

## 2. Głosy v2 (Voice Design, model `eleven_ttv_v3`, `guidance_scale: 3`)

Kolumna „Seria” mówi, z której serii opisów pochodzi zwycięzca; w drugiej kolumnie jest numer podglądu (1–3) w tej serii.

| Postać | voice_id | Seria / podgląd | Środek f0 | Tempo podglądu |
|---|---|---|---|---|
| Basia | `vqyfbWoOfYmPoa0QNkKB` | 2 / 2 | ok. 160 Hz (niski alt) | 20,7 s na tekst testowy |
| Kuba | `l49KzmmcER7qYZfvh1NN` | 2 / 2 | ok. 114 Hz | 18,7 s |
| Marta | `rOIbi11t4PdzPrW90No0` | 1 / 1 | ok. 225 Hz | 15,0 s (najszybsza, „rzeczowa”) |
| Helena | `0YMlrD87k6Saqi6L1Joy` | 2 / 2 | ok. 160 Hz | 22,9 s (spokojna) |

Nazwy na koncie: „NotarAI Komputerku v2 - <Imię>”. Etykiety: `seria=notarai-komputerku-v2`, `postac=<slug>`.
Transkrypcja Scribe podglądów: 4/4 bez błędów (polszczyzna, odmiana, „PEP”, „Unii Lubelskiej”).
Podglądy leżą w `glosy_v2/zrodla/glos_<postac>_v2_podglad.mp3`.

### Opisy (wklejać bez zmian)

**Basia:** Polish woman in her early fifties, office manager who has seen everything. Native Polish speaker from Warsaw. Low, slightly raspy, lived-in voice with motherly warmth underneath. Sardonic and deadpan: delivers sarcasm quietly, almost under her breath, with long dry pauses and a little exhale before the punchline. Speaks at an easy, measured pace, very natural and spontaneous, like talking to a colleague across a desk, never theatrical or announcer-like. Realistic close microphone in a small quiet office.

**Kuba:** Young Polish man, late twenties, enthusiastic apprentice lawyer, a little awkward and endearing. Bright tenor-baritone with a smile in the voice, slightly breathy. Talks like a real person in an office: fast bursts, filler hesitations, cautious half-whisper when he proposes something cheeky, then hopeful upward lift. Native Polish, no foreign accent, no radio voice. Natural room tone of a quiet office, close mic.

**Marta:** Native Polish woman, 38, modern notary. Clear, confident mid-range voice, warm and friendly but decisive. Speaks briskly with crisp diction and firm falling intonation at the end of commands, like someone used to being in charge; light smile in the voice, no drama. Natural, conversational, not a commercial voice-over. Standard Polish accent. Close microphone in a quiet office, dry, intimate.

**Helena:** Polish woman in her mid fifties, distinguished head of a notary office, kind but firm. Deep, slightly smoky mature voice, composed and reassuring, speaks slowly and deliberately with thoughtful pauses, gentle downward cadence. Occasionally a dry, teasing remark said completely deadpan. Natural spoken Polish of a native speaker, intimate and real, not theatrical, not a voice-over. Close mic, quiet office ambience.

### Zasady pisania opisu (dla nowych postaci)

1. Kolejność: narodowość i wiek → rola → barwa → **sposób mówienia** (tempo, pauzy, intonacja, humor) → zakaz („not a narrator / voice-over / announcer”) → mikrofon i pokój („close mic, quiet small office, dry”).
2. Zawsze „native Polish speaker, no foreign accent”. Bez tego zdarza się obcy akcent.
3. Tekst podglądu ma 100–1000 znaków i składa się z prawdziwych kwestii postaci (z `scenariusze.md`), razem z tagami (`[sighs]`, `...`). Głos dopasowuje się wtedy do roli, nie do „czytania”.
4. `guidance_scale` 3 (v1 szło na domyślnym 5). Dokumentacja ostrzega, że wysokie wartości brzmią robotycznie; 5 nie testowaliśmy osobno.
5. Zawsze 2 serie opisów (różne akcenty charakteru) × 3 podglądy. Każdy podgląd pobierz: `POST /v1/text-to-voice/design` ze `stream_previews: true`, potem `GET /v1/text-to-voice/<generated_voice_id>/stream` (plik trafia do Storage). Przy wyborze patrz na:
   - środek f0, czyli wiek i barwę;
   - odchylenie f0 w półtonach, czyli melodię (powyżej 3,3 st u kobiet to już nie monotonia);
   - pauzy;
   - transkrypcję Scribe, która musi się zgadzać 1:1.

   Na końcu **odsłuch człowieka**.
6. Zapis: `POST /v1/text-to-voice` z polami `voice_name`, `generated_voice_id`, `voice_description`, `labels`.

## 3. Nagrywanie sceny: Text to Dialogue

- Endpoint: `POST /v1/text-to-dialogue?output_format=mp3_44100_192` (192 kb/s jest dostępne na planie Creator).
- Body: `model_id: "eleven_v3"`, `language_code: "pl"`, `settings: {stability: 0.5}`, stały `seed` (do powtórek), `inputs: [{voice_id, text}, …]`. Na jedno wywołanie najwyżej 10 głosów i ok. 2000 znaków.
- Cała scena idzie **jednym** wywołaniem. Model słyszy poprzednią kwestię, więc reakcje (westchnienie, ton odpowiedzi) wynikają z kontekstu.
- Wersja `with-timestamps` zwraca audio w base64 i przez konektor jest za duża. Czasy bierzemy z transkrypcji: `speech_to_text` z `diarize=true` zwraca słowa z czasami i mówcą.
- Kroję w `narzedzia/glosy_v2_tnij.sh`:
  - cięcia wypadają w ciszy między kwestiami;
  - przed westchnieniem zostaje ok. 0,1 s zapasu;
  - na początku i końcu jest krótki fade, żeby nie było trzasków;
  - nagranie zapisuje się w 48 kHz mono.

### Reżyseria w tagach (eleven_v3)

Tagi piszemy po angielsku w nawiasach kwadratowych, a tekst po polsku. Zasady:

- **Jeden lub dwa tagi na zdanie.** Opisują stan („[tired, dry]”, „[deadpan]”, „[hesitant, shy]”, „[confident, matter-of-fact]”), a nie fonetykę.
- **Pauzę** robi `...` albo `[short pause]` przed słowem, które ma wybrzmieć. W v3 `[short pause]` + `...` dawało ok. 0,75 s, a samo `...` niewiele.
- **Dźwięki niewerbalne:** `[sighs]` na początku kwestii działa pewnie (słychać wydech przed „Kubusiu”). Czy `[nervous laugh]` w podglądzie Kuby zadziałał, trzeba sprawdzić uchem; Scribe nie zapisuje śmiechu.
- **Charakter siedzi w głosie, a tag go tylko wyzwala.** Ironia Basi to opis głosu plus `[deadpan]`; nie pisz `[sarcastically]` przy każdym zdaniu.
- **Komenda do komputera** (Marta): `[confident, matter-of-fact]`, bez pauz. Pewność ma być w tempie, a nie w głośności.
- Bez SSML `<break>`: v3/v4 go nie obsługują.

### Ustawienia

| Parametr | Wartość | Uwagi |
|---|---|---|
| model | `eleven_v3` | v4 (wariant 2) dał wolniejszą, bardziej „aktorską” scenę (+2,4 s) i w transkrypcji wyszło „Pani Bosiu”; v3 trzyma tempo serii |
| stability | 0.5 (Natural) | według dokumentacji niższa wartość daje szerszy zakres emocji kosztem stabilności; niższych wartości jeszcze nie testowaliśmy |
| similarity | 0.75 (domyślne) | |
| style / speed | nie dotyczy | Text to Dialogue ich nie przyjmuje; tempo reżyserujemy tekstem i pauzami |
| seed | stały per scena (odc. 1: 23) | zapisz seed obok sceny |

## 4. Dźwięk: ambience

- Jeden podkład na serię: `glosy_v2/zrodla/ambience_kancelaria_22s.mp3`. Ma 22 s i jest robiony przez `generate_sound_effect`, `prompt_influence 0.5`. Opis: „Quiet small law office room tone: soft air conditioning hum, very distant city traffic behind closed window, occasional faint paper rustle and a quiet pen click, an old office printer softly whirring in the background. Calm, no voices, no music.”
- Poziom: plik ma średnio −38,6 dB, w miksie `volume=0.55`. Ma być ledwo słyszalny i wypełniać ciszę między cięciami.
- Do HeyGen idzie **czysta mowa**, bo synchronizacja ust jest lepsza bez tła. Ambience kładziemy dopiero w montażu, pod całą scenę z postaciami (u1–u4), z fade.
- Normalizacja całości: `loudnorm I=-16 TP=-1.5` (format social).

## 5. Odcinek 1: wynik

- Wariant 1 (render): `glosy_v2/zrodla/dialog_w1_v3_seed23.mp3`, kwestie w `glosy_v2/nowe_w1/`.
- Wariant 2 (zapas, v4): `glosy_v2/zrodla/dialog_w2_v4_seed11.mp3`, kwestie w `glosy_v2/nowe_w2/`.
- Próba A (`dialog_proba_A_v3_seed11.mp3`) odrzucona. Kuba nie zrobił pauzy przed „poprosić”, a Scribe usłyszał „Herbusiu” zamiast „Kubusiu”.
- Porównanie A/B (do odsłuchu): `glosy_v2/A_stare_v1_scena.mp3` vs `glosy_v2/B_nowe_v2_w1_scena.mp3` (oraz `B_nowe_v2_w2_scena.mp3`). Opis różnic jest w `glosy_v2/PORÓWNANIE.md`.

## 6. Checklista na kolejny odcinek

1. Kwestie z `scenariusze.md`, dopisane tagi według sekcji 3; jedna scena to jedno wywołanie Text to Dialogue (v3, stability 0.5, seed zapisany).
2. Transkrypcja z `diarize=true`. Sprawdź, czy tekst zgadza się 1:1 (imiona!) i czy pauzy są tam, gdzie miały być. Jeśli nie, zmień seed albo tag, a nie głos.
3. Cięcie według czasów słów (wzór w `narzedzia/glosy_v2_tnij.sh`), potem HeyGen z `audio_url` (czysta mowa, `captions=off`).
4. W montażu ambience pod ujęcia z postaciami i `loudnorm`.
5. Głosy zmieniamy tylko jako nową wersję obsady (v3). Opisy z sekcji 2 są kanonem.
