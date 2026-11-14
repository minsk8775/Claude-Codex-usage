"""Draw assets/claude-usage.ico: a Claude-style spark on top, a terminal
prompt (Codex) below, and "Usage" between them.

The marks are drawn here, not copied from either company's logo. Run with
Pillow installed: python tools/make_icon.py
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "claude-usage.ico"
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
BIG = 1024  # draw large, then scale down for smooth edges

BG = (30, 30, 46, 255)        # the widget's background
CLAUDE = (217, 119, 87, 255)  # warm orange
WHITE = (255, 255, 255, 255)
CODEX_TILE = (16, 16, 16, 255)


def font(size):
    for name in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def spark(draw, cx, cy, radius):
    """A burst of rounded rays of slightly different lengths."""
    lengths = (1.0, 0.78, 0.92, 0.7, 0.98, 0.8, 0.9, 0.72, 1.0, 0.76, 0.88, 0.74)
    width = radius * 0.2
    for index, scale in enumerate(lengths):
        angle = math.radians(index * 30 - 90)
        inner, outer = radius * 0.12, radius * scale
        x1, y1 = cx + inner * math.cos(angle), cy + inner * math.sin(angle)
        x2, y2 = cx + outer * math.cos(angle), cy + outer * math.sin(angle)
        draw.line((x1, y1, x2, y2), fill=CLAUDE, width=int(width))
        r = width / 2
        draw.ellipse((x2 - r, y2 - r, x2 + r, y2 + r), fill=CLAUDE)
    r = radius * 0.2
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=CLAUDE)


def prompt(draw, cx, cy, half):
    """A dark rounded tile with a '>_' prompt."""
    draw.rounded_rectangle((cx - half, cy - half, cx + half, cy + half),
                           radius=half * 0.38, fill=CODEX_TILE, outline=WHITE,
                           width=max(2, int(half * 0.07)))
    stroke = int(half * 0.2)
    chevron = [(cx - half * 0.5, cy - half * 0.38), (cx - half * 0.08, cy),
               (cx - half * 0.5, cy + half * 0.38)]
    draw.line(chevron, fill=WHITE, width=stroke, joint="curve")
    for x, y in (chevron[0], chevron[2]):
        draw.ellipse((x - stroke / 2, y - stroke / 2, x + stroke / 2, y + stroke / 2), fill=WHITE)
    draw.rounded_rectangle((cx + half * 0.06, cy + half * 0.22, cx + half * 0.56, cy + half * 0.22 + stroke),
                           radius=stroke / 2, fill=WHITE)


def frame(with_text):
    image = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((16, 16, BIG - 16, BIG - 16), radius=210, fill=BG)
    if with_text:
        spark(draw, BIG / 2, 205, 150)
        text = "Usage"
        face = font(178)
        box = draw.textbbox((0, 0), text, font=face)
        width, height = box[2] - box[0], box[3] - box[1]
        draw.text(((BIG - width) / 2 - box[0], 512 - height / 2 - box[1]), text, font=face, fill=WHITE)
        prompt(draw, BIG / 2, 812, 132)
    else:
        # Too small for text: just the two marks, one above the other.
        spark(draw, BIG / 2, 282, 215)
        prompt(draw, BIG / 2, 750, 200)
    return image


def main():
    full, compact = frame(True), frame(False)
    images = [(full if size >= 48 else compact).resize((size, size), Image.LANCZOS) for size in SIZES]
    images[-1].save(OUT, format="ICO", sizes=[(size, size) for size in SIZES],
                    append_images=images[:-1])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
