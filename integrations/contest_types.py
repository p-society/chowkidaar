"""
Shared types for the contest-API integrations.

Both leetcode_contests and codeforces_contests return lists of ContestEntry
so the poller can treat them uniformly.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

Platform = Literal["leetcode", "codeforces"]


@dataclass
class ContestEntry:
    platform: Platform
    contest_id: str
    contest_name: str
    contest_date: datetime         # UTC, timezone-aware
    rank: Optional[int]            # final placing; may be None if not yet rated
    rating_delta: Optional[int]    # newRating - oldRating; may be None
    attended: bool                 # for LC, this can be False (registered but no-show)

    def __str__(self) -> str:
        delta = f"{self.rating_delta:+d}" if self.rating_delta is not None else "  —"
        rank = str(self.rank) if self.rank is not None else "—"
        return (
            f"[{self.platform:10}] {self.contest_date.date()}  "
            f"rank={rank:>6}  delta={delta:>4}  {self.contest_name}"
        )
