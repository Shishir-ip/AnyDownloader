"""Generate AnyDownloader icon assets: app.ico (multi-size) + brand PNGs.

Matches the in-app programmatic icon: rounded blue→purple gradient tile,
white download arrow and underline.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).resolve().parent.parent / "assets"
SQUARE_SIZES = (16, 24, 32, 48, 64, 128, 256)


def rounded_gradient_tile(size: int, radius_ratio: float = 0.225) -> Image.Image:
    scale = 4  # supersample for smooth edges
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = int(s * radius_ratio)
    # diagonal gradient #0A84FF → #5E5CE6 → #AF52DE
    grad = Image.new("RGBA", (s, s))
    for y in range(s):
        for x in range(0, s, 4):  # step columns; gradient is diagonal-smooth
            t = (x + y) / (2 * s)
            if t < 0.55:
                u = t / 0.55
                r = int(0x0A + (0x5E - 0x0A) * u)
                g = int(0x84 + (0x5C - 0x84) * u)
                b = int(0xFF + (0xE6 - 0xFF) * u)
            else:
                u = (t - 0.55) / 0.45
                r = int(0x5E + (0xAF - 0x5E) * u)
                g = int(0x5C + (0x52 - 0x5C) * u)
                b = int(0xE6 + (0xDE - 0xE6) * u)
            for dx in range(4):
                if x + dx < s:
                    grad.putpixel((x + dx, y), (r, g, b, 255))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=255)
    img.paste(grad, (0, 0), mask)
    # soft highlight
    hl = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(hl).rounded_rectangle(
        [int(s * 0.08), int(s * 0.05), int(s * 0.92), int(s * 0.45)],
        radius=int(radius * 0.8), fill=(255, 255, 255, 26))
    img.alpha_composite(hl, (0, 0), (0, 0))
    img = _clip(img, mask)
    return img.resize((size, size), Image.LANCZOS)


def _clip(img: Image.Image, mask: Image.Image) -> Image.Image:
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def draw_arrow(img: Image.Image) -> Image.Image:
    size = img.size[0]
    scale = 4
    s = size * scale
    big = img.resize((s, s), Image.LANCZOS)
    draw = ImageDraw.Draw(big)
    cx = s * 0.5
    width = max(int(s * 0.055), scale * 2)
    # shaft
    draw.line([(cx, s * 0.24), (cx, s * 0.52)], fill=(255, 255, 255, 255), width=width)
    # arrowhead (rounded joins via polygons+circles)
    hw = s * 0.15   # half width of head
    rise = s * 0.10
    tip = (cx, s * 0.52 + rise)
    left = (cx - hw, s * 0.52 - rise)
    right = (cx + hw, s * 0.52 - rise)
    draw.line([left, tip], fill=(255, 255, 255, 255), width=width)
    draw.line([tip, right], fill=(255, 255, 255, 255), width=width)
    r = width / 2
    for pt in (left, tip, right, (cx, s * 0.24), (cx, s * 0.52)):
        draw.ellipse([pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r],
                     fill=(255, 255, 255, 255))
    # underline
    draw.line([(s * 0.26, s * 0.72), (s * 0.74, s * 0.72)],
              fill=(255, 255, 255, 255), width=width)
    rr = width / 2
    for pt in ((s * 0.26, s * 0.72), (s * 0.74, s * 0.72)):
        draw.ellipse([pt[0] - rr, pt[1] - rr, pt[0] + rr, pt[1] + rr],
                     fill=(255, 255, 255, 255))
    return big.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    master = draw_arrow(rounded_gradient_tile(1024))
    master.save(OUT_DIR / "icon.png")
    ico_sizes = [(s, s) for s in SQUARE_SIZES]
    base_256 = draw_arrow(rounded_gradient_tile(256))
    # Pillow downscales `base` into every size listed — save 256 only, sized list does the rest
    base_256.save(OUT_DIR / "app.ico", format="ICO", sizes=ico_sizes)
    # repo assets
    for s in (512, 256, 128):
        tile = rounded_gradient_tile(s)
        draw_arrow(tile).save(OUT_DIR / f"icon-{s}.png")
    # social preview banner
    banner = Image.new("RGBA", (1280, 640), (0, 0, 0, 0))
    bg = Image.new("RGBA", (1280, 640))
    for y in range(640):
        for x in range(0, 1280, 8):
            t = (x + y) / (1280 + 640)
            r = int(0x0A + (0xAF - 0x0A) * t)
            g = int(0x84 + (0x52 - 0x84) * t)
            b = int(0xFF + (0xDE - 0xFF) * t)
            for dx in range(8):
                if x + dx < 1280:
                    bg.putpixel((x + dx, y), (r, g, b, 255))
    banner.alpha_composite(bg)
    big_icon = draw_arrow(rounded_gradient_tile(360))
    banner.alpha_composite(big_icon, (120, 140))
    d = ImageDraw.Draw(banner)
    d.text((560, 250), "AnyDownloader", fill=(255, 255, 255, 255), font_size=96)
    d.text((568, 380), "Download video & audio from (almost) anywhere",
           fill=(255, 255, 255, 210), font_size=40)
    banner.convert("RGB").save(OUT_DIR / "banner.png")
    print("icon assets written to", OUT_DIR)


if __name__ == "__main__":
    main()
