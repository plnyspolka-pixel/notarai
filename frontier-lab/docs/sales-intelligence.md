# Sales Intelligence: experimental causal decision layer

## Core goal
Measure **incremental qualified outcomes**, not clicks or time-on-page alone. A prediction that a customer is likely to convert does not establish that a proposed intervention caused conversion. Track opt-outs and harm as first-class negative outcomes.

## Data intake (proposed, not connected)
1. Explicit, lawful event collection and consent preferences where applicable; strict minimization; short retention.
2. Event envelope in contracts/event.schema.json (no phone/email/name/precise address/IP in the research stream).
3. Quarantined ingestion; validated context/purpose/tenant; identity resolution restricted to authorized parties and audited.
4. Aggregate fact tables (impressions, qualified leads, outcomes, contacts) in private EU storage with role-scoped access.
5. Experiment assignment registry with locked seeds, analysis plan and treatment timestamps.
6. Separate online scoring and offline evaluation; any real messages, calls or pricing require explicit business approval and compliance review.

## Research layers and candidate tools
- Behavioral telemetry: OpenReplay, PostHog, Jitsu. Session replay can capture sensitive information; require masking and lawful basis *before* integration.
- Storage/features: ClickHouse, PostgreSQL, Apache Unomi; identity linking only when justified.
- Survival and temporal events: EasyTPP and River.
- Causal: DoWhy, EconML, DoubleML, CausalML. State identification assumptions and diagnostics; model fit alone cannot remove confounding.
- Offline bandit/recommender evaluation: Open Bandit Pipeline, ReAgent, RecSim NG, FuxiCTR, RecBole, Vowpal Wabbit.
- Process analysis: PM4Py; check AGPL or other obligations separately.
- Media efficiency: Meridian (Google), GeoLift (Meta), PyMC-Marketing.
- Behavioral experiments: jsPsych, mouse-based research with attention to consent.

## Experiment roadmap
EX-S1 Randomized outreach: control vs single approved reminder. Unit of randomization: lead or organization, not page view. Pre-register primary metric (e.g. qualified next step within a fixed window), negative outcomes (opt-out/complaint) and cost. Strata and clustering decided *before* tests.
EX-S2 Uplift policy: compare random baseline against learned policy via proper propensity logging / off-policy evaluation only where support is adequate. Prevent leakage across user/time.
EX-S3 Process mining: isolate abandonment stages using fictitious form-event sequences, compare intervention and control, investigate accessibility before nudging.
EX-S4 MMM/geo experiments: requires adequate channel-level data and valid design; do not claim attribution from correlation.

## Reproducibility
tools/uplift_demo.py simulates assigned groups under randomization. It estimates simple risk difference and Wilson intervals. **Synthetic results have zero evidentiary value for user behavior, performance or revenue.** No external data is accessed.

## Finance You specific compliance
Keep borrower and investor data contexts segregated. Do not build a public/protected investor project catalog or algorithmic market of loans by accident. Only communications and lead processing supported by correct legal review, consent rules, KYC/AML controls and permissions. No processing of sensitive financial data in this research repository.