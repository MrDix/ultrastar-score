"""High-level pitch detection interface wrapping the C++ ptAKF module."""

from __future__ import annotations

import numpy as np

# Try native C++ extension first, fall back to pure-Python implementation
try:
    from ultrastar_score.pitch._ptakf import PtAKF as _PtAKF, PitchResult
    _HAS_NATIVE = True
except ImportError:
    _HAS_NATIVE = False

# Constants matching ptAKF
WINDOW_SIZE = 2048
HOP_SIZE = 1024
BASE_FREQ = 65.4064  # C2
MAX_HALFTONE = 56
SAMPLE_RATE = 44100


class PitchDetector:
    """Pitch detector using Vocaluxe's ptAKF algorithm.

    Falls back to a pure-Python AMDF implementation if the C++ extension
    is not available (slower but functional).
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE, volume_threshold: float = 0.01):
        self.sample_rate = sample_rate
        self.volume_threshold = volume_threshold
        if _HAS_NATIVE:
            self._engine = _PtAKF(sample_rate)
        else:
            self._engine = None
            self._periods = np.array([
                sample_rate / (BASE_FREQ * 2 ** (t / 12))
                for t in range(MAX_HALFTONE + 1)
            ])

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

        if _HAS_NATIVE:
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

        # Pure-Python fallback (AMDF only, slower)
        return self._detect_all_python(audio, hop_size)

    def _detect_all_python(self, audio: np.ndarray, hop_size: int) -> list[dict]:
        """Pure-Python AMDF pitch detection fallback."""
        n = len(audio)
        results = []

        num_frames = max(0, (n - WINDOW_SIZE) // hop_size + 1)

        for frame_idx in range(num_frames):
            start = frame_idx * hop_size
            window = audio[start:start + WINDOW_SIZE]

            time_sec = start / self.sample_rate

            # Volume gate
            if np.max(np.abs(window[WINDOW_SIZE // 2:])) < self.volume_threshold:
                results.append({"tone": -1, "frequency": 0.0, "confidence": 0.0, "time": time_sec})
                continue

            # Apply Hamming window
            windowed = window * np.hamming(WINDOW_SIZE)

            # AMDF for each halftone candidate
            best_tone = -1
            best_score = float("inf")

            for tone in range(MAX_HALFTONE + 1):
                lag = int(round(self._periods[tone]))
                if lag < 2 or lag >= WINDOW_SIZE // 2:
                    continue

                # AMDF
                diff = np.abs(windowed[:WINDOW_SIZE - lag] - windowed[lag:WINDOW_SIZE])
                amdf = np.mean(diff)

                if amdf < best_score:
                    best_score = amdf
                    best_tone = tone

            if best_tone >= 0:
                freq = BASE_FREQ * 2 ** (best_tone / 12)
                # Rough confidence from AMDF (lower = better)
                energy = np.mean(windowed ** 2)
                conf = max(0.0, min(1.0, 1.0 - best_score / (np.sqrt(energy) + 1e-10)))
                results.append({"tone": best_tone, "frequency": freq, "confidence": conf, "time": time_sec})
            else:
                results.append({"tone": -1, "frequency": 0.0, "confidence": 0.0, "time": time_sec})

        # Median smoothing over 3 frames
        if len(results) >= 3:
            tones = [r["tone"] for r in results]
            for i in range(1, len(results) - 1):
                med = sorted([tones[i - 1], tones[i], tones[i + 1]])[1]
                if med != results[i]["tone"] and med >= 0:
                    results[i]["tone"] = med
                    results[i]["frequency"] = BASE_FREQ * 2 ** (med / 12)

        return results
