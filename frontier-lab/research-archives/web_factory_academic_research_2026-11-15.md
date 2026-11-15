# Web Factory: academic research brief & experimental roadmap
**Review date:** 2026-11-15  
**Scope:** multimodal web engineering, screenshot-to-code, design intent, visual alignment, browser-verifiable functionality, preference modeling, open-source viability.

## Executive research claim
A high-performing web-design coding agent should not be viewed as an LLM generating code from prompts. It is a **stateful, evidence-seeking optimization system** where the design target and current rendered application share an explicit structured representation; tests certify interaction transitions; visual critics suggest *scoped* corrections; independent judges and humans prevent metric gaming; and safety/functional gates dominate pure aesthetics.

### Evidence hierarchy
- **Peer-reviewed, with executable/public artifacts:** Design2Code (NAACL 2025), DCGen (FSE 2025), WebGen-Agent (ICLR 2026 paper and public code/weights; repository license not confirmed), Code Aesthetics / OpenDesign (ICLR 2026 paper; repository release completeness limited), Vision2Web (ICML 2026; NC dataset), WebCompass (EMNLP 2026; public code, license not confirmed), WebWeaver (EMNLP 2026; public Web4Style dataset NC), VFLM (CVPR 2026; Apache-2.0 code), LayoutPrompter (NeurIPS 2023).
- **Research preprints needing independent replication:** LiveWorkspace (2026-11-09), VisStateCoder (2026-10), RefCraft (2026-10), WebGrader (2026-08), vision-guided iterative refinement (2026-04), InterWebCoder (2026-10).
- **Practical OSS transfer candidates:** Sony WebGen-V Bench (MIT), VFLM (Apache-2.0), LPIPS code (BSD), BrowserGym (verify current components/dependencies), Playwright, axe-core. **Public repository without license is not commercial-use authorization.**

## Key publications and transferable mechanisms

| No | Study | Venue/status | Mechanism | Evidence and limitations | Artifact |
|---:|---|---|---|---|---|
| 1 | Design2Code (Si et al.) | NAACL 2025 | Screenshot -> code with high-level CLIP and fine-grained block/text/position/color checks | 484 real-world webpages; benchmark warns that systems miss elements and layouts; data has blue placeholders for images | [paper](https://aclanthology.org/2025.naacl-long.199/) · [code](https://github.com/jiahuigeng/Design2Code) |
| 2 | DCGen (Wan et al.) | FSE 2025 | Divide large screenshots into regions; generate/reassemble | Up to ~15% visual similarity gain on specified experiments; limitations: static and segmentation decisions | [paper](https://doi.org/10.1145/3729364) · [code](https://github.com/WebPAI/DCGen) |
| 3 | WebSight (Laurençon et al.) | 2024 technical report | Synthetic screenshot–HTML pairs for VLM training | v0.2 ~1.92M rows, real imagery and Tailwind; synthetic-to-real shift, license and source assets need scrutiny | [report](https://arxiv.org/abs/2403.09029) · [data](https://huggingface.co/datasets/HuggingFaceM4/WebSight) |
| 4 | Vision2Web (He et al.) | ICML 2026 | Three-level website tasks: static, interactive, full-stack; GUI agent + VLM judge | 193 tasks, 918 images, 1,255 tests; data CC BY-NC-SA 4.0 research-only | [paper](https://proceedings.mlr.press/v306/he26n.html) · [code](https://github.com/zai-org/Vision2Web) |
| 5 | WebCompass (Lei et al.) | EMNLP 2026 | Multimodal inputs: text/image/video; generation/edit/repair and browser-based agent judge | 1,526 tasks; 25-point closed/open model gap reported on authors' suite. Repository labels/distributions may differ from paper: pin version | [paper](https://aclanthology.org/2026.emnlp-main.1669/) · [code](https://github.com/NJU-LINK/WebCompass) |
| 6 | WebWeaver (Xu et al.) | EMNLP 2026 | Explicit style contract transferred across agents; WebJudge rubric | Better than compared baselines on tested models; Web4Style dataset 300 public briefs, CC BY-NC 4.0 | [paper](https://aclanthology.org/2026.findings-emnlp.582/) · [dataset](https://huggingface.co/datasets/Web4StyleLab/Web4Style) |
| 7 | WebGen-Agent (Lu et al.) | ICLR 2026 | Multi-level feedback, screenshot/GUI feedback and step-level GRPO | Public inference/training, models 7B/8B; repo licensing not verified | [paper](https://openreview.net/forum?id=fE14yWa68Z) · [code](https://github.com/mnluzimu/WebGen-Agent) |
| 8 | Vision-guided iterative refinement (Sansford et al.) | ICLR 2026 workshop / arXiv | Critic-in-loop on screenshots | Up to 17.8% improvement after 3 cycles within its protocol; transfer requires same tasks/metric | [paper](https://arxiv.org/abs/2604.05839) |
| 9 | Code Aesthetics / OpenDesign (Xiao et al.) | ICLR 2026 | Execution agent + static aesthetics agent + interaction agent; RL reward | 840 design cases and AesCode-358K. Public repo has release TODO items; audit completeness before reuse | [paper](https://openreview.net/forum?id=Q87kwGI6bx) · [code](https://github.com/bangx7/code_aesthetics) |
| 10 | WebGen-V Bench (Sony) | KDD 2026 | Decompose into section-level specifications, generate/evaluate/refine per section | MIT code; Gemini-first, requires adaptation to other models; dataset URLs partly withheld for copyright | [code](https://github.com/sony/web_gen_v_bench) |
| 11 | LiveWorkspace (Xiao et al.) | arXiv 2026-11-09 | Persistent target/current shared visual states; deterministic visual diff and source bindings | +1.8 Design2Code, +2.0 ScreenBench; 93.0% edits on 100 controlled cases; preprint, no verified official OSS | [paper](https://arxiv.org/abs/2611.12112) |
| 12 | VisStateCoder (Pan et al.) | arXiv 2026-10 | Project State Graph links prototype, files, workflows, render evidence; localized changes | +26.1/+22.6 on Vision2Web interactive/full-stack (model-averaged), but evaluated on smaller, non-React projects; preprint | [paper](https://arxiv.org/abs/2610.17861) |
| 13 | WebGrader (Chen et al.) | arXiv 2026-08 | Executable browser Flow Contracts; trace-backed reward for real success | 8B model 52.01% success; +7.88 points over baseline; preprint | [paper](https://arxiv.org/abs/2608.06474) |
| 14 | InterWebCoder (Xiao et al.) | arXiv 2026-10 | Reproducible executable interaction tests + SFT + GRPO | Synthesized 1,736 verified samples, reduced reward time >97% in experiments; preprint | [paper](https://arxiv.org/abs/2610.28610) |
| 15 | RefCraft (Wang et al.) | arXiv 2026-10 | Generate using 1-5 visual references and natural instructions | 300 tasks; best of 9 models scores 52.12/100; not a guarantee for production; code not verified | [paper](https://arxiv.org/abs/2610.26826) |
| 16 | Seeing is Improving / VFLM (Guo et al.) | CVPR 2026 | Rendered visual feedback for SVG/text layouts; OCR-informed reward | Formal graphic layout, not directly web apps; Apache-2.0 code and reward serving | [paper](https://openaccess.thecvf.com/content/CVPR2026/html/Guo_Seeing_is_Improving_Visual_Feedback_for_Iterative_Text_Layout_Refinement_CVPR_2026_paper.html) · [code](https://github.com/FolSpark/VFLM) |
| 17 | LayoutPrompter (Lin et al.) | NeurIPS 2023 | Constraint serialization, dynamic exemplar retrieval, ranking without training | Evaluated graphics layouts, not whole app; easy to transplant as design candidate proposer | [paper](https://papers.neurips.cc/paper_files/paper/2023/hash/88a129e44f25a571ae8b838057c46855-Abstract-Conference.html) · [code](https://github.com/microsoft/LayoutGeneration/tree/main/LayoutPrompter) |
| 18 | LPIPS (Zhang et al.) | CVPR 2018 | Neural perceptual image distance | Better perceptual signal than pixel-by-pixel for many distortions; not a measure of usability/legibility on its own | [code](https://github.com/richzhang/PerceptualSimilarity) |
| 19 | ScreenSpot-Pro (Li et al.) | ACM MM 2025 | GUI element grounding in dense professional software | 23 apps, high-res targets; original baseline 18.9%, cascaded 48.1% (launch-era), leaderboard evolved | [paper](https://arxiv.org/abs/2504.07981) · [code](https://github.com/likaixin2000/ScreenSpot-Pro-GUI-Grounding) |
| 20 | Mind2Web (Deng et al.) | NeurIPS 2023 | Broad web interactions and generalization across sites | >2,000 tasks, 137 sites; useful to train/test agents but external sites change | [code](https://github.com/OSU-NLP-Group/Mind2Web) |
| 21 | BrowserGym (ServiceNow) | research software | Sandboxed task-driven browser gym; agent test harness | Independent from design scoring, particularly useful for task execution robustness | [code](https://github.com/ServiceNow/BrowserGym) |
| 22 | RILA (Rendering-in-the-Loop) | arXiv 2026-09 | Replays action trajectories, evaluates functionality and visuals in browser, then edits | Research setup fine-tunes 9B on 16 H800 GPUs; not a viable first step for lean team | [paper](https://arxiv.org/abs/2609.02088) |

**Name collision warning:** the EMNLP 2026 paper *WebWorld: The Browser as a World Model for Self-Improving Web Code* is **not automatically** the same artifact as [QwenLM/WebWorld](https://github.com/QwenLM/WebWorld), a differently described browser-state simulator. Do not confuse papers or assume code matches a similarly named repo.

## Integration architecture: Design Intelligence Compiler

```text
Requirements (natural language, annotated Figma, screenshots, videos)
       |
       v
Intent compiler: content + interaction + brand/style contract (WebWeaver)
       |
       v
Target Visual State: typed visual hierarchy, geometry, tokens, constraints (LiveWorkspace)
       |                                       |
       v                                       v
Project State Graph -------------------> component/file impact scope (VisStateCoder)
       |
       v
Variant generator (Claude Code/Codex and optional open local coder)
       |
       v
Sandbox build + render 3 viewports + interaction flow recorder (Playwright)
       |                    |                      |
       v                    v                      v
Visual diff           Perceptual critic       Executable Flow Contracts
regions, OCR, LPIPS    style consistency       DOM, network, mock backend state
       \                    |                      /
        \-------------------+---------------------/
                            v
               Hard-gates and multiobjective ranker
                            |
             Human blind A/B preference evaluation
                            |
                   Human-approved candidate PR
```

**Important:** a visual model may propose fixes but must not certify sensitive business state. A recorded success toast does not prove persistence; verify mock backend state. Agent tool access should be scoped to a dev/staging sandbox without client data.

## Experiment protocol (pre-register before implementation)

### Research questions
- **RQ1:** Does a structured style contract improve blind human preference over a prompt-only baseline at equal model and iteration budgets?
- **RQ2:** Does structured region-based visual feedback improve fidelity and reduce token cost relative to comparing full screenshots?
- **RQ3:** Do executable Flow Contracts prevent false positives in visual/LLM judges for forms and multipage flows?
- **RQ4:** Does persistent visual state + project dependency graph reduce regressions when editing shared components?
- **RQ5:** Can a local open-weight visual critic rank variant pairs without materially reducing agreement with blind human judgments?

### Test suite
Construct 60 **original, licensed or synthetic** frontend tasks: 15 responsive landing pages, 15 complex form flows, 15 data-dense dashboards, 15 multi-route workflows. Maintain 12 hidden test tasks. Create synthetic accounts only; never use real notarial/investor documents. For each task collect acceptance checks, target viewports, intended content and style, required interactions, and permitted assets.

### Experimental arms
- **A (control):** same coding model + text prompt + conventional compile/test.
- **B:** A + style contract and layout segmentation.
- **C:** B + structured visual state and region-level feedback.
- **D:** C + executable flow checks, preservation tests, impact-scoped code edits.
All arms get matched total time/token/API budgets. Randomize per-task trial order and run at least 3 independent seeds per arm; log all failed builds (do not silently drop). Do not change the judge mid-study.

### Primary and secondary outcomes
1. **Functional acceptance:** weighted percentage of independently executable state transitions, including synthetic backend verification.
2. **Blind visual preference:** pairwise choices by human judges using identical viewport screenshots; require both option order randomization and inter-rater agreement reporting.
3. **Critical safety/a11y gates:** no unapproved network calls, serious WCAG violations, unsafe data exposures or production mutations. Failures remain failures regardless of attractive appearance.
4. **Visual fidelity:** combine region-level geometry/element recall, OCR/text fidelity and LPIPS with *explicit non-compensation rules* (a missing CTA cannot be offset by attractive colors).
5. **Engineering cost:** wall clock time, token count, API calls, browser time, dollars/task, repair iterations and regression count.
6. **Performance:** LCP, CLS, INP where field-data exists (lab measurements separately labeled). Record keyboard-only usability and reduced-motion behavior.

### Statistics
Report distributions, bootstrap confidence intervals clustered by task, task-level paired deltas, Wilson intervals for binary passes, and blinded pairwise preference win/tie/lose. Correct for multiple comparisons or designate a primary hypothesis. Show raw results and code; report worst-case task regressions, not just average gains. Main comparison A vs D should preserve same model architecture and budget. For aesthetics, retain a human holdout: model-as-judge is a noisy proxy and can optimize its own weaknesses.

### Reward / selection policy
Hard fail on deploy/run errors, missing critical interactions, unauthorized egress, critical a11y or sensitive data, then Pareto-rank viable candidates by:
- F: interaction/correctness evidence;
- V: geometric/OCR/perceptual fidelity;
- S: style-contract adherence and blind user preference;
- E: effort and runtime cost;
- P: accessibility and page performance.
Avoid reducing all metrics to one scalar before inspecting trade-offs. A compact optional experimental objective is `U = 0.35F + 0.25V + 0.20S + 0.10P + 0.10E` **only after** hard gates; these weights are initial hypotheses, not validated scientific constants.

## Rollout into existing Web Factory MVP
**P0 — reproducibility:** pin Node/Playwright/browser/fonts/timing; freeze animations and dynamic widgets; use synthetic fixtures; collect DOM bounding boxes, accessibility tree and three screenshot breakpoints; stabilize baseline assignment.

**P1 — style-contract compiler:** define machine-readable fields (`identity`, `typeScale`, `spacing`, `color`, `density`, `motion`, `responsiveness`, `interaction`, `antiPatterns`); version them separately per product; render style-constraint violations as evidence.

**P2 — structured visual diff:** build region tree from DOM + image; align reference/current using normalized text and geometry; output missing/extra/moved/resized nodes; combine with LPIPS on aligned crops and screenshot diffs; tag all nodes with source component paths.

**P3 — executable interaction contracts:** store each workflow's setup, action, expected DOM change, network result and mock DB effect. Use browser recordings to propose tests, human review them, and promote only deterministic checks.

**P4 — local critic evaluation:** evaluate a small open-weight VLM as *critic* on synthetic UIs; record human agreement before using it to drive any automatic refactoring; only fine-tune with LoRA if RQ5 indicates benefit.

**P5 — research-grade CI:** version prompts, model IDs, code commits, dependencies, benchmarks, datasets, screenshots, reviewer rubrics, run costs and confidence intervals; release one research report per controlled experiment.

## Legal and licensing diligence
- WebGen-V Bench repository states MIT; third-party pages and assets still subject to separate rights.
- VFLM repository states Apache-2.0.
- LPIPS project package identifies BSD license.
- WebSight dataset CC BY 4.0 and supplementary disclosure provision; inspect original assets and dataset card before commercial reuse.
- Web4Style dataset CC BY-NC 4.0 (not approved for commercial training/deployment without separate permission).
- Vision2Web dataset CC BY-NC-SA 4.0, research-only.
- WebCompass and WebGen-Agent repositories are publicly viewable but a clear project-wide OSS license was not verified; do not vendor into a commercial app without resolving that.
- Design2Code material highlights research-only licensing and C4 provenance; avoid copying evaluation examples/assets directly to commercial products.
- Aesthetic similarity does not authorize cloning a competitor’s design, visual assets, brand, text or source code. Prefer original or appropriately licensed fixtures.

## References (primary sources)
1. [Design2Code, NAACL 2025](https://aclanthology.org/2025.naacl-long.199/)
2. [DCGen, ACM FSE 2025](https://doi.org/10.1145/3729364)
3. [WebSight, arXiv 2024](https://arxiv.org/abs/2403.09029)
4. [Vision2Web, ICML 2026](https://proceedings.mlr.press/v306/he26n.html)
5. [WebCompass, EMNLP 2026](https://aclanthology.org/2026.emnlp-main.1669/)
6. [WebWeaver, Findings EMNLP 2026](https://aclanthology.org/2026.findings-emnlp.582/)
7. [WebGen-Agent, ICLR 2026](https://openreview.net/forum?id=fE14yWa68Z)
8. [Vision-Guided Iterative Refinement, arXiv 2026](https://arxiv.org/abs/2604.05839)
9. [Code Aesthetics with Agentic Reward Feedback, ICLR 2026](https://openreview.net/forum?id=Q87kwGI6bx)
10. [WebGen-V Bench, Sony KDD 2026 implementation](https://github.com/sony/web_gen_v_bench)
11. [LiveWorkspace, arXiv 2026](https://arxiv.org/abs/2611.12112)
12. [VisStateCoder, arXiv 2026](https://arxiv.org/abs/2610.17861)
13. [WebGrader, arXiv 2026](https://arxiv.org/abs/2608.06474)
14. [InterWebCoder, arXiv 2026](https://arxiv.org/abs/2610.28610)
15. [RefCraft, arXiv 2026](https://arxiv.org/abs/2610.26826)
16. [VFLM, CVPR 2026](https://openaccess.thecvf.com/content/CVPR2026/html/Guo_Seeing_is_Improving_Visual_Feedback_for_Iterative_Text_Layout_Refinement_CVPR_2026_paper.html)
17. [LayoutPrompter, NeurIPS 2023](https://papers.neurips.cc/paper_files/paper/2023/hash/88a129e44f25a571ae8b838057c46855-Abstract-Conference.html)
18. [LPIPS, CVPR 2018 project](https://github.com/richzhang/PerceptualSimilarity)
19. [ScreenSpot-Pro, arXiv 2025](https://arxiv.org/abs/2504.07981)
20. [Mind2Web, NeurIPS 2023 artifact](https://github.com/OSU-NLP-Group/Mind2Web)
21. [BrowserGym, ServiceNow](https://github.com/ServiceNow/BrowserGym)
22. [RILA, arXiv 2026](https://arxiv.org/abs/2609.02088)