# Dark Trap Beat

Dark minor-themed trap beat generated with Python (music21, DawDreamer, pedalboard).

## Beat Config

| Parameter | Value |
|-----------|-------|
| **Key** | C minor |
| **BPM** | 152 |
| **Length** | 64 bars (~1:43) |
| **Chord Progression** | i → iv → VI → V (Cm → Fm → Ab → G) |

## Sound Layers

| Layer | Source | Notes |
|-------|--------|-------|
| **Drums** | Obie trap kit (WAV samples) | Sparse kick (beat 1), layered clap+snare (beats 2/4), 1/16th + 1/32nd hi-hat rolls |
| **808 Bass** | Obie 808 sample, pitch-shifted per chord | Bounce pattern with ghost notes, sidechained under kick |
| **Dark Pad** | FAUST synth (5x detuned sawtooth) | Low cutoff 200-800Hz, slow LFO, heavy reverb |
| **Dark Bell Lead** | FAUST FM synth | Sine + FM modulation, fast attack, sparse melody (1-2 notes/bar) |

## Drum Samples

All from `Obie - ALL GENRE KIT PT 2 / MODERN TRAP/`:
- Kick: `Kick @el.obie 49.wav`
- Snare: `Snare @el.obie 53.wav`
- Clap: `Clap @el.obie 26.wav`
- Closed HH: `HH @el.obie 13.wav`
- Open HH: `OH @el.obie 11.wav`
- 808: `808 @el.obie 37.wav`
- Perc: `PERCS @el.obie 46.wav`
- Crash: `LOLL @el.obie 1.wav`

## Arrangement

| Section | Bars | Description |
|---------|------|-------------|
| Intro | 0-7 | Dark pad + sparse lead, no drums |
| Hook A | 8-23 | Full arrangement, hi-hat rolls |
| Verse | 24-39 | Stripped drums (8th note hats), minimal lead |
| Bridge | 40-47 | Half-time feel, held lead notes |
| Hook B | 48-63 | Full arrangement reprise |

## Mix Levels

| Stem | Level | Processing |
|------|-------|------------|
| Drums | 0.90 | Compressor → gain → limiter, 6% room verb |
| 808 | 0.92 | HPF 30Hz, LPF 300Hz, distortion, compressor |
| Pad | 0.58 | HPF 80Hz, LPF 8kHz, reverb (room 0.85), stereo widen 20ms |
| Lead | 0.30 | HPF 150Hz, LPF 8kHz, reverb (room 0.80, wet 0.40), stereo widen 18ms |
| FX | 0.50 | Snare rolls, reverse tails, crash hits |

## How to Run

```bash
# 1. Compose MIDI
python compose_flute_trap.py

# 2. Render audio
python render_flute_trap.py
```

### Dependencies
- music21, mido, numpy, scipy, soundfile, pydub
- pedalboard, dawdreamer, pyroomacoustics
