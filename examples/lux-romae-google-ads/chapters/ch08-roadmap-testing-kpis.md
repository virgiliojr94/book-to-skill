# Chapter 8: Roadmap, Testing & KPIs

## Core Idea
Sequence work over **12 weeks**: foundation → funnel alignment → Search launch → remarketing → value optimisation → expansion. Test inside Google's experiments framework, not by ad-hoc setting changes. Run **two decision dashboards**: a daily traffic/spend one and a weekly confirmed-booking one.

## Frameworks Introduced

### 12-Week Implementation Plan

| Phase | Timeframe | Actions | Main outputs |
|---|---|---|---|
| **Foundation** | Week 1–2 | Verify GTM, GA4, Google Ads link, Consent Mode v2, conversion linker, event map, offline import design | Clean measurement base |
| **Funnel alignment** | Week 2–3 | Tighten booking pages, shorten path to availability, align language pages, add trust + policy blocks | Better LP conversion rate |
| **Search launch** | Week 3–4 | Brand + high-intent non-brand Search in EN + IT; assets + negative lists | Efficient base traffic |
| **Remarketing layer** | Week 5–6 | Build GA4 + Ads audiences; launch Search remarketing + Display remarketing | Lower-cost recovery traffic |
| **Value optimisation** | Week 7–9 | Import confirmed offline bookings; enable enhanced conversions; shift mature campaigns to tCPA or tROAS | Better bidding quality |
| **Expansion** | Week 9–12 | Add Spanish, French, German where justified; test PMax or travel inventory if feed support exists | Controlled scale |
| **Travel inventory** | Parallel path | Check booking-engine/partner support for Google Vacation Rentals / Hotel Center | High-intent Google travel presence |

### Prioritised Checklist (use as a launch gate)

| Priority | Task |
|---|---|
| **Critical** | Confirm the final booking path: instant online vs assisted close |
| **Critical** | Install/verify GTM, GA4, Ads tag, conversion linker, Consent Mode v2 |
| **Critical** | Set up offline import for confirmed email/WhatsApp/phone bookings |
| **Critical** | Launch brand defence Search |
| **High** | Launch non-brand long-tail Search |
| **High** | Build multilingual language-matched landing pages for top languages |
| **High** | Create audience pools for date checkers and begin-checkout visitors |
| **High** | Add sitelinks, callouts, snippets, call asset, location asset |
| **High** | Check Vacation Rentals / Hotel Center support with the booking engine |
| **Medium** | Test PMax after conversion quality is proven |
| **Medium** | Add video remarketing + richer creative |

### A/B Testing Matrix (run inside Google's experiments framework)

| Test | Variant A | Variant B | Main KPI | Min observation rule |
|---|---|---|---|---|
| Value proposition | Book Direct emphasis | Flexible Cancellation emphasis | Booking rate, CPA | Until one full booking cycle has passed |
| CTA | Check Dates | Book Direct | Begin-checkout rate, booking rate | Prefer equal traffic split |
| Landing-page order | Availability widget first | Trust + reviews first | Begin-checkout rate | Keep same traffic source |
| Policy emphasis | Best Price plan highlighted | Flexible plan highlighted | Booking value + cancellation-adjusted CPA | Measure confirmed bookings, not only form submits |
| Language match | Native-language LP | English fallback LP | Conversion rate by language | Only in meaningful traffic languages |
| Remarketing window | 7-day | 30-day | CPA + conversion rate | Exclude converters in both arms |
| Bidding | Max Conv + tCPA | Max Conv Value + tROAS | Revenue, ROAS, confirmed CPA | Only after reliable values exist |
| Inventory expansion | Search only | Search + PMax or travel feed | Incremental conversions | Use formal uplift / custom experiment |

### Automation Stack (protective, not flashy)

| Automation | Tool | Lux Romae use |
|---|---|---|
| Spend spike alert | Automated rule | Email when campaign cost exceeds planned pacing |
| Broken landing-page monitor | Link Checker script | Catch dead URLs in ads + sitelinks before waste |
| Daily performance digest | Account Summary Report script | Snapshot: spend, conversions, CPA, revenue |
| Weekly search-term export | Script/report to spreadsheet | Systematic query mining + negative-keyword additions |
| Event-week budget schedule | Automated rule | Raise/lower budgets around Easter, holidays, Rome events |
| Phone-hours scheduling | Call asset schedule | Show phone CTA only during real response hours |

### KPI Definitions (the truth metric: profitable confirmed direct bookings)

| KPI | Formula | Why it matters |
|---|---|---|
| **CPA** | Ad spend ÷ confirmed direct bookings | Core efficiency |
| **ROAS** | Attributed booking revenue ÷ ad spend | Revenue efficiency |
| **Conversion rate** | Confirmed bookings ÷ ad clicks (or sessions) | Funnel effectiveness |
| **CLTV** | First-stay net contribution + expected repeat + referral value | Determines sustainable acquisition ceiling — internal metric, not platform-reported |
| **Booking-start rate** | Begin checkouts ÷ landing-page sessions | Detects LP friction |
| **Assisted close rate** | Confirmed offline bookings ÷ booking requests/calls | Lead-quality handling |
| **Search impression share** | Impressions ÷ eligible impressions | Missed demand |
| **Brand leakage rate** | OTA/intermediary clicks on branded terms ÷ total branded clicks (where measurable) | How well direct demand is protected |

CLTV is **internal management**, not platform-reported — Google won't compute it for you.

### Two-Dashboard Operating Model (strong recommendation)
- **Daily**: traffic + spend dashboard (Google Ads native) — answers "are we buying right traffic efficiently?"
- **Weekly**: confirmed-booking dashboard including offline-imported conversions + cancellation-adjusted economics — answers "are we attracting profitable bookings, not just any?"

Without the second, the account will look better or worse than it actually is depending on how much closes later via message/phone.

### KPI Dashboard Block Layout

| Block | Metric | Source | Cadence | Operational question |
|---|---|---|---|---|
| Spend & reach | Spend, clicks, CTR, CPC, impression share | Ads | Daily | Are we buying the right traffic efficiently? |
| Search quality | Search terms, exact-match share, negative additions, top imp share | Ads | Twice weekly | Are irrelevant queries leaking budget? |
| Landing pages | Sessions, engagement rate, booking-start, check-availability | GA4 | Weekly | Which page/language creates friction? |
| Conversions | Online bookings, requests, calls, offline confirmed bookings | Ads + CRM/booking log | Daily + weekly | Are conversions real + being imported? |
| Profitability | CPA, ROAS, average booking value, booked nights, stay length | Ads + booking engine/sheet | Weekly | Is scale improving contribution, not just volume? |
| Segmentation | Performance by geo, language, device, audience, day | Ads + GA4 | Weekly | Which slices deserve isolated campaigns? |
| Quality of demand | Cancellation-adjusted CPA, no-show-adjusted ROAS, assisted close rate | Booking records | Monthly | Are we attracting the right guests, not just any? |

## Open Questions (materially affect final design — resolve before scaling)

| Open point | Why it matters |
|---|---|
| Does the booking engine complete instant bookings, or route many users to assisted contact? | Determines whether the account is ecommerce or lead-gen with offline closure |
| Current GTM / GA4 / Ads tag / CMP status | Determines pre-launch implementation work |
| Historical data by country, language, device, season | Drives which of the 13 languages get paid priority first |
| Average booking value, length of stay, margin, cancellation rate, OTA commission avoided | Needed to set rational CPA + ROAS targets |
| Does the booking engine support Vacation Rentals / Hotel Center via partner? | Determines access to Google's highest-intent lodging surfaces |
| Share of paid traffic converting via phone, WhatsApp, or later email | Determines how critical offline import is |

**Until those are resolved**: buy only the clearest intent, measure every step, resist broadening faster than the data justifies.

## Mental Models

- **"Build measurement before media."** Foundation weeks 1–2 exist for a reason; spending before they're done amplifies noise.
- **"Experiments > setting changes."** Google's experiments framework + ad variations let you actually attribute lift to changes; ad-hoc edits don't.
- **"The truth metric is later than today."** Cancellation-adjusted, no-show-adjusted, with offline import — that's the real account performance.

## Anti-patterns

- **Going to "Search launch" before tracking is verified** → bidding learns on broken data
- **Daily-only dashboards** → optimistic or pessimistic, never accurate
- **Ad-hoc setting changes** instead of structured experiments → no clean attribution of lift
- **Scaling before answering the 6 open questions** → budget grows but the system is still wrong
- **Letting the daily spike-alert be the only automation** → no negative-keyword pipeline, no LP link monitoring, no event-week scheduling

## Key Takeaways

1. **Don't compress the 12 weeks.** Foundation before launch, launch before remarketing, remarketing before value-bid, value-bid before expansion.
2. **Treat the critical checklist as a launch gate** — none can be skipped.
3. **Test inside Google's experiments framework**, with one variable at a time.
4. **Build six protective automations** before adding more campaigns.
5. **Two dashboards, not one** — daily traffic + weekly confirmed bookings (with offline imports).
6. **CLTV is internal management**, not a platform metric.
7. **Resolve the six open questions** before any aggressive scaling.

## Connects To
- **Ch 1**: roadmap operationalises the 4-Priority Architecture in time
- **Ch 3**: budget scenarios slot into phases by week
- **Ch 5**: foundation phase = the measurement work in detail
- **Ch 6**: foundation phase also includes CMP + Consent Mode v2
- **Ch 7**: language expansion is a Phase 6 (week 9–12) action, not launch
