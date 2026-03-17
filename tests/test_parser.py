"""Tests for UltraStar TXT parser."""

import textwrap
from pathlib import Path

import pytest

from ultrastar_score.parser import parse_ultrastar, Note, UltraStarSong


@pytest.fixture
def simple_song(tmp_path):
    """Create a simple UltraStar song file."""
    content = textwrap.dedent("""\
        #TITLE:Test Song
        #ARTIST:Test Artist
        #BPM:300
        #GAP:5000
        #MP3:test.mp3
        : 0 4 60 Hello
        : 4 2 62  world
        * 8 4 64  gol
        - 14
        : 16 4 60 Se
        F 20 2 0  cond
        : 24 4 65  line
        E
    """)
    p = tmp_path / "test.txt"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def v120_song(tmp_path):
    """Create a v1.2.0 format song file."""
    content = textwrap.dedent("""\
        #VERSION:1.2.0
        #TITLE:V120 Song
        #ARTIST:Test
        #BPM:200
        #GAP:1000
        : 0 4 12 Test
        : 4 4 14  note
        E
    """)
    p = tmp_path / "v120.txt"
    p.write_text(content, encoding="utf-8")
    return p


def test_parse_metadata(simple_song):
    song = parse_ultrastar(simple_song)
    assert song.title == "Test Song"
    assert song.artist == "Test Artist"
    assert song.bpm == 300.0
    assert song.gap == 5000.0
    assert song.audio == "test.mp3"


def test_parse_notes(simple_song):
    song = parse_ultrastar(simple_song)
    notes = song.all_notes
    assert len(notes) == 6

    # First note
    assert notes[0].note_type == ":"
    assert notes[0].start_beat == 0
    assert notes[0].duration == 4
    assert notes[0].pitch == 60
    assert notes[0].text == "Hello"

    # Golden note
    assert notes[2].note_type == "*"
    assert notes[2].is_golden
    assert notes[2].score_factor == 2

    # Freestyle note
    assert notes[4].note_type == "F"
    assert notes[4].is_freestyle
    assert notes[4].score_factor == 0


def test_parse_lines(simple_song):
    song = parse_ultrastar(simple_song)
    assert len(song.lines) == 2
    assert len(song.lines[0].notes) == 3
    assert len(song.lines[1].notes) == 3


def test_score_value(simple_song):
    song = parse_ultrastar(simple_song)
    # Line 1: normal(4*1) + normal(2*1) + golden(4*2) = 4+2+8 = 14
    assert song.lines[0].score_value == 14
    # Line 2: normal(4*1) + freestyle(0) + normal(4*1) = 4+0+4 = 8
    assert song.lines[1].score_value == 8
    assert song.score_value == 22


def test_beat_to_seconds(simple_song):
    song = parse_ultrastar(simple_song)
    # GAP = 5000ms = 5.0s
    # BPM = 300, so 1 beat = 60/(300*4) = 0.05s
    assert song.beat_to_seconds(0) == pytest.approx(5.0)
    assert song.beat_to_seconds(20) == pytest.approx(6.0)


def test_v120_format(v120_song):
    song = parse_ultrastar(v120_song)
    assert song.is_v1_2_0
    assert song.version == "1.2.0"


def test_non_empty_lines(simple_song):
    song = parse_ultrastar(simple_song)
    assert song.non_empty_lines == 2


def test_comma_decimal_separator(tmp_path):
    """Test BPM/GAP with comma as decimal separator."""
    content = "#BPM:300,5\n#GAP:1000,25\n: 0 4 60 Test\nE\n"
    p = tmp_path / "comma.txt"
    p.write_text(content, encoding="utf-8")
    song = parse_ultrastar(p)
    assert song.bpm == 300.5
    assert song.gap == 1000.25


def test_rap_notes(tmp_path):
    """Test rap and rap-golden note types."""
    content = "#BPM:300\n#GAP:0\nR 0 4 60 Rap\nG 4 4 62 RapGold\nE\n"
    p = tmp_path / "rap.txt"
    p.write_text(content, encoding="utf-8")
    song = parse_ultrastar(p)
    notes = song.all_notes
    assert notes[0].is_rap
    assert not notes[0].is_golden
    assert notes[0].score_factor == 1
    assert notes[1].is_rap
    assert notes[1].is_golden
    assert notes[1].score_factor == 2


def test_utf8_bom(tmp_path):
    """Test UTF-8 BOM handling."""
    content = "\ufeff#TITLE:BOM Song\n#BPM:300\n#GAP:0\n: 0 4 60 Test\nE\n"
    p = tmp_path / "bom.txt"
    p.write_bytes(content.encode("utf-8-sig"))
    song = parse_ultrastar(p)
    assert song.title == "BOM Song"


def test_cp1252_encoding(tmp_path):
    """Test CP1252 encoded file."""
    content = "#TITLE:Über Nacht\n#BPM:300\n#GAP:0\n: 0 4 60 Test\nE\n"
    p = tmp_path / "cp1252.txt"
    p.write_bytes(content.encode("cp1252"))
    song = parse_ultrastar(p)
    assert song.title == "Über Nacht"
