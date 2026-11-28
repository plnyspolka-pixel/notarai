# Methods for choosing and validating a digital product before building it

Status: 28 Nov 2026. Evidence labels used below: **[PR]** peer-reviewed, **[WP]** working paper / preprint, **[PRAC]** practitioner or vendor source (opinion or unaudited data). Numbers are quoted as stated by the authors (abstract or cited passage); where an OpenAlex record had no abstract, the finding is given qualitatively and marked "(summary, not re-verified this session)". Companion registry: `rejestr_walidacja.jsonl` (72 works, all IDs from OpenAlex tool results).

Access limits this session: `www.kickstarter.com`, `www.lennysnewsletter.com` and `www.evanmiller.org` could not be fetched (hosts outside the session's allowed network), so their numbers come only via search-result summaries and third parties. The OpenAlex daily search budget ran out twice; later records were retrieved by free DOI lookups.

## 1. Pre-sales, waitlists, fake doors, landing-page tests, concierge/Wizard-of-Oz, crowdfunding: how well do stated interest and sign-ups predict real purchases?

### Takeaway
Stated interest systematically overstates buying: meta-analyses put the hypothetical-to-real gap at about 21% for consumer-goods WTP (marketing), a median ratio of 1.35, and up to a factor of about 3 in some settings, and intentions predict worst for new products. Only tests with a real payment (pre-sale, deposit, incentive-aligned choice) have direct validation against purchases; fake-door and waitlist tests have no peer-reviewed predictive-validity studies at all.

### Cited Findings
- [PR, meta-analysis] 77 studies / 115 effect sizes (24,347 hypothetical and 20,656 real WTP observations): "on average, the hypothetical bias is 21%"; indirect methods (conjoint) "overestimate RWTP significantly stronger than direct methods"; bias is greater for higher-valued products, specialty goods and within-subject designs (Schmidt & Bijmolt, JAMS 2020) — [OpenAlex W2947920467](https://openalex.org/W2947920467) / [doi](https://doi.org/10.1007/s11747-019-00666-6)
- [PR, meta-analysis] Murphy et al. 2005: 28 valuation studies, median ratio of hypothetical to actual value 1.35 (figure restated in the Stefani et al. addendum abstract) — [W3121785658](https://openalex.org/W3121785658); [W1536244577](https://openalex.org/W1536244577)
- [PR, meta-analysis] List & Gallet 2001: subjects overstate preferences by a factor of about 3 on average in hypothetical settings; smaller for private than public goods and for WTP than WTA (summary, not re-verified this session; abstract missing in OpenAlex) — [W1524056198](https://openalex.org/W1524056198)
- [PR, meta-analyses] Further moderators of hypothetical bias: Penn & Hu 2018 (enhanced meta-analysis of sources and mitigation), Penn & Hu 2019 (cheap-talk scripts), Schläpfer & Fischhoff 2012 (task familiarity and contextual cues predict the bias) — [W2806860413](https://openalex.org/W2806860413); [W2916665850](https://openalex.org/W2916665850); [W2083357469](https://openalex.org/W2083357469)
- [PR] Sheeran 2002, meta-analysis of meta-analyses of the intention-behaviour gap (paper reports intentions explain about 28% of variance in behaviour; summary of body text) — [W2070257463](https://openalex.org/W2070257463)
- [PR, meta-analysis] Webb & Sheeran 2006, 47 experimental tests: "a medium-to-large change in intention (d = 0.66) leads to a small-to-medium change in behavior (d = 0.36)" — [W2109827187](https://openalex.org/W2109827187)
- [PR] Morwitz, Steckel & Gupta 2007: intentions correlate more with purchase for existing than new products, durables than non-durables, short horizons, and specific brands/models (summary, not re-verified this session) — [W3121203183](https://openalex.org/W3121203183). Morwitz 2014 review: "Purchase intentions are correlated and predict future sales, but do so imperfectly" — [W2001431891](https://openalex.org/W2001431891)
- [PR] Chandon, Morwitz & Reinartz 2005: measuring intentions itself inflates the intention-behaviour association ("self-generated validity") — [W2116308420](https://openalex.org/W2116308420)
- [PR] Wertenbroch & Skiera 2002: incentive-compatible BDM "yields lower WTP estimates than do non-incentive-compatible methods such as open-ended and double-bounded contingent valuation" — [W3124768374](https://openalex.org/W3124768374)
- [PR, theory] Pre-ordering as demand learning: firms "learn about total demand from a limited sample of target consumers preordering a new product" and invest only if updated expectations are high enough (Chemla & Tinn 2020); contracting with consumers before investment "improves screening for valuable projects" (Strausz, AER 2017) — [W3121441921](https://openalex.org/W3121441921); [W2219244669](https://openalex.org/W2219244669)
- [PR] Cao, Koning & Nanda 2023: on a platform for launching digital products, female-focused products launching when nine in ten users are men "experience 45% less growth a year after" launch, i.e. the test sample differed from the target market — [W4389734865](https://openalex.org/W4389734865)
- [PR] Anderson et al. 2015: some early buyers are "harbingers of failure" whose early adoption "is a strong signal that a product will fail" — [W2015859456](https://openalex.org/W2015859456)
- [PRAC] Waitlist-to-paid conversion: Lenny Rachitsky's 2022 benchmark, as summarised by secondary sources, is 5%-25%, averaging about 20% when people get access within a month and below 10% after three months; one founder anecdote reports about 0.11% from 4,500 sign-ups — [Lenny's Newsletter](https://www.lennysnewsletter.com/p/what-is-good-waitlist-conversion) (paywalled, not fetched); [Indie Hackers thread](https://www.indiehackers.com/post/anyone-have-benchmarks-for-waitlist-to-signup-conversion-813460d68a)
- [PRAC] Strategyzer's experiment library lists 44 experiments "from customer interviews to presales", rated on cost, setup time, run time and evidence strength, on a scale from "Say" to "Do" and from "Low-stakes action" to "Real-world commitment"; advice is to start with cheap discovery experiments and move to validation — [Strategyzer experiment library](https://www.strategyzer.com/library/experiment-library); [How strong is your innovation evidence?](https://www.strategyzer.com/library/how-strong-is-your-innovation-evidence)
- [PRAC] Median landing-page conversion (any conversion goal, mostly lead capture): 6.6% across industries and 3.8% for SaaS in Unbounce's 2024 report (41,000 pages); the 2020 report gave 3.2% overall — [Unbounce benchmark report](https://unbounce.com/conversion-benchmark-report/)

### Inferences
- A defensible evidence ladder, weakest to strongest: opinions/interviews < survey intent or WTP < e-mail sign-up/waitlist < fake-door click < deposit or pre-order with real payment < repeat use/renewal. The academic literature validates the two ends (stated measures are biased; paid commitments screen projects) but not the middle rungs.
- Planning discounts supported by the literature: cut survey WTP by at least the 21% average and more for expensive or niche products; treat intent for a new product as an upper bound; treat waitlist counts as 5%-25% buyers only if access comes within weeks and the list came from the target segment, with large downside (the 0.11% anecdote).
- Because measurement inflates behaviour (self-generated validity) and warm audiences differ from the market (sampling bias), conversion from surveyed or owned audiences should not be extrapolated to cold traffic.
- Concierge and Wizard-of-Oz MVPs test value delivery and retention rather than initial demand; no quantitative validity evidence was found, so they belong after a paid-demand signal.

### Gaps
- No peer-reviewed study was found that tracks fake-door / smoke-test click rates or waitlist sign-ups to later purchases of the same product. All waitlist numbers are practitioner data from one 2022 newsletter survey.
- No validated benchmark for pre-sale conversion of courses/ebooks from cold ads was found.
- Ethical/legal treatment of fake-door tests (consumer-law exposure of advertising a non-existent product) was not researched.

## 2. Lean startup / scientific approach to entrepreneurship: what improves outcomes?

### Takeaway
RCT evidence shows that teaching founders to state explicit theories, pre-set tests and decision rules makes them terminate weak ideas more often, pivot a small number of times and perform better; large-sample observational evidence links A/B-testing adoption to 30%-100% better performance after a year. The mechanism is faster, better-calibrated killing and pivoting, not better ideas.

### Cited Findings
- [PR, RCT] Camuffo et al. (Management Science 2020): 116 Italian startups, 16 data points over about a year, both arms get 10 training sessions; treated founders "perform better, are more likely to pivot to a different idea, and are not more likely to drop out than the control group in the early stages"; the approach "reduces the odds of pursuing projects with false positive returns" — [W2767996707](https://openalex.org/W2767996707)
- [PR, RCT replication] Camuffo et al. (SMJ 2024): 759 firms in four RCTs; "positive impact on idea termination" and a nonlinear effect on radical pivots, "treated firms running few over no or repeated pivots" — [W4393152018](https://openalex.org/W4393152018)
- [PRAC summary of the RCT] Innovation Growth Lab reports 49% of trained founders pivot at least once versus 21% of untrained; revenue appeared earlier and average revenue was higher though odds of positive revenue in the first nine months were not higher — [IGL blog](https://innovationgrowthlab.org/node/1034)
- [PR, observational] Koning, Hasan & Chatterji (Management Science 2022): "although relatively few firms adopt A/B testing, among those that do, performance improves by 30%–100% after a year of use"; experimentation helps start-ups "develop more new products, identify and scale promising ideas, and fail faster" — [W3124144674](https://openalex.org/W3124144674)
- [PR] Leatherbee & Katila 2020: 152 NSF I-Corps teams; hypothesis formulation, probing and idea convergence link up as the method predicts, with team composition a boundary condition — [W3091900761](https://openalex.org/W3091900761)
- [PR] Bennett & Chatterji (SMJ 2023): "Fewer than half of those who considered starting a business take even the lowest cost steps, like searching the Internet for potential competitors or speaking with a friend" — [W2967932666](https://openalex.org/W2967932666)
- [PR, conceptual] Felin et al. 2019 argue feedback-led lean experimentation without prior theory yields incremental ideas; Shepherd & Gruber 2020 note limited academic testing of the lean startup framework; Kerr, Nanda & Rhodes-Kropf 2014 frame entrepreneurship as staged experiments — [W2954550564](https://openalex.org/W2954550564); [W2999610823](https://openalex.org/W2999610823); [W2400126264](https://openalex.org/W2400126264)

### Inferences
- The programme should require, per candidate product, a written theory (who, problem, why they pay), falsifiable hypotheses with numeric thresholds set before data collection, and a pre-committed kill/pivot rule. That is the treatment that was randomised in the RCTs.
- Expect the main payoff as more and earlier terminations; a programme in which no candidate is killed is probably not being run rigorously.
- Koning et al. is correlational with adoption timing; the 30%-100% figure is for venture-backed technology start-ups and should not be read as a causal estimate for a small company.

### Gaps
- Exact revenue effect sizes from the Camuffo RCTs were not retrieved from the full text.
- No RCT was found on customer-interview techniques specifically or on pre-sale versus build-first strategies.

## 3. Crowdfunding research and its relevance for pre-selling digital products

### Takeaway
Campaign outcomes mix demand with the creator's network: networks, preparation quality and early momentum drive success, and crowd decisions are broadly sensible. The number of backers, more than money raised, relates to later market performance, so a pre-sale should be read as a count of independent paying strangers.

### Cited Findings
- [PR] Mollick 2014: over 48,500 projects and $237M; "personal networks and underlying project quality are associated with the success of crowdfunding efforts"; "over 75% deliver products later than expected" — [W3121716941](https://openalex.org/W3121716941)
- [PR] Colombo, Franzoni & Rossi-Lamastra 2015: 669 Kickstarter projects; "contributions received in the early days of a campaign accelerate its success" and internal social capital attracts them — [W2060164253](https://openalex.org/W2060164253)
- [PR] Kuppuswamy & Bayus 2017: backer support rises as a project nears its goal and falls after the goal is reached (summary, not re-verified this session) — [W2553640711](https://openalex.org/W2553640711)
- [PR] Stanko & Henard 2017: among funded Kickstarter innovations the number of backers, rather than funds raised, relates to subsequent market performance (summary, not re-verified this session) — [W2593139483](https://openalex.org/W2593139483)
- [PR] Mollick & Nanda 2016: crowd and expert evaluations largely agree; where they differ, the crowd is more willing to fund (summary of truncated abstract) — [W3121312468](https://openalex.org/W3121312468)
- [PR] Viotto da Cruz 2018: entrepreneurs use campaign outcomes as demand information, including after unsuccessful campaigns (summary, not re-verified this session) — [W2557721229](https://openalex.org/W2557721229)
- [PR] Zhang & Liu 2012 (microloans): "Well-funded borrower listings tend to attract more funding"; lenders herd rationally by observational learning — [W1980573833](https://openalex.org/W1980573833)
- [WP] Mollick, "Delivery Rates on Kickstarter": survey of 47,188 backers; failure to deliver "around 9% of all projects, with a possible range of 5% to 14%" — [UPenn repository](https://repository.upenn.edu/mgmt_papers/210)
- [PRAC/third-party] Kickstarter lifetime success rate 41.98% across more than 651,000 launched projects as of January 2025; 376,698 unsuccessful, of which 246,351 raised between 1% and 20% of goal; highest category success rates comics 67.65%, dance 61.11%, theater 59.72% — [Statista](https://www.statista.com/statistics/235405/kickstarter-project-funding-success-rate); other sources quote 39.11% for a different date — [Kickstarter stats](https://www.kickstarter.com/help/stats) (not fetched)
- [WP] Two recent meta-studies of crowdfunding signals exist but their results were not retrieved: Hornuf & Voshaar 2024 — [W4405620457](https://openalex.org/W4405620457); Talhaoui & Brinckmann 2026 — [W7168409735](https://openalex.org/W7168409735)

### Inferences
- A pre-sale on one's own page behaves like a small all-or-nothing campaign: set a public threshold and deadline, refund below threshold, and count distinct buyers outside the warm network as the primary metric.
- Failed Kickstarter projects mostly fail by a wide margin (1%-20% of goal), which suggests pre-sale results are usually unambiguous; borderline results are the minority.
- Early-days momentum is partly manufactured by the creator's network, so compare candidates only under equal promotion effort and equal social-proof display.

### Gaps
- Kickstarter does not report a "digital products" category; category success rates for publishing, games and technology were not retrieved. No peer-reviewed study on pre-order campaigns for courses, templates or SaaS was found.
- The two signal meta-analyses above need full-text reading for effect sizes.

## 4. Customer discovery interviews (Mom Test, JTBD) and survey methods for WTP (Van Westendorp, Gabor-Granger, conjoint, BDM)

### Takeaway
Interview methods such as The Mom Test and jobs-to-be-done have no direct experimental validation; their core rule (ask about past behaviour, not hypothetical futures) is consistent with the hypothetical-bias literature. For pricing, incentive-aligned methods (BDM, incentive-aligned conjoint) match real purchases best, yet cheap hypothetical methods can still pick the right price even when they overstate volume.

### Cited Findings
- [PR] Miller et al. 2011 compared open-ended questions, choice-based conjoint (CBC), BDM and incentive-aligned CBC with real purchase data: "the BDM and ICBC approaches can pass statistical and decision-oriented tests"; "Even when the OE format and CBC analysis generate hypothetical bias, they may still lead to the right demand curves and right pricing decisions" — [W2085485552](https://openalex.org/W2085485552)
- [PR] Ding, Grewal & Liechty 2005: "incentive-aligned choice conjoint outperforms hypothetical choice conjoint in out-of-sample predictions", replicated in a second study — [W2125037695](https://openalex.org/W2125037695)
- [PR] Schmidt & Bijmolt 2020: indirect methods overestimate real WTP more than direct methods, contrary to conventional wisdom — [W2947920467](https://openalex.org/W2947920467)
- [PR, lower-tier journal] Kloss & Kunter 2016 compare the Van Westendorp Price Sensitivity Meter with contingent valuation and BDM (results truncated in the record) — [W2464890154](https://openalex.org/W2464890154)
- [PR] Hainmueller, Hangartner & Yamamoto 2015 validate conjoint and vignette designs against real-world behaviour, in a non-purchase domain — [W2166789068](https://openalex.org/W2166789068)
- [PR] Scott, Shu & Lubynsky 2020: expert ratings of venture ideas predict commercialisation in R&D-intensive sectors but not in consumer product, consumer web/mobile and enterprise software (summary, not re-verified this session) — [W2963750605](https://openalex.org/W2963750605)
- [PR] Kornish & Ulrich 2014: raw-idea quality rated by consumer purchase-intent panels is associated with later sales (summary, not re-verified this session) — [W3125813555](https://openalex.org/W3125813555)

### Inferences
- Use interviews for problem discovery and wording, not as demand evidence; use a consumer panel rating short idea descriptions to rank candidates; use a hypothetical price survey only to choose among price points; use a real-payment test to estimate volume.
- Van Westendorp and Gabor-Granger are direct hypothetical methods, so the 21% average overstatement is the relevant correction; neither has strong published validation.

### Gaps
- No empirical study testing The Mom Test or JTBD interview protocols against outcomes was found (the OpenAlex search budget ended before a dedicated search; absence is therefore not confirmed).
- No validation study of Gabor-Granger was retrieved.

## 5. Statistics of small tests: sample size, sequential testing, Bayesian rules, peeking, false-positive risk

### Takeaway
At 1%-5% base rates a classical A/B comparison needs thousands of visitors per arm, which a small company usually cannot afford, while a single-arm go/no-go test against pre-set thresholds needs only a few hundred. Peeking and low prior success rates inflate false positives well above the nominal 5%, so stop rules must be fixed in advance and surprising wins replicated.

### Cited Findings
- [PR] Johari et al. 2017: with continuous monitoring "traditional p-values and confidence intervals give unreliable inference"; they provide always-valid p-values — [W2744538883](https://openalex.org/W2744538883)
- [WP, later Management Science 2022] Berman et al.: improper optional stopping "increases the false discovery rate (FDR) from 33% to 40% among experiments p-hacked at 90% confidence"; "approximately 75% of the effects are truly null"; expected cost of a false discovery is "a loss of 1.95% in lift" — [SSRN abstract](https://papers.ssrn.com/abstract=3204791); [W2884097858](https://openalex.org/W2884097858)
- [PR] Miller & Hosanagar 2025: in nearly 2,300 e-commerce A/B tests "we found no significant evidence of p-hacking" — [W4406985965](https://openalex.org/W4406985965)
- [PR, KDD 2022; figures via Kohavi's slide deck] False positive risk at alpha 0.05 by prior success rate: Microsoft 33% success, 5.9% FPR; Bing 15%, 15.0%; Booking.com/Google Ads/Netflix 10%, 22.0%; Airbnb Search 8%, 26.4% — [slide deck](https://docs.google.com/presentation/d/18U3rlRmNMUaRvM4JlsuXidpiI8AylWBf/htmlpresent); [paper page](https://exp-platform.com/abtestingintuitionbusters/); [W7111675757](https://openalex.org/W7111675757)
- [PR] Kohavi et al. 2013: at Bing "many ideas impact key metrics by 1% and are not well estimated a-priori"; "we have a high occurrence of false positives that we address" — [W2112508839](https://openalex.org/W2112508839). Microsoft slides: about 1/3 of ideas positive, 1/3 flat, 1/3 negative — [Kohavi slides](https://ai.stanford.edu/~ronnyk/ExPThinkWeek2009Public.pdf)
- [PR] Azevedo et al. 2020: if innovation-quality tails are not too fat, "a few high-powered 'big' experiments is optimal"; with fat tails many small experiments are better — [W2801728724](https://openalex.org/W2801728724)
- [PR] Feit & Berman 2019 recast test sizing as profit maximisation for a finite population; profit-maximising samples are much smaller than hypothesis-test samples (summary, not re-verified this session) — [W2985618097](https://openalex.org/W2985618097)
- [WP] Perini et al. 2026: always-valid inference "is overly conservative"; group sequential designs with planned looks are proposed as the middle ground — [W7223119010](https://openalex.org/W7223119010)
- [PR] Lewis & Rao 2015: 25 ad experiments worth $2.8M; "The median confidence interval on return on investment is over 100 percentage points wide" — [W1745376753](https://openalex.org/W1745376753)
- [PRAC] Evan Miller advises fixing the sample size in advance and not stopping on significance — [How Not To Run an A/B Test](https://www.evanmiller.org/how-not-to-run-an-ab-test.html) (not fetched; via search summary)
- [PRAC] Meta ads 2025 averages: traffic campaigns CTR 1.71% and CPC $0.70; lead campaigns CTR 2.59% and CPC $1.92 — [WordStream 2025 benchmarks](https://www.wordstream.com/blog/facebook-ads-benchmarks-2025)

### Inferences
Own calculations (normal-approximation and exact binomial; script kept in the session scratchpad, not a published source):
- Two-arm A/B, alpha 0.05 two-sided, power 80%, visitors per arm by baseline rate and relative lift:

| Baseline | +20% | +30% | +50% | +100% |
|---|---|---|---|---|
| 1% | 42,693 | 19,827 | 7,750 | 2,319 |
| 2% | 21,109 | 9,798 | 3,826 | 1,141 |
| 3% | 13,914 | 6,455 | 2,518 | 749 |
| 5% | 8,158 | 3,780 | 1,471 | 435 |

- Single-arm go/no-go ("is true conversion at least p1 rather than at most p0", one-sided alpha about 0.10, power about 0.80):

| Kill level p0 | Go level p1 | Visitors | Go if purchases at least |
|---|---|---|---|
| 0.5% | 2% | 215 | 3 |
| 1% | 3% | 225 | 5 |
| 1% | 2% | 685 | 11 |
| 2% | 4% | 340 | 11 |
| 2% | 5% | 180 | 7 |

- Precision is poor at these sizes: 10 purchases from 500 visitors gives a 95% Wilson interval of 1.09%-3.64%; 0 from 300 still allows up to 1.26%; 20 from 1,000 gives 1.30%-3.07%.
- Simulated A/A test at a 3% base rate, 2,000 per arm, stopping at the first nominal p < 0.05: false-positive rate 5.6% with one look, 8.6% with 2, 14.5% with 5, 18.5% with 10, 23.8% with 20 looks.
- Bayesian rule with a uniform prior: 6 purchases from 300 visitors gives a 96.7% posterior probability that the rate exceeds 1%; 3 from 300 gives 64.4%; 4 from 500 gives a 12.9% probability of exceeding 1.5%.
- Budget: at the $0.70 average traffic CPC, 225-685 visitors cost roughly $160-$480 per candidate before creative costs; a properly powered A/B price test at a 2% base rate (about 2 x 3,826 visitors for a +50% lift) costs about $5,400. So the affordable design is one offer page per candidate judged against absolute thresholds, with A/B testing reserved for large expected differences.
- Because most ideas are null and priors are low, a "go" from one small test should be replicated on fresh traffic before the build decision.

### Gaps
- CPC and conversion benchmarks for Poland / Polish-language audiences and for education products were not found.
- The Intuition Busters table was confirmed only through the authors' slides, not the paper PDF.

## 6. Demand signals from data: search volume, marketplace data, communities, competition, first-mover vs fast-follower

### Takeaway
Search volume is a real but modest predictor of near-term sales, and marketplace ranks can be converted into competitor sales estimates. Existing competition is better read as evidence of demand than as a barrier: pioneers fail about half the time and unbiased tests find no first-mover advantage in profit or survival.

### Cited Findings
- [PR] Goel et al. 2010: search query volume forecasts opening-weekend box office, first-month video-game sales and song ranks "days or even weeks in advance" — [W2147634746](https://openalex.org/W2147634746)
- [PR] Choi & Varian 2012: Google Trends improves short-term forecasts of sales-type indicators (summary, not re-verified this session) — [W2323881768](https://openalex.org/W2323881768)
- [PR] Chevalier & Goolsbee 2003: public sales ranks can be mapped to quantities to estimate online demand (summary, not re-verified this session) — [W1550784417](https://openalex.org/W1550784417)
- [PR] Golder & Tellis 1993: about 500 brands in 50 categories; "almost half of market pioneers fail"; early market leaders "enter an average of 13 years after pioneers" — [W3123704062](https://openalex.org/W3123704062)
- [PR, meta-analysis] VanderWerf & Mahon 1997: tests using market share were "sharply and significantly more likely to find a first-mover advantage"; tests using none of the questioned practices find it "no more often than can be accounted for by random statistical error alone" — [W2042786149](https://openalex.org/W2042786149)
- [PR, meta-analysis] Market potential is among the strongest predictors of new product performance (Henard & Szymanski 2001) — [W2176801670](https://openalex.org/W2176801670)

### Inferences
- A cheap desk-research gate before any ad spend: (a) sustained search interest for the problem, (b) at least a few competitors with visible sales (bestseller ranks, review counts, public revenue), (c) identifiable communities where the problem is discussed. Failing all three is a reason to drop a candidate.
- Fast-follower positioning with a clear product advantage is supported; "no competitors" should raise the required strength of the paid-demand test.

### Gaps
- No peer-reviewed validation of Reddit/community mining or of keyword-tool volumes as predictors of digital-product sales was found (search budget ended before dedicated queries).
- No study quantifying "competitor revenue as a demand signal" for info products was found.

## 7. New product success factors; audience-first vs product-first; effect of audience size

### Takeaway
Meta-analyses identify product advantage, market potential, meeting customer needs, pre-development proficiency and dedicated resources as the strongest predictors, but effect sizes have weakened over time and success rates are generally below 25%. Evidence on audience size is practitioner-only and shows extremely skewed creator earnings.

### Cited Findings
- [PR, meta-analysis] Henard & Szymanski 2001: of 24 predictors, "product advantage, market potential, meeting customer needs, predevelopment task proficiencies, and dedicated resources, on average, have the most significant impact on new product performance" — [W2176801670](https://openalex.org/W2176801670)
- [PR, meta-analysis] Evanschitzky et al. 2012: 233 studies, 2,618 effect sizes; "generally weaker effect sizes than those reported by Henard and Szymanski"; "success rates are generally below 25%" — [W2135848754](https://openalex.org/W2135848754)
- [PR] Mollick 2014: personal networks are associated with crowdfunding success — [W3121716941](https://openalex.org/W3121716941)
- [PRAC, unaudited] Gumroad: median creator earned about $70 in 2020 and the top 1% of creators about 60% of the money; a 2026 vendor dataset puts the median at $72 per month across 146,271 products with fewer than 5% of creators above $1,000 per month; a product-level analysis says 0.4% of products clear $1,000 lifetime — [Silicon Florist 2021](https://siliconflorist.com/2021/01/12/what-happened-in-the-gumroad-creator-community-in-2020/); [InsightRaider](https://insightraider.com/en/data/gumroad-statistics-2026); [profitable.app](https://profitable.app/gumroad/stats)
- [PRAC, blogs] Rule of thumb for course launches: 1%-2% of the e-mail list buys, 2%-4% for engaged lists; one benchmark article reports 2.1%-4.7% — [Paige Brunton](https://www.paigebrunton.com/blog/email-list-size-online-course); [emaillistvalidation.com](https://emaillistvalidation.com/blog/online-course-launch-email-sequence-conversion-benchmarks/)

### Inferences
- With a list-to-buyer rate of 1%-2%, a 1,000-subscriber list yields 10-20 buyers per launch, so an owned audience functions both as the cheapest test panel and as the main revenue driver; without one, paid traffic costs must be budgeted into each test.
- Candidates should be scored on product advantage over existing alternatives and on market potential first, since those are the factors with meta-analytic support.

### Gaps
- No peer-reviewed study on audience-first versus product-first sequencing or on audience size versus launch revenue was found; platform reports from Kit, Podia and Teachable were not retrieved. All creator-economy numbers above are unaudited.

## 8. Portfolio / bandit approach, kill criteria, expected-value frameworks and scorecards (RICE/ICE)

### Takeaway
Theory and field evidence favour testing more candidates shallowly and shifting budget adaptively towards winners when outcomes are fat-tailed. Scorecards have support only as simple, equal-weight checklists; RICE and ICE themselves have no validation studies.

### Cited Findings
- [PR] Azevedo et al. 2020: with fat-tailed idea quality, many low-powered experiments beat a few big ones — [W2801728724](https://openalex.org/W2801728724)
- [PR] Schwartz, Bradlow & Fader 2017: bandit allocation of display ads improved customer acquisition over a balanced experiment (summary, not re-verified this session) — [W3121632328](https://openalex.org/W3121632328); Scott 2010 describes Thompson sampling — [W2158125716](https://openalex.org/W2158125716)
- [PR] Åstebro & Elhedhli 2006: experts score 37 characteristics; a conjunctive count of good and bad cues "achieves a 91.8% forecasting accuracy of the experts' correct forecasts" — [W2038224823](https://openalex.org/W2038224823)
- [PR] Dawes 1979: unit-weighted linear models outperform intuitive judgement — [W2056418346](https://openalex.org/W2056418346)
- [PR] Camuffo et al. 2024: the scientific approach raises idea termination — [W4393152018](https://openalex.org/W4393152018)
- [PR] Terwiesch et al. 2026: LLM-generated ideas are "7 times more likely to rank in the top 10%" by purchase intent but less diverse — [W7170184151](https://openalex.org/W7170184151)
- [PRAC, opinion] Critiques of RICE: multiplying factors multiplies uncertainty so the score "only has the same precision as the least precise factor"; confidence terms systematically favour small projects — [Peter Hilton](https://hilton.org.uk/blog/product-arithmetic); [A Smart Bear](https://longform.asmartbear.com/confidence/)
- [PRAC] Strategyzer suggests about one experiment per week and reassessing after roughly 12 data points — [Strategyzer](https://www.strategyzer.com/library/how-to-track-the-progress-of-business-experiments)

### Inferences
- For 2-5 candidates: equal small budgets in round one, then reallocate in proportion to each candidate's posterior probability of being best, and kill any candidate whose posterior probability of exceeding the "go" conversion falls below a pre-set level (for example 10%).
- Use an equal-weight scorecard built from the meta-analytic factors (advantage, market potential, need fit, evidence strength) only to choose which candidates enter testing, not to decide what gets built.
- Opportunity cost argues for time-boxed tests: each week spent on a null candidate delays the others, and most candidates are expected to be null.

### Gaps
- No empirical validation of RICE or ICE scores against outcomes was found. No published kill-criteria benchmarks for digital products were found.

## 9. Generative AI: building cost and time-to-test, and buyers' willingness to pay for AI-generated content

### Takeaway
Experiments show large speed gains on bounded tasks (writing 40% faster, a coding task 55.8% faster, consulting tasks 25.1% faster) but uneven business outcomes, so AI lowers the cost of prototypes and test assets more reliably than it raises revenue. Evidence on AI disclosure is mixed: labels cut perceived authenticity and stated valuations in some studies, while incentivised measures sometimes show no drop.

### Cited Findings
- [PR] Noy & Zhang 2023: 453 professionals; "average time taken decreased by 40% and output quality rose by 18%" — [W4384154918](https://openalex.org/W4384154918)
- [WP] Peng et al. 2023: Copilot users completed the task "55.8% faster" — [W4320854981](https://openalex.org/W4320854981)
- [PR] Dell'Acqua et al. 2026: 758 consultants; AI users completed "12.2% more tasks" and "25.1% more quickly"; outside the frontier they were "19% less likely to produce correct solutions" — [W7135096569](https://openalex.org/W7135096569)
- [PR] Brynjolfsson, Li & Raymond 2025: 5,172 support agents; productivity up "15% on average" — [W4407142724](https://openalex.org/W4407142724)
- [WP, field experiment] Otis et al. 2023: no significant average effect of a GPT-4 assistant on revenue and profit; "low performers did nearly 10% worse", "high performers may have benefited by over 15%" — [W4390050383](https://openalex.org/W4390050383)
- [PR] Zhang & Gosline 2023: revealing the source "reduces—but does not reverse—the perceived quality gap"; knowing a human expert made it raises perceived quality, knowing AI was involved "does not affect its perceived quality" — [W4389094616](https://openalex.org/W4389094616)
- [PR] Shi & Jiang 2026: AI disclosure labels raise attitudes and purchase intention via novelty and lower them via reduced authenticity; effects are more favourable for utilitarian products — [W7127040071](https://openalex.org/W7127040071)
- [WP] Abel & Johnson (IZA, 2025): incentivised experiment, 654 participants; willingness to pay and to work "did not differ between the labels", although almost 40% said afterwards they would have paid less for AI writing — [IZA summary](https://newsroom.iza.org/en/archive/opinion/ai-bias-for-creative-writing)
- [PRAC summary of a study] Music: once disclosed as AI-generated, listeners' desire to relisten and willingness to pay decrease — [ProMarket](https://www.promarket.org/2026/08/27/consumers-prefer-ai-music-until-theyre-told-its-ai/)
- [WP] Brand, Israeli & Ngwe 2023 explore LLM "respondents" for WTP estimation — [W4361855702](https://openalex.org/W4361855702)

### Inferences
- Cheaper building shifts the bottleneck from construction to selection and distribution, which raises the relative value of demand tests and makes "build a rough version and sell it" a viable test for templates and small tools.
- For authored knowledge products (courses, ebooks) visible human expertise is the safer positioning; for utilitarian tools an AI label is less risky.
- Stated devaluation of AI content is itself subject to hypothetical bias; a real-price split test of disclosure wording would be more informative than a survey.

### Gaps
- No 2024-2026 study measuring end-to-end time or cost to launch a digital product with AI was found; lab task speed-ups may not transfer. No percentage estimate of a WTP discount for disclosed AI-generated courses or ebooks was found.

## 10. Common failure reasons and base rates of success

### Takeaway
"No market need" is the most cited or second most cited failure reason in founder post-mortems (35%-42% depending on the edition), and base rates for small digital products are low and heavily skewed. All of this is practitioner data with strong self-selection.

### Cited Findings
- [PRAC] CB Insights post-mortems: the 101-startup edition lists no market need 42%, ran out of cash 29%, got outcompeted 19%, lack of business model 17%; a later edition (111 post-mortems) lists ran out of cash / failed to raise 38%, no market need 35%, outcompeted 20% — [Fortune 2014](https://fortune.com/2014/09/25/why-startups-fail-according-to-their-founders/); [SmartCompany](https://www.smartcompany.com.au/startupsmart/analysis/startups-fail-founders-capital/); [CB Insights](https://www.cbinsights.com/blog/startup-failure-reasons-top/)
- [PR] New product success rates "are generally below 25%" (Evanschitzky et al. 2012) — [W2135848754](https://openalex.org/W2135848754)
- [PR] Berman et al.: about 75% of tested effects in A/B experiments are truly null — [SSRN](https://papers.ssrn.com/abstract=3204791)
- [PRAC, unaudited] Indie SaaS: a 2026 report on 3,787 revenue-generating products gives a median under $145 per month, 6.1% reaching $10k MRR and 0.58% reaching $100k MRR; share clearing $1k MRR about 50% for 2020-2022 launches versus 23.5% for 2025 launches; another analysis of about 10,150 products found 2.41% reached roughly $100k ARR — [BigIdeasDB](https://bigideasdb.com/state-of-indie-saas-revenue-2026); [TechStartups](https://techstartups.com/2026/09/28/what-percentage-of-indie-hacker-products-make-100k-in-arr/)
- [PRAC, unaudited] Gumroad median creator about $70 per year in 2020 — [Silicon Florist](https://siliconflorist.com/2021/01/12/what-happened-in-the-gumroad-creator-community-in-2020/)

### Inferences
- With prior success odds this low, a portfolio of 2-5 candidates should be planned on the assumption that most will be killed; the false-positive-risk logic in section 5 applies directly (low prior, small samples).
- Post-mortem percentages are founders' self-diagnoses with multiple reasons per company, and the indie datasets include only products that earn revenue, so true base rates are lower than quoted.

### Gaps
- The 2021 CB Insights report percentages could not be confirmed from the primary source. No audited dataset of info-product (course/ebook) success rates was found; MicroConf's State of Independent SaaS figures were not retrieved.
