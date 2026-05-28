"""
Local preview for the level-up card. No DB or Discord needed.

Generates a few sample cards covering different progress tiers so you can
eyeball the design and tune utils/card_generator.py before wiring it into
the bot.

Usage:
    uv run --python 3.12 scripts/test_card.py

Output:
    outputs/card_early.png
    outputs/card_mid.png
    outputs/card_late.png
    outputs/card_done.png
    outputs/card_no_badges.png
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.card_generator import CardData, render_card

# Try to find a local image to use as a test avatar for dynamic theming
avatar_bytes = None
test_avatar_paths = [
    "/home/spandan/.gemini/antigravity/brain/427d13ac-61b2-42ca-a4d9-e231d2bda3d6/coding_dark_bg_1779188586272.png",
    "assets/images/fire.png",
    "assets/logos/techsoc.jpg",
]
for p in test_avatar_paths:
    if os.path.exists(p):
        try:
            with open(p, "rb") as f:
                avatar_bytes = f.read()
            print(f"Loaded test avatar for dynamic theming from {p}")
            break
        except Exception:
            pass

SAMPLES = [
    ("card_early",     CardData(name="Aman Raj", student_id="B124011", day_progress=3,
                                streak=2, total_solved=7, badge_emojis=[], avatar_webp_bytes=avatar_bytes)),
    ("card_mid",       CardData(name="Aman Raj", student_id="B124011", day_progress=12,
                                streak=5, total_solved=29, badge_emojis=["🥉", "🎯"],
                                badge_keys=["day7_done", "contest_participant"],
                                avatar_webp_bytes=avatar_bytes,
                                custom_line="Halfway there — let's go.")),
    ("card_late",      CardData(name="Spandan Mishra", student_id="B124002", day_progress=20,
                                streak=9, total_solved=51, badge_emojis=["🥉", "🥈", "🎯"],
                                badge_keys=["day7_done", "day14_done", "contest_participant"],
                                avatar_webp_bytes=avatar_bytes)),
    ("card_done",      CardData(name="Spandan Mishra", student_id="B124002", day_progress=25,
                                streak=25, total_solved=73,
                                badge_emojis=["🥉", "🥈", "🥇", "🎯", "🌟", "📈"],
                                badge_keys=["day7_done", "day14_done", "day25_done", "contest_participant", "contest_top_100", "contest_rating_climber"],
                                avatar_webp_bytes=avatar_bytes)),
    ("card_no_badges", CardData(name="New Joiner",   student_id="B124099", day_progress=1,
                                streak=1, total_solved=2, badge_emojis=[], avatar_webp_bytes=avatar_bytes)),
]


def main():
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")
    os.makedirs(out_dir, exist_ok=True)

    for tag, data in SAMPLES:
        png_bytes = render_card(data)
        out_path = os.path.join(out_dir, f"{tag}.png")
        with open(out_path, "wb") as f:
            f.write(png_bytes)
        print(f"  wrote {out_path}  ({len(png_bytes) // 1024} KB)")

    print(f"\nOpen the PNGs above (e.g. `open {out_dir}/card_mid.png`) to preview.")


if __name__ == "__main__":
    main()
