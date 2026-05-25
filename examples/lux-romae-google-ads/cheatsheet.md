# Cheatsheet — Lux Romae Google Ads

## The 4-Priority Architecture
1. **Brand defence Search** (immediate)
2. **High-intent non-brand Search** (immediate)
3. **Remarketing** (after audiences populate)
4. **Google Vacation Rentals / Hotel Center** (parallel, if booking engine supports)

PMax = **later** expansion layer. Display = remarketing only. Video = warm audiences only.

## Decision Tables

### When to launch what
| Channel | Launch trigger |
|---|---|
| Brand Search | Day 1 |
| Non-brand high-intent Search | Day 1 (with negatives) |
| Search remarketing | Week 5–6, after audiences populate |
| Display remarketing | After tracking is stable |
| Vacation Rentals / Hotel | Parallel — once booking engine support is confirmed |
| Performance Max | Only after offline import + clean primary conversions |
| YouTube/Video remarketing | Late phase; warm audiences only |
| Local / store-goal PMax | Avoid (wrong objective for online lodging) |

### Match-type choice
| Cluster | Match types |
|---|---|
| Brand | Exact + phrase |
| Location intent | Exact + phrase |
| Product intent | Exact + phrase |
| Policy intent | Phrase |
| Competitor interception | Phrase, very selective |

Broad → controlled experiment only after mature negatives + tracking.

### Bidding ladder
| Phase | Strategy | Trigger to climb |
|---|---|---|
| Early | Max Conversions (no target) | Sparse data |
| Controlled | Max Conv + tCPA | Volume + quality stable |
| Value-based | Max Conv Value + tROAS | Real booking values flow back (incl. offline imports) |

### Budget scenarios
| Scenario | Monthly | Search / Remarketing / PMax-Travel / Video |
|---|---|---|
| Lean validation | €600–1,200 | 70–80% / 15–25% / 0–10% / 0% |
| Controlled growth | €1,200–2,500 | 60–70% / 15–20% / 10–20% / 0% |
| Peak push | €2,500–5,000 | 45–60% / 10–15% / 20–35% / 5–10% |

### Primary vs Secondary conversions
| Action | Type |
|---|---|
| Online `purchase` | **Primary** |
| Imported offline confirmed booking | **Primary** |
| Booking request submit | Secondary (primary only as bridge) |
| `begin_checkout` | Secondary |
| `click_tel`, `click_whatsapp`, `select_dates` | Secondary |

### Language tiering
| Tier | Languages | Paid? |
|---|---|---|
| Core | EN + IT | Yes, dedicated |
| Expansion | ES, FR, DE | When justified |
| Site-only | Remaining 8 of 13 | No paid until proven |

### Geo targeting
- Default: **Presence or Interest** (travel lift)
- Build by **source market**, not "in Rome"
- Customer Match: needs EEA-grade consent

## Launch Gate Checklist (do NOT skip)

- [ ] Confirmed booking path (instant vs assisted)
- [ ] GTM + GA4 + Ads tag + Conversion Linker on **every page**
- [ ] Consent Mode v2 + compliant CMP active (EEA/UK/CH)
- [ ] Cross-subdomain (`www.` ↔ `book.`) `_gl` continuity verified
- [ ] Native Ads booking-confirm conversion created
- [ ] Offline conversion import wired
- [ ] Enhanced conversions on
- [ ] DDA on primary conversion
- [ ] Brand defence Search live
- [ ] Day-one negative list applied
- [ ] Sitelinks, callouts, snippets, call asset, location asset deployed
- [ ] Vacation Rentals / Hotel Center feasibility checked with booking engine

## Day-One Negative Starter
`long term, monthly rent, lease, real estate, for sale, roommate, shared room, student housing, hostel job, cleaning jobs, property management jobs, office rent, commercial rent`

## First-Screen Landing-Page Test (<3s)
1. Where is it?
2. How many guests?
3. Why book direct?
4. Check dates now?
5. Cancellation policy?

## Vacation Rentals Eligibility Quick Rules
- ≥8 images recommended; **<5 = blocked**
- Structured data required
- Accurate price + availability
- Direct website link required
- Small inventory → crawled listing feed OK

## Anti-Patterns (do not do)
- 13 equal-language paid campaigns
- PMax on day 1 with thin data
- Optimising to phone/WhatsApp clicks as primary
- Broad match before negatives + tracking mature
- "In Rome" geo only (kills inbound bookers)
- Ad-language mismatch with landing-page language
- Loading ads tags before consent in EEA
- Daily-only dashboard (no offline-import view)
- Changing attribution without retuning tCPA/tROAS
- Submitting <5 images to Vacation Rentals
- Machine-translated cancellation wording

## KPIs to Watch
| Daily | Weekly | Monthly |
|---|---|---|
| Spend, clicks, CTR, CPC, impression share | Search terms + negatives, LP friction, confirmed bookings (incl. offline), CPA/ROAS, language segmentation | Cancellation-adjusted CPA, no-show-adjusted ROAS, assisted close rate, CLTV check |

## Six Open Questions (resolve before scaling)
1. Booking engine: instant vs assisted?
2. Current GTM/GA4/Ads/CMP status?
3. Historical performance by country/language/device/season?
4. Avg booking value, length of stay, margin, cancellation rate, OTA commission avoided?
5. Vacation Rentals / Hotel Center support via booking partner?
6. Share of paid traffic closing via phone/WhatsApp/email?

## Operating Mantras
- **Pin the demand you already have, then expand.**
- **If it doesn't come back, it didn't happen — for Smart Bidding.**
- **Loosen targets before peaks, not during them.**
- **Localise; don't translate.**
- **Verify, don't assume** (Tag Assistant before media).
- **Experiments > setting changes.**
