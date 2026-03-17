"""Tests for pitch detection."""

import numpy as np
import pytest

from ultrastar_score.pitch.detector import PitchDetector, BASE_FREQ, WINDOW_SIZE


class TestPitchDetector:
    """Test pitch detection with synthesized audio."""

    @staticmethod
    def _generate_sine(freq: float, duration: float = 0.2, sr: int = 44100) -> np.ndarray:
        """Generate a sine wave at the given frequency."""
        t = np.arange(int(sr * duration)) / sr
        return 0.5 * np.sin(2 * np.pi * freq * t)

    def test_detect_a4(self):
        """Detect A4 (440 Hz) = ptAKF tone 33."""
        audio = self._generate_sine(440.0, duration=0.5)
        detector = PitchDetector(sample_rate=44100)
        results = detector.detect_all(audio)

        # Check that at least some frames detect tone 33 (A4)
        tones = [r["tone"] for r in results if r["tone"] >= 0]
        assert len(tones) > 0
        # Median should be 33 (A4)
        median_tone = sorted(tones)[len(tones) // 2]
        assert abs(median_tone - 33) <= 1, f"Expected ~33 (A4), got {median_tone}"

    def test_detect_e4(self):
        """Detect E4 (329.63 Hz) = ptAKF tone 28."""
        audio = self._generate_sine(329.63, duration=0.5)
        detector = PitchDetector(sample_rate=44100)
        results = detector.detect_all(audio)

        tones = [r["tone"] for r in results if r["tone"] >= 0]
        assert len(tones) > 0
        median_tone = sorted(tones)[len(tones) // 2]
        assert abs(median_tone - 28) <= 1, f"Expected ~28 (E4), got {median_tone}"

    def test_silence_returns_unvoiced(self):
        """Silence should return unvoiced frames."""
        audio = np.zeros(44100)
        detector = PitchDetector(sample_rate=44100)
        results = detector.detect_all(audio)

        for r in results:
            assert r["tone"] == -1

    def test_low_volume_threshold(self):
        """Very quiet audio should be filtered by volume threshold."""
        audio = self._generate_sine(440.0) * 0.001  # Very quiet
        detector = PitchDetector(sample_rate=44100, volume_threshold=0.01)
        results = detector.detect_all(audio)

        # Should mostly be unvoiced due to volume gate
        unvoiced = sum(1 for r in results if r["tone"] == -1)
        assert unvoiced == len(results)

    def test_frame_timing(self):
        """Frame times should be correctly spaced."""
        audio = self._generate_sine(440.0, duration=1.0)
        detector = PitchDetector(sample_rate=44100)
        results = detector.detect_all(audio, hop_size=1024)

        if len(results) >= 2:
            dt = results[1]["time"] - results[0]["time"]
            expected_dt = 1024 / 44100
            assert abs(dt - expected_dt) < 1e-6

    def test_confidence_nonzero_for_clean_signal(self):
        """Clean sine wave should have non-zero confidence."""
        audio = self._generate_sine(440.0, duration=0.5)
        detector = PitchDetector(sample_rate=44100)
        results = detector.detect_all(audio)

        voiced = [r for r in results if r["tone"] >= 0]
        if voiced:
            avg_conf = np.mean([r["confidence"] for r in voiced])
            assert avg_conf > 0.1
