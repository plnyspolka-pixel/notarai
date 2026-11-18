# Audyt produkcji kampanii „Komputerku…” — 13.11.2026
Status: weryfikacja repozytorium, **nie ocena wizualna renderów**. Repozytorium: \`plnyspolka-pixel/notarai\`, gałąź \`master\`.

## Co rzeczywiście odnaleziono
- **Scenografia v2:** jeden opis pomieszczenia \`pakiet/09_scenografia_v2/scenografia.json\`, 9 kamer K1–K9, plany i gotowe statyczne referencje. Nie zmieniać wnętrza dla nowej estetyki thrillera; dobudować zewnętrzne lokacje.
- **Obsada v2:** Helena (K2), Marta (K5), Basia (K3), Kuba (K6); każda ma kartę postaci, referencje, zaakceptowany kadr, głos v2 ElevenLabs i awatar HeyGen. Źródło: \`KANCELARIA_I_POSTACIE.md\`.
- **Głosy:** poprzednie v1 i nowe v2, testy A/B \`glosy_v2/PORÓWNANIE.md\`. Dla spójności zachować v2; nie wracać do v1.
- **Wideo:** podglądy \`podglady/odc1_podglad_u1-u5.mp4\`, \`odc1_podglad_v2.mp4\` i \`odc1_podglad_v3.mp4\`, klip \`u5_ekran_komputerku_1080x1920.mp4\`, ponadto 11 krótkich porównań awatarów u3. W repo **nie ma dowodu ukończenia finalnego filmu sezonu 1**, ani gotowych 8 odcinków.
- **Materiały:** referencyjne plansze 9:16/1:1/16:9, znaki marki, elementy UI, mapy scenograficzne, prompty i skrypty montażowe. \`README.md\` oraz \`narzedzia/\`.
- **Dokumentacja V4:** 8 koncepcji, 72 kontrole autoryzacji i walidator; materiały niezatwierdzone do emisji.

## Ostatnie istotne zmiany
1. **PR #20 (scalony 12.11):** koncepcja V4, scenografia/obsada v2, produkcja wideo i głosów, podglądy.
2. **Commity 12.11, u1–u4:** render Awatar 6 Turbo i \`motion_prompt\`, nowe głosy i składanka \`odc1_podglad_v3.mp4\`.
3. **PR #22 (scalony 12.11, ostatni commit master \`d60b36a67e3f\`):** kalendarz → sprawa, teczka na telefonie, odświeżanie załączników, projekt w tle, pola BRAK/WYBOR także w DOCX, stanowiska zespołu. Udokumentowano \`docs/odcinek-01-luki.md\`, testy podstawowe; brak pełnego testu produkcyjnego Bedrock i dwóch urządzeń na app.notarai.pl.
4. **PR #21 (draft):** niezależna pełna biblia scenariuszy sezonu 1 — dokumentacja nie była jeszcze scalona z \`master\`.
5. **PR #19 (otwarty):** webhooki ElevenLabs dla asystenta obsługującego zapytania klientów / pytania o produkt, **nie potwierdzają** głosowego zarządzania poufnymi sprawami kancelarii z samochodu.
6. **PR #23 (draft):** dokumenty dot. RzPESEL; bez bezpośredniej roli w kampanii.

## Werdykt
Mamy rzeczywistą bibliotekę assetów i **wczesny montaż pierwszych ujęć pilota**, a nie kompletny sezon. Priorytet: utrzymać obsadę i głosy, dołożyć rzeczywiste ujęcia zewnętrzne oraz świadomie wybrać klipy do regeneracji. Żadna zmiana fabularna nie wymaga przerenderowania 9 kamer kancelarii.

## Lista materiałów do ręcznego obejrzenia
- \`podglady/odc1_podglad_v3.mp4\` — aktualny podgląd;
- \`podglady/odc1_podglad_v2.mp4\` — głosy v2;
- \`podglady/odc1_podglad_u1-u5.mp4\` — pierwszy montaż;
- \`podglady/awatary_test/u3_porownanie_siatka.mp4\` — test ruchu postaci;
- \`glosy_v2/B_nowe_v2_w1_scena.mp3\` — głos wybrany do ujęć pilota.

**Uwaga:** niniejszy audyt potwierdza pliki, metadane i dokumentację. Nie odtwarzano tu plików wideo, zatem nie wydajemy subiektywnej oceny jakości mimiki/lipsync. Zmiany należy skonfrontować z rzeczywistym podglądem przed dalszą produkcją.
