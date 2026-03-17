"""Tests for USDX scoring engine."""

import textwrap
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from ultrastar_score.parser import parse_ultrastar, Note, Line, UltraStarSong
from ultrastar_score.scoring import (
    score_song,
    Difficulty,
    SongScore,
    _normalize_pitch,
    MAX_SONG_POINTS,
    MAX_SONG_LINE_BONUS,
)


class TestDifficulty:
    def test_easy_tolerance(self):
        assert Difficulty.EASY.tolerance == 2

    def test_medium_tolerance(self):
        assert Difficulty.MEDIUM.tolerance == 1

    def test_hard_tolerance(self):
        assert Difficulty.HARD.tolerance == 0


class TestNormalizePitch:
    def test_legacy_c4(self):
        # MIDI 60 (C4) -> ptAKF tone 24 (C4 is 2 octaves above C2)
        assert _normalize_pitch(60, is_v1_2_0=False) == 24

    def test_v120_c4(self):
        # v1.2.0: pitch 12, MIDI = 12+48 = 60 -> ptAKF tone 24
        assert _normalize_pitch(12, is_v1_2_0=True) == 24

    def test_legacy_a4(self):
        # MIDI 69 (A4) -> ptAKF tone 33
        assert _normalize_pitch(69, is_v1_2_0=False) == 33

    def test_v120_matches_legacy(self):
        # Same MIDI note should produce same ptAKF tone
        for midi in range(36, 93):
            legacy = _normalize_pitch(midi, is_v1_2_0=False)
            v120 = _normalize_pitch(midi - 48, is_v1_2_0=True)
            assert legacy == v120, f"MIDI {midi}: legacy={legacy}, v120={v120}"


class TestSongScore:
    def test_percentage(self):
        s = SongScore()
        s.score_notes = 4500
        s.score_golden = 2000
        s.score_line_bonus = 500
        assert s.percentage == pytest.approx(70.0)

    def test_rating_superstar(self):
        s = SongScore()
        s.score_notes = 8000
        s.score_line_bonus = 1000
        s.score_golden = 500
        assert s.rating == "Superstar"

    def test_rating_poor(self):
        s = SongScore()
        s.score_notes = 500
        assert s.rating == "Poor"


class TestScoring:
    """Integration tests using mocked pitch detection."""

    @staticmethod
    def _make_song(bpm=300, gap=0, notes=None):
        """Create a test song."""
        song = UltraStarSong(bpm=bpm, gap=gap)
        line = Line()
        for n in (notes or []):
            line.notes.append(n)
        song.lines = [line]
        return song

    def test_perfect_score_single_note(self, tmp_path):
        """Perfect pitch on a single note should score 9000 + line bonus."""
        song = self._make_song(
            bpm=300, gap=0,
            notes=[
                Note(":", 0, 8, 60, "Test"),  # MIDI 60 -> ptAKF tone 24
            ]
        )

        # Mock pitch detector to always return the correct tone
        def mock_detect(audio, hop_size=1024):
            return [{"tone": 24, "frequency": 0, "confidence": 1.0, "time": i * 1024/44100}
                    for i in range(int(len(audio) / 1024) + 1)]

        with patch("ultrastar_score.scoring.load_audio") as mock_load, \
             patch("ultrastar_score.scoring.PitchDetector") as MockDetector:
            mock_load.return_value = np.zeros(44100 * 2)  # 2 seconds
            instance = MockDetector.return_value
            instance.detect_all.side_effect = mock_detect

            result = score_song(song, "dummy.wav", Difficulty.HARD)

        # All beats hit → 9000 note score + line bonus
        assert result.score_notes == pytest.approx(9000, abs=100)
        assert result.total > 9000

    def test_freestyle_not_scored(self, tmp_path):
        """Freestyle notes should contribute 0 points."""
        song = self._make_song(
            bpm=300, gap=0,
            notes=[
                Note("F", 0, 4, 60, "Free"),
                Note(":", 4, 4, 62, " scored"),
            ]
        )

        # Only 4 scorable beats (the normal note)
        assert song.score_value == 4

    def test_golden_worth_double(self):
        """Golden notes should have double score factor."""
        song = self._make_song(
            bpm=300, gap=0,
            notes=[
                Note(":", 0, 4, 60, "Normal"),
                Note("*", 4, 4, 60, " Golden"),
            ]
        )
        # normal: 4*1=4, golden: 4*2=8
        assert song.score_value == 12

    def test_tolerance_easy_allows_2st(self):
        """Easy difficulty should accept pitches within ±2 semitones."""
        song = self._make_song(
            bpm=300, gap=0,
            notes=[Note(":", 0, 4, 60, "Test")]  # expects ptAKF tone 24
        )

        # Return tone 26 (2 semitones off) - should hit on Easy
        def mock_detect(audio, hop_size=1024):
            return [{"tone": 26, "frequency": 0, "confidence": 1.0, "time": i * 1024/44100}
                    for i in range(int(len(audio) / 1024) + 1)]

        with patch("ultrastar_score.scoring.load_audio") as mock_load, \
             patch("ultrastar_score.scoring.PitchDetector") as MockDetector:
            mock_load.return_value = np.zeros(44100)
            instance = MockDetector.return_value
            instance.detect_all.side_effect = mock_detect

            result_easy = score_song(song, "dummy.wav", Difficulty.EASY)
            result_hard = score_song(song, "dummy.wav", Difficulty.HARD)

        assert result_easy.notes_hit > 0
        assert result_hard.notes_hit == 0

    def test_rap_always_hits(self):
        """Rap notes should always count as hit regardless of pitch."""
        song = self._make_song(
            bpm=300, gap=0,
            notes=[Note("R", 0, 4, 60, "Rap")]
        )

        # Return completely wrong pitch
        def mock_detect(audio, hop_size=1024):
            return [{"tone": 0, "frequency": 0, "confidence": 1.0, "time": i * 1024/44100}
                    for i in range(int(len(audio) / 1024) + 1)]

        with patch("ultrastar_score.scoring.load_audio") as mock_load, \
             patch("ultrastar_score.scoring.PitchDetector") as MockDetector:
            mock_load.return_value = np.zeros(44100)
            instance = MockDetector.return_value
            instance.detect_all.side_effect = mock_detect

            result = score_song(song, "dummy.wav", Difficulty.HARD)

        assert result.notes_hit > 0

    def test_octave_folding(self):
        """Pitch detection one octave off should still match (octave folding)."""
        song = self._make_song(
            bpm=300, gap=0,
            notes=[Note(":", 0, 4, 60, "Test")]  # expects ptAKF tone 24
        )

        # Return tone 12 (one octave lower = C3 instead of C4) - should fold
        def mock_detect(audio, hop_size=1024):
            return [{"tone": 12, "frequency": 0, "confidence": 1.0, "time": i * 1024/44100}
                    for i in range(int(len(audio) / 1024) + 1)]

        with patch("ultrastar_score.scoring.load_audio") as mock_load, \
             patch("ultrastar_score.scoring.PitchDetector") as MockDetector:
            mock_load.return_value = np.zeros(44100)
            instance = MockDetector.return_value
            instance.detect_all.side_effect = mock_detect

            result = score_song(song, "dummy.wav", Difficulty.HARD)

        # After octave folding, diff = 12 -> folded to 0 -> exact match
        assert result.notes_hit > 0
