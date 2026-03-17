"""Audio loading and resampling for ultrastar-score."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

TARGET_SAMPLE_RATE = 44100


def load_audio(path: str | Path, target_sr: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    """Load an audio file and return mono float64 samples at the target sample rate.

    Supports WAV, OGG, FLAC natively via soundfile.
    MP3 support requires the ``audioread`` package (``pip install ultrastar-score[mp3]``).

    Args:
        path: Path to audio file.
        target_sr: Target sample rate (default 44100 Hz for ptAKF compatibility).

    Returns:
        1-D numpy array of float64 samples normalised to [-1, 1].
    """
    path = Path(path)

    try:
        audio, sr = sf.read(str(path), dtype="float64", always_2d=True)
    except RuntimeError:
        # soundfile can't read this format; try audioread for MP3 etc.
        audio, sr = _load_with_audioread(path)

    # Convert to mono by averaging channels
    if audio.ndim == 2 and audio.shape[1] > 1:
        audio = np.mean(audio, axis=1)
    elif audio.ndim == 2:
        audio = audio[:, 0]

    # Resample if needed
    if sr != target_sr:
        audio = _resample(audio, sr, target_sr)

    return audio


def _resample(audio: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    """Resample audio using soxr (high quality)."""
    import soxr
    return soxr.resample(audio, sr_in, sr_out, quality="VHQ")


def _load_with_audioread(path: Path) -> tuple[np.ndarray, int]:
    """Load audio using audioread (for MP3 and other formats)."""
    try:
        import audioread
    except ImportError:
        raise ImportError(
            f"Cannot read {path.suffix} files. "
            "Install MP3 support: pip install ultrastar-score[mp3]"
        )

    with audioread.audio_open(str(path)) as f:
        sr = f.samplerate
        channels = f.channels
        frames = []
        for buf in f:
            frame = np.frombuffer(buf, dtype=np.int16).astype(np.float64) / 32768.0
            frames.append(frame)

    audio = np.concatenate(frames)
    if channels > 1:
        audio = audio.reshape(-1, channels)

    return audio, sr
