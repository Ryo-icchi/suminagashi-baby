#!/usr/bin/env python3
"""すみながしアプリのアイコンPNGを生成する（標準ライブラリのみ・Pillow不要）。

アプリ本体（v4.3-kirei・はなやかモード）と同じ表示パイプラインで描く:
和紙の上に、1歳児がぽとぽと落とした鮮やかな色の柔らかい滴と、指でなぞった
細い流れ筋。**黒は使わない**（はなやかモードの INKS と同一・濁り除去 mudCut /
濃度上限 dispMax をアイコンにも適用して、本体と同じ「綺麗さ優先」の発色にする）。
icon-180 / icon-192 / icon-512 を出力する。
"""
import math
import struct
import zlib

PAPER = (0.945, 0.922, 0.871)  # index.html PAPER_RGB と同一
ABSORB_K = 2.6                 # displayShader の exp(-dye * 2.6)
MUD_CUT = 0.75                 # はなやか: 全チャンネル共通の濁り成分を抜く
DISP_MAX = 0.55                # 表示濃度の上限（黒を数学的に出力不能にする）

# 吸収ベクトル（index.html の INKS = はなやかモードと同一・黒は無い）
AKA = (0.06, 1.05, 1.00)       # あか（ビビッド朱赤）
AO = (1.05, 0.50, 0.06)        # あお（コバルト）
KIIRO = (0.03, 0.14, 1.10)     # きいろ（ビビッド黄）
MIDORI = (0.95, 0.10, 0.90)    # みどり（鮮緑）
DAIDAI = (0.05, 0.55, 1.05)    # だいだい（橙）
MURASAKI = (0.60, 1.00, 0.22)  # むらさき（明るい紫）

# 滴: (中心x, 中心y, 半径, 濃さ, 吸収ベクトル, 揺らぎ位相) — 座標/半径は 0..1
# 背景の水: 鮮やかな色の柔らかい滴を四隅に軽く散らす（中央の赤い金魚を引き立てる・黒なし）。
# 金魚が赤なので、近接する色は赤を避けて配色（混ざっても濁らない）
DROPS = [
    (0.25, 0.28, 0.115, 0.48, AO, 0.7),        # あお（左上）
    (0.74, 0.29, 0.110, 0.46, KIIRO, 2.9),     # きいろ（右上）
    (0.27, 0.74, 0.105, 0.46, MIDORI, 1.8),    # みどり（左下）
    (0.75, 0.73, 0.100, 0.44, MURASAKI, 5.1),  # むらさき（右下）
]

# 流れ筋: (吸収ベクトル, 濃さ, 線半径, 揺らぎ位相, [(x,y), ...]制御点) — 水の流れ
# 金魚の周りを縫う、すみながし特有の細い渦の筋（黒くならず色のまま残る・控えめに）。
# 制御点は Catmull-Rom スプラインで滑らかな曲線に補間する（折れ線の角を消す）。
STROKES = [
    (AO, 0.30, 0.015, 1.3,
     [(0.16, 0.40), (0.26, 0.32), (0.40, 0.30), (0.52, 0.34)]),
    (MURASAKI, 0.28, 0.014, 3.1,
     [(0.84, 0.58), (0.74, 0.66), (0.60, 0.70), (0.46, 0.69)]),
]

# 金魚（はなやかモードの赤系で・黒なし）。中央でやや右上を向いて泳ぐ。
# 各パーツ: (中心x, 中心y, 横半径rx, 縦半径ry, 回転theta[rad], 濃さamp, 減衰指数, 吸収ベクトル)
FISH_TILT = -0.13  # 全体をやや頭上がりに傾ける
FISH_CX, FISH_CY = 0.52, 0.51
FISH_PARTS = [
    (0.535, 0.510, 0.130, 0.096, 0.0,  0.72, 2.5, AKA),    # 胴体（卵型・主役・頭は右）
    (0.380, 0.510, 0.028, 0.040, 0.0,  0.46, 1.8, AKA),    # 尾の付け根（くびれを細く）
    (0.250, 0.430, 0.092, 0.046, -0.62, 0.46, 1.6, DAIDAI),# 尾びれ上ろう（広げる・橙で軽やか）
    (0.250, 0.590, 0.092, 0.046,  0.62, 0.46, 1.6, DAIDAI),# 尾びれ下ろう
    (0.540, 0.392, 0.058, 0.042, -0.15, 0.44, 1.7, DAIDAI),# 背びれ
    (0.490, 0.625, 0.046, 0.030, 0.30, 0.38, 1.7, DAIDAI), # 腹びれ
]
EYE_CX, EYE_CY, EYE_R = 0.610, 0.485, 0.023  # 目（紙の白を抜く）+ 瞳


def catmull_rom(pts, steps=14):
    """制御点を Catmull-Rom スプラインで密な滑らか曲線に展開する。"""
    if len(pts) < 3:
        return pts
    ext = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(pts[-1])
    return out


# 制御点を滑らかな密ポリラインに前展開
STROKES = [(absorb, amp, lr, phase, catmull_rom(pts))
           for (absorb, amp, lr, phase, pts) in STROKES]


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


def seg_dist(px, py, ax, ay, bx, by):
    """点(px,py)と線分(a-b)の最短距離。"""
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    c1 = vx * wx + vy * wy
    if c1 <= 0:
        return math.hypot(px - ax, py - ay)
    c2 = vx * vx + vy * vy
    if c2 <= c1:
        return math.hypot(px - bx, py - by)
    t = c1 / c2
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def goldfish(u, v, dens):
    """中央の金魚を吸収ベクトル空間に加算する（赤系・黒なし・目は紙の白抜き）。"""
    # 全体をやや頭上がりに傾けるため、金魚中心まわりで座標を逆回転
    ct, st = math.cos(-FISH_TILT), math.sin(-FISH_TILT)
    ru = FISH_CX + (u - FISH_CX) * ct - (v - FISH_CY) * st
    rv = FISH_CY + (u - FISH_CX) * st + (v - FISH_CY) * ct
    for (cx, cy, rx, ry, th, amp, pe, absorb) in FISH_PARTS:
        dx, dy = ru - cx, rv - cy
        ec, es = math.cos(th), math.sin(th)
        lx = dx * ec + dy * es
        ly = -dx * es + dy * ec
        nd = math.sqrt((lx / rx) ** 2 + (ly / ry) ** 2)
        if nd > 2.6:
            continue
        g = amp * (math.exp(-nd ** pe) + 0.20 * math.exp(-((nd / 1.5) ** 2.0)))
        for i in range(3):
            dens[i] += absorb[i] * g
    # 目: 胴体の赤を小さく白抜き（紙が覗く）→ ぷっくりした金魚の目に。瞳は控えめな点
    ed = math.hypot(ru - EYE_CX, rv - EYE_CY)
    if ed < EYE_R * 3.0:
        carve = math.exp(-((ed / (EYE_R * 1.15)) ** 2.0))   # 白抜き量
        for i in range(3):
            dens[i] *= (1 - 0.92 * carve)
        pupil = 0.42 * math.exp(-((ed / (EYE_R * 0.5)) ** 2.0))  # 瞳（あおで・黒にしない）
        for i in range(3):
            dens[i] += AO[i] * pupil


def density(u, v):
    """点(u,v)での墨密度（吸収ベクトル空間・3チャンネル）を合成する。"""
    dens = [0.0, 0.0, 0.0]
    for (cx, cy, r, amp, absorb, phase) in DROPS:
        dx, dy = u - cx, v - cy
        d2 = dx * dx + dy * dy
        if d2 > (r * 2.4) ** 2:
            continue
        ang = math.atan2(dy, dx)
        # 縁のごく僅かな揺らぎ（強いと花びら状になる・実物のにじみは滑らか）
        wob = 1 + 0.018 * math.sin(5 * ang + phase) + 0.010 * math.sin(8 * ang + phase * 1.7)
        dn = math.sqrt(d2) / max(r * wob, 1e-6)
        # コア（濃い芯）+ ハロ（羽毛状のにじみ）
        g = amp * (math.exp(-dn ** 2.4) + 0.28 * math.exp(-((dn / 1.35) ** 2.0)))
        for i in range(3):
            dens[i] += absorb[i] * g
    for (absorb, amp, lr, phase, pts) in STROKES:
        best = 1e9
        for j in range(len(pts) - 1):
            best = min(best, seg_dist(u, v, pts[j][0], pts[j][1], pts[j + 1][0], pts[j + 1][1]))
            if best < 1e-4:
                break
        if best > lr * 3.2:
            continue
        # 線からの距離でガウス減衰（細い筋）
        wob = 1 + 0.05 * math.sin(28 * best + phase)
        dn = best / max(lr * wob, 1e-6)
        g = amp * math.exp(-dn ** 2.0)
        for i in range(3):
            dens[i] += absorb[i] * g
    goldfish(u, v, dens)
    return dens


def render(size):
    """RGBAバッファ（PNGスキャンライン形式）を生成。"""
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
            # --- 墨密度の合成 ---
            dye = density(u, v)
            # --- 本体 displayShader と同じ「綺麗さ優先」処理 ---
            mud = min(dye)                      # 全チャンネル共通の濁り成分
            dye = [max(0.0, d - MUD_CUT * mud) for d in dye]
            dye = [min(d, DISP_MAX) for d in dye]  # 黒を出力不能にする上限
            color = bytes(
                max(0, min(255, round(PAPER[i] * shade * math.exp(-ABSORB_K * dye[i]) * 255)))
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
