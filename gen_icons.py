#!/usr/bin/env python3
"""すみながしアプリのアイコンPNGを生成する（標準ライブラリのみ・Pillow不要）。

「一目で金魚と分かる」ことを最優先に、輪郭のはっきりした金魚を描く:
和紙＋ごく薄い色の水（はなやかモードの雰囲気）の上に、大きな赤い金魚
（卵型の胴 + 大きく広がる扇の尾びれ + 背びれ + 目 + 縁取り）をくっきり描画。
背景の水は柔らかいにじみ（吸収モデル）、金魚はスーパーサンプリングでアンチ
エイリアスした明確なシルエット。icon-180 / icon-192 / icon-512 を出力する。
"""
import math
import struct
import zlib

PAPER = (0.945, 0.922, 0.871)
ABSORB_K = 2.6
MUD_CUT = 0.75
DISP_MAX = 0.55

# 背景の水（はなやかモードの INKS と同一の吸収ベクトル・黒なし）
AO = (1.05, 0.50, 0.06)        # あお
KIIRO = (0.03, 0.14, 1.10)     # きいろ
MIDORI = (0.95, 0.10, 0.90)    # みどり
MURASAKI = (0.60, 1.00, 0.22)  # むらさき

# 四隅にごく薄い色の水（金魚を主役にするため控えめ）
DROPS = [
    (0.15, 0.16, 0.150, 0.30, AO, 0.7),
    (0.86, 0.18, 0.145, 0.28, KIIRO, 2.9),
    (0.14, 0.85, 0.140, 0.28, MIDORI, 1.8),
    (0.87, 0.84, 0.135, 0.26, MURASAKI, 5.1),
]

# 金魚（直接RGBで合成・くっきり）。赤金魚。
FISH_BODY = (0.93, 0.30, 0.15)   # 胴体（朱赤）
FISH_FIN = (0.97, 0.52, 0.22)    # ひれ・尾びれ（明るい橙でひらひら感）
FISH_LINE = (0.58, 0.13, 0.06)   # 縁取り（深い赤・黒は使わない）
EYE_WHITE = (0.99, 0.98, 0.95)
EYE_PUPIL = (0.16, 0.10, 0.09)   # 瞳（ごく小さい暗色・目の表現に限定）

FISH_TILT = -0.08          # やや頭上がり
FISH_CX, FISH_CY = 0.50, 0.50
OUTLINE = 1.075            # 縁取りのためのシルエット膨張率

# 胴体: (cx, cy, rx, ry, theta)
BODY = (0.545, 0.500, 0.200, 0.150, 0.0)
# ひれ・尾びれ（胴体の後ろ＝左に大きな扇）
FINS = [
    (0.235, 0.350, 0.165, 0.082, -0.46),  # 尾びれ上ろう
    (0.180, 0.500, 0.190, 0.086,  0.00),  # 尾びれ中ろう（大きく後ろへ）
    (0.235, 0.650, 0.165, 0.082,  0.46),  # 尾びれ下ろう
    (0.560, 0.330, 0.078, 0.090, -0.05),  # 背びれ（上へ）
    (0.520, 0.658, 0.078, 0.050,  0.28),  # 腹びれ（下へ）
]
EYE = (0.660, 0.452, 0.044)    # 白目
PUPIL = (0.668, 0.452, 0.022)  # 瞳
# 口: 頭の先のごく小さなくぼみ（縁取り色の点）
MOUTH = (0.742, 0.520, 0.018)

# 金魚を含むおおよその範囲（ここだけスーパーサンプリングする）
FISH_BBOX = (0.00, 0.84, 0.20, 0.80)
SS = 3  # スーパーサンプリング（3x3）


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


def bg_color(u, v, px, py):
    """背景（和紙 + ごく薄い色の水）の色 0..1。柔らかいので1サンプルで十分。"""
    fiber = (vnoise(u * 6, v * 6) * 0.45 + vnoise(u * 25, v * 25) * 0.35
             + vnoise(u * 110, v * 110) * 0.20)
    speck = hash01(px // 2, py // 2)
    shade = 0.965 + 0.055 * fiber + 0.012 * speck
    dens = [0.0, 0.0, 0.0]
    for (cx, cy, r, amp, absorb, phase) in DROPS:
        dx, dy = u - cx, v - cy
        d2 = dx * dx + dy * dy
        if d2 > (r * 2.4) ** 2:
            continue
        dn = math.sqrt(d2) / r
        g = amp * (math.exp(-dn ** 2.4) + 0.28 * math.exp(-((dn / 1.35) ** 2.0)))
        for i in range(3):
            dens[i] += absorb[i] * g
    mud = min(dens)
    dens = [min(max(0.0, d - MUD_CUT * mud), DISP_MAX) for d in dens]
    return [PAPER[i] * shade * math.exp(-ABSORB_K * dens[i]) for i in range(3)]


def _ell(u, v, cx, cy, rx, ry, th):
    """楕円の正規化距離の2乗（<=1 で内側）。"""
    dx, dy = u - cx, v - cy
    c, s = math.cos(th), math.sin(th)
    lx = dx * c + dy * s
    ly = -dx * s + dy * c
    return (lx / rx) ** 2 + (ly / ry) ** 2


def fish_layer(u, v):
    """点(u,v)の金魚レイヤーを返す。None=金魚外 / 'line'|'fin'|'body'|'eye'|'pupil'。"""
    # 金魚中心まわりで逆回転（全体の傾き）
    ct, st = math.cos(-FISH_TILT), math.sin(-FISH_TILT)
    ru = FISH_CX + (u - FISH_CX) * ct - (v - FISH_CY) * st
    rv = FISH_CY + (u - FISH_CX) * st + (v - FISH_CY) * ct

    # 目（胴体より前面）
    if (ru - PUPIL[0]) ** 2 + (rv - PUPIL[1]) ** 2 <= PUPIL[2] ** 2:
        return 'pupil'
    if (ru - EYE[0]) ** 2 + (rv - EYE[1]) ** 2 <= EYE[2] ** 2:
        return 'eye'
    # 口（縁取り色の小点）
    if (ru - MOUTH[0]) ** 2 + (rv - MOUTH[1]) ** 2 <= MOUTH[2] ** 2:
        return 'line'

    in_body = _ell(ru, rv, *BODY) <= 1.0
    if in_body:
        return 'body'
    for f in FINS:
        if _ell(ru, rv, *f) <= 1.0:
            return 'fin'
    # 縁取り（シルエットを膨張させた外周リング）
    o2 = OUTLINE ** 2
    if _ell(ru, rv, *BODY) <= o2:
        return 'line'
    for f in FINS:
        if _ell(ru, rv, *f) <= o2:
            return 'line'
    return None


LAYER_COLOR = {
    'line': FISH_LINE, 'fin': FISH_FIN, 'body': FISH_BODY,
    'eye': EYE_WHITE, 'pupil': EYE_PUPIL,
}


def render(size):
    rows = []
    inv = 1.0 / size
    bx0, bx1, by0, by1 = FISH_BBOX
    for py in range(size):
        row = bytearray()
        row.append(0)  # PNG filter: None
        v = (py + 0.5) * inv
        for px in range(size):
            u = (px + 0.5) * inv
            base = bg_color(u, v, px, py)
            if bx0 <= u <= bx1 and by0 <= v <= by1:
                # 金魚周辺はスーパーサンプリングでアンチエイリアス
                acc = [0.0, 0.0, 0.0]
                for sy in range(SS):
                    for sx in range(SS):
                        su = (px + (sx + 0.5) / SS) * inv
                        sv = (py + (sy + 0.5) / SS) * inv
                        lay = fish_layer(su, sv)
                        col = LAYER_COLOR[lay] if lay else base
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
