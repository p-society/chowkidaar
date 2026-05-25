"""
Fetches upcoming contests from Codeforces, LeetCode, and CodeChef.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List
import requests
import asyncio
import logging
from config import CLIST_USERNAME, CLIST_API_KEY

logger = logging.getLogger(__name__)

@dataclass
class UpcomingContest:
    platform: str
    name: str
    url: str
    start_time: datetime
    duration: timedelta
    requires_registration: bool = False

def fetch_clist_upcoming() -> List[UpcomingContest]:
    if not CLIST_USERNAME or not CLIST_API_KEY:
        logger.error("CLIST credentials are not set in config.")
        return []

    headers = {
        'Authorization': f'ApiKey {CLIST_USERNAME}:{CLIST_API_KEY}'
    }
    
    # We want contests starting from now
    now = datetime.now(timezone.utc)
    now_str = now.strftime('%Y-%m-%dT%H:%M:%S')

    params = {
        'resource__regex': 'codeforces.com|leetcode.com|codechef.com',
        'start__gte': now_str,
        'order_by': 'start',
        'limit': 50
    }

    try:
        resp = requests.get('https://clist.by:443/api/v4/contest/', headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        contests = []
        for c in data.get('objects', []):
            platform_raw = c.get('resource')
            platform_map = {
                'codeforces.com': 'Codeforces',
                'leetcode.com': 'LeetCode',
                'codechef.com': 'CodeChef'
            }
            platform = platform_map.get(platform_raw, platform_raw)
            
            # Start time is in UTC ISO format like '2026-05-30T14:35:00'
            start_str = c.get('start')
            try:
                start_time = datetime.fromisoformat(start_str)
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
                
            duration_secs = int(c.get('duration', 0))
            
            contests.append(UpcomingContest(
                platform=platform,
                name=c.get('event', 'Unknown Contest'),
                url=c.get('href', ''),
                start_time=start_time,
                duration=timedelta(seconds=duration_secs),
                requires_registration=True # Safe default for CF/LC
            ))
            
        return contests
    except Exception as e:
        logger.error(f"Error fetching Clist contests: {e}")
        return []

async def fetch_all_upcoming_contests() -> List[UpcomingContest]:
    loop = asyncio.get_running_loop()
    all_contests = await loop.run_in_executor(None, fetch_clist_upcoming)
    return all_contests
