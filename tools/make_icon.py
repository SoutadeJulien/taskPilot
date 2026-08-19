"""Genere les icones de l'application, sans dependance externe.

Reprend le dessin du logo de l'app (pastille arrondie a l'accent + triangle
« play » sombre) et l'ecrit dans les deux formats attendus :

* ``taskpilot/assets/icon.ico`` — Windows (icone du .exe) ;
* ``taskpilot/assets/icon.png`` — bureaux Unix, ou les gestionnaires de
  fenetres et les serveurs de notification veulent du PNG.

A relancer si la palette ou le dessin du logo changent :

    python tools/make_icon.py
"""

import os
import struct
import zlib

# Palette (alignee sur taskpilot/qt/theme.py).
ACCENT = (0x6a, 0xa8, 0x84)       # pastille
ACCENT_FG = (0x0e, 0x1a, 0x14)    # triangle "play"

SIZES = (16, 24, 32, 48, 64, 128, 256)
ASSETS = os.path.join(os.path.dirname(__file__), os.pardir,
                      "taskpilot", "assets")
OUT_ICO = os.path.join(ASSETS, "icon.ico")
OUT_PNG = os.path.join(ASSETS, "icon.png")
#: Signature d'un fichier PNG (norme RFC 2083).
OPAQUE = bytes((0xFF,))          # canal alpha d un pixel opaque
PNG_MAGIC = bytes((0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A))
#: Taille du PNG : suffisante pour toutes les tailles d'icone des bureaux Unix.
PNG_SIZE = 256


def _pixel(x, y, size):
    """Couleur RGBA d'un pixel, ou ``None`` (transparent) hors de la pastille."""
    r = size * 0.24
    lo, hi = r, size - 1 - r

    def in_badge(px, py):
        dx = (lo - px) if px < lo else (px - hi if px > hi else 0)
        dy = (lo - py) if py < lo else (py - hi if py > hi else 0)
        return dx * dx + dy * dy <= r * r

    ax, ay = size * 0.38, size * 0.30
    bx, by = size * 0.38, size * 0.70
    cx, cy = size * 0.70, size * 0.50

    def sign(px, py, x1, y1, x2, y2):
        return (px - x2) * (y1 - y2) - (x1 - x2) * (py - y2)

    def in_triangle(px, py):
        d1 = sign(px, py, ax, ay, bx, by)
        d2 = sign(px, py, bx, by, cx, cy)
        d3 = sign(px, py, cx, cy, ax, ay)
        neg = d1 < 0 or d2 < 0 or d3 < 0
        pos = d1 > 0 or d2 > 0 or d3 > 0
        return not (neg and pos)

    if not in_badge(x, y):
        return None
    return ACCENT_FG if in_triangle(x, y) else ACCENT


def _bmp_image(size):
    """DIB 32 bits (BITMAPINFOHEADER + XOR BGRA + masque AND) pour une taille."""
    header = struct.pack(
        "<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    xor = bytearray()
    for y in range(size - 1, -1, -1):       # BMP : lignes du bas vers le haut
        for x in range(size):
            px = _pixel(x, y, size)
            if px is None:
                xor += b"\x00\x00\x00\x00"   # transparent
            else:
                r, g, b = px
                xor += bytes((b, g, r, 255))
    and_row = ((size + 31) // 32) * 4        # masque 1bpp, lignes alignees 32b
    and_mask = b"\x00" * (and_row * size)
    return header + bytes(xor) + and_mask


def _png_chunk(kind, payload):
    """Chunk PNG : longueur, type, donnees, CRC32 (sur type + donnees)."""
    body = kind + payload
    return (struct.pack(">I", len(payload)) + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))


def _png_image(size):
    """PNG RGBA 8 bits, non entrelace (assez pour un aplat de deux couleurs)."""
    transparent = bytes(4)          # RGBA (0, 0, 0, 0)
    raw = bytearray()
    for y in range(size):
        raw += bytes(1)                 # octet de filtre (0 = None) par ligne
        for x in range(size):
            px = _pixel(x, y, size)
            raw += transparent if px is None else bytes(px) + OPAQUE
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 6 = RGBA
    return (PNG_MAGIC
            + _png_chunk(b"IHDR", ihdr)
            + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _png_chunk(b"IEND", b""))


def _write_ico():
    images = [(s, _bmp_image(s)) for s in SIZES]
    count = len(images)
    out = bytearray(struct.pack("<HHH", 0, 1, count))   # ICONDIR
    offset = 6 + 16 * count
    for size, data in images:
        out += struct.pack("<BBBBHHII", size & 0xFF, size & 0xFF, 0, 0,
                           1, 32, len(data), offset)
        offset += len(data)
    for _size, data in images:
        out += data
    with open(OUT_ICO, "wb") as f:
        f.write(out)
    print(f"Ecrit {os.path.normpath(OUT_ICO)} "
          f"({len(out)} octets, {count} tailles)")


def _write_png():
    data = _png_image(PNG_SIZE)
    with open(OUT_PNG, "wb") as f:
        f.write(data)
    print(f"Ecrit {os.path.normpath(OUT_PNG)} "
          f"({len(data)} octets, {PNG_SIZE}x{PNG_SIZE})")


def main():
    os.makedirs(ASSETS, exist_ok=True)
    _write_ico()
    _write_png()


if __name__ == "__main__":
    main()
