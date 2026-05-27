from typing import Any, Dict, List, Tuple

BADGES_CATALOG: List[Dict[str, Any]] = [
    # milestone
    {
        "key": "day7_done",
        "name": "Day 7 Done",
        "description": "Submitted on at least 7 days of the event",
        "category": "milestone",
        "emoji": "🥉",
        "display_priority": 10,
        "threshold": 7,
    },
    {
        "key": "day14_done",
        "name": "Day 14 Done",
        "description": "Submitted on at least 14 days of the event",
        "category": "milestone",
        "emoji": "🥈",
        "display_priority": 20,
        "threshold": 14,
    },
    {
        "key": "day25_done",
        "name": "Day 25 Done",
        "description": "Completed the full 25-day challenge",
        "category": "milestone",
        "emoji": "🥇",
        "display_priority": 30,
        "threshold": 25,
    },
    # contest
    {
        "key": "contest_participant",
        "name": "Contest Participant",
        "description": "Attended at least one LC or CF contest during the event",
        "category": "contest",
        "emoji": "🎯",
        "display_priority": 15,
    },
    {
        "key": "contest_top_100",
        "name": "Top 100",
        "description": "Finished in the top 100 of any LC or CF contest",
        "category": "contest",
        "emoji": "🌟",
        "display_priority": 25,
    },
    {
        "key": "contest_rating_climber",
        "name": "Rating Climber",
        "description": "Gained rating in at least one LC or CF contest",
        "category": "contest",
        "emoji": "📈",
        "display_priority": 18,
    },
]


def get_milestone_thresholds() -> List[Tuple[int, str]]:
    """Return milestone threshold mappings as a sorted list of tuples (threshold, badge_key)."""
    milestones = [
        (b["threshold"], b["key"])
        for b in BADGES_CATALOG
        if b["category"] == "milestone" and "threshold" in b
    ]
    milestones.sort(key=lambda x: x[0])
    return milestones


def sync_badges_to_db() -> None:
    """
    Synchronizes the python-defined badge catalog to the PostgreSQL database.
    Performs an UPSERT (INSERT ON CONFLICT UPDATE) for each badge.
    """
    import json
    import os
    from db.db import connect_to_database

    # Load event_config.json to find any user-configured badge role IDs
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "configs",
        "event_config.json",
    )
    badge_roles = {}
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                cfg = json.load(f)
                badge_roles = cfg.get("badge_roles") or {}
    except Exception as e:
        print(f"Warning: could not load badge_roles from event_config.json: {e}")

    conn = connect_to_database(purpose="Auto-Sync Badge Catalog")
    if not conn:
        print("Failed to connect to database for badge sync")
        return
    try:
        with conn.cursor() as cur:
            for b in BADGES_CATALOG:
                # Retrieve the configured Discord Role ID for this badge, if set
                role_id_raw = badge_roles.get(b["key"])
                role_id = int(role_id_raw) if role_id_raw is not None else None

                cur.execute(
                    """
                    INSERT INTO badges (key, name, description, category, emoji, display_priority, discord_role_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (key) DO UPDATE
                    SET name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        category = EXCLUDED.category,
                        emoji = EXCLUDED.emoji,
                        display_priority = EXCLUDED.display_priority,
                        discord_role_id = EXCLUDED.discord_role_id;
                    """,
                    (
                        b["key"],
                        b["name"],
                        b["description"],
                        b["category"],
                        b.get("emoji"),
                        b.get("display_priority", 0),
                        role_id,
                    ),
                )
            conn.commit()
            print(f"Successfully auto-synced {len(BADGES_CATALOG)} badges in the database!")
    except Exception as e:
        print(f"Error synchronizing badges: {e}")
        conn.rollback()
    finally:
        conn.close()
