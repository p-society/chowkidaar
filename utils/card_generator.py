"""
Level-up card renderer.

Produces a 1080×1920 PNG (Instagram Story dimensions) summarizing a user's
progress in the 25-day event. Dark + accent style:

  - Background:  deep navy   #0F172A
  - Accent:      teal         #14B8A6
  - Text:        off-white    #F8FAFC
  - Muted:       slate gray   #64748B

Layout zones (top to bottom):
  0–500      Hero band       — avatar + name + student_id
  500–950    Big number      — "DAY 14 / 25"
  950–1250   Stats row       — streak | total solved
  1250–1550  Badges row      — emoji icons
  1550–1920  Footer          — personalized one-liner + brand line

Public API:
    render_card(data: CardData) -> bytes
    CardData dataclass holds everything the renderer needs.

Font loading is forgiving — if Inter isn't bundled, we fall back to Helvetica,
Arial, DejaVu Sans, and finally PIL's default.
"""

from __future__ import annotations

import io
import os
import random
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Pulled lazily inside render_card so importing this module never touches disk.


# ──────────────────────────────────────────────────────────────────────────
# Style constants
# ──────────────────────────────────────────────────────────────────────────

WIDTH, HEIGHT = 1080, 1920

BG_NAVY      = (15, 23, 42)         # #0F172A
CARD_NAVY    = (30, 41, 59)         # #1E293B  (slightly lighter for stat cards)
ACCENT_TEAL  = (20, 184, 166)       # #14B8A6
TEXT_WHITE   = (248, 250, 252)      # #F8FAFC
MUTED_GRAY   = (148, 163, 184)      # #94A3B8

# Font candidates in priority order. First file found is used.
FONTS_REGULAR = [
    "assets/fonts/Inter-Regular.ttf",
    "/usr/share/fonts/google-carlito-fonts/Carlito-Regular.ttf",
    "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVuSans.ttf",
]
FONTS_BOLD = [
    "assets/fonts/Inter-Bold.ttf",
    "/usr/share/fonts/google-carlito-fonts/Carlito-Bold.ttf",
    "/usr/share/fonts/liberation-sans/LiberationSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "DejaVuSans-Bold.ttf",
]

# Color-emoji fonts. PIL's truetype() only accepts the font's *native* bitmap
# size for these (137 for Apple Color Emoji, 128 for Noto Color Emoji); we
# render at that size and resize the resulting image. (path, native_size)
EMOJI_FONTS = [
    ("/System/Library/Fonts/Apple Color Emoji.ttc",              137),
    ("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",        128),
    ("/usr/share/fonts/noto-cjk/NotoColorEmoji.ttf",             128),
    ("assets/fonts/NotoColorEmoji.ttf",                          128),
]

# Personalized one-liners tuned to progress tier.
TIER_LINES = {
    "early":   [
        "Just getting started — keep showing up.",
        "Every legend starts at Day 1.",
        "Momentum is everything. Go again tomorrow.",
    ],
    "mid":     [
        "Halfway there — you're built different.",
        "You've put in the reps. Don't stop now.",
        "The streak is the prize.",
    ],
    "late":    [
        "Final stretch. Finish strong.",
        "You can already see the finish line.",
        "Almost there — don't ease up.",
    ],
    "done":    [
        "25 days down. Hall of Fame energy.",
        "You actually did it. Take the bow.",
        "Completed the challenge — that's the flex.",
    ],
}


# ──────────────────────────────────────────────────────────────────────────
# Data
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class CardData:
    name: str
    student_id: str
    day_progress: int                 # 0..25 (distinct days submitted)
    duration_days: int = 25
    streak: int = 0
    total_solved: int = 0
    badge_emojis: List[str] = field(default_factory=list)
    badge_keys: List[str] = field(default_factory=list)
    avatar_webp_bytes: Optional[bytes] = None    # raw WebP/image bytes, optional
    custom_line: Optional[str] = None           # if None, picked from TIER_LINES

    def tier(self) -> str:
        d = self.day_progress
        if d >= self.duration_days: return "done"
        if d >= int(self.duration_days * 0.7): return "late"
        if d >= int(self.duration_days * 0.3): return "mid"
        return "early"

    def line(self) -> str:
        if self.custom_line:
            return self.custom_line
        choices = TIER_LINES.get(self.tier(), TIER_LINES["early"])
        return random.choice(choices)


# ──────────────────────────────────────────────────────────────────────────
# Font helper
# ──────────────────────────────────────────────────────────────────────────

_cached_fonts = {}

def _load_font(candidates: Sequence[str], size: int) -> ImageFont.FreeTypeFont:
    cache_key = (tuple(candidates), size)
    if cache_key in _cached_fonts:
        return _cached_fonts[cache_key]

    for path in candidates:
        try:
            font = ImageFont.truetype(path, size)
            _cached_fonts[cache_key] = font
            return font
        except (OSError, IOError):
            continue
    # Last resort — PIL's bitmap default. Doesn't honor `size`, but at least renders.
    font = ImageFont.load_default()
    _cached_fonts[cache_key] = font
    return font


def _font_regular(size: int) -> ImageFont.FreeTypeFont:
    return _load_font(FONTS_REGULAR, size)


def _font_bold(size: int) -> ImageFont.FreeTypeFont:
    return _load_font(FONTS_BOLD, size)


def _render_emoji(char: str, target_size: int) -> Image.Image:
    """
    Render one emoji as an RGBA image of (target_size, target_size).

    Color-emoji fonts only render at their native bitmap size, so we draw to
    a native-sized canvas and then resize. If no emoji font is available
    (sandbox, minimal Linux container), we fall back to the regular bold font
    — the glyph will show as a placeholder box but the layout still works.
    """
    for path, native in EMOJI_FONTS:
        if not os.path.exists(path):
            continue
        try:
            font = ImageFont.truetype(path, native)
            img = Image.new("RGBA", (native, native), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            # Center within the native-size canvas
            bbox = d.textbbox((0, 0), char, font=font, embedded_color=True)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = (native - tw) // 2 - bbox[0]
            y = (native - th) // 2 - bbox[1]
            d.text((x, y), char, font=font, embedded_color=True)
            return img.resize((target_size, target_size), Image.LANCZOS)
        except (OSError, IOError, ValueError):
            continue

    # Fallback: render the char with the regular text font onto a blank canvas.
    img = Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _font_bold(int(target_size * 0.85))
    bbox = d.textbbox((0, 0), char, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((target_size - tw) // 2 - bbox[0], (target_size - th) // 2 - bbox[1]),
           char, font=font, fill=TEXT_WHITE)
    return img


# ──────────────────────────────────────────────────────────────────────────
# Drawing primitives
# ──────────────────────────────────────────────────────────────────────────

def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _text_height(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def _center_text(draw: ImageDraw.ImageDraw, y: int, text: str, font: ImageFont.FreeTypeFont, fill):
    w = _text_width(draw, text, font)
    draw.text(((WIDTH - w) // 2, y), text, font=font, fill=fill)


def _circular_avatar(raw_bytes: bytes, size: int) -> Image.Image:
    """Decode bytes, resize to (size, size), apply circular alpha mask."""
    avatar = Image.open(io.BytesIO(raw_bytes)).convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size))
    out.paste(avatar, (0, 0), mask)
    return out


def _make_circular_badge(img: Image.Image, size: int) -> Image.Image:
    """Resize image to (size, size) and apply a circular alpha mask to crop it perfectly."""
    resized = img.convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size))
    out.paste(resized, (0, 0), mask)
    return out


def _placeholder_avatar(size: int, initial: str, fill=ACCENT_TEAL) -> Image.Image:
    """When no avatar is provided, draw a teal circle with the user's initial."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, size, size), fill=fill)
    font = _font_bold(int(size * 0.5))
    w = _text_width(d, initial, font)
    h = _text_height(d, initial, font)
    d.text(((size - w) // 2, (size - h) // 2 - int(size * 0.05)), initial, font=font, fill=TEXT_WHITE)
    return img


def _draw_rounded_card(draw: ImageDraw.ImageDraw, box, radius: int, fill):
    """Filled rounded rectangle — PIL has rectangle_rounded but spelled differently per version."""
    draw.rounded_rectangle(box, radius=radius, fill=fill)


# ──────────────────────────────────────────────────────────────────────────
# Public renderer
# ──────────────────────────────────────────────────────────────────────────

_cached_base_bg = None
_cached_icons = {}
_cached_badges = {}

def _get_base_background(branding, bg_navy, accent_color) -> Image.Image:
    global _cached_base_bg
    if _cached_base_bg is not None:
        return _cached_base_bg.copy()

    bg_path = "assets/images/coding_bg.png"
    if os.path.exists(bg_path):
        bg_img = Image.open(bg_path).convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS)
        # Darken it so text pops, but keep it light enough to show details
        darkener = Image.new("RGBA", (WIDTH, HEIGHT), (*bg_navy, 90)) # 90 alpha instead of 180
        bg_img.paste(darkener, (0, 0), darkener)
        img = bg_img
    else:
        img = Image.new("RGB", (WIDTH, HEIGHT), bg_navy)
        
    draw = ImageDraw.Draw(img)

    # ── Logos at the top corners ──
    LOGO_SIZE = 110
    
    def _make_circular(img_obj: Image.Image, size: int) -> Image.Image:
        resized = img_obj.convert("RGBA").resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
        out = Image.new("RGBA", (size, size))
        out.paste(resized, (0, 0), mask)
        return out
        
    try:
        if os.path.exists("assets/logos/psoc.png"):
            psoc_img = Image.open("assets/logos/psoc.png")
            psoc_circ = _make_circular(psoc_img, LOGO_SIZE)
            img.paste(psoc_circ, (40, 40), psoc_circ)
    except Exception as e:
        import logging; logging.getLogger(__name__).error(f"Failed to load psoc.png: {e}")

    try:
        if os.path.exists("assets/logos/techsoc.jpg"):
            techsoc_img = Image.open("assets/logos/techsoc.jpg")
            techsoc_circ = _make_circular(techsoc_img, LOGO_SIZE)
            img.paste(techsoc_circ, (WIDTH - 40 - LOGO_SIZE, 40), techsoc_circ)
    except Exception as e:
        import logging; logging.getLogger(__name__).error(f"Failed to load techsoc.jpg: {e}")

    # ── Poster heading (y ≈ 80–200) ──
    # Letter-spaced uppercase title in accent, smaller subtitle below in muted.
    title_font = _font_bold(38)
    subtitle_font = _font_regular(28)
    title = branding["title"].upper()
    # Manual letter spacing for the title — draw each char individually so the
    # uppercase reads as a "poster" header without a custom font.
    title_chars = list(title)
    char_gap = 4
    char_widths = [_text_width(draw, c, title_font) for c in title_chars]
    total_title_w = sum(char_widths) + char_gap * (len(title_chars) - 1)
    x = (WIDTH - total_title_w) // 2
    for c, cw in zip(title_chars, char_widths):
        draw.text((x, 80), c, font=title_font, fill=accent_color)
        x += cw + char_gap
    _center_text(draw, 142, branding["subtitle"], subtitle_font, MUTED_GRAY)

    # Thin accent divider under the heading
    draw.line([(WIDTH // 2 - 80, 208), (WIDTH // 2 + 80, 208)], fill=accent_color, width=3)
    
    _cached_base_bg = img
    return _cached_base_bg.copy()


def render_card(data: CardData) -> bytes:
    # Read branding lazily so swapping configs doesn't require restarting tests.
    from utils.event_window import get_event_branding
    branding = get_event_branding()

    import io

    AV_SIZE = 300

    # Default theme colors (sleek cyber teal + navy)
    accent_color = ACCENT_TEAL
    bg_navy = BG_NAVY
    card_navy = CARD_NAVY

    avatar = (
        _circular_avatar(data.avatar_webp_bytes, AV_SIZE)
        if data.avatar_webp_bytes
        else None
    )

    img = _get_base_background(branding, bg_navy, accent_color)
    draw = ImageDraw.Draw(img)

    # ── Hero band: avatar + name + student_id (y ≈ 240–640) ──
    if not avatar:
        avatar = (
            _circular_avatar(data.avatar_webp_bytes, AV_SIZE)
            if data.avatar_webp_bytes
            else _placeholder_avatar(AV_SIZE, (data.name or "?")[:1].upper(), fill=accent_color)
        )
    img.paste(avatar, ((WIDTH - AV_SIZE) // 2, 240), avatar)

    name_font_size = 70
    name_font = _font_bold(name_font_size)
    name_w = _text_width(draw, data.name, name_font)
    max_name_w = 880  # 100px padding on each side
    while name_w > max_name_w and name_font_size > 36:
        name_font_size -= 4
        name_font = _font_bold(name_font_size)
        name_w = _text_width(draw, data.name, name_font)
    _center_text(draw, 565 + (70 - name_font_size) // 2, data.name, name_font, TEXT_WHITE)

    sid_font_size = 34
    sid_font = _font_regular(sid_font_size)
    sid_w = _text_width(draw, data.student_id, sid_font)
    while sid_w > max_name_w and sid_font_size > 20:
        sid_font_size -= 2
        sid_font = _font_regular(sid_font_size)
        sid_w = _text_width(draw, data.student_id, sid_font)
    _center_text(draw, 650 + (34 - sid_font_size) // 2, data.student_id, sid_font, accent_color)

    # ── Big number: DAY X / 25 (y ≈ 720–1010) ──
    big_font = _font_bold(260)
    small_font = _font_bold(110)

    big_str = f"{data.day_progress}"
    small_str = f" / {data.duration_days}"

    big_w = _text_width(draw, big_str, big_font)
    small_w = _text_width(draw, small_str, small_font)
    total_w = big_w + small_w
    big_x = (WIDTH - total_w) // 2
    big_y = 720
    draw.text((big_x, big_y), big_str, font=big_font, fill=accent_color)
    draw.text((big_x + big_w, big_y + (260 - 110) - 10), small_str, font=small_font, fill=MUTED_GRAY)

    label_font = _font_regular(44)
    _center_text(draw, big_y + 260 + 20, "DAYS COMPLETED", label_font, MUTED_GRAY)

    # ── Progress Bar (y ≈ 1060–1104) ──
    BAR_W = 700
    BAR_H = 44
    bar_x = (WIDTH - BAR_W) // 2
    bar_y = 1060
    
    # 1. Background Bar
    _draw_rounded_card(
        draw,
        (bar_x, bar_y, bar_x + BAR_W, bar_y + BAR_H),
        radius=BAR_H // 2,
        fill=card_navy
    )
    
    # 2. Filled Bar
    pct = data.day_progress / data.duration_days
    fill_w = int(BAR_W * pct)
    if fill_w > 0:
        fill_w = max(fill_w, BAR_H)
        _draw_rounded_card(
            draw,
            (bar_x, bar_y, bar_x + fill_w, bar_y + BAR_H),
            radius=BAR_H // 2,
            fill=accent_color
        )
    
    # 3. Percentage text inside the bar
    pct_str = f"{int(pct * 100)}%"
    pct_font = _font_bold(26)
    pct_w = _text_width(draw, pct_str, pct_font)
    pct_h = _text_height(draw, pct_str, pct_font)
    
    text_color = bg_navy if fill_w > (BAR_W // 2 + pct_w // 2) else TEXT_WHITE
    draw.text(
        (bar_x + (BAR_W - pct_w) // 2, bar_y + (BAR_H - pct_h) // 2 - 2),
        pct_str,
        font=pct_font,
        fill=text_color
    )

    # ── Stats row (y ≈ 1170–1390): streak | total solved ──
    CARD_W = 460
    CARD_H = 220
    CARD_GAP = 40
    cards_total_w = CARD_W * 2 + CARD_GAP
    cards_x0 = (WIDTH - cards_total_w) // 2
    cards_y0 = 1170

    def _stat_card(
        x: int, label: str, local_image_filename: str, number: int, value_color
    ):
        _draw_rounded_card(
            draw,
            (x, cards_y0, x + CARD_W, cards_y0 + CARD_H),
            radius=36,
            fill=card_navy,
        )
        val_font = _font_bold(110)
        lbl_font = _font_regular(32)
        ICON_SIZE = 90
        GAP = 18

        number_str = str(number)
        number_w = _text_width(draw, number_str, val_font)
        content_w = ICON_SIZE + GAP + number_w

        content_x = x + (CARD_W - content_w) // 2
        icon_y = cards_y0 + 40
        num_y = cards_y0 + 30

        # Construct path to the image asset directory
        image_asset_path = f"assets/images/{local_image_filename}"

        if image_asset_path in _cached_icons:
            icon_img = _cached_icons[image_asset_path]
            img.paste(icon_img, (content_x, icon_y), icon_img)
        elif os.path.exists(image_asset_path):
            # Load, convert to transparent RGBA, and scale to the standard 90x90 canvas slot
            icon_img = (
                Image.open(image_asset_path)
                .convert("RGBA")
                .resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
            )
            _cached_icons[image_asset_path] = icon_img
            img.paste(icon_img, (content_x, icon_y), icon_img)
        else:
            # Fallback block text logic if assets get moved unexpectedly
            draw.text(
                (content_x, num_y + 20),
                "•",
                font=val_font,
                fill=accent_color,
            )

        draw.text(
            (content_x + ICON_SIZE + GAP, num_y),
            number_str,
            font=val_font,
            fill=value_color,
        )

        lw = _text_width(draw, label, lbl_font)
        draw.text(
            (x + (CARD_W - lw) // 2, cards_y0 + 160),
            label,
            font=lbl_font,
            fill=MUTED_GRAY,
        )

    # Swapped out raw string characters for direct image references inside the assets folder
    _stat_card(cards_x0, "DAY STREAK", "fire.png", data.streak, TEXT_WHITE)
    _stat_card(
        cards_x0 + CARD_W + CARD_GAP,
        "PROBLEMS SOLVED",
        "check.png",
        data.total_solved,
        TEXT_WHITE,
    )

    # ── Badges row (y ≈ 1450–1650) ──
    badge_y = 1450
    if data.badge_keys or data.badge_emojis:
        EMOJI_SIZE = 130
        spacing = 40
        
        badge_imgs = []
        for i, key in enumerate(data.badge_keys):
            img_path = f"assets/badges/{key}.png"
            if img_path in _cached_badges:
                badge_imgs.append(_cached_badges[img_path])
            elif os.path.exists(img_path):
                try:
                    b_img = Image.open(img_path)
                    b_img = _make_circular_badge(b_img, EMOJI_SIZE)
                    _cached_badges[img_path] = b_img
                    badge_imgs.append(b_img)
                except Exception as e:
                    import logging; logging.getLogger(__name__).error(f"Failed to load badge image {key}: {e}")
            else:
                if i < len(data.badge_emojis):
                    emoji = data.badge_emojis[i]
                    badge_imgs.append(_render_emoji(emoji, EMOJI_SIZE))
                    
        # Fill any remaining slots
        while len(badge_imgs) < len(data.badge_emojis):
            emoji = data.badge_emojis[len(badge_imgs)]
            badge_imgs.append(_render_emoji(emoji, EMOJI_SIZE))
            
        if badge_imgs:
            total_w = EMOJI_SIZE * len(badge_imgs) + spacing * (len(badge_imgs) - 1)
            bx = (WIDTH - total_w) // 2
            for b_img in badge_imgs:
                img.paste(b_img, (bx, badge_y), b_img)
                bx += EMOJI_SIZE + spacing
                
            badge_label_font = _font_regular(34)
            _center_text(draw, badge_y + EMOJI_SIZE + 30, "BADGES EARNED", badge_label_font, MUTED_GRAY)
        else:
            no_badges_font = _font_regular(38)
            _center_text(draw, badge_y + 50, "No badges yet — keep going!", no_badges_font, MUTED_GRAY)
    else:
        no_badges_font = _font_regular(38)
        _center_text(draw, badge_y + 50, "No badges yet — keep going!", no_badges_font, MUTED_GRAY)

    # ── Footer: personalized one-liner (y ≈ 1700–1850). The poster header
    #    already carries the event + org, so no second brand line is needed.
    line_font = _font_regular(44)
    line = data.line()
    # Wrap manually at ~32 chars per line.
    words, current_lines, current = line.split(), [], ""
    for w in words:
        if len(current) + len(w) + 1 > 32:
            current_lines.append(current.strip())
            current = w + " "
        else:
            current += w + " "
    if current.strip():
        current_lines.append(current.strip())

    # Vertically center the 1-3 line block around y=1790.
    total_h = len(current_lines[:3]) * 58
    ly = 1790 - total_h // 2
    for ln in current_lines[:3]:
        _center_text(draw, ly, ln, line_font, TEXT_WHITE)
        ly += 58

    # ── Encode to WebP bytes ──
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=85)
    return buf.getvalue()
