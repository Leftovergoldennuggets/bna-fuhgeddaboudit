"""
07_social_card.py — Render the social-media share image
==========================================================================
Builds data/web/social-card.png (1200×630, the Open Graph size), the
picture shown when someone shares the site on social media or in a chat.
It carries live headline numbers, so it is regenerated on every run.

Inputs:
  - data/web/site-data.json
  - pipeline/assets/social-skyline.png   (city drawings, rendered once
    from the CITY_ART paths in site/js/app.js)
  - pipeline/assets/fonts/               (Source Serif 4, Inter, IBM Plex
    Mono — the site's fonts, SIL Open Font License)

Usage:
  python pipeline/07_social_card.py
==========================================================================
"""

import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import WEB_SITE_DATA, WEB_SOCIAL_CARD

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
FONTS = os.path.join(ASSETS, "fonts")

WIDTH, HEIGHT, MARGIN = 1200, 630, 64
BACKGROUND = "#faf8f5"
INK = "#1a1a1a"
TEXT = "#333333"
MUTED = "#6b6b6b"
ACCENT = "#8b6f47"
NUMBER = "#5c4a2e"
RULE = "#d4d0cc"


def font(name, size, variation=None):
    """Load a bundled font; variable fonts take a named instance ("Bold")."""
    f = ImageFont.truetype(os.path.join(FONTS, name), size)
    if variation:
        f.set_variation_by_name(variation)
    return f


def wrap(draw, text, fnt, max_width):
    """Greedy word wrap to a pixel width."""
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= max_width:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def main():
    print("=" * 60)
    print("STEP 7: SOCIAL SHARE IMAGE")
    print("=" * 60)
    with open(WEB_SITE_DATA) as f:
        stats = json.load(f)

    overview = stats["overview"]
    miles = stats.get("waymo_context", {}).get("total_rider_only_miles")
    injury = stats.get("benchmarks", {}).get("overall", {}).get("any_injury")
    figures = [
        (f"{overview['total_crashes']:,}", "crashes reported by Waymo's driverless cars"),
        (str(overview["public_metros_count"]), "U.S. cities with public robotaxi service"),
    ]
    if miles:
        figures.append((f"{round(miles / 1e6)}M", "driverless miles, the base for every crash rate"))
    if injury:
        figures.append((f"{round(injury['reduction_pct'])}%", "fewer injury crashes than human drivers, by Waymo's analysis"))

    img = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(img)

    kicker = font("IBMPlexMono-Medium.ttf", 19)
    title = font("SourceSerif4.ttf", 70, "Bold")
    dek = font("Inter.ttf", 25, "Regular")
    big = font("IBMPlexMono-SemiBold.ttf", 54)
    label = font("Inter.ttf", 18, "Regular")
    footer = font("IBMPlexMono-Medium.ttf", 17)

    y = 54
    draw.text((MARGIN, y), "THE WAYMO CRASH RECORD", font=kicker, fill=ACCENT)
    y += 40
    draw.text((MARGIN, y), "Every Waymo Crash, Mapped", font=title, fill=INK)
    y += 98
    for line in wrap(draw, "Every crash Waymo has reported to federal regulators for its "
                           "driverless cars — with crash rates per mile and how they "
                           "compare with human drivers.", dek, WIDTH - 2 * MARGIN):
        draw.text((MARGIN, y), line, font=dek, fill=TEXT)
        y += 34

    # Headline figures in equal columns
    y += 26
    col = (WIDTH - 2 * MARGIN) // len(figures)
    for i, (number, text) in enumerate(figures):
        x = MARGIN + i * col
        draw.line([(x, y), (x + col - 28, y)], fill=INK, width=2)
        draw.text((x, y + 12), number, font=big, fill=NUMBER)
        ly = y + 80
        for line in wrap(draw, text, label, col - 32)[:3]:
            draw.text((x, ly), line, font=label, fill=MUTED)
            ly += 24

    # City drawings along the bottom, then the footer
    skyline = Image.open(os.path.join(ASSETS, "social-skyline.png")).convert("RGBA")
    img.paste(skyline, ((WIDTH - skyline.width) // 2, HEIGHT - 132), skyline)
    draw.line([(MARGIN, HEIGHT - 58), (WIDTH - MARGIN, HEIGHT - 58)], fill=RULE, width=1)
    through = stats["meta"].get("federal_data_through_label", "")
    note = f"Updated weekly · data through {through}"
    url = "leftovergoldennuggets.github.io/bna-fuhgeddaboudit"
    url_x = WIDTH - MARGIN - draw.textlength(url, font=footer)
    if MARGIN + draw.textlength(note, font=footer) + 24 > url_x:
        note = "Updated weekly"  # never let the two collide
    draw.text((MARGIN, HEIGHT - 44), note, font=footer, fill=MUTED)
    draw.text((url_x, HEIGHT - 44), url, font=footer, fill=ACCENT)

    os.makedirs(os.path.dirname(WEB_SOCIAL_CARD), exist_ok=True)
    img.save(WEB_SOCIAL_CARD, optimize=True)
    print(f"  Saved: {WEB_SOCIAL_CARD} ({os.path.getsize(WEB_SOCIAL_CARD) // 1024} KB)")


if __name__ == "__main__":
    main()
