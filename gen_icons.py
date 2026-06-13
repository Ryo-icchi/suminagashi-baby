#!/usr/bin/env python3
"""すみながしアプリのアイコンPNGを生成する（標準ライブラリのみ・Pillow不要）。

アプリ本編に泳ぐ金魚と同じ「やわらかい水彩・墨にじみ調」のコーラル色の金魚を、
和紙＋淡い青い水のにじみの上に描く。輪郭はカートゥーン風の硬い線ではなく、
水彩のように少しにじむが、しずく型の胴＋流れる二股の尾びれという上品で明確な
シルエットで「金魚」と分かるようにする。icon-180 / icon-192 / icon-512 を出力。
"""
import math
import struct
import zlib

PAPER = (0.952, 0.930, 0.882)        # 和紙の生成り
WATER = (0.66, 0.75, 0.84)           # 淡い青い水のにじみ
WATER_C = (0.50, 0.46)               # 水のにじみの中心（やや上）
WATER_R = 0.42                       # 水のにじみの広がり
WATER_STRENGTH = 0.42

# 金魚の色（水彩コーラル・黒も硬い縁取りも使わない）
BODY_COL = (0.93, 0.47, 0.30)        # 胴体（コーラル橙）
FIN_COL = (0.95, 0.57, 0.44)         # 尾びれ・ひれ（明るいサーモンで透け感）
RIM_COL = (0.82, 0.31, 0.19)         # 縁ににじみが溜まる深い橙（水彩の縁プール）
EYE_COL = (0.42, 0.17, 0.13)         # 目（ごく小さな暗色の点）

# 金魚の配置（横向き・頭は右／尾は左。ほぼ水平にして「耳」化を断つ）
FISH_C = (0.50, 0.50)
FISH_ANGLE = -0.05                   # rad（ほぼ水平・頭がほんの少し上）
FISH_SCALE = 0.58                    # 参考画像のように水の中を泳ぐ小さめサイズ（周りに余白）
FEATHER = 0.072                      # 縁のにじみ幅（小=くっきり / 大=やわらか）

# ローカル座標（頭=+x 右向き・原点=胴中心）でのパーツ:
# (cx, cy, rx, ry, theta, category) category: 'body' or 'fin'
# 尾は1つの繋がった扇（fan）を後方へ長く流し、先端2点で二股を示唆。ひれは細く後方へ流す
# （丸い突起が手足に見えないように）
BODY_PARTS = [
    (0.04, 0.00, 0.300, 0.150, 0.0, 'body'),  # 胴体（横長しずく型・後方へ細る）
    (0.20, 0.00, 0.115, 0.125, 0.0, 'body'),  # 頭側をやや丸く
]
FIN_PARTS = [
    (-0.30,  0.000, 0.090, 0.050, 0.00, 'fin'),  # 尾の付け根（胴と扇を繋ぐ・細い）
    (-0.50, -0.115, 0.235, 0.058, 0.42, 'fin'),  # 尾びれ上ろう（付け根から上へ開く扇）
    (-0.50,  0.115, 0.235, 0.058, -0.42, 'fin'), # 尾びれ下ろう（付け根から下へ開く扇）
    (-0.05, -0.150, 0.120, 0.038, -0.20, 'fin'), # 背びれ（細く後方へ流す）
    (-0.02,  0.150, 0.092, 0.032,  0.22, 'fin'), # 腹びれ（細く後方へ）
    (0.12,   0.108, 0.082, 0.026,  0.78, 'fin'), # 胸びれ（細く後ろ下へ流す）
]
EYE_LOCAL = (0.195, -0.026, 0.023)   # 目（ローカル座標・半径）
SS = 3


def hash01(ix, iy):
    return math.modf(math.sin(ix * 127.1 + iy * 311.7) * 43758.5453123)[0] % 1.0


def vnoise(x, y):
    ix, fx = math.floor(x), x - math.floor(x)
    iy, fy = math.floor(y), y - math.floor(y)
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    a = hash01(ix, iy)
    b = hash01(ix + 1, iy)
    c = hash01(ix, iy + 1)
    d = hash01(ix + 1, iy + 1)
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy


def smoothstep(e0, e1, x):
    if e0 == e1:
        return 0.0 if x < e0 else 1.0
    t = (x - e0) / (e1 - e0)
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def bg_color(u, v, px, py):
    """和紙 + 淡い青い水のにじみ。"""
    fiber = (vnoise(u * 6, v * 6) * 0.45 + vnoise(u * 24, v * 24) * 0.35
             + vnoise(u * 105, v * 105) * 0.20)
    speck = hash01(px // 2, py // 2)
    shade = 0.965 + 0.05 * fiber + 0.012 * speck
    col = [PAPER[i] * shade for i in range(3)]
    d = math.hypot(u - WATER_C[0], v - WATER_C[1])
    # にじみのムラ（水彩らしく不均一に）
    wob = 0.85 + 0.30 * vnoise(u * 4 + 3.1, v * 4 + 7.7)
    w = WATER_STRENGTH * math.exp(-((d / WATER_R) ** 2.2)) * wob
    w = max(0.0, min(WATER_STRENGTH, w))
    return [col[i] * (1 - w) + WATER[i] * w for i in range(3)]


def _nd(lx, ly, cx, cy, rx, ry, th):
    """ローカル点(lx,ly)の楕円正規化距離（1で縁）。"""
    dx, dy = lx - cx, ly - cy
    c, s = math.cos(th), math.sin(th)
    ex = dx * c + dy * s
    ey = -dx * s + dy * c
    return math.sqrt((ex / rx) ** 2 + (ey / ry) ** 2)


def fish_pixel(u, v, base):
    """背景色 base の上に金魚を水彩調で合成して返す。"""
    # グローバル→ローカル（頭=+x）
    c, s = math.cos(FISH_ANGLE), math.sin(FISH_ANGLE)
    dx, dy = (u - FISH_C[0]) / FISH_SCALE, (v - FISH_C[1]) / FISH_SCALE
    lx = dx * c + dy * s
    ly = -dx * s + dy * c

    nd_body = min((_nd(lx, ly, *p[:5]) for p in BODY_PARTS), default=9.9)
    nd_fin = min((_nd(lx, ly, *p[:5]) for p in FIN_PARTS), default=9.9)
    nd_min = min(nd_body, nd_fin)
    cov = smoothstep(1.0 + FEATHER, 1.0 - FEATHER, nd_min)
    if cov <= 0.0:
        return base

    base_col = BODY_COL if nd_body <= nd_fin else FIN_COL
    # 縁に深い色が溜まる水彩プール（中心=本来色 / 縁=深い橙）
    core = smoothstep(1.0, 0.45, nd_min)
    col = [RIM_COL[i] + (base_col[i] - RIM_COL[i]) * core for i in range(3)]
    # 内部の淡いムラ（紙に染みた感じ）
    mott = 0.96 + 0.07 * vnoise(lx * 9 + 11.0, ly * 9 + 5.0)
    col = [col[i] * mott for i in range(3)]
    # 目（小さな暗点・胴の上）
    ed = math.hypot(lx - EYE_LOCAL[0], ly - EYE_LOCAL[1])
    if ed < EYE_LOCAL[2] * 1.6:
        ecov = smoothstep(EYE_LOCAL[2] * 1.3, EYE_LOCAL[2] * 0.6, ed)
        col = [col[i] + (EYE_COL[i] - col[i]) * ecov for i in range(3)]

    return [base[i] * (1 - cov) + col[i] * cov for i in range(3)]


def render(size):
    rows = []
    inv = 1.0 / size
    for py in range(size):
        row = bytearray()
        row.append(0)
        for px in range(size):
            u = (px + 0.5) * inv
            v = (py + 0.5) * inv
            base = bg_color(u, v, px, py)
            acc = [0.0, 0.0, 0.0]
            for sy in range(SS):
                for sx in range(SS):
                    su = (px + (sx + 0.5) / SS) * inv
                    sv = (py + (sy + 0.5) / SS) * inv
                    col = fish_pixel(su, sv, base)
                    acc[0] += col[0]; acc[1] += col[1]; acc[2] += col[2]
            n = SS * SS
            base = [acc[0] / n, acc[1] / n, acc[2] / n]
            row += bytes(max(0, min(255, round(base[i] * 255))) for i in range(3)) + b"\xff"
        rows.append(bytes(row))
    return b"".join(rows)


def write_png(path, size):
    raw = render(size)

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    print(f"wrote {path} ({size}x{size}, {len(png)} bytes)")


if __name__ == "__main__":
    for s, name in [(180, "icon-180.png"), (192, "icon-192.png"), (512, "icon-512.png")]:
        write_png(name, s)
