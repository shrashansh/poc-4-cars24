# POC-4: Challan Settlement Audit (Cars24)

Shrashansh Dixit, October 2026. Built from public information only, with no Cars24 data or system access.

## The problem

Cars24 lets people pay traffic challans on cars24.com, CarInfo and VehicleInfo. The user pays the fine plus a fee, and Cars24 or a partner then pays the government on their behalf. In the words of the cars24.com challan page: "Pay the due amount online, and Cars24 will settle the challan" (S1).

When this goes wrong, the user has paid but the challan is still open. Their Google Play reviews tell the same story again and again: money taken, the challan still pending on Parivahan weeks later, a refund that never arrives. Some say the app showed "Settled" while the government site still showed the challan as unpaid.

This matters more in 2026 than before. On 28 September 2026 the Supreme Court directed states to blacklist vehicles with unpaid e-challans and block their ownership transfer (S6), and under amended Rule 167 such vehicles are marked "Not to be Transacted" on Vahan (S9, applied by the Orissa High Court in February 2026). For Cars24 that is no longer only an app-store problem. It touches every car it buys and sells.

## The numbers

These come straight from the data in this repository. `python3 build.py` regenerates the table, and a test fails if it ever drifts from the data. They count public complaints, so the number of people affected is higher: most people never write a review. Cars24 does not publish how many challans it settles, so no failure rate is given.

<!-- METRICS:START -->
| What | Number | Source |
|---|---|---|
| 1-2 star Play reviews read (2025-01-01 to 2026-10-22) | 11,540 (CarInfo 2,702, Cars24 5,232, VehicleInfo 3,606) | `metrics.low_star_total` |
| Of those, about challans | 1,167 (CarInfo 470, Cars24 79, VehicleInfo 618) | `metrics.challan_reviews` |
| Of those, written after Cars24 owned the app | 753 (CarInfo 307, Cars24 79, VehicleInfo 367; CarInfo from 2026-01-05, VehicleInfo from 2026-03-11) | `metrics.since_acquisition` |
| Challan-failure reviews as a share of all 1-2 star reviews, 2026 Q2 to Q3 | 7% to 8% (keyword rules flag 88 then 212; all 1-2 star reviews also rose, 1,330 to 2,701) | `metrics.q3_vs_q2` |
| Failures within Cars24's and its payment partner's control, based on how users describe them | 74% (95% CI 65% to 81%) of 116 failure reviews in the labelled sample | `metrics.sample_estimates.control.in_control` |
| Failures about wrong, missing or stale challan data | 25% (95% CI 18% to 34%) | `metrics.sample_estimates.control.partial` |
| Failures described as a physical-court case | 1% (95% CI 0% to 5%) | `metrics.sample_estimates.control.structural` |
| App showed "Settled" or "Paid" while the government still showed it pending | about 78 reviews (95% CI 43 to 138); 10 of 150 in the labelled sample; keyword rules flag 18 | `metrics.sample_estimates.types.FALSE_SETTLED` |
| Paid, still pending on Parivahan or in court | about 513 reviews (95% CI 424 to 607); 66 of 150 in the labelled sample; keyword rules flag 358 | `metrics.sample_estimates.types.PAID_PENDING` |
| Refund not received | about 140 reviews (95% CI 90 to 212); 18 of 150 in the labelled sample; keyword rules flag 136 | `metrics.sample_estimates.types.REFUND_STUCK` |
| Charged far above the fine, or fee not shown upfront | about 187 reviews (95% CI 128 to 265); 24 of 150 in the labelled sample; keyword rules flag 83 | `metrics.sample_estimates.types.OVERCHARGE` |
| Challan shown that does not exist, or missing or stale | about 241 reviews (95% CI 175 to 325); 31 of 150 in the labelled sample; keyword rules flag 141 | `metrics.sample_estimates.types.WRONG_DATA` |
| Developer replied | 78% of challan reviews, median 20 hours | `metrics.replies` |
| Replies that point to an email address or a form | 83% | `metrics.replies.redirect_share` |
| Replies that give any timeline | 3% (most common: "5–7 working days") | `metrics.replies.timelines_quoted` |
| Settlement or refund timeline in the published terms | none (cars24.com challan page, CarInfo terms, CarInfo refund policy) | `sources:S1`, `sources:S2`, `sources:S3` |
| Keyword rules on 100 held-out labelled reviews | precision 0.87, recall 0.57 | `metrics.validation.test` |
<!-- METRICS:END -->

"About N reviews" is estimated from a labelled random sample of 150 challan reviews, scaled to all of them, with a 95% confidence interval. "Keyword rules flag" is what the automatic rules find across every review. The rules miss some reviews and occasionally flag the wrong one, so that figure is a cross-check, not a bound.

## The gap

Four things stand out.

1. The status a user sees is not tied to the government record. "Settled" can appear before Parivahan confirms anything, so the user finds out only when a challan resurfaces, sometimes after it has moved to court.
2. No timeline is promised anywhere a user can hold Cars24 to. Support replies quote "5–7 working days" for online challans and "up to 90 days" for court challans, but the published pages commit to nothing. CarInfo's terms call challan payment a third-party service used at the user's own risk (S2), and its refund policy says challan payments are "strictly non-refundable" once processed (S3).
3. Most complaints describe steps Cars24 and its payment partner run themselves: taking the payment, submitting it, showing the status, refunding, charging the fee. Very few describe a challan that genuinely had to go through a physical court. For challans sent to the Virtual Court, the government site itself says the challan "can be paid here" online (S5, checked live on 22 October 2026).
4. Nobody in the market guarantees settlement either. Spinny's challan provider says outright that it "does not guarantee … that the challans shall be settled" (S7). A settlement that users can trust would set Cars24 apart.

## The solution

A settlement engine built on one rule: never show "Settled" until the government confirms it.

`engine/settlement.py` tracks every challan payment as a state machine. Compared with what users describe today:

| | Today, as users describe it | With the truth rule |
|---|---|---|
| When "Settled" is shown | when the partner says it is paid | only after a government receipt or a status read from the government portal |
| Deadline | none published | online and Virtual Court: 7 working days; court: 90 days; refund: 7 working days (each taken from Cars24's own replies) |
| Missed deadline | the user chases support | overdue and owned by the partner, then escalated to ops two working days later, with a refund offered |
| Rejected payment | "non-refundable" | refund due by a date, owned by finance |
| Fee | sometimes seen only after paying | flagged unless shown before payment (in line with RBI's payment aggregator directions, S8) |

The app's Engine tab replays 1,000 simulated payments through both versions. The mix of failures comes from the labelled reviews. The overall failure rate (10%), the split of challan types, the amounts and the timings are assumptions, and they are labelled as such. The demo shows what the rule changes for a user; it is not a measurement of Cars24.

The same engine fits the moment Cars24 buys a car. At inspection it could pay the car's open challans directly, hold back money only for challans that are actually open, and release that holdback when the government confirms payment. That idea is described in the app's At inspection tab but not built here.

## How the numbers were made

1. **Reviews.** 1-2 star Google Play reviews of Cars24 (`com.cars24.seller`), CarInfo (`com.cuvora.carinfo`) and VehicleInfo (`com.vehicle.rto.vahan.status.information.register`), dated 1 January 2025 to 22 October 2026, collected on 22 October 2026 with `google-play-scraper`. The collection used several passes (newest first, and filtered by star rating) to reach back to January 2025. `audit/pull.py` is a simpler re-pull script; the store changes daily, so a re-pull will not match byte for byte. The SHA-256 of each file actually used is recorded in `data/metrics.json`.
2. **Privacy.** Only eight fields per review are kept. Names in reply greetings, phone numbers, emails, registration numbers, challan numbers, bank and UPI references are masked before anything is saved (`audit/mask.py`). Tests fail the build if any of these appear in a shipped file.
3. **Classification.** Fixed keyword rules in English, Hinglish and Devanagari (`audit/classify.py`) tag six kinds of failure: paid but pending, false "Settled", wrong data, refund stuck, overcharge, and court involvement. There is no model in the loop, so every build gives the same answer.
4. **Labelled sample.** A stratified random sample of 150 challan reviews (seed 24) was read one by one and labelled against those six definitions (`data/validation.csv`). The first reader was an AI model (Claude) reading the review text only, without the rules' output; `python3 -m audit.label_check` gives the author a blind page to re-label 50 of them, and the build then reports agreement. The rules were tuned on the first 50 only. The other 100 were held back and scored once, and the build fails if precision on them drops below 0.80. The labels and the rules come from the same analysis, so the held-out score is probably a little optimistic.
5. **Estimates.** Headline shares use the labelled sample with 95% Wilson intervals, because the keyword rules miss some reviews.

## What this does not show

- Reviews are written by people with a problem. These numbers describe complaints, not how often settlement fails.
- The engine runs on simulated payments. Wiring it to real data needs Cars24's payment records and a status feed from Parivahan.
- Whether a stuck challan is Cars24's fault or its partner's is inferred from how the user describes it, not from internal records.

## Run it

```bash
python3 build.py                               # metrics, the table above, dist/
python3 -m unittest discover -s tests -v       # all tests
python3 -m http.server -d dist 8000            # then open http://localhost:8000
```

Python 3.10 or later, no other dependencies. `python3 prepare.py` rebuilds `data/` from the raw review files, which stay on the author's machine because they contain reviewer names. Vercel runs `python3 build.py` and serves `dist/`.

| Path | What it does |
|---|---|
| `audit/` | collection, masking, classification, sampling, validation, metrics |
| `engine/` | the settlement state machine and the simulation |
| `data/` | masked challan reviews, quarterly counts, labelled sample, sources, metrics |
| `web/index.html` | the app: Audit, Evidence, Engine, At inspection, Method |
| `tests/` | masking, classifier, validation floor, metrics, engine rules, README sync, privacy |

## Sources

| | Claim | Link |
|---|---|---|
| S1 | cars24.com: "Pay the due amount online, and Cars24 will settle the challan." The page gives no fee, timeline or refund terms | https://www.cars24.com/traffic-challan/ |
| S2 | CarInfo lists challan payment among services "provided by its third-party affiliates", used at "Your own risk" | https://www.carinfo.app/terms-and-conditions |
| S3 | CarInfo: challan payments are "strictly non-refundable and non-cancellable once processed" | https://www.carinfo.app/refund-policy |
| S4 | VehicleInfo pays challans "via secure, authorized partners" (developer reply on Google Play, 24 April 2026) | Google Play listing |
| S5 | e-Challan: a challan forwarded to the Virtual Court "can be paid here" (checked live, 22 October 2026) | https://echallan.parivahan.gov.in/index/accused-challan |
| S6 | Supreme Court, S. Rajaseekaran v. Union of India, 28 Sep 2026: block ownership transfer for unpaid e-challans (LiveLaw report) | https://www.livelaw.in/top-stories/impound-vehicles-with-unpaid-e-challans-freeze-online-services-supreme-court-orders-notes-over-23000-crore-traffic-fines-pending-552686 |
| S7 | Spinny's provider Pureride "does not guarantee … that the challans shall be settled" | https://www.spinny.com/e-challan/terms-and-conditions/ |
| S8 | RBI payment aggregator directions: other charges must be "distinctly displayed to the payer prior to the transaction" | https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12896 |
| S9 | Amended Rule 167: "Not to be Transacted" for unpaid challans, applied by the Orissa High Court, 10 Feb 2026 (StudyCafe report; gazette not read) | https://studycafe.in/hc-rules-fuel-cannot-be-denied-for-pending-challans-upholds-puc-refusal-under-amended-rule-167-411163.html |
| S10 | Cars24 acquires CarInfo, 5 Jan 2026 (MediaNama) | https://www.medianama.com/2026/01/223-cars24-acquires-carinfo-rs-118-crore-ahead-ipo/ |
| S11 | Cars24 acquires Vehicle Info, reported 11 Mar 2026 (Entrepreneur India) | https://india.entrepreneur.com/news-and-trends/cars24-acquires-automotive-utility-app-vehicle-info/503346 |
