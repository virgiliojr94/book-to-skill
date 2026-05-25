# Patterns

Concrete techniques and operating patterns from the strategy. Each pattern: **When to use → How → Trade-offs**.

## Brand-Defence Search

**When to use**: from day one for any direct-booking brand that's also distributed on OTAs (Airbnb, Vrbo, Booking).
**How**: exact + phrase keywords on `lux romae`, `lux romae apartment`, `lux romae rome`, `lux romae direct booking`. Pair with Max Conversions bidding (no target at launch).
**Trade-offs**: trivial CPC if no OTA bids on the brand; non-trivial otherwise. Either way, cheaper than letting OTAs harvest your booked guests at 15–20% commission.

## Search-vs-PMax Pinning

**When to use**: whenever Search and PMax run in the same account.
**How**: ensure every high-value query exists as an eligible exact or phrase keyword in Search. Google prioritises Search over PMax on identical-query matches.
**Trade-offs**: more keyword housekeeping; in return, PMax can't cannibalise your most efficient demand.

## Tiered Multilingual Rollout

**When to use**: when the site is multilingual but the ad budget is finite.
**How**: launch paid only in core languages with proven demand (EN + IT for Lux Romae). Expand into ES/FR/DE when volume + conversion data justify. Other site languages live but unsupported by paid until demand is proven.
**Trade-offs**: gives up theoretical reach; gains data density and faster learning per ad group.

## Aggressive Day-One Negatives

**When to use**: every new account, especially single-property advertisers.
**How**: pre-seed a negative list with `long term, monthly rent, lease, real estate, for sale, roommate, shared room, student housing, hostel job, cleaning jobs, property management jobs, office rent, commercial rent`. Append weekly from search-terms exports.
**Trade-offs**: tiny risk of cutting an edge query; eliminates a known waste category immediately.

## Presence-or-Interest Geo Targeting

**When to use**: travel/lodging advertisers whose customers are not local.
**How**: set advanced location option to "Presence or Interest" (default) rather than restricting to "Presence". Build source-market campaigns by country, not "in Rome".
**Trade-offs**: slightly higher click variance; Google reports a conversion lift for travel accounts that made the switch.

## Three-Phase Bidding Climb

**When to use**: every new Search/PMax account.
**How**:
1. **Early**: Max Conversions (no target) — let the system stabilise
2. **Controlled**: Max Conversions + tCPA — once volume + quality stable
3. **Value-based**: Max Conv Value + tROAS — once real booking values flow back (incl. offline imports)
**Trade-offs**: tROAS rushed before clean values causes erratic bidding; waiting too long leaves revenue efficiency on the table.

## Hybrid Commerce + Lead-Gen Conversion Set

**When to use**: any site mixing instant booking with email/WhatsApp/phone assisted close.
**How**: 
- Primary: online `purchase` + imported offline confirmed booking
- Secondary: `begin_checkout`, `click_tel`, `click_whatsapp`, `select_dates`
- Never let secondary events steer bidding.
**Trade-offs**: more wiring (offline import); without it, Smart Bidding optimises to phantom or shallow signals.

## Offline Conversion Import Loop

**When to use**: any meaningful share of bookings closes off-site (email/WhatsApp/phone).
**How**: capture `gclid` (or enhanced-conversion identifier) at landing; carry through CRM/booking log; upload confirmed bookings via Ads Data Manager or supported upload route; promote to primary.
**Trade-offs**: requires operational discipline + a place to store the click ID; the payoff is bidding on real revenue, not proxies.

## Cross-Subdomain Continuity Check (`www.` ↔ `book.`)

**When to use**: when the marketing site and booking engine live on different subdomains or domains.
**How**: configure cross-domain/cross-subdomain linker in GTM; verify `_gl` link decoration is appended when the user crosses between tag contexts; debug with Tag Assistant on a real booking flow.
**Trade-offs**: silent failure mode if missed — sessions split at the highest-value step (booking entrance) and attribution collapses there.

## Conversion Linker on Every Page

**When to use**: always.
**How**: fire the Conversion Linker GTM tag on **all** pages, not only checkout. Stores ad-click info early so later conversions attribute reliably.
**Trade-offs**: none meaningful; failure mode is silent attribution loss.

## Native Ads Conversion as Primary

**When to use**: whenever an online booking confirmation exists.
**How**: create a native Google Ads conversion (booking-confirm or request-submit) and set it as primary for bidding. Keep imported GA4 conversions secondary unless deliberately promoted.
**Trade-offs**: extra tag work; cleaner bidding signal than relying solely on imported GA4 events.

## Consent Mode v2 + CMP Gate

**When to use**: any EEA/UK/CH traffic.
**How**: deploy a compliant CMP; activate Consent Mode v2 with `ad_user_data` + `ad_personalization`; preferred approach is to **not load ads/remarketing tags before the user's choice**.
**Trade-offs**: a small share of users won't be measurable/remarketable; the alternative is regulatory + signal-quality degradation.

## Data-Driven Attribution + Bid Retune

**When to use**: every meaningful conversion in the account; revisit on any attribution change.
**How**: set DDA for the primary booking conversion. Whenever the attribution model changes, immediately recalibrate tCPA / tROAS targets in the same change window.
**Trade-offs**: requires discipline pairing model changes with bid changes — but without it, bids end up misaligned with the new credit distribution.

## First-Screen Booking Interview

**When to use**: every landing page used by paid traffic.
**How**: in <3 seconds above the fold, answer: (1) where is it, (2) how many guests fit, (3) why book direct, (4) can I check dates now, (5) what's the cancellation policy. Hero → trust strip → availability widget → differentiators → policy → social proof → FAQ.
**Trade-offs**: less storytelling space above the fold; meaningful conversion-rate gain.

## Full Ad-Asset Stack

**When to use**: every Search ad group.
**How**: deploy sitelinks, callouts, structured snippets, call asset (with answered-hours schedule), location asset, plus price/promotion only when accuracy can be guaranteed. RSAs with 8–10 headlines and 3–4 descriptions.
**Trade-offs**: more creative work; assets contribute to Ad Rank and trust, missing them costs cheap impression share.

## Event-Week Budget Schedule

**When to use**: Rome event compression windows (e.g. conclave, Easter, Christmas, confirmed major events from Turismo Roma calendar).
**How**: automated rules raise budgets and loosen ROAS/CPA targets the week **before** demand spikes. Pre-build short-lived promo assets reusing only language that matches guest intent.
**Trade-offs**: requires a live event-monitoring routine; if you wait until compression starts, you've already missed cheap clicks.

## Two-Dashboard Operating Model

**When to use**: any STR / lodging account with offline-closing bookings.
**How**: 
- Daily: spend + traffic dashboard (Google Ads native)
- Weekly: confirmed-booking dashboard with offline imports + cancellation-adjusted economics
**Trade-offs**: more reporting setup; without it, the account looks better or worse than it actually is depending on offline-close share.

## Protective Automation Stack

**When to use**: any account where the operator can't watch metrics every day.
**How**: deploy six automations: spend-spike alert, broken-LP monitor (Link Checker script), daily perf digest (Account Summary script), weekly search-term export, event-week budget schedule, phone-hours call-asset scheduling.
**Trade-offs**: setup cost; protects against high-cost failure modes (broken LPs, runaway spend) more than it generates upside.

## Google Vacation Rentals / Hotel Center Onboarding

**When to use**: when the booking engine or a connectivity partner supports it.
**How**: confirm partner connectivity → ensure structured data on listing → 8+ images per listing (<5 is blocked) → accurate price/availability feed → direct website link. Small inventory can use a crawled listing feed.
**Trade-offs**: technical setup; in return, access to Google's highest-intent lodging surfaces and the "official site" badge unavailable to OTAs.

## Google Experiments for Testing

**When to use**: any meaningful Search or PMax change you want to attribute lift to.
**How**: use Campaign Experiments, Ad Variations, or Performance Max Experiments — not ad-hoc setting changes. One variable per test; minimum observation = one full booking cycle for booking-rate KPIs.
**Trade-offs**: slower than just flipping a setting; the only honest way to know what worked.
