# TURBO PREMIUM — OPEN-SOURCE WEB ENGINEERING

**Data:** 2026-11-15  
**Zakres:** tworzenie stron, programowalne projektowanie, eksperymentalny rendering, weryfikacja wizualna, warsztat agenta frontendowego.  
**Założenie:** preferencja dla licencji OSI (MIT, Apache-2.0, BSD, AGPL, MPL, Unlicense). Projekty nieoznaczone jako otwarte źródłowo nie należą do podstawowego stosu.

## A. Programowalny design, canvas i design-to-code

| Repo | Licencja | Dlaczego warto | Gotowość/ryzyko |
|---|---|---|---|
| [OpenPencil](https://github.com/open-pencil/open-pencil) | MIT | Programowalny canvas, import/export `.fig`, CLI, MCP, scene graph, 100+ narzędzi projektowych | Rozwijany intensywnie; testować zgodność formatów i wydajność |
| [Puck](https://github.com/puckeditor/puck) | MIT | Pełny edytor drag-and-drop na bazie własnych komponentów React | Stabilny fundament, własny model danych i publikacji |
| [Puck Skills](https://github.com/puckeditor/skills) | MIT | Gotowe umiejętności agentów dla integracji Puck | Pomocniczy komponent |
| [Puck Configs](https://github.com/puckeditor/puck-configs) | sprawdzić dla konkretnej paczki | Przykłady integracji z bibliotekami UI | Repo referencyjne |
| [Design Extract / designlang](https://github.com/Manavarya09/design-extract) | MIT | Pobieranie design tokens, typografii, layoutu, motion; MCP; porównanie fidelity | Dużo deklarowanych możliwości; wymagana reprodukcja benchmarków |
| [Mirrorframe](https://github.com/byte271/mirrorframe) | MIT | Rekonstrukcja DOM i stanów interakcji na podstawie działającej strony, pixel-diff per element | Wersja 0.x; nie rekonstruuje interaktywnych canvasów/WebGL |
| [Open CoDesign](https://github.com/OpenCoworkAI/open-codesign) | MIT | Lokalne środowisko generatywnego designu, BYOK, wielu dostawców modeli | Młodszy produkt; sandbox i uprawnienia do przeglądu |
| [Kimo](https://github.com/Saudade-media/kimo) | MIT | Git-native design canvas, pliki `.kimo` jako JSON, MCP, deterministyczny eksport React/HTML | Eksperyment; ocena jakości renderingu przed adopcją |
| [Craft.js](https://github.com/prevwong/craft.js) | MIT | Elastyczny framework do własnych wizualnych edytorów React | Alternatywa dla Puck, nie integrować obu bez potrzeby |
| [GrapesJS](https://github.com/GrapesJS/grapesjs) | BSD-3-Clause | Silnik edycji HTML/stron/newsletterów | SDK Studio jest odrębną ofertą, nie mylić z core |
| [Plasmic](https://github.com/plasmicapp/plasmic) | MIT poza `platform/`, AGPL w `platform/` | Pełny edytor i runtime wizualny | Komplikacja licencyjna przy forku platformy |
| [Builder.io Mitosis](https://github.com/BuilderIO/mitosis) | zweryfikować manifest przed kopiowaniem | Kod komponentów kompilowany do wielu frameworków | Opcjonalnie, gdy rzeczywiście potrzebna wieloframeworkowość |

## B. Silniki doświadczeń premium: WebGL / WebGPU / 3D

| Repo | Licencja | Dlaczego warto | Gotowość/ryzyko |
|---|---|---|---|
| [gpu-curtains](https://github.com/martinlaxenaire/gpu-curtains) | MIT | Łączenie DOM z WebGPU i WGSL, geometry/compute/particles | WIP; wymagany fallback dla przeglądarek bez WebGPU |
| [curtains.js](https://github.com/martinlaxenaire/curtainsjs) | MIT | Responsywne obrazy i wideo DOM → WebGL teksturowane płaszczyzny | Dobry fallback do shaderów 2D |
| [OGL](https://github.com/oframe/ogl) | Unlicense | Minimalne API WebGL, niewielki narzut, własne shadery | Wymaga umiejętności graficznych |
| [React Three Fiber](https://github.com/pmndrs/react-three-fiber) | MIT | Integracja scen Three.js z komponentami React | Dojrzały, pilnować wersji React/R3F |
| [react-postprocessing](https://github.com/pmndrs/react-postprocessing) | MIT | Wrapper efektów postprocessingu dla R3F | Zależny od Three/postprocessing |
| [postprocessing](https://github.com/pmndrs/postprocessing) | Zlib | Bloom, DoF, glitch, SSAO, color grading i autorskie passy | Pilnować budżetu GPU |
| [Spark — Gaussian Splatting](https://github.com/sparkjsdev/spark) | MIT | Photorealistic 3D Gaussian splats w Three.js, edycja i animacja | Nowy rodzaj assetów 3D, kontrola wagi i pamięci |
| [uikit](https://github.com/pmndrs/uikit) | sprawdzić licencję na poziomie wybranego pakietu | Layout i elementy UI w przestrzeni 3D/XR | Tylko gdy faktycznie potrzebna przestrzenna nawigacja |
| [Theatre.js](https://github.com/theatre-js/theatre) | `@theatre/core`: Apache-2.0, `@theatre/studio`: AGPL-3.0 | Wizualna choreografia animacji, oś czasu, 3D, mikrointerakcje | Rozdzielić zależności runtime i edytora |
| [Motion Primitives](https://github.com/ibelick/motion-primitives) | MIT | Komponenty React dla subtelnych animacji klasy premium | Projekt beta; wybierać komponenty punktowo |
| [Opus Motion Library](https://github.com/GovinduSasanka/opus-motion-library) | MIT | Parametryzowane animacje React/Remotion, przydatne w sekcjach promocyjnych i video | Duży katalog, nie importować wszystkiego |
| [SVGR](https://github.com/gregberge/svgr) | MIT | Transformacja własnych SVG do komponentów React | Narzędzie produkcyjne |

## C. Design systems i odporne komponenty

| Repo | Licencja | Dlaczego warto |
|---|---|---|
| [Ark UI](https://github.com/chakra-ui/ark) | sprawdzić manifest konkretnej wersji | Bez stylu; fundament własnych dostępnych komponentów |
| [Zag.js](https://github.com/chakra-ui/zag) | MIT | Maszyny stanów dla rozbudowanych interakcji (menu, modal, select itd.) |
| [React Aria Components](https://github.com/adobe/react-spectrum) | Apache-2.0 | Ponad 50 dostępnych wzorców i bogate wsparcie klawiatury/AT/i18n |
| [Headless UI](https://github.com/tailwindlabs/headlessui) | MIT | Niezależne od wyglądu komponenty React/Vue |
| [Fumadocs](https://github.com/fuma-nama/fumadocs) | MIT | System dokumentacji i portali pomocy, docs, search |
| [next-intl](https://github.com/amannn/next-intl) | MIT | Lokalizacja aplikacji Next.js, poprawna obsługa dat/liczb i języków |
| [VoltAgent Awesome DESIGN.md](https://github.com/VoltAgent/awesome-design-md) | MIT repozytorium; licencje nazw/assetów osobno | Katalog analiz języka wizualnego innych firm; inspiracje, nie kopiowanie tożsamości |

## D. Agenci wizualni, deterministyczna QA, CI

| Repo | Licencja | Dlaczego warto | Ryzyko |
|---|---|---|---|
| [UX/UI Agent Skills](https://github.com/plugin87/ux-ui-agent-skills) | MIT | System reguł projektowych i deklarowane 52 testy, 34 używają przeglądarki | Przeprowadzić własny eksperyment, nie ufać samej liczbie testów |
| [ui-review-agent](https://github.com/MartinCastroAlvarez/ui-review-agent) | MIT | Lokalny crawler QA: viewporty, kontrast, axe, piksele i opcjonalny Ollama/VLM | Mała baza użytkowników; przed wdrożeniem hardening |
| [Argos](https://github.com/argos-ci/argos) | MIT | Open source platforma weryfikacji regresji screenshotów, przegląd zmian | Self-host wymaga serwera i storage |
| [Storybook Addon VIS](https://github.com/repobuddy/visual-testing) | sprawdzić manifest | Snapshoty komponentów Storybook w CI | Kompatybilność wersji Storybook/Vitest |
| [web-vitals](https://github.com/GoogleChrome/web-vitals) | Apache-2.0 | Prawdziwy pomiar LCP, CLS, INP od użytkowników | Pomiar to nie narzędzie optymalizacji |
| [Playwright](https://github.com/microsoft/playwright) | Apache-2.0 | Podstawa powtarzalnych testów interakcji i renderingu | Rzeczywiste testy + izolowane środowiska |

## E. Licencje, których nie wolno pomylić

- **[LYGIA](https://github.com/patriciogonzalezvivo/lygia)**: bardzo wartościowa biblioteka shaderów, ale Prosperity/Patron, nie standardowa bezwarunkowa licencja OSI; komercyjna integracja wymaga weryfikacji uprawnień. Polecana do nauki idei, nie jako dowolny komponent produkcyjny.
- **[VisualLens](https://github.com/b0ir/visual-lens)**: Elastic License 2.0, source-available, a nie OSI open source. Ograniczenia m.in. hostowanej usługi.
- **[Theatre.js](https://github.com/theatre-js/theatre)**: różna licencja w core i studio; nie przenosić AGPL Studio bez analizy obowiązków.
- **[Plasmic](https://github.com/plasmicapp/plasmic)**: pliki poza `platform/` pod MIT; `platform/` pod AGPL.
- **[Doop](https://github.com/kgoedecke/doop)**: AGPL-3.0, mimo że prawdziwy open source. Integracje Figma/Canva i niektóre funkcje są wyłącznie cloud.
- **Assety wzorcowych marek**: otwartość repo nie oznacza prawa do ponownego użycia logo, fontu, zdjęcia czy indywidualnego layoutu obcej firmy.

## F. Architektura do eksperymentów: WEB FACTORY 2.0

1. **Design Genome:** normalizacja design tokens (DTCG), paleta, typografia, spacing, media, reguły UX; analizy Design Extract oraz własne brand specs.
2. **Canvas:** OpenPencil do scen i makiet, osobny edytor Puck dla produkcyjnych stron z komponentów.
3. **UI Engine:** design tokens + React Aria/Zag.js + biblioteka własnych komponentów opisana w Storybook.
4. **Motion Engine:** Motion Primitives, Theatre.js (ze ścisłym rozdzieleniem licencji), efekty WebGPU jako odseparowane moduły lazy-load.
5. **Render & QA:** Playwright, Argos, web-vitals, a11y, agentowy krytyk tylko do propozycji jakościowych; błędy deterministyczne mają pierwszeństwo.
6. **Evaluation:** desktop/mobile, light/dark, keyboard-only, reduced-motion, slow network, budget GPU/CPU, fideliity do zaakceptowanego projektu. Każda zmiana ma screenshoty oraz porównanie baseline.
7. **Security:** przeglądarka na izolowanych danych testowych, brak kluczy produkcyjnych w sesji generowania UI; prompt injection z oglądanych stron traktować jako dane; nie instalować automatycznie cudzych skilli po ich treści bez przeglądu kodu.

### Proponowany próg przyjęcia biblioteki

Licencja OSI i zgodność komercyjna; kod źródłowy i wydania; stan utrzymania; build/test; bezpieczeństwo zależności; bundle size; działanie na mobile; dostępność; izolacja i łatwość usunięcia. Dla bardzo młodych projektów wymagany samodzielny spike i weryfikacja utrzymywalności.

### Najciekawsze trzy pierwsze prototypy

- **Prototyp 1 — Living Design System:** OpenPencil -> DTCG -> React Aria/Zag -> Storybook -> Argos. Agent może zarówno projektować, jak i stale wykrywać rozjazd wyglądu.
- **Prototyp 2 — Premium Landing:** Puck + Motion Primitives + opcjonalny curtains.js / gpu-curtains; wszystko za feature flagą z fallbackiem do statycznego HTML i ograniczeniem ruchu.
- **Prototyp 3 — UI Reverse Engineering Lab:** Design Extract + Mirrorframe + screenshot diff, porównania autorskich wzorców i projektów, bez kopiowania cudzych zasobów.

**Uwaga:** To jest zweryfikowany przegląd publicznych deklaracji repozytoriów i licencji, nie raport po samodzielnym zbudowaniu i przetestowaniu każdego projektu w kodzie. Przed instalacją sprawdzić konkretne wersje, wszystkie pliki LICENSE i zależności.