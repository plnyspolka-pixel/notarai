# WEB FACTORY — BIG TECH RESEARCH LAB
**Research memo | 15 listopada 2026 | Google/DeepMind, Microsoft, Apple, Amazon, Meta, NVIDIA, Wix**

## Założenia

Celem nie jest kolejny generator landing page'y, lecz agentowy system wytwarzania i oceniania interfejsów (React/TanStack/TypeScript), który: rozumie screenshot, DOM i drzewo dostępności; tworzy celowane patche; odkrywa i testuje interakcje; zbiera powtarzalne metryki; działa w izolacji; publikuje zmianę tylko po odrębnej autoryzacji. Badania są odrębne od produktów wdrożonych w kodzie. Wyniki benchmarków pochodzą z eksperymentów autorów, nie są gwarancją osiągnięcia ich w NotarAI / Finance You.

**Hierarchia dowodów:** (I) recenzowany paper + udostępniony kod; (II) paper/preprint + kod; (III) paper bez kodu; (IV) dokumentacja produktu lub blog badawczy. Uwaga: publiczne repozytorium ≠ automatycznie licencja open source na kod, dane i modele.

## 1. Rekomendacje — priorytet strategiczny

| Priorytet | Wynik badań | Czego się nauczyć / co zrobić | Stan zasobów |
|---|---|---|---|
| P0 | Microsoft Orchard / OpenWebRL | Powtarzalne sandboksy, logi trajektorii, ewaluacje GUI+SWE | Kod MIT, dane i wagi sprawdzić osobno |
| P0 | Apple RL from Designer Feedback | Dopracowany feedback projektanta -> pary before/after + uzasadnienie | Kod publiczny; dataset CC BY-NC-ND i wagi research-only, NIE używać komercyjnie |
| P0 | Apple FlowEval | Porównywać wykonane ścieżki użytkownika, nie wyłącznie końcowe screenshoty | Paper, nie potwierdzono kompletnego repo produkcyjnego |
| P0 | Apple SQUIRE | Zakres edycji jawnie przypięty do konkretnego poddrzewa UI | Paper; implementacja do własnego odtworzenia |
| P0 | Microsoft ActionEngine | Przeglądarka opisana grafem stanów, re-grounding po błędzie | Paper; kod niepotwierdzony |
| P0 | Microsoft WeaveBench / WebStep | Ocena procesu i dowodów, nie tylko sukcesu końcowego | WeaveBench kod publiczny, WebStep paper |
| P0 | Google ScreenAI + Pix2Struct | Przetwarzanie screenshotów w ustrukturyzowane elementy | Pix2Struct Apache-2.0 + checkpointy; ScreenAI osobna praca, dane sprawdzić |
| P0 | Microsoft OmniParser / Phi-Ground | Lokalizacja elementów z obrazu, obsługa gęstych ekranów | OmniParser kod publiczny; licencje wag osobno |
| P0 | Amazon Firecracker / Google gVisor | Izolowanie kodu i automatycznych przeglądarek | Apache-2.0 dla bazowych repo |
| P0 | Cedar for Agents | Polityki autoryzacji niezależne od promptów | Apache-2.0 |
| P1 | Google UniAR | Przewidywanie uwagi użytkownika i kolejności przeglądania | Paper, nie zakładać publicznych wag |
| P1 | Apple Celestial (distinguishing variations) | Generowanie znacząco różnych, realistycznych wariantów komponentu | Paper, kod niepotwierdzony |
| P1 | Apple UICoder | Kompilacja + modele oceny do filtrowania syntetycznych przykładów UI | Paper, licencje ewentualnych zbiorów osobno |
| P1 | Apple Weblica | Migawki HTTP + odtwarzalne interaktywne strony testowe | Paper, publiczny kod niepotwierdzony |
| P1 | Microsoft Hybrid Computer Use / UFO2 | Hybryda AX tree + GUI screenshot + CLI, fallback i wykrywanie nieaktualnych targetów | Publiczny kod, sprawdzić zależności |
| P1 | Wix DLT | Generowanie geometrii układu (obiekty, wielkości, pozycje) | Kod publiczny, osobno sprawdzić licencję |
| P1 | Microsoft LayoutPrompter | Layouty bez fine-tuningu, kontrola overlap / alignment | Repo archiwalne od 09.2026 |
| P1 | Meta Sapienz/SapFix | Inwarianty i automatyczne odkrywanie problemów przez eksplorację interfejsu | Publikacja inżynierska; nie pakiet npm do integracji |
| P1 | Meta StyleX/Lexical | Produkcyjna architektura CSS i dokumentów | Otwarte repo, zgodność ze stackiem ocenić |
| P1 | NVIDIA NeMo Guardrails | Programowalne guardrails (dodatkowa warstwa) | Open source, nie zastępuje Cedar/sandbox |

## 2. Microsoft Research — narzędzia i wyniki

### Orchard / Orchard-GUI (2026)
- [Oficjalne opracowanie](https://www.microsoft.com/en-us/research/blog/orchard-an-open-framework-for-scalable-agentic-ai/)
- [Kod — Orchard-Agentic](https://github.com/microsoft/Orchard-Agentic)
- [Orchard: paper arXiv 2605.15040](https://arxiv.org/abs/2605.15040)
- Model GUI: Qwen3-VL-4B-Thinking; 400 demonstracji + 2200 zadań RL; autorzy podają 68.4% średnio na WebVoyager/Online-Mind2Web/DeepShop (74.1/67.0/64.0). 3,070 udostępnionych trajektorii przeglądarkowych. Podsystem Orchard Env używa sieci deny-egress, limitów zasobów, TTL i sandboksów. **Następny eksperyment:** zestaw 30 zadań na syntetycznej kopii NotarAI, logowane ślady, deterministyczny verifier, pomiar pass@1 i kosztu.

### ActionEngine (2026)
- [Microsoft Research](https://www.microsoft.com/en-us/research/publication/actionengine-from-reactive-to-programmatic-gui-agents-via-state-machine-memory/)
- Zespół Crawling Agent -> State Machine Memory -> Execution Agent. Według autorów 95% sukcesu na Reddit-task subset WebArena kontra 66% baseline, 11.8× redukcji kosztu. Wynik dotyczy wąskiego zestawu zadań. **Eksperyment:** kompilacja ścieżek w wersjonowaną mapę ekranów/akcji, walidacja po każdym kroku, wykrywanie stale element IDs i auto-fallback.

### WeaveBench (2026; EMNLP)
- [Repo](https://github.com/weavebench/WeaveBench)
- [Microsoft paper](https://www.microsoft.com/en-us/research/publication/weavebench-a-long-horizon-real-world-benchmark-for-computer-use-agents-with-hybrid-interfaces/)
- 114 długich, mieszanych zadań GUI + CLI + kod. Najlepszy wynik w badaniu paper 41.2%. Nie wystarcza, że agent napisze „gotowe” — weryfikator inspektuje realne pliki, logi, ślady działań, screenshoty. **Eksperyment:** 30 oryginalnych zadań z obowiązkowym łańcuchem dowodowym: patch SHA -> build -> screenshot -> request/DB test -> raport.

### WebStep / process-level evaluation
- [Microsoft Research](https://www.microsoft.com/en-us/research/publication/where-did-it-go-wrong-process-level-evaluation-of-web-agents-with-semantic-state-tracking/)
- 1,800 kontrolowanych instancji z semantycznym zapisem przejść. Rozdziela błędy eksploracji, wykonania i commit. **Eksperyment:** event log stanów biznesowych (np. „formularz wysłany”, „dokument niezatwierdzony”), nie polegać wyłącznie na modelu oceniającym.

### Microsoft OmniParser / Phi-Ground / UFO2
- [OmniParser repo](https://github.com/microsoft/OmniParser)
- [OmniParser V2 — oficjalny opis](https://www.microsoft.com/en-us/research/articles/omniparser-v2-turning-any-llm-into-a-computer-use-agent/)
- [Phi-Ground](https://www.microsoft.com/en-us/research/articles/phi-ground-improving-how-ai-agents-navigate-screen-interface/)
- [UFO repo](https://github.com/microsoft/UFO)
- [UFO2 paper](https://arxiv.org/abs/2504.14603)
- OmniParser: UI screenshot -> reprezentacja obszarów klikalnych. Phi-Ground: dokładne wskazywanie punktów na ekranie; błędy benchmarkowe nadal istotne. UFO2: HostAgent + AppAgent; API+GUI; screen OCR zamiast DOM fallback, jeśli UIA/AX niedostępne. **Eksperyment:** Browser DOM/AX-first, vision-only fallback, shadow DOM i canvas testy.

### Microsoft LayoutPrompter
- [Paper](https://www.microsoft.com/en-us/research/publication/layoutprompter-awaken-the-design-ability-of-large-language-models/)
- [Kod](https://github.com/microsoft/LayoutGeneration)
- Repo archiwalne od 15.09.2026. Warto wykorzystać wyłącznie jako referencję metod alignment, overlap i content-aware layout, nie przyjmować jako rozwijaną zależność produkcyjną.

## 3. Apple — UI research szczególnie przydatny do premium designu

### Improving UI Generation Models from Designer Feedback (CHI 2026)
- [Apple research](https://machinelearning.apple.com/research/designer-feedback)
- [Kod i modele](https://github.com/apple-aiml-research/ml-rldf)
- 21 projektantów, około 1500 adnotacji (komentarze, szkice, bezpośrednie rewizje). Autorzy porównali RLHF-rankings z feedbackiem zgodnym z pracą projektantów; zgłaszają większą preferencję wyników niż badane baseline w tym GPT-5.
- **KRYTYCZNA KWESTIA LICENCJI:** `LICENSE` dotyczy kodu; `LICENSE_DATA` zawiera ograniczenia NonCommercial/NoDerivatives, a `LICENSE_MODEL` dopuszcza wyłącznie niekomercyjne Research Purposes, z wykluczeniem rozwoju produktu i użycia komercyjnego. Do Web Factory używać koncepcji i samodzielnie wyprodukowanego, licencjonowanego zbioru feedbacku; nie osadzać dostarczonych checkpointów Apple w komercyjnej aplikacji.

### FlowEval (2026)
- [Apple research](https://machinelearning.apple.com/research/floweval-ui-evaluation)
- [arXiv](https://arxiv.org/abs/2605.04165)
- Podobieństwo ścieżek na stronie: trasy referencyjne kontra wygenerowane analogi, metric DTW. Małe badanie użytkowników/ekspertów, silna korelacja z oceną ludzi, nie uniwersalna walidacja. **Eksperyment:** Playwright zapisuje flow transcript (states/actions/network) i porównuje semantycznie, nie przez pojedyncze współrzędne.

### SQUIRE (UIST 2026)
- [Apple research](https://machinelearning.apple.com/research/squire)
- Intermediate representation SquireIR: jawne scope edycji i semantyka zachowania elementów nieobjętych zmianą. Próba 11 frontend developerów. **Eksperyment:** kodowy patch contract: allowedFiles, allowedComponents, forbiddenRegions, snapshot hash + powtórne sprawdzanie po patche.

### UICoder (NAACL 2025)
- [Apple research](https://machinelearning.apple.com/research/uicoder)
- Synthetic code generation -> compile + VLM review -> deduplicate/filter -> fine-tune. **Eksperyment:** własny mechanizm zbierania syntetycznych, zatwierdzonych przykładów, bez zewnętrznych datasetów o niewyjaśnionym statusie.

### The Way We Notice — Celestial (CHI 2026)
- [Apple research](https://machinelearning.apple.com/research/we-notice)
- Warianty komponentów powinny się znacząco różnić i jednocześnie wyglądać naturalnie dla danej domeny; badanie n=12. **Eksperyment:** generator 6 wariantów z kontrolowaną różnicą: nawigacja, siatka, akcent, density, typografia. Nie generować pozornie nowych wariantów z jednym zmienionym kolorem.

### Ferret-UI Lite / Ferret-UI 2
- [Ferret-UI Lite](https://machinelearning.apple.com/research/ferret-ui)
- [Ferret-UI 2](https://machinelearning.apple.com/research/ferret-ui-2)
- Lite 3B osiąga wg autorów 91.6% ScreenSpot-V2, 53.3% ScreenSpot-Pro, 19.8% OSWorld. **Uwaga:** grounding elementów ≠ skuteczność kompletnego agenta; osobno audyt licencji modeli.

### Weblica (2026)
- [Apple research](https://machinelearning.apple.com/research/weblica-visual-web-agents)
- HTTP-level caching + LLM synthesis reprodukowalnych środowisk webowych do RL. **Eksperyment:** snapshoty HTTP interfejsów testowych na danych syntetycznych, backend stuby, deterministyczne scenariusze.

### Models That Prove Their Own Correctness (2026)
- [Apple research](https://machinelearning.apple.com/research/correctness)
- Badanie teoretyczne dowodów interaktywnych i RLVF. Nie mylić z uniwersalnie poprawnym generowaniem kodu: przykład inspirujący do oddzielnego weryfikatora.

## 4. Google / DeepMind

### ScreenAI (2024)
- [Paper Google Research](https://research.google/pubs/screenai-a-vision-language-model-for-ui-and-infographics-understanding/)
- [Blog](https://research.google/blog/screenai-a-visual-language-model-for-ui-and-visually-situated-language-understanding/)
- Rozpoznanie typów elementów, położenia, ikon, tekstu w UI; wygenerowane opisy wspomagają uczenie danych do nawigacji. **Eksperyment:** screenshot + Playwright DOM geometry + accessibility tree -> jeden ustrukturyzowany UI graph.

### Pix2Struct
- [Kod Google Research](https://github.com/google-research/pix2struct) — Apache-2.0; repo zawiera kod i checkpointy Base/Large, ale nie cały zbiór pretrainingowy. Środowisko oryginalne zakłada TPU/JAX/T5X. **Eksperyment:** odniesienie do metod parsowania screenshotu; nie trzeba od razu uruchamiać ciężkiego treningu.

### UniAR — attention & response
- [Google paper](https://research.google/pubs/uniar-a-unified-model-for-predicting-human-attention-and-responses-on-visual-content/)
- [Blog](https://research.google/blog/towards-a-unified-model-for-predicting-human-responses-to-diverse-visual-content/)
- Modeluje kolejność uwagi, heatmapy i subiektywne oceny dla treści wizualnych, w tym stron. **Eksperyment:** modelowe attention prediction jako sygnał pomocniczy, nigdy zamiennik rzeczywistych badań użytkowników.

### AndroidWorld (ICLR 2025)
- [Google research](https://research.google/pubs/androidworld-an-open-world-for-autonomous-agents/)
- [Kod](https://github.com/google-research/android_world) — Apache-2.0; repo obecnie podaje 116 parametryzowanych zadań/20 aplikacji. Autorzy paper podawali 114 pierwotnych zadań. **Lekcja:** środowiska testowe oceniają stan systemu, a zadania parametryzowane zapobiegają pamięciowemu odtwarzaniu scenariuszy.

### gVisor
- [Kod](https://github.com/google/gvisor) — Apache-2.0 (wybrane zależności z innymi licencjami). Izolowane kontenery z dodatkową warstwą mechanizmów systemowych. **Eksperyment:** oddzielny execution sandbox dla każdej niezweryfikowanej gałęzi.

## 5. Amazon / AWS

### Amazon Nova Act
- [Amazon Science](https://www.amazon.science/blog/nova-act)
- Badania nad agentami przeglądarkowymi, SDK research preview. **Ważne:** nie jest to to samo co w pełni otwarty model Nova Act; nie wliczać go do stosu open source bez oceny licencji/usługi.

### R-VLM Region-aware GUI grounding
- [Paper Amazon Science](https://cdn.amazon.science/ef/f6/93f8a3c7457ba3c99a490b2f591d/r-vlm0-region-aware-vision-language-model-for-precise-gui-grounding.pdf)
- Precyzyjna lokalizacja małych elementów na dużych ekranach. **Eksperyment:** coarse-to-fine crop z zoomem i testem centrum bounding box.

### Firecracker
- [Kod](https://github.com/firecracker-microvm/firecracker) — Apache-2.0, rozwijany przez AWS. MicroVM do uruchamiania nieufnego kodu izolowanego od systemu hosta. Do masowej orkiestracji potrzebne również limity CPU, sieci i zarządzanie sekretami.

### Cedar for Agents
- [Kod](https://github.com/cedar-policy/cedar-for-agents) — Apache-2.0. Policy schemas i kontrola uprawnień dla narzędzi MCP. **Eksperyment:** pre-action authorization na każde wywołanie; CLI deployment disabled by default.

## 6. Meta

### Sapienz + SapFix
- [Sapienz](https://engineering.fb.com/2018/05/02/developer-tools/sapienz-intelligent-automated-software-testing-at-scale/)
- [SapFix](https://engineering.fb.com/2018/09/13/developer-tools/finding-and-fixing-software-bugs-automatically-with-sapfix-and-sapienz/)
- Automatyczne odkrywanie ścieżek, grupowanie sekwencji interakcji, analiza crashy i generowanie patchy. To praktyki udokumentowane w Meta, nie gotowa zależność dla React do automatycznej instalacji. **Eksperyment:** pokrycie stanów i flows za pomocą heurystycznego explorera w testowym systemie.

### StyleX / Lexical / Infer
- [StyleX](https://github.com/meta/stylex) — design system na poziomie kompilacji CSS; integracja wymaga decyzji architektonicznej, nie mieszać bezrefleksyjnie z Tailwind.
- [Lexical](https://github.com/facebook/lexical) — MIT; dostępny, testowalny edytor dokumentów o stabilnej strukturze stanu, istotne dla aplikacji notarialnej.
- [Infer](https://github.com/facebook/infer) — MIT; analiza statyczna Java/C/C++/ObjC, **nie** analiza React/TS. Nie polecać go jako głównego lintera frontendu.

## 7. NVIDIA

### NVIDIA NeMo Guardrails
- [Kod](https://github.com/NVIDIA-NeMo/Guardrails)
- Programowalne reguły rozmowy i ochrony prompt-injection. **Ograniczenie:** to nie sandbox systemowy ani alternatywa dla Cedar.

### WebGPU / WebNN inference
- [NVIDIA Developer](https://developer.nvidia.com/ai-apps-for-rtx-pcs/inference-backends)
- NVIDIA omawia backendy WebGPU/WebNN, ONNX Runtime Web i Transformers.js. **Eksperyment:** pomocniczy lokalny model VLM dla UI (o ile działa przy akceptowalnym SLA), przy czym rzeczywiste renderowanie Playwright zazwyczaj nie potrzebuje wynajmu GPU.

## 8. Wix: generatywna geometria layoutów

- [Wix Diffusion Layout Transformer](https://github.com/wix-incubator/DLT); [paper arXiv 2303.03755](https://arxiv.org/abs/2303.03755); ICCV 2023.
- Generacja layoutu warunkowana kategorią, rozmiarem i położeniem elementów; dane Rico / PubLayNet / Magazine. **Praktyka:** użyć metryk alignment/overlap i kodu metryk jako inspiracji, a nie od razu trenować dyfuzyjny generator stron w produkcji.

## 9. Proponowana architektura WEB FACTORY v2

```
Natural-language task / design brief
   -> Style Contract + UI Tree + immutable scope (Apple SQUIRE)
   -> Agent plans patches (Claude Code/Codex or open weights)
   -> Sandbox per branch (Orchard Env + Firecracker/gVisor)
   -> Build and static checks
   -> Browser agent (Playwright AX/DOM; OmniParser/Phi-Ground fallback)
   -> Visual evaluator (screenshot, typography, geometry, LPIPS + human)
   -> FlowEval-style evaluator (reference navigation + event states)
   -> Independent authorization (Cedar for Agents)
   -> PR + signed evidence package; no auto-merge
   -> Designer feedback (own licensed before/after pairs)
   -> Optional research RL/SFT pipeline (Orchard)
```

### 9.1 Evidence package per PR
- SHA base/HEAD, versioned synthetic fixture seed, explicit target contract.
- DOM snapshot, accessibility tree (with controlled redaction), 3 viewport screenshots, Web Vitals and network error logs.
- Flow trace steps and authoritative app-state assertions (not LLM prose).
- Critical gate: no unauthorized data disclosure, no business actions on production, tests pass.
- Design score components: geometry, visual diff, accessibility, user flow, human aesthetic approval.

### 9.2 Experimental design
Benchmark 50 tasks in four families: marketing, dashboard, document editor, multi-step forms; each task 3 seeds. Baseline vs design contract vs memory vs verifier feedback. Compare same compute budget and same model, record pass@1, all attempted actions, failure modes, API cost, median and p95 walltime. Human blind ratings for style, automated gates for function. Avoid leaderboard overfitting by holding out private synthetic test routes.

### 9.3 Security
- Only localhost or explicitly approved staging with synthetic data. No production credentials in agent containers.
- Restrict outbound network at kernel/network policy layer, not just Playwright route interception.
- Deny all destructive operations unless separate human approval + policy permit.
- Audit untrusted content from screenshots, DOM, README, third-party MCP tools for instruction injection.
- Source license is not equal to model license or dataset license; verify version+NOTICE before release.

## 10. Licensing do not copy blindly

**Pragmatic OSS candidates (at source level):** Microsoft Orchard MIT, Google Pix2Struct Apache-2.0, Google AndroidWorld Apache-2.0, Amazon Firecracker Apache-2.0, Google gVisor Apache-2.0, Cedar for Agents Apache-2.0, Meta Lexical MIT, Meta Infer MIT (language mismatch), public NeMo Guardrails. Inspect dependency, dataset, model-weight and checkpoint licenses separately.

**Apple RLDF:** repository has three **different** licenses. Code terms allow certain use/redistribution, BUT research model license excludes commercial product development and commercial deployment, and dataset license is NonCommercial. Treat model/data as academic-only. Links: [LICENSE](https://github.com/apple-aiml-research/ml-rldf/blob/main/LICENSE), [LICENSE_DATA](https://github.com/apple-aiml-research/ml-rldf/blob/main/LICENSE_DATA), [LICENSE_MODEL](https://github.com/apple-aiml-research/ml-rldf/blob/main/LICENSE_MODEL).

**Research not yet equivalent to production-ready OSS:** Apple FlowEval, SQUIRE, Weblica; Microsoft ActionEngine; Google ScreenAI and UniAR models/weights; Amazon Nova Act; these are excellent methodological references, not verified deployable open-source packages.

**Archived:** Microsoft LayoutGeneration archived 15 Sep 2026. Use techniques, not as maintained dependency.

## 11. Next implementation proposal

**Milestone M1:** Add semantic UI graph to existing Web Factory and capture Playwright trace on 3 original test flows. Evidence: replay within a fresh test environment with 100% verified state assertions.

**Milestone M2:** Scoped-edit guard following SQUIRE: unchanged routes/components compared by hashes or AST structural diff, require explicit list of allowed changes.

**Milestone M3:** Isolate agent process with gVisor or Firecracker (depending on deployment) and implement Cedar MCP authorizer with local deny by default.

**Milestone M4:** Establish design feedback store with one click comments/regions on screenshots and before/after pair collection; no Apple commercial weights.

**Milestone M5:** Train or calibrate a small local reviewer on first-party licensed data; validate correlation to blind human judgments. Only if justified, progress to Orchard RL experiments.

## Source audit

All URLs above were discovered in public primary-source publications or owner repositories. Publication dates and benchmark values reflect the stated publication context. Source and data licensing are independently relevant. This memo does not imply access to restricted defence research or military certification. No code was deployed in this research step.