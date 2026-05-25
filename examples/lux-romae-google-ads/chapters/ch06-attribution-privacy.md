# Chapter 6: Attribution & Privacy (GDPR / Consent Mode v2)

## Core Idea
Use **data-driven attribution (DDA)** for the primary booking conversion, govern conversions strictly, and treat **Consent Mode v2** as non-optional for EEA/UK/CH traffic. Privacy is not an add-on — it's the precondition for measurement and remarketing.

## Frameworks Introduced

### Attribution Default: Data-Driven (DDA)
- DDA is Google's default for most conversion actions
- Distributes credit using account data across Search, YouTube, Display, Demand Gen, and other Google paid touchpoints
- All conversion actions are eligible; **stronger models** with more data — Google's reference: ~**200 conversions** and **2,000 ad interactions** in supported networks over 30 days
- For Lux Romae: apply DDA to the primary booking conversion unless there's a compelling counter-reason

### Conversion Governance Table

| Conversion action | Primary/Secondary | Attribution model | Used for bidding |
|---|---|---|---|
| **Online confirmed booking** | Primary | Data-driven | Yes |
| **Confirmed offline booking** (from request or call) | Primary | Data-driven if in Ads; otherwise imported and used for bidding | Yes |
| **Booking request submit** | Secondary at first, primary only if no confirmation action exists yet | Data-driven | Only temporarily if needed |
| **Begin checkout** | Secondary | Data-driven | No |
| **Phone click, WhatsApp click** | Secondary | DDA or Analytics reporting only | No |

**Critical**: shallow events (phone click, casual date checks) must **not** steer bidding.

### Attribution-Change Side Effect
Changing attribution model alters credit distribution across campaigns → re-tune tCPA / tROAS targets at the same time. Don't change model and bidding target separately.

### Consent Mode v2 (EEA/UK/CH non-negotiable)
- Google tags measuring behaviour in Europe **must pass end-user consent choices** to Google
- v2 adds two signals: **`ad_user_data`** and **`ad_personalization`**
- To keep measurement, ad personalisation, and remarketing features → **collect consent AND share consent signals appropriately**
- Without consent signals, ads/remarketing/measurement features degrade

### EU + Italian Regulatory Baseline
- **GDPR (EU Commission)**: lawful bases of processing apply; consent is one lawful basis but specific to context
- **Italian Garante cookie guidance**: profiling cookies create user profiles → require **appropriate information + valid consent**
- Operational stance for Lux Romae:
  1. Run a **compliant CMP** (Consent Management Platform)
  2. **Activate Consent Mode v2**
  3. **Avoid loading advertising / remarketing tags before the user's choice** (the preferred approach for profiling tools)

> This is operational guidance, **not legal advice**. The correct direction of travel; specific implementation should be validated by counsel for the actual jurisdictions served.

### Verification Caveat (the public crawl evidence)
A text crawl of current public Lux Romae pages did not expose `gtag`, `googletagmanager`, or cookie-related strings. **This is not proof of absence** — only of non-visibility in that crawl. **Validate with Tag Assistant + browser inspection** before media launch.

## Key Concepts

- **Data-Driven Attribution (DDA)**: model that distributes credit across touchpoints using account data; Google default
- **Consent Mode v2**: Google's framework for passing consent state via tag parameters, including `ad_storage`, `analytics_storage`, `ad_user_data`, `ad_personalization`
- **CMP (Consent Management Platform)**: UI + storage layer that collects user consent and feeds it to tags
- **Profiling cookie**: cookie used to construct a user profile for advertising/personalisation → high consent bar
- **Lawful basis (GDPR)**: legal ground for processing personal data (consent, contract, legitimate interest, legal obligation, vital interests, public task)

## Mental Models

- **"Attribution change ↔ bidding target change."** Always retune Smart Bidding when you switch models.
- **"Consent is upstream of measurement."** Without compliant consent flow, measurement is degraded — not just legally risky.
- **"Public-crawl absence is not implementation absence."** Verify with the right tools before assuming the site has no tags.

## Anti-patterns

- **Changing attribution model without retuning tCPA/tROAS** → bid targets become misaligned with new credit distribution
- **Letting phone-click stay primary** because volumes look nice → bidding optimises for low-funnel actions, not bookings
- **Loading ads/remarketing tags before consent in EEA** → regulatory + signal-quality risk
- **Assuming Consent Mode "default deny" without consent signalling** is enough → modelled conversions and remarketing features still degrade
- **Trusting a public site crawl** to confirm absence of GTM / CMP — verify with Tag Assistant

## Key Takeaways

1. **DDA on the primary booking conversion**, with offline-imported bookings included.
2. **Booking request submit stays secondary** unless no confirmation action exists; promote only as a bridge.
3. **Phone / WhatsApp clicks are reporting signals**, never bidding signals.
4. **Consent Mode v2 + a compliant CMP** are launch prerequisites for EEA/UK/CH traffic.
5. **Don't load profiling tags before the user's choice** (preferred approach).
6. **Validate live tag and CMP status** with Tag Assistant before media starts.
7. **Whenever attribution changes, recalibrate Smart Bidding targets** in the same change window.

## Connects To
- **Ch 5**: enhanced conversions + offline import work alongside DDA + consent-mode signal sharing
- **Ch 4**: Customer Match in EEA contexts depends on the consent-signal layer here
- **Ch 7**: language/landing strategy must include language-appropriate consent UI
- **Ch 8**: Foundation phase (weeks 1–2) installs CMP + Consent Mode v2 before any media launch
