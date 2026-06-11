#!/usr/bin/env python3
"""すみながしアプリのアイコンPNGを生成する（標準ライブラリのみ・Pillow不要）。

アプリ本体と同じ「吸収モデル（紙色 × exp(-墨密度)）」で描く:
和紙テクスチャの上に、1歳児がぽとぽと落としたような柔らかい墨滴
（墨・朱・藍・山吹）と、指でなぞった流れ筋。エッジは羽毛状。
icon-180 / icon-192 / icon-512 を出力する。
"""
import math
import struct
import zlib

PAPER = (0.945, 0.922, 0.871)
ABSORB_K = 2.6  # アプリの displayShader と同じ減衰係数

# 吸収ベクトル（index.html の INKS / PALETTE_INKS と同一）
SUMI = (0.85, 0.83, 0.79)
SHU = (0.26, 0.70, 0.74)
AI = (0.80, 0.66, 0.40)
YAMABUKI = (0.12, 0.30, 0.82)

# 墨滴: (中心x, 中心y, 半径, 濃さ, 吸収ベクトル, 揺らぎ位相) — 座標/半径は 0..1
# 1歳児が画面をぽとぽとタップした感じ: 大きい墨1つ + 色とりどりの小滴
DROPS = [
    (0.38, 0.40, 0.165, 1.50, SUMI, 0.7),      # 主役の墨（左上寄り・大きく）
    (0.72, 0.33, 0.105, 1.25, SHU, 2.9),       # 朱
    (0.33, 0.75, 0.095, 1.25, AI, 5.1),        # 藍
    (0.74, 0.68, 0.075, 1.15, YAMABUKI, 1.8),  # 山吹
    (0.57, 0.62, 0.045, 1.00, SUMI, 4.2),      # 墨の小滴（ちょん、と）
]


def hash01(ix, iy):
    """決定論の擬似乱数（シェーダの hash と同役割）。"""
    return math.modf(math.sin(ix * 127.1 + iy * 311.7) * 43758.5453123)[0] % 1.0


def vnoise(x, y):
    """値ノイズ（バイリニア補間）。"""
    ix, fx = math.floor(x), x - math.floor(x)
    iy, fy = math.floor(y), y - math.floor(y)
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    a = hash01(ix, iy)
    b = hash01(ix + 1, iy)
    c = hash01(ix, iy + 1)
    d = hash01(ix + 1, iy + 1)
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy


def render(size):
    """RGBAバッファ（PNGスキャンライン形式）を生成。"""
    blobs = DROPS
    rows = []
    for py in range(size):
        row = bytearray()
        row.append(0)  # PNG filter type: None
        v = py / size
        for px in range(size):
            u = px / size
            # --- 和紙: 低周波の繊維ムラ + 粒子（displayShader と同式） ---
            fiber = (vnoise(u * 6, v * 6) * 0.45
                     + vnoise(u * 25, v * 25) * 0.35
                     + vnoise(u * 110, v * 110) * 0.20)
            speck = hash01(px // 2, py // 2)
            shade = 0.965 + 0.055 * fiber + 0.012 * speck
            # --- 墨密度の合成（色ごとの吸収 × コア+ハロの2層減衰） ---
            dens = [0.0, 0.0, 0.0]
            for (cx, cy, r, amp, absorb, phase) in blobs:
                dx, dy = u - cx, v - cy
                d2 = dx * dx + dy * dy
                if d2 > (r * 2.4) ** 2:
                    continue
                ang = math.atan2(dy, dx)
                # 縁の揺らぎはごく僅か（強いと花びら状のノッチが出る・実物のにじみは滑らかな円）
                wob = 1 + 0.018 * math.sin(5 * ang + phase) + 0.010 * math.sin(8 * ang + phase * 1.7)
                dn = math.sqrt(d2) / max(r * wob, 1e-6)
                # コア（濃い芯）+ ハロ（羽毛状のにじみ）。ハロは控えめに（広げすぎると濁る）
                g = amp * (math.exp(-dn ** 2.4) + 0.28 * math.exp(-((dn / 1.35) ** 2.0)))
                dens[0] += absorb[0] * g
                dens[1] += absorb[1] * g
                dens[2] += absorb[2] * g
            color = bytes(
                max(0, min(255, round(PAPER[i] * shade * math.exp(-ABSORB_K * dens[i]) * 255)))
                for i in range(3)
            )
            row += color + b"\xff"
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
