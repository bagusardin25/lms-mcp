"""Membuat ikon server: buku terbuka yang tersambung ke sebuah titik koneksi.

Ikon ini dibuat khusus untuk proyek ini dan sengaja tidak memakai logo atau warna kampus,
karena proyek ini tidak resmi. Jalankan dengan: uv run python scripts/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

CANVAS = 2048
OUTPUT = Path(__file__).resolve().parents[1] / "src" / "lms_mcp" / "assets"

BACKGROUND = (15, 76, 92, 255)
PAGE = (248, 250, 252, 255)
# Warna solid, karena warna transparan akan membuat ikon berlubang.
PAGE_LINE = (183, 204, 210, 255)
ACCENT = (246, 174, 45, 255)


def curve(start, control, end, steps=48):
    """Titik-titik kurva Bezier kuadratik."""
    points = []
    for step in range(steps + 1):
        t = step / steps
        x = (1 - t) ** 2 * start[0] + 2 * (1 - t) * t * control[0] + t**2 * end[0]
        y = (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * control[1] + t**2 * end[1]
        points.append((x, y))
    return points


def scaled(points):
    return [(x * CANVAS / 1024, y * CANVAS / 1024) for x, y in points]


def page(side):
    """Satu halaman buku. side -1 untuk kiri dan 1 untuk kanan."""
    spine = 512 + side * 14
    outer = 512 + side * 340
    middle = 512 + side * 170
    top = curve((spine, 470), (middle, 372), (outer, 420))
    bottom = curve((outer, 790), (middle, 742), (spine, 840))
    return top + bottom


def page_line(side, y):
    return curve(
        (512 + side * 72, y + 26),
        (512 + side * 170, y - 28),
        (512 + side * 278, y),
    )


def draw_icon():
    image = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    unit = CANVAS / 1024

    draw.rounded_rectangle((0, 0, CANVAS - 1, CANVAS - 1), radius=int(224 * unit), fill=BACKGROUND)

    # Garis koneksi digambar lebih dulu supaya pangkalnya tertutup halaman buku.
    draw.line(scaled([(512, 240), (512, 480)]), fill=ACCENT, width=int(44 * unit))

    for side in (-1, 1):
        draw.polygon(scaled(page(side)), fill=PAGE)
        for y in (520, 610, 700):
            draw.line(scaled(page_line(side, y)), fill=PAGE_LINE, width=int(26 * unit), joint="curve")

    x, y, radius = 512 * unit, 214 * unit, 92 * unit
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=ACCENT)
    return image


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    icon = draw_icon()
    for size in (256, 64):
        icon.resize((size, size), Image.LANCZOS).save(OUTPUT / f"icon-{size}.png", optimize=True)
    icon.resize((256, 256), Image.LANCZOS).save(
        OUTPUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)]
    )


if __name__ == "__main__":
    main()
