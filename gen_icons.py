#!/usr/bin/env python3
"""すみながしアプリのアイコンPNGを生成する（標準ライブラリのみ・Pillow不要）。

同心の墨流しリング（藍・和紙・朱・和紙・墨）に正弦波の揺らぎを加えた
マーブリング風デザイン。icon-180 / icon-192 / icon-512 を出力する。
"""
import math
import struct
import zlib

PAPER = (0xF3, 0xEC, 0xDF)
RINGS = [
    # (半径比, 色) — 外側から順に。中心に近いリングほど後で上書きされる
    (0.46, (0x2E, 0x4D, 0x8E)),  # 藍
    (0.36, PAPER),               # 和紙
    (0.27, (0xC4, 0x3C, 0x2E)),  # 朱
    (0.17, PAPER),               # 和紙
    (0.09, (0x1F, 0x1F, 0x1F)),  # 墨
]


def render(size):
    """RGBAバッファ（PNGスキャンライン形式）を生成。"""
    rows = []
    half = size / 2
    for y in range(size):
        row = bytearray()
        row.append(0)  # PNG filter type: None
        for x in range(size):
            dx, dy = x - half, y - half
            d = math.hypot(dx, dy)
            a = math.atan2(dy, dx)
            # 角度に応じて半径しきい値を波打たせる（マーブリング感）
            wobble = 1 + 0.06 * math.sin(5 * a + 1.3) + 0.03 * math.sin(9 * a)
            color = PAPER
            for ratio, ring_color in RINGS:
                if d < size * ratio * wobble:
                    color = ring_color
            row += bytes(color) + b"\xff"
        rows.append(bytes(row))
    return b"".join(rows)


def write_png(path, size):
    raw = render(size)

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8bit RGBA
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)
    print(f"wrote {path} ({size}x{size}, {len(png)} bytes)")


if __name__ == "__main__":
    for s, name in [(180, "icon-180.png"), (192, "icon-192.png"), (512, "icon-512.png")]:
        write_png(name, s)
