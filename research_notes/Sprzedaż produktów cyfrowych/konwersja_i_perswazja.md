# Online conversion at the point of sale for digital products: sales pages, checkout, persuasion and trust (evidence base, as of November 2026)

Reading notes for the report writer:

- **PR** = peer-reviewed or scholarly source; **VENDOR** = vendor / industry report (uncontrolled, self-interested, usually no methods disclosure). Keep them apart in the report.
- **[verified]** = the number was seen in a tool result during this session (OpenAlex abstract or web search result). **[recalled]** = the number is quoted from the paper's abstract as the researcher remembers it; the paper's existence and OpenAlex record were verified, the figure itself was not re-read in this session. Re-check [recalled] numbers before printing them as headline figures.
- Every scholarly work below has a verified OpenAlex record; the registry with IDs is in `rejestr_konwersja.jsonl` (97 works, RK001-RK097).
- Access limits: page fetching was blocked in this session (only search snippets were available), so Baymard, Qubit, Stripe, Optimizely and Unbounce figures come from search-result summaries of those pages, not from reading the full pages. The OpenAlex daily budget ran out once mid-session; landmark papers were then resolved by citation (resolve_references) instead of keyword search.

## 1. Large-scale A/B test evidence: which categories work, how often tests win, how big true effects are

### Takeaway
Most tested ideas do not move the metric (roughly 8-33% of tests win, about 12% on a large vendor platform), true effects are usually around 1% or less, and the distribution is fat-tailed, so a few rare large wins matter. Behavioural interventions (scarcity, social proof, urgency) had the largest average lifts in the one big e-commerce meta-analysis (about 1.5-3% revenue per visitor), while cosmetic UI changes were near zero.

### Cited Findings
- VENDOR (data assured by PwC, not peer-reviewed): Browne and Swarbrick-Jones (Qubit, 2017), "What works in e-commerce - a meta-analysis of 6,700 online experiments", mostly retail and travel. Reported mean uplift in revenue per visitor: scarcity (stock pointers) +2.9%, social proof +2.3%, urgency (countdown timers) +1.5% [verified via search summaries]. Button changes 0.2% (16 experiments); cosmetic UI changes "weren't effective"; pop-ups and back-to-top buttons could be negative; only 4 of 29 common CRO techniques improved revenue per visit by as much as 1% [verified via summaries]. — [Paper PDF](https://www.gwern.net/doc/economics/advertising/2017-browne.pdf); [VentureBeat coverage](https://venturebeat.com/2017/06/21/analysis-of-2-billion-user-stories-explains-how-to-compete-with-amazon); [CustomerThink press text](https://customerthink.com/qubit-releases-data-on-more-than-two-billion-user-journeys-to-help-brands-take-on-the-ecommerce-giants/)
- A third-party blog attributes to the same Qubit paper that 90% of experiments had less than 1.2% effect on revenue per visitor; this was not confirmed against the paper itself. — [Convert blog](https://www.convert.com/blog/a-b-testing/what-is-meta-analysis-in-ab-testing/)
- The Qubit paper is not indexed in OpenAlex (resolve_references returned no match), so it is absent from the registry.
- VENDOR: Optimizely "Evolution of Experimentation" (2023), over 127,000 experiments run 2018-2023: around 12% of experiments win on the primary metric, 88% do not [verified]. Newer Optimizely guides use 173k experiments and call a 10-30% win rate healthy [verified]. — [Optimizely takeaways](https://www.optimizely.com/insights/top-10-takeaways-from-running-127000-experiments/); [173k guide](https://www.optimizely.com/field-notes/guides/173000-experiments)
- PR/practitioner (Kohavi and co-authors): reported experiment success rates of about 33% at Microsoft (2009), 15% at Bing, 10% at Booking.com, Google Ads and Netflix, and 8% at Airbnb Search, with estimated false-positive risk rising as the success rate falls (5.9% at Microsoft, 15% at Bing, 22% at Booking.com, 26.4% at Airbnb Search) [verified via search summaries of Kohavi's book excerpt and slides]. — [Trustworthy Online Controlled Experiments, ch. 1 excerpt](https://assets.cambridge.org/97811087/24265/excerpt/9781108724265_excerpt.pdf); [A/B Testing Intuition Busters](https://airbnb.tech/wp-content/uploads/sites/19/2025/10/ABTestingIntuitionBusters.pdf)
- PR: Azevedo, Deng, Montiel Olea, Rao and Weyl (2020, Journal of Political Economy): the optimal testing strategy depends on whether gains come from typical innovations or rare, unpredictable large successes; if tails are not too fat, a few high-powered experiments are optimal [verified, abstract]. With fat tails (which the authors report for Bing experiments), many small "lean" experiments are better [recalled]. — [OpenAlex W2801728724](https://openalex.org/W2801728724)
- PR: Koning, Hasan and Chatterji (2022, Management Science): among start-ups that adopt A/B testing, performance improves by 30%-100% after a year of use [verified, abstract]. — [OpenAlex W3124144674](https://openalex.org/W3124144674)
- PR: Berman and Van den Bulte (Management Science) and Berman, Pekelis, Scott and Van den Bulte (2018, SSRN): on a commercial A/B platform a large share of tested effects are true nulls, so many "significant" wins are false discoveries, and optional stopping (ending the test when significance is reached) makes this worse (exact percentages not re-read this session). — [OpenAlex W4206768734](https://openalex.org/W4206768734); [OpenAlex W2884097858](https://openalex.org/W2884097858)
- PR: Johari, Koomen, Pekelis and Walsh (2017, KDD): continuously "peeking" at fixed-horizon tests inflates false positives; always-valid p-values fix it. — [OpenAlex W2744538883](https://openalex.org/W2744538883)
- PR (preprint, later Econ Journal Watch 23(1), 2026): Kohavi, Linowski, Vermeer and co-authors ran three high-powered A/B tests, each with over two thousand times more users than an earlier study that claimed a large lift from rounded buttons, and found only small effects; underpowered studies (below 50% power) suffer from the winner's curse [verified via search summary]. — [arXiv 2512.24521](https://arxiv.org/abs/2512.24521v2); [OpenAlex W7117982802](https://openalex.org/W7117982802)
- Working paper: Miller and Hosanagar (Wharton), meta-analysis of e-commerce A/B tests on one platform (a blog says 2,732 tests by 252 US companies; a Wharton summary says nearly 2,000 tests by more than 200 companies; the count is unconfirmed). Price promotions and tests on category or product-listing pages had the largest effects; price promotions worked best early in the funnel and shipping promotions late (product and checkout pages) [verified via Wharton summary]. Not indexed in OpenAlex under that title. — [Mack Institute summary](https://mackinstitute.wharton.upenn.edu/2020/empirical-meta-analysis-e-commerce-a-b-testing-practices/)
- VENDOR: Unbounce Conversion Benchmark Report 2024 (41 thousand landing pages, 464 million visitors): median landing-page conversion rate 6.6%; pages written at a 5th-7th grade reading level had an 11.1% median conversion rate versus 5.3% for college-level copy; SaaS median 3.8% [verified]. Correlational. — [Unbounce report](https://unbounce.com/conversion-benchmark-report/); [MarketingProfs summary](https://marketingprofs.com/charts/2024/52374/landing-page-conversion-benchmarks)

### Inferences
- A small seller with low traffic cannot detect 1-3% effects: at a 2-3% baseline conversion a test needs tens of thousands of visitors per arm. The practical consequence is to test only large, structural changes (offer, price and payment terms, guarantee, proof, page structure) and to skip button colours and micro-copy.
- Published "case study" lifts of 20-50% from single tests are mostly winner's-curse artefacts; expect the true effect to be a fraction of what a small test shows.
- Category ranking from the Qubit data (scarcity, social proof, urgency above cosmetics) comes from large retail and travel sites selling physical stock and inventory; transfer to a solo creator's course page is plausible but untested.

### Gaps
- No large public meta-analysis exists for digital-product sales pages specifically (courses, ebooks, templates).
- Microsoft, Booking and Optimizely win rates are for mature products that are already optimised; win rates on an unoptimised small site are unknown and could be higher.
- The exact false-discovery percentages in Berman and Van den Bulte were not re-read.

## 2. Social proof: reviews, ratings, testimonials, buyer counts

### Takeaway
Reviews and popularity signals have the most consistent causal and meta-analytic support of any sales-page element, but average effects are modest (meta-analytic correlation with sales about .09), strongest for unknown sellers and niche products, with steep diminishing returns after the first handful of reviews. A perfect 5.0 is not optimal; purchase likelihood peaks around 4.0-4.7 stars in the main vendor study.

### Cited Findings
- PR: Babić Rosario, Sotgiu, De Valck and Bijmolt (2016, Journal of Marketing Research): meta-analysis of 1,532 effect sizes across 96 studies, 40 platforms and 26 product categories; eWOM is on average positively correlated with sales (.091), with differences by platform, product and metric [verified, abstract]. — [OpenAlex W2239794783](https://openalex.org/W2239794783)
- PR: You, Vadakkepatt and Joshi (2015, Journal of Marketing): meta-analytic eWOM volume elasticity 0.236 and valence elasticity 0.417 [recalled]. — [OpenAlex W2158892116](https://openalex.org/W2158892116)
- PR: Floyd, Freling, Alhoqail, Cho and Freling (2014, Journal of Retailing): meta-analysis confirming a positive effect of online product reviews on retail sales, with moderators. — [OpenAlex W2028538363](https://openalex.org/W2028538363)
- PR: Chevalier and Mayzlin (2006, Journal of Marketing Research): better reviews raise a book's relative sales at that site; for most samples the impact of one-star reviews is greater than the impact of five-star reviews; reviews are overwhelmingly positive [verified, abstract]. — [OpenAlex W3123091093](https://openalex.org/W3123091093)
- PR (working paper): Luca (2011): a one-star increase in Yelp rating leads to a 5-9% increase in revenue for independent restaurants, with no effect for chains [recalled]. — [OpenAlex W2128383499](https://openalex.org/W2128383499)
- PR: Zhu and Zhang (2010, Journal of Marketing): reviews matter more for less popular products (video games) and for more Internet-experienced consumers. — [OpenAlex W2163975393](https://openalex.org/W2163975393)
- VENDOR/academic centre: Spiegel Research Center (Northwestern, 2017, with PowerReviews): a product with five reviews has a purchase likelihood 270% greater than one with no reviews; the marginal benefit diminishes rapidly after the first five reviews; purchase likelihood peaks at ratings in the 4.0-4.7 range and falls as ratings approach 5.0; reviews from verified buyers raise purchase likelihood by 15% versus anonymous reviews; effects are larger for higher-priced items (one figure: 380%) [verified via search summary]. — [Spiegel Research Center](https://spiegel.medill.northwestern.edu/How-Online-Reviews-Influence-Sales)
- PR: Maslowska, Malthouse and Viswanathan (2017, Decision Support Systems): with retailer data, the valence-purchase relationship depends on review volume, exposure to reviews and price, and is not simply "higher is better". — [OpenAlex W2602808862](https://openalex.org/W2602808862)
- PR: Kupor and Tormala (2018, Journal of Consumer Research): moderately positive reviews can out-persuade extremely positive ones when they deviate from the perceived default rating. — [OpenAlex W2789056680](https://openalex.org/W2789056680)
- PR: Berger, Sorensen and Rasmussen (2010, Marketing Science): negative reviews hurt well-known authors' books but can raise sales of unknown authors' books by increasing awareness. — [OpenAlex W2169621740](https://openalex.org/W2169621740)
- PR: Park, Shin and Xie (2021, Marketing Science): the valence of the first review has a persistent effect on later review valence and volume. — [OpenAlex W3127613597](https://openalex.org/W3127613597)
- PR, field experiment: Tucker and Zhang (2011, Management Science): showing popularity information benefits narrow-appeal sellers more than equally popular broad-appeal sellers. — [OpenAlex W2108424188](https://openalex.org/W2108424188)
- PR, field experiment: Cai, Chen and Fang (2009, American Economic Review): displaying the five most popular dishes raised demand for them by 13 to 20% [recalled]. — [OpenAlex W3121216316](https://openalex.org/W3121216316)
- PR: Chen, Wang and Xie (2011, Journal of Marketing Research): negative word of mouth is more influential than positive; positive observational-learning (popularity) information raises sales while negative has no effect. — [OpenAlex W3124923688](https://openalex.org/W3124923688)
- PR, field experiment: Bapna and Umyarov (2015, Management Science): a friend's adoption of a premium subscription raised the odds of buying by more than 60% on a freemium music network [recalled]. — [OpenAlex W2117852767](https://openalex.org/W2117852767)
- PR: Salganik, Dodds and Watts (2006, Science): visible download counts made success more unequal and less predictable; early traction compounds. — [OpenAlex W2147453867](https://openalex.org/W2147453867)
- Fake reviews, PR: He, Hollenbeck and Proserpio (Marketing Science): bought Amazon reviews raise ratings and sales short-term, followed by a drop and more one-star reviews when buying stops; Luca and Zervas (2016): roughly 16% of Yelp restaurant reviews are filtered as suspicious [recalled], and fraud rises with weak reputation and more competition; Mayzlin, Dover and Chevalier (American Economic Review): manipulation patterns follow incentives. — [OpenAlex W3151441651](https://openalex.org/W3151441651); [OpenAlex W3122315158](https://openalex.org/W3122315158); [OpenAlex W3122952517](https://openalex.org/W3122952517)
- Law: the US FTC final rule banning fake reviews and testimonials took effect 21 October 2024 and allows civil penalties against knowing violators ($51,744 per violation in 2024; an FTC template dated December 2025 cites $53,088) [verified]. The EU Omnibus Directive (2019/2161) bans submitting or commissioning fake reviews and claiming reviews are from real buyers without reasonable verification steps [verified via secondary source]. — [FTC press release](https://www.ftc.gov/news-events/news/press-releases/2024/08/federal-trade-commission-announces-final-rule-banning-fake-reviews-testimonials); [Termly on Omnibus](https://termly.io/resources/articles/eu-omnibus/)

### Inferences
- For a new digital product the first 5-10 genuine, verifiable reviews are probably the highest-value proof asset; chasing hundreds more has rapidly falling returns.
- Show the real rating distribution and keep credible 4-star reviews with caveats; do not curate to a perfect 5.0.
- A "most chosen" label on the recommended package and a truthful buyer or student count have field-experiment support; they help niche, unknown sellers most.
- Meta-analytic correlations (.09) and elasticities are mostly from marketplaces with many competing products. On a single-product sales page with no comparison set the effect may differ.

### Gaps
- No peer-reviewed field experiment was found that tests testimonials (text or video) on a creator's own sales page for a course or ebook.
- The Spiegel figures come from one retailer partner dataset and a vendor collaboration; the 270% figure is relative to zero reviews.
- No reliable evidence found on user-generated content widgets or "X people bought today" notifications for small sellers.

## 3. Scarcity and urgency

### Takeaway
Scarcity raises purchase intentions on average in lab studies, but online time-limited promotions do not reliably beat identical non-urgent offers, and the effect depends on the product type and on the deadline having a believable external reason. Fake scarcity is both a legal risk in the EU and a documented trust cost.

### Cited Findings
- PR: Barton, Zlatevska and Oppewal (2022, Journal of Retailing): meta-analysis of 416 effect sizes from 131 studies; demand-based scarcity is most effective for utilitarian products, supply-based scarcity for experiences, and time-based scarcity for high-involvement products [verified, abstract]. The outcome is purchase intention, not sales. — [OpenAlex W4284967436](https://openalex.org/W4284967436)
- PR: Hmurovic, Lamberton and Goldsmith (2022, Journal of Marketing Research): meta-analytic and experimental results suggest positive effects of time-scarcity promotions observed offline "may not emerge" online, because online they activate persuasion knowledge; adding a retailer-exogenous justification for the time limit (birthday, seasonal change) raises the chance of a positive effect, more so when little time remains, but results "stop short" of showing consistent superiority over identical control promotions [verified, abstract]. — [OpenAlex W4288035992](https://openalex.org/W4288035992)
- PR, field experiments: Cui, Zhang and Bassamboo (Management Science): on 23,665 Amazon lightning deals, a 10% increase in past claims leads to a 2.08% increase in cart add-ins in the next hour; a deep discount weakens and a good rating amplifies this [verified, abstract]. — [OpenAlex W2586593278](https://openalex.org/W2586593278)
- PR: Aggarwal, Jun and Huh (2011, Journal of Advertising): limited-quantity messages were more effective than limited-time messages for purchase intention, especially for symbolic brands [verified, abstract]. — [OpenAlex W2794157377](https://openalex.org/W2794157377)
- PR: Lynn (1991, Psychology and Marketing): classic meta-analysis concluding scarcity enhances perceived value. — [OpenAlex W2133235809](https://openalex.org/W2133235809)
- PR, field: Shu and Gneezy (2010, Journal of Marketing Research): people given longer deadlines redeem less than those given shorter deadlines. — [OpenAlex W1977376275](https://openalex.org/W1977376275)
- PR: Tuncer and co-authors (2023, Behaviour and Information Technology): online experiment (N = 202) on how limited-time and limited-quantity cues affect perceived task load, perceived benevolence and user experience; scarcity cues are increasingly seen as dark patterns [verified, abstract]. — [OpenAlex W4387021653](https://openalex.org/W4387021653)
- VENDOR: Qubit meta-analysis: scarcity +2.9%, urgency +1.5% mean revenue per visitor (see section 1). — [Qubit paper](https://www.gwern.net/doc/economics/advertising/2017-browne.pdf)
- Law and enforcement: the European Commission lists fake countdown timers as an example of dark patterns; in an EU-wide check published 26 March 2026, 18% of checked sites used pressure-selling techniques such as claiming a product is running out or countdown timers, and more than half of those cases were misleading [verified]. A Digital Fairness Act proposal targeting fake low-stock and limited-time claims was reported; its text was not retrieved. — [European Commission news, 26 March 2026](https://commission.europa.eu/news-and-media/news/eu-check-reveals-misleading-sales-practices-online-2026-03-26_en); [Your Europe: unfair commercial practices](https://europa.eu/youreurope/citizens/consumers/unfair-treatment/unfair-commercial-practices/index_ga.htm)

### Inferences
- For digital goods with unlimited supply, quantity scarcity is not credible unless something real is limited (live cohort seats, coaching slots, founder pricing for the first N buyers). Barton's moderators point to real seat limits and real enrolment deadlines for courses and memberships.
- A deadline with an external reason (cohort start date, end of pre-sale, price rise on a stated date) is the defensible version of urgency; an evergreen countdown that resets per visitor is deceptive and matches the practices regulators sweep for.
- Expect low single-digit percentage effects, not the doubling claimed in launch-marketing folklore.

### Gaps
- No peer-reviewed field experiment was found on cohort deadlines or cart-close launches for online courses.
- No reliable measure of backlash (refunds, complaints, unsubscribes) from countdown timers in real sales data.
- The overall pooled effect size in Barton et al. was not in the abstract and was not retrieved.

## 4. Risk reversal and credibility signals

### Takeaway
Third-party assurance seals have randomized field evidence of raising conversion; money-back guarantees are well supported by signalling theory and lab studies but lack published field effect sizes; free samples and trials raise acquisition but can lower retention or substitute for purchase. Creator credibility and parasocial relationship evidence is correlational.

### Cited Findings
- PR, randomized field experiment: Özpolat, Gao, Jank and Viswanathan (2013, Information Systems Research): in 9,098 shopping sessions at an online retailer, the presence of a third-party assurance seal increased the likelihood of purchase conversion [verified, abstract]. — [OpenAlex W2141192301](https://openalex.org/W2141192301)
- PR, theory: Moorthy and Srinivasan (1995, Marketing Science): money-back guarantees can signal quality when buyers cannot inspect the product before purchase [verified, abstract]. — [OpenAlex W2021573668](https://openalex.org/W2021573668)
- PR: Suwelack, Hogreve and Hoyer (2011, Journal of Retailing): money-back guarantees affect emotions, perceived risk, purchase intention and willingness to pay. — [OpenAlex W2031747054](https://openalex.org/W2031747054)
- PR: Kirmani and Rao (2000, Journal of Marketing) and Akerlof (1970): signals are credible when costly to low-quality sellers; guarantees and reputation counter the "lemons" problem. — [OpenAlex W2179200719](https://openalex.org/W2179200719); [OpenAlex W2156109180](https://openalex.org/W2156109180)
- PR: Bawa and Shoemaker (2004, Marketing Science): free samples can produce measurable long-term sales effects. — [OpenAlex W1969045005](https://openalex.org/W1969045005)
- PR: Datta, Foubert and van Heerde (2015, Journal of Marketing Research): customers acquired via free trials have lower retention but respond more to marketing and to their own usage. — [OpenAlex W2787323089](https://openalex.org/W2787323089)
- PR: Li, Jain and Kannan (2019, Journal of Marketing Research): for digital products the amount and choice of sampled content affects later purchase. — [OpenAlex W2940771723](https://openalex.org/W2940771723)
- PR: Gefen, Karahanna and Straub (2003), Pavlou (2003), Kim, Ferrin and Rao (2008): trust and perceived risk are direct drivers of online purchase intention, on a par with usefulness and ease of use. — [OpenAlex W1574235309](https://openalex.org/W1574235309); [OpenAlex W1708393801](https://openalex.org/W1708393801); [OpenAlex W2093548531](https://openalex.org/W2093548531)
- PR: Schlosser, White and Lloyd (2006, Journal of Marketing): visible investment in site design signals ability and raises purchase intentions. — [OpenAlex W2164806821](https://openalex.org/W2164806821)
- PR: Pornpitakpan (2004): across five decades, high-credibility sources are generally more persuasive. Sokolova and Kefi (2020): creator credibility and parasocial interaction correlate with purchase intention (survey). — [OpenAlex W2157392583](https://openalex.org/W2157392583); [OpenAlex W2913701832](https://openalex.org/W2913701832)
- VENDOR: Baymard reports "didn't trust the site with card information" among checkout abandonment reasons; the percentage was not retrieved this session. — [Baymard](https://baymard.com/lists/cart-abandonment-rate)

### Inferences
- For an unknown seller, a recognised payment-provider or trust mark near the pay button and a clearly stated guarantee are cheap, evidence-backed first tests.
- A guarantee works as a signal precisely because it is costly if the product is bad; a conditional or hard-to-claim guarantee weakens the signal. In the EU, consumers can lose the 14-day withdrawal right for digital content only with explicit consent, so a voluntary guarantee is a real differentiator rather than a legal default (legal detail not researched here).
- A free lesson or sample chapter addresses fit uncertainty; give enough to judge quality, not enough to replace the product.

### Gaps
- No published field experiment gives the conversion lift and refund-rate cost of a money-back guarantee for digital products.
- No causal evidence on creator credentials or parasocial relationship on sales-page conversion.
- The Özpolat effect size was not in the abstract.

## 5. Message framing and copy

### Takeaway
Framing effects (loss versus gain) are real but small and context-dependent; narrative has small-to-moderate meta-analytic effects on intentions and behaviour; concrete language has field support. Claims about long versus short copy and sales-page video have no peer-reviewed support either way.

### Cited Findings
- PR: Kühberger (1998): meta-analysis finds a small to moderate framing effect that varies strongly with study design. — [OpenAlex W1998740918](https://openalex.org/W1998740918)
- PR: O'Keefe and Jensen (2007): gain-framed appeals have only a very small persuasive advantage over loss-framed ones for prevention behaviours, confined to a narrow set of behaviours. — [OpenAlex W2114823211](https://openalex.org/W2114823211)
- PR: van Laer, de Ruyter, Visconti and Wetzels (2014, Journal of Consumer Research): narrative transportation shapes affect, beliefs, attitudes and intentions and reduces critical thoughts. — [OpenAlex W3123476072](https://openalex.org/W3123476072)
- PR: Braddock and Dillard (2016): narratives have positive effects on beliefs (r = .17), attitudes (r = .19), intentions (r = .17) and behaviours (r = .23) [recalled]. — [OpenAlex W2293452863](https://openalex.org/W2293452863)
- PR: Packard and Berger (Journal of Consumer Research): concrete language toward customers raises satisfaction, willingness to purchase and actual purchases. — [OpenAlex W3043760017](https://openalex.org/W3043760017)
- PR, field experiments: Sahni, Wheeler and Chintagunta (2018, Marketing Science): adding the recipient's name to the email subject line raised opens by 20% and sales leads by 31% and cut unsubscribes by 17% [recalled]. — [OpenAlex W2788138901](https://openalex.org/W2788138901)
- PR, field experiments: Matz, Kosinski, Nave and Stillwell (2017, PNAS): psychologically matched ads to over 3.5 million people gave up to 40% more clicks and up to 50% more purchases [recalled]; the design was later criticised for non-random ad delivery. — [OpenAlex W2768262152](https://openalex.org/W2768262152)
- VENDOR, correlational: Unbounce 2024: simpler copy (5th-7th grade reading level) had an 11.1% median conversion rate versus 5.3% for college-level copy [verified]. — [MarketingProfs summary](https://marketingprofs.com/charts/2024/52374/landing-page-conversion-benchmarks)
- PR: Kumar and Tan (2015, Management Science) study demand effects of product videos in online retail (record verified; result not re-read). — [OpenAlex W3122526332](https://openalex.org/W3122526332)

### Inferences
- "Loss framing beats gain framing" is not a safe default for headlines; test it, expect a small difference.
- A customer story or creator story and concrete, specific description of contents are reasonable defaults with meta-analytic or field backing.
- Simple, readable copy correlates with conversion in vendor data; causality is unproven (simple products may have simple copy).

### Gaps
- No peer-reviewed evidence found on long-form versus short-form sales pages, benefit versus feature copy, or video sales letters for digital products. Treat all such claims as vendor lore.

## 6. Choice architecture, checkout friction, payment methods, page speed

### Takeaway
Defaults and instalment or BNPL options have the strongest evidence; choice overload averages to zero and matters only under identifiable conditions; the decoy effect is fragile with realistic stimuli. Checkout friction evidence is mostly vendor survey data, pointing to extra costs, forced account creation and long forms.

### Cited Findings
- PR: Scheibehenne, Greifeneder and Todd (2010, Journal of Consumer Research): meta-analysis of 63 conditions from 50 experiments finds a mean choice-overload effect of virtually zero with large variance [verified, abstract]. — [OpenAlex W2177382657](https://openalex.org/W2177382657)
- PR: Chernev, Böckenholt and Goodman (2014/2015, Journal of Consumer Psychology): choice overload is moderated by choice-set complexity, decision-task difficulty, preference uncertainty and decision goal. — [OpenAlex W2087356051](https://openalex.org/W2087356051)
- PR: Iyengar and Lepper (2000): the original jam studies (6 versus 24 or 30 options). — [OpenAlex W2126311339](https://openalex.org/W2126311339)
- PR: Jachimowicz, Duncan, Weber and Johnson (2019, Behavioural Public Policy): meta-analysis shows defaults substantially increase uptake of the pre-selected option, with large variation across domains (the abstract reports d = 0.68 from 58 studies [recalled]). — [OpenAlex W2742773638](https://openalex.org/W2742773638)
- PR: Hummel and Maedche (2019): across 100 publications and 317 effect sizes, defaults are the most effective nudge category; median relative effect 21%; about one third of effects not significant [recalled]. — [OpenAlex W2921959179](https://openalex.org/W2921959179)
- PR: Frederick, Lee and Baskin (2014) and Yang and Lynn (2014), both Journal of Marketing Research: the attraction (decoy) effect mostly fails to appear with realistic product representations. Original: Huber, Payne and Puto (1982). — [OpenAlex W2043499048](https://openalex.org/W2043499048); [OpenAlex W2150337234](https://openalex.org/W2150337234); [OpenAlex W2117503214](https://openalex.org/W2117503214)
- PR: Maesen and Ang (2024/2025, Journal of Marketing): at a large US retailer, BNPL adoption is associated with higher purchase incidence and larger purchase amounts, more for smaller-basket shoppers; three preregistered experiments attribute this to reduced perceived financial constraints [verified, abstract]. — [OpenAlex W4402116954](https://openalex.org/W4402116954)
- PR: Ashby, Sharifi, Yao and Ang (2025, Journal of Retailing): transaction data and experiments show greater spending with BNPL than with other payment modes [verified, abstract]. — [OpenAlex W4407049287](https://openalex.org/W4407049287)
- PR: Berg, Burg, Keil and Puri (2025, Journal of Financial Economics; NBER w33152): merchant-side analysis of BNPL at a German e-commerce furniture seller with randomized offering; a conference discussant summarises the result as "offering BNPL leads to +20% sales" (discussant's wording, not verified against the paper). — [NBER w33152](https://www.nber.org/papers/w33152); [Discussant slides](https://bguttmankenney.github.io/Public/MFA24.pdf); [OpenAlex W4410732092](https://openalex.org/W4410732092)
- VENDOR: Stripe A/B tests on more than 150,000 checkout sessions: offering BNPL gave up to a 14% increase in revenue (a ceiling, not an average); a separate Stripe talk cites an average 10% relative conversion uplift from adding BNPL [verified via secondary summaries]. — [Stripe blog](https://stripe.com/en-bg/blog/testing-the-impact-of-buy-now-pay-later); [Payments Dive](https://www.paymentsdive.com/news/how-buy-now-pay-later-benefits-merchants/720281/)
- VENDOR: Baymard: average documented cart abandonment about 70% (70.19%-70.22% depending on page version, unweighted average of 50 studies 2006-2025); among US shoppers, 40% abandoned because of extra costs at checkout (39% in another citation), 18% because the site required an account (survey of 1,026 US adults, 2025), 17% because of a too long or complicated checkout; 42% have abandoned because they were "just browsing"; Baymard estimates the average large e-commerce site could gain 35.26% in conversion from fixing checkout usability issues [verified via search summaries]. — [Baymard cart abandonment list](https://baymard.com/lists/cart-abandonment-rate); [Baymard statistics article](https://baymard.com/blog/cart-abandonment-rate-statistics); [Baymard checkout UX](https://baymard.com/blog/current-state-of-checkout-ux)
- PR: Kukar-Kinney and Close (2010): cart abandonment is also driven by using carts for entertainment or organisation, cost concern and waiting for a sale. — [OpenAlex W2091631293](https://openalex.org/W2091631293)
- PR, field experiment: Blake, Moshary, Sweeney and Tadelis (2021, Marketing Science): hiding fees until checkout on a ticket marketplace increased purchasing and spending relative to upfront all-in prices. — [OpenAlex W2898806675](https://openalex.org/W2898806675)
- VENDOR (Google-commissioned, observational): Deloitte "Milliseconds Make Millions": a 0.1 second mobile speed improvement was associated with retail conversions up 8.4% and average order value up 9.2%, across 37 brands over four weeks; every page in the journey had to improve [verified]. — [web.dev summary](https://web.dev/case-studies/milliseconds-make-millions)
- PR: Galletta, Henry, McCoy and Polak (2004): lab experiments show attitudes and intentions deteriorate with page delays of a few seconds. — [OpenAlex W2740580754](https://openalex.org/W2740580754)
- PR: Gourville (1998): "pennies-a-day" reframing helps for small amounts. Senecal and Nantel (2004): recommended products were chosen twice as often [recalled]. — [OpenAlex W2029136992](https://openalex.org/W2029136992); [OpenAlex W2118898598](https://openalex.org/W2118898598)

### Inferences
- For a course priced in the hundreds, offering instalments or BNPL and showing the per-instalment price is likely the single best-evidenced checkout change. Merchant fees and consumer-credit rules need checking.
- Buyers of a course are typically novices with uncertain preferences, which is the condition where too many packages hurts; two or three clearly differentiated tiers with one recommended default is consistent with the moderators.
- Pre-selecting the recommended plan is supported; pre-ticked paid add-ons (order bumps ticked by default) are prohibited in the EU under the Consumer Rights Directive (not researched in detail here) and count as a dark pattern.
- Show the all-in price (with VAT) early; hidden fees raise short-term sales but are the top self-reported abandonment reason and a regulatory target.
- Do not design pricing tables around a decoy tier.

### Gaps
- No peer-reviewed field experiment found on guest checkout, number of form fields, one-page versus multi-step checkout, or opt-in (unticked) order bumps.
- Baymard reasons are self-reports from US shoppers of physical goods; shipping-cost reasons do not transfer to digital products.
- Page-speed evidence on conversion is vendor or observational; no clean published experiment was retrieved.

## 7. Nudge meta-analyses and the publication-bias debate: realistic effect sizes

### Takeaway
Published nudge effects are inflated several-fold by publication bias. At scale, well-run interventions average about 1.4 percentage points (8% relative), versus 8.7 points in journals. Plan for small effects and heterogeneity.

### Cited Findings
- PR: Mertens, Herberz, Hahnel and Brosch (PNAS, 2021/2022): more than 200 studies, over 450 effect sizes (n = 2,149,683); small-to-medium overall effect of Cohen's d = 0.43, with moderate publication bias [verified]. — [OpenAlex W4205744578](https://openalex.org/W4205744578); [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC8740589)
- PR: Maier, Bartoš, Stanley, Shanks, Harris and Wagenmakers (PNAS, 2022): after correcting for publication bias, no evidence remains that nudges are effective as tools for behaviour change [verified]. — [OpenAlex W4286218562](https://openalex.org/W4286218562); [PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9351501/)
- PR: Szaszi and co-authors (PNAS, 2022): no reason to expect large and consistent effects; a related commentary gives bias-adjusted averages from d = 0.03 (severe bias) to d = 0.31 (moderate) [verified via search summary]. — [OpenAlex W4286218446](https://openalex.org/W4286218446); [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9351519)
- PR: DellaVigna and Linos (2022, Econometrica): 126 RCTs covering 23 million individuals from two US Nudge Units; Nudge Unit trials average 1.4 percentage points (s.e. 0.3) on a control take-up of 17.2 points [verified], versus 8.7 points (a 33.4% increase) in academic journal samples [recalled]; publication bias accounts for much of the gap. — [OpenAlex W3121638228](https://openalex.org/W3121638228); [Working paper](https://eml.berkeley.edu/~sdellavi/wp/NudgeToScale2020-05-09.pdf)
- PR: Milkman and co-authors (2021, Nature): megastudy of 54 interventions with 61,293 gym members; 45% of interventions significantly increased weekly visits, by 9% to 27%; forecasters could not predict which would work [recalled]. — [OpenAlex W4200604215](https://openalex.org/W4200604215)
- PR: Open Science Collaboration (2015, Science): 97% of original psychology studies were significant versus 36% of replications, with replication effects about half the size [recalled]. — [OpenAlex W1897139626](https://openalex.org/W1897139626)

### Inferences
- A realistic prior for a behavioural tweak on a sales page is a relative lift in the low single digits to roughly 10%, and frequently zero. This matches the vendor A/B data in section 1 (1-3% revenue per visitor for the best categories).
- Structural changes to the choice (defaults, payment terms) outperform informational nudges (labels, reminders, framing).

### Gaps
- Nudge-unit trials are public-sector (letters, enrolment); direct transfer to commercial checkout is an assumption.

## 8. Cialdini principles: field evidence in e-commerce versus failures to replicate

### Takeaway
Social proof and (genuine) scarcity have field evidence in commerce, though with small effects and failed replications in some contexts. Authority and commitment have supporting but indirect evidence; reciprocity and liking have little direct e-commerce field evidence in the works retrieved.

### Cited Findings
- Social proof: supported by field experiments (Cai et al. 2009; Tucker and Zhang 2011; Bapna and Umyarov 2015; Cui et al. on lightning deals) and meta-analyses of reviews (section 2). The flagship field study, Goldstein, Cialdini and Griskevicius (2008, hotel towels), failed to replicate in German hotels (Bohner and Schlüter 2014), while a Bayesian synthesis of the studies still supports a positive overall effect (Scheibehenne, Jamil and Wagenmakers 2016). — [OpenAlex W2130950828](https://openalex.org/W2130950828); [OpenAlex W2129060128](https://openalex.org/W2129060128); [OpenAlex W2409052306](https://openalex.org/W2409052306)
- Scarcity: supported on intentions (Barton et al. 2022) and partly in the field (Cui et al.), but time scarcity online is unreliable (Hmurovic et al. 2022). — [OpenAlex W4284967436](https://openalex.org/W4284967436); [OpenAlex W4288035992](https://openalex.org/W4288035992)
- Authority: source-credibility review (Pornpitakpan 2004) and the assurance-seal field experiment (Özpolat et al. 2013) support credibility signals. — [OpenAlex W2157392583](https://openalex.org/W2157392583); [OpenAlex W2141192301](https://openalex.org/W2141192301)
- Reciprocity and concession: Feeley, Anker and Aloe (2012) meta-analysed 35 years of door-in-the-face studies; this evidence is about compliance with requests, not online purchases. Free-sample effects (Bawa and Shoemaker 2004) are usually explained by learning about quality, not reciprocity. — [OpenAlex W1968891623](https://openalex.org/W1968891623); [OpenAlex W1969045005](https://openalex.org/W1969045005)
- Liking and unity: only correlational survey evidence (parasocial interaction, Sokolova and Kefi 2020). — [OpenAlex W2913701832](https://openalex.org/W2913701832)

### Inferences
- Ranking by evidence strength for a small seller: social proof, then authority or credibility signals, then genuine scarcity; treat reciprocity (lead magnets "create obligation"), commitment (micro-yes ladders) and liking as untested in commerce.

### Gaps
- No systematic replication audit of all Cialdini principles in e-commerce was found; commitment and consistency (foot-in-the-door) and reciprocity were not searched in depth because the OpenAlex budget ran out.

## 9. Dark patterns: effectiveness versus legal and reputational risk

### Takeaway
Dark patterns raise short-term conversion substantially in experiments, and aggressive ones provoke backlash; they are widespread, detectable and an active enforcement target in the EU and US.

### Cited Findings
- PR: Luguri and Strahilevitz (Journal of Legal Analysis, 13(1), 2021): mild dark patterns more than doubled sign-ups to a dubious service and aggressive ones nearly quadrupled them (one summary says more than four times); aggressive patterns generated a powerful backlash, mild ones did not; with dark patterns the price of the service became immaterial; less educated subjects were more susceptible to mild patterns [verified via search summaries]. — [Oxford Academic](https://academic.oup.com/jla/article/13/1/43/6180579); [University of Chicago summary](https://www.law.uchicago.edu/news/dark-patterns-can-consumers-break-out); [OpenAlex W3137759237](https://openalex.org/W3137759237)
- PR: Mathur and co-authors (2019): crawl of about 11K shopping sites found 1,818 dark-pattern instances of 15 types and 183 sites with deceptive practices, plus third-party vendors selling such features [recalled]. — [OpenAlex W4288086176](https://openalex.org/W4288086176)
- PR: Sin, Harris, Nilsson and Beck (2022, Behavioural Public Policy): in a hypothetical shopping experiment all tested dark patterns increased purchase impulsivity versus control [verified, abstract]. — [OpenAlex W4229375673](https://openalex.org/W4229375673)
- PR: Zac and co-authors (2025, Behavioural Public Policy): dark patterns and consumer vulnerability (record verified; result not re-read). — [OpenAlex W4407083802](https://openalex.org/W4407083802)
- Enforcement: EU sweep of March 2026 (18% of sites using pressure selling, more than half of those misleading); FTC fake-review rule with per-violation penalties (see sections 2 and 3). — [European Commission](https://commission.europa.eu/news-and-media/news/eu-check-reveals-misleading-sales-practices-online-2026-03-26_en); [FTC](https://www.ftc.gov/news-events/news/press-releases/2024/08/federal-trade-commission-announces-final-rule-banning-fake-reviews-testimonials)

### Inferences
- The conversion gain from dark patterns is real in the short run, which is exactly why regulators target them; for a creator whose asset is audience trust and repeat purchase, backlash and refund risk outweigh the gain.
- Practical red lines: fake or resetting timers, invented stock or buyer notifications, pre-ticked paid add-ons, fees revealed at the last step, fake or unverifiable reviews, hard-to-cancel subscriptions.

### Gaps
- No evidence on long-run revenue (refunds, churn, chargebacks) after dark-pattern-driven sales.
- DSA Article 25 wording and the Polish regulator's (UOKiK) decisions were not retrieved; the Digital Fairness Act text was not read.

## 10. Digital-product-specific drivers: courses, ebooks, paid content

### Takeaway
Digital products are experience goods with high quality and fit uncertainty, so purchase hinges on trust, expected outcome, perceived instructor expertise and the chance to try before buying. Evidence specific to courses is mostly survey-based (purchase intention), not sales experiments.

### Cited Findings
- PR, survey (443 users of knowledge-payment platforms, SEM): Chen, Ding, Meng, Li and Zhang (2021/2023, Information Development): trust and performance expectation raise purchase intention toward online paid courses; perceived lecturer expertise, prior learning experience and personal trial experience raise trust and performance expectation [verified, abstract]. — [OpenAlex W3181423968](https://openalex.org/W3181423968)
- PR: Hong and Pavlou (2014) and Dimoka, Hong and Pavlou (2012): product fit uncertainty and product (quality) uncertainty are distinct from seller uncertainty; diagnostic descriptions and third-party assurances mitigate them. — [OpenAlex W2129204218](https://openalex.org/W2129204218); [OpenAlex W3121659628](https://openalex.org/W3121659628)
- PR: Oestreicher-Singer and Zalmanson (2013, MIS Quarterly): willingness to pay for premium content is strongly associated with community participation. — [OpenAlex W3122080363](https://openalex.org/W3122080363)
- PR: Gu, Kannan and Ma (2018, Journal of Marketing): design of the premium product line in a freemium setting affects premium demand (field experiments). — [OpenAlex W2897722974](https://openalex.org/W2897722974)
- PR: Goli, Chintagunta and Sriram (Journal of Marketing Research): effect of payment on engagement in online courses (record verified; direction of result not re-read). — [OpenAlex W3157101706](https://openalex.org/W3157101706)
- PR: Li, Jain and Kannan (2019): free-sample design for digital products (section 4). — [OpenAlex W2940771723](https://openalex.org/W2940771723)
- Other course-specific survey studies located but not read: Wang, Esperança and Wu (2022) on TikTok online-course purchase intention; Shi, Zheng and Yang (2020) on payment for live courses in Q&A communities; Yu and co-authors (2021) on knowledge-paying behaviour (UTAUT). — [OpenAlex W4293214217](https://openalex.org/W4293214217); [OpenAlex W3013920041](https://openalex.org/W3013920041); [OpenAlex W3171338409](https://openalex.org/W3171338409)

### Inferences
- A sales page for a course should mainly reduce two uncertainties: quality (who teaches, proof of results, sample lesson, guarantee) and fit ("who this is for and not for", detailed syllabus, prerequisites).
- Building a free community or audience before the offer is consistent with the content-or-community finding; it is correlational.
- Suggested test order for a small seller, by evidence strength and likely effect size: (1) offer and price structure including instalments; (2) real reviews and buyer counts near the call to action; (3) guarantee and trust marks at checkout; (4) free sample or preview; (5) clear fit statement and concrete syllabus; (6) recommended default tier with two or three options; (7) real deadline or seat limit with a stated reason; (8) speed and checkout friction (all-in price, no forced account, fewer fields). Last and usually not worth testing at low traffic: button colour or shape, decoy tiers, loss-framed headlines, fake urgency.

### Gaps
- No randomized sales experiments on creator-run course, ebook, template or membership pages were found in the scholarly literature; nearly all course-specific evidence is cross-sectional surveys of intention from Chinese knowledge-payment platforms.
- No evidence on price points, launch models (evergreen versus cohort) or webinar funnels.
- GoodUI, CXL, Speero, VWO, Convert and Nielsen Norman Group sources were suggested but not retrieved (page fetching blocked); they remain unchecked.
