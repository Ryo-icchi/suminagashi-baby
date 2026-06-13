#!/usr/bin/env python3
"""すみながしアプリのアイコンPNGを生成する（標準ライブラリのみ・Pillow不要）。

設計方針（プロのアイコン設計＋本物の墨流しアルゴリズムを踏まえる）:
- 背景レイヤー = 本物の墨流し（Mathematical Marbling: 面積保存のインク滴で同心円
  リングを作り、櫛 tine でドラッグして流れる模様にする / Lu,Jaffer,Jin,Zhao,Mao）。
  伝統的すみながしらしい藍×生成りの上品な同心円を、櫛で優雅に流す。
- 前景レイヤー = コーラル色の金魚（単一の焦点）。背景より高彩度で主役として浮かせる。
- 小サイズ（60px）でも金魚が一目で分かること（焦点を1つに絞る原則）。
内部 2x でレンダリングしてダウンサンプル（全体をアンチエイリアス）。
icon-180 / icon-192 / icon-512 を出力する。
"""
import math
import struct
import zlib

# ---------------- 色 ----------------
PAPER = (0.953, 0.933, 0.886)         # 和紙の生成り
WATER_BASE = (0.955, 0.945, 0.915)    # 水面（明るい生成り・線を主役に）

# 墨流しのインク線の色（藍を主に・濃淡で奥行き）。線（筋）として細く描く
INK_DEEP = (0.14, 0.26, 0.46)         # 濃藍
INK_BLUE = (0.20, 0.40, 0.60)         # 藍
INK_TEAL = (0.26, 0.52, 0.60)         # 青緑
INK_AQUA = (0.42, 0.64, 0.70)         # 淡い藍
CREAM = (0.955, 0.945, 0.915)         # （後方互換・未使用）

# 金魚（水彩コーラル・黒も硬い縁取りも使わない）
BODY_COL = (0.95, 0.45, 0.27)
FIN_COL = (0.97, 0.56, 0.42)
RIM_COL = (0.83, 0.29, 0.17)
EYE_COL = (0.32, 0.13, 0.11)

# ---------------- 金魚の配置 ----------------
FISH_C = (0.50, 0.51)
FISH_ANGLE = -0.05
FISH_SCALE = 0.60
FEATHER = 0.042       # 輪郭をやや立てて小サイズ視認性を上げる（背景が賑やかなため）
BODY_PARTS = [
    (0.04, 0.00, 0.300, 0.150, 0.0, 'body'),
    (0.20, 0.00, 0.115, 0.125, 0.0, 'body'),
]
FIN_PARTS = [
    (-0.30,  0.000, 0.090, 0.050, 0.00, 'fin'),
    (-0.50, -0.115, 0.235, 0.058, 0.42, 'fin'),
    (-0.50,  0.115, 0.235, 0.058, -0.42, 'fin'),
    (-0.05, -0.150, 0.120, 0.038, -0.20, 'fin'),
    (-0.02,  0.150, 0.092, 0.032,  0.22, 'fin'),
    (0.12,   0.108, 0.082, 0.026,  0.78, 'fin'),
]
EYE_LOCAL = (0.195, -0.026, 0.023)
FISH_REACH = 0.46     # 金魚合成を行う中心からの半径（最適化）
SS = 2                # 内部スーパーサンプリング


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
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


# ================= 墨流しエンジン（Mathematical Marbling） =================
def build_marble():
    """インク滴（面積保存変換）＋櫛 tine で同心円の流れ模様を作る。
    返り値: [(color, [(x,y), ...]), ...]（古い順＝奥から手前へ）。座標は 0..1。"""
    drops = []  # (color, points)

    def drop(cx, cy, r, color, n=200):
        # 既存の全点を外側へ押し出す（面積保存: |p'-c| = sqrt(|p-c|^2 + r^2)）
        for _col, pts in drops:
            for i in range(len(pts)):
                px, py = pts[i]
                dx, dy = px - cx, py - cy
                d2 = dx * dx + dy * dy
                f = math.sqrt(1.0 + r * r / d2) if d2 > 1e-12 else 1.0
                pts[i] = (cx + dx * f, cy + dy * f)
        # 新しい円を最前面に追加（半径を低周波ノイズで揺らして有機的に＝真円にしない）
        seed = len(drops) * 1.7
        ring = []
        for k in range(n):
            a = 2 * math.pi * k / n
            wob = (1.0 + 0.05 * math.sin(3 * a + seed) + 0.035 * math.sin(5 * a - seed * 0.7)
                   + 0.025 * math.sin(8 * a + seed))
            rr = r * wob
            ring.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        drops.append((color, ring))

    def comb(drag_axis, drag_amt, teeth_axis, t0, spacing, count, falloff):
        """櫛: teeth_axis 方向に等間隔の歯。各点を drag_axis 方向へ、最寄りの歯から
        の距離でガウス減衰させてドラッグ＝marbling のフェザー模様を作る。"""
        teeth = [t0 + k * spacing for k in range(count)]
        w = spacing * falloff
        for _col, pts in drops:
            for i in range(len(pts)):
                px, py = pts[i]
                coord = px if teeth_axis == 'x' else py
                dmin = min(abs(coord - t) for t in teeth)
                disp = drag_amt * math.exp(-((dmin / w) ** 2))
                if drag_axis == 'y':
                    pts[i] = (px, py + disp)
                else:
                    pts[i] = (px + disp, py)

    # --- 複数の中心に滴を落とす（面積保存で互いに押し合い、重なり合う不規則な
    #     リング＝本物のすみながしの有機的な筋模様になる）。各リングは細線で描く ---
    # 塗りの色帯（藍×生成りを交互に）で同心バンドを作り、櫛で流す＝本物のマーブル。
    bands = [INK_DEEP, CREAM, INK_BLUE, CREAM, INK_TEAL, CREAM,
             INK_BLUE, CREAM, INK_AQUA, CREAM, INK_DEEP, CREAM]
    # 主中心: 大きめの同心バンドでキャンバスを満たす
    r = 0.40
    for col in bands:
        drop(0.50, 0.49, r, col)
        r -= 0.032
    # 副中心で有機的に重ねる
    drop(0.30, 0.35, 0.10, INK_BLUE)
    drop(0.30, 0.35, 0.065, CREAM)
    drop(0.72, 0.66, 0.10, INK_TEAL)
    drop(0.72, 0.66, 0.065, CREAM)
    # --- 櫛（comb）で大きくドラッグして同心円を崩す＝marbling のフェザー模様 ---
    comb('y',  0.085, 'x', 0.10, 0.20, 5, 0.45)   # 縦に引く櫛（歯は横並び）
    comb('y', -0.085, 'x', 0.20, 0.20, 5, 0.45)   # 逆向きでフェザーに
    comb('x',  0.085, 'y', 0.10, 0.20, 5, 0.45)   # 横に引く櫛（直交）
    comb('x', -0.060, 'y', 0.22, 0.22, 5, 0.45)   # 戻し
    return drops


def fill_poly(buf, N, pts, color):
    """多角形を scanline で塗る（even-odd）。pts は 0..1。buf は float RGB（N*N*3）。"""
    P = [(x * N, y * N) for (x, y) in pts]
    ys = [p[1] for p in P]
    y0 = max(0, int(math.floor(min(ys))))
    y1 = min(N - 1, int(math.ceil(max(ys))))
    n = len(P)
    cr, cg, cb = color
    for y in range(y0, y1 + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            x1, yy1 = P[i]
            x2, yy2 = P[(i + 1) % n]
            if (yy1 <= yc < yy2) or (yy2 <= yc < yy1):
                xs.append(x1 + (yc - yy1) / (yy2 - yy1) * (x2 - x1))
        if len(xs) < 2:
            continue
        xs.sort()
        rowbase = y * N
        for k in range(0, len(xs) - 1, 2):
            xa = max(0, int(math.ceil(xs[k] - 0.5)))
            xb = min(N - 1, int(math.floor(xs[k + 1] - 0.5)))
            idx = (rowbase + xa) * 3
            for _x in range(xa, xb + 1):
                buf[idx] = cr; buf[idx + 1] = cg; buf[idx + 2] = cb
                idx += 3


def _stamp(buf, N, cx, cy, rad, color):
    """中心(cx,cy)に半径radの円を置く（線スタンプ用）。"""
    x0 = max(0, int(cx - rad)); x1 = min(N - 1, int(cx + rad))
    y0 = max(0, int(cy - rad)); y1 = min(N - 1, int(cy + rad))
    r2 = rad * rad
    cr, cg, cb = color
    for y in range(y0, y1 + 1):
        dy = y + 0.5 - cy
        base = y * N
        for x in range(x0, x1 + 1):
            dx = x + 0.5 - cx
            if dx * dx + dy * dy <= r2:
                idx = (base + x) * 3
                buf[idx] = cr; buf[idx + 1] = cg; buf[idx + 2] = cb


def stroke_poly(buf, N, pts, color, width):
    """多角形の輪郭を太さ width の線で描く（墨流しのインクの筋）。pts は 0..1。"""
    w = max(0.6, width / 2.0)
    P = [(x * N, y * N) for (x, y) in pts]
    n = len(P)
    for i in range(n):
        x1, y1 = P[i]
        x2, y2 = P[(i + 1) % n]
        seg = math.hypot(x2 - x1, y2 - y1)
        steps = max(1, int(seg / (w * 0.7)))
        for s in range(steps + 1):
            t = s / steps
            _stamp(buf, N, x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, w, color)


def box_blur(buf, N, rad, passes=2):
    """分離型ボックスぼかし（インクのにじみ＝柔らかい縁を作る）。端はクランプ。"""
    if rad < 1:
        return buf
    w = 2 * rad + 1
    src = buf
    for _ in range(passes):
        # 横方向
        dst = [0.0] * len(src)
        for y in range(N):
            base = y * N * 3
            for ch in range(3):
                s = 0.0
                for x in range(-rad, rad + 1):
                    s += src[base + max(0, min(N - 1, x)) * 3 + ch]
                for x in range(N):
                    dst[base + x * 3 + ch] = s / w
                    s += (src[base + min(N - 1, x + rad + 1) * 3 + ch]
                          - src[base + max(0, x - rad) * 3 + ch])
        # 縦方向
        src2 = dst
        dst2 = [0.0] * len(src2)
        for x in range(N):
            for ch in range(3):
                col = x * 3 + ch
                s = 0.0
                for y in range(-rad, rad + 1):
                    s += src2[max(0, min(N - 1, y)) * N * 3 + col]
                for y in range(N):
                    dst2[y * N * 3 + col] = s / w
                    s += (src2[min(N - 1, y + rad + 1) * N * 3 + col]
                          - src2[max(0, y - rad) * N * 3 + col])
        src = dst2
    return src


def _nd(lx, ly, cx, cy, rx, ry, th):
    dx, dy = lx - cx, ly - cy
    c, s = math.cos(th), math.sin(th)
    ex = dx * c + dy * s
    ey = -dx * s + dy * c
    return math.sqrt((ex / rx) ** 2 + (ey / ry) ** 2)


def fish_pixel(u, v, base):
    """背景色 base の上に金魚を水彩調で合成。金魚外は base のまま返す。"""
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
    core = smoothstep(1.0, 0.45, nd_min)
    col = [RIM_COL[i] + (base_col[i] - RIM_COL[i]) * core for i in range(3)]
    mott = 0.96 + 0.07 * vnoise(lx * 9 + 11.0, ly * 9 + 5.0)
    col = [col[i] * mott for i in range(3)]
    ed = math.hypot(lx - EYE_LOCAL[0], ly - EYE_LOCAL[1])
    if ed < EYE_LOCAL[2] * 1.6:
        ecov = smoothstep(EYE_LOCAL[2] * 1.3, EYE_LOCAL[2] * 0.6, ed)
        col = [col[i] + (EYE_COL[i] - col[i]) * ecov for i in range(3)]
    # うっすら影で前景として浮かせる（金魚の下側を少し暗く）
    return [base[i] * (1 - cov) + col[i] * cov for i in range(3)]


def render(size):
    N = size * SS
    inv = 1.0 / N
    # --- 背景: 水面 + 墨流し ---
    buf = [0.0] * (N * N * 3)
    for py in range(N):
        v = (py + 0.5) * inv
        rowbase = py * N
        for px in range(N):
            u = (px + 0.5) * inv
            fiber = (vnoise(u * 6, v * 6) * 0.45 + vnoise(u * 24, v * 24) * 0.35
                     + vnoise(u * 105, v * 105) * 0.20)
            shade = 0.97 + 0.045 * fiber
            idx = (rowbase + px) * 3
            buf[idx] = WATER_BASE[0] * shade
            buf[idx + 1] = WATER_BASE[1] * shade
            buf[idx + 2] = WATER_BASE[2] * shade
    for color, pts in build_marble():
        fill_poly(buf, N, pts, color)

    # --- 墨流しをぼかしてインクのにじみ（柔らかい縁）にする ---
    buf = box_blur(buf, N, max(1, round(N * 0.008)), passes=2)

    # --- 前景: 金魚（焦点）を合成 ---
    fx0 = int(max(0, (FISH_C[0] - FISH_REACH) * N))
    fx1 = int(min(N - 1, (FISH_C[0] + FISH_REACH) * N))
    fy0 = int(max(0, (FISH_C[1] - FISH_REACH) * N))
    fy1 = int(min(N - 1, (FISH_C[1] + FISH_REACH) * N))
    for py in range(fy0, fy1 + 1):
        v = (py + 0.5) * inv
        rowbase = py * N
        for px in range(fx0, fx1 + 1):
            u = (px + 0.5) * inv
            idx = (rowbase + px) * 3
            base = (buf[idx], buf[idx + 1], buf[idx + 2])
            col = fish_pixel(u, v, base)
            buf[idx] = col[0]; buf[idx + 1] = col[1]; buf[idx + 2] = col[2]

    # --- SS でダウンサンプル ---
    out = bytearray()
    for oy in range(size):
        out.append(0)  # PNG filter: None
        for ox in range(size):
            r = g = b = 0.0
            for sy in range(SS):
                yy = oy * SS + sy
                for sx in range(SS):
                    xx = ox * SS + sx
                    idx = (yy * N + xx) * 3
                    r += buf[idx]; g += buf[idx + 1]; b += buf[idx + 2]
            n = SS * SS
            out += bytes((max(0, min(255, round(r / n * 255))),
                          max(0, min(255, round(g / n * 255))),
                          max(0, min(255, round(b / n * 255))), 255))
    return bytes(out)


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
