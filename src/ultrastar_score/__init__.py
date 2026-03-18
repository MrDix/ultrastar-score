"""ultrastar-score: Score UltraStar karaoke files against vocal audio."""

__version__ = "0.2.0"

from ultrastar_score.scoring import score_song, SongScore, Difficulty
from ultrastar_score.parser import parse_ultrastar

__all__ = ["score_song", "SongScore", "Difficulty", "parse_ultrastar"]
