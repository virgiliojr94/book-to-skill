# Chapter 4: Keywords, Audiences & Bidding

## Core Idea
**Exact + phrase on highest-value terms first; broad only after negatives and conversion data are mature.** Geo defaults to **Presence or Interest** (travel lift). Bidding climbs three rungs: Max Conv → tCPA → tROAS.

## Frameworks Introduced

### Keyword Map (launch structure)

| Cluster | Launch match types | Sample themes |
|---|---|---|
| **Brand** | Exact, phrase | `lux romae`, `lux romae apartment`, `lux romae rome`, `lux romae direct booking` |
| **Location-intent** | Exact, phrase | `apartment ostiense rome`, `apartment piramide rome`, `apartment near ostiense station`, `apartment near piramide metro` |
| **Product-intent** | Exact, phrase | `2 bedroom apartment rome`, `family apartment rome`, `design apartment rome`, `apartment rome for 4` |
| **Policy-intent** | Phrase | `book direct rome apartment`, `flexible cancellation rome apartment`, `reserve now pay later rome apartment` |
| **Competitor interception** | Very selective phrase only | `better than hotel near ostiense`, `apartment instead of hotel rome ostiense` |

### Match-Type Discipline
- **Exact match** = the most steering / lowest waste
- **Phrase match** = expands meaning controllably
- **Broad match** = relies on Smart Bidding to police relevance; only after negatives + tracking are mature
- Open with exact + phrase; introduce broad as a **controlled experiment**, not a default

### Negative-Keyword Starter List (aggressive from day one)
`long term, monthly rent, lease, real estate, for sale, roommate, shared room, student housing, hostel job, cleaning jobs, property management jobs, office rent, commercial rent` + any irrelevant neighbourhood / transport-only searches that don't carry lodging intent.

### Geo Targeting Rule
- Use **Presence or Interest** (not "Presence" alone) for travel — Google documents a conversion lift for travel accounts switching from Presence to Presence or Interest
- Bookers are mostly **outside Rome**; "Rome residents only" defeats the channel
- Begin with **source-market campaigns** (top inbound markets) rather than "in Rome" geo logic

### Audience Stack (build in this order)
1. **Website visitors** (all)
2. **Date checkers** (custom event triggered)
3. **Begin-checkout users**
4. **High-engagement visitors** (session duration / scroll depth)
5. **Email leads** (form submitters)
6. **Confirmed guests** — used as **exclusion**, not target
7. **Customer Match** (Search, YouTube, Gmail, Display) — only with valid consent + usable first-party data

**Lookalike note**: Google's Demand Gen Lookalike segments are transitioning to **suggestion mode through 2026**. Don't build strategy on the legacy autobuilt assumption. Customer Match in EEA contexts requires correct consent handling.

### Bidding-Strategy Progression (3 phases)

| Phase | Search brand | Search non-brand | PMax | Why |
|---|---|---|---|---|
| **Early launch** | Max Conversions (no target) | Max Conversions (no target) | Off or very limited | Let Google optimise to deepest reliable conv while data builds |
| **Controlled optimisation** | Max Conv + tCPA | Max Conv + tCPA | Max Conv or Max Conv Value | Once conversion volume + quality stable |
| **Value-based scaling** | Max Conv Value + tROAS (if booking values vary materially) | Max Conv Value + tROAS on mature campaigns | Max Conv Value + tROAS | Once booking value, stay length, seasonality flow back accurately |

Strategy-label note: Search labels were consolidated — Max Conversions can carry an optional tCPA; Max Conv Value an optional tROAS. Smart Bidding uses auction-time signals (device, browser, location, time of day, remarketing status).

**Decisive rule**: optimise to **booking count** when values aren't robust yet → shift to **value-based** once real revenue flows back cleanly.

## Key Concepts

- **Smart Bidding**: Google's auction-time, signal-driven bidding family (tCPA, tROAS, Max Conv, Max Conv Value)
- **tCPA / tROAS**: target Cost-Per-Action / target Return-On-Ad-Spend — set after volume is reliable
- **Customer Match**: upload hashed customer data to serve/exclude on Search, YouTube, Gmail, Display
- **Lookalike (Demand Gen)**: similar-audience expansion — now in suggestion mode through 2026
- **Presence vs Presence-or-Interest**: geo targeting modes; the latter captures intent-based non-resident demand
- **Source market**: country/region the booker browses from (not the destination)

## Mental Models

- **"Exact pins, phrase fishes, broad explores."** Use each for what it's good at; don't open on the exploratory one.
- **"Negatives are a budget lever, not a hygiene chore."** For one-property advertisers, negative discipline is one of the biggest efficiency wins.
- **"Bidding strategy follows data, not ambition."** Don't set a tROAS target before you have credible revenue values flowing back.

## Anti-patterns

- **Launching on broad match** with thin tracking → waste before you can see it
- **Ignoring negatives until something obvious appears in search terms** → already paid for the lesson
- **Targeting "in Rome only"** for an inbound-tourism business → cuts the actual booker pool
- **Setting tROAS too early** → erratic bidding because Smart Bidding has no reliable value signal
- **Building strategy on Lookalike autobuild** → docs say it's moving to suggestion mode through 2026

## Key Takeaways

1. **Exact + phrase first.** Broad is an experiment, not a default.
2. **Negatives from day one** — long-term/rent/job/commercial/etc.
3. **Presence or Interest** for geo; build by source market.
4. **Stack audiences from broad → deep** and use guests for **exclusion**.
5. **Climb the bidding ladder**: Max Conv → tCPA → tROAS only as data justifies.
6. **Customer Match needs EEA-grade consent**; Lookalike is moving to suggestion mode.

## Connects To
- **Ch 3**: pinning keywords in Search makes the Search-vs-PMax rule deterministic
- **Ch 5**: bidding ladder depends on stable, primary conversions (offline import included)
- **Ch 6**: Customer Match + remarketing require consent-mode-v2-compliant signal sharing
- **Ch 8**: test plan rotates value props, CTAs, landing-page order, bidding strategy
