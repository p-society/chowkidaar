"""
Standalone smoke test for the LeetCode + Codeforces contest API clients.

No DB required. Hits the real APIs and prints what comes back.

Usage:
    uv run --python 3.12 scripts/test_contest_apis.py <lc_handle> <cf_handle>
    uv run --python 3.12 scripts/test_contest_apis.py neal_wu tourist

Optional: filter to a date window
    uv run --python 3.12 scripts/test_contest_apis.py neal_wu tourist 2025-06-01 2025-06-26
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

# Allow `import integrations.*` from this script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.leetcode_contests import (
    LeetCodeAPIError,
    fetch_user_contests as fetch_lc_contests,
)
from integrations.codeforces_contests import (
    CodeforcesAPIError,
    fetch_user_contests as fetch_cf_contests,
)


def _parse_date(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2

    lc_handle = sys.argv[1]
    cf_handle = sys.argv[2]
    since = _parse_date(sys.argv[3]) if len(sys.argv) > 3 else None
    until = _parse_date(sys.argv[4]) if len(sys.argv) > 4 else None

    if since or until:
        print(f"Date window: {since} -> {until}")
        print()

    print(f"--- LeetCode: {lc_handle} ---")
    try:
        lc = fetch_lc_contests(lc_handle, since=since, until=until)
        if not lc:
            print("  (no attended contests in window)")
        for entry in lc:
            print(" ", entry)
    except LeetCodeAPIError as e:
        print(f"  LeetCode error: {e}")
    except Exception as e:
        print(f"  Unexpected error: {type(e).__name__}: {e}")

    print()
    print(f"--- Codeforces: {cf_handle} ---")
    try:
        cf = fetch_cf_contests(cf_handle, since=since, until=until)
        if not cf:
            print("  (no rated contests in window)")
        for entry in cf:
            print(" ", entry)
    except CodeforcesAPIError as e:
        print(f"  Codeforces error: {e}")
    except Exception as e:
        print(f"  Unexpected error: {type(e).__name__}: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
