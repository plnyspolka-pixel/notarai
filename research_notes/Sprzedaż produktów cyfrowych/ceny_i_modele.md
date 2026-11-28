# Pricing and monetization models for digital products: evidence base (as of November 2026)

Scope: information goods, online courses, ebooks, templates, software, memberships. Companion registry: `rejestr_ceny.jsonl` (83 works, IDs RC001-RC083, every OpenAlex ID taken from a tool result).

How to read the evidence labels used below:
- **[PR-meta]** peer-reviewed meta-analysis; **[PR-field]** peer-reviewed field experiment or quasi-experiment on real purchases; **[PR-lab]** peer-reviewed lab/online experiment; **[PR-obs]** peer-reviewed observational; **[PR-theory]** analytical model; **[WP]** working paper; **[VENDOR]** vendor or practitioner data (not peer reviewed, usually correlational, sample self-selected).
- "Abstract n/a" means OpenAlex returned no abstract and the number was taken from the publisher abstract via a secondary index or press office; those are flagged individually.
- Years in OpenAlex sometimes reflect the working-paper date (e.g. Goli et al. listed 2019, published JMR 2022; Aral and Dhillon listed 2016, published Management Science 2021). Journal years are given where known.

## 1. Information-goods economics: versioning, bundling vs unbundling, zero marginal cost, price discrimination

### Takeaway
Theory supports bundling many zero-marginal-cost items at one price and offering a flat fee, but it does not support tiering by default: in baseline models a single version is optimal and tiers pay only when they pull in a distinct segment. Field evidence on tiers for content is thin; the one clean field experiment found that adding a second paid option raised sales of the existing one.

### Cited Findings
- [PR-theory, 1999] Bundling very large numbers of unrelated information goods at a fixed price "can be surprisingly profitable", because the law of large numbers makes bundle valuations easier to predict than valuations of single goods. — [Bakos and Brynjolfsson, Management Science 1999](https://openalex.org/W3122946301)
- [PR-theory, 2008] For goods whose variable cost is invariant with quality (including zero variable cost), the authors derive a simple decision rule for when adding lower-quality versions is optimal; versioning is not always optimal. — [Bhargava and Choudhary, Management Science 2008](https://openalex.org/W2166988709)
- [PR-theory, 2014] In a baseline model where consumers differ in taste for quality, "an information goods monopolist only offers one version", which the authors note differs from practice; extra features (e.g. group tastes) are needed to make several versions optimal. — [Wei and Nault, POM 2014](https://openalex.org/W2042913341)
- [PR-theory, 2007] Absent piracy a single version is the optimal strategy in the model; versioning becomes useful as an instrument against piracy. — [Wu and Chen, Operations Research 2007](https://openalex.org/W2117114641)
- [PR-theory, 2000] With network externalities a monopolist with multiple existing products offers exactly two distinct qualities. — [Jing, ICIS 2000](https://openalex.org/W1763128083)
- [PR-theory, 2004] Offering fixed-fee pricing in addition to nonlinear usage-based pricing "is always profit improving in the presence of nonzero transaction costs", and in some markets a pure fixed fee is optimal. — [Sundararajan, Management Science 2004](https://openalex.org/W2104347355)
- [PR-review, 2002] Classification of bundling strategies (pure vs mixed, price vs product bundling) with a framework for when each is optimal. — [Stremersch and Tellis, Journal of Marketing 2002](https://openalex.org/W3125309408)
- [PR-obs, 2010] Music unbundling studied with weekly digital-track, digital-album and physical-album sales, January 2005 to April 2007, for titles by more than 200 artists; the paper examines the sales effect of unbundling and which bundle characteristics drive it (effect size not in the OpenAlex abstract). — [Elberse, Journal of Marketing 2010](https://openalex.org/W2174371867)
- [PR-field, 2018] Randomized field experiment at an online content provider (free PDF, paid paperback): paperback titles accompanied by an additional premium version (e-book or hardcover) had higher sales than control; effect stronger for more popular or cheaper titles, and for e-books priced closer to the paperback; compromise and attraction effects identified in individual choices. — [Gu, Kannan and Ma, Journal of Marketing 2018](https://openalex.org/W2897722974)
- [PR-field, JPE 2023] Price discrimination: in a randomized pricing experiment at a digital firm, "unexercised market power increases profit by 55%"; personalization adds a further 19% (86% relative to the non-optimized price); over 60% of consumers benefit although total consumer surplus declines. — [Dubé and Misra, Journal of Political Economy](https://openalex.org/W4280549099)
- [Practitioner, 1998] Statement of the versioning idea (self-selection by willingness to pay); no effect sizes. — [Shapiro and Varian, HBR 1998](https://openalex.org/W1550473992)

### Inferences
- For a template pack or course library, a bundle is the theoretically favoured default; mixed bundling (bundle plus items sold separately) keeps single-item buyers.
- Good-better-best is a hypothesis to test, not a law. A defensible minimal design is two paid options, since the only field evidence on content shows an added premium option lifting the target option.
- Zero marginal cost removes the cost floor, so the binding constraints are willingness to pay and cannibalisation between versions.

### Gaps
- No peer-reviewed field experiment was found that compares one tier vs three tiers on revenue for courses, ebooks or templates.
- The bundle-size effect in Bakos and Brynjolfsson is asymptotic; no evidence was found on how many items a small seller needs before the effect appears.

## 2. Freemium, free trials, free samples, paywalls

### Takeaway
The strongest field result is that shorter free trials beat 30-day trials on acquisition, retention and profit in SaaS, and that trial-acquired customers are worth much less. Paywall and free-content levers have large, measurable effects on traffic and subscriptions, with the net revenue sign depending on context. Conversion benchmarks from vendors exist but are correlational.

### Cited Findings
- [PR-field, Management Science 2023] Large-scale SaaS field experiment: "on average, shorter trial lengths (surprisingly) maximize customer acquisition, retention, and profitability"; long inactivity at the end of the trial is associated with lower conversion; a personalised policy improves subscriptions by 6.8% over a uniform 30-day policy; experienced users benefit from longer trials, beginners from shorter. — [Yoganarasimhan, Barzegary and Pani](https://openalex.org/W4297830788)
- [WP, 2020] The working-paper version of the same study (users randomised to 7, 14 or 30 days) reports the 7-day trial for all as the best uniform policy, with a 5.59% increase in subscriptions; this figure is from the arXiv version and should be checked against the journal text before quoting. — [arXiv 2006.13420](https://arxiv.org/pdf/2006.13420)
- [PR-obs, 2015] Digital TV panel data: average customer lifetime value of free-trial customers is 59% lower than that of regular customers; they are more responsive to marketing communication and to their own usage. — [Datta, Foubert and van Heerde, JMR 2015](https://openalex.org/W2787323089); figure confirmed in the [Tilburg record](https://research.tilburguniversity.edu/en/publications/the-challenge-of-retaining-customers-acquired-with-free-trials/)
- [PR-theory, 2011 and 2015] A time-locked trial trades reduced uncertainty against demand cannibalisation; a hybrid trial (limited features plus time lock) weakly dominates pure variants in the model. — [Cheng and Liu, ISR 2011](https://openalex.org/W3123120761); [Cheng, Li and Liu, POM 2015](https://openalex.org/W2088246205)
- [PR-obs, 2014] Panel of 711 ranked Google Play apps: a free version is positively associated with paid-app sales, and a high review rating of the free version leads to higher paid sales. — [Liu, Au and Choi, JMIS 2014](https://openalex.org/W2015518777)
- [PR-obs, 2017] Free versions and the performance of paid apps for small, unknown developers; a counterpoint to the above (direction and size not in the OpenAlex abstract). — [Arora, ter Hofstede and Mahajan, Journal of Marketing 2017](https://openalex.org/W2735157213)
- [PR, 2019] Free-sample design for digital content and SaaS framed as a revenue-maximisation problem. — [Li, Jain and Kannan, JMR 2019](https://openalex.org/W2940771723)
- [PR-obs, 2013; abstract n/a] Three local newspapers: "a 51 percent drop in visits after the introduction of a paywall and a far larger drop for younger readers". — [Chiou and Tucker, Information Economics and Policy 2013](https://openalex.org/W2075974558); figure from [MIT DSpace abstract](https://dspace.mit.edu/handle/1721.1/110528)
- [PR-obs, 2016] Firms with both free and paid content "should offer more free - and not less" content in periods of high demand. — [Lambrecht and Misra, Management Science 2016](https://openalex.org/W3122597397)
- [PR-obs, Management Science 2021; abstract n/a] New York Times quasi-experiments: paywall design has an economically significant effect on content demand, subscriptions and net revenue; a University of Michigan summary cites a 9.9% decline in content demand over the seven months studied (secondary source; subscription effect size not retrieved). — [Aral and Dhillon](https://openalex.org/W3015521008); [U-M Record](https://record.umich.edu/articles/u-m-researcher-says-online-news-needs-a-new-pay-model)
- [PR-obs, 2008] Moving from free to "free and fee": long-term revenue loss arises from attracting fewer free subscribers, alongside gains from paid subscribers. — [Pauwels and Weiss, Journal of Marketing 2008](https://openalex.org/W2168591670)
- [PR-obs, 2016] The NYT paywall rollout changed word-of-mouth via social media, a main channel for attracting new visitors. — [Oh, Animesh and Pinsonneault, MIS Quarterly 2016](https://openalex.org/W2339364093)
- [PR-lab, 2019] Freemium conversion is low partly because free options are valued disproportionately (zero-price effect). — [Niemand, Mai and Kraus, Psychology and Marketing 2019](https://openalex.org/W2938736700)
- [VENDOR, 2026] RevenueCat State of Subscription Apps 2026 (mobile apps): median trial-to-paid conversion 42.5% for trials of 17-32 days vs 25.5% for trials of four days or less; hard paywalls show a 10.7% median day-35 conversion-to-paid rate vs 2.1% for freemium apps (the retrieved summary labels this "trial-to-paid"; check the metric definition in the report), with near-identical one-year retention (27% vs 28%). RevenueCat itself notes this shows what is common, not which trial length performs best. — [RevenueCat report](https://www.revenuecat.com/state-of-subscription-apps-2026/); [RevenueCat benchmarks blog](https://revenuecat.com/blog/growth/subscription-app-trends-benchmarks-2026)
- [VENDOR, 2023] Lenny's Newsletter and Kyle Poyar (1,000+ products, six-month window): self-serve freemium free-to-paid 3-5% is good and 6-8% great; free trial 8-12% good and 15-25% great; visitor sign-up rates are lower for trials than freemium (5% vs 9%). — [Lenny's Newsletter](https://www.lennysnewsletter.com/p/what-is-a-good-free-to-paid-conversion)
- [VENDOR, unverified origin] Opt-out trials (card required) convert at 48.8% vs 18.2% for opt-in trials, as quoted by Crazy Egg; the primary source could not be verified and the same page contains a mislabelled table. — [Crazy Egg](https://www.crazyegg.com/blog/free-to-paid-conversion-rate/)

### Inferences
- The peer-reviewed trial result (shorter is better) and the RevenueCat correlation (longer trials convert better) conflict. The first is randomised in one SaaS firm; the second is cross-sectional across apps that chose their own trial length, so selection is the likely explanation. Treat trial length as a test variable with a short trial as the prior.
- Card-required trials raise trial-to-paid conversion but lower trial starts; only end-to-end visitor-to-paid conversion and refund rate settle the comparison.
- For a one-off digital product (ebook, template) a time-limited trial is ill-suited; a partial sample or preview is the analogue.

### Gaps
- No peer-reviewed randomised comparison of credit-card-required vs no-card trials was retrieved.
- No peer-reviewed field evidence on metered vs hard paywalls for small creators; the paywall literature is on newspapers.
- Spotify free-tier and Duolingo evidence: no scholarly pricing study retrieved (see section 7).

## 3. Subscription vs one-time vs lifetime; annual vs monthly; churn; flat-rate bias; pay-per-use

### Takeaway
Buyers systematically prefer and overpay for flat rates, and a large share of subscription revenue comes from inertia. Forced auto-renewal, however, deters sign-ups enough to reduce subscribers over two years in the one large field experiment. Evidence on lifetime deals and on annual vs monthly plans is vendor-only.

### Cited Findings
- [PR-obs, 2006] Many users prefer a flat rate although pay-per-use would be cheaper for them (flat-rate bias); some show the reverse bias. — [Lambrecht and Skiera, JMR 2006](https://openalex.org/W2111073395)
- [PR-obs, 2006] 7,752 members of three US health clubs over three years: members on a flat monthly fee of over $70 attend on average 4.3 times a month, paying more than $17 per expected visit. — [DellaVigna and Malmendier, AER 2006](https://openalex.org/W2026559010)
- [PR-obs, 2025] Payment-card data: months in which cards are replaced, when active renewal is required, show much higher cancellation; the authors estimate that these cancellation frictions "roughly double" the relevant subscription outcome (the OpenAlex abstract is truncated at that point; verify the object before quoting). — [Einav, Klopack and Mahoney, AER 2025](https://openalex.org/W4409963015)
- [WP/registered RCT, 2022-2023] Two million readers of a European newspaper offered auto-renewing or auto-cancelling contracts: "offering auto-renewing contracts lowers subscriptions by 24% and reduces subscribers by 10% over two years; most of the inert readers preempt inertia". — [Miller, Sahni and Strulov-Shlain, SSRN](https://openalex.org/W4220938497); [AEA RCT registry entry](https://openalex.org/W4367041099)
- [PR-field, 2002] Market experiment on a service with a monthly access fee plus per-minute charge: usage and retention depend on both absolute and relative prices; a low-usage customer may later find the monthly fee unjustified. — [Danaher, Marketing Science 2002](https://openalex.org/W2099926492)
- [PR-lab, 2021] Experienced purchasing professionals also show a flat-rate bias across business services (four experiments). — [Kienzler, Kowalkowski and Kindström, Journal of Business Research 2021](https://openalex.org/W3157136923)
- [VENDOR, 2019] ProfitWell (about 2,500 subscription companies): companies with fully annual contracts showed about 80% lower churn than monthly-only companies; correlational, and the page is flagged by Paddle as possibly outdated. — [Paddle/ProfitWell](https://paddle.com/studios/shows/profitwell-report/annual-vs-monthly)
- [VENDOR, 2026] RevenueCat 2026: twelve-month retention for non-AI apps 9.5% on monthly plans vs 30.7% on annual plans; higher-priced apps show 23% median retention vs 36% for lower-priced apps. — [RevenueCat benchmarks blog](https://revenuecat.com/blog/growth/subscription-app-trends-benchmarks-2026)

### Inferences
- Unlimited or flat access is easier to sell than metered access; this supports a one-time price or a simple membership over usage billing.
- Annual plans retain better in vendor data, but the comparison confounds contract length (one cancellation opportunity instead of twelve) with customer self-selection.
- Offering a non-renewing option is a credible test arm: it may raise sign-ups and, per the newspaper experiment, need not lose subscribers long term.

### Gaps
- No peer-reviewed evidence on lifetime deals (one-time payment for permanent access) vs subscription was found.
- No peer-reviewed estimate of the optimal annual-plan discount.
- Churn benchmarks specific to creator memberships or course subscriptions were not found.

## 4. Behavioural pricing levers

### Takeaway
Most classic pricing "tricks" have small or fragile effects once tested at scale or corrected for publication bias. The levers with real-purchase evidence are 9-endings and the left-digit threshold (small but real), late disclosure of fees (large but legally risky), and credible reference prices. Decoys and arbitrary anchors are unreliable.

### Cited Findings
**Charm prices and left-digit bias**
- [PR-meta, 2023] Preregistered meta-analysis (k = 69 studies, m = 362 effect sizes, N = 40,541): just-below vs round prices increase purchase decisions (g = 0.13, 95% CI [0.01, 0.25]), improve price image (g = 0.28), have no effect on perceived quality (g = 0.00, p = 0.96) and are more often underestimated (g = 0.67); "effect sizes are small and highly heterogenous" and bias corrections suggest smaller, at times non-significant true effects. — [Troll, Frankenbach, Friese and Loschelder, Journal of Consumer Psychology](https://openalex.org/W4366422183)
- [PR-field, 2003; abstract n/a] Three catalogue field experiments: a $9 ending increased demand in all three, more for items the retailer had not sold before, and less when "Sale" cues were used (direction from the Kellogg summary; percentages not retrieved). — [Anderson and Simester, QME 2003](https://openalex.org/W1506265753); [Kellogg summary](https://www.kellogg.northwestern.edu/faculty/research/detail/2003/effects-of-9-price-endings-on-retail-sales-evidence)
- [PR-obs, 2023] Scanner data, 3,500 products, 25 US chains: consumers respond to a one-cent increase from a 99-ending price "as if it were more than a twenty-cent increase". — [Strulov-Shlain, Review of Economic Studies](https://openalex.org/W4313389595)
- [WP, 2013] A field test where removing .99 seemed to raise sales, an effect that did not survive a fuller specification; offered as a warning about confounds. — [Filippin](https://openalex.org/W288191843)
- No peer-reviewed evidence was found for a specific advantage of 7-endings (e.g. 47, 97) over 9-endings.

**Decoy, compromise and anchoring**
- [PR-lab, 2014] "Ninety-one attempts to produce an attraction effect (23 product classes, 73 decoyed choice sets) produced only 11 reliable effects"; verbal and pictorial descriptions substantially reduced effects. — [Yang and Lynn, JMR 2014](https://openalex.org/W2150337234)
- [PR-lab, 2014] The attraction effect "may be restricted to stylized product representations" with numeric dimensions. — [Frederick, Lee and Baskin, JMR 2014](https://openalex.org/W2043499048)
- [PR-meta, 1995] Earlier meta-analysis: decoys reduce shares of lower-quality competitors more than higher-quality ones. — [Heath and Chatterjee, JCR 1995](https://openalex.org/W2109020490)
- [PR-lab, 1992] Extremeness aversion: an option gains when it is intermediate in the set. — [Simonson and Tversky, JMR 1992](https://openalex.org/W2011747645)
- [PR-lab, 2014] New evidence on anchoring in economic valuations with a framework for why initial findings warrant caution. — [Maniadis, Tufano and List, AER 2014](https://openalex.org/W2056125794)

**Price-quality inference**
- [PR-meta, 1989] For consumer products the price-perceived quality relationship is positive and statistically significant. — [Rao and Monroe, JMR 1989](https://openalex.org/W2012238114)
- [PR-meta, 2007; abstract n/a] Updated meta-analytic review of the price-perceived quality relationship and its determinants. — [Völckner and Hofmann, Marketing Letters 2007](https://openalex.org/W2039390112)
- [PR-lab, 2005] Consumers paying a discounted price may derive less actual benefit from a product (three experiments). — [Shiv, Carmon and Ariely, JMR 2005](https://openalex.org/W3123020128)

**Partitioned and drip pricing**
- [PR-meta, 2018] Partitioning can raise preference (lower recalled price) or lower it (unfavourable surcharge evaluation); direction depends on presentation moderators such as whether the total is shown. The underlying dissertation covers 149 observations from 43 studies in 27 papers (N = 12,878). — [Abraham and Hamilton, JMR 2018](https://openalex.org/W4255489062); [dissertation](https://drum.lib.umd.edu/handle/1903/16560)
- [PR-field, 2021] StubHub field experiment: disclosing fees upfront "reduces both the quantity and quality of purchases"; in the NBER version the quality effect accounts for at least 28% of the revenue decline and effects persist for experienced users. — [Blake, Moshary, Sweeney and Tadelis, Marketing Science 2021](https://openalex.org/W2898806675); [NBER w25186](https://openalex.org/W3162433802)

**Reference prices, discounts, coupons**
- [PR-meta, 2002; abstract n/a] Meta-analysis of price-presentation effects on perceived savings (outcome is perception, not sales). — [Krishna, Briesch, Lehmann and Yuan](https://openalex.org/W2090656822)
- [WP, HBS; secondary summary] Outlet-retail data: for every $1 increase in the posted "original price", consumers were willing to pay on average an extra 77 cents; frequent shoppers were least affected. — [HBS Working Knowledge on Ngwe](https://www.library.hbs.edu/working-knowledge/bargain-hunters-beware-a-store-s-original-price-might-not-be-after-all)
- [PR-field, 2004] Three large catalogue field experiments: deeper discounts increased future purchases by first-time customers, with a different long-run effect for established customers (the truncated abstract does not state the sign; the paper is generally cited for a negative effect). — [Anderson and Simester, Marketing Science 2004](https://openalex.org/W2138560722)

**Temporal reframing**
- [PR-lab, 1998] "Pennies-a-day" reframing works through comparison to small routine expenses. — [Gourville, JCR 1998](https://openalex.org/W2029136992)
- [PR-lab, 2024] Temporal reframing can intensify feelings of being misled when the frame does not match the category's usual pricing period. — [Chung and Sheinin, Journal of Consumer Behaviour 2024](https://openalex.org/W4401969200)

**Zero-price effect**
- [PR-lab, 2007] People perceive the benefits of free products as higher rather than merely subtracting cost. — [Shampanier, Mazar and Ariely, Marketing Science 2007](https://openalex.org/W2147664728)
- [PR-lab, 2022] Five studies: zero vs low price boosts demand when incidental costs are low but lowers it when they are high (e.g. time cost of a class). — [Fan, Cai and Bodenhausen, JAMS 2022](https://openalex.org/W4212932351)
- [PR-lab, 2013] Willingness to pay after a promotion is higher when the item had been free than when it had been deeply discounted. — [Palmeira and Srivastava, JCR 2013](https://openalex.org/W2099165443)

**Pay-what-you-want (PWYW)**
- [PR-field, 2010] N = 113,047 souvenir-photo customers, fixed price vs PWYW crossed with a half-to-charity variant; at a fixed price the charity component only slightly increased demand, while under PWYW the outcome differed. — [Gneezy, Gneezy, Nelson and Brown, Science 2010](https://openalex.org/W2055274915)
- [PR-field, 2009] Three field studies: PWYW prices paid are significantly greater than zero. — [Kim, Natter and Spann, Journal of Marketing 2009](https://openalex.org/W2164355801)
- [PR-field, 2012] Three field experiments: when allowed to name the price, "fewer consumers choose to buy it than when the price is fixed and low", driven by self-image concerns. — [Gneezy, Gneezy, Riener and Nelson, PNAS 2012](https://openalex.org/W2043074681)
- [PR-obs, 2009; digital] Magnatune online music, buyer chooses within $5-$18: "on average customers pay $8.20", above the $5 minimum and the recommended $8. — [Regner and Barria, JEBO 2009](https://openalex.org/W1971665890); [working-paper abstract](https://openalex.org/W2268178829)
- [PR-review, 2017 and 2024] Reviews of 72 and 106 PWYW publications; practical applications have produced mixed results. — [Gerpott 2017](https://openalex.org/W2555482051); [Güzel et al. 2024](https://openalex.org/W4405031204)
- [PR-lab, 2023] People pay more after than before receiving the product when value is high; mitigated or reversed when value is low. — [KC, Mak and Ofek, Journal of Marketing 2023](https://openalex.org/W4309324990)
- [VENDOR] itch.io creator docs: 30% of all money spent on itch.io is paid above the minimum. — [itch.io docs](https://itch.io/docs/creators/pricing)
- [VENDOR, weak] A third-party analysis of 146,271 Gumroad products claims PWYW products get about 8% more sales while average price falls from $66 to $18; methodology undisclosed. — [InsightRaider](https://insightraider.com/fr/data/gumroad-statistics-2026)

### Inferences
- Ranked by evidence quality for a small digital seller: (1) stay just below a round threshold; (2) show one all-inclusive price; (3) use a credible reference price only if it is a genuine prior price; (4) treat decoys, arbitrary anchors and per-day reframing as optional test arms with low prior.
- PWYW with a minimum and a suggested price is the only PWYW variant with digital field support; unbounded PWYW is a reach tool.
- Drip pricing raises revenue in the field but conflicts with EU consumer-law expectations on total price display; it is listed as evidence of effect size, not as a recommendation.

### Gaps
- No evidence retrieved on tiered (volume) discounts or on announcing price increases in advance for digital products; these questions remain unanswered.
- No Gumroad-published PWYW statistics were found.
- Effect sizes for strike-through discounts on digital goods specifically were not found; the Ngwe figure is from physical outlet retail and from a secondary summary.

## 5. Price level, perceived quality and engagement or completion in courses

### Takeaway
Paying does raise engagement in online courses, but the sunk-cost component is short-lived (weeks), and meta-analytic evidence shows the effect fading over time. A lasting goal such as a certificate matters more than the amount paid.

### Cited Findings
- [PR-obs, JMR 2022; abstract n/a] Coursera, over 70 courses: sunk-cost and certificate effects raise engagement by about 17-20% and 8-9% respectively; the sunk-cost effect lasts only a few weeks after payment, while the certificate effect lasts until the passing grade. — [Goli, Chintagunta and Sriram](https://openalex.org/W3157101706); figures from the [journal abstract index](https://www.x-mol.com/paper/1386872421005418496); the university press office reported a 10-12% combined rise from an earlier draft: [U-M Record](https://record.umich.edu/articles/research-shows-certificates-boost-mooc-completion-rates)
- [PR-meta, 2014] 98 effect sizes: "clear evidence that the sunk-cost effect emerges", with size contingent on decision type; "the sunk-cost effect is attenuated by time in utilization decisions"; older adults are less susceptible. — [Roth, Robbert and Straus, Business Research](https://openalex.org/W2060738052)
- [PR-lab, 1998] Payment depreciation: attention to a sunk cost fades as payment recedes in time. — [Gourville and Soman, JCR 1998](https://openalex.org/W2031538264)
- [PR-field, 2010] Zambia door-to-door experiment built to separate screening (higher prices select high-use buyers) from a psychological sunk-cost effect; the OpenAlex abstract is truncated before stating which effect was found. — [Ashraf, Berry and Shapiro, AER 2010](https://openalex.org/W3123121782)
- [PR-lab, 1985; abstract n/a] Original sunk-cost demonstrations. — [Arkes and Blumer 1985](https://openalex.org/W2006397401)
- [Conference paper, 2019; different dataset] A HarvardX/MITx study cites about 7.7% completion for all participants vs about 60% for verified (paying) participants; this is a selection-laden comparison, not a causal effect. — [Ruipérez-Valiente et al., L@S 2019](https://webs.um.es/jruiperez/papers/conferences/2019_L@S_FreeCertificates.pdf)

### Inferences
- Higher price selects more motivated buyers (screening) more reliably than it causes extra effort; raw completion gaps between paying and non-paying learners overstate the causal effect.
- To sustain engagement, recurring commitment points (instalments, milestones, a credential) fit the evidence better than a single high upfront price.

### Gaps
- No replication of the sunk-cost effect on course completion with randomised prices was found; Goli et al. is observational with identification from platform changes.
- No evidence on whether price level changes completion for self-paced courses sold by individual creators.

## 6. Money-back guarantees and return policies

### Takeaway
Across the meta-analysis, lenient return policies raise purchases more than returns, and the dimensions differ: refund amount and low effort drive purchases, while longer return windows reduce returns. None of this evidence is specific to digital goods that cannot be handed back.

### Cited Findings
- [PR-meta, Journal of Retailing 2016; abstract n/a] Leniency increases purchase more than return; money and effort leniency increase purchase; time and exchange leniency reduce returns; scope leniency increases returns. Sources differ on the number of papers pooled (21 in the abstract, 22 in press releases). — [Janakiraman, Syrdal and Freling](https://openalex.org/W2183705853); [RePEc abstract](https://econpapers.repec.org/RePEc:eee:jouret:v:92:y:2016:i:2:p:226-235); [UT Dallas summary](https://news.utdallas.edu/?p=11491)
- [PR-theory, 1995] Money-back guarantees can signal quality when buyers cannot inspect before purchase; transaction costs of returning are central. — [Moorthy and Srinivasan, Marketing Science 1995](https://openalex.org/W2021573668)
- [PR-theory, 2013] Model of price, quantity and refund amount under full or partial money-back guarantees. — [Akçay, Boyacı and Zhang, POM 2013](https://openalex.org/W2050529056)

### Inferences
- A full-refund, low-hassle guarantee with a long window is the evidence-consistent default; a longer window should not raise refunds.
- For a downloadable product the signalling value is weaker because honouring a refund costs the seller little, and abuse (keep the file, take the refund) is possible; measure refund rate as a primary test outcome.

### Gaps
- No field experiment on guarantees for ebooks, templates or courses was found; effect on sales vs refunds for digital goods remains unquantified.

## 7. Price experimentation methods and what large-scale experiments show

### Takeaway
Stated willingness to pay overstates real willingness to pay by about a fifth, and conjoint is not more accurate than direct questions. Real-purchase price tests are the benchmark, and the best-documented one found that the firm had been pricing far too low.

### Cited Findings
- [PR-meta, JAMS 2020] 77 studies in 47 papers, 115 effect sizes: average hypothetical bias is about 21%; "indirect methods overestimate real WTP significantly more than direct methods"; bias is larger for higher-priced and specialty goods. — [Schmidt and Bijmolt](https://openalex.org/W2947920467); [Springer](https://link.springer.com/article/10.1007/s11747-019-00666-6)
- [PR, 2011] Open-ended questions, choice-based conjoint, BDM and incentive-aligned conjoint compared against real purchase data. — [Miller, Hofstetter, Krohmer and Zhang, JMR 2011](https://openalex.org/W2085485552)
- [PR-meta, 2005] Updated empirical generalisations on price elasticity and its determinants. — [Bijmolt, van Heerde and Pieters, JMR 2005](https://openalex.org/W2153205326)
- [PR-field, JPE 2023] ZipRecruiter-type experiment: optimising the uniform price alone raised profit by 55%. — [Dubé and Misra](https://openalex.org/W4280549099)
- [Secondary, Chicago Booth Review] In September 2015 new ZipRecruiter visitors were randomised to monthly prices from $19 to $399 against a $99 control; the estimated best uniform price lay between $249 and $399; doubling the price to $199 lost about a quarter of customers who would have paid $99; in the follow-up month profits rose 84% relative to $99. The working paper reports a 64.9% revenue improvement for optimised uniform pricing. These figures use different metrics and paper versions than the 55% in the published abstract. — [Chicago Booth Review](https://chicagobooth.edu/review/are-you-ready-personalized-pricing); [NBER w23775](https://www.nber.org/papers/w23775.pdf)
- [VENDOR/practitioner] Duolingo's engineering blog describes a subscription promotion test with a slight revenue increase and a decrease in retention; a former product lead states that A/B tests, not surveys, gave reliable pricing signals. No revenue figures are published. — [Duolingo blog](https://blog.duolingo.com/improving-duolingo-one-experiment-at-a-time); [RevenueCat podcast notes](https://www.revenuecat.com/blog/growth/cem-kansu-duolingo-sub-club-podcast-2026)
- [Practitioner/teaching sources] Van Westendorp: results vary with the price range shown, the output is an acceptable range rather than a revenue-maximising price, and it carries hypothetical bias. — [Penn State course notes](https://courses.ems.psu.edu/ba850/book/export/html/733)

### Inferences
- A workable sequence: use a survey (Van Westendorp or Gabor-Granger) only to bound the range, discount stated figures by roughly a fifth, then run a real-purchase test over a wide range, including prices several times the current one.
- Judge price tests on profit per visitor including refunds and, for subscriptions, on retention; Duolingo's example shows revenue and retention can move in opposite directions.
- Pitfalls: low traffic gives low power; visitors seeing different prices raises fairness and legal questions; single tests of small levers (price endings) can produce spurious results either way.

### Gaps
- No peer-reviewed validation study of Van Westendorp or Gabor-Granger against real purchases for digital goods was retrieved; the criticism cited is from teaching and practitioner sources.
- No scholarly pricing experiment for Duolingo or Spotify was found; the NYT evidence is quasi-experimental.
- OpenView SaaS benchmarks and Price Intelligently data were not retrieved in this pass.

## 8. Which effects failed to replicate or shrink in the field

### Takeaway
Published behavioural effects shrink sharply at scale: in the largest comparison the average effect in practice was about one sixth of the published one, mostly because of selective publication. Within pricing, the decoy effect and arbitrary anchoring are the clearest casualties; charm pricing survives as a small effect.

### Cited Findings
- [PR-meta, 2022] 126 RCTs, 23 million individuals: average nudge effect in academic journals 8.7 percentage points (33.4% over control) vs 1.4 points (8.0%) in Nudge Unit trials; selective publication, exacerbated by low power, explains about 70 percent of the difference. — [DellaVigna and Linos, Econometrica 2022](https://openalex.org/W3121638228)
- [PR-meta, 2022] After adjusting for publication bias, no evidence remains for an overall effect of nudges. — [Maier et al., PNAS 2022](https://openalex.org/W4286218562); [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC9351501)
- [PR-lab, 2014] Attraction (decoy) effect: 11 reliable effects in 91 attempts. — [Yang and Lynn, JMR 2014](https://openalex.org/W2150337234); see also [Frederick, Lee and Baskin 2014](https://openalex.org/W2043499048)
- [PR-lab, 2014] Anchoring in valuations: new evidence urging caution about the original result. — [Maniadis, Tufano and List, AER 2014](https://openalex.org/W2056125794)
- [PR-meta, 2023] Just-below prices: small pooled effect (g = 0.13), p-curve shows a large share of non-significant effects, and bias-corrected estimates are smaller and at times non-significant; the expected quality penalty is zero. — [Troll et al. 2023](https://openalex.org/W4366422183)
- [PR-meta, 2014] Sunk-cost effect exists but is attenuated by time in utilisation decisions. — [Roth, Robbert and Straus 2014](https://openalex.org/W2060738052)
- [PR-meta, 2018] Partitioned pricing has no stable direction. — [Abraham and Hamilton 2018](https://openalex.org/W4255489062)
- [PR-field, 2012] PWYW can reduce the number of buyers relative to a low fixed price. — [Gneezy et al., PNAS 2012](https://openalex.org/W2043074681)
- [PR-lab, 2022] Zero price can backfire when the offer has high time or risk costs. — [Fan, Cai and Bodenhausen 2022](https://openalex.org/W4212932351)

### Inferences
- Status summary for the report writer: **robust in real purchases** - flat-rate preference, inertia in subscriptions, left-digit threshold, short trials beating long trials (one firm), fee salience, lenient returns raising sales; **real but small** - 9-endings, sunk-cost effect on usage; **context-dependent** - partitioned pricing, PWYW, zero price, free version alongside paid; **fragile** - decoy effect, arbitrary anchoring, pennies-a-day outside small amounts.
- When powering a pricing test, assume effects several times smaller than published lab effects.

### Gaps
- No pricing-specific equivalent of the DellaVigna and Linos comparison (published vs at-scale effects) was found; the shrinkage factor is borrowed from nudge trials.
- Direct replications of the placebo effect of price (Shiv, Carmon and Ariely 2005) and of the zero-price effect were not retrieved, so their replication status is unknown here.
