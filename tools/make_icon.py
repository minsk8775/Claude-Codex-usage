"""Draw assets/claude-usage.ico from the Claude and OpenAI logos.

The Claude logo sits top left, the OpenAI logo bottom right, overlapping, with
"Usage" (Inter Display SemiBold, plain) underneath; at 32 px and below only the
two logos. They sit on a "liquid glass" frame: a frosted, see-through rounded
square with a bright rim, so the black OpenAI logo and the text stay readable
on a dark taskbar. --style glass (the default) also gives the logos a light
sheen and rim while keeping their colours; --style flat draws them as they
are.

The logos are the SVGs in assets/. Needs Pillow and cairosvg:
    python tools/make_icon.py [--style glass|flat]
"""
import argparse
import io
import re
from pathlib import Path

import cairosvg
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
OUT = ASSETS / "claude-usage.ico"
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
BIG = 1024  # draw large, then scale down for smooth edges

CLAUDE = (217, 119, 87)
INK = (20, 20, 19)


def logo_mask(name, size):
    svg = (ASSETS / name).read_text(encoding="utf-8")
    # cairosvg does not read CSS hsl(); only the shape is needed here anyway.
    svg = re.sub(r'fill="hsl\([^"]*\)"', 'fill="#000"', svg)
    png = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=size, output_height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA").getchannel("A")


def text_mask(text, size, outline=0):
    face = None
    for name in ("InterDisplay-SemiBold.otf", "/usr/share/fonts/opentype/inter/InterDisplay-SemiBold.otf",
                 "Inter-SemiBold.otf", "segoeuisb.ttf", "segoeuib.ttf", "arialbd.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            face = ImageFont.truetype(name, size)
            break
        except OSError:
            continue
    face = face or ImageFont.load_default()
    box = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=face)
    mask = Image.new("L", (box[2] - box[0] + 8, box[3] - box[1] + 8), 0)
    pad = 4 + outline
    mask = Image.new("L", (box[2] - box[0] + 2 * pad, box[3] - box[1] + 2 * pad), 0)
    ImageDraw.Draw(mask).text((pad - box[0], pad - box[1]), text, font=face, fill=255,
                              stroke_width=outline, stroke_fill=255)
    return mask


def scaled(mask, factor):
    return mask.point(lambda value: int(value * factor))


def flat(mask, color):
    layer = Image.new("RGBA", mask.size, color + (255,))
    layer.putalpha(mask)
    return layer


def glass(mask, color):
    """The shape filled with a translucent sheen, a bright rim and a soft shadow."""
    width, height = mask.size
    pad = max(8, width // 16)
    canvas = (width + 2 * pad, height + 2 * pad)
    full = Image.new("L", canvas, 0)
    full.paste(mask, (pad, pad))
    out = Image.new("RGBA", canvas, (0, 0, 0, 0))
    blur = max(2, width // 40)

    shadow = full.filter(ImageFilter.GaussianBlur(blur))
    shadow = ImageChops.offset(shadow, 0, blur)
    out.alpha_composite(flat(scaled(shadow, 0.14), (0, 0, 0)))

    # Body: lighter at the top, the logo's own colour at the bottom.
    top = tuple(int(c + (255 - c) * 0.12) for c in color)  # keep the colour vivid
    gradient = Image.new("RGBA", canvas)
    draw = ImageDraw.Draw(gradient)
    for y in range(canvas[1]):
        t = y / max(1, canvas[1] - 1)
        draw.line([(0, y), (canvas[0], y)],
                  fill=tuple(int(top[i] + (color[i] - top[i]) * t) for i in range(3)) + (255,))
    gradient.putalpha(full)
    out.alpha_composite(gradient)

    # Rim: a thin bright edge all round, strongest along the top.
    edge = max(2, width // 90)
    inner = full.filter(ImageFilter.MinFilter(edge * 2 + 1))
    rim = ImageChops.subtract(full, inner)
    out.alpha_composite(flat(scaled(rim, 0.35), (255, 255, 255)))
    lifted = ImageChops.offset(full, 0, edge * 2)
    highlight = ImageChops.subtract(full, lifted).filter(ImageFilter.GaussianBlur(edge / 2))
    out.alpha_composite(flat(scaled(highlight, 0.45), (255, 255, 255)))
    return out, pad


def glass_frame(image, box, radius):
    """A frosted, see-through rounded square: a white body that fades from top
    to bottom, a bright rim (strongest on top), a soft sheen and shadow."""
    x1, y1, x2, y2 = box
    size = image.size
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius, fill=255)

    # Shadow only outside the glass: under it, it would show through as grey.
    shadow = ImageChops.offset(mask.filter(ImageFilter.GaussianBlur(18)), 0, 12)
    shadow = ImageChops.subtract(shadow, mask)
    image.alpha_composite(flat(scaled(shadow, 0.25), (0, 0, 0)))

    fade = Image.new("L", size, 0)
    draw = ImageDraw.Draw(fade)
    for y in range(y1, y2 + 1):
        t = (y - y1) / max(1, y2 - y1)
        draw.line([(x1, y), (x2, y)], fill=int(46 - 34 * t))  # nearly clear: 18% -> 5%
    body = Image.new("RGBA", size, (255, 255, 255, 255))
    body.putalpha(ImageChops.multiply(mask, fade))
    image.alpha_composite(body)

    # Light bends at the edges of real glass: a bright band just inside the rim.
    band = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(41)))
    image.alpha_composite(flat(scaled(band.filter(ImageFilter.GaussianBlur(14)), 0.5), (255, 255, 255)))

    sheen = Image.new("L", size, 0)
    ImageDraw.Draw(sheen).ellipse((x1 - 160, y1 - 560, x2 + 160, y1 + 230), fill=85)
    sheen = ImageChops.multiply(sheen.filter(ImageFilter.GaussianBlur(26)), mask)
    image.alpha_composite(flat(sheen, (255, 255, 255)))
    streak = Image.new("L", size, 0)  # a soft highlight along the top-left corner
    ImageDraw.Draw(streak).arc((x1 + 18, y1 + 18, x1 + 2 * radius, y1 + 2 * radius), 185, 265, fill=255, width=14)
    image.alpha_composite(flat(scaled(streak.filter(ImageFilter.GaussianBlur(5)), 0.9), (255, 255, 255)))

    inner = mask.filter(ImageFilter.MinFilter(9))
    rim = ImageChops.subtract(mask, inner)
    image.alpha_composite(flat(scaled(rim, 0.95), (255, 255, 255)))
    top_rim = ImageChops.subtract(mask, ImageChops.offset(mask, 0, 10))
    image.alpha_composite(flat(scaled(top_rim.filter(ImageFilter.GaussianBlur(2)), 0.9), (255, 255, 255)))
    edge = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(3)), mask)
    image.alpha_composite(flat(scaled(edge, 0.45), (60, 60, 70)))  # a hairline that shows on light backgrounds


def place(image, mask, color, at, style):
    if style == "glass":
        layer, pad = glass(mask, color)
        image.alpha_composite(layer, (at[0] - pad, at[1] - pad))
    else:
        image.alpha_composite(flat(mask, color), at)


def frame(with_text, style):
    image = Image.new("RGBA", (BIG + 200, BIG + 200), (0, 0, 0, 0))  # room for shadows
    o = 100
    glass_frame(image, (o + 24, o + 16, o + BIG - 24, o + BIG - 32), 200)
    if with_text:
        place(image, logo_mask("logo-openai.svg", 520), INK, (o + 420, o + 230), style)
        place(image, logo_mask("logo-claude.svg", 530), CLAUDE, (o + 80, o + 70), style)
        # Plain letters (no glass); a thin light outline keeps them readable
        # where the see-through frame shows a dark taskbar.
        halo, words = text_mask("Usage", 168, outline=7), text_mask("Usage", 168)
        at = (o + (BIG - halo.width) // 2, o + 786)
        image.alpha_composite(flat(scaled(halo, 0.75), (255, 255, 255)), at)
        image.alpha_composite(flat(words, INK), (at[0] + 7, at[1] + 7))
    else:
        place(image, logo_mask("logo-openai.svg", 560), INK, (o + 390, o + 380), style)
        place(image, logo_mask("logo-claude.svg", 580), CLAUDE, (o + 60, o + 50), style)
    return image.crop((o, o, o + BIG, o + BIG))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", choices=("glass", "flat"), default="glass")
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()
    full, compact = frame(True, args.style), frame(False, args.style)
    # Scale with premultiplied alpha, or transparent pixels darken the edges.
    images = [(full if size >= 48 else compact).convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA")
              for size in SIZES]
    images[-1].save(args.out, format="ICO", sizes=[(size, size) for size in SIZES],
                    append_images=images[:-1])
    if args.out == str(OUT):
        images[-1].save(ASSETS / "icon.png")  # for the README
    print("wrote", args.out)


if __name__ == "__main__":
    main()
