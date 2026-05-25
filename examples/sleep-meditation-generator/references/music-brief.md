# Music Brief Template

Use this verbatim, filling in the bracketed fields for the chosen style.

---

```
MUSIC BRIEF — [Track Title]
Duration: [N] minutes (voice) + 30–60s tail fade
Style: [clinical-hypnotic | mindfulness | yoga-nidra-lite | lullaby]

[Function statement]
The music's role is to create physiological permission, not emotional drama.
It should make breath easier and remove the listener's need to listen actively.

[Tempo / pulse]
- No obvious beat OR a very soft pulse around 50–65 BPM
- Avoid rhythmic insistence — never percussive
- A hidden slow amplitude movement around calm breathing (~6–8 breaths/min) is effective if subtle

[Harmony]
- Stable, slow-changing, consonant
- No sudden modulations
- No tension–release drama
- No bright major climax, no melancholic sadness
- Suggested: sustained tonic with one neighbour chord, returning home softly

[Melody]
- Sparse, descending, narrow range (perfect 4th or 5th maximum)
- Ideally NO memorable hook (a hook keeps the mind engaged)
- If a melodic motif appears, it should not resolve in a satisfying way; it should dissolve

[Timbre]
- Warm pads
- Felt piano (soft hammers, slightly muted)
- Low strings (cellos, double bass with bow, no pizzicato)
- Soft choir-like textures, hummed not sung
- Distant rain, low wind, gentle room tone — natural and low-novelty
- Avoid: bright bells, gongs, cymbals, hand drums, plucked harps with sustain

[Frequency balance]
- Reduce harsh 2–5 kHz presence
- Keep low end soft — no rumble, no sub bass swells
- Remove clicks, plosives, sharp transients
- Roll off everything above ~10 kHz gently (helps with earbud comfort)

[Dynamics]
- Very small changes only
- No drops, no risers, no cymbal swells, no sudden entrances
- No emotional peaks
- Crescendo over many seconds; never a fast build
- Integrated loudness LOWER than normal spoken content (listener may be in bed with earbuds)

[Voice/Music mix]
- Voice clearly above music at first
- Music gradually takes over toward the final 25–30% of the track
- Music carries the last 30–60s alone — voice has stopped
- Voice: intimate, slow, non-commanding, close mic, warm low end, no harsh sibilance

[Duration handling]
- Voice portion: [N] minutes
- Music tail: 30–60 seconds of slow fade
- Optional looped extension: 5–15 minutes of pure music after the fade for users who want to keep playing
```

---

## Style Variants

### clinical-hypnotic (default for sleep tracks)
- **Timbre lean**: warm pad + felt piano
- **Melodic content**: very sparse, descending phrases that don't resolve
- **Movement**: slow harmonic drift, never accelerating
- **Mood**: held, contained, not searching

### mindfulness
- **Timbre lean**: minimal drone + distant rain
- **Melodic content**: essentially none
- **Movement**: almost static — only subtle amplitude breathing
- **Mood**: spacious, present, unattached

### yoga-nidra-lite
- **Timbre lean**: low strings + soft hummed choir
- **Melodic content**: long sustained chords, slow harmonic walking
- **Movement**: sustained chords with gradual voice-leading
- **Mood**: enveloping, full, womb-like

### lullaby
- **Timbre lean**: felt piano + low room tone, perhaps a soft music-box muted timbre
- **Melodic content**: narrow descending motif, lullaby-like but not a hook
- **Movement**: rocking-cradle gentle 4/4 at very slow tempo, or rubato
- **Mood**: domestic, warm, familiar, safe

---

## Things to Reject in a Music Brief

If the user requests these, push back:

- "432 Hz / solfeggio / healing frequencies" → no evidence; remove the framing
- "Binaural beats to entrain delta waves" → no robust evidence base for sleep; reject the health claim, can offer ambient panning if they want spatial interest
- "Subliminal affirmations" → ethically and policy-problematic
- "ASMR triggers" → wrong modality; ASMR creates micro-arousal, opposite goal
- "Brown noise to cure insomnia" → no cure claims; noise floor is fine if soft and low
- "EDM-tempo chill version" → wrong tempo class; rejected
- "Dramatic build to a climax" → opposite of the production goal

---

## Final Mix Spec

| Parameter | Target |
|---|---|
| Integrated loudness (LUFS) | −20 to −24 LUFS (lower than typical −16 LUFS podcast) |
| True peak | ≤ −3 dBTP |
| Voice ducking | Soft — voice ~6 dB above bed |
| Voice EQ | High-pass at 80–100 Hz; gentle de-ess; warm low-mids |
| Music EQ | Reduce 2–5 kHz; gentle low shelf below 100 Hz |
| Stereo image | Music wider than voice; voice centered, narrow |
| Fade in | 4–8 sec (slow) |
| Fade out | 15–30 sec (slow) |
| Export format | WAV master (24-bit / 48 kHz) + MP3 192 kbps for streaming |
