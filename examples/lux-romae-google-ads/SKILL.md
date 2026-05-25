---
name: lux-romae-google-ads
description: "Knowledge base from \"Google Ads Strategy for Lux Romae Apartment\". Use when planning or running Google Ads for a single short-term rental in Rome, designing campaign architecture (Search, PMax, remarketing, travel inventory), setting up GA4/Tag Manager/consent mode v2 for hotels, choosing keywords and bidding strategies, or auditing measurement and offline conversion imports."
allowed-tools:
  - Read
  - Grep
argument-hint: [topic, framework name, or chapter number]
---

# Google Ads Strategy for Lux Romae Apartment
**Subject**: Single-property short-term rental, Rome (Ostiense/Piramide) | **Chapters**: 8 | **Generated**: 2026-05-25

## How to Use This Skill

- **Without arguments** — load the core campaign architecture and decision rules
- **With a topic** — ask about `keywords`, `bidding`, `measurement`, `consent`, `landing pages`, `attribution`, `PMax`, `vacation rentals`, etc.
- **With chapter** — ask for `ch04` to dive into a specific chapter
- **Browse** — ask "what chapters do you have?" for the full index

When you ask about a topic not covered below, I read the relevant chapter file before answering.

---

## Core Frameworks & Decision Rules

### The 4-Priority Architecture (the core thesis)
For a one-property budget, do these four things and nothing else at launch:

1. **Brand defence Search** — stop OTAs (Airbnb, Vrbo, Booking) from intercepting "lux romae"-type queries. Cheapest, most protective spend.
2. **High-intent non-brand Search** — exact + phrase match on location/product/policy long-tail (e.g. `apartment piramide rome`, `2 bedroom apartment rome family`).
3. **Remarketing** (Search + Display) — re-close visitors who checked dates or started checkout.
4. **Google Vacation Rentals / Hotel Center** — if the booking engine or a connectivity partner supports it. Direct suppliers can earn the "official site" badge OTAs cannot.

Performance Max is a **later expansion layer**, not a starting point. Google says PMax needs ≥6 weeks and minimal early changes to learn; with thin booking data that becomes expensive ambiguity.

### Search-vs-PMax Coexistence Rule
When a user's query is **identical** to an eligible Search keyword in the account, Google prioritises the Search campaign over Performance Max. Use this: pin every high-value exact/phrase query in Search; let PMax work only at the edges.

### Conversion-First, Not Awareness-First
Rome demand is record-strong (22.9M arrivals in 2025, hotel occupancy >70%) but the STR market is dense (42K+ listings on Airbnb/Vrbo, ADR >$200). Win on **relevance, trust, and friction reduction**, not reach.

### Geo Targeting: "Presence or Interest" (not "Presence")
Default to **Presence or Interest** for Search. Google itself reports a conversion lift for travel accounts that switched from Presence-only. Bookers are outside Rome.

### Language: Match Ad → Landing → Booking Engine
Google may serve an ad in a language different from the user's query if it thinks they understand it. Do not let it improvise. **Tiered rollout**:
- Core launch: **English + Italian** — dedicated campaigns, ads, landing pages
- Expansion: Spanish, French, German — only when volume justifies
- Site-only at launch: the remaining translated languages stay live but unsupported by paid

Thirteen thin campaigns = low data density, slow learning. Fewer, properly localised campaigns win.

### Keyword Match-Type Rule
Launch on **exact + phrase only** on highest-value terms. Broad belongs in controlled experiments **after** negatives and conversion tracking are mature. Aggressive negatives from day one: `long term, monthly rent, lease, real estate, for sale, roommate, shared room, student housing, hostel job, cleaning jobs, office rent, commercial rent`.

### Bidding Strategy Progression (3 phases)
| Phase | Use |
|---|---|
| Early launch | `Maximise conversions` (no target) on brand and non-brand; PMax off or minimal |
| Controlled optimisation | `Maximise conversions` with **tCPA** once volume/quality stable |
| Value-based scaling | `Maximise conversion value` with **tROAS** once booking value/stay length/seasonality feed back cleanly |

Rule: optimise to **booking count** when values aren't robust, then switch to **value-based** once real revenue flows back.

### Measurement: Hybrid Commerce + Assisted Lead-Gen
Lux Romae mixes instant booking with WhatsApp/email/phone assisted close. The account must measure **both**. Without offline conversion import, paid traffic that closes later looks unprofitable and Smart Bidding optimises to the wrong signal.

**Primary conversions** (used for bidding): online confirmed `purchase` + **imported offline confirmed booking**.
**Secondary** (reporting only, not for bidding): `begin_checkout`, `click_tel`, `click_whatsapp`, `select_dates`. Letting shallow events steer bidding is a classic, expensive mistake.

### Attribution Default: Data-Driven (DDA)
DDA is Google's default for most conversion actions. Apply it to the primary booking conversion. Caveat: model changes alter credit distribution — re-tune tCPA/tROAS targets whenever you change attribution.

### Consent Mode v2 (EEA/UK/CH non-negotiable)
For European traffic, Google tags must pass `ad_user_data` and `ad_personalization` consent signals. To keep measurement, ad personalisation, and remarketing, collect consent **and share consent signals**. Italian Garante: profiling cookies require valid consent and prior information. Operationally: compliant CMP + consent mode v2 active + ads/remarketing tags blocked before consent.

### Budget Sizing Heuristics
| Scenario | Monthly | Split |
|---|---|---|
| Lean validation | €600–1,200 | 70–80% Search / 15–25% remarketing / 0–10% PMax test |
| Controlled growth | €1,200–2,500 | 60–70% Search / 15–20% remarketing / 10–20% PMax or travel feed |
| Peak-season push | €2,500–5,000 | 45–60% Search / 10–15% remarketing / 20–35% PMax or travel / 5–10% video |

Peak push only during spring, autumn, Christmas, or confirmed event compression (e.g. conclave-style weeks).

### Landing Page First-Screen Test
The page above the fold must answer in <3 seconds: **where is it, how many guests fit, why book direct, can I check dates now, what's the cancellation policy.** Storytelling goes below.

### Google Vacation Rentals Eligibility (if pursued)
- Listings with **fewer than 5 images are blocked**; 8+ recommended
- Structured data required; accurate price & availability mandatory
- Direct website link required
- Small inventory can use a crawled listing feed (no full XML feed needed)

---

## Chapter Index

| # | Title | Key Frameworks |
|---|-------|----------------|
| [ch01](chapters/ch01-executive-summary.md) | Executive Summary & Core Thesis | 4-Priority Architecture, Search-first sequencing |
| [ch02](chapters/ch02-market-funnel-diagnosis.md) | Market & Funnel Diagnosis | Rome demand/seasonality, event sensitivity, OTA leakage |
| [ch03](chapters/ch03-campaign-architecture.md) | Campaign Architecture & Budgets | Campaign mix table, budget scenarios, Search-vs-PMax rule |
| [ch04](chapters/ch04-keywords-audiences-bidding.md) | Keywords, Audiences & Bidding | Keyword clusters, match-type rule, Smart Bidding phases |
| [ch05](chapters/ch05-measurement-tracking.md) | Measurement & Tracking | GA4 event map, GTM sequence, offline import, primary vs secondary |
| [ch06](chapters/ch06-attribution-privacy.md) | Attribution & Privacy (GDPR) | DDA default, Consent Mode v2, Garante rules |
| [ch07](chapters/ch07-creative-landing-multilingual.md) | Creative, Landing Pages, Multilingual | Tiered language rollout, asset stack, sample ads |
| [ch08](chapters/ch08-roadmap-testing-kpis.md) | Roadmap, Testing & KPIs | 12-week plan, A/B matrix, KPI dashboard, automations |

## Topic Index

- **Attribution / DDA** → ch06
- **Audiences / Customer Match / Lookalike** → ch04
- **Automation / Scripts / Rules** → ch08
- **Bidding (tCPA, tROAS, Max Conv)** → ch04
- **Brand defence** → ch01, ch03
- **Budget scenarios** → ch03
- **Call assets / phone tracking** → ch05, ch07
- **Campaign architecture / mix** → ch03
- **Consent mode v2 / GDPR / Garante** → ch06
- **Conversion linker / Tag Assistant** → ch05
- **Cross-domain tracking (`_gl`, www ↔ book subdomain)** → ch05
- **Enhanced conversions** → ch05
- **Event-week / Easter / Christmas / conclave** → ch02, ch08
- **GA4 events / recommended events** → ch05
- **Geo targeting / Presence or Interest** → ch01, ch04
- **Google Vacation Rentals / Hotel Center** → ch01, ch03, ch07
- **GTM / Google Tag Manager** → ch05
- **KPIs (CPA, ROAS, CLTV, impression share)** → ch08
- **Landing page structure** → ch07
- **Language strategy / multilingual / Italian / Spanish / French / German** → ch07
- **Match types (exact, phrase, broad)** → ch04
- **Negative keywords** → ch04
- **Offline conversion import** → ch05
- **OTA leakage / "official site" badge** → ch01, ch02
- **Performance Max (PMax)** → ch01, ch03
- **Rate policies (Flexible, Best Price, Reserve, Family Flexible)** → ch07
- **Remarketing (Search / Display / video)** → ch03, ch04
- **Roadmap / 12-week plan** → ch08
- **Rome market / AirDNA / occupancy** → ch02
- **Sample ad copy (EN/IT)** → ch07
- **Search campaigns** → ch01, ch03, ch04
- **Sitelinks / callouts / structured snippets / price assets** → ch07
- **Testing / experiments / ad variations** → ch08
- **Turismo Roma events calendar** → ch02

## Supporting Files

- [glossary.md](glossary.md) — every key term with definitions and chapter refs
- [patterns.md](patterns.md) — concrete techniques and operating patterns
- [cheatsheet.md](cheatsheet.md) — decision tables and quick reference

---

## Scope & Limits

This skill covers the Lux Romae Google Ads strategy document only. It is grounded in:
- The Lux Romae public site & booking page (Ostiense/Piramide, 2BR, Flexible/Best Price/Reserve/Family Flexible rate policies)
- Rome market data (Turismo Roma 2025, AirDNA, CoStar/STR, HVS)
- Google's official documentation for Search, PMax, attribution, Smart Bidding, hotel/vacation rentals, consent mode v2
- Italian Garante and EU Commission guidance on cookies & lawful processing

**Six open questions** (see ch08) materially affect final campaign design — most importantly: does the booking engine complete instant bookings, or route many users to assisted contact? Until resolved, follow the conservative path: buy only the clearest intent, measure every step, resist broadening faster than data justifies.

This is operational guidance, not legal advice; CMP/consent implementation should be validated by counsel for the actual jurisdictions served.
