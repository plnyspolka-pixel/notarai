# A/B: głosy v1 vs v2, odc. 1 (u1–u4)

Pliki do odsłuchu (ten katalog):

| | Plik | Długość | Co to jest |
|---|---|---|---|
| **A** | `A_stare_v1_scena.mp3` | 14,4 s | ścieżka z obecnych ujęć HeyGen (głosy v1, każda kwestia osobno, bez tła) |
| **B1** | `B_nowe_v2_w1_scena.mp3` | 16,9 s | głosy v2, cała scena jednym Text to Dialogue (eleven_v3, seed 23), z ambience; **wariant wybrany do renderu** |
| **B2** | `B_nowe_v2_w2_scena.mp3` | 19,3 s | to samo na eleven_v4 (seed 11), wolniej, dłuższe pauzy |

Pojedyncze kwestie: `stare/u1–u4.mp3`, `nowe_w1/`, `nowe_w2/`.
Kopie w Storage (publiczne linki):
- dialog B1: https://vkzndnaoxhdxrxlpntcb.supabase.co/storage/v1/object/public/studio-media/mcp/api/2026-11/v1-text-to-dialogue-fa536e89.mp3
- dialog B2: https://vkzndnaoxhdxrxlpntcb.supabase.co/storage/v1/object/public/studio-media/mcp/api/2026-11/v1-text-to-dialogue-0c5aa8f8.mp3
- ambience: https://vkzndnaoxhdxrxlpntcb.supabase.co/storage/v1/object/public/studio-media/mcp/sfx/2026-11/quiet-small-law-office-room-to-3c3a4227.mp3

## Różnice (zmierzone; odsłuch należy do właściciela)

| Kwestia | v1 (A) | v2 wariant 1 (B1) |
|---|---|---|
| u1 Basia | Scribe zapisał jednym ciągiem: „…nadawczej ręcznie”. Brak pauzy przed puentą, czytanie listy. | „…nadawczej.” **[0,76 s]** „Ręcznie.” Puenta podana sucho, osobnym zdaniem. |
| u2 Kuba | 2,5 s, jednym tchem. | „a gdyby tak…” **[0,78 s]** „poprosić komputer?” Pauza i wahanie przed propozycją, jak w reżyserii. |
| u3 Basia | Zaczyna od razu od „Kubusiu”. | Najpierw krótkie **westchnienie** (`[sighs]`), potem „Kubusiu.” z pauzą 0,56 s przed resztą. Reakcja na Kubę, nie osobne czytanie. |
| u4 Marta | 3,7 s, neutralnie. | 3,4 s, szybciej i rzeczowo (f0 ok. 240 Hz, wyraźna intonacja opadająca w komendzie). |
| Całość | 4 osobne nagrania bez wspólnej przestrzeni; każde zaczyna „od zera”. | Jedno nagranie sceny: wspólna akustyka, przejścia między mówcami, cichy room tone pod spodem. |

Transkrypcja Scribe nowych kwestii zgadza się 1:1 ze scenariuszem (wariant 1). W wariancie 2 Scribe usłyszał „Pani **Bosiu**”, co jest kolejnym powodem, żeby renderować wariant 1.

Uczciwie: statystyki samej wysokości dźwięku (odchylenie f0) v1 i v2 są podobne, 4–9 półtonów na kwestię. Różnica nie polega na „bardziej śpiewnym” głosie, tylko na **grze**:
- pauzy w miejscach puent;
- westchnienie;
- reakcja na poprzednią kwestię;
- tempo różne dla każdej postaci;
- wspólna akustyka.

Wybór zrobiono na podstawie pomiarów i transkrypcji. Ostateczna ocena należy do ucha: posłuchaj A i B1 jedno po drugim.

## Koszt

- ElevenLabs: 8 serii Voice Design (24 podglądy), 3 dialogi, 1 efekt dźwiękowy. Wszystko mieści się w limicie znaków planu Creator: przed pracą zużyte było 10 tys. z 697 tys., a cała praca to kilka tysięcy znaków.
- HeyGen: 4 rendery, razem ok. 17 s audio.
