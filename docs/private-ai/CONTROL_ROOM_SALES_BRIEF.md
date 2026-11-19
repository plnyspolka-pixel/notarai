# Private AI Control Room — product & sales design brief

**Product mandate (2026-11-16; decision of product owner):** Control Room is PRIMARILY a **sales, trust-building and conversion asset**. It should demonstrate to prospective customers and purchasing committees *why NotarAI / Finance You can be trusted with sensitive workflows*. It is not primarily a technical console for engineers or a decorative audit log.

The user describes it as "coś w stylu dowodu społecznego, materiał sprzedażowy dla nas przede wszystkim". Respect this direction in all future designs, PRs and demos. Design for buyer confidence **without fabricating social proof or overstating security**.

## Target audience and main question

First screen must answer in roughly 5 seconds: **"Co dzieje się z moimi danymi, kto ma dostęp i jak mogę to sprawdzić?"**

- Business buyer / notary / head of operations: understand protection and control without technical jargon.
- DPO / compliance / risk / enterprise procurement: inspect underlying verifiable evidence, scope, time, provider and limitation.
- Security auditor: deep data lineage and denied/unknown events without exposing client content.
- Sales representative: demo a convincing, repeatable scenario with clearly labeled synthetic examples.

## Two-level information architecture

1. **Sales-facing Trust Overview (landing/demo mode) — lead with an outcome, not a log.**
   - Hero proposition: control and traceability of each authorized AI data flow.
   - Four *plain-language* answers: **Where does data go? Who can access it? What is blocked? What proof can be viewed?**
   - Visually prominent flow: upload → policy decision → EU processor → metadata evidence. Click for detail.
   - Explain protections in customer value terms; reveal AWS/private networks, IAM, policy engines, encryption and evidentiary chain in progressive disclosure.
   - Trust-proof tiles such as "Dostęp na podstawie uprawnień", "Ścieżka przetwarzania", "Operacje zablokowane", "Zdarzenia bez potwierdzenia"; never imply controls have been independently audited if not true.
   - Clear CTA suitable for B2B sales (e.g. "Zobacz demonstrację zabezpieczeń", "Porozmawiaj o wdrożeniu"), but **do not invent a working booking URL or verified certifications**.
   - Use **DEMO / SYNTETYCZNE** prominently on mock data, and label each proof as `observed`, `declared`, `unknown`, or `independently verified` only with valid evidence.
2. **Evidence & Audit Drill-down (authenticated operator and auditor mode).**
   - Detailed time-ordered event log, tenant-scoped search, document pseudonyms, actors, regions, policy decisions, proof levels and incidents.
   - Server-enforced auth and tenant isolation; safe exports; no content in logs.
   - "Brak dowodu" / gaps and incidents displayed honestly, not hidden to improve appearance.

Do NOT conflate a public sales/demo page with a customer's private authenticated evidence. Public demo must contain only fixed synthetic data. Private evidence must never be accessible to sales users or outsiders by default.

## Narrative architecture — three short demo stories

- **Normal path:** test document is accepted, checked, processed in a validated destination, metadata event is recorded. Explicitly distinguish what the synthetic pilot demonstrates from what is not yet deployed.
- **Attempted unauthorized access / egress:** rule denies the operation; show where enforcement occurred and what *recorded evidence* demonstrates the denial.
- **Missing proof:** event is marked uncertain; buyer sees that the platform does not paint uncertain cases green. The trust claim is transparent handling of exceptions, not "zero incidents".

Lead with before/after *conceptual benefits* (clarity, control, auditability) rather than unmeasured time savings or invented risk reduction percentages.

## Design directives

- Premium, restrained, enterprise-grade visual character: serious trust platform, not hacker/military cosplay.
- One-page clean hero; fewer competing numbers; concise human Polish; prioritize visual hierarchy and storytelling.
- Data pathway diagram and evidence chips should be legible at presentation distance. 16:9 screen share and responsive phone layouts are first-class.
- "Show, don't merely claim": each substantive security claim links to its evidence, policy scope, deployment status and caveats.
- Emphasize confirmed EU geography and isolation **only after live verification**, not by graphic badges alone.
- Optional customer logos, independent audit seals, testimonials, ISO certificates, partner logos and quantitative KPIs **only if genuine, current, permissioned and evidenced**. Until then use labeled demo scenarios instead of fake social proof.
- Avoid "military-grade", "zero risk", "guaranteed EU-only", "certified for banks/hospitals" or "nobody can ever access your data" unless independently substantiated in precisely defined scope.
- Every design review: ask whether the asset makes a skeptical enterprise buyer more likely to request a demo **and** whether every reassurance survives a DPO/security audit.

## Non-negotiable trust matrix

| What is shown | Customer-facing phrasing | Condition |
| --- | --- | --- |
| Synthetic offline prototype | "Demonstracja sposobu kontroli przepływu" | Clearly labeled DEMO; not live |
| CI / unit tests | "Mechanizmy testowane automatycznie" | Link exact commit and CI |
| Actual deployed AWS staging | "Testowane w odizolowanym środowisku" | Live evidence and scope |
| Observed event | "Zdarzenie zarejestrowane" | Trusted producer identity exists |
| Gap | "Nie mamy wystarczającego dowodu" | Visible as UNKNOWN |
| Independent attestation | "Zweryfikowano niezależnie" | Third-party/source evidence |
| Legal/industry certification | Exact certificate claim only | Valid issuer/scope/date |

## Next UI iteration

1. Keep the existing Control Room layout as reference, but replace the opening *technical* framing with a **trust-oriented sales hero**, with four proof demonstrations above the fold.
2. Make a separate sales demo mode and evidence drill-down; retain precise demo labels and zero connection to customer data.
3. Add guided 60–90-second walk-through of the three proof stories; not auto-play, no false claims, no fake clients.
4. In `.claude/commands/private-ai-control-room.md` ensure Claude considers this document binding for UI/product choices.
5. Validate presentation quality, typography, WCAG AA, responsiveness, user comprehension and factual grounding before merge.

**Priority decision:** Optimize Control Room for **credible sales conversion and buyer trust**; deep observability serves that business goal.
