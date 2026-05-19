"""
External-platform integrations (LeetCode, Codeforces, ...).

Each module exposes pure functions that take a handle and return a list of
ContestEntry dataclasses. No database access here — the poller is responsible
for persisting results.
"""
