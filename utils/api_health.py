"""
API Health Checks — Lightweight pulse checks for Codeforces and LeetCode.

Used by the queue processor to decide whether to attempt draining the
submission queue. Each check hits a cheap, public endpoint with a short
timeout to avoid blocking the event loop.
"""

import requests
import logging

logger = logging.getLogger(__name__)


def check_codeforces_pulse() -> bool:
    """Hit a cheap Codeforces endpoint; return True if the API is healthy."""
    try:
        r = requests.get(
            "https://codeforces.com/api/user.info?handles=tourist",
            timeout=5,
        )
        return r.status_code == 200
    except Exception as e:
        logger.warning(f"Codeforces pulse check failed: {e}")
        return False


def check_leetcode_pulse() -> bool:
    """Hit a lightweight LeetCode GraphQL query; return True if healthy."""
    query = {
        "operationName": "healthCheck",
        "variables": {"username": "leetcode"},
        "query": """
        query healthCheck($username: String!) {
            matchedUser(username: $username) {
                username
            }
        }
        """,
    }
    try:
        r = requests.post(
            "https://leetcode.com/graphql",
            json=query,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=5,
        )
        return r.status_code == 200
    except Exception as e:
        logger.warning(f"LeetCode pulse check failed: {e}")
        return False
