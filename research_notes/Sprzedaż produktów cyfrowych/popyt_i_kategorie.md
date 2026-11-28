# Popyt i kategorie produktów cyfrowych 2024-2026 (which digital products are in demand and profitable)

Research date: 2026-11-28. Reliability tags used on every number:
**[PR]** peer-reviewed paper, **[PP]** preprint / working paper, **[1P-fin]** first-party audited or regulatory filing (10-K, earnings release), **[1P]** platform first-party report or statement (unaudited, self-selected), **[3P-est]** third-party estimate or scraped dataset, **[VM]** vendor marketing / blog claim, **[MR]** paid market-research forecast (definitions vary, low reliability).

Method caveats (read first):
- Web numbers come from search-result extracts; direct page fetching was blocked for several hosts in this session (insightraider.com and kajabi.com failed to resolve), so those figures were NOT verified on the primary page. They are marked "(snippet)".
- Academic evidence: OpenAlex MCP. About 35 search attempts were made (keyword and semantic); roughly two thirds were rejected by the daily budget / 1-request-per-second limit, 12 returned results. In addition 75 references were resolved through `resolve_references` (71 matched), 2 citation lists were followed, and 36 full records were pulled with `get_work`. Paper numbers below are only those stated in the abstract returned by OpenAlex ("according to the authors"). 50 works are in `rejestr_popyt.jsonl` (IDs RP001-RP050).
- Anything dated before 2023 is flagged **(pre-2023, possibly stale)**.

## 1. Market size and growth per category: which sources, which year, how reliable?

### Takeaway
There is no reliable single number for "digital products"; headline forecasts differ by 2-100x depending on definition, so they are useless for choosing a category. The only hard numbers are company filings, and they show flat-to-slow growth in mass-market self-paced courses and marketplaces (Udemy flat, Etsy slightly up, Thinkific GMV flat) against fast growth in subscriptions, paid communities and newsletters (Whop, Substack, beehiiv, Patreon).

### Cited Findings
Creator economy (top-down)
- Goldman Sachs Research (2023) put the creator-economy TAM at about $250B, forecast to reach $480B by 2027; no updated Goldman forecast was found in 2025-2026. **[MR/bank research, 2023]** — [Goldman Sachs](https://www.goldmansachs.com/insights/articles/the-creator-economy-could-approach-half-a-trillion-dollars-by-2027)
- Newer estimates with different definitions place the 2026 creator economy at roughly $310-323B; WPP Media estimates creators generate $184.9B revenue globally in 2025. **[MR, secondary, snippet]** — [Quasa summary](https://quasa.io/media/goldman-sachs-sees-the-creator-economy-nearing-480-billion-by-2027)
- Patreon crossed $10B cumulative creator payouts in August 2025; CEO says more than $2B per year now goes to creators. **[1P, 2025]** — [Axios](https://www.axios.com/2025/08/05/patreon-10-billion-creator-economy-ai)
- Patreon claims 25M+ paid memberships; a third-party tracker counts about 17.8M public paid memberships; creator counts cited range 250-300k. **[1P vs 3P-est, conflict]** — [Search Engine Land](https://searchengineland.com/guide/patreon-users)
- Kajabi also reports $10B cumulative creator revenue (Aug 2025). **[1P, 2025]** — [BusinessWire](https://www.businesswire.com/news/home/20250806424975/en/%2410B-in-Creator-Revenue-and-Climbing-Kajabi-Creators-Are-Achieving-Long-Term-Financial-Success); [Tubefilter](https://www.tubefilter.com/2025/08/07/patreon-kajabi-10-billion-creator-economy-payouts-funding-since-launch/)

E-learning / online courses
- HolonIQ's often-quoted "$404B EdTech by 2025" is a 2019-era forecast, not a measured result **(pre-2023, stale)**. 2025 EdTech estimates from other firms are about $197-200B (MarketsandMarkets $197.3B -> $353.1B by 2030; The Business Research Company $199.7B -> $456.4B by 2030); Knowledge Sourcing Intelligence puts "online education" at $388.8B in 2025. **[MR, mutually inconsistent]** — [HolonIQ](https://www.holoniq.com/notes/global-education-technology-market-to-reach-404b-by-2025); [QS/HolonIQ 2025 outlook](https://www.qs.com/insights/2025-global-education-outlook)
- QS/HolonIQ 2025 outlook: total global education market about $7.3T in 2025 -> about $10T by 2030 (4.4% CAGR), with EdTech/digital about 5.2% of spend. **[MR, 2025]** — [QS](https://www.qs.com/insights/2025-global-education-outlook)
- Udemy FY2025: revenue $789.8M vs $786.6M in 2024 (flat). Consumer segment -9% to $265.8M (transactional purchases -$39.8M, consumer subscription +$13.5M); consumer paid subscribers +102% to 343,000; Udemy Business +6% to $524.1M, ARR $540.0M (+4%), net dollar retention 93%; subscription = 72% of revenue. Pending combination with Coursera. **[1P-fin, FY2025]** — [BusinessWire](https://www.businesswire.com/news/home/20260204247314/en/Udemy-Reports-Fourth-Quarter-and-Full-Year-2025-Results); [SEC 10-K](https://www.sec.gov/Archives/edgar/data/1607939/000160793926000034/udmy-20251231.htm)
- Thinkific FY2025: revenue $73.2M (+9%); creator GMV $460.0M (flat y/y); Q4 GMV $117.3M (+2%); Q3 2025 ARPU $173/month. **[1P-fin, FY2025]** — [Thinkific IR](https://investors.thinkific.com/2026-03-05-Thinkific-Announces-Fourth-Quarter-and-Full-Year-2025-Financial-Results)
- Coursera 2025 revenue about $757M (+9%), 197M registered learners. **[1P-fin relayed by secondary site, snippet]** — [Coursera 10-K](https://s27.q4cdn.com/928340662/files/doc_financials/2025/ar/COURSERA_10K_2026.pdf)
- Teachable publishes no GMV; 2025 year-in-review claims 95M lifetime students and 150,000+ creators. **[1P]** — [Teachable](https://www.teachable.com/blog/2025-rewind)

Marketplaces for templates / printables / digital downloads
- Etsy FY2025: marketplace GMS $10.46B, 5.6M active sellers, 86.5M active buyers (-3.4% y/y); Q4 GMS +2.4%. Etsy does NOT disclose the digital-download share. **[1P-fin, FY2025]** — [Etsy 10-K](https://www.sec.gov/Archives/edgar/data/1370637/000137063726000019/etsy-20251231.htm)
- Third-party listing counts: about 848,685 "digital planner" listings and about 1.85M "Canva template" listings on Etsy (supply-side saturation indicator, not sales). **[3P-est, 2026, snippet]** — [Analyzify](https://analyzify.com/hub/digital-products-to-sell-on-etsy)

Paid newsletters
- Substack passed 5M paid subscriptions by March 2025 (4M in Nov 2024, 3M a year earlier); no newer milestone confirmed, and Substack declined to give Press Gazette a figure in Feb 2026. **[1P, 2025]** — [Hollywood Reporter](https://www.hollywoodreporter.com/business/business-news/substack-number-subscribers-video-trump-1236158048/); [Press Gazette](https://pressgazette.co.uk/newsletters/newsletters-2026-prices-retention-churn/)
- beehiiv paid-subscription revenue: $8M (2024) -> $19M (2025), +138%; projected about $35M for 2026; share of revenue-generating users earning from paid subscriptions rose from 15% to 30%. **[1P, 2026]** — [beehiiv State of Paid Newsletters 2026](https://www.beehiiv.com/blog/the-state-of-paid-newsletters-2026.md); [Press Gazette](https://pressgazette.co.uk/newsletters/newsletters-2026-prices-retention-churn/)

Paid communities / memberships
- Whop: company-reported cumulative GMV about $2.67B and 183,628 sellers as of Feb 2026 (another source says $3B+); Sacra estimates 2024 GMV at $410M and about $100M monthly GMV by April 2025; 650+ creators have earned $1M+. **[1P + 3P-est, conflict on some figures]** — [Sacra](https://sacra.com/c/whop/)
- Skool: no official GMV or payout number found; "over 100,000 communities" appears only in an unsourced review. **[VM]** — [Coda review](https://coda.io/@sham-deli/skool-review-2025-is-this-community-platform-worth-99-month-for-)

Software / subscriptions
- RevenueCat State of Subscription Apps 2026: data from 115,000+ apps and $16B+ revenue; 27.1% of subscription apps are classified AI-powered. **[1P dataset, 2026]** — [RevenueCat](https://www.revenuecat.com/state-of-subscription-apps-2026/)

Stock assets / data licensing
- Shutterstock FY2025: revenue $989.9M (+6%); Content $786.7M (+4%, helped by the Envato acquisition; Q4 content revenue -11%); Data, Distribution & Services $203.3M (+16%, 21% of revenue). **[1P-fin, FY2025]** — [Yahoo Finance](https://finance.yahoo.com/news/shutterstock-sstk-reports-989-9m-114655765.html); [Shutterstock IR](https://shutterstock.gcs-web.com/node/14551)

Certification / exam prep
- Professional certification (credentialing) market $8.1B in 2025 -> $16.8B by 2032 (Stratistics MRC); "test preparation" estimates range from about $0.5B (Global Growth Insights, IMARC) to $69.9B (Research and Markets) depending on definition. **[MR, order-of-magnitude disagreement]** — [Stratistics via MarketResearch](https://www.marketresearch.com/Stratistics-Market-Research-Consulting-v4058/Professional-Certification-Forecasts-Global-Credentialing-42785163); [IMARC](https://imarcgroup.com/test-preparation-market)
- AI prompt marketplace estimated at $1.94B in 2025 (The Business Research Company, via a secondary article). **[MR, low reliability]** — [greyjournal](https://greyjournal.net/?p=105837)

Europe / Poland
- Poland e-learning and digital education market: $1.5B in 2025, about 11.8% CAGR to 2032 (Ken Research; covers all digital education, not creator courses). **[MR]** — [Ken Research](https://www.kenresearch.com/poland-e-learning-and-digital-education-market.md)
- Statista projected Poland "Online Education" revenue at EUR 311.7M in 2024 (a projection, not a measurement). **[MR]** — [Statista](https://www.statista.com/outlook/emo/online-education/poland)
- Poles trail EU leaders (Netherlands, Finland, Sweden) in online-learning participation (Eurostat, via Rzeczpospolita). **[official stat, secondary]** — [rp.pl](https://www.rp.pl/rynek-pracy/art39783761-polacy-daleko-za-unijna-czolowka-w-edukacji-online)
- Reuters Institute Digital News Report: 13% in Poland pay for online news (2025 country page). **[survey, 2025]** — [Reuters Institute](https://reutersinstitute.politics.ox.ac.uk/digital-news-report/2025/poland)

### Inferences
- Use filings, not forecasts. The pattern in filings: one-off purchases of generic self-paced courses are shrinking (Udemy consumer transactional -$39.8M) while recurring products grow (Udemy consumer subscribers +102%, beehiiv paid +138%, Substack 3M -> 5M in about a year, Whop GMV multiplying).
- B2B is where course money moved: Udemy Business is 66% of Udemy revenue and growing; consumer is declining.
- Data/licensing is a growing line even inside a declining content business (Shutterstock data +16% while Q4 content -11%).
- Polish market numbers are too coarse to size a creator-product niche; treat Poland as roughly a $1-1.5B total digital-education market in which creator-sold products are an unknown fraction.

### Gaps
- No verified first-party numbers for Gumroad GMV, Lemon Squeezy, Podia, Skool, AppSumo, Notion Marketplace, Canva creators, Creative Market, ThemeForest/Envato standalone, or PromptBase.
- No measured share of digital downloads in Etsy GMS.
- No reliable size for templates, presets, audio packs, digital planners, B2B reports or licences as separate categories; I found only listing counts and anecdotes.
- Eurostat 2025 figures on online-course participation (EU/PL) were not retrieved.

## 2. What do platform datasets show about what actually sells, and how are creator incomes distributed?

### Takeaway
Every dataset shows a steep power law: the median seller earns close to nothing, and the top 1-4% take most of the revenue, across Gumroad, indie SaaS, YouTube, subscription apps and creator surveys. Product types with the highest median revenue per seller are courses, bundles, software/dev tools and memberships; the lowest are ebooks and single low-priced downloads.

### Cited Findings
Gumroad (third-party scraped estimates; Gumroad itself publishes no category data)
- InsightRaider 2026 dataset (revenue estimated from ratings counts): median creator about $72/month; 44% of products generated exactly $0; median product 28 sales at a $13 median price, about $364 lifetime. **[3P-est, 2026, snippet, not verified on page]** — [InsightRaider via DEV](https://dev.to/insightraider/72month-thats-what-the-median-gumroad-creator-earns-these-5-niches-break-the-pattern-49f0)
- Concentration claims from the same vendor conflict: "top 1% of products capture 77.3% of tracked revenue" vs "99.5% of platform revenue accrues to the top 1% of creators". **[3P-est, internally inconsistent]** — [InsightRaider via DEV](https://dev.to/insightraider/how-to-sell-digital-products-on-gumroad-in-2026-146k-products-analyzed-4ddp)
- Category: Software Development is the top-revenue Gumroad category at $65.8M, 32% of tracked revenue (another post from the same ecosystem claims one category takes 88%, which does not reconcile). Sub-niche averages: Blender tutorials about $1,400 per product, Figma/UI-UX about $1,600; average revenue per seller $2,326. **[3P-est]** — [DEV post](https://dev.to/solobillions/i-analyzed-146k-gumroad-products-heres-what-actually-makes-money-5e8i)
- Profitable.app (data updated June 2026): median product grosses about $88 lifetime among products that sell; by type, median revenue among earners is about $154 for courses, about $209 for bundles, about $35 for ebooks. **[3P-est, 2026]** — [profitable.app](https://profitable.app/gumroad/stats)

Indie / micro-SaaS
- Dataset of 3,787 revenue-generating indie SaaS: half make less than $145/month; 2025 launches have a $168 median and 23.5% exceed $1k MRR, versus about half of 2020-2022 launches; median month-over-month growth 0%; 64.4% flat or declining. **[3P-est, 2026]** — [BigIdeasDB](https://bigideasdb.com/state-of-indie-saas-revenue-2026)
- Separate analysis of 5,000+ Stripe-verified startups: median about $140/month, about 1,300 at $1k+ MRR. **[3P-est]** — [Indie Hackers post](https://www.indiehackers.com/post/i-analyzed-5-079-stripe-verified-startups-f0f6bd053f)
- RevenueCat 2026: top-quartile subscription apps grew MRR 80%+ y/y while the bottom quartile shrank more than 33%; a podcast summary puts median growth at about 5% and top-decile above 300%. **[1P dataset, 2026]** — [9to5Mac](https://9to5mac.com/2026/03/04/new-report-looks-into-the-sustainability-of-the-subscription-app-market-for-2026/)

Creator surveys and platform reports
- Goldman (2023): about 4% of creators are "professionals" earning more than $100k/year; share expected to stay steady. **[MR, 2023]** — [Goldman Sachs](https://www.goldmansachs.com/insights/articles/the-creator-economy-could-approach-half-a-trillion-dollars-by-2027)
- Linktree (older study, quoted in 2025 roundups): only 12% of full-time creators make more than $50k/year. G2 2025 roundup: 46% of creators say they are finding success, 58% struggle to monetize. **[survey, mixed years]** — [G2](https://learn.g2.com/creator-economy-statistics)
- Kit/ConvertKit 2022: 15.4% of surveyed creators earn $50-150k (22% of full-time creators); sample is Kit users **(pre-2023, self-selected)**. Kit 2024 (n>1,000): 28% self-employed. No 2025 edition found. **[1P survey]** — [Kit 2022](https://convertkit.com/creator-economy-2022); [Kit 2024](https://convertkit.com/reports/creator-economy-2024)
- Stan State of the Creator Economy 2026: 29% of creators earned from ads/brand deals/sponsorships, 24% from platform payouts, only 14% from digital products or merch; 59K+ creators earned money on Stan in 2025. **[1P survey, 2026]** — [Stan](https://stan.store/blog/state-of-the-creator-economy/)
- Kajabi State of Creator Commerce 2025 (n=1,717, Dec 2024-Jan 2025): creators with community offerings report earning about 2x those without (a later Kajabi release says 40% more); creators who bundle several products earn 4.5x single-product sellers. **[VM / 1P survey, self-reported, internally inconsistent]** — [BusinessWire](https://www.businesswire.com/news/home/20250417375846/en); [Kajabi release](https://www.businesswire.com/news/home/20250916760140/en/Kajabi-Unveils-Companys-Largest-Ever-Product-Upgrade-to-Empower-Next-Generation-of-Creators-Entrepreneurs)
- Substack: top 10 writers collectively earn $40M+/year per secondary sources (Substack itself said about $20M in 2021). **[secondary, unverified]** — [Backlinko](https://backlinko.com/substack-users)
- Whop: 650+ sellers have earned $1M+ out of about 184k sellers (about 0.35%). **[1P/3P]** — [Sacra](https://sacra.com/c/whop/)
- Notion templates: anecdotal top earners (Thomas Frank about $1M total, Easlo $239k in a year, Nick Lafferty $80k in 12 months); no aggregate data. **[VM anecdotes, 2024]** — [Kajabi blog](https://www.kajabi.com/blog/how-to-sell-notion-templates)
- GPT Store: no payout data; anecdotes range from "$0 with 80 GPTs" to one promotional "$10k" case. **[anecdote]** — [OpenAI community](https://community.openai.com/t/has-anyone-made-money-from-gpts/961791)

Poland
- "Ekonomia twórców po polsku 2024" (Imker / Influencers Live Wrocław): one in three creators who sell their own products makes more than 10,000 PLN/month; 31.4% treat creating purely as a hobby. **[survey, 2024]** — [iFirma](https://www.ifirma.pl/blog/jak-zarabia-tworca-internetowy-influencer-w-polsce.html)
- Selling own courses, trainings and consultations is the most important income source for 38% of surveyed Polish creators (ClickMeeting-linked survey, methodology unverified); among creators active less than a year, 89% do not reach 100k PLN annual revenue. **[survey, secondary]** — [Bezprawnik](https://bezprawnik.pl/wszyscy-chca-zarabiac-w-internecie-nie-kazdy-moze/); [Forbes.pl](https://www.forbes.pl/biznes/nauka-kraula-i-obslugi-koparki-trwa-boom-na-kursy-online-manualnych-umiejetnosci/lslqcld)
- Forbes.pl reports a boom in courses for manual/practical skills (example: a balloon-garland course earning 100k PLN in the first campaign, 400k PLN after eight months). **[anecdote, 2025]** — [Forbes.pl](https://www.forbes.pl/biznes/nauka-kraula-i-obslugi-koparki-trwa-boom-na-kursy-online-manualnych-umiejetnosci/lslqcld)

Academic evidence on income distribution
- YouTube channels in Germany/Austria/Switzerland: earnings Gini coefficient of 0.89, "winner-take-all dynamics" according to the authors. **[PR, 2026]** — [Verwiebe et al., European Societies](https://openalex.org/W4414155446)
- Patreon transaction data: "hundreds of creators" crowdfund more than $2,500 monthly; communication quality predicts success. **[PR, 2020, pre-2023]** — [Regner, J. Cultural Economics](https://openalex.org/W3004569825)
- VTuber livestream income (1,923 VTubers, 1M+ hours): "stark inequality", increasingly concentrated in two agencies. **[PR, 2025]** — [Zhao et al., CHI](https://openalex.org/W4409736134)

### Inferences
- Planning number for a first product with no audience: expect the median, i.e. tens to low hundreds of dollars per month (Gumroad about $72-100/month; indie SaaS about $145-168/month). Anything above $1k/month puts a product in roughly the top quarter of even revenue-generating indie SaaS.
- The category matters less than distribution: the same power law appears in every category. Category choice changes the median and the ceiling, not the shape.
- Relative ordering supported by at least two independent datasets: bundles > courses > single ebooks on revenue per product (profitable.app; Kajabi bundling claim; Bakos-Brynjolfsson bundling theory). Software/dev-tool products are the largest Gumroad revenue pool (one vendor's estimate).
- Only 14% of surveyed creators earn from digital products at all (Stan 2026): digital products remain a minority monetization route, which implies less competition than ads/brand deals but also that most audiences are not yet trained to buy.

### Gaps
- No Gumroad first-party category breakdown; all Gumroad numbers are estimates from one vendor ecosystem with internal inconsistencies.
- No income-distribution data for Teachable, Podia, Skool, Lemon Squeezy, AppSumo, Etsy digital sellers, Notion or Canva creators.
- The full Kajabi 2025 and Stan 2026 reports (product-type revenue splits, price points) were not accessible in this session.
- Polish surveys are small, self-selected and from 2024.

## 3. Typical price points, margins, refund rates, completion rates and repeat purchase by category

### Takeaway
Price ladders are fairly stable: ebooks and templates sell around $10-35, self-paced courses at a median of about $90-150, paid newsletters at $10/month or $100/year, communities at $20-60/month, cohort courses in the low thousands. Completion is in single digits for free/cheap self-paced courses and far higher for cohorts; refund and churn data are mostly vendor rules of thumb, with RevenueCat the only large measured dataset.

### Cited Findings
Benchmarks table (each row sourced below)

| Category | Typical price | Completion / retention | Refund / churn | Evidence quality |
|---|---|---|---|---|
| Ebook / guide | about $13 median Gumroad price; median earner about $35 lifetime | n/a | low-ticket refunds 8-15% (rule of thumb) | 3P-est / VM |
| Self-paced course | Podia mean $137 (first course mean $157, median $89); Ruzuku median $110, mean $416 | MOOCs 6.5% average; open-access courses on Ruzuku 41.9% | mid-ticket 5-10% (rule of thumb) | 1P + PR |
| Cohort course | $1,500-5,000+ (vendor claim) | Ruzuku 53.4% (65.2% for cohorts of 11-25) | high-ticket 3-7% (rule of thumb) | 1P / VM |
| Paid newsletter | $10/month or $100/year median | free-to-paid about 3% typical; outliers 10-20% | finance has the highest churn | 1P |
| Paid community | $20-60/month "sweet spot" | n/a | memberships 2-5% refunds (rule of thumb) | VM |
| Subscription app / SaaS | varies | 27-28% retention (paywall vs freemium) | 56% -> 72% of annual subscribers cancel in year 1 | 1P dataset |
| Template / printable | about $13 Gumroad median | n/a | n/a | 3P-est |

Price points
- Podia analysis of 130,000+ courses: average price $137 (SD 167); creators' first courses average $157, median $89. **[1P, date of analysis not confirmed]** — [Podia](https://podia.com/articles/how-much-should-you-charge-for-your-online-course)
- Ruzuku 2026 platform data: median paid course price $110, mean $416 (inflated by high-ticket coaching and certification programs). **[1P, 2026]** — [Ruzuku](https://www.ruzuku.com/learn/articles/online-course-statistics)
- beehiiv (2,500+ newsletters, June 2026): typical paid price $10/month or $100/year, unchanged since 2024, and about the same for lists under 1,000 and above 100,000. **[1P, 2026]** — [Press Gazette](https://pressgazette.co.uk/newsletters/newsletters-2026-prices-retention-churn/)
- Cohort courses "regularly sell at $1,500-5,000+" versus self-paced "topping out at $200-500". **[VM, no methodology]** — [Systeme.io](https://systeme.io/glossary/cohort-based-course/)
- Skool communities: suggested pricing sweet spot $20-60/month. **[VM]** — [SkoolPrep](https://skoolprep.com/how-to-make-money-on-skool)
- Udemy catalog (academic description, 2022): 157,000 courses, 40M users, 428M enrollments, with regional price differentiation (USA/India/France). **[PR conference paper, 2022, pre-2023]** — [Patra et al., IEEE LWMOOCS](https://openalex.org/W4308216045)

Platform fees (margin drivers)
- Whop: about 3% on direct sales, 30% if the buyer came via Whop Discover; about 97% of GMV is direct. Skool: flat $99/month (a Hobby plan at $9/month plus 10% is reported by a creator). Crossover where Skool becomes cheaper than Whop is near $3,300/month revenue. **[3P-est / VM]** — [Sacra](https://sacra.com/c/whop/); [AI Funnel Insider](https://aifunnelinsider.com/whop-vs-skool-2026/)
- Substack takes 10% of paid subscriptions. **[1P policy, secondary]** — [Sacra](https://sacra.com/c/substack)
- PromptBase keeps 20% and caps new sellers at $4.99 per listing. **[secondary]** — [greyjournal](https://greyjournal.net/?p=105837)
- Notion Marketplace: Notion is merchant of record, payouts biweekly with a $20 minimum, plus 1% FX fee for non-US creators; a competitor claims a 10% + $0.40 fee (not verified against Notion's page). **[1P docs + competitor VM]** — [Notion help](https://www.notion.com/help/selling-on-marketplace); [Payhip](https://payhip.com/blog/how-to-sell-notion-templates/)

Completion
- Average MOOC enrolls about 43,000 students, 6.5% complete; completion falls with course length. **[PR, 2014, pre-2023 but repeatedly confirmed]** — [Jordan, IRRODL](https://openalex.org/W1511434862)
- Behavioral nudges tested on 250,000 students in 247 courses did not raise completion at scale; scaling reduced average effectiveness "by an order of magnitude". **[PR field experiment, 2020]** — [Kizilcec et al., PNAS](https://openalex.org/W3034223452)
- Completion computed on learner intentions is far higher than the traditional rate. **[PR, 2024]** — [Çelik & Çağıltay, Open Praxis](https://openalex.org/W4401996702)
- Ruzuku platform data: scheduled cohort courses complete at 53.4% vs 41.9% for open-access courses (11.5 points); peak 65.2% for cohorts of 11-25; Ruzuku itself notes this is observational, not causal. **[1P, 2026]** — [Ruzuku](https://www.ruzuku.com/learn/articles/cohort-vs-self-paced-completion-study)
- Industry claims of 60-90%+ cohort completion vs 3-15% self-paced are vendor marketing without disclosed data. **[VM]** — [Learnopoly](https://learnopoly.com/cohort-based-learning-statistics/)
- Free-certificate coupons raise verified-track sign-ups but are associated with lower certification rates in the same course. **[PR, 2020]** — [Littenberg-Tobias et al., IRRODL](https://openalex.org/W2999412724)

Conversion, refunds, churn
- Substack free-to-paid: about 3% average in one guide (tech category about 8%); Substack said 5-10% in 2021 **(pre-2023)**. beehiiv median free-to-paid of 0.62% is reported only by a secondary synthesis (unverified); outliers: Tangle converts 16%, top finance newsletters up to 20%. **[secondary, conflicting]** — [Backlinko](https://backlinko.com/substack-users); [Digital Applied](https://www.digitalapplied.com/blog/newsletter-statistics-2026-data-points); [Press Gazette](https://pressgazette.co.uk/newsletters/newsletters-2026-prices-retention-churn/)
- Refund rules of thumb: low-ticket (<$100) 8-15%, mid-ticket ($100-1,000) 5-10%, high-ticket (>$1,000) 3-7%, memberships 2-5%; longer refund windows raise refunds somewhat. **[VM calculator, no dataset]** — [Learning Revolution](https://www.learningrevolution.net/creator-tools/refund-rate-cost-calculator/)
- RevenueCat 2026: more than half of trial cancellations happen on day one; hard paywalls convert almost 6x freemium with nearly the same retention (27% vs 28%); about 56% of annual subscribers cancelled in year 1 in 2025, worsening to about 72% in 2026; reactivation 4.4% for high-priced annual plans vs 28.9% for monthly; AI apps earn about 41% more per user but churn about 30% faster. **[1P dataset, 2026; AI figures via secondary coverage]** — [9to5Mac](https://9to5mac.com/2026/03/04/new-report-looks-into-the-sustainability-of-the-subscription-app-market-for-2026/); [PPC Land](https://ppc.land/ai-apps-earn-41-more-per-user-but-churn-30-faster-revenuecat-finds/)
- Udemy Business net dollar retention 93% (below 100%, i.e. net contraction in existing B2B accounts). **[1P-fin, FY2025]** — [BusinessWire](https://www.businesswire.com/news/home/20260204247314/en/Udemy-Reports-Fourth-Quarter-and-Full-Year-2025-Results)
- Free-trial customers have 59% lower lifetime value than regular customers (digital TV panel). **[PR, 2015, pre-2023]** — [Datta et al., JMR](https://openalex.org/W2787323089)
- Consumer inattention raises subscription sellers' revenue by 14% to more than 200% relative to full attention (ten services, card-network data). **[PP, NBER 2023]** — [Einav et al.](https://openalex.org/W4385799721)

### Inferences
- Gross margin on all these products is high by construction; the real margin killers are platform take rate (3-30%), payment/VAT handling, refunds (5-15% on cheap products) and, above all, customer acquisition. No source gave measured net margins by category.
- Cheap one-off products (ebooks, single templates at about $13) cannot cover paid acquisition; they only work as tripwires in a ladder or as bundle components. The $89-157 course band and the $10/month newsletter band are the lowest tiers where unit economics can plausibly work with organic traffic.
- Recurring revenue looks better on paper than it is: first-year annual cancellation of 56-72% (apps) and inertia-driven revenue (Einav et al.) mean subscription LTV must be measured, not assumed.
- A paid entry point is defensible: payment itself is associated with engagement (Goli et al.) and zero-price coupons lower completion rates.

### Gaps
- No measured refund-rate dataset by category from Paddle, Gumroad, Teachable or Stripe; the available figures are rules of thumb.
- No repeat-purchase / cross-sell rates by category found in any primary source.
- No first-party completion data from Maven or other cohort platforms; no completion data for Polish platforms.
- No verified average prices for Polish courses or ebooks.

## 4. Which niches show the highest willingness to pay, and what is the evidence?

### Takeaway
Evidence for niche-level willingness to pay is weak and mostly vendor opinion; the defensible signals point to niches tied to income or career outcomes (finance/investing, B2B and software skills, AI skills, certification) and away from general information. Academic work shows that credentials and community participation, not content volume, are what people pay for.

### Cited Findings
- Finance newsletters convert best (top finance newsletters up to 20% free-to-paid) but also have some of the highest churn. **[1P, 2026]** — [Press Gazette](https://pressgazette.co.uk/newsletters/newsletters-2026-prices-retention-churn/)
- Substack: tech category leads with about 8% conversion vs about 3% average. **[secondary]** — [Backlinko](https://backlinko.com/substack-users)
- Gumroad estimates: software development is the largest revenue category (32% of tracked revenue); design-tool tutorials (Blender, Figma/UI-UX) average about $1,400-1,600 per product. **[3P-est]** — [DEV post](https://dev.to/solobillions/i-analyzed-146k-gumroad-products-heres-what-actually-makes-money-5e8i)
- AI skills: Coursera/Udemy Global Skills Report 2026 reports GenAI enrollments above 45 per minute (25 in 2025; 12 per minute in the 2025 report; 1 per minute in 2023), AI micro-credential enrollments +122%, critical-thinking enrollments +107% y/y. **[1P marketing report, 2026]** — [Coursera blog](https://blog.coursera.org/global-skills-report-2026/)
- B2B: Udemy Business $524.1M (+6%) vs consumer $265.8M (-9%). **[1P-fin, FY2025]** — [BusinessWire](https://www.businesswire.com/news/home/20260204247314/en/Udemy-Reports-Fourth-Quarter-and-Full-Year-2025-Results)
- Language learning: Duolingo Q2 2025 revenue $252.3M (+41%), paid subscribers 10.9M (+37%), per analyst coverage surfaced by search; verify against Duolingo IR. **[1P-fin via secondary, 2025]** — [Nasdaq/Zacks coverage](https://www.nasdaq.com/articles/chegg-turns-ai-efficiency-enough-offset-subscriber-decline)
- Poland: demand for language and IT tutoring on one platform fell 42% and 55% respectively since the start of the year, attributed to AI (single-platform data). **[1P single platform, via press, 2025-2026]** — [Rzeczpospolita](https://pro.rp.pl/raporty-ekonomiczne/art45050441-ai-uderza-w-korepetytorow-i-szkoly-jezykowe-popyt-spada-nawet-o-55-proc)
- Poland: boom in online courses for manual/practical skills (swimming technique, excavator operation, balloon decoration). **[press, anecdotal]** — [Forbes.pl](https://www.forbes.pl/biznes/nauka-kraula-i-obslugi-koparki-trwa-boom-na-kursy-online-manualnych-umiejetnosci/lslqcld)
- Vendor claims that finance has "the highest lifetime customer values" and that digital marketing courses "command the highest prices" come with no data. **[VM]** — [BloggingX](https://bloggingx.com/online-course-niches/)
- Certification as a purchase reason: a 61-percentage-point hiring preference for a freelancer profile with a MOOC credential over none, though traditional degrees are preferred over MOOCs. **[PR experiment, 2020]** — [Rivas et al., AERA Open](https://openalex.org/W3108490595)
- Microcredentials raise freelancers' earnings via reduced employer uncertainty; the effect is smaller for experienced workers. **[PR, 2022]** — [Kässi & Lehdonvirta, J. Human Resources](https://openalex.org/W4221037326)
- General news: digital subscriptions contributed only 3% of reader revenue at 50 US newspapers ("online news as an inferior good"). **[PR, 2020, pre-2023]** — [Chyi & Ng, Digital Journalism](https://openalex.org/W3011328698)
- A systematic review of 37 studies on willingness to pay for digital journalism finds 17 drivers but ambiguous results because of inconsistent measurement. **[PR review, 2020]** — [O'Brien et al.](https://openalex.org/W3033217106)
- Willingness to pay for premium is more strongly linked to community participation than to the volume of content consumed (Last.fm). **[PR, 2013, pre-2023]** — [Oestreicher-Singer & Zalmanson, MIS Quarterly](https://openalex.org/W3122080363)
- Only 13% of Poles pay for online news. **[survey, 2025]** — [Reuters Institute](https://reutersinstitute.politics.ox.ac.uk/digital-news-report/2025/poland)

### Inferences
- Ranking by strength of evidence for willingness to pay: (1) B2B / employer-paid skills and compliance (filings); (2) money/finance and investing information (highest conversion, but high churn and, in the EU/Poland, regulatory exposure for anything resembling investment advice); (3) AI implementation skills (very fast enrollment growth, but supply is growing at least as fast); (4) career credentials and exam prep (experimental evidence on signalling value); (5) software/design tool skills (Gumroad estimates). Health, parenting and hobbies have no quantified evidence in what I found; hobby/manual-skill demand in Poland is anecdotal.
- Legal/compliance and financial document templates combine three of the supported drivers (B2B payer, outcome-linked, verification matters). I found no dataset on them, so this is an inference, not a finding.
- Language tutoring is polarizing: an AI-native app (Duolingo) grows 41% while human tutoring demand on a Polish platform falls 42%. Niche willingness to pay is shifting to the product form, not disappearing.

### Gaps
- No primary dataset gives revenue per customer or conversion by niche for Podia, Teachable, Kajabi, Thinkific or Skool.
- No evidence found for parenting, health/fitness or hobby niches beyond vendor opinion.
- No data on legal/compliance template demand or pricing (globally or in Poland).
- No candidate-survey data on willingness to pay for exam prep (CFA, PMP, AWS, Polish professional exams).

## 5. How has generative AI changed demand in 2025-2026: what got commoditized, what gained?

### Takeaway
Peer-reviewed and filing evidence agrees: generic answers, simple writing/translation, homework help, stock images and commodity ebooks lost demand or unit revenue (declines of roughly 17-50%), while AI implementation work, data licensing, communities with social ties, credentials and AI-native apps gained. Markets where AI lowers production cost tend to grow in volume while prices and revenue per item fall.

### Cited Findings
Commoditized / losing
- Stack Overflow activity fell 25% within six months of ChatGPT relative to Russian/Chinese counterparts and maths forums; post quality unchanged; decline similar for experienced and inexperienced users. **[PR, 2024]** — [del Rio-Chanona et al., PNAS Nexus](https://openalex.org/W4402462263)
- Job posts for automation-prone writing and coding work fell 21% within eight months of ChatGPT; image-creation posts fell 17% after image AI; remaining jobs are more complex and better paid. **[PR, 2025]** — [Demirci, Hannane, Zhu, Management Science](https://openalex.org/W4406798513)
- Demand for substitutable freelance skills (writing, translation) fell 20-50% relative to trend, most for short 1-3 week jobs; demand for novices declined. **[PR, 2025]** — [Teutloff et al., JEBO](https://openalex.org/W4406893601)
- Freelancers in highly affected occupations lost employment and earnings; past quality did not protect them, and top freelancers appear disproportionately affected. **[PR, 2024]** — [Hui, Reshef, Zhou, Organization Science](https://openalex.org/W4402758071)
- Chegg: subscribers down 40% to 2.6M (attributed mainly to traffic lost to Google AI Overviews); Q3 2026 revenue $46.5M; company says AI "hit our business hard". **[1P-fin, 2025-2026]** — [Nasdaq](https://www.nasdaq.com/articles/chegg-turns-ai-efficiency-enough-offset-subscriber-decline); [Chegg Q3 2026 via Morningstar](https://www.morningstar.com/news/globe-newswire/9868915/chegg-reports-third-quarter-2026-earnings)
- Self-published ebooks on Amazon (14,419 genre-fiction titles, 2023-2026): books with sales grew 19.2-fold while revenue grew 8.9-fold, so revenue per selling book fell in most genres; books with substantial AI text gained share of sales and top ranks. **[PP, arXiv 2026]** — [Chakrabarty et al.](https://openalex.org/W7170218259)
- Stock images: after a marketplace allowed GenAI images, production +136%, total sales +82%, but non-GenAI sales -28% and non-GenAI active artists -29%; GenAI output is concentrated in characteristic space and human creators move into niches. **[PR, QJE 2026]** — [Goldberg & Lam](https://openalex.org/W4409679099)
- Shutterstock Q4 2025 content revenue -11% and weak new-customer acquisition. **[1P-fin]** — [Shutterstock IR](https://shutterstock.gcs-web.com/node/14551)
- Illustrators on Pixiv who did not adopt AI reduced uploads after a text-to-image launch, losing viewer attention; comic artists were less affected. **[PP, NBER 2026]** — [Kim, Jin, Lee](https://openalex.org/W7125714198)
- Art outsourcing platform (China): prices -64%, order volume +121%, total revenue +56%, driven by low-end personal orders. **[PP, 2023]** — [Zhang, Yuan, Xiong](https://openalex.org/W4388685257)
- News publishers in Poland: AI Overviews and AI Mode launched in 2025 and reduced referral traffic. **[survey report, 2026]** — [Reuters Institute Poland 2026](https://reutersinstitute.politics.ox.ac.uk/digital-news-report/2026/poland)
- Udemy consumer transactional course purchases -$39.8M in 2025 (the company frames this as a pivot to subscriptions; AI is not named as the cause). **[1P-fin]** — [BusinessWire](https://www.businesswire.com/news/home/20260204247314/en/Udemy-Reports-Fourth-Quarter-and-Full-Year-2025-Results)

Gaining
- Demand for machine-learning programming +24% and AI chatbot development "nearly tripled" on a freelancing platform. **[PR, 2025]** — [Teutloff et al.](https://openalex.org/W4406893601)
- Reddit developer communities showed no decline while Stack Overflow fell; the authors point to "social fabric" as a buffer. **[PR, 2024]** — [Burtch, Lee, Chen, Scientific Reports](https://openalex.org/W4396674231)
- Data licensing: Shutterstock Data, Distribution & Services +16% to $203.3M. **[1P-fin, FY2025]** — [Yahoo Finance](https://finance.yahoo.com/news/shutterstock-sstk-reports-989-9m-114655765.html)
- AI skills training: GenAI enrollments 45+/minute, AI micro-credentials +122%. **[1P marketing, 2026]** — [Coursera blog](https://blog.coursera.org/global-skills-report-2026/)
- AI-native consumer apps: 27.1% of subscription apps are AI-powered and earn about 41% more per user but churn about 30% faster. **[1P dataset via secondary, 2026]** — [PPC Land](https://ppc.land/ai-apps-earn-41-more-per-user-but-churn-30-faster-revenuecat-finds/)
- Paid newsletters and memberships kept growing through the AI period (beehiiv paid revenue +138% in 2025; Patreon more than $2B/year). **[1P]** — [Press Gazette](https://pressgazette.co.uk/newsletters/newsletters-2026-prices-retention-churn/); [Axios](https://www.axios.com/2025/08/05/patreon-10-billion-creator-economy-ai)
- Higher-skilled freelancers adapt by moving into programming-intensive work; lower-skilled ones are left behind. **[PR, ISR 2026]** — [Liu et al.](https://openalex.org/W7223273929)

Limits of AI as a substitute (room for guided products)
- Titles with field evidence: "Generative AI without guardrails can harm learning" (PNAS 2025) and "The Uneven Impact of Generative AI on Entrepreneurial Performance: Evidence from a Field Experiment in Kenya" (Management Science 2026). Abstracts were not returned by OpenAlex, so no numbers are quoted. **[PR]** — [Bastani et al.](https://openalex.org/W4411627694); [Otis et al.](https://openalex.org/W7167915571)
- Generative AI raises individual creativity but reduces collective diversity of content (title-level finding). **[PR, 2024]** — [Doshi & Hauser, Science Advances](https://openalex.org/W4400578758)

### Inferences
- Commoditized: "how to do X" ebooks and FAQ-style courses, generic prompt packs, simple copy/translation, undifferentiated stock assets, presets and single graphics, homework-help content. The consistent mechanism is that supply explodes, so price and revenue per item fall even where total sales rise.
- Gained or protected: (a) implementation and done-for-you/done-with-you services wrapped around AI; (b) tools and agents that perform the task rather than describe it; (c) communities and cohorts with real social ties; (d) credentials/certification where a third party cares; (e) proprietary or curated data and licences; (f) products requiring coherence across many pieces (systems, sequences), by analogy with comic artists being less affected than illustrators.
- AI wrappers and micro-tools are the most crowded response: recent indie SaaS cohorts reach $1k MRR at half the rate of 2020-2022 cohorts, and AI apps churn faster. Domain depth (law, finance, a regulated workflow) is the plausible differentiator; code alone is not.
- For a founder with domain expertise in a regulated field, the evidence favours "tool or template system + verification + community/cohort" over "information product".

### Gaps
- No rigorous study of AI's effect on online-course or template sales specifically (only freelance, Q&A, stock-image, illustration and book markets). The OpenAlex search for ChatGPT's effect on tutoring/education-platform demand returned only commentary papers.
- No data on prompt-pack or GPT/agent marketplace revenue trends; PromptBase and GPT Store publish nothing usable.
- No evidence found on consumer willingness to pay a premium for human-made or "AI-free" content (the one relevant OpenAlex hit is a 2026 SSRN preprint on AI labels, not retrieved in full).
- Causality for Udemy's consumer decline is not established.

## 6. Academic evidence on demand and willingness to pay for digital / information goods, paid MOOC conversion, paywalls and subscriptions

### Takeaway
The literature says general information has low willingness to pay, zero is a special price, bundling and versioning raise profit for zero-marginal-cost goods, and what converts free users is social engagement, a credential or an outcome. For courses, paying is associated with engagement, completion is in single digits by default, and certificates carry measurable but limited signalling value.

### Cited Findings
Online courses and certificates
- Average MOOC: about 43,000 enrolled, 6.5% complete. **[PR, 2014]** — [Jordan](https://openalex.org/W1511434862)
- "The MOOC pivot" (Science, 2019): OpenAlex returns only a one-line abstract ("What happened to disruptive transformation of education?"); cited here as the reference for MOOC providers' move to paid professional credentials, without numbers. **[PR, 2019]** — [Reich & Ruipérez-Valiente](https://openalex.org/W2910811057)
- Payment and engagement on Coursera, including a sunk-cost mechanism (abstract not available in OpenAlex; described from title and keywords only). **[PR, JMR]** — [Goli, Chintagunta, Sriram](https://openalex.org/W3157101706)
- Large-scale nudges do not raise completion. **[PR field experiment]** — [Kizilcec et al.](https://openalex.org/W3034223452)
- MOOC credential: 61-point preference over no credential; all traditional degrees preferred over a MOOC. **[PR experiment]** — [Rivas et al.](https://openalex.org/W3108490595)
- Microcredentials raise earnings through reduced uncertainty, less so for experienced workers. **[PR]** — [Kässi & Lehdonvirta](https://openalex.org/W4221037326)
- Paid-knowledge marketplaces: user-generated signals (ratings, followers, upvotes) and post-purchase refund warranties are studied as sales drivers (abstracts not available; no numbers quoted). **[PR]** — [Zhang et al., J. Business Research](https://openalex.org/W3042387464); [Fang et al., Information & Management](https://openalex.org/W3131542013)
- Instructor strategies differ between Udemy (per-course sales) and Skillshare (subscription pool). **[PR, 2021]** — [Cisel & Pontalier](https://openalex.org/W3198111550)

Paywalls and willingness to pay for content
- Digital subscriptions = 3% of reader revenue at 50 US newspapers. **[PR, 2020]** — [Chyi & Ng](https://openalex.org/W3011328698)
- The NYT paywall produced engagement and print-spillover externalities besides direct subscription revenue. **[PR, 2018]** — [Pattabhiramaiah, Sriram, Manchanda, J. Marketing](https://openalex.org/W2593021465)
- Further paywall studies retrieved without abstracts (no numbers quoted): Chiou & Tucker 2013; Aral & Dhillon (Management Science); Lambrecht & Misra "Fee or Free". **[PR]** — [Chiou & Tucker](https://openalex.org/W2075974558); [Aral & Dhillon](https://openalex.org/W3015521008); [Lambrecht & Misra](https://openalex.org/W3122597397)
- Review of 37 studies: 17 drivers of paying for digital journalism, ambiguous because of measurement. **[PR review]** — [O'Brien et al.](https://openalex.org/W3033217106)

Freemium, trials, subscriptions
- Willingness to pay for premium tracks community participation more than content consumption. **[PR, 2013]** — [Oestreicher-Singer & Zalmanson](https://openalex.org/W3122080363)
- Free-trial customers: 59% lower lifetime value. **[PR, 2015]** — [Datta, Foubert, van Heerde](https://openalex.org/W2787323089)
- Inattention raises subscription seller revenue by 14% to more than 200%. **[PP, NBER 2023]** — [Einav, Klopack, Mahoney](https://openalex.org/W4385799721)
- Retrieved without abstracts (described by title only): "Monetizing Freemium Communities" (MISQ), "Selling the Premium in Freemium" (J. Marketing), "The effect of free sampling strategies on freemium conversion rates" (Electronic Markets), "Moving from Free to Fee" (J. Marketing), "Design and Evaluation of Optimal Free Trials" (Management Science). **[PR]** — [Bapna et al.](https://openalex.org/W2603982726); [Gu, Kannan, Ma](https://openalex.org/W2897722974); [Koch & Benlian](https://openalex.org/W2551448766); [Pauwels & Weiss](https://openalex.org/W2168591670); [Yoganarasimhan et al.](https://openalex.org/W4297830788)

Pricing of information goods
- Classic theory and experiments retrieved (no abstracts; cited for the concept only): bundling of information goods; zero as a special price; pay-what-you-want (mechanism paper, Science field experiment, integrative review); digital economics review; long tail and search costs. All pre-2023. **[PR / theory]** — [Bakos & Brynjolfsson](https://openalex.org/W3122946301); [Shampanier, Mazar, Ariely](https://openalex.org/W2147664728); [Kim, Natter, Spann](https://openalex.org/W2164355801); [Gneezy et al.](https://openalex.org/W2055274915); [Gerpott review](https://openalex.org/W2555482051); [Goldfarb & Tucker](https://openalex.org/W4252846263); [Brynjolfsson, Hu, Simester](https://openalex.org/W2159347126)

### Inferences
- The academic picture supports a product built as: free or near-free sample (zero-price effect), a paid entry that is not zero (payment and engagement), a bundle or tiered premium (bundling/versioning), a community layer (strongest observed correlate of paying), and a credential or verifiable outcome where a third party values it.
- Stated willingness to pay is a poor guide (O'Brien review; newspapers' 3%). Validate with pre-sales, not surveys.
- Subscription revenue is partly inertia; in the EU this is a compliance and reputation risk as well as an inflated LTV.
- Most of the canonical evidence predates 2023 and comes from news, music and MOOCs. It transfers in direction, not in magnitude, to templates, tools and creator products.

### Gaps
- No meta-analysis was found on paid-conversion rates of MOOCs or creator courses; "paid conversion" for Coursera/edX was not available in any retrieved abstract.
- No peer-reviewed work found on Gumroad, Substack earnings, Notion/Canva templates, printables, digital planners, presets or audio packs; Substack hits in OpenAlex were qualitative media-studies papers.
- Several key abstracts are missing in OpenAlex (Goli et al., Bapna et al., Aral & Dhillon, Chiou & Tucker, Bastani et al.), so their magnitudes are not reported here; a full-text pass is needed before quoting numbers.
- OpenAlex daily budget and rate limits blocked roughly two thirds of the attempted searches; coverage of 2025-2026 creator-economy papers is therefore incomplete.
