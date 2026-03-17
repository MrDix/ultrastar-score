"""UltraStar TXT file parser."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Note:
    """A single note in an UltraStar song."""
    note_type: str          # ":" (normal), "*" (golden), "F" (freestyle), "R" (rap), "G" (rap golden)
    start_beat: int         # Start beat
    duration: int           # Duration in beats
    pitch: int              # MIDI-like pitch value
    text: str               # Lyric text

    @property
    def is_scorable(self) -> bool:
        return self.note_type in (":", "*", "R", "G")

    @property
    def is_golden(self) -> bool:
        return self.note_type in ("*", "G")

    @property
    def is_rap(self) -> bool:
        return self.note_type in ("R", "G")

    @property
    def is_freestyle(self) -> bool:
        return self.note_type == "F"

    @property
    def score_factor(self) -> int:
        """USDX score factor: 0=freestyle, 1=normal/rap, 2=golden/rapgolden."""
        factors = {":": 1, "*": 2, "F": 0, "R": 1, "G": 2}
        return factors.get(self.note_type, 0)


@dataclass
class Line:
    """A line (sentence) of notes."""
    notes: list[Note] = field(default_factory=list)

    @property
    def score_value(self) -> int:
        """Total weighted duration for this line."""
        return sum(n.duration * n.score_factor for n in self.notes)


@dataclass
class UltraStarSong:
    """Parsed UltraStar song with metadata and notes."""
    # Required metadata
    bpm: float = 0.0
    gap: float = 0.0  # in milliseconds

    # Optional metadata
    title: str = ""
    artist: str = ""
    version: str = ""
    audio: str = ""

    # Notes organized by lines
    lines: list[Line] = field(default_factory=list)

    @property
    def all_notes(self) -> list[Note]:
        return [n for line in self.lines for n in line.notes]

    @property
    def score_value(self) -> int:
        """Total weighted duration across all notes (USDX Track.ScoreValue)."""
        return sum(line.score_value for line in self.lines)

    @property
    def non_empty_lines(self) -> int:
        """Number of lines with at least one scorable note."""
        return sum(1 for line in self.lines if line.score_value > 0)

    def beat_to_seconds(self, beat: int) -> float:
        """Convert a beat number to time in seconds."""
        if self.bpm <= 0:
            return 0.0
        # UltraStar BPM is "quarter beats per minute" × 4
        # so actual BPM = bpm_value * 4 for conversion
        # Time = GAP/1000 + beat / (BPM * 4 / 60)
        return self.gap / 1000.0 + beat * 60.0 / (self.bpm * 4.0)

    @property
    def is_v1_2_0(self) -> bool:
        """Check if this is a v1.2.0 format file (MIDI - 48 pitches)."""
        return self.version.startswith("1.")


def parse_ultrastar(path: str | Path) -> UltraStarSong:
    """Parse an UltraStar TXT file.

    Handles both legacy format (raw MIDI pitches) and v1.2.0 format (MIDI - 48).
    """
    path = Path(path)
    text = _read_file(path)

    song = UltraStarSong()
    current_line = Line()
    song.lines.append(current_line)

    for raw_line in text.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        # Metadata tags
        if raw_line.startswith("#"):
            _parse_tag(raw_line, song)
            continue

        # End of song
        if raw_line.startswith("E"):
            break

        # Line break
        if raw_line.startswith("-"):
            current_line = Line()
            song.lines.append(current_line)
            continue

        # Note line: TYPE START DURATION PITCH TEXT
        m = re.match(r'^([:\*FRG])\s+(-?\d+)\s+(\d+)\s+(-?\d+)\s*(.*)', raw_line)
        if m:
            note = Note(
                note_type=m.group(1),
                start_beat=int(m.group(2)),
                duration=int(m.group(3)),
                pitch=int(m.group(4)),
                text=m.group(5),
            )
            current_line.notes.append(note)

    # Remove empty trailing lines
    song.lines = [l for l in song.lines if l.notes]

    return song


def _parse_tag(line: str, song: UltraStarSong) -> None:
    """Parse a #TAG:VALUE line."""
    m = re.match(r'^#(\w+):\s*(.*)', line)
    if not m:
        return

    tag = m.group(1).upper()
    value = m.group(2).strip()

    if tag == "BPM":
        # Handle comma as decimal separator
        song.bpm = float(value.replace(",", "."))
    elif tag == "GAP":
        song.gap = float(value.replace(",", "."))
    elif tag == "TITLE":
        song.title = value
    elif tag == "ARTIST":
        song.artist = value
    elif tag == "VERSION":
        song.version = value
    elif tag == "MP3" or tag == "AUDIO":
        song.audio = value


def _read_file(path: Path) -> str:
    """Read a text file, handling BOM and common encodings."""
    raw = path.read_bytes()

    # Strip UTF-8 BOM (both raw bytes and encoded forms)
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    # Also handle case where BOM was already part of the encoding
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        # UTF-16 BOM — decode directly
        return raw.decode("utf-16")

    # Try UTF-8 first, then CP1252 fallback
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            # Strip any remaining Unicode BOM character
            if text.startswith("\ufeff"):
                text = text[1:]
            return text
        except UnicodeDecodeError:
            continue

    text = raw.decode("utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    return text
