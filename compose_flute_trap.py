"""
Dark Trap Beat v3
Key: C minor | BPM: 152 | 64 bars (~1:41)

Research: YouTube tutorials S4CdACq0TuI, 0Eg0wWvm3mM, KGC3tlF1ygE
  - Layer piano + pad + lead for richness
  - Sus2/sus4 chords, inversions with common notes
  - Half-step tension (C→B, Eb→D) in melody
  - Fast hats (1/32) in hooks, 808 bounce
  - Melody quiet and lowkey (vel 38-50)

Chord Progression (4-bar loop, C minor — i→iv→VI→V):
  Bar 0: Cm(sus4)  (C3, F3, G3)   — i sus4, tension
  Bar 1: Fm        (C3, F3, Ab3)  — iv, inversion sharing C3
  Bar 2: Ab        (Ab2, C3, Eb3) — VI, dark
  Bar 3: G         (G2, B2, D3)   — V, resolve

5 Sound Layers:
  1. Drums     — kick, layered snare+clap, 1/32 hi-hats (hooks), crash
  2. 808 bass  — bounce pattern, pitched to roots
  3. Pad       — FAUST synth, sustained chords
  4. Piano     — arpeggiated chord tones
  5. Lead      — FAUST FM bell, quiet repetitive motif

Song Structure:
  Intro     bars  0– 7: Pad + sparse piano
  Hook A    bars  8–23: Full arrangement
  Verse     bars 24–39: Stripped drums + 808 + minimal lead
  Bridge    bars 40–47: Pad + held notes, half-time drums
  Hook B    bars 48–63: Full again
"""

import os
import random
import numpy as np
from music21 import stream, note, chord, tempo, meter
from mido import MidiFile, Message

random.seed(42)

OUTPUT_DIR = '/Users/ronantakizawa/Documents/FluteTrap_Beat'
os.makedirs(OUTPUT_DIR, exist_ok=True)

BPM = 152
BPB = 4   # beats per bar

# Section boundaries (0-indexed bars)
INTRO_S,   INTRO_E   =  0,  8
HOOKA_S,   HOOKA_E   =  8, 24
VERSE_S,   VERSE_E   = 24, 40
BRIDGE_S,  BRIDGE_E  = 40, 48
HOOKB_S,   HOOKB_E   = 48, 64


def bb(bar, beat=0.0):
    """Absolute offset from bar (0-indexed) + beat (0-indexed)."""
    return float(bar * BPB + beat)


# ─── Chord tables ─────────────────────────────────────────────────────────────
# i(sus4)→iv(inv)→VI→V in C minor
# Inversions chosen so adjacent chords share a common note (C3)
CHORDS = [
    ['C3', 'F3',  'G3' ],   # 0: Cm sus4 (tension)
    ['C3', 'F3',  'A-3'],   # 1: Fm 2nd inversion (shares C3, F3)
    ['A-2', 'C3', 'E-3'],   # 2: Ab root position (shares C3)
    ['G2', 'B2',  'D3' ],   # 3: G (resolve)
]
CHORDS_LOW = [
    ['C2', 'F2',  'G2' ],
    ['C2', 'F2',  'A-2'],
    ['A-1', 'C2', 'E-2'],
    ['G1', 'B1',  'D2' ],
]
BASS_ROOTS = ['C2', 'F1', 'A-1', 'G1']

# Piano arpeggiation patterns (indices into chord tones, with octave bumps)
# Each tuple: (chord_tone_index, octave_shift, duration)
PIANO_ARP_HOOK = [
    (0, 0, 1.0), (2, 0, 1.0), (1, 0, 1.0), (2, 1, 1.0),  # root-5th-3rd-5th(up)
]
PIANO_ARP_INTRO = [
    (0, 0, 2.0), (1, 0, 2.0),  # slower, just root-3rd
]


# ─── Lead melody tables ──────────────────────────────────────────────────────
# MELODY TIMBRE RULE: quiet (vel 38-50), repetitive 2-bar motif,
# half-step tension (C→B, Eb→D). Never raise above vel 50.

# Hook: repetitive 2-bar motif, repeated over 4-bar chord cycle
LEAD_HOOK = [
    # Bar 0 (Cm): C4 → B3 (half-step down = tension)
    [('C4', 1.5), ('B3', 0.5), (None, 2.0)],
    # Bar 1 (Fm): rest → Ab3
    [(None, 2.0), ('A-3', 2.0)],
    # Bar 2 (Ab): Eb4 → D4 (half-step tension)
    [('E-4', 1.5), ('D4', 0.5), (None, 2.0)],
    # Bar 3 (G): rest
    [(None, 4.0)],
]

# Verse: 1 note every 2 bars (sparse)
LEAD_VERSE = [
    [(None, 4.0)],
    [('C4', 4.0)],
    [(None, 4.0)],
    [(None, 4.0)],
]

# Intro: silence (piano carries it)
LEAD_INTRO = [
    [(None, 4.0)],
    [(None, 4.0)],
    [(None, 4.0)],
    [(None, 4.0)],
]

# Bridge: held single notes
LEAD_BRIDGE = [
    [('G3', 4.0)],
    [(None, 4.0)],
    [('A-3', 4.0)],
    [(None, 4.0)],
]


# ─── DRUMS ────────────────────────────────────────────────────────────────────
# Juicy Jules Stardust kit (rendered in render script)
# GM mapping: 36=kick  38=snare  39=clap  42=closed-HH  46=open-HH  49=crash
def create_drums():
    part = stream.Part()
    part.partName = 'Drums'
    part.insert(0, tempo.MetronomeMark(number=BPM))
    part.insert(0, meter.TimeSignature('4/4'))

    def hit(offset, note_num, vel=90):
        n = note.Note(note_num, quarterLength=0.25)
        n.volume.velocity = min(127, max(1, int(vel)))
        part.insert(offset, n)

    def trap_bar(bar, fast_hats=True, half_time=False, crash=False):
        """One bar of trap drums. Tutorial: snare first, then fast hats."""
        o = bb(bar)

        # Kick: beat 0 (sparse trap)
        hit(o + 0.0, 36, 100)
        # Ghost kick on beat 2.5 every 4 bars
        if bar % 4 == 3:
            hit(o + 2.5, 36, 55)

        if half_time:
            # Bridge: clap on beat 3 only
            hit(o + 3.0, 39, 88)
        else:
            # Layered clap + snare on beats 1 and 3 (tutorial: snare first)
            hit(o + 1.0, 38, 86)
            hit(o + 1.0, 39, 82)
            hit(o + 3.0, 38, 90)
            hit(o + 3.0, 39, 86)

        # Hi-hats
        if fast_hats:
            # 1/32 notes in hooks (16 hits per bar = every 0.25 beats)
            # Tutorial: "every 2 steps = 1/32 notes"
            for i in range(16):
                vel = 55 if i % 4 == 0 else (40 if i % 2 == 0 else 28)
                hit(o + i * 0.25, 42, vel)
        else:
            # Verse/bridge: quarter notes, low velocity
            for i in range(4):
                hit(o + i * 1.0, 42, 32)

        # Crash on beat 0
        if crash:
            hit(o + 0.0, 49, 82)

    # Intro: no drums (bars 0-7)

    # Snare roll build into Hook A (bar 7)
    o = bb(7)
    for h in range(8):
        hit(o + h * 0.5, 38, 64 + h * 5)
    hit(o + 3.5, 49, 80)   # crash into hook

    # Hook A (bars 8-23): full trap with 1/32 hats
    for bar in range(HOOKA_S, HOOKA_E):
        idx = bar - HOOKA_S
        trap_bar(bar, fast_hats=True, crash=(idx % 8 == 0))

    # Verse (bars 24-39): simpler hats
    for bar in range(VERSE_S, VERSE_E):
        idx = bar - VERSE_S
        trap_bar(bar, fast_hats=False, crash=(idx % 8 == 0))

    # Bridge (bars 40-47): half-time feel
    for bar in range(BRIDGE_S, BRIDGE_E):
        idx = bar - BRIDGE_S
        trap_bar(bar, fast_hats=False, half_time=True, crash=(idx == 0))

    # Hook B (bars 48-63): full trap with 1/32 hats
    for bar in range(HOOKB_S, HOOKB_E):
        idx = bar - HOOKB_S
        trap_bar(bar, fast_hats=True, crash=(idx % 8 == 0))

    return part


# ─── 808 BASS ────────────────────────────────────────────────────────────────
def create_808():
    """808 with bounce pattern: hit beat 1, ghost beat 2.5, tail beat 3.5."""
    part = stream.Part()
    part.partName = '808 Bass'
    part.insert(0, tempo.MetronomeMark(number=BPM))

    def bass_bar(bar, vel=90, ghost=True, tail=False):
        o    = bb(bar)
        root = BASS_ROOTS[bar % 4]
        # Main hit: 2.5 beats
        n1 = note.Note(root, quarterLength=2.5)
        n1.volume.velocity = vel
        part.insert(o, n1)
        # Bounce ghost at beat 2.5
        if ghost:
            n2 = note.Note(root, quarterLength=0.75)
            n2.volume.velocity = int(vel * 0.35)
            part.insert(o + 2.5, n2)
        # Tail hit at beat 3.5 every other bar
        if tail:
            n3 = note.Note(root, quarterLength=0.25)
            n3.volume.velocity = int(vel * 0.25)
            part.insert(o + 3.5, n3)

    # Hook A
    for bar in range(HOOKA_S, HOOKA_E):
        bass_bar(bar, vel=92, ghost=True, tail=(bar % 2 == 1))

    # Verse
    for bar in range(VERSE_S, VERSE_E):
        bass_bar(bar, vel=84, ghost=True, tail=False)

    # Bridge: sparser, just main hit
    for bar in range(BRIDGE_S, BRIDGE_E):
        bass_bar(bar, vel=76, ghost=False, tail=False)

    # Hook B
    for bar in range(HOOKB_S, HOOKB_E):
        bass_bar(bar, vel=94, ghost=True, tail=(bar % 2 == 1))

    return part


# ─── PAD / CHORDS ─────────────────────────────────────────────────────────────
def create_chords():
    part = stream.Part()
    part.partName = 'Chords Pad'
    part.insert(0, tempo.MetronomeMark(number=BPM))

    def pad(bar, vel=52, low=False):
        c_list = CHORDS_LOW[bar % 4] if low else CHORDS[bar % 4]
        c = chord.Chord(c_list, quarterLength=4.0)
        c.volume.velocity = vel
        part.insert(bb(bar), c)

    # Intro: light pad, low octave (from bar 0 — no silent intro)
    for bar in range(INTRO_S, INTRO_E):    pad(bar, vel=38, low=True)
    # Hook A
    for bar in range(HOOKA_S, HOOKA_E):    pad(bar, vel=55)
    # Verse
    for bar in range(VERSE_S, VERSE_E):    pad(bar, vel=48)
    # Bridge
    for bar in range(BRIDGE_S, BRIDGE_E):  pad(bar, vel=60)
    # Hook B
    for bar in range(HOOKB_S, HOOKB_E):    pad(bar, vel=55)

    return part


# ─── PIANO (arpeggiated chords) ──────────────────────────────────────────────
def create_piano():
    """Piano arpeggiates chord tones for richness (tutorial: layer piano+pad+lead)."""
    part = stream.Part()
    part.partName = 'Piano'
    part.insert(0, tempo.MetronomeMark(number=BPM))

    def arp_bar(bar, pattern, vel=55):
        o = bb(bar)
        chord_tones = CHORDS[bar % 4]
        beat = 0.0
        for tone_idx, oct_shift, dur in pattern:
            idx = min(tone_idx, len(chord_tones) - 1)
            pitch_str = chord_tones[idx]
            # Apply octave shift
            if oct_shift != 0:
                n_obj = note.Note(pitch_str)
                n_obj.octave += oct_shift
                pitch_str = n_obj.nameWithOctave
            nd = note.Note(pitch_str, quarterLength=dur)
            nd.volume.velocity = int(np.clip(vel + random.randint(-3, 3), 1, 127))
            part.insert(o + beat, nd)
            beat += dur

    # Intro: slow arp (bars 0-7)
    for bar in range(INTRO_S, INTRO_E):
        arp_bar(bar, PIANO_ARP_INTRO, vel=42)

    # Hook A: full arp
    for bar in range(HOOKA_S, HOOKA_E):
        arp_bar(bar, PIANO_ARP_HOOK, vel=52)

    # Verse: slow arp
    for bar in range(VERSE_S, VERSE_E):
        arp_bar(bar, PIANO_ARP_INTRO, vel=40)

    # Bridge: single note per bar
    for bar in range(BRIDGE_S, BRIDGE_E):
        chord_tones = CHORDS[bar % 4]
        nd = note.Note(chord_tones[0], quarterLength=4.0)
        nd.volume.velocity = 38
        part.insert(bb(bar), nd)

    # Hook B: full arp
    for bar in range(HOOKB_S, HOOKB_E):
        arp_bar(bar, PIANO_ARP_HOOK, vel=52)

    return part


# ─── DARK BELL LEAD ──────────────────────────────────────────────────────────
def create_lead():
    """Dark bell lead — rendered via FAUST FM synth in the render script.
    MELODY TIMBRE RULE: sine+FM bell, vel 38-50, never louder than drums/bass.
    Half-step tension: C→B, Eb→D. Repetitive 2-bar motif."""
    part = stream.Part()
    part.partName = 'Dark Lead'
    part.insert(0, tempo.MetronomeMark(number=BPM))

    def write_phrase(phrase, start_bar, vel=44):
        for bar_off, motif in enumerate(phrase):
            o    = bb(start_bar + bar_off)
            beat = 0.0
            for pitch, dur in motif:
                if pitch is None:
                    part.insert(o + beat, note.Rest(quarterLength=dur))
                else:
                    nd = note.Note(pitch, quarterLength=dur)
                    nd.volume.velocity = int(np.clip(vel + random.randint(-3, 3), 1, 50))
                    part.insert(o + beat, nd)
                beat += dur

    # Intro: no lead (piano carries it)
    write_phrase(LEAD_INTRO, 0, vel=0)
    write_phrase(LEAD_INTRO, 4, vel=0)

    # Hook A: dark melody (bars 8-23, 4x)
    for cycle in range(HOOKA_S, HOOKA_E, 4):
        write_phrase(LEAD_HOOK, cycle, vel=random.randint(42, 48))

    # Verse: minimal (bars 24-39, 4x)
    for cycle in range(VERSE_S, VERSE_E, 4):
        write_phrase(LEAD_VERSE, cycle, vel=random.randint(38, 44))

    # Bridge: held notes (bars 40-47, 2x)
    write_phrase(LEAD_BRIDGE, 40, vel=40)
    write_phrase(LEAD_BRIDGE, 44, vel=40)

    # Hook B: dark melody (bars 48-63, 4x)
    for cycle in range(HOOKB_S, HOOKB_E, 4):
        write_phrase(LEAD_HOOK, cycle, vel=random.randint(42, 48))

    return part


# ─── MIDI HELPERS ─────────────────────────────────────────────────────────────
def insert_program(track, program):
    pos = 0
    for j, msg in enumerate(track):
        if msg.type == 'track_name':
            pos = j + 1
            break
    track.insert(pos, Message('program_change', program=program, time=0))


def fix_instruments(mid, part_names):
    for i, track in enumerate(mid.tracks):
        if i == 0:
            continue
        pidx = i - 1
        if pidx >= len(part_names):
            break
        name = part_names[pidx].lower()
        if 'drum' in name:
            for msg in track:
                if hasattr(msg, 'channel'):
                    msg.channel = 9
        elif '808' in name or 'bass' in name:
            insert_program(track, 38)    # Synth Bass 1
        elif 'chord' in name or 'pad' in name:
            insert_program(track, 89)    # Pad 2 (warm)
        elif 'piano' in name:
            insert_program(track, 0)     # Acoustic Grand Piano
        elif 'lead' in name or 'bell' in name:
            insert_program(track, 14)    # Tubular Bells


def save(score, filename):
    path = os.path.join(OUTPUT_DIR, filename)
    score.write('midi', fp=path)
    mid  = MidiFile(path)
    names = [p.partName or '' for p in score.parts]
    fix_instruments(mid, names)
    mid.save(path)
    print(f'  ✓  {filename}')
    return path


def solo(part):
    s = stream.Score()
    s.append(part)
    return s


# ─── COMPOSE & SAVE ───────────────────────────────────────────────────────────
print('Composing Dark Trap Beat v3 …')
print(f'  Key: C minor  |  BPM: {BPM}  |  64 bars (~1:41)')
print(f'  Layers: drums, 808, pad, piano, lead')
print(f'  Kit: Juicy Jules Stardust\n')

drums  = create_drums()
bass   = create_808()
chords = create_chords()
piano  = create_piano()
lead   = create_lead()

print('Saving individual stems …')
save(solo(drums),  'DarkTrap_drums.mid')
save(solo(bass),   'DarkTrap_808.mid')
save(solo(chords), 'DarkTrap_chords.mid')
save(solo(piano),  'DarkTrap_piano.mid')
save(solo(lead),   'DarkTrap_lead.mid')

print('\nSaving full arrangement …')
full = stream.Score()
full.append(drums)
full.append(bass)
full.append(chords)
full.append(piano)
full.append(lead)
save(full, 'DarkTrap_FULL.mid')

print('\nDone! MIDI files saved to:')
print(f'  {OUTPUT_DIR}')
