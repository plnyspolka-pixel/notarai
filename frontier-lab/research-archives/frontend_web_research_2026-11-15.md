# WEB FACTORY — research repozytoriów i architektura agentów frontendowych
Data: 2026-11-15
Przeznaczenie: Claude Code / Codex / agenci kodujący / lokalne LLM
Zakres: budowanie witryn, aplikacji webowych, paneli, UX/UI, efekty premium, testy i eksperymenty.

## Główna teza
Jeden model nie zastępuje specjalistycznego warsztatu: agent projektant (reguły i inspiracje), agent implementator (komponenty, framework), agent wizualny (browser screenshot i porównanie), agent QA (testy, audyty), agent badawczy (pomiary, benchmarki).

## 1. Skille / inteligencja designu
| Repozytorium | Funkcja | Priorytet |
|---|---|---|
| https://github.com/anthropics/claude-code/tree/main/plugins/frontend-design | Oficjalny skill estetyki frontendu, zapobieganie szablonowym projektom | P0 |
| https://github.com/nextlevelbuilder/ui-ux-pro-max-skill | Baza stylów, palet, fontów i wytycznych UX dla agenta | P0 |
| https://github.com/vercel-labs/agent-skills | web-design-guidelines i react-best-practices: audyt UX, dostępności, perf. | P0 |
| https://github.com/anthropics/skills/tree/main/skills/webapp-testing | Gotowa metodologia testów aplikacji lokalnych | P0 |
| https://github.com/motiondivision/ai-kit | Skill i MCP dla animacji Motion | P1 |

## 2. Edytory wizualne, design to code, generacja UI
| Repozytorium | Funkcja | Priorytet |
|---|---|---|
| https://github.com/onlook-dev/onlook | Edytor wizualny na działającym kodzie, branching, AI | P0 |
| https://github.com/penpot/penpot | Self-hostable projektowanie, design tokens, komponenty, MCP | P1 |
| https://github.com/figma/mcp-server-guide | Oficjalne workflowy Figma MCP; usługa limitowana i nie jest w pełni OSS | P1 |
| https://github.com/GLips/Figma-Context-MCP | Uproszczony kontekst projektu Figma do agenta | P1 |
| https://github.com/abi/screenshot-to-code | Screenshot, Figma, nagranie interfejsu -> prototyp kodu; wymaga API LLM | P1 |
| https://github.com/stackblitz-labs/bolt.diy | Pełny workspace AI do web app, własni dostawcy modeli; warunki WebContainers | P2 |
| https://github.com/21st-dev/magic-mcp | 21st MCP: komponenty i inspiracje; generowanie zależy od planu | P1 |
| https://github.com/notsointresting/frontend-inspo-mcp | Agregator źródeł komponentów, design tokens, shaderów, wzorców | P1 — eksperymentalny |

## 3. Komponenty i zaawansowany interfejs
| Repozytorium | Funkcja | Priorytet |
|---|---|---|
| https://github.com/shadcn-ui/ui | Komponenty i rejestry; dystrybucja własnych presetów i skilli | P0 |
| https://github.com/DavidHDev/react-bits | Animowane komponenty, tła, efekty i MCP | P1 |
| https://github.com/magicuidesign/magicui | Przeprojektowane komponenty i microinteractions | P1 |
| https://github.com/magicuidesign/mcp | MCP do katalogu Magic UI | P1 |
| https://github.com/motiondivision/motion | Animacje i gesty, transitions, scroll; skill/MCP | P1 |
| https://github.com/darkroomengineering/lenis | Smooth scroll i synchronizacja z WebGL | P2 |
| https://github.com/pmndrs/react-three-fiber | Grafika 3D w React | P2 |
| https://github.com/pmndrs/drei | Gotowe abstrakcje 3D dla React Three Fiber | P2 |
| https://github.com/theatre-js/theatre | Animacje scen i choreografia; repo przeniosło aktywny rozwój do prywatnego repo, studio ma AGPL | P3 |
| https://github.com/xyflow/xyflow | Edytory grafów i workflowy w React/Svelte | P1 |
| https://github.com/tldraw/tldraw | Infinite canvas i wizualne diagramy; sprawdzić licencję SDK | P2 |
| https://github.com/konvajs/react-konva | Edytory 2D, adnotacje, canvasy | P2 |
| https://github.com/BuilderIO/mitosis | Komponenty pisane raz i kompilowane do wielu frameworków | P3 |
| https://github.com/withastro/astro | Lekki frontend dla stron content-first | P1 — nowe projekty marketingowe |

## 4. Agent w przeglądarce i weryfikacja
| Repozytorium | Funkcja | Priorytet |
|---|---|---|
| https://github.com/vercel-labs/agent-browser | CLI/MCP do nawigowania i testowania stron przez agentów | P0 |
| https://github.com/microsoft/playwright | Deterministyczne testy, screenshoty, accessibility; Playwright MCP | P0 |
| https://github.com/ChromeDevTools/chrome-devtools-mcp | DevTools: błędy, network, trace, performance, debugging | P0 |
| https://github.com/web-infra-dev/midscene | Wizualny agent testowy; asercje językiem naturalnym | P1 |
| https://github.com/browserbase/stagehand | AI act/extract/observe + deterministyczny browser automation | P2 |
| https://github.com/unclecode/crawl4ai | Pobieranie treści, struktury i metadanych stron; aktualizować, sandboxować | P2 |
| https://github.com/rrweb-io/rrweb | Rekonstrukcja rzeczywistych sesji użytkowników, replay | P2 |
| https://github.com/openreplay/openreplay | Samodzielnie hostowane sesje i debugging użytkownika | P2 |

## 5. Jakość i CI
| Repozytorium | Funkcja | Priorytet |
|---|---|---|
| https://github.com/dequelabs/axe-core | Automatyczny accessibility testing | P0 |
| https://github.com/dequelabs/axe-accessibility | Skill/plug-in dla agentowego audytu a11y | P1; zależne od usługi/kluczy |
| https://github.com/pa11y/pa11y-ci | Audyt dostępności w CI, także sitemap i formularze | P1 |
| https://github.com/GoogleChrome/lighthouse-ci | Automatyczne budżety wydajności, SEO, accessibility | P0 |
| https://github.com/storybookjs/storybook | Katalog i testy stanów komponentów | P1 |
| https://github.com/lost-pixel/lost-pixel | Visual diff, ALE ARCHIWUM od 2026-04-22 — nie wdrażać jako nowej zależności | Nie rekomendowane |

## 6. Zaawansowane laboratorium / nauka modeli
| Repozytorium / dataset | Funkcja | Priorytet |
|---|---|---|
| https://github.com/NoviScl/Design2Code | Benchmark screenshot -> HTML z metrykami jakości, hard-set | P1 eksperymenty |
| https://huggingface.co/datasets/HuggingFaceM4/WebSight | Duży zbiór par screenshot + HTML/CSS/Tailwind | P2; uwzględnić podziały i licencję |
| https://github.com/microsoft/OmniParser | Wydobywanie struktury elementów ze screenshotu | P2 |
| https://github.com/ServiceNow/BrowserGym | Zestaw benchmarków zadań przeglądarkowych, m.in. VisualWebArena | P2 |
| https://github.com/ServiceNow/AgentLab | Równoległe testowanie wariantów agenta, porównywanie wyników | P2 |
| https://github.com/bytedance/UI-TARS | Modele vision-language do interakcji z GUI | P3 |
| https://github.com/bytedance/UI-TARS-desktop | TYLKO materiał archiwalny; repo archiwizowane 2026-11-09 | Nie rekomendowane jako baza |

## 7. Architektura proponowana dla obecnych aplikacji
1. Odczytaj strukturę istniejącego repo, lockfile, framework, routing, style, komponenty i aktualną semantykę UI.
2. Zapisz niezmienne kontrakty i granice bezpieczeństwa: formularze, auth, API, ACL, dane poufne, role.
3. Projektant (frontend-design + ui-ux-pro-max + web-design-guidelines) przygotowuje 2–3 kierunki estetyczne i design tokens.
4. Agent implementacji korzysta z istniejących komponentów i ewentualnie prywatnego rejestru shadcn; NIE przebudowuje backendu przy zmianie skinu.
5. Agent wizualny wykonuje lokalny browser run w kilku viewportach; zbiera screenshoty i krytyczne błędy konsoli.
6. Recenzent porównuje snapshoty/wzorce, sprawdza layout, rozmiary, kontrast, stan formularzy i scenariusze klawiaturowe.
7. QA: typecheck, lint, unit/integration/e2e, a11y, Lighthouse CI oraz testy autoryzacji.
8. Iteruj tylko na podstawie mierzalnej listy usterek; wydaj wersję do osobnej gałęzi i PR. NIE merguj ani deployuj do produkcji bez zgody.

### Proponowane agenty
- **DESIGN_DIRECTOR**: brand system, kontrast, hierarchia, propozycje UI.
- **COMPONENT_CURATOR**: pobieranie legalnych, zgodnych komponentów, kontrola zależności.
- **FRONTEND_IMPLEMENTER**: integracja bez naruszenia logiki biznesowej.
- **BROWSER_REVIEWER**: testy ścieżek użytkownika, screenshoty, ocena jakości.
- **PERFORMANCE_GUARD**: Core Web Vitals i ograniczenia bundle.
- **SECURITY_GUARD**: auth, RBAC, no secret leaks, CSP, origin, supply-chain.
- **EXPERIMENT_RUNNER**: warianty projektu i porównania według powtarzalnych metryk.

### Rozdział projektów
- **NotarAI**: Priorytet panelu kancelarii, kontekstu/organizacji spraw, gęstości informacji, czytelności i dostępności. 3D i dekoracja tylko na marketingu. Nigdy nie ujawniaj treści akt ani danych klientów do niezaufanych zewnętrznych narzędzi.
- **Finance You**: Form flow, zrozumiałe CTA, stabilne walidacje, prędkość, wersje mobile. Zachowaj istniejącą kontrolę dostępu do projektów i separację inwestorów; żadne zmiany UI nie omijają ACL.

## 8. Test akceptacji agenta webowego
- Desktop 1440px, tablet 768px, mobile 390px, mobile 320px: bez poziomego scrolla lub obciętych kontrolek.
- Dla każdej ścieżki: puste dane, błędne dane, loading, success, error, brak uprawnień, powrót.
- Zero nieobsłużonych błędów JS i żądań niezgodnych z kontraktem API.
- Przeprowadź automatyczny a11y test; sprawdź manualnie keyboard focus, modal i screen reader w krytycznych flow.
- Lighthouse wyniki traktuj jako metrykę trendu, nie jeden absolutny warunek; w PR raportuj delty i uzasadnienie.
- Screenshoty i porównania zapisuj jako artefakty testu, bez niezamaskowanych danych użytkowników.
- Każda zmiana z opisem i rollbackiem, dopiero po review merge/deploy.

## 9. Prompt do Claude Code
> Zbuduj system WEB FACTORY w istniejącym repo, wyłącznie na nowej gałęzi. Najpierw przeprowadź audyt kodu, architektury UI, auth, roli i API — nie zastępuj ich bez potrzeby. Użyj frontend-design, ui-ux-pro-max, vercel agent-skills, shadcn registry, agent-browser/Playwright i Chrome DevTools. Zaproponuj 3 odrębne, profesjonalne koncepcje dla wybranej strony, z tokenami designu, tekstami i kryteriami UX. Implementuj tylko uzgodniony kierunek. Po każdej iteracji renderuj widok na 4 szerokościach, wykonaj testy interakcji, klawiatury, accessibility i Lighthouse. Porównaj screenshoty, wypisz konkretne różnice i popraw je. Zachowaj backend, dostępność, autoryzację, dane i dotychczasowe zachowania. Nie instaluj nieznanych skryptów bez oceny ryzyka; wersjonuj zależności. Nie wysyłaj danych poufnych do usług zewnętrznych. Przygotuj raport, screenshoty, checklistę i PR; nie wykonuj merge ani deploy bez zgody.

## 10. Pułapki
- `Lost Pixel`: repo archiwalne od 22 kwietnia 2026; nadaje się jako inspiracja, nie fundament.
- `UI-TARS-desktop`: repo archiwalne od 9 listopada 2026; rozważyć tylko kod/model, nie aktywną zależność.
- `Theatre.js`: aktualne prace przeniesione czasowo do prywatnego repo; osobne licencje core/studio.
- `bolt.diy`: kod MIT, ale produkcyjna komercyjna eksploatacja WebContainers API może wymagać licencji.
- `21st MCP`: zewnętrzny klucz, dostęp do generacji AI uzależniony od konta/planu.
- `Figma MCP`: limity korzystania zależne od planu i uprawnień.
- `Crawl4AI`: historia krytycznych advisory; wyłącznie bieżąca, zweryfikowana wersja, sandbox, whitelist domen.
- Cudzych stron nie kopiować wprost wraz z tekstami/assetami/brandem — badać mechanikę i wzorce.
- Dane z produkcji: maskowanie screenshotów i sesji, osobna izolacja przeglądarki.

*Wszystkie adresy to publiczne, znalezione repozytoria/projekty. Priorytet jest rekomendacją architektoniczną, nie wynikiem formalnego benchmarku w środowisku użytkownika.*

## 11. Strony marketingowe, CMS, SEO i eksperymenty
| Repozytorium | Funkcja | Priorytet |
|---|---|---|
| https://github.com/payloadcms/payload | Headless CMS zintegrowany z Next.js; strony redagowane poza repo | P1 nowe projekty |
| https://github.com/withastro/starlight | Serwisy dokumentacyjne, help center i wiedza produktowa | P1 |
| https://github.com/growthbook/growthbook | A/B, feature flags, metryki, odwracalne rollouty | P1 po zbudowaniu podstaw |
| https://github.com/growthbook/skills | Skille agentowe dla planowania i analizy eksperymentów | P1 |
| https://github.com/nuxt-modules/robots | Kontrola robots/indexacji dla witryn na Nuxt | P2 tylko Nuxt |
| https://github.com/nuxt-modules/sitemap | Sitemapy dla Nuxt | P2 tylko Nuxt |

**Uwaga:** wdrożenie nowych CMS i frameworków do już działającego repo może być kosztowniejsze i mniej bezpieczne niż użycie obecnej architektury. W pierwszym etapie podłącz skille, MCP, kontrolę jakości i bibliotekę komponentów, a nie framework-rewrite.