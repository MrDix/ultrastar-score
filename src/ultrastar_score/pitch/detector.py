"""High-level pitch detection interface wrapping the C++ ptAKF module.

The C++ extension is REQUIRED — there is no Python fallback.
This is intentional: ultrastar-score uses Vocaluxe's ptAKF algorithm
as an independent pitch detector, completely separate from UltraSinger's
SwiftF0 pipeline. A Python reimplementation would risk sharing systematic
biases with UltraSinger, defeating the purpose of independent validation.
"""

from __future__ import annotations

import numpy as np

from ultrastar_score.pitch._ptakf import PtAKF as _PtAKF  # C++ extension (mandatory)

# Constants matching ptAKF
WINDOW_SIZE = 2048
HOP_SIZE = 1024
BASE_FREQ = 65.4064  # C2
MAX_HALFTONE = 56
SAMPLE_RATE = 44100


class PitchDetector:
    """Pitch detector using Vocaluxe's ptAKF algorithm (C++ extension).

    Uses AKF/AMDF hybrid autocorrelation (Kobayashi & Shimamura, 2001)
    with Hamming windowing, sub-semitone fine-tuning, energy validation,
    and median smoothing — identical to the algorithm used in Vocaluxe
    for real-time karaoke scoring.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE, volume_threshold: float = 0.01):
        self.sample_rate = sample_rate
        self.volume_threshold = volume_threshold
        self._engine = _PtAKF(sample_rate)

    def detect_all(
        self,
        audio: np.ndarray,
        hop_size: int = HOP_SIZE,
    ) -> list[dict]:
        """Detect pitch for all frames in the audio.

        Args:
            audio: Mono audio, float64, normalised to [-1, 1].
                   Sample rate must match ``self.sample_rate``.
            hop_size: Hop between frames in samples.

        Returns:
            List of dicts with keys: tone (int, -1=unvoiced), frequency (float),
            confidence (float), time (float, seconds).
        """
        audio = np.ascontiguousarray(audio, dtype=np.float64)

        raw = self._engine.detect_multi(audio, hop_size, self.volume_threshold)
        results = []
        for i, r in enumerate(raw):
            results.append({
                "tone": r.tone,
                "frequency": r.frequency,
                "confidence": r.confidence,
                "time": i * hop_size / self.sample_rate,
            })
        return results
