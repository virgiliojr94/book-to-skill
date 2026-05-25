# Glossary

**4-Priority Architecture** — Lux Romae's core campaign frame: brand defence Search, high-intent non-brand Search, remarketing, and Google Vacation Rentals / Hotel Center connectivity (Ch1, Ch3)

**Ad asset** — formerly "extension"; sitelinks, callouts, snippets, call, location, price, promotion. Contributes to Ad Rank (Ch7)

**Ad Rank** — auction ranking factor that determines ad position and eligibility; assets contribute (Ch7)

**ADR (Average Daily Rate)** — hotel/STR metric; Rome ADR was >$200 (AirDNA) and €351.13 during 25 Apr 2025 event compression (Ch2)

**`add_contact_info`** — GA4 recommended/custom event for contact-details step; secondary signal (Ch5)

**`ad_personalization`** — Consent Mode v2 signal indicating consent for personalised advertising (Ch6)

**`ad_user_data`** — Consent Mode v2 signal indicating consent to share user data with ads (Ch6)

**AirDNA** — STR market intelligence source; reports 42,376 Airbnb/Vrbo properties, 64% occupancy, seasonality score 65 for Rome (Ch2)

**Assisted close / assisted enquiry** — booking that completes off-site via WhatsApp/email/phone after a paid visit; invisible to bidding without offline import (Ch1, Ch5)

**Assisted close rate** — confirmed offline bookings ÷ booking requests or calls; measures lead-quality handling (Ch8)

**Begin checkout (`begin_checkout`)** — GA4 ecommerce event; deep funnel signal; secondary by default (Ch5)

**Brand defence / brand protection** — paid Search on your own property name to prevent OTAs/aggregators from intercepting your branded demand (Ch1, Ch3)

**Brand leakage rate** — OTA/intermediary clicks on branded terms ÷ total branded clicks; measures direct-demand protection (Ch8)

**Broad match** — keyword match type that relies on Smart Bidding to police relevance; suitable only after negatives + tracking are mature (Ch4)

**CLTV (Customer Lifetime Value)** — first-stay net contribution + expected repeat + referral; internal management metric, not Google-reported (Ch8)

**CMP (Consent Management Platform)** — software collecting user consent and feeding it to tags (Ch6)

**Conversion Linker** — GTM tag that stores ad-click info (`gclid` etc.) in first-party cookies for later attribution. Must be on every page (Ch5)

**Consent Mode v2** — Google framework for passing consent signals; v2 adds `ad_user_data` and `ad_personalization`. Required for European traffic (Ch6)

**Controlled growth (budget scenario)** — €1,200–2,500/month; 60–70% Search / 15–20% remarketing / 10–20% PMax or travel feed (Ch3)

**CoStar / STR** — hotel performance data source; reported Rome's 88.8% peak occupancy and €351.13 ADR on 25 Apr 2025 (Ch2)

**CPA (Cost Per Action)** — ad spend ÷ confirmed direct bookings; core efficiency metric (Ch8)

**Crawled listing feed** — small-inventory option for Google Vacation Rentals where Google fetches listings without a full XML feed (Ch3, Ch7)

**Customer Match** — upload hashed customer data for targeting/exclusion across Search, YouTube, Gmail, Display; requires EEA-grade consent (Ch4)

**DDA (Data-Driven Attribution)** — Google's default attribution model for most conversion actions; stronger with ~200 conversions + 2,000 ad interactions over 30 days (Ch6)

**DebugView (GA4)** — live debug surface to verify events fire correctly (Ch5)

**Demand Gen Lookalike** — similar-audience expansion; transitioning to suggestion mode through 2026 (Ch4)

**Enhanced conversions** — hashes first-party data (email/phone) to recover measurement lost to consent/cross-device gaps (Ch5)

**Eligible keyword** — Search keyword that could legitimately match the user's query and is not paused/blocked; determines Search-vs-PMax priority (Ch3)

**Event compression** — sharp short-term demand spike around events (e.g. conclave, Pope's funeral); requires loosening ROAS/CPA targets in advance (Ch2)

**Exact match** — most steering, lowest waste keyword match type; preferred at launch (Ch4)

**Family Flexible** — one of Lux Romae's public rate policy categories (Ch1, Ch7)

**`gclid`** — Google click ID stored in URL/cookies; basis for click-to-conversion attribution (Ch5)

**`generate_lead`** — GA4 recommended event for lead-submission; can be primary if site behaves like lead-gen (Ch5)

**`_gl` (link decoration)** — parameter used by Google Tag for cross-domain session continuity; critical between `www.luxromaeapartments.com` and `book.luxromaeapartments.com` (Ch5)

**Google Vacation Rentals** — Google product surfacing vacation rentals in dedicated travel search; supports free booking links + paid hotel formats (Ch1, Ch3, Ch7)

**Hotel Center** — Google's hotel inventory/feed surface where direct suppliers can earn the "official site" badge OTAs cannot (Ch1, Ch3)

**HVS** — hospitality consulting source; reports stable Rome hotel supply with further luxury openings (Ch2)

**Lean validation (budget scenario)** — €600–1,200/month; 70–80% Search / 15–25% remarketing / 0–10% PMax test (Ch3)

**Lookalike (Demand Gen)** — see Demand Gen Lookalike (Ch4)

**Max Conversions / Max Conversion Value** — Smart Bidding strategies; can carry optional tCPA / tROAS respectively (Ch4)

**Negative keyword** — keyword excluded from triggering an ad; biggest efficiency lever for one-property advertisers (Ch4)

**Offline conversion import** — uploading confirmed off-site bookings (via Ads Data Manager or supported upload) so Smart Bidding optimises real bookings (Ch5)

**"Official site" badge** — Google hotel-surface badge available to direct suppliers; OTAs do not qualify (Ch1, Ch2)

**Ostiense / Piramide** — Lux Romae neighbourhood + transport hub (Piramide Metro, Ostiense Station) (Ch1, Ch2, Ch7)

**Peak-season push (budget scenario)** — €2,500–5,000/month; 45–60% Search / 10–15% remarketing / 20–35% PMax or travel feed / 5–10% video remarketing (Ch3)

**Performance Max (PMax)** — cross-channel automated campaign type; needs ≥6 weeks stable + minimal early changes; expansion layer, not starter (Ch1, Ch3)

**Phrase match** — controlled meaning expansion keyword type; safe to use alongside exact at launch (Ch4)

**Presence vs Presence or Interest** — geo targeting modes; "Presence or Interest" is preferred for travel — Google reports a conversion lift (Ch1, Ch4)

**Primary conversion** — action used for bidding; should be online confirmed booking + imported offline confirmed booking (Ch5, Ch6)

**Profiling cookie** — cookie creating a user profile for advertising/personalisation; requires explicit consent under Italian Garante / GDPR (Ch6)

**`purchase` (GA4 event)** — best primary conversion when an online checkout completes (Ch5)

**Quality Score** — Google's keyword-level relevance score; improves with ad-LP-keyword coherence + CTR + LP experience (Ch7)

**Rate policies (Lux Romae)** — Flexible, Best Price, Reserve, Family Flexible (Ch1, Ch7)

**Reserve (rate policy)** — one of Lux Romae's lower-friction reserve options (Ch1)

**ROAS (Return On Ad Spend)** — attributed booking revenue ÷ ad spend (Ch4, Ch8)

**RSA (Responsive Search Ad)** — Search ad format mixing headlines/descriptions per query; needs 8–10 headlines + 3–4 descriptions (Ch7)

**Search impression share** — impressions received ÷ eligible impressions; indicates missed demand (Ch8)

**Secondary conversion** — reporting-only action; not used for bidding (e.g. `begin_checkout`, `click_tel`, `click_whatsapp`) (Ch5, Ch6)

**`select_dates`** — custom GA4 event for date selection step; secondary signal (Ch5)

**Smart Bidding** — Google's auction-time signal-based bidding family (tCPA, tROAS, Max Conv, Max Conv Value) (Ch4)

**Source market** — country/region of the booker (not the destination); preferred for geo campaign construction (Ch4)

**STR (Short-Term Rental)** — apartment-style rental segment; Rome has 42,000+ STR listings on Airbnb/Vrbo (Ch2)

**Structured snippet** — ad asset showing categorised lists (e.g. Amenities: WiFi, Kitchen, Smart TV, AC) (Ch7)

**Tag Assistant** — Google tool to verify GTM/Ads/GA4 tags fire correctly live (Ch5, Ch6)

**Target CPA (tCPA)** — Smart Bidding target for CPA; second-rung in the bidding progression (Ch4)

**Target ROAS (tROAS)** — Smart Bidding target for ROAS; top-rung once real booking values flow (Ch4)

**Turismo Roma** — official Rome tourism source; reports 22.9M arrivals + 52.92M overnight stays in 2025 records (Ch2)

**`view_search_results`** — GA4 recommended event for availability/search interaction; secondary signal (Ch5)
