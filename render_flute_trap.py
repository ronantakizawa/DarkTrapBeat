"""
Dark Trap Beat v3 — Render Script
C minor | 152 BPM | 64 bars

Kit: Juicy Jules Stardust (rotated from Obie)

MIDI track indices in DarkTrap_FULL.mid:
  0: tempo/metadata  1: drums  2: 808 bass
  3: chords/pad      4: piano  5: dark bell lead
"""

import os
import sys
import subprocess
import json
import numpy as np
from collections import defaultdict
from math import gcd
from scipy import signal
from scipy.signal import fftconvolve
from scipy.io import wavfile
import soundfile as sf
from pydub import AudioSegment
import mido
import pedalboard as pb
import dawdreamer as daw
import pyroomacoustics as pra
import glob as _glob
import pyloudnorm as pyln


OUTPUT   = '/Users/ronantakizawa/Documents/FluteTrap_Beat'
FULL_MID = os.path.join(OUTPUT, 'DarkTrap_FULL.mid')
FIXED_MID= os.path.join(OUTPUT, 'DarkTrap_FIXED.mid')

_existing = _glob.glob(os.path.join(OUTPUT, 'DarkTrap_v*.mp3'))
_version  = max([int(os.path.basename(p).split('_v')[1].split('.')[0])
                 for p in _existing], default=0) + 1
_vstr    = f'v{_version}'
OUT_WAV  = os.path.join(OUTPUT, f'DarkTrap_{_vstr}.wav')
OUT_MP3  = os.path.join(OUTPUT, f'DarkTrap_{_vstr}.mp3')
print(f'Output: {OUT_MP3}')

SR    = 44100
BPM   = 152
BEAT  = 60.0 / BPM
BAR   = BEAT * 4
NBARS = 64
SONG  = NBARS * BAR
NSAMP = int((SONG + 4.0) * SR)

INTRO_S,  INTRO_E  =  0,  8
HOOKA_S,  HOOKA_E  =  8, 24
VERSE_S,  VERSE_E  = 24, 40
BRIDGE_S, BRIDGE_E = 40, 48
HOOKB_S,  HOOKB_E  = 48, 64

rng = np.random.RandomState(42)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def load_sample(path):
    data, orig_sr = sf.read(path, dtype='float32', always_2d=True)
    mono = data.mean(axis=1)
    if orig_sr != SR:
        g    = gcd(SR, orig_sr)
        mono = signal.resample_poly(mono, SR // g, orig_sr // g)
    return mono.astype(np.float32)


def place(buf_L, buf_R, snd, start_s, gain_L=1.0, gain_R=1.0):
    e = min(start_s + len(snd), NSAMP)
    if e <= start_s:
        return
    chunk = snd[:e - start_s]
    buf_L[start_s:e] += chunk * gain_L
    buf_R[start_s:e] += chunk * gain_R


def apply_pb(arr2ch, board):
    out = board(arr2ch.T.astype(np.float32), SR)
    return out.T.astype(np.float32)


def midi_to_hz(n):
    return 440.0 * (2 ** ((n - 69) / 12.0))


def parse_track(mid_path, track_idx):
    mid       = mido.MidiFile(mid_path)
    tpb       = mid.ticks_per_beat
    tempo_val = 500000
    for msg in mid.tracks[0]:
        if msg.type == 'set_tempo':
            tempo_val = msg.tempo
            break
    active, result = {}, []
    ticks = 0
    for msg in mid.tracks[track_idx]:
        ticks += msg.time
        t = mido.tick2second(ticks, tpb, tempo_val)
        if msg.type == 'note_on' and msg.velocity > 0:
            active[msg.note] = (t, msg.velocity)
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            if msg.note in active:
                s, v = active.pop(msg.note)
                if t - s > 0:
                    result.append((s, msg.note, v, t - s))
    return result


def make_automation(notes, release_gap=0.015):
    gap      = int(release_gap * SR)
    freq_arr = np.zeros(NSAMP, dtype=np.float32)
    gate_arr = np.zeros(NSAMP, dtype=np.float32)
    gain_arr = np.ones(NSAMP,  dtype=np.float32)
    for start_sec, note_num, vel, dur_sec in notes:
        s = int(start_sec * SR)
        e = min(int((start_sec + dur_sec) * SR), NSAMP)
        hz = midi_to_hz(note_num)
        freq_arr[max(0, s - gap):e] = hz
        gate_arr[s:e] = 1.0
        gain_arr[s:e] = vel / 127.0
    last = midi_to_hz(60)
    for i in range(NSAMP):
        if freq_arr[i] > 0:
            last = freq_arr[i]
        else:
            freq_arr[i] = last
    return freq_arr, gate_arr, gain_arr


def humanize_notes(notes, timing_ms=8, vel_range=5):
    result = []
    jitter_samp = timing_ms / 1000.0
    for start, note_num, vel, dur in notes:
        t_jitter = rng.uniform(-jitter_samp, jitter_samp)
        v_jitter = rng.randint(-vel_range, vel_range + 1)
        result.append((max(0, start + t_jitter), note_num,
                        int(np.clip(vel + v_jitter, 1, 127)), dur))
    return result


def faust_render(dsp_string, freq_arr, gate_arr, gain_arr, vol=1.0):
    engine = daw.RenderEngine(SR, 512)
    synth  = engine.make_faust_processor('s')
    synth.set_dsp_string(dsp_string)
    if not synth.compile():
        raise RuntimeError('FAUST compile failed')
    synth.set_automation('/dawdreamer/freq', freq_arr)
    synth.set_automation('/dawdreamer/gate', gate_arr)
    synth.set_automation('/dawdreamer/gain', gain_arr)
    engine.load_graph([(synth, [])])
    engine.render(NSAMP / SR)
    audio = synth.get_audio()
    return (audio.T * vol).astype(np.float32)


def separate_voices(notes):
    groups = defaultdict(list)
    for n in notes:
        key = round(n[0] * 20) / 20
        groups[key].append(n)
    voices = [[], [], [], []]
    for key in sorted(groups):
        ch = sorted(groups[key], key=lambda x: x[1])
        for i, n in enumerate(ch[:4]):
            voices[i].append(n)
    return voices


def bar_to_s(bar, beat=0.0):
    return (bar + beat / 4.0) * BAR


def pan_stereo(buf, position):
    angle = (position + 1) * np.pi / 4
    result = buf.copy()
    result[:, 0] *= np.cos(angle)
    result[:, 1] *= np.sin(angle)
    return result


def stereo_widen(buf, delay_ms=12):
    d = int(delay_ms / 1000.0 * SR)
    if d <= 0 or d >= len(buf):
        return buf.copy()
    result = buf.copy()
    result[d:, 1] = buf[:-d, 1]
    result[:d, 1] *= 0.3
    return result


# ─── FAUST DSP ───────────────────────────────────────────────────────────────

PAD_DSP = """
import("stdfaust.lib");
freq = hslider("freq[unit:Hz]", 440, 0.001, 20000, 0.001);
gain = hslider("gain", 1, 0, 1, 0.01);
gate = button("gate");
osc  = (os.sawtooth(freq)
      + os.sawtooth(freq * 1.009)
      + os.sawtooth(freq * 0.991)
      + os.sawtooth(freq * 1.018)
      + os.sawtooth(freq * 0.982)) * 0.2;
env  = en.adsr(0.50, 0.60, 0.68, 3.0, gate);
lfo  = os.osc(0.03) * 0.5 + 0.5;
cutoff = 200.0 + lfo * 600.0;
process = osc * env * gain * 0.40 : fi.lowpass(2, cutoff) <: _, _;
"""

# PIANO TIMBRE RULE: bright attack, fast decay — NOT a pad sound.
# Triangle + sine with short envelope for plucked/bell-like piano tone.
PIANO_DSP = """
import("stdfaust.lib");
freq = hslider("freq[unit:Hz]", 440, 0.001, 20000, 0.001);
gain = hslider("gain", 1, 0, 1, 0.01);
gate = button("gate");
osc  = os.triangle(freq) * 0.6 + os.osc(freq * 2.0) * 0.15 + os.osc(freq * 3.0) * 0.05;
env  = en.adsr(0.005, 0.35, 0.15, 0.8, gate);
process = osc * env * gain * 0.50 : fi.lowpass(2, 4000) <: _, _;
"""

# LEAD TIMBRE RULE: FM bell, vel 38-50, cap gain at 0.32 in mix.
# Do NOT raise mix coefficient above 0.32.
LEAD_DSP = """
import("stdfaust.lib");
freq = hslider("freq[unit:Hz]", 440, 0.001, 20000, 0.001);
gain = hslider("gain", 1, 0, 1, 0.01);
gate = button("gate");
mod  = os.osc(freq * 2.01) * freq * 0.3;
osc  = os.osc(freq + mod) + os.osc(freq * 0.5) * 0.3;
env  = en.adsr(0.002, 0.30, 0.12, 1.0, gate);
process = osc * env * gain * 0.45 : fi.lowpass(2, 2500) <: _, _;
"""


# ══════════════════════════════════════════════════════════════════════════════
# STEP 0 — Fix MIDI
# ══════════════════════════════════════════════════════════════════════════════
print('\nStep 0: Fixing MIDI …')
mid = mido.MidiFile(FULL_MID)
new_t0     = mido.MidiTrack()
seen_tempo = False
for msg in mid.tracks[0]:
    if msg.type == 'set_tempo':
        if not seen_tempo:
            new_t0.append(mido.MetaMessage('set_tempo', tempo=msg.tempo, time=0))
            seen_tempo = True
    else:
        new_t0.append(msg)
mid.tracks[0] = new_t0
mid.save(FIXED_MID)
print(f'  ✓  FIXED_MID  ({len(mid.tracks)} tracks)')


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Load samples (Juicy Jules Stardust — rotated from Obie)
# ══════════════════════════════════════════════════════════════════════════════
print('\nStep 1: Loading Juicy Jules Stardust samples …')
JJ = '/Users/ronantakizawa/Documents/instruments/☆ Juicy Jules - Stardust ☆/☆ Juicy Jules - Stardust ☆'

KICK     = load_sample(f'{JJ}/☆ Kicks/Kick - Deep.wav')
SNARE    = load_sample(f'{JJ}/☆ Snares/Snare - Codeine.wav')
CLAP     = load_sample(f'{JJ}/☆ Claps/Clap - Layer.wav')
HH_CL   = load_sample(f'{JJ}/☆ Closed Hats/HH - 3.wav')
HH_OP   = load_sample(f'{JJ}/☆ Open Hats/OH - Mellow.wav')
BASS_808 = load_sample(f'{JJ}/☆ 808s/808 - Dark.wav')
CRASH    = load_sample(f'{JJ}/☆ Crashes/Crash - Classic.wav')
FX_STORM = load_sample(f'{JJ}/☆ FX/FX - Storm.wav')
FX_UHH   = load_sample(f'{JJ}/☆ FX/FX - Uhh.wav')

print(f'  Kick={len(KICK)/SR:.2f}s  Snare={len(SNARE)/SR:.2f}s  808={len(BASS_808)/SR:.2f}s')
print(f'  Clap={len(CLAP)/SR:.2f}s  HH_CL={len(HH_CL)/SR:.2f}s  Crash={len(CRASH)/SR:.2f}s')
print(f'  FX_Storm={len(FX_STORM)/SR:.2f}s  FX_Uhh={len(FX_UHH)/SR:.2f}s')


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Drums
# ══════════════════════════════════════════════════════════════════════════════
print('\nStep 2: Building drum track …')

room = pra.ShoeBox([3.0, 2.5, 2.4], fs=SR,
                   materials=pra.Material(0.50), max_order=2)
room.add_source([1.5, 1.2, 1.2])
room.add_microphone(np.array([[1.8, 1.6, 1.4]]).T)
room.compute_rir()
room_ir = np.array(room.rir[0][0], dtype=np.float32)
room_ir = room_ir[:int(SR * 0.15)]   # tight trap room (150ms)
room_ir /= (np.abs(room_ir).max() + 1e-9)
print(f'  Room IR: {len(room_ir)/SR*1000:.0f} ms')

kick_L   = np.zeros(NSAMP, dtype=np.float32)
kick_R   = np.zeros(NSAMP, dtype=np.float32)
nk_L     = np.zeros(NSAMP, dtype=np.float32)
nk_R     = np.zeros(NSAMP, dtype=np.float32)
kick_env = np.zeros(NSAMP, dtype=np.float32)

drum_events = parse_track(FIXED_MID, 1)
MAX_JITTER  = int(0.006 * SR)
pan_toggle  = False

for sec, note_num, vel, _ in drum_events:
    bs = int(sec * SR)
    if bs >= NSAMP:
        continue
    g = vel / 127.0

    if note_num == 36:   # Kick
        snd   = KICK * g * 1.05
        chunk = snd[:min(len(snd), NSAMP - bs)]
        e     = bs + len(chunk)
        kick_env[bs:e] += np.abs(chunk)
        kick_L[bs:e]   += chunk * 0.96
        kick_R[bs:e]   += chunk * 0.96

    elif note_num == 38:   # Snare (tutorial: snare -2/-3dB from kick)
        jitter = rng.randint(-MAX_JITTER, MAX_JITTER + 1)
        s      = int(np.clip(bs + jitter, 0, NSAMP - 1))
        snd    = SNARE * g * rng.uniform(0.93, 1.07)
        e      = min(s + len(snd), NSAMP)
        nk_L[s:e] += snd[:e - s] * 0.75  # -2/-3dB from kick
        nk_R[s:e] += snd[:e - s] * 0.75

    elif note_num == 39:   # Clap (layered with snare)
        jitter = rng.randint(-MAX_JITTER, MAX_JITTER + 1)
        s      = int(np.clip(bs + jitter, 0, NSAMP - 1))
        snd    = CLAP * g * rng.uniform(0.90, 1.05)
        e      = min(s + len(snd), NSAMP)
        nk_L[s:e] += snd[:e - s] * 0.70
        nk_R[s:e] += snd[:e - s] * 0.70

    elif note_num == 42:   # Closed HH
        pan_toggle = not pan_toggle
        jitter = rng.randint(-MAX_JITTER, MAX_JITTER + 1)
        s      = int(np.clip(bs + jitter, 0, NSAMP - 1))
        v      = g * rng.uniform(0.68, 1.00)
        snd    = HH_CL * v * 0.48
        pr     = 0.62 if pan_toggle else 0.38
        e      = min(s + len(snd), NSAMP)
        ch     = snd[:e - s]
        nk_L[s:e] += ch * (1 - pr) * 2
        nk_R[s:e] += ch * pr * 2

    elif note_num == 46:   # Open HH
        jitter = rng.randint(-MAX_JITTER // 2, MAX_JITTER // 2 + 1)
        s      = int(np.clip(bs + jitter, 0, NSAMP - 1))
        snd    = HH_OP * g * rng.uniform(0.65, 0.90)
        place(nk_L, nk_R, snd, s, 0.48, 0.52)

    elif note_num == 49:   # Crash
        snd = CRASH * g * 0.58
        place(nk_L, nk_R, snd, bs, 0.44, 0.56)

# Combine kick + non-kick, apply room IR
drum_L = kick_L + nk_L
drum_R = kick_R + nk_R

dl_room = fftconvolve(drum_L, room_ir, mode='full')[:NSAMP]
dr_room = fftconvolve(drum_R, room_ir, mode='full')[:NSAMP]
drum_L  = drum_L * 0.92 + dl_room * 0.06   # 6% wet — dry for trap
drum_R  = drum_R * 0.92 + dr_room * 0.06

drum_stereo = np.stack([drum_L, drum_R], axis=1)
drum_board  = pb.Pedalboard([
    pb.Compressor(threshold_db=-10, ratio=4.0, attack_ms=2, release_ms=80),
    pb.Gain(gain_db=2.5),
    pb.Limiter(threshold_db=-0.8),
])
drum_stereo = apply_pb(drum_stereo, drum_board)
print(f'  ✓  {len(drum_events)} drum events')


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Sidechain
# ══════════════════════════════════════════════════════════════════════════════
print('\nStep 3: Sidechain …')
smooth  = int(SR * 0.010)
sc_env  = np.convolve(kick_env, np.ones(smooth) / smooth, mode='same')
sc_env /= sc_env.max() + 1e-9
sc_gain = np.clip(1.0 - sc_env * 0.55, 0.45, 1.0)
print('  ✓  Sidechain ready')


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — 808 Bass (pitch-shifted to chord roots)
# ══════════════════════════════════════════════════════════════════════════════
print('\nStep 4: Building 808 bass …')

# Detect 808 root pitch via FFT
_fft_808  = np.abs(np.fft.rfft(BASS_808 * np.hanning(len(BASS_808))))
_freq_808 = np.fft.rfftfreq(len(BASS_808), 1 / SR)
_mask_808 = (_freq_808 > 20) & (_freq_808 < 500)
_peak_808 = _freq_808[_mask_808][np.argmax(_fft_808[_mask_808])]
BASS_ROOT_MIDI = int(round(12 * np.log2(_peak_808 / 440) + 69))
print(f'  808 root detected: MIDI {BASS_ROOT_MIDI}  ({_peak_808:.1f} Hz)')

# Chord roots: C2=36, F1=29, Ab1=32, G1=31
BASS_TARGETS = {36: 'C2', 29: 'F1', 32: 'Ab1', 31: 'G1'}

pitched_808 = {}
for target_midi in BASS_TARGETS:
    st = target_midi - BASS_ROOT_MIDI
    if st == 0:
        pitched_808[target_midi] = BASS_808.copy()
    else:
        board_p = pb.Pedalboard([pb.PitchShift(semitones=st)])
        pitched_808[target_midi] = board_p(BASS_808[np.newaxis, :], SR)[0].astype(np.float32)
    print(f'  808 → {BASS_TARGETS[target_midi]} ({st:+d}st): {len(pitched_808[target_midi])/SR:.2f}s')

bass_notes = parse_track(FIXED_MID, 2)
bass_L = np.zeros(NSAMP, dtype=np.float32)
bass_R = np.zeros(NSAMP, dtype=np.float32)

def closest_808_target(midi_note):
    return min(BASS_TARGETS.keys(), key=lambda t: abs(t - midi_note))

for sec, midi_note, vel, dur_sec in bass_notes:
    s = int(sec * SR)
    if s >= NSAMP:
        continue
    target = closest_808_target(midi_note)
    snd    = pitched_808[target]
    g      = (vel / 127.0) * rng.uniform(0.92, 1.08)
    trim   = min(int(dur_sec * SR), len(snd))
    chunk  = snd[:trim].copy() * g
    fade_n = max(1, int(SR * 0.020))
    if trim > fade_n:
        chunk[-fade_n:] *= np.linspace(1, 0, fade_n)
    e = min(s + len(chunk), NSAMP)
    bass_L[s:e] += chunk[:e - s] * 0.95
    bass_R[s:e] += chunk[:e - s] * 0.95

bass_buf = np.stack([bass_L, bass_R], axis=1)
bass_buf[:, 0] *= (sc_gain * 0.70 + 0.30)
bass_buf[:, 1] *= (sc_gain * 0.70 + 0.30)

bass_board = pb.Pedalboard([
    pb.HighpassFilter(cutoff_frequency_hz=30),
    pb.LowpassFilter(cutoff_frequency_hz=1200),
    pb.Distortion(drive_db=4.0),
    pb.Compressor(threshold_db=-10, ratio=3.5, attack_ms=4, release_ms=130),
    pb.Gain(gain_db=3.5),
    pb.Limiter(threshold_db=-1.5),
])
bass_buf = apply_pb(bass_buf, bass_board)
print(f'  ✓  808 bass  events={len(bass_notes)}  max={np.abs(bass_buf).max():.3f}')


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — PAD (FAUST synth)
# ══════════════════════════════════════════════════════════════════════════════
print('\nStep 5: Synthesizing PAD …')
chord_notes = parse_track(FIXED_MID, 3)
voices      = separate_voices(chord_notes)
pad_buf     = np.zeros((NSAMP, 2), dtype=np.float32)
for vi, voice in enumerate(voices):
    if not voice:
        continue
    freq_a, gate_a, gain_a = make_automation(voice)
    audio = faust_render(PAD_DSP, freq_a, gate_a, gain_a, vol=0.70)
    pad_buf += audio[:NSAMP]
    print(f'  Voice {vi+1}: {len(voice)} notes')

pad_buf[:, 0] *= (sc_gain * 0.20 + 0.80)
pad_buf[:, 1] *= (sc_gain * 0.20 + 0.80)
pad_board = pb.Pedalboard([
    pb.HighpassFilter(cutoff_frequency_hz=150),
    pb.LowpassFilter(cutoff_frequency_hz=8000),
    pb.Reverb(room_size=0.85, damping=0.40, wet_level=0.42, dry_level=0.80, width=0.98),
    pb.Compressor(threshold_db=-18, ratio=2.5, attack_ms=40, release_ms=500),
    pb.Gain(gain_db=0.5),
])
pad_buf = apply_pb(pad_buf, pad_board)
print(f'  ✓  Pad  max={np.abs(pad_buf).max():.3f}')


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — PIANO (FAUST synth — bright plucked tone)
# ══════════════════════════════════════════════════════════════════════════════
print('\nStep 6: Synthesizing Piano …')
piano_notes = parse_track(FIXED_MID, 4)
piano_notes = humanize_notes(piano_notes, timing_ms=10, vel_range=4)
print(f'  Piano events: {len(piano_notes)}')

freq_a, gate_a, gain_a = make_automation(piano_notes)
piano_buf = faust_render(PIANO_DSP, freq_a, gate_a, gain_a, vol=0.60)
piano_buf = piano_buf[:NSAMP]

piano_buf[:, 0] *= (sc_gain * 0.15 + 0.85)
piano_buf[:, 1] *= (sc_gain * 0.15 + 0.85)

piano_board = pb.Pedalboard([
    pb.HighpassFilter(cutoff_frequency_hz=180),
    pb.LowpassFilter(cutoff_frequency_hz=6000),
    pb.Reverb(room_size=0.60, damping=0.55, wet_level=0.28, dry_level=0.85, width=0.80),
    pb.Compressor(threshold_db=-14, ratio=2.5, attack_ms=8, release_ms=180),
    pb.Gain(gain_db=0.5),
])
piano_buf = apply_pb(piano_buf, piano_board)
print(f'  ✓  Piano  notes={len(piano_notes)}  max={np.abs(piano_buf).max():.3f}')


# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — DARK BELL LEAD (FAUST FM synth)
# ══════════════════════════════════════════════════════════════════════════════
print('\nStep 7: Synthesizing dark bell lead …')
lead_notes = parse_track(FIXED_MID, 5)
lead_notes = humanize_notes(lead_notes, timing_ms=6, vel_range=3)
print(f'  Lead events: {len(lead_notes)}')

freq_a, gate_a, gain_a = make_automation(lead_notes)
lead_buf = faust_render(LEAD_DSP, freq_a, gate_a, gain_a, vol=0.65)
lead_buf = lead_buf[:NSAMP]

lead_buf[:, 0] *= (sc_gain * 0.15 + 0.85)
lead_buf[:, 1] *= (sc_gain * 0.15 + 0.85)

lead_board = pb.Pedalboard([
    pb.HighpassFilter(cutoff_frequency_hz=200),
    pb.LowpassFilter(cutoff_frequency_hz=8000),
    pb.Reverb(room_size=0.80, damping=0.50, wet_level=0.40, dry_level=0.75, width=0.92),
    pb.Compressor(threshold_db=-16, ratio=2.5, attack_ms=6, release_ms=200),
    pb.Gain(gain_db=0.5),
])
lead_buf = apply_pb(lead_buf, lead_board)
print(f'  ✓  Lead  notes={len(lead_notes)}  max={np.abs(lead_buf).max():.3f}')


# ══════════════════════════════════════════════════════════════════════════════
# STEP 8 — Atmosphere + Vocal Chops
# ══════════════════════════════════════════════════════════════════════════════
print('\nStep 8: Atmosphere + vocal chops …')
atmo_L = np.zeros(NSAMP, dtype=np.float32)
atmo_R = np.zeros(NSAMP, dtype=np.float32)

# Loop FX-Storm quietly under the whole song
storm_len = len(FX_STORM)
pos = 0
while pos < NSAMP:
    end = min(pos + storm_len, NSAMP)
    chunk = FX_STORM[:end - pos]
    atmo_L[pos:end] += chunk * 0.08
    atmo_R[pos:end] += chunk * 0.08
    pos += storm_len

# Vocal chop (FX-Uhh) at hook entries, pitched down
uhh_pitched = pb.Pedalboard([pb.PitchShift(semitones=-7)])(
    FX_UHH[np.newaxis, :], SR)[0].astype(np.float32)
uhh_verb = pb.Pedalboard([
    pb.Reverb(room_size=0.80, damping=0.30, wet_level=0.55, dry_level=0.60, width=0.95),
    pb.Distortion(drive_db=3.0),
])(uhh_pitched[np.newaxis, :], SR)[0].astype(np.float32)

# Place at hook A entry, hook B entry
for hook_bar in [HOOKA_S, HOOKB_S]:
    s = int(bar_to_s(hook_bar) * SR)
    place(atmo_L, atmo_R, uhh_verb * 0.35, s, 0.55, 0.45)

# Place lighter at verse entry
s = int(bar_to_s(VERSE_S) * SR)
place(atmo_L, atmo_R, uhh_verb * 0.20, s, 0.45, 0.55)

atmo_buf = np.stack([atmo_L, atmo_R], axis=1)
atmo_board = pb.Pedalboard([
    pb.HighpassFilter(cutoff_frequency_hz=200),
    pb.LowpassFilter(cutoff_frequency_hz=10000),
    pb.Compressor(threshold_db=-18, ratio=2.0, attack_ms=20, release_ms=300),
])
atmo_buf = apply_pb(atmo_buf, atmo_board)
print(f'  ✓  Atmosphere + vocal chops')


# ══════════════════════════════════════════════════════════════════════════════
# STEP 9 — Transition FX
# ══════════════════════════════════════════════════════════════════════════════
print('\nStep 9: Transition FX …')
fx_L = np.zeros(NSAMP, dtype=np.float32)
fx_R = np.zeros(NSAMP, dtype=np.float32)


def snare_roll(target_bar, bars_build=1.0):
    n_beats = int(bars_build * 4)
    densities = [2, 3, 4, 6, 8]
    for beat_i in range(n_beats):
        progress = beat_i / n_beats
        d_idx    = min(int(progress * len(densities)), len(densities) - 1)
        n_hits   = densities[d_idx]
        for h in range(n_hits):
            t   = bar_to_s(target_bar - bars_build, beat_i + h / n_hits)
            vel = (0.25 + 0.65 * progress) * rng.uniform(0.90, 1.10)
            s   = int(t * SR)
            if 0 <= s < NSAMP:
                place(fx_L, fx_R, SNARE * vel * 0.55, s, 0.50, 0.50)


def reverse_tail(target_bar, length_beats=3):
    tail_len = int(length_beats * BEAT * SR)
    padded   = np.zeros(tail_len, dtype=np.float32)
    sn_len   = min(len(SNARE), tail_len)
    padded[:sn_len] = SNARE[:sn_len] * 0.5
    tail_verb = pb.Pedalboard([
        pb.Reverb(room_size=0.92, damping=0.25, wet_level=0.95, dry_level=0.0, width=1.0),
    ])
    wet  = tail_verb(padded[np.newaxis, :], SR)[0]
    rev  = wet[::-1].copy()
    fade = int(0.04 * SR)
    rev[:fade] *= np.linspace(0, 1, fade)
    end_s   = int(bar_to_s(target_bar) * SR)
    start_s = max(0, end_s - len(rev))
    chunk   = rev[:end_s - start_s]
    place(fx_L, fx_R, chunk, start_s, 0.48, 0.52)


# Intro → Hook A (bar 8)
snare_roll(HOOKA_S, bars_build=1.0)
reverse_tail(HOOKA_S, length_beats=3)
place(fx_L, fx_R, CRASH * 0.72, int(bar_to_s(HOOKA_S) * SR), 0.44, 0.56)

# Hook A → Verse (bar 24)
place(fx_L, fx_R, CRASH * 0.45, int(bar_to_s(HOOKA_E) * SR), 0.44, 0.56)

# Verse → Bridge (bar 40)
reverse_tail(BRIDGE_S, length_beats=2)

# Bridge → Hook B (bar 48)
snare_roll(HOOKB_S, bars_build=2.0)
reverse_tail(HOOKB_S, length_beats=3)
place(fx_L, fx_R, CRASH * 0.72, int(bar_to_s(HOOKB_S) * SR), 0.44, 0.56)

fx_buf = np.stack([fx_L, fx_R], axis=1)
fx_board = pb.Pedalboard([
    pb.HighpassFilter(cutoff_frequency_hz=120),
    pb.Reverb(room_size=0.55, damping=0.60, wet_level=0.18, dry_level=0.92, width=0.85),
    pb.Compressor(threshold_db=-14, ratio=3.0, attack_ms=4, release_ms=120),
    pb.Gain(gain_db=1.5),
])
fx_buf = apply_pb(fx_buf, fx_board)
print('  ✓  Snare builds + reverse tails + crash hits')


# ══════════════════════════════════════════════════════════════════════════════
# STEP 10 — Stereo panning + final mix
# ══════════════════════════════════════════════════════════════════════════════
print('\nStep 10: Stereo panning + final mix …')

drum_panned  = pan_stereo(drum_stereo, 0.0)
bass_panned  = pan_stereo(bass_buf, 0.0)
pad_panned   = stereo_widen(pad_buf, 20)
piano_panned = stereo_widen(piano_buf, 15)
lead_panned  = stereo_widen(lead_buf, 18)
atmo_panned  = stereo_widen(atmo_buf, 22)
fx_panned    = pan_stereo(fx_buf, 0.0)

# Mix levels (tutorial: kick+808 loudest, snare -2/-3dB, melody -6dB)
mix = (drum_panned  * 0.90 +
       bass_panned  * 0.92 +
       pad_panned   * 0.55 +
       piano_panned * 0.42 +
       lead_panned  * 0.30 +    # LEAD MIX RULE: cap at 0.32
       atmo_panned  * 0.18 +
       fx_panned    * 0.50)



# ══════════════════════════════════════════════════════════════════════════════
# STEP 11 — Master chain
# ══════════════════════════════════════════════════════════════════════════════
print('Step 11: Master chain …')
master_board = pb.Pedalboard([
    pb.HighpassFilter(cutoff_frequency_hz=28),
    pb.LowpassFilter(cutoff_frequency_hz=18000),
    pb.Compressor(threshold_db=-10, ratio=2.5, attack_ms=15, release_ms=200),
    pb.Distortion(drive_db=3.0),
    pb.Gain(gain_db=2.5),
    pb.Limiter(threshold_db=-0.5),
])
mix  = apply_pb(mix, master_board)
trim = int((SONG + 2.0) * SR)
mix  = mix[:trim]


# ══════════════════════════════════════════════════════════════════════════════
# STEP 11.5 — LUFS normalization
# ══════════════════════════════════════════════════════════════════════════════
print('Step 11.5: LUFS normalization …')
meter = pyln.Meter(SR, block_size=0.400)
TARGET_LUFS = -14.0

lufs_before = meter.integrated_loudness(mix)
print(f'  Pre-norm LUFS: {lufs_before:.1f}')
if np.isfinite(lufs_before):
    gain_db = TARGET_LUFS - lufs_before
    mix = mix * (10 ** (gain_db / 20.0))
    limit_board = pb.Pedalboard([pb.Limiter(threshold_db=-0.5)])
    mix = apply_pb(mix, limit_board)
    lufs_after = meter.integrated_loudness(mix)
    print(f'  Post-norm LUFS: {lufs_after:.1f}  (target: {TARGET_LUFS})')
else:
    print('  Could not measure LUFS — skipping normalization')


# ══════════════════════════════════════════════════════════════════════════════
# STEP 12 — Export
# ══════════════════════════════════════════════════════════════════════════════
print('Step 12: Exporting …')

def export(buf, wav_path, mp3_path, title):
    out_i16 = (buf * 32767).clip(-32767, 32767).astype(np.int16)
    wavfile.write(wav_path, SR, out_i16)
    seg = AudioSegment.from_wav(wav_path)
    seg.export(mp3_path, format='mp3', bitrate='192k', tags={
        'title':  title,
        'artist': 'Claude Code',
        'album':  'Dark Trap Beat',
        'genre':  'Trap',
    })
    m, s = divmod(int(len(seg) / 1000), 60)
    print(f'  ✓  {os.path.basename(mp3_path)}: {os.path.getsize(mp3_path)/1e6:.1f} MB  |  {m}:{s:02d}')

export(mix, OUT_WAV, OUT_MP3, f'Dark Trap {_vstr}')

print(f'\nDone!  →  {OUT_MP3}')


# ══════════════════════════════════════════════════════════════════════════════
# STEP 12.5 — Mix analysis
# ══════════════════════════════════════════════════════════════════════════════
print('\n── Mix Analysis ──')
y_mono = mix.mean(axis=1).astype(np.float32)
rms_val = np.sqrt(np.mean(y_mono ** 2))
_spec = np.abs(np.fft.rfft(y_mono))
_freqs = np.fft.rfftfreq(len(y_mono), 1.0 / SR)
_spec_sum = _spec.sum() + 1e-9
centroid_hz = np.sum(_freqs * _spec) / _spec_sum
bw_hz = np.sqrt(np.sum(((_freqs - centroid_hz) ** 2) * _spec) / _spec_sum)
final_lufs = meter.integrated_loudness(mix)
print(f'  Spectral centroid: {centroid_hz:.0f} Hz')
print(f'  Spectral bandwidth: {bw_hz:.0f} Hz')
print(f'  RMS: {rms_val:.4f}  ({20*np.log10(rms_val+1e-9):.1f} dB)')
print(f'  Integrated LUFS: {final_lufs:.1f}')

# librosa analysis in subprocess (avoids dawdreamer/numba LLVM conflict)
_analysis = subprocess.run(
    ['python', '-c', f"""
import numpy as np, json, librosa
y, _ = librosa.load('{OUT_WAV}', sr={SR}, mono=True)
c = float(librosa.feature.spectral_centroid(y=y, sr={SR}).mean())
r = float(librosa.feature.rms(y=y).mean())
b = float(librosa.feature.spectral_bandwidth(y=y, sr={SR}).mean())
print(json.dumps({{"centroid": c, "rms": r, "bandwidth": b}}))
"""], capture_output=True, text=True)
if _analysis.returncode == 0:
    _a = json.loads(_analysis.stdout.strip())
    print(f'  librosa centroid: {_a["centroid"]:.0f} Hz')
    print(f'  librosa bandwidth: {_a["bandwidth"]:.0f} Hz')
    print(f'  librosa RMS: {_a["rms"]:.4f}  ({20*np.log10(_a["rms"]+1e-9):.1f} dB)')
print('──────────────────')
