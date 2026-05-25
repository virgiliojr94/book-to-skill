---
name: sleep-meditation-generator
description: "Generates complete sleep-meditation audio track packages — voiceover script (timed, with pause markers), music brief, production checklist, and safe-use published description — for insomnia-supportive use. Outputs are non-medical, non-coercive, evidence-aligned with CBT-I, AASM, NICE, and European Insomnia Guideline framing. Use when the user asks for a meditation script, sleep audio, insonnia/relaxation track, lyrics for meditation music, or a music brief for ambient sleep audio."
allowed-tools:
  - Read
  - Write
  - Grep
argument-hint: [duration_min] [language] [style] [metaphor]
---

# Sleep Meditation Generator

Generates a **complete, ready-to-record sleep meditation track package** for an insomnia-supportive use case.

## What You Produce (every invocation)

A single Markdown document containing **four sections**:

1. **Script** — timed voiceover with `[pause N sec]` markers; word count matched to target duration (85–95 wpm)
2. **Music brief** — tempo, harmony, melody, timbre, dynamics, mix, duration
3. **Producer checklist** — recording, mixing, export, A/B test pairing
4. **Published description copy** — safe-use note, non-medical framing, clinical referral line

If the user wants only one of these (e.g. "just the script"), produce only that — but include the safe-use note at the bottom regardless.

---

## Non-Negotiable Principles (cite these in your generation, don't violate)

These come directly from the source guide and reflect AASM / NICE / European Insomnia Guideline / Cochrane positions. **If the user asks for output that violates them, push back briefly and reframe.**

1. **Do not claim to cure insomnia.** Frame as "supports relaxation and sleep readiness." CBT-I is first-line. This audio is **adjunctive**.
2. **Reduce arousal, not consciousness.** Don't force sleep. Soften muscle tone, breath, threat monitoring, mental rehearsal.
3. **Permissive hypnosis, never commands.** Use "you may", "perhaps", "as if", "there is no need". Never "sleep now", "you must sleep", "go deeper immediately".
4. **One emotional promise: safety.** Not magic, not depth, not control. Safety.
5. **No cognitive activation.** No complex stories, no problem-solving, no counting-as-task, no vivid adventure, no emotionally charged memories, no alertness checks, no awakening language.
6. **One central metaphor per track.** Don't change scene.
7. **Sensory imagery only, slow and low-contrast.** Warm room, dim light, quiet shore, soft forest at dusk — never narrative.
8. **Long pauses, written as `[pause N sec]`.** A 4-min script is a *score*, not a paragraph.
9. **No subliminal claims, no brainwave/binaural pseudo-science**, no medication advice, no diagnostic claims.
10. **Always include a clinical-referral line** in the published description: persistent insomnia, severe distress, trauma activation, breathing disorders, or medication issues → qualified clinician.

---

## Generation Protocol

### Step 1 — Resolve parameters

Accept positional args **or ask** if missing. Defaults in **bold**.

| Parameter | Values | Default |
|---|---|---|
| `duration_min` | 3, 4, 6, 8, 10 | **4** |
| `language` | en, it, es, fr | **en** |
| `style` | clinical-hypnotic, mindfulness, yoga-nidra-lite, lullaby | **clinical-hypnotic** |
| `metaphor` | warm-room, quiet-shore, soft-forest, night-meadow, candle-room, custom string | **warm-room** |
| `voice` | masc, fem, neutral (informs phrasing, not gender claims) | **neutral** |

If the user gives a vague brief ("make me one for tonight"), pick the defaults and proceed — don't stall.

### Step 2 — Pull the timing blueprint

Read `references/blueprints.md` for the section split matching `duration_min`. Each blueprint specifies seconds per section and the section's function.

**Word budget rule**: target 85–95 wpm of spoken time **minus** pause time. For a 4-min track with ~60s of pauses, that's ~180–270 spoken words. Stay in this band.

### Step 3 — Build the script

For each section in the blueprint:

1. Pick 1–3 phrases from `references/phrase-bank-<lang>.md` for that section's function
2. Bind them to the chosen `metaphor` (load `references/metaphors.md` for the metaphor's sensory anchors)
3. Insert `[pause N sec]` per the blueprint
4. Keep clauses **short**, vocabulary **low-cognitive-load**, repetition **welcome**

**Hard constraints in the script**:
- Never command, always permit
- No second-person plural; use second-person singular softly
- No awakening language at the end (this is a sleep track)
- One metaphor only, sustained
- The last 30–60s leaves music to carry the fade — don't fill it with words

### Step 4 — Build the music brief

Use `references/music-brief.md` as the template. Adjust for `style`:
- **clinical-hypnotic** → warm pad + felt piano, very slow, descending
- **mindfulness** → minimal drone + distant rain, no melody
- **yoga-nidra-lite** → low strings + soft choir, sustained chords
- **lullaby** → felt piano + low room tone, narrow descending melody

All styles share: no obvious beat (or ≤65 BPM), consonant slow harmony, no dynamic peaks, no climax, reduced 2–5 kHz presence, soft low end.

### Step 5 — Build the producer checklist

Use the checklist from `references/producer-checklist.md` as-is. Add any duration-specific notes (e.g. 8-min and 10-min tracks need a longer-loop variant for sustained listening).

### Step 6 — Build the published description

Use `references/safety-copy.md` boilerplate in the requested language. **Always include** the clinical-referral line. Use calm titles like "Sleep Meditation", "Night Reset", "Deep Rest Audio" — never "Cure for Insomnia".

### Step 7 — Assemble and deliver

Output one Markdown document with all four sections, plus a one-line header listing the chosen parameters so the user can iterate.

---

## When the User Asks for Something Out of Scope

| Request | Response |
|---|---|
| "Make it cure insomnia" | Generate the track, but reframe in description: "supports relaxation and sleep readiness." Tell the user briefly why, citing CBT-I as first-line. |
| "Add binaural beats / specific Hz to heal" | Decline the pseudo-science framing. Offer the same track without health claims about frequencies. |
| "Tell them to stop their sleep medication" | Refuse. Reword to "speak with a qualified clinician about persistent insomnia." |
| "Use subliminal messages" | Refuse. Subliminal claims violate principle 9. |
| "Make it 20 minutes with adventure imagery" | Refuse the adventure imagery (principle 5). Offer the longer duration with slow sustained imagery instead. |
| "I have trauma / panic at night" | Generate the track but soften further (no body-scan that activates threat monitoring), and add a stronger referral note. |
| "Make a track for a child under 12" | Generate a shorter (3-min), softer lullaby-style track; add a parent-supervision note. |

---

## Iteration Commands the User May Use

- `tweak: shorter` → drop one section, redistribute time
- `tweak: more permissive` → strip any residual imperative; add more "perhaps", "you may"
- `tweak: change metaphor to X` → keep structure, swap sensory anchors via `references/metaphors.md`
- `tweak: translate to <lang>` → switch phrase bank; preserve timing and `[pause]` markers
- `tweak: music only` → output only the music brief
- `tweak: A/B variant` → produce a second version differing on one variable (e.g. voice-only vs. voice+music-bed; metaphor A vs. metaphor B); document the variable for testing

---

## Reference Files

- [references/principles.md](references/principles.md) — full clinical / ethical guardrails with source citations
- [references/blueprints.md](references/blueprints.md) — timing blueprints for 3, 4, 6, 8, 10 min tracks
- [references/phrase-bank-en.md](references/phrase-bank-en.md) — English permissive phrases by section
- [references/phrase-bank-it.md](references/phrase-bank-it.md) — Italian permissive phrases by section
- [references/metaphors.md](references/metaphors.md) — sensory anchors per central metaphor
- [references/music-brief.md](references/music-brief.md) — music brief template + style variants
- [references/producer-checklist.md](references/producer-checklist.md) — recording, mix, export, A/B test
- [references/safety-copy.md](references/safety-copy.md) — published-description boilerplate (EN/IT/ES/FR)
- [examples/4min-en-warm-room.md](examples/4min-en-warm-room.md) — canonical example from the source guide

---

## Sources Behind This Skill

- European Insomnia Guideline update 2023
- NICE CKS — Managing insomnia
- AASM clinical practice guideline — behavioral & psychological treatments for chronic insomnia
- Accademia Italiana di Medicina del Sonno — Linee guida insonnia
- Cochrane Review — Listening to music for insomnia in adults
- Hypnosis intervention effects on sleep outcomes — systematic review (PMC5786848)
- Hypnotherapy for insomnia — systematic review (PMID 26365453)
- Engineering music to slow breathing — arXiv 1907.08844
- Digital CBT-I trial (Sleepio, SLEEP 2012)

---

## Scope & Limits

This skill produces **audio production artifacts**, not medical content. It is built to:
- Generate compliant sleep-meditation scripts and music briefs
- Refuse pseudo-science (binaural healing claims, subliminal content)
- Refuse medical claims (cure, treatment, medication advice)
- Always include a clinical-referral pathway

It is **not**:
- A diagnostic tool
- A replacement for CBT-I or clinical sleep medicine
- A substitute for emergency care when severe distress is present
