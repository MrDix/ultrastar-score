# ultrastar-score

Score UltraStar karaoke song files against vocal audio tracks using real game algorithms.

- **Pitch detection**: Vocaluxe ptAKF C++ extension (AKF/AMDF hybrid autocorrelation)
- **Scoring**: USDX-compatible (10000-point scale with line bonus)
- **Difficulty levels**: Easy (±2 ST), Medium (±1 ST), Hard (exact match), or custom tolerance

## Installation

Pre-built wheels are available for all major platforms (no compiler needed):

| OS | Architectures |
|----|---------------|
| **Windows** | x86_64, ARM64 |
| **Linux** | x86_64, aarch64 |
| **macOS** | x86_64, arm64 (Apple Silicon) |

Python 3.11, 3.12, and 3.13 are supported.

```bash
pip install ultrastar-score
```

For MP3 support:
```bash
pip install ultrastar-score[mp3]
```

### From source (development)

See [Development](#development) below for build requirements and setup instructions.

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

Building from source requires a C++ compiler and CMake (≥3.18):

| Platform | Compiler | Install |
|----------|----------|---------|
| **Windows** | MSVC Build Tools | `winget install Microsoft.VisualStudio.2022.BuildTools --override "--quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"` |
| **Linux** | GCC/Clang | `sudo apt install build-essential cmake` (Debian/Ubuntu) |
| **macOS** | Clang (Xcode) | `xcode-select --install` |

CMake (≥3.18) is also required. On Windows, install via `winget install Kitware.CMake`. On Linux/macOS it's typically included or available via your package manager.

```bash
git clone https://github.com/MrDix/ultrastar-score
cd ultrastar-score
pip install -e ".[dev]"
pytest
```

The C++ extension is built automatically by `pip install`. If you encounter build issues, run `pip install -e ".[dev]" -v` for verbose build output.

## Algorithm Details

### Pitch Detection (ptAKF)

The pitch detection uses the combined AKF/AMDF method (Kobayashi & Shimamura, 2001):

```
f(τ) = AKF(τ) / (AMDF(τ) + 1)
```

This is a **compiled C++ extension** — there is no Python fallback. This is intentional: ultrastar-score is designed as an **independent validation tool** for UltraStar song generators. Using a completely different pitch detection algorithm (Vocaluxe ptAKF) from the generator (e.g., UltraSinger's SwiftF0) ensures that systematic pitch detection errors are caught rather than masked.

Key parameters:

- Window: 2048 samples with Hamming window
- Hop: 1024 samples (~23ms at 44.1kHz)
- Range: C2 (65.4 Hz) to G#6 (~1661 Hz)
- Fine-tuning: ±1/3 semitone sub-resolution
- Validation: AKF at detected lag must be ≥33% of signal energy
- Smoothing: Median filter over 3 consecutive frames

Based on Vocaluxe's C++ implementation (GPL v3).

## Publishing to PyPI (Maintainers)

### One-Time Setup: OIDC Trusted Publishing

The release workflow uses PyPI's [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC) so no API tokens are needed.

1. Go to <https://pypi.org> and log in (or create an account).
2. Navigate to <https://pypi.org/manage/account/publishing/>.
3. Under **"Add a new pending publisher"**, fill in:
   - **PyPI project name:** `ultrastar-score`
   - **Owner:** `MrDix`
   - **Repository:** `ultrastar-score`
   - **Workflow name:** `release.yml`
   - **Environment name:** `pypi`
4. Click **"Add"**.

This tells PyPI to trust tokens issued by GitHub Actions for this specific repository and workflow.

### Creating a Release

1. Update the version in `pyproject.toml`.
2. Commit and push to `main`.
3. Create a GitHub release with a tag matching the version (e.g., `v0.2.0`).
4. The CI automatically builds wheels for all platforms (Linux x86_64/aarch64, Windows x86_64/ARM64, macOS x86_64/arm64) and publishes to PyPI.
5. Users can then install with `pip install ultrastar-score`.

### Workflow Requirements

The publish job in `.github/workflows/release.yml` must have these two settings for OIDC to work:

```yaml
environment: pypi          # must match the environment name on PyPI
permissions:
  id-token: write          # allows the job to request an OIDC token
```

Both are already configured in the current workflow.

## License

GPL-3.0-or-later (due to Vocaluxe ptAKF code)
