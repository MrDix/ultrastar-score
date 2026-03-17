"""USDX-compatible scoring engine for UltraStar songs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

import numpy as np

from ultrastar_score.parser import UltraStarSong, Note
from ultrastar_score.pitch import PitchDetector
from ultrastar_score.audio import load_audio


class Difficulty(IntEnum):
    """USDX difficulty levels with pitch tolerance in semitones."""
    EASY = 0    # ±2 semitones
    MEDIUM = 1  # ±1 semitone
    HARD = 2    # exact match

    @property
    def tolerance(self) -> int:
        """Pitch tolerance in semitones."""
        return 2 - self.value


@dataclass
class NoteScore:
    """Scoring result for a single note."""
    note: Note
    beats_hit: int = 0
    beats_total: int = 0
    detected_tones: list[int] = field(default_factory=list)

    @property
    def hit_ratio(self) -> float:
        return self.beats_hit / self.beats_total if self.beats_total > 0 else 0.0


@dataclass
class LineScore:
    """Scoring result for a line (sentence)."""
    note_scores: list[NoteScore] = field(default_factory=list)
    points_earned: float = 0.0
    points_possible: float = 0.0
    line_bonus: float = 0.0

    @property
    def perfection(self) -> float:
        return self.points_earned / self.points_possible if self.points_possible > 0 else 0.0


@dataclass
class SongScore:
    """Complete scoring result for a song."""
    line_scores: list[LineScore] = field(default_factory=list)
    difficulty: Difficulty = Difficulty.EASY
    custom_tolerance: Optional[float] = None

    # USDX score components (0-10000 scale)
    score_notes: float = 0.0      # Normal note points (part of 9000)
    score_golden: float = 0.0     # Golden note points (part of 9000)
    score_line_bonus: float = 0.0 # Line bonus (up to 1000)

    @property
    def total(self) -> float:
        """Total score (0-10000)."""
        return self.score_notes + self.score_golden + self.score_line_bonus

    @property
    def percentage(self) -> float:
        """Score as percentage (0-100)."""
        return self.total / 100.0

    @property
    def notes_hit(self) -> int:
        return sum(ns.beats_hit for ls in self.line_scores for ns in ls.note_scores)

    @property
    def notes_total(self) -> int:
        return sum(ns.beats_total for ls in self.line_scores for ns in ls.note_scores)

    @property
    def hit_ratio(self) -> float:
        return self.notes_hit / self.notes_total if self.notes_total > 0 else 0.0

    @property
    def rating(self) -> str:
        """Human-readable rating based on score."""
        s = self.total
        if s >= 9500:
            return "Superstar"
        elif s >= 8000:
            return "Fantastic"
        elif s >= 5000:
            return "Good"
        elif s >= 2000:
            return "OK"
        else:
            return "Poor"


MAX_SONG_SCORE = 10000
MAX_SONG_LINE_BONUS = 1000
MAX_SONG_POINTS = MAX_SONG_SCORE - MAX_SONG_LINE_BONUS  # 9000


def score_song(
    song: UltraStarSong,
    audio_path: str,
    difficulty: Difficulty = Difficulty.EASY,
    tolerance: Optional[float] = None,
    volume_threshold: float = 0.01,
) -> SongScore:
    """Score a song by comparing its notes against detected pitch from audio.

    Args:
        song: Parsed UltraStar song.
        audio_path: Path to vocal audio file (WAV, OGG, FLAC, MP3).
        difficulty: USDX difficulty level (Easy/Medium/Hard).
        tolerance: Custom tolerance in semitones (overrides difficulty).
        volume_threshold: Minimum volume for pitch detection (0.0-1.0).

    Returns:
        SongScore with detailed per-note and per-line results.
    """
    # Load audio at 44.1 kHz for ptAKF
    audio = load_audio(audio_path)

    # Detect pitch for every frame
    detector = PitchDetector(sample_rate=44100, volume_threshold=volume_threshold)
    pitch_frames = detector.detect_all(audio)

    # Build a time-indexed lookup: time_sec -> tone
    # pitch_frames are evenly spaced at HOP_SIZE / sample_rate intervals
    hop_sec = PitchDetector.HOP_SIZE if hasattr(PitchDetector, 'HOP_SIZE') else 1024
    hop_sec = hop_sec / 44100.0

    # Effective tolerance
    tol = tolerance if tolerance is not None else float(difficulty.tolerance)

    # Pre-compute score value for point-per-beat calculation
    track_score_value = song.score_value
    if track_score_value <= 0:
        return SongScore(difficulty=difficulty, custom_tolerance=tolerance)

    points_per_beat = MAX_SONG_POINTS / track_score_value
    num_non_empty_lines = song.non_empty_lines

    result = SongScore(difficulty=difficulty, custom_tolerance=tolerance)
    score_accumulated = 0.0

    for line in song.lines:
        line_score = LineScore()
        line_start_score = score_accumulated

        # Compute max possible points for this line
        line_max = sum(n.duration * n.score_factor * points_per_beat for n in line.notes)

        for note in line.notes:
            ns = NoteScore(note=note, beats_total=note.duration)

            if note.is_freestyle:
                line_score.note_scores.append(ns)
                continue

            # For each beat of this note, check the detected pitch
            for beat_offset in range(note.duration):
                beat = note.start_beat + beat_offset
                time_sec = song.beat_to_seconds(beat)

                # Find the closest pitch frame
                frame_idx = int(round(time_sec / hop_sec))
                if frame_idx < 0 or frame_idx >= len(pitch_frames):
                    continue

                detected = pitch_frames[frame_idx]
                detected_tone = detected["tone"]

                if detected_tone < 0:
                    # Unvoiced frame - miss
                    ns.detected_tones.append(-1)
                    continue

                ns.detected_tones.append(detected_tone)

                # Rap notes always hit (pitch ignored)
                if note.is_rap:
                    ns.beats_hit += 1
                    earned = points_per_beat * note.score_factor
                    if note.is_golden:
                        result.score_golden += earned
                    else:
                        result.score_notes += earned
                    score_accumulated += earned
                    continue

                # Octave folding (USDX style)
                expected = _normalize_pitch(note.pitch, song.is_v1_2_0)
                diff = detected_tone - expected
                while diff > 6:
                    diff -= 12
                while diff < -6:
                    diff += 12

                # Check tolerance
                if abs(diff) <= tol:
                    ns.beats_hit += 1
                    earned = points_per_beat * note.score_factor
                    if note.is_golden:
                        result.score_golden += earned
                    else:
                        result.score_notes += earned
                    score_accumulated += earned

            line_score.note_scores.append(ns)

        # Line bonus (USDX formula)
        line_earned = score_accumulated - line_start_score
        if line_max > 2 and num_non_empty_lines > 0:
            perfection = min(1.0, max(0.0, line_earned / (line_max - 2)))
            bonus_per_line = MAX_SONG_LINE_BONUS / num_non_empty_lines
            line_score.line_bonus = bonus_per_line * perfection
            result.score_line_bonus += line_score.line_bonus

        line_score.points_earned = line_earned
        line_score.points_possible = line_max
        result.line_scores.append(line_score)

    return result


def _normalize_pitch(pitch: int, is_v1_2_0: bool) -> int:
    """Convert UltraStar pitch to ptAKF tone index (0=C2).

    Legacy format: pitch = raw MIDI note number
    v1.2.0 format: pitch = MIDI - 48

    ptAKF tone: 0 = C2 (MIDI 36)
    """
    if is_v1_2_0:
        # pitch = MIDI - 48, so MIDI = pitch + 48
        midi = pitch + 48
    else:
        # pitch = raw MIDI
        midi = pitch

    # Convert MIDI to ptAKF tone (0 = C2 = MIDI 36)
    # Keep full range — octave folding happens in the scoring loop
    return midi - 36


def score_song_from_files(
    txt_path: str,
    audio_path: str,
    difficulty: Difficulty = Difficulty.EASY,
    tolerance: Optional[float] = None,
    volume_threshold: float = 0.01,
) -> SongScore:
    """Convenience function: parse TXT and score against audio in one call."""
    from ultrastar_score.parser import parse_ultrastar
    song = parse_ultrastar(txt_path)
    return score_song(song, audio_path, difficulty, tolerance, volume_threshold)
