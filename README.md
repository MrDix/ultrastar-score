# ultrastar-score

Score UltraStar karaoke song files against vocal audio tracks using real game algorithms.

- **Pitch detection**: Vocaluxe ptAKF (AKF/AMDF hybrid autocorrelation)
- **Scoring**: USDX-compatible (10000-point scale with line bonus)
- **Difficulty levels**: Easy (±2 ST), Medium (±1 ST), Hard (exact match), or custom tolerance

## Installation

```bash
pip install ultrastar-score
```

For MP3 support:
```bash
pip install ultrastar-score[mp3]
```

## Usage

### Command Line

```bash
# Basic scoring (Easy difficulty)
uscore song.txt vocals.wav

# Different difficulty levels
uscore song.txt vocals.ogg --difficulty medium
uscore song.txt vocals.ogg --difficulty hard

# Custom tolerance (1.5 semitones)
uscore song.txt vocals.wav --tolerance 1.5

# JSON output for automation
uscore song.txt vocals.wav --json

# Detailed breakdowns
uscore song.txt vocals.wav --per-line
uscore song.txt vocals.wav --per-note
```

### Python API

```python
from ultrastar_score import score_song, parse_ultrastar, Difficulty

song = parse_ultrastar("song.txt")
result = score_song(song, "vocals.wav", difficulty=Difficulty.MEDIUM)

print(f"Score: {result.total:.0f}/10000 ({result.percentage:.1f}%)")
print(f"Rating: {result.rating}")
print(f"Beats hit: {result.notes_hit}/{result.notes_total}")
```

## Scoring Model

Follows the USDX scoring model:

| Component | Max Points | Description |
|-----------|-----------|-------------|
| Notes | 9000 | Per-beat scoring, golden notes worth 2x |
| Line Bonus | 1000 | Awarded proportionally per line |
| **Total** | **10000** | |

### Note Types

| Type | Symbol | Score Factor | Pitch Required |
|------|--------|:---:|:---:|
| Normal | `:` | 1x | Yes |
| Golden | `*` | 2x | Yes |
| Freestyle | `F` | 0 | No |
| Rap | `R` | 1x | No |
| Rap Golden | `G` | 2x | No |

### Octave Folding

Like USDX, detected pitch is octave-folded to within 6 semitones of the expected note before comparison. This means octave errors don't count as misses.

## Supported Formats

- **Audio**: WAV, OGG, FLAC (native), MP3 (with `[mp3]` extra)
- **Song files**: UltraStar TXT (legacy and v1.2.0 format)
- **Encodings**: UTF-8, UTF-8-BOM, CP1252, Latin-1

## Development

```bash
git clone https://github.com/MrDix/ultrastar-score
cd ultrastar-score
pip install -e ".[dev]"
pytest
```

## Algorithm Details

### Pitch Detection (ptAKF)

The pitch detection uses the combined AKF/AMDF method (Kobayashi & Shimamura, 2001):

```
f(τ) = AKF(τ) / (AMDF(τ) + 1)
```

- Window: 2048 samples with Hamming window
- Hop: 1024 samples (~23ms at 44.1kHz)
- Range: C2 (65.4 Hz) to G#6 (~1661 Hz)
- Smoothing: Median filter over 3 consecutive frames
- Validation: AKF at detected lag must be ≥33% of signal energy

Based on Vocaluxe's C++ implementation.

## License

GPL-3.0-or-later (due to Vocaluxe ptAKF code)
