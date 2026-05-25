# Chapter 5: Measurement & Tracking

## Core Idea
Treat the funnel as **hybrid commerce + assisted lead-gen**. Measure both the online `purchase` event and the offline-closed bookings from email/WhatsApp/phone — then **import them back** so Smart Bidding optimises real revenue, not phantom leads.

## Frameworks Introduced

### GA4 Event Map (recommended event model)

| Funnel stage | GA4 event | Google Ads treatment | Notes |
|---|---|---|---|
| Landing page view | `page_view` | Reporting only | Base traffic / landing analysis |
| Availability interaction | custom `check_availability` or `view_search_results` | Secondary | Strong intent signal |
| Date selection | custom `select_dates` | Secondary | Useful for remarketing |
| Booking started | `begin_checkout` | Secondary (maybe primary if data sparse) | Deep funnel |
| Contact details entered | `add_contact_info` | Secondary | Useful in assisted checkout |
| Booking request submitted | `generate_lead` or custom `booking_request_submit` | Primary **if** site behaves like lead-gen | Must be qualified offline later |
| Booking confirmed online | `purchase` | **Primary** | Best primary conversion if available |
| Phone click | custom `click_tel` | Secondary | Pair with call reporting or offline import |
| WhatsApp click | custom `click_whatsapp` | Secondary | Important for assisted journeys |
| Offline confirmed booking | imported offline conversion | **Primary** | Crucial when requests close after the visit |

### GTM → GA4 → Ads Implementation Sequence (strict order)

| Step | Action | Why it matters |
|---|---|---|
| 1 | **Link GA4 and Google Ads** (property ↔ ad account; enable audience + metric sharing) | Required for imported audiences and Analytics diagnostics in Ads |
| 2 | **Deploy Google tag through GTM** (one governance layer for GA4 + Ads) | Cleaner change control & debugging |
| 3 | **Add Conversion Linker on all pages** | Stores ad-click info for reliable conversion measurement |
| 4 | **Verify cross-domain / cross-subdomain continuity** (include `www.luxromaeapartments.com` and `book.luxromaeapartments.com`; verify `_gl` behaviour if flow spans distinct tag contexts) | Prevents session + attribution breakage across the booking flow |
| 5 | **Configure GA4 events** (ecommerce/lead events + Lux Romae custom events) | Builds audiences, funnel reporting, imported conversions |
| 6 | **Create native Google Ads conversions** (native Ads action for booking-confirm or request-submit; keep imported GA4 conversions **secondary unless deliberately promoted**) | Google notes imported GA4 conversions created from Analytics are secondary by default |
| 7 | **Turn on enhanced conversions** (web if online checkout exists; leads if bookings close later) | Improves measurement accuracy + bidding |
| 8 | **Implement offline conversion import** (Ads Data Manager or supported upload for confirmed bookings from requests, calls, messages) | Lets Smart Bidding optimise to real bookings instead of thin proxy leads |
| 9 | **Add call measurement** (call assets + call reporting; track phone link clicks on site separately) | Important for mobile booking journeys |
| 10 | **Debug end to end** (GA4 DebugView + Tag Assistant) | Prevents silent data loss |

### Primary vs Secondary Conversion Rule
- **Primary** (used for bidding): online confirmed `purchase` + imported offline confirmed booking
- **Secondary** (reporting only): `begin_checkout`, `click_tel`, `click_whatsapp`, `select_dates`
- **Avoid letting shallow events steer bidding** — a phone-click on mobile is intent, not revenue

### Cross-Domain Watch-Out (Lux Romae specific)
Site appears split across `www.luxromaeapartments.com` (marketing) and `book.luxromaeapartments.com` (booking engine). Cross-subdomain or cross-domain linker must be configured; verify `_gl` link decoration is present where the user crosses between distinct tag contexts. Without this, sessions break and attribution collapses at the worst point — the booking entrance.

## Key Concepts

- **Conversion Linker (GTM tag)**: stores ad-click parameters (gclid, etc.) in first-party cookies so later conversions can attribute back to the click
- **Enhanced conversions**: hashes first-party data (email, phone) to recover measurement lost to consent or cross-device gaps
- **Offline conversion import**: upload confirmed bookings (with the original `gclid` or enhanced-conversion identifier) so Ads counts them as primary conversions
- **Imported GA4 conversion**: a GA4 event imported into Ads — **secondary by default**; promote to primary only deliberately
- **DebugView (GA4)** / **Tag Assistant**: live debugging surfaces to verify events fire correctly

## Mental Models

- **"If it doesn't come back, it didn't happen — for Smart Bidding."** Without offline import, the late-closing portion of paid traffic is invisible to the algorithm.
- **"Native Ads conversions beat imported GA4 ones for bidding."** Use a native Ads action for the primary booking signal; let GA4 imports stay secondary unless you deliberately promote them.
- **"Verify, don't assume."** A text crawl of the public site didn't show `gtag`, `googletagmanager`, or visible cookie text — but that's not proof. Validate with Tag Assistant + browser inspection before launch.

## Anti-patterns

- **Skipping offline import** because "we mostly book online" → assisted bookings disappear; bidding learns the wrong target
- **Optimising to phone clicks / WhatsApp clicks as primary** → shallow events steer spend toward intent-without-purchase
- **Putting Conversion Linker only on the checkout page** → ad-click info never stored at landing; attribution silently breaks
- **Cross-subdomain (`www.` ↔ `book.`) without `_gl` continuity** → sessions split at the booking entrance; the highest-value step is the one that breaks
- **Promoting imported GA4 conversions to primary without reason** → noisier signal than a native Ads action

## Key Takeaways

1. **GA4 event map first, tags second.** Define the funnel events before instrumenting.
2. **Offline import is mandatory** if any meaningful share of bookings closes via email/WhatsApp/phone.
3. **Native Ads conversion for the primary booking**; imported GA4 stays secondary unless deliberately promoted.
4. **Conversion Linker on every page** — not just on checkout.
5. **Cross-subdomain continuity check** between `www.` and `book.` is the single most likely silent failure.
6. **Enhanced conversions on**, scoped to web checkout or leads as appropriate.
7. **Debug with DebugView + Tag Assistant** end-to-end before media spends.

## Connects To
- **Ch 3**: PMax cannot move past test share until this measurement is clean
- **Ch 4**: bidding ladder (Max Conv → tCPA → tROAS) only progresses when these primary conversions are stable
- **Ch 6**: consent mode v2 + enhanced conversions interact — both required for full European measurement
- **Ch 8**: foundation phase (weeks 1–2) is exactly this work
