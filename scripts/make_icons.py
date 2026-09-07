# -*- coding: utf-8 -*-
"""
Generate PWA icons as PNG.

Two variants, because they are not interchangeable:
  * "any"      — full-bleed rounded square, artwork close to the edges.
  * "maskable" — the launcher crops this to whatever shape the OS wants
                 (often a circle), so all artwork must sit inside the safe
                 zone: the centre 80% diameter. Everything outside is padding.

The artwork mirrors the invoice itself: a white sheet with the blue 계산서
header band and a heavier total row at the foot.
"""
from PIL import Image, ImageDraw

INK = (17, 17, 17, 255)
PAPER = (255, 255, 255, 255)
BAND = (189, 215, 238, 255)      # #bdd7ee — the grid header on the invoice
BAND_DARK = (31, 78, 121, 255)   # #1f4e79 — its text colour
ROW = (60, 60, 60, 255)
OUT = r'C:\invoice_generator\public\icons'

DOC = (0.180, 0.150, 0.820, 0.850)
BAND_BOX = (0.180, 0.150, 0.820, 0.288)
ROWS = [
    (0.245, 0.355, 0.755, 0.397),
    (0.245, 0.437, 0.755, 0.479),
    (0.245, 0.519, 0.755, 0.561),
    (0.245, 0.601, 0.585, 0.643),
]
TOTAL = (0.180, 0.712, 0.820, 0.850)
TOTAL_LINE = (0.470, 0.760, 0.755, 0.802)


def draw_icon(size, maskable):
    ss = 4  # supersample, then downscale for clean edges
    n = size * ss
    img = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if maskable:
        # Full bleed: the OS mask decides the silhouette, so no rounding here.
        d.rectangle([0, 0, n, n], fill=INK)
        # Centre 72% — comfortably inside the 80% safe circle even diagonally.
        scale = 0.72
    else:
        d.rounded_rectangle([0, 0, n - 1, n - 1], radius=int(n * 0.125), fill=INK)
        scale = 1.0
    offset = (1 - scale) / 2

    def box(frac):
        x0, y0, x1, y1 = frac
        return [int((offset + v * scale) * n) for v in (x0, y0, x1, y1)]

    r_doc = int(n * 0.026 * scale)
    r_row = int(n * 0.009 * scale)

    d.rounded_rectangle(box(DOC), radius=r_doc, fill=PAPER)

    # Blue header band, square along its lower edge.
    bx0, by0, bx1, by1 = box(BAND_BOX)
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=r_doc, fill=BAND)
    d.rectangle([bx0, by1 - r_doc, bx1, by1], fill=BAND)

    for row in ROWS:
        d.rounded_rectangle(box(row), radius=r_row, fill=ROW)

    # Total row, square along its upper edge.
    tx0, ty0, tx1, ty1 = box(TOTAL)
    d.rounded_rectangle([tx0, ty0, tx1, ty1], radius=r_doc, fill=BAND_DARK)
    d.rectangle([tx0, ty0, tx1, ty0 + r_doc], fill=BAND_DARK)
    d.rounded_rectangle(box(TOTAL_LINE), radius=r_row, fill=PAPER)

    return img.resize((size, size), Image.LANCZOS)


made = []
for size in (192, 512):
    p = '%s\\icon-%d.png' % (OUT, size)
    draw_icon(size, maskable=False).save(p, 'PNG', optimize=True)
    made.append(p)

    p = '%s\\icon-maskable-%d.png' % (OUT, size)
    draw_icon(size, maskable=True).save(p, 'PNG', optimize=True)
    made.append(p)

# Apple applies its own rounding and does not honour transparency.
apple = Image.new('RGB', (180, 180), (17, 17, 17))
apple.paste(draw_icon(180, maskable=False).convert('RGB'), (0, 0))
p = '%s\\apple-touch-icon.png' % OUT
apple.save(p, 'PNG', optimize=True)
made.append(p)

for m in made:
    print('wrote', m)
