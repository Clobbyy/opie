#!/usr/bin/env python3
"""
Render the Opie app icon master PNG (1024x1024, RGBA) with pure standard library.

A rounded-square ("squircle") with an indigo->violet gradient and three white
lighting faders at different levels — "voice-controlled lighting board".

This is a DEV tool, not shipped at runtime. Build the .icns with:

    python3 tools/make_icon.py /tmp/opie_master.png
    # then sips/iconutil turn it into opie/resources/Opie.icns (see the PR notes)

Output is antialiased via signed-distance-field coverage, so 1024 is crisp on
its own and downsizes cleanly.
"""
import math
import struct
import sys
import zlib

SIZE = 1024


def srgb(*c):
    return tuple(c)


TOP = srgb(99, 102, 241)      # indigo-500  #6366F1
BOTTOM = srgb(139, 92, 246)   # violet-500  #8B5CF6
WHITE = srgb(255, 255, 255)


def clamp01(x):
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def sd_round_rect(px, py, cx, cy, hx, hy, r):
    qx = abs(px - cx) - (hx - r)
    qy = abs(py - cy) - (hy - r)
    outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
    inside = min(max(qx, qy), 0.0)
    return outside + inside - r


def sd_vcapsule(px, py, x, y0, y1, r):
    cy = y0 if py < y0 else (y1 if py > y1 else py)
    return math.hypot(px - x, py - cy) - r


def over(dst, src, a):
    """Porter-Duff src-over onto an opaque-or-transparent dst (premultiplied-free)."""
    dr, dg, db, da = dst
    sr, sg, sb = src
    na = a + da * (1 - a)
    if na <= 0:
        return (0, 0, 0, 0.0)
    nr = (sr * a + dr * da * (1 - a)) / na
    ng = (sg * a + dg * da * (1 - a)) / na
    nb = (sb * a + db * da * (1 - a)) / na
    return (nr, ng, nb, na)


def render():
    s = SIZE
    cx = cy = s / 2
    half = 0.402 * s          # squircle half-size (≈ 824px box → ~10% padding)
    rad = 0.224 * (2 * half)  # corner radius

    # Fader geometry.
    track_x = [cx - 0.176 * s, cx, cx + 0.176 * s]
    ty0, ty1 = 0.355 * s, 0.645 * s
    track_r = 0.010 * s
    knob_hx, knob_hy = 0.072 * s, 0.026 * s
    knob_r = knob_hy
    knob_y = [0.585 * s, 0.430 * s, 0.530 * s]   # varied levels

    px_bytes = bytearray()
    for y in range(s):
        px_bytes.append(0)  # PNG filter byte: none
        fy = y + 0.5
        ty = fy / s
        grad = (TOP[0] + (BOTTOM[0] - TOP[0]) * ty,
                TOP[1] + (BOTTOM[1] - TOP[1]) * ty,
                TOP[2] + (BOTTOM[2] - TOP[2]) * ty)
        for x in range(s):
            fx = x + 0.5
            px = (0.0, 0.0, 0.0, 0.0)

            d = sd_round_rect(fx, fy, cx, cy, half, half, rad)
            a = clamp01(0.5 - d)
            if a > 0:
                px = over(px, grad, a)

            if px[3] > 0:  # only draw faders on top of the squircle
                for xx in track_x:
                    dt = sd_vcapsule(fx, fy, xx, ty0, ty1, track_r)
                    at = clamp01(0.5 - dt) * 0.22
                    if at > 0:
                        px = over(px, WHITE, at)
                for xx, ky in zip(track_x, knob_y):
                    dk = sd_round_rect(fx, fy, xx, ky, knob_hx, knob_hy, knob_r)
                    ak = clamp01(0.5 - dk)
                    if ak > 0:
                        px = over(px, WHITE, ak)

            r, g, b, al = px
            px_bytes += bytes((int(r + 0.5), int(g + 0.5), int(b + 0.5),
                               int(al * 255 + 0.5)))
    return bytes(px_bytes)


def write_png(path, raw, w=SIZE, h=SIZE):
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)  # 8-bit RGBA
    idat = zlib.compress(raw, 9)
    with open(path, "wb") as f:
        f.write(sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b""))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "opie_master.png"
    write_png(out, render())
    print("wrote", out)
