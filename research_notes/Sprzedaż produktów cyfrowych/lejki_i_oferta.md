# Funnel and offer architecture for selling digital products (2023-2026): benchmarks, evidence, failure modes

Research date: 28 November 2026. Evidence labels used on every number:

- **[P]** peer-reviewed study (design named: meta-analysis, field experiment, lab experiment, observational, theory)
- **[M]** measured dataset published by a platform about its own customers (still self-selected, unaudited)
- **[V]** vendor claim without disclosed method (treat as an upper bound)
- **[A]** single anecdote or self-reported case
- **[S]** secondary aggregator or blog repeating a number whose original could not be checked

Access limits in this session: direct page fetches were blocked for unbounce.com, baymard.com, ruzuku.com and indiehackers.com (hosts outside the session's allowed network). Numbers from those sites come from search-result extracts, not from reading the full page. They should be re-checked against the original before publication. The companion registry of 64 scholarly works retrieved from OpenAlex is in `rejestr_lejki.jsonl` (ids RL001-RL064). Years quoted in the text are journal publication years; the registry carries the year OpenAlex records, which differs for a few works (for example Goli et al. 2019 in OpenAlex, 2021 in the journal).

---

## 1. Funnel types and their realistic benchmarks

### Takeaway
Only three funnel stages have reasonably measured benchmarks: landing-page conversion (median 6.6% across all page types), free-to-paid conversion for products with a free tier (roughly 0.6-5% depending on the product), and webinar attendance (33-60% of registrants). Everything specific to "info-product" funnels (tripwire, challenge, VSL, evergreen webinar, high-ticket call) rests on vendor claims and single anecdotes, and no independent dataset was found.

### Cited Findings

**Lead magnet → email sequence → offer**
- All-industry median landing-page conversion is 6.6%, from 41,000 pages, 464 million visits and 57 million conversions, July 2023-July 2024. This covers every landing-page goal, not only opt-in pages. [M, 2024] — [Unbounce Conversion Benchmark Report](https://unbounce.com/conversion-benchmark-report/)
- By sector in the same report: SaaS median 3.8%; financial services 8.3% (8.4% in a secondary summary). [M, 2024] — [Unbounce](https://unbounce.com/conversion-benchmark-report/); [MarketingProfs summary](https://marketingprofs.com/charts/2024/52374/landing-page-conversion-benchmarks)
- Email is the highest-converting traffic source in that report: 13.9% median in professional services, 28.6% in ecommerce. [M, 2024] — [Unbounce press release](https://prnewswire.com/news-releases/unbounces-2024-conversion-benchmark-report-proves-that-attention-spans-are-declining-and-so-are-conversion-rates-302239407.html)
- Lead-magnet and opt-in pages "typically" convert 5-20%, cold traffic 3-10%. This is a stated range, not a measured median. [V, 2026] — [Leadpages blog](https://leadpages.com/blog/landing-page-conversion-benchmarks-2026)
- GetResponse opt-in pages average 10.76%, as quoted by a third party; the original was not verified. [S] — [LanderLab](https://landerlab.io/blog/landing-page-conversion-rate)
- Email engagement baseline: average open rate 43.46%, click rate 2.09%, click-to-open 6.81%, unsubscribe 0.22% (up from 0.08% in 2024, attributed to Gmail's one-click unsubscribe); "authors" category 43.14% open and 2.75% click. Data window December 2024-November 2025. [M, 2025] — [MailerLite benchmarks](https://www.mailerlite.com/blog/email-marketing-benchmarks)
- Omnisend's 2025 dataset shows a lower average open rate of about 30.22%. Open rates are not comparable across providers. [M, 2025] — [Omnisend](https://omnisend.com/blog/email-marketing-benchmarks/)
- Automated flows convert better than broadcasts: clothing and accessories email campaigns 0.97% placed-order rate against 1.62% for flows. This is physical ecommerce, not digital products. [M, 2026] — [Klaviyo benchmarks](https://klaviyo.com/products/email-marketing/benchmarks)
- Welcome flows average $2.65 revenue per recipient in Klaviyo's 2024 report, as relayed in a community post. [S, 2024] — [Klaviyo community](https://community.klaviyo.com/strategic-advice-27/klaviyo-s-benchmark-report-takeaways-and-use-cases-12028?postid=48010)
- Adding the recipient's name to marketing emails consistently benefited advertisers in randomised field experiments with three companies and millions of emails. [P, field experiment, 2018] — [Sahni, Wheeler, Chintagunta](https://openalex.org/W2788138901)

**Low-ticket "tripwire" / self-liquidating offer funnel**
- No audited dataset was found. Search returned podcasts and agency blogs only.
- Typical described structure: $7-$47 front-end product, with the front end meant to recover ad spend through bumps and upsells rather than to profit by itself. [V] — [Panda Video guide](https://www.pandavideo.com/blog/low-ticket-funnel)
- One agency-reported case: $750,000 in one month mainly from a $127 offer on a reported $200,000 ad spend. [A, unverified] — [The Scaling Season podcast](https://www.buzzsprout.com/2198975/episodes/18175354-high-ticket-businesses-here-s-how-to-start-selling-low-ticket-offers-ep-101)
- One reported "$27 funnel" at 2.5x ROAS on Meta ads. [A] — [The Art of Online Business podcast](https://www.buzzsprout.com/1866710/episodes/18816769-inside-michelle-knight-s-27-funnel-that-hit-2-5x-roas-on-facebook-instagram-ads)
- A hypothetical model, not observed data: $5 cost per click, $79 entry offer at 4% purchase rate, $297 bump taken by 22%, $1,200 core offer bought by 8% within 14 days, giving $8.30 revenue per click. The same source warns that weak cheap offers produce upsell take rates near 2%, which breaks the model. [V, illustrative] — [growthmechanic blog](https://growthmechanic1.github.io/landing/blog-post-9.html)
- Causal returns from paid search at eBay were a fraction of non-experimental estimates, and brand-keyword ads had no measurable short-term benefit. Platform-reported ROAS overstates incremental sales. [P, field experiment, 2015] — [Blake, Nosko, Tadelis](https://openalex.org/W2922202912)

**Webinar funnels (live and evergreen)**
- Registrant-to-attendee conversion: 57% in ON24's 2025 report (2024 data), 60% in its 2026 report. ON24 counts on-demand viewing, and its customers are mostly B2B. [M, 2025-2026] — [ON24](https://www.on24.com/blog/key-takeaways-from-the-webinar-benchmarks-report/); [MarketingProfs](https://www.marketingprofs.com/charts/2025/52917/b2b-webinar-benchmarks-conversion-attendance-personalization?e=4)
- Average attendance rate 33% (up from 29%) across 19,000+ webinars. [M, 2025] — [Goldcast](https://www.goldcast.io/blog-post/2025-webinar-statistics-b2b-marketers-should-know)
- Show-up rates of about 50-52% by weekday, Tuesday highest. [M, 2026 report on 2025 data] — [Livestorm](https://livestorm.co/webinar-benchmark-report-2026)
- About 40% of registrants attend live for webinars hosted on Wistia. [M, 2026] — [Wistia](https://wistia.com/learn/marketing/webinar-analytics-benchmarks)
- 49% live attendance, 57% including replays (attributed to Univid). [S] — [Zoom roundup](https://www.zoom.com/en/blog/webinar-statistics/)
- Evergreen/automated: eWebinar claims 40% attendance for live sessions against 83% for its on-demand sessions, and 65% average for its customers. [V] — [eWebinar](https://ewebinar.com/marketing); [eWebinar blog](https://ewebinar.com/blog/increase-webinar-attendance)
- One EverWebinar testimonial reports conversion about 10% lower than live but five times the volume. [A] — [EverWebinar](https://everwebinar.com/?p=331)
- A "63% live versus 19% on-demand conversion" figure circulates (attributed to TwentyThree) without a definition of conversion. [S] — [Zoom roundup](https://www.zoom.com/en/blog/webinar-statistics/)
- No independent study comparing sales conversion of live and automated webinars was found.
- A blog table lists 8-15% purchase conversion for webinar or workshop attendees, without a named source. [S] — [Earnifyhub](https://www.earnifyhub.com/blog/course-launch-data-creator-numbers-0-to-180k.php)

**Product launch (open/close cart) versus evergreen**
- The usual planning assumption is that 1-2% of an email list buys during a launch; "some convert 0%". [V/rule of thumb] — [Paige Brunton](https://www.paigebrunton.com/blog/email-list-size-online-course)
- Kajabi uses 2% of the list as "a common planning assumption". [V, 2025-2026] — [Kajabi](https://www.kajabi.com/blog/why-most-online-courses-never-sell)
- Blog table: engaged list 1.5-3.5%, highly engaged 3-7%, average 1.8% for email and 0.3% for direct social promotion. No named dataset; the page reads like generated content. [S, low confidence] — [Earnifyhub](https://www.earnifyhub.com/blog/course-launch-data-creator-numbers-0-to-180k.php)
- The Focus Course: about 6,000 subscribers, $117,000 in first-week sales. [A, older] — [The Focus Course](https://thefocuscourse.com/behind-the-scenes-six-figure-course-launch)
- One pre-sale case: 25 buyers from 245 subscribers (10.2%). [A] — [Contra case](https://contra.com/p/eYsqBebo-email-marketing-success-for-course-pre-sale)
- One launch debrief reports about 40% of sales in the first 48 hours. [A] — [launch debrief, part 2](https://www.goodreads.com/author_blog_posts/23025116-launch-debrief-pt-2-sales-breakdown-unsubscribes-refund-rates-and)
- No measured comparison of launch against evergreen revenue per subscriber was found.

**Challenge funnels**
- One $17 paid 5-day challenge reported 43% conversion to the back-end offer. [A, published by a platform that sells the model] — [membership.io](https://membership.io/blog/the-paid-5-day-challenge-that-converted-at-43-sarah-williams-coaching-week-playbook)
- "Completion 75-85%, upsell 30-45%" for $19-$47 five-day sprints, no method given. [V] — [CommuniPass](https://communipass.com/blog/interactive-challenge-models-for-creators-2026/)
- No comparison of paid versus free challenges was found.

**VSL funnels**
- No benchmark data of any quality was found for video sales letter funnels in 2023-2026.

**Application / high-ticket call funnels**
- Close rate 15-30% of attended calls; show rate above 80% for same-day or next-day bookings and below 50% beyond five days without follow-up. [V, playbook] — [SegMetrics show-rate playbook](https://segmetrics.io/wp-content/uploads/Playbook-Sales-Call-Show-Rate.pdf)
- Stage ranges from another vendor: lead to application 15-25%, application to call 40-60%, call to close 25-40%. [V] — [Owlclaw benchmarks](https://owlclaw.com/benchmarks/high-ticket-lead-benchmarks)
- General sales survey average close rate 29%, not specific to high-ticket offers. [S] — [Cirrus Insight](https://www.cirrusinsight.com/blog/sales-conversion-rate-benchmarks)

**Free community → paid (Skool model)**
- Posts inside Skool communities give free-to-paid conversion of 3-9.4%, "4% benchmark", or 5-10% of engaged free members within 90 days. None discloses a dataset. [V/A, 2026] — [Skool post](https://www.skool.com/skool-monetization-strategies-2218/freemium-on-skool-real-conversion-data-for-2026); [Skool post](https://www.skool.com/the-visionary-vibe-8324/target-skool-conversion-rates-how-do-you-stack-up)
- One vendor case: a creator with 146,000 YouTube subscribers converted about 1.9% of subscribers to paid members. [A] — [CommuniPass](https://communipass.com/blog/skool-free-vs-paid-community-2026/)
- Kajabi's survey (1,717 respondents, December 2024-January 2025, with Qualtrics) reports that creators with community offerings say they make 2x more than those without. Self-reported and correlational. [M survey, 2025] — [Business Wire](https://www.businesswire.com/news/home/20250417375846/en)
- A randomised field experiment was designed to identify the causal effect of peer influence on adoption of a paid subscription in an online social network. [P, field experiment, 2015] — [Bapna & Umyarov](https://openalex.org/W2117852767)

**Freemium tool → paid**
- Survey of 1,000+ software products: freemium self-serve 3-5% is good and 6-8% great; free trial 8-12% good and 15-25% great; sales-assisted freemium 5-7% good and 10-15% great. Conversion measured as share of new accounts paying within six months. [M survey, 2023] — [Lenny's Newsletter / Kyle Poyar](https://www.lennysnewsletter.com/p/what-is-a-good-free-to-paid-conversion)
- Visitor-to-signup rates are lower for free trials (5%) than for freemium (9%). [M survey, 2023] — [Lenny's Newsletter](https://www.lennysnewsletter.com/p/what-is-a-good-free-to-paid-conversion)
- A secondary article quotes different free-trial thresholds (3-5% good), so the two sources conflict. [S] — [Crazy Egg](https://www.crazyegg.com/blog/free-to-paid-conversion-rate/)
- Large-scale field experiment at a SaaS firm: on average shorter trial lengths maximise acquisition, retention and profitability. [P, field experiment, 2022] — [Yoganarasimhan, Barzegary, Pani](https://openalex.org/W4297830788)
- Customers acquired with free trials differ systematically from regular customers in retention decisions. [P, observational, 2015] — [Datta, Foubert, van Heerde](https://openalex.org/W2787323089)
- Panel of 711 Google Play apps: a free version is positively associated with paid-app sales, and a highly rated free version raises paid sales. [P, observational, 2014] — [Liu, Au, Choi](https://openalex.org/W2015518777)

**Newsletter → paid**
- beehiiv's June 2026 report on its own paid publications: platform-wide median free-to-paid conversion 0.62%; highest niche median 1.93% (sports); top-decile finance lists roughly 18-31%. Figures come from secondary write-ups; the report itself was not opened. [M via S, 2026] — [beehiiv report page](https://www.beehiiv.com/blog/the-state-of-paid-newsletters-2026.md); [Voxbooster summary](https://voxbooster.com/blog/newsletter-paid-subscriber-conversion-statistics-2026)
- Ghost describes a "good" paid conversion as 2-5%. [V] — [Ghost](https://ghost.org/resources/examining-your-analytics/)
- Substack once promoted 10% as a reasonable estimate and later moved to a sliding scale tied to open rate. [S] — [Simon Owens](https://simonowens.substack.com/p/whats-a-realistic-conversion-rate)
- The Free Press is cited at 11.3% free-to-paid against 2-5% for typical freemium models. [S] — [Sacra](https://sacra.com/chat/h/8549a1a3-c03a-454f-9f71-a6408d97608c/)

**Marketplace listing → own list**
- No data was found on the share of Etsy or Gumroad digital sellers' revenue that comes from the marketplace versus their own audience. Only advice articles exist. — [Printify guide](https://printify.com/blog/how-to-sell-digital-downloads-on-etsy/)

### Inferences
- A defensible planning model for a first test uses the measured numbers at their conservative end: opt-in page 5-10% of visitors, launch purchase 1-2% of the list. For a 2,000-visitor test that is 100-200 subscribers and 1-4 buyers. A first test therefore cannot distinguish a 1% from a 3% offer statistically; it can only show whether anyone buys.
- The 0.62% platform median for newsletters against the 5-10% "rule" shows how far guru numbers sit above medians. The same gap should be assumed for tripwire, challenge and webinar claims, where no medians exist at all.
- Funnel types that require live selling (challenge, webinar, call) have the best anecdotes and the weakest data, so they are better treated as later experiments once the offer itself has sold.

### Gaps
- No independent benchmark for tripwire/self-liquidating funnels, VSLs, challenges or evergreen webinars.
- No measured launch-versus-evergreen comparison.
- No marketplace-to-own-list migration data.
- ClickFunnels-specific published data was not retrieved.

---

## 2. Benchmarks: opt-in, lead-to-customer, sales page, bumps, upsells, abandonment, refunds, AOV, LTV

### Takeaway
Order bumps (20-40% take rate) and post-purchase upsells (about 5-16%) are the best-supported levers for raising order value, but every number comes from checkout or app vendors. Cart abandonment near 70% is the one robust multi-study figure. Refund rates and sales-page conversion by price have no authoritative source.

### Cited Findings

**Order bumps**
- Order bumps convert at 35-40% "across SamCart", and one bump raises average customer value by about 31%; the same guide mentions a single 56% case as unusually high. [V] — [SamCart order bump guide](https://www.samcart.com/blog/the-complete-guide-to-order-bumps)
- A "healthy" bump take rate is 20-40%, and take rate drops sharply after the first bump when several are shown. [V] — [Systeme.io glossary](https://systeme.io/glossary/order-bump/)
- Order bumps 37.8% and post-purchase offers 14.6% in a study of 1,847 North American digital businesses. The publisher's own pages disagree on the study date (2025 versus January-July 2026) and on category figures, and no method is published. [V/S, low confidence] — [Focus Digital 2026](https://focus-digital.co/average-upsell-conversion-rate-2026-report/); [Focus Digital 2025](https://focus-digital.co/average-upsell-conversion-rate-2025-report/)
- A seller-side guide notes that take rate is not incrementality: a bump can cannibalise an item the buyer would have added anyway. [V] — [CartMango](https://cartmango.com/order-bump/)
- SamCart's comparison against ThriveCart (21% conversion advantage, 51% higher order value) rests on one customer's split test. [A, vendor] — [SamCart](https://www.samcart.com/compare/samcart-vs-thrivecart)
- ThriveCart's multiple order bumps support digital products only. [V] — [ThriveCart](https://thrivecart.com/?p=34147)
- No published order-bump data from Stripe, Gumroad or Lemon Squeezy was found.

**One-click upsells and downsells**
- About 20% is "a good benchmark to shoot for" on post-purchase upsells. [V] — [SamCart upsell strategies](https://samcart.com/blog/upsell-strategies)
- Post-purchase one-click offers: 3-8% acceptance, above 5% good, tuned stores 8-10%. [V, Shopify context] — [GrowthSuite](https://www.growthsuite.net/resources/shopify-upsell-cross-sell/complete-guide/benchmarks)
- Average about 4.7%, top decile about 28.3%, attributed to a 2023 ReConvert dataset of 40,000+ Shopify merchants; original not verified. [S] — [Digital Applied](https://www.digitalapplied.com/blog/post-purchase-upsell-thank-you-page-2026-ecommerce-playbook)
- Zipify says its merchants average a 16.2% take rate on post-purchase offers. [V, 2026] — [Zipify](https://zipify.com/blog-how-to-upsell-in-2026/)
- SamCart pages state that one-click upsells lift average order value by 68.1% and that 58% of revenue processed comes from upsell transactions. The source and date of these two figures are unclear. [V] — [SamCart](https://samcart.com/blog/how-to-increase-average-order-value)
- No benchmark specific to downsells was found.
- Academic analogue: presenting a fully loaded product and letting buyers delete options is more favourable to the seller than letting them add options to a base model. [P, lab experiments, 2000] — [Park, Jun, MacInnis](https://openalex.org/W2031241465)
- Reactance mediates how upsell timing affects attitudes (2x2 experiment, 250 consumers). [P, lab experiment, 2022] — [Denizci Guillet et al.](https://openalex.org/W4293240617)

**Cart abandonment and recovery**
- Average documented cart abandonment 70.22%, the unweighted mean of 50 studies from 2006-2025, list updated 22 September 2025; Baymard's 2025 checkout report gives 70.19%. [M, meta-compilation, 2025] — [Baymard](https://baymard.com/lists/cart-abandonment-rate)
- Abandoned-cart emails: average click rate about 6%, top 10% of brands 11.3%; top 10% of flows reach $13.70 revenue per recipient. From 143,000+ flows in 2023, physical ecommerce. [M, 2024 report] — [Klaviyo](https://www.klaviyo.com/marketing-resources/abandoned-cart-benchmarks)
- Abandoned-cart flows have the highest placed-order rate of all flows, 3.33% per recipient. [M, 2024] — [Klaviyo](https://www.klaviyo.com/marketing-resources/abandoned-cart-benchmarks)
- Dynamic Yield's live-data abandonment figure is 77.38%, a different method from Baymard's. [S] — [Contentsquare roundup](https://contentsquare.com/en/guides/cart-abandonment/stats/)

**Sales page conversion by price and traffic temperature**
- No measured dataset by price point or traffic temperature was found. Gumroad does not publish conversion by price.
- A third-party scrape estimates average Gumroad page conversion at 3.2%, top pages 8-12%, weak pages 0.5-1%, and says the $30-49 band converts 28% better than under $10. Revenue and conversion are modelled from ratings counts with a multiplier, not measured. [S, modelled, 2026] — [InsightRaider](https://insightraider.com/en/data/gumroad-statistics-2026); [dev.to summary](https://dev.to/insightraider/the-30-49-pricing-sweet-spot-146k-gumroad-products-tested-2oja)
- One creator lowered a product from $49 to $25 and reached about 8% conversion on a small sample. [A] — [Build to Launch](https://buildtolaunch.substack.com/p/how-to-fix-digital-product-conversion-rate)
- Email traffic converts far above other channels on landing pages (13.9-28.6% medians above). [M, 2024] — [Unbounce press release](https://prnewswire.com/news-releases/unbounces-2024-conversion-benchmark-report-proves-that-attention-spans-are-declining-and-so-are-conversion-rates-302239407.html)

**Refund rates**
- No authoritative benchmark from Teachable, Thinkific or Kajabi exists.
- Mid-ticket courses "mostly" see 5-10% refunds; cheaper products higher, high-ticket lower; a longer window raises refunds somewhat. [V] — [Learning Revolution calculator](https://www.learningrevolution.net/creator-tools/refund-rate-cost-calculator/)
- A 4.8% average refund rate attributed to Podia, and an 18% checkout lift from a 30-day guarantee attributed to Teachable, appear in a statistics roundup without verifiable originals. [S, low confidence] — [Voxbooster](https://voxbooster.com/blog/digital-course-sales-statistics-2026/)
- Lifetime-deal marketplaces show much higher refunds: 587 refunds on 1,470 copies sold (about 40%) in one AppSumo launch and 22% in another. Both figures come from a search extract over several Indie Hackers post-mortems; the pages could not be opened, so which post each figure belongs to is unconfirmed. [A] — candidate sources: [Indie Hackers](https://www.indiehackers.com/post/my-appsumo-campaign-zero-audience-362-paying-customers-6281b4a990); [Indie Hackers](https://www.indiehackers.com/post/what-i-learned-making-60k-on-appsumo-d14a3ff92a); [Indie Hackers](https://www.indiehackers.com/post/honest-review-of-our-appsumo-launch-and-how-we-lost-30-of-our-potential-sales-ef30ececc3)
- Blog claim that creators relying on paid ads for over 30% of sales had 2.8x higher refund rates. Unverified. [S, low confidence] — [Earnifyhub](https://www.earnifyhub.com/blog/course-launch-data-creator-numbers-0-to-180k.php)

**LTV by product type**
- Paid newsletters: median subscriber lifetime value from $83 (community category) to $230 (investing). [M via S, 2026] — [beehiiv](https://www.beehiiv.com/blog/the-state-of-paid-newsletters-2026.md)
- Thinkific creators: $460 million in 2025 sales and $175 average revenue per user per month, per a secondary roundup. [S] — [Ruzuku statistics page](https://www.ruzuku.com/learn/articles/online-course-statistics)
- No LTV dataset by digital product format (template, course, membership) was found.

### Inferences
- A cautious model for a first checkout: one bump at 20% take rate priced at 30-50% of the main product raises order value by 6-10%, not the 31% vendors quote. The vendor figure assumes the top of the take-rate range and a high bump price.
- Abandonment recovery matters less at low volume: at 3.33% orders per abandoned-cart recipient, 100 abandoned checkouts recover about three sales.
- Because take rate is not incrementality, a bump should be something the buyer would not have bought separately (a companion template, not a second course).
- Under EU consumer rules, paid extras cannot be pre-ticked, so the "subtractive framing" result has to be used through bundle tiers rather than a pre-checked box.

### Gaps
- Sales-page conversion by price point and by traffic temperature.
- Refund rates by price band from any platform's own data.
- Downsell take rates; order-bump data from Stripe, Gumroad and Lemon Squeezy.
- Incremental (not gross) effect of bumps and upsells.

---

## 3. Offer construction: bundles, bonuses, guarantees, instalments, deadlines, price ladders, memberships, lifetime deals

### Takeaway
The academic record supports bonuses framed as "free" extras, instalment payments and large bundles of near-zero-cost goods. It gives only weak support to the "value ladder" logic that a small first purchase causes a large later one, and the best-known deadline study was retracted in 2026. Memberships churn at roughly 5-9% a month at creator price points, and lifetime deals carry 20-40% refunds in reported cases.

### Cited Findings

**Bundles and bonuses**
- Bundling many unrelated information goods at one price can be surprisingly profitable because bundle valuations are more predictable than single-item valuations. [P, theory, 1999] — [Bakos & Brynjolfsson](https://openalex.org/W3122946301)
- Holding total saving constant, reductions framed as "free" product options are rated more favourably than plain discounts, which beat rebates. [P, lab experiment, 2001] — [Munger & Grewal](https://openalex.org/W2002121006)
- The perceived value of a bundle discount depends on which item the discount is attached to (six experiments). [P, lab experiments, 2004] — [Janiszewski & Cunha](https://openalex.org/W2095532324)
- Bundling is predicted to "decouple" costs from benefits and weaken the sunk-cost pull to consume each item. [P, 2001] — [Soman & Gourville](https://openalex.org/W2003217648)
- Choice overload is conditional on moderators such as choice-set complexity, task difficulty, preference uncertainty and decision goal. [P, meta-analysis, 2015] — [Chernev, Böckenholt, Goodman](https://openalex.org/W2087356051)

**Guarantees**
- A money-back guarantee can signal quality when buyers cannot inspect the product, with the seller's transaction costs making the signal credible. [P, theory, 1995] — [Moorthy & Srinivasan](https://openalex.org/W2021573668)
- Free sample trials and money-back guarantees partly substitute for each other; an analytical model sets out when to offer both. [P, theory, 2024] — [Lin, Choi, Kuo](https://openalex.org/W4401278412)
- No measured dataset on conversion lift from guarantees for digital products was found; the "+18%" figure above is unverified.

**Payment plans and BNPL**
- BNPL adoption at a large US retailer is associated with higher purchase incidence and larger purchase amounts, more for small-basket and credit-reliant shoppers; three preregistered experiments attribute this to lower perceived financial constraints. [P, difference-in-differences plus experiments, 2024] — [Maesen & Ang](https://openalex.org/W4402116954)
- Transaction data and experiments show greater spending with BNPL than with other payment modes. [P, 2025] — [Ashby et al.](https://openalex.org/W4407049287)
- Stripe A/B test over 150,000+ checkout sessions: showing a BNPL option produced up to 14% more revenue, and 66% of BNPL volume was net-new. Figures are from secondary coverage and Stripe's guide; "up to" marks a maximum. [M/V, 2023-2025] — [Stripe blog](https://stripe.com/en-hk/blog/testing-the-impact-of-buy-now-pay-later); [Payments Dive](https://www.paymentsdive.com/news/how-buy-now-pay-later-benefits-merchants/720281/)
- One seller: 90% of instalment customers chose 10 payments of $99 although it cost $100 more than the alternative plan. [A] — [MyWifeQuitHerJob](https://mywifequitherjob.com/?p=27123)
- Teachable author: more than 60% of payment-plan sales end without all payments completed. Method unclear. [V, low confidence] — [Teachable](https://www.teachable.com/blog-author/michael-cliffe)
- Two to six months is the most common plan length among Podia creators. [V] — [Podia](https://podia.com/articles/use-payment-plans)
- Reframing a price as small ongoing expenses can raise compliance ("pennies-a-day"). [P, lab experiments, 1998] — [Gourville](https://openalex.org/W2029136992)

**Deadlines, cohort close dates and scarcity**
- Meta-analysis of 416 effect sizes from 131 studies: scarcity cues raise purchase intentions; time-based scarcity works best for high-involvement products, demand-based for utilitarian products, supply-based for experiences. Outcome is intention, not sales. [P, meta-analysis, 2022] — [Barton, Zlatevska, Oppewal](https://openalex.org/W4284967436)
- Ariely & Wertenbroch (2002), the standard citation for deadlines improving performance, was retracted by Psychological Science in 2026. A replication of Study 2 found negligible effects of deadlines, and Data Colada concluded that the Study 2 data had been tampered with. Both authors agreed to the retraction; the notice does not establish who altered the data. [P, replication, 2026] — [Hyndman & Bisin replication](https://openalex.org/W4399154521); [Retraction Watch](https://retractionwatch.com/2026/09/03/procrastination-study-duke-dan-ariely-psychological-science-data-colada-tampering-retraction/); [Data Colada 138](https://datacolada.org/138)
- Field experiment with students: strong demand for self-imposed deadlines, but deadlines did not increase completion rates. [P, field experiment, 2020] — [Bisin & Hyndman](https://openalex.org/W1594026760); [NBER w19874](https://www.nber.org/papers/w19874)
- A crawl of about 53,000 product pages on 11,000 shopping sites documented deceptive urgency and scarcity patterns. [P, observational, 2019] — [Mathur et al.](https://openalex.org/W4288086176)
- Experiments give the first public evidence of how strongly dark patterns raise acceptance of unwanted offers. [P, experiments, 2021] — [Luguri & Strahilevitz](https://openalex.org/W3137759237)

**Price ladders, value ladder and ascension**
- Foot-in-the-door meta-analysis of 120 experimental groups: replicable but weak, with nearly half of studies showing no effect or the wrong direction. [P, meta-analysis, 1983] — [Beaman et al.](https://openalex.org/W1973945715)
- Foot-in-the-door r = .17 and door-in-the-face r = .15 even under optimal conditions; both need a prosocial topic. [P, meta-analysis, 1984] — [Dillard, Hunter, Burgoon](https://openalex.org/W1539499155)
- A direct replication in Poland and Ukraine notes that the original effect size has never been reproduced. [P, 2019] — [Gamian-Wilk & Doliński](https://openalex.org/W2971802883)
- Randomised field experiment: adding further premium formats increased demand for the existing premium version; the AMA summary reports paperback revenue up 8.9% after adding a hardback. [P, field experiment, 2018] — [Gu, Kannan, Ma](https://openalex.org/W2897722974); [AMA summary](https://www.ama.org/2018/12/06/winning-the-freemium-to-premium-product-wars/)
- Cross-buying by customers with adverse traits (low spend, reversals, heavy service use, promotion-only buying) produces growing losses. [P, observational, 2012] — [Shah et al.](https://openalex.org/W2064861448)
- When customers name their own price, fewer buy than at a low fixed price, because of self-image concerns. [P, field experiments, 2012] — [Gneezy et al.](https://openalex.org/W2043074681)

**Memberships and churn**
- Education subscriptions have the highest voluntary churn of any Recurly vertical at 3.30%; digital media 2.55% voluntary plus 1.59% involuntary. Recurly's pages are inconsistent on period and on monthly versus annual basis. [M, period unclear] — [Recurly](https://www.recurly.com/research/churn-rate-benchmarks)
- Paid newsletters: monthly churn from 5.06% (food and drink) to 16.67% (money); investing 11.72%, sports 7.76%. [M via S, 2026] — [Press Gazette](https://pressgazette.co.uk/newsletters/newsletters-2026-prices-retention-churn/); [Voxbooster](https://voxbooster.com/blog/newsletter-paid-subscriber-conversion-statistics-2026)
- Churn rises as price falls: under $10 average revenue per account 6-7% monthly churn, $500+ 1-2%; a December 2025 analysis of 3,500 software companies found products under $50 a month retain noticeably worse. [M, 2025] — [ChartMogul help](https://help.chartmogul.com/hc/en-us/articles/203359321); [ChartMogul](https://chartmogul.com/saas-metrics/customer-churn/)
- Memberful reports average annual churn of 9.8% in Q3 2025, up from 8.4% a year earlier. The definition differs from monthly churn. [M, 2025] — [Memberful](https://memberful.com/operator/the-state-of-membership-q3-2025)
- Creator memberships 5-9% monthly churn, from a vendor selling a cancellation tool. [V] — [ChurnRecovery](https://churnrecovery.pages.dev/posts/membership-site-churn-rate)
- Premium video streaming weighted average monthly churn 4.6% (Antenna 2025). [M via S] — [Uscreen](https://www.uscreen.tv/blog/ott-subscriber-retention-strategies/)
- Health-club members on a flat fee above $70 attended 4.3 times a month and paid over $17 per visit (7,752 members, three years). [P, observational, 2006] — [DellaVigna & Malmendier](https://openalex.org/W2026559010)
- Many users prefer a flat rate even when pay-per-use would cost them less. [P, observational, 2006] — [Lambrecht & Skiera](https://openalex.org/W2111073395)
- Targeting retention offers at the highest-risk customers is not necessarily optimal. [P, field experiments, 2018] — [Ascarza](https://openalex.org/W3122149192)

**Lifetime deals**
- $110,000 gross on AppSumo became $45,000 net after the platform's share and refunds. [A] — [Indie Hackers](https://www.indiehackers.com/post/the-45k-sugar-rush-what-110k-in-appsumo-gross-revenue-taught-us-0383952b35)
- "$100k revenue on $200k sales" in another campaign. [A] — [Indie Hackers](https://www.indiehackers.com/post/we-made-100k-revenue-on-200k-sales-via-appsumo-our-learnings-from-the-campaign-fe38e95fb0)
- AppSumo pays out 60 days after month end, and sellers remove refunded users by hand from a CSV. From the same search extract; exact post unconfirmed. [A] — candidate source: [Indie Hackers](https://www.indiehackers.com/post/what-it-s-like-to-run-a-campaign-on-appsumo-viewst-1st-month-on-air-66acb9b493)
- Founders warn that lifetime customers' support and running costs continue after the deal closes; a post titled "4 years into an AppSumo lifetime deal: the unvarnished math" exists but its content was not read. [A] — [Indie Hackers](https://www.indiehackers.com/post/appsumo-pros-and-cons-after-over-200-000-in-sales-9cceeb46a9); [Indie Hackers](https://www.indiehackers.com/post/4-years-into-an-appsumo-lifetime-deal-the-unvarnished-math-and-a-question-i-m-stuck-on-4dd2b262ac)

### Inferences
- The evidence favours a two- or three-tier offer (base, base plus bonuses, premium) over a long ascension ladder: the tier result is a field experiment, while the "small yes leads to big yes" mechanism has small effects and comes from non-commercial settings.
- At a 7-9% monthly churn a member stays about 11-14 months on average, so a 30-50 PLN membership yields roughly 350-700 PLN lifetime revenue before fees. A membership makes sense only if new content cost per month is well below that.
- Instalments are the best-evidenced conversion lever for mid-priced products, with a known cost: the buyers they add are more budget-constrained, which is consistent with the reported high share of unfinished payment plans.
- Deadlines should be real and tied to something that actually ends (a cohort start, a bonus that is withdrawn). Fake timers have documented legal and trust costs and no measured sales advantage in the sources found.

### Gaps
- Measured effect of guarantees and of guarantee length on digital-product conversion and refunds.
- Payment-plan uptake and default rates from platform data.
- Any measured "ascension rate" from low-ticket buyers to high-ticket offers.
- Churn for paid communities on Skool and Circle from the platforms themselves.

---

## 4. Product format effects: self-paced, cohort, community, certificates; completion and its consequences

### Takeaway
Free self-paced courses are completed by a few percent of registrants, and scalable nudges do not change that. Payment, certificates and hard commitment devices do raise engagement, and cohort formats show higher completion in platform data, though that comparison is observational. No source measured the link from completion to refunds, reviews or repeat purchase.

### Cited Findings

**Baseline completion**
- On edX courses from MIT and Harvard, 52% of registrants never enter the courseware, and low completion had not improved in six years. [P, observational, 2019] — [Reich & Ruipérez-Valiente](https://openalex.org/W2910811057); [postprint](https://webs.um.es/jruiperez/papers/journals/2019_Science_MOOCPivot_postprint.pdf)
- Traditional completion-based success rates of 6.5% and 5.6% in two MOOCs. [P, observational, 2017] — [Henderikx, Kreijns, Kalz](https://openalex.org/W2754780169)
- Reported MOOC completion below 5% in the sources cited by a 2019 AAAI paper. [P, 2019] — [Feng, Tang, Liu](https://openalex.org/W2905464284)
- Public enrolment and completion data for early MOOCs were compiled in 2014; a secondary source summarises this as a median 6.5% completion across 39 MOOCs. [P, observational, 2014; median via S] — [Jordan](https://openalex.org/W1511434862); [Rework summary](https://resources.rework.com/libraries/edtech-growth/course-completion-rates)
- Students who enrol one day late are 17 percentage points less likely to earn a certificate. [P, observational, 2014] — [Banerjee & Duflo](https://openalex.org/W2139993466)

**Payment and certificates**
- Across 70+ Coursera courses, the certificate effect raises engagement by about 8-9% and the sunk-cost effect by about 17-20%; the sunk-cost effect lasts only a few weeks after payment, while the certificate effect persists until the passing grade. [P, observational, 2021] — [Goli, Chintagunta, Sriram](https://openalex.org/W3157101706); [University of Michigan summary](https://record.umich.edu/articles/research-shows-certificates-boost-mooc-completion-rates)
- The pull of a sunk cost fades as time passes since payment. [P, lab experiments, 1998] — [Gourville & Soman](https://openalex.org/W2031538264)
- Free-certificate coupons change participation and certification patterns (two case studies). [P, observational, 2020] — [Littenberg-Tobias, Ruipérez-Valiente, Reich](https://openalex.org/W2999412724)

**Nudges, commitment devices, deadlines**
- Interventions tested over 2.5 years on about 250,000 students in 250 courses had effects an order of magnitude smaller than in the original studies; self-regulation interventions raised early engagement but not completion. [P, field experiment, 2020] — [Kizilcec et al.](https://openalex.org/W3034223452); [Cornell summary](https://news.cornell.edu/node/319503)
- The earlier small study had found planning prompts raising completion from 14% to 18% among committed English-fluent students (n = 2,053). [P, field experiment, 2017] — [Yeomans & Reich](https://openalex.org/W2592491576); [PMC full text of the 2020 paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7334459)
- Four large trials found an overall null effect of planning prompts, ruling out effects beyond [-7%, 3%]. [P, preprint, 2018] — [Andor et al.](https://openalex.org/W2922889227)
- A commitment device limiting distracting internet time raised completion by 40% (11 percentage points), time on course by 24% and performance by 0.29 standard deviations; reminders had no measurable effect (n = 657). [P, field experiment, 2018] — [Patterson](https://openalex.org/W2886688093); [EconPapers record](https://econpapers.repec.org/RePEc:eee:jeborg:v:153:y:2018:i:c:p:293-321)
- Review of hard versus soft commitment devices and the limited demand for hard ones. [P, review, 2010] — [Bryan, Karlan, Nelson](https://openalex.org/W4239240859)
- Deadlines: see the retraction and failed replication in section 3. [P, 2026] — [Hyndman & Bisin](https://openalex.org/W4399154521)

**Cohort versus self-paced**
- Ruzuku platform data: scheduled cohort courses average 53.4% completion against 41.9% for open-access self-paced courses; cohorts of 11-25 students peak at 65.2%. The author states these are observational differences, not proof that deadlines or live sessions cause completion. Paid courses on a small platform. [M, 2026] — [Ruzuku study](https://www.ruzuku.com/learn/articles/cohort-vs-self-paced-completion-study)
- Maven's own listing claims 75-90% completion; a blog estimate says about 96%; the widely repeated 96% for altMBA has no primary source in the results. [V/S] — [Maven on Product Hunt](https://www.producthunt.com/posts/maven-eca0ac99-b076-4f60-8cb7-4d204fe8ff7f); [Philippa Hardman](https://drphilippahardman.substack.com/p/maven-a-masterclass-in-great-online)
- Average course price on Maven is about $500 according to Maven's help centre; another site says $2,500. [V; conflict] — [Maven help](https://help.maven.com/en/articles/6732396-pricing-your-course); [Skillademia](https://www.skillademia.com/?p=38908)
- Circle's blog claims 90% completion for cohort courses, and Teachable quotes 85% for a Harvard Business School cohort course, neither with a primary source. [V] — [Circle](https://circle.so/br/blog/cohort-based-courses); [Teachable](https://teachable.com/blog/improve-student-success)
- A survey quoted in a roundup says 85.8% of creators charge under $100 for their main course; source and sample unidentified. [S, low confidence] — [Ruzuku statistics page](https://www.ruzuku.com/learn/articles/online-course-statistics)

**Free content: cannibalisation versus promotion**
- Free samples have three separable effects: acceleration, cannibalisation of paid trial purchases, and expansion to new buyers (two field experiments). [P, field experiments, 2004] — [Bawa & Shoemaker](https://openalex.org/W1969045005)
- Free samples of digital content should be designed (size and content) to maximise revenue. [P, 2019] — [Li, Jain, Kannan](https://openalex.org/W2940771723)
- Firms with both free and paid content should offer more free content in periods of high demand. [P, observational, 2017] — [Lambrecht & Misra](https://openalex.org/W3122597397)
- People perceive the benefits of zero-price options as higher than cost-benefit arithmetic implies. Dan Ariely is a co-author; the paper is not retracted. [P, experiments, 2007] — [Shampanier, Mazar, Ariely](https://openalex.org/W2147664728)
- Conversion to premium is low in freemium because the free option delivers disproportionately high perceived value. [P, experiment, 2019] — [Niemand, Mai, Kraus](https://openalex.org/W2938736700)
- Most readers planned not to pay when the New York Times put previously free content behind a metered paywall. [P, survey, 2012] — [Cook & Attari](https://openalex.org/W2065597208)

### Inferences
- The durable part of the payment effect is the certificate (a goal with a finish line), not the money paid. A product with a defined deliverable at the end (a filled-in template, a reviewed project, a certificate) should hold engagement longer than access alone.
- Because the sunk-cost pull lasts a few weeks, a first paid product should deliver its main result within two to four weeks of purchase.
- Bundles and "lifetime library" offers sell access but lower consumption per item, which makes them a poor fit when the goal of the test is testimonials and repeat purchase.
- Templates and tools sidestep the completion problem because value arrives on first use, whereas a course's value depends on finishing it. This is an inference; no source compared templates with teaching directly.

### Gaps
- No data linking completion to refund rate, review rate or repeat purchase.
- No controlled comparison of cohort and self-paced versions of the same course.
- No evidence on community add-ons or done-with-you tiers beyond the Kajabi self-report.
- No comparison of templates against teaching formats.

---

## 5. Documented case studies, failures and median outcomes

### Takeaway
Wherever a distribution is published, the median outcome is tiny and the top 1% takes most of the revenue: about $70 a year for the median Gumroad creator in 2020, about half of Stripe-verified Indie Hackers products at $0, and a 0.62% median paid conversion for newsletters. Published success cases are the tail of these distributions.

### Cited Findings

**Distributions**
- Gumroad's own 2020 figures as reported in 2021: the median creator made about $70 in 2020, and the top 1% earned about 60% of the money. [M via S, 2020] — [Silicon Florist](https://siliconflorist.com/2021/01/12/what-happened-in-the-gumroad-creator-community-in-2020/)
- A 2026 third-party model of 146,000 Gumroad products gives a $72 monthly median and a top-1% revenue share of 77.3% on one page and 99.5% on another. Revenue is modelled from ratings counts, and the pages contradict each other. [S, modelled, low confidence] — [InsightRaider](https://insightraider.com/en/state-of-gumroad-2026); [InsightRaider data](https://insightraider.com/en/data/gumroad-statistics-2026)
- Indie Hackers Stripe-verified products: more than 54% made no revenue in a scrape of 937 products; 48.7% made $0 in a later sample of 998. [M, community scrapes] — [Indie Hackers](https://www.indiehackers.com/post/how-much-money-do-indie-hackers-products-make-74db9631f0); [Indie Hackers](https://www.indiehackers.com/post/indie-hackers-are-making-60-million-in-stripe-verified-arr-bac07f782d)
- September 2026 analysis: among 4,987 products with revenue in a 30-day window, the median was $169, and the top 1% took 76.1% of all revenue. [M, scrape, 2026] — [TechStartups](https://techstartups.com/2026/09/28/what-percentage-of-indie-hacker-products-make-100k-in-arr/)
- 5,079 Stripe-verified projects on another directory: median $148 a month in year 0, rising to about $2,500 by year 5 among survivors. [M, scrape, March 2026] — [Indie Hackers](https://www.indiehackers.com/post/i-analyzed-5-079-stripe-verified-startups-f0f6bd053f)
- Kit/ConvertKit creator survey figures relayed by a third party: 46.7% of creators work full-time on content, 18% earn over $100,000 a year, and 57% of full-time creators earn below the US living wage. Original report not retrieved. [S] — [Spiralytics](https://spiralytics.com/blog/content-creator-statistics-2025)
- Kajabi's 2025 report is quoted for an average creator income of about $37,000 a year. An average on a premium platform, not a median. [S] — [Kajabi blog](https://kajabi.com/blog/is-selling-online-courses-profitable)
- In 48,500 crowdfunding projects, success is associated with personal networks and project quality. [P, observational, 2014] — [Mollick](https://openalex.org/W3121716941)

**Winners (tail cases)**
- Thomas Frank reported about $1,000,508 in Notion template sales for 2022: Ultimate Brain $760,000, bundle $298,000, Ultimate Tasks $86,000. He had a large existing YouTube audience. [A, self-reported] — [Thomas Frank thread](https://typefully.com/TomFrankly/dollar1-million-in-notion-template-sales-kuFT0iD)
- Easlo: $239,000 from templates in 2022 in one source, "over $500,000" in another; figures conflict. [A/S] — [Kajabi blog](https://kajabi.com/blog/can-you-make-money-selling-notion-templates)
- At the other end, one seller documented $250 in total template sales. [A] — [The Mindful Planner](https://themindfulplanner.substack.com/p/how-i-made-250-selling-notion-templates)

**Launch platforms**
- Product Hunt #1 Product of the Day with 1,110 upvotes produced two paid customers for one maker (Mixily), who blamed a generous free tier. From a search extract over several post-mortems; exact page unconfirmed. [A] — candidate sources: [Product Hunt discussion](https://www.producthunt.com/discussions/what-were-your-launch-day-metrics-from-a-successful-product-hunt-launch); [Indie Hackers](https://www.indiehackers.com/post/postmortem-of-our-product-hunt-launch-5f2d4a86e5)
- Another #1 launch (You Need A Wiki): 969 signups, all in trial, paid conversion not reported. Exact page unconfirmed. [A] — candidate source: [Indie Hackers](https://www.indiehackers.com/post/first-product-hunt-launch-1-product-of-the-day-6e5c09946c)
- Curated Letters: signups went 28, 682, 53 across the months before, during and after launch. [A] — [Indie Hackers](https://www.indiehackers.com/product/curatedletters/how-we-topped-product-hunt-and-gained-hundreds-of-users--O6WJEnQ8qsno-dWOtYf)
- A launch with three upvotes after four weeks of work. [A] — [dev.to post-mortem](https://dev.to/ykiki/4-weeks-1-saas-3-upvotes-an-honest-product-hunt-postmortem-53h6)
- AppSumo: $110,000 gross to $45,000 net; refund shares of 22% and about 40% in two other campaigns (section 2 and 3). [A] — [Indie Hackers](https://www.indiehackers.com/post/the-45k-sugar-rush-what-110k-in-appsumo-gross-revenue-taught-us-0383952b35)

**Newsletters**
- Median free-to-paid conversion 0.62% on beehiiv against the 5-10% often quoted. [M via S, 2026] — [Voxbooster](https://voxbooster.com/blog/newsletter-paid-subscriber-conversion-statistics-2026)

### Inferences
- Selection runs in one direction at every step: only some makers list products, only some verify revenue, and only winners write case studies. Published medians are therefore already above the true median.
- The winners share one visible trait, a pre-existing audience (YouTube, newsletter, community). Mollick's crowdfunding result and the Product Hunt post-mortems point the same way.
- For a first test, the realistic success criterion is "a few strangers paid", not a revenue target taken from case studies.

### Gaps
- No Podia, Teachable or Lemon Squeezy earnings distributions.
- No verified low-ticket ad-funnel case with complete account data.
- No current first-party Gumroad distribution after 2020.

---

## 6. Retention and repeat purchase

### Takeaway
The only creator-specific figure found is SamCart's: about 12% of purchases come from returning buyers, and they account for 44% of revenue. It is a vendor number, but it matches the general pattern that a small repeat group carries a large revenue share.

### Cited Findings
- About 12% of purchases on SamCart are by returning purchasers, and 44% of total revenue comes from the 11.81% of customers who are repeat buyers. From SamCart's 2023 Creator Profits Report covering 17,507 creators and $3.5 billion in sales. [M/V, 2023] — [SamCart](https://www.samcart.com/blog/5-illuminating-data-points-uncovered-from-samcarts-2023-creator-profits-report)
- Shopify says repeat customers often make up almost half of a store's sales. Physical ecommerce, no method. [V] — [Shopify](https://www.shopify.com/blog/repeat-purchases-increase)
- "70% of creator product buyers never come back" appears without a source. [S, low confidence] — [Built by Foundry](https://www.builtbyfoundry.io/blog/why-creator-product-buyers-never-come-back)
- "65% of revenue from existing customers" is a generic ecommerce figure with weak sourcing. [S, low confidence] — [Sender](https://www.sender.net/marketing-glossary/repeat-purchase-rate/statistics/)
- Cross-buying is unprofitable for an identifiable segment of customers. [P, observational, 2012] — [Shah et al.](https://openalex.org/W2064861448)
- Kit says creators earn on average 3.5 times what they spend on the platform from products sold through it. [V] — [Kit](https://kit.com/resources/blog/trends-in-creator-economy)

### Inferences
- If roughly one buyer in eight returns and those buyers produce close to half of revenue, a second product for existing buyers is worth more per unit of effort than a second acquisition channel. This rests on one vendor dataset.
- The backend offer should be planned before the first sale, since the buyer list is the main asset a low-margin front-end product creates.

### Gaps
- Repeat-purchase rates on Gumroad, Podia, Kajabi or Lemon Squeezy.
- Time between first and second purchase for digital products.
- Which backend formats (membership, higher tier, service) buyers of low-ticket products actually take.

---

## 7. Checkout tooling data

### Takeaway
Published checkout data comes almost entirely from SamCart, with one rigorous test from Stripe on BNPL. ThriveCart, Gumroad and Lemon Squeezy publish feature descriptions rather than performance data.

### Cited Findings
- SamCart: bumps 35-40% take rate, one bump adds about 31% to average customer value. [V] — [SamCart](https://www.samcart.com/blog/the-complete-guide-to-order-bumps)
- SamCart: using upsell features "more than doubles" creator revenue. [V] — [SamCart](https://www.samcart.com/blog/how-do-million-dollar-brands-make-2x-more-from-each-customer)
- Stripe: A/B tests on 150,000+ sessions; BNPL display linked to up to 14% more revenue and 66% net-new BNPL volume. [M/V] — [Stripe](https://stripe.com/en-hk/blog/testing-the-impact-of-buy-now-pay-later)
- Stripe documents how to A/B test a payment method in its own checkout. [V, documentation] — [Stripe docs](https://docs.stripe.com/payments/a-b-testing)
- ThriveCart limits multiple bumps to digital products, up to six on its Pro+ licence according to SamCart's comparison page. [V] — [ThriveCart](https://thrivecart.com/?p=34147); [SamCart comparison](https://www.samcart.com/compare/samcart-vs-thrivecart)
- Gumroad's effective fee falls from about 20.9% on a $10 product to 13.1% on a $500 product. [S, 2026] — [Checkout Page](https://checkoutpage.com/blog/gumroad-fees)
- Baymard's 70.22% abandonment average is the reference point for checkout friction. [M, 2025] — [Baymard](https://baymard.com/lists/cart-abandonment-rate)
- Partitioned pricing has contradictory effects that depend on presentation, such as whether the total is shown. [P, meta-analysis, 2018] — [Abraham & Hamilton](https://openalex.org/W4255489062)

### Inferences
- On a $10-$20 product, marketplace fees of about 20% plus payment costs take a fifth of revenue, so very low prices need high volume or a bump to cover even small ad spend.
- A checkout that supports one bump, one post-purchase offer and instalments covers every lever that has any evidence behind it.

### Gaps
- First-party performance data from ThriveCart, Gumroad, Lemon Squeezy, Podia and Whop.
- Incrementality of bumps and upsells in any tool.

---

## 8. Academic evidence: summary of what holds and what does not

### Takeaway
Marketing folklore is weakest exactly where gurus lean on it most: sequential-commitment effects are small, the deadline classic is retracted, and nudges for completion fail at scale. The better-supported findings concern instalments, free-option framing, tiered product lines, free-sample design, shorter trials and hard commitment devices.

### Cited Findings

| Claim in practitioner material | What the evidence says | Source |
|---|---|---|
| A small purchase makes a large one likely | Small effects (r = .17), prosocial requests only, nearly half of studies null | [Beaman 1983](https://openalex.org/W1973945715); [Dillard 1984](https://openalex.org/W1539499155) |
| Downsell after refusal works better or worse than upsell | No significant difference between the two sequences in direct comparisons | [Pascual & Guéguen 2005](https://openalex.org/W2148636014) |
| Deadlines improve follow-through | Key study retracted in 2026; replication null; deadlines did not raise completion in a field experiment | [Hyndman & Bisin 2026](https://openalex.org/W4399154521); [Bisin & Hyndman 2020](https://openalex.org/W1594026760) |
| Scarcity sells | Raises purchase intentions on average; type must match product; sales effect not measured | [Barton 2022](https://openalex.org/W4284967436) |
| Bonuses beat discounts | Supported for evaluations and intentions at equal value | [Munger & Grewal 2001](https://openalex.org/W2002121006) |
| Bigger bundles are better | Profitable for near-zero-cost goods, but consumption per item falls | [Bakos & Brynjolfsson 1999](https://openalex.org/W3122946301); [Soman & Gourville 2001](https://openalex.org/W2003217648) |
| Payment plans lift sales | Supported: higher purchase incidence and basket size | [Maesen & Ang 2024](https://openalex.org/W4402116954) |
| Free content cannibalises sales | Depends on sample design; more free content can pay when demand is high | [Li, Jain, Kannan 2019](https://openalex.org/W2940771723); [Lambrecht & Misra 2017](https://openalex.org/W3122597397) |
| Longer free trials convert better | Opposite on average in a large field experiment | [Yoganarasimhan 2022](https://openalex.org/W4297830788) |
| A premium tier cannibalises the base product | Adding premium versions raised demand for the existing premium version | [Gu, Kannan, Ma 2018](https://openalex.org/W2897722974) |
| Paying makes people finish | Engagement up 17-20% from sunk cost for a few weeks, 8-9% from the certificate for longer | [Goli et al. 2021](https://openalex.org/W3157101706) |
| Reminders and planning prompts fix completion | Null at scale; a hard commitment device did work in one trial | [Kizilcec 2020](https://openalex.org/W3034223452); [Patterson 2018](https://openalex.org/W2886688093) |
| Every buyer should be cross-sold | A segment becomes more unprofitable the more it buys | [Shah et al. 2012](https://openalex.org/W2064861448) |
| Ad platform ROAS shows what ads earn | Experimental returns are a fraction of reported ones | [Blake, Nosko, Tadelis 2015](https://openalex.org/W2922202912) |
| Gated content generates better leads | No scholarly study found on OpenAlex | — |

- A multiple-process review shows the foot-in-the-door procedure also triggers reactance, which lowers compliance. [P, review, 1999] — [Burger](https://openalex.org/W1992451914)

### Inferences
- Most of the supporting studies measure intentions or come from retail, hospitality or MOOCs. Transfer to a small seller of digital products is plausible but untested, so each lever should enter the first funnel as a hypothesis with a planned measurement.
- Three levers have field-experimental or quasi-experimental support with real purchases and are cheap to add: instalments, a second premium tier, and a recipient's first name in emails.

### Gaps
- No scholarly work was found on order bumps or one-click post-purchase offers as such; the nearest evidence is option framing and hotel or airline upselling.
- No scholarly work was found on gated content and lead quality (two OpenAlex queries returned nothing relevant).
- No peer-reviewed study of webinar, challenge or launch funnels was found.
- OpenAlex abstracts were truncated for several works, so some registry findings are stated qualitatively without the authors' numbers.
