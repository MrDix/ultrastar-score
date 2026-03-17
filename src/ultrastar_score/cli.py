"""CLI entry point for ultrastar-score."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from ultrastar_score.parser import parse_ultrastar
from ultrastar_score.scoring import score_song, Difficulty, SongScore


@click.command()
@click.argument("txt_file", type=click.Path(exists=True))
@click.argument("audio_file", type=click.Path(exists=True))
@click.option(
    "-d", "--difficulty",
    type=click.Choice(["easy", "medium", "hard"], case_sensitive=False),
    default="easy",
    help="Scoring difficulty (easy=±2 ST, medium=±1 ST, hard=exact).",
)
@click.option(
    "-t", "--tolerance",
    type=float,
    default=None,
    help="Custom pitch tolerance in semitones (overrides --difficulty).",
)
@click.option(
    "--volume-threshold",
    type=float,
    default=0.01,
    help="Minimum volume for pitch detection (0.0-1.0).",
)
@click.option(
    "--json-output", "json_out",
    is_flag=True,
    help="Output results as JSON.",
)
@click.option(
    "--per-line",
    is_flag=True,
    help="Show per-line score breakdown.",
)
@click.option(
    "--per-note",
    is_flag=True,
    help="Show per-note score breakdown.",
)
@click.version_option()
def main(
    txt_file: str,
    audio_file: str,
    difficulty: str,
    tolerance: float | None,
    volume_threshold: float,
    json_out: bool,
    per_line: bool,
    per_note: bool,
) -> None:
    """Score an UltraStar song file against vocal audio.

    TXT_FILE is the UltraStar .txt song file.
    AUDIO_FILE is the vocal audio track (WAV, OGG, FLAC, MP3).

    \b
    Examples:
      uscore song.txt vocals.wav
      uscore song.txt vocals.ogg --difficulty hard
      uscore song.txt vocals.wav --tolerance 1.5
      uscore song.txt vocals.wav --json
    """
    diff = Difficulty[difficulty.upper()]

    # Parse song
    song = parse_ultrastar(txt_file)
    if not song.all_notes:
        click.echo("Error: No notes found in song file.", err=True)
        sys.exit(1)

    tol_display = f"±{tolerance} ST (custom)" if tolerance is not None else f"±{diff.tolerance} ST ({diff.name})"

    if not json_out:
        click.echo(f"Scoring: {song.artist} - {song.title}")
        click.echo(f"Difficulty: {tol_display}")
        click.echo(f"Notes: {len(song.all_notes)}, Lines: {len(song.lines)}")
        click.echo("Detecting pitch...")

    # Score
    result = score_song(song, audio_file, diff, tolerance, volume_threshold)

    if json_out:
        _output_json(result, song, tol_display, per_line, per_note)
    else:
        _output_text(result, song, tol_display, per_line, per_note)


def _output_text(result: SongScore, song, tol_display: str, per_line: bool, per_note: bool) -> None:
    click.echo()
    click.echo(f"{'='*50}")
    click.echo(f"  Score: {result.total:.0f} / 10000  ({result.percentage:.1f}%)")
    click.echo(f"  Rating: {result.rating}")
    click.echo(f"{'='*50}")
    click.echo()
    click.echo(f"  Notes:  {result.score_notes:.0f}")
    click.echo(f"  Golden: {result.score_golden:.0f}")
    click.echo(f"  Line:   {result.score_line_bonus:.0f}")
    click.echo()
    click.echo(f"  Beats hit: {result.notes_hit}/{result.notes_total} ({result.hit_ratio:.1%})")

    if per_line:
        click.echo()
        click.echo("Per-line breakdown:")
        for i, ls in enumerate(result.line_scores):
            text = " ".join(ns.note.text for ns in ls.note_scores)[:60]
            click.echo(
                f"  Line {i+1:3d}: {ls.perfection:5.1%} "
                f"({ls.points_earned:.0f}/{ls.points_possible:.0f}) "
                f"bonus={ls.line_bonus:.0f}  {text}"
            )

    if per_note:
        click.echo()
        click.echo("Per-note breakdown:")
        for ls in result.line_scores:
            for ns in ls.note_scores:
                n = ns.note
                status = f"{ns.beats_hit}/{ns.beats_total}" if ns.beats_total > 0 else "free"
                click.echo(
                    f"  [{n.note_type}] beat={n.start_beat:5d} dur={n.duration:3d} "
                    f"pitch={n.pitch:3d} hit={status:>5s}  {n.text}"
                )


def _output_json(result: SongScore, song, tol_display: str, per_line: bool, per_note: bool) -> None:
    data = {
        "score": round(result.total),
        "percentage": round(result.percentage, 2),
        "rating": result.rating,
        "difficulty": result.difficulty.name,
        "tolerance": tol_display,
        "components": {
            "notes": round(result.score_notes),
            "golden": round(result.score_golden),
            "line_bonus": round(result.score_line_bonus),
        },
        "beats_hit": result.notes_hit,
        "beats_total": result.notes_total,
        "hit_ratio": round(result.hit_ratio, 4),
        "song": {
            "title": song.title,
            "artist": song.artist,
            "bpm": song.bpm,
            "notes": len(song.all_notes),
            "lines": len(song.lines),
        },
    }

    if per_line:
        data["lines"] = [
            {
                "index": i + 1,
                "perfection": round(ls.perfection, 4),
                "points_earned": round(ls.points_earned),
                "points_possible": round(ls.points_possible),
                "line_bonus": round(ls.line_bonus),
            }
            for i, ls in enumerate(result.line_scores)
        ]

    if per_note:
        data["notes_detail"] = [
            {
                "type": ns.note.note_type,
                "start_beat": ns.note.start_beat,
                "duration": ns.note.duration,
                "pitch": ns.note.pitch,
                "beats_hit": ns.beats_hit,
                "beats_total": ns.beats_total,
                "text": ns.note.text,
            }
            for ls in result.line_scores
            for ns in ls.note_scores
        ]

    click.echo(json.dumps(data, indent=2))
