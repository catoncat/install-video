"""Z 型折叠集装箱参数化模型。

单位米。原点在箱体底面中心，X 为长度方向，Y 为宽度方向，-Y 为正面（带门）。
模型按"展开后"的状态建；折叠 / 展开由 shots.py 里的 pose() 给各组对象打关键帧。
尺寸来自报价单（资料/Z-Foldable Container Quotation 261016.pdf）；标"推定"的是按照片和同类产品推的，见 资料整理.md。

对象分组（shots.pose 靠名字前缀找）：
  底框 @02_base · 顶框 @03_roof · 端墙 endL_* / endR_*（绕底部铰链转）· 长墙 wallF_* / wallR_*（绕底边转）
"""
import math
from engine.geo import *

# ---------------- 尺寸 ----------------
L, W, H = 5.900, 2.500, 2.470      # 外尺寸（报价单）
FH, RH = 0.16, 0.16                # 底框 / 顶框梁高：画面上做薄（报价单 240 / 243），给门留出高度
FIT = (0.18, 0.15)                 # 角件 180×150（报价单）
CX, CY = 0.15, 0.13                # 立柱截面（推定）
STUB = 0.19                        # 端墙铰链下的固定短柱高（推定：让端墙折叠时压在长墙上方）
WALL_T = 0.05                      # 50 mm EPS 夹芯板
DOOR = (0.84, 2.035)               # 钢门 840×2035
WINDOW = (0.80, 1.10)              # PVC 推拉窗 800×1100
SILL = 0.90                        # 窗台高（推定）
FOLD_DEG = 4.0                     # 折叠状态端墙与水平面的夹角（推定）

XE = L / 2 - CX / 2 - 0.015        # 端墙（立柱中心线）X
YC = W / 2 - CY / 2 - 0.01         # 立柱中心 Y
YL = W / 2 - 0.045                 # 长墙中心线 Y
HINGE_Z = FH + STUB                # 端墙铰链高度
HC = H - RH - HINGE_Z              # 端墙（含立柱）高度
HL = H - RH - FH                   # 长墙高度
LW = 2 * (XE - CX / 2 - 0.005)     # 长墙长度（两端立柱之间）
LONG_PIVOT_Z = FH + 0.03
REAR_LIFT = 0.055                  # 后长墙折叠时叠在前长墙上方
SPREADER_Z = H + 1.4               # 吊具横梁高度（展开状态下）
HOOK_Z = H + 3.0

CORNERS = [(i, j, sx, sy) for i, sx in enumerate((-1, 1)) for j, sy in enumerate((-1, 1))]


def roof_dz(theta_deg):
    """端墙角度 θ 时屋顶相对展开位置的 Z 偏移：墙顶始终顶在屋顶滑槽下"""
    t = math.radians(theta_deg)
    return HINGE_Z + HC * math.sin(t) + CX / 2 * math.cos(t) - (H - RH)

FOLDED_H = H + roof_dz(FOLD_DEG)   # 折叠后总高（画面用；报价单包装高 445）


# ---------------- 材质 ----------------
M = {}
def materials():
    M["frame"] = mat("frame_grey", (0.36, 0.38, 0.41), 0.4, 0.45)
    M["panel"] = mat("wall_panel", (0.88, 0.88, 0.86), 0.1, 0.6)
    M["panel_in"] = mat("wall_inner", (0.80, 0.81, 0.80), 0.1, 0.6)
    M["floor"] = mat("pvc_floor", (0.55, 0.50, 0.44), 0.0, 0.5)
    M["roof"] = mat("roof_sheet", (0.85, 0.86, 0.87), 0.6, 0.35)
    M["ceiling"] = mat("ceiling", (0.90, 0.90, 0.88), 0.2, 0.5)
    M["door"] = mat("steel_door", (0.86, 0.86, 0.84), 0.3, 0.4)
    M["upvc"] = mat("upvc_white", (0.93, 0.93, 0.92), 0.0, 0.35)
    M["glass"] = mat("glass", (0.70, 0.80, 0.86), 0.0, 0.05, transmission=1.0)
    M["bar"] = mat("bar_galv", (0.62, 0.63, 0.65), 0.9, 0.35)
    M["handle"] = mat("handle", (0.20, 0.20, 0.21), 0.8, 0.3)
    M["concrete"] = mat("concrete", (0.40, 0.40, 0.39), 0.0, 0.9)
    M["bolt"] = mat("bolt_zinc", (0.78, 0.77, 0.70), 1.0, 0.3)
    M["elec"] = mat("switch_white", (0.95, 0.95, 0.94), 0.0, 0.3)
    M["led"] = mat("led", (1.0, 0.97, 0.92), 0.0, 0.3, emission=4.0)
    M["sealant"] = mat("sealant", (0.95, 0.95, 0.93), 0.0, 0.3)
    M["cable"] = mat("steel_cable", (0.25, 0.25, 0.26), 0.8, 0.4)
    M["rig"] = mat("rig_yellow", (0.85, 0.62, 0.10), 0.3, 0.5)


# ---------------- 小工具 ----------------
def rod(name, p0, p1, r, material, stage, **props):
    """两点之间的圆杆（钢丝绳）"""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=r, radius2=r, depth=d.length)
    q = Vector((0, 0, 1)).rotation_difference(d.normalized())
    for v in bm.verts:
        v.co = (p0 + p1) / 2 + q @ v.co
    return obj(name, bm, material, stage, **props)

def wall(prefix, axis, fixed, ns, span, z0, z1, openings, stage):
    """一面夹芯板墙（含门窗洞）。axis="X"：墙沿 X（长墙），"Y"：墙沿 Y（端墙）。
       openings = [(kind, 中心 u, 底标高)]；门窗也归入同一前缀，跟墙一起转"""
    def P(u, v, du, dv, dd=WALL_T, off=0.0):
        n = fixed + ns * off
        return ((du, dd, dv), (u, n, v)) if axis == "X" else ((dd, du, dv), (n, u, v))
    a0, a1 = span
    cuts = sorted([(u - (DOOR if k == "door" else WINDOW)[0] / 2, u + (DOOR if k == "door" else WINDOW)[0] / 2, k, u, b)
                   for k, u, b in openings])
    parts, s = [], a0
    for c0, c1, kind, u, b in cuts:
        parts.append(P((s + c0) / 2, (z0 + z1) / 2, c0 - s, z1 - z0))
        ow, oh = DOOR if kind == "door" else WINDOW
        parts.append(P(u, (b + oh + z1) / 2, ow, z1 - b - oh))
        if b > z0:
            parts.append(P(u, (z0 + b) / 2, ow, b - z0))
        opening(f"{prefix}_{kind}", kind, P, u, b, ow, oh, stage)
        s = c1
    parts.append(P((s + a1) / 2, (z0 + z1) / 2, a1 - s, z1 - z0))
    out = [ns, 0, 0] if axis == "Y" else [0, ns, 0]
    boxes(f"{prefix}_panel", parts, M["panel"], stage, 0.002, out=out)
    # 板缝：每 1150 一条浅槽线，外表面
    seams = [P(a0 + k * 1.15, (z0 + z1) / 2, 0.006, z1 - z0 - 0.02, 0.004, WALL_T / 2)
             for k in range(1, int((a1 - a0) / 1.15) + 1) if a0 + k * 1.15 < a1 - 0.1
             and not any(c0 - 0.05 < a0 + k * 1.15 < c1 + 0.05 for c0, c1, *_ in cuts)]
    if seams:
        boxes(f"{prefix}_seams", seams, M["panel_in"], stage)
    return P

def opening(name, kind, P, mid, ob, ow, oh, stage):
    fw, fd = 0.05, 0.07
    frame = [P(mid - ow / 2 + fw / 2, ob + oh / 2, fw, oh, fd), P(mid + ow / 2 - fw / 2, ob + oh / 2, fw, oh, fd),
             P(mid, ob + oh - fw / 2, ow, fw, fd)]
    if kind == "window":
        frame += [P(mid, ob + fw / 2, ow, fw, fd), P(mid, ob + oh / 2, 0.04, oh - 2 * fw, fd)]
        boxes(f"{name}_frame", frame, M["upvc"], stage, 0.002)
        gw = (ow - 2 * fw - 0.04) / 2
        for k, sg in enumerate((-1, 1)):
            boxes(f"{name}_glass_{k}", [P(mid + sg * (gw / 2 + 0.02), ob + oh / 2, gw, oh - 2 * fw, 0.006, 0.01 * sg)],
                  M["glass"], stage)
        n = 5
        bars = [P(mid - ow / 2 + fw + (ow - 2 * fw) * (k + 0.5) / n, ob + oh / 2, 0.014, oh - 2 * fw, 0.014, 0.05)
                for k in range(n)]
        bars += [P(mid, ob + oh * f, ow - 2 * fw, 0.03, 0.006, 0.05) for f in (0.33, 0.67)]
        boxes(f"{name}_bars", bars, M["bar"], stage)
    else:
        boxes(f"{name}_frame", frame, M["door"], stage, 0.002)
        lw, lh = ow - 2 * fw - 0.006, oh - fw - 0.01
        boxes(f"{name}_leaf", [P(mid, ob + 0.005 + lh / 2, lw, lh, 0.045)], M["door"], stage, 0.003)
        boxes(f"{name}_handle", [P(mid + lw / 2 - 0.08, ob + 1.0, 0.13, 0.025, 0.025, s) for s in (0.05, -0.05)],
              M["handle"], stage)


# ---------------- 部件 ----------------
def foundation():
    # 推定：四角各一个混凝土墩，顶面找平到 ±0
    for i, j, sx, sy in CORNERS:
        box(f"pier_{i}{j}", (0.5, 0.5, 0.2), (sx * (L / 2 - 0.2), sy * (W / 2 - 0.2), -0.1), M["concrete"],
            "01_foundation", 0.005)

def frame_ring(tag, z0, h, stage):
    """一圈主梁 + 4 个角件"""
    fx, fy = FIT
    for i, j, sx, sy in CORNERS:
        box(f"{tag}_corner_{i}{j}", (fx, fy, h + 0.004), (sx * (L / 2 - fx / 2), sy * (W / 2 - fy / 2), z0 + h / 2),
            M["frame"], stage, 0.006)
    t = 0.12
    for sy, side in ((-1, "front"), (1, "rear")):
        box(f"{tag}_beam_{side}", (L - 2 * fx, t, h), (0, sy * (W / 2 - t / 2), z0 + h / 2), M["frame"], stage, 0.004)
    for sx, side in ((-1, "left"), (1, "right")):
        box(f"{tag}_beam_{side}", (t, W - 2 * fy, h), (sx * (L / 2 - t / 2), 0, z0 + h / 2), M["frame"], stage, 0.004)

def base():
    st = "02_base"
    frame_ring("base", 0, FH, st)
    box("floor_deck", (L - 0.24, W - 0.24, 0.02), (0, 0, FH - 0.01), M["floor"], st)
    # 端墙铰链下的固定短柱 + 下护板（推定）
    for i, j, sx, sy in CORNERS:
        box(f"stub_{i}{j}", (CX - 0.004, CY - 0.004, STUB),      # 比立柱小一圈，侧面不共面（防闪烁）
            (sx * XE, sy * YC, FH + STUB / 2), M["frame"], st, 0.004)
    for sx, side in ((-1, "left"), (1, "right")):
        box(f"stub_panel_{side}", (WALL_T - 0.004, 2 * (YC - CY / 2) - 0.004, STUB), (sx * XE, 0, FH + STUB / 2), M["panel"], st, 0.002)
        # 铰链座
        for sy in (-1, 1):
            cylinder(f"hinge_{side}_{'f' if sy < 0 else 'r'}", 0.03, 0.06, (sx * XE, sy * (YC - CY / 2 - 0.05), HINGE_Z),
                     "Y", M["frame"], st)

def roof():
    st = "03_roof"
    z0 = H - RH
    frame_ring("roof", z0, RH, st)
    # 屋面彩钢瓦：肋沿宽度方向
    ix, iy = L / 2 - 0.12, W / 2 - 0.12
    ribs = int(2 * ix / 0.2)
    boxes("roof_sheet", [((2 * ix, 2 * iy, 0.004), (0, 0, H - 0.03))] +
          [((0.05, 2 * iy, 0.02), (-ix + 2 * ix * k / ribs, 0, H - 0.018)) for k in range(ribs + 1)], M["roof"], st)
    box("ceiling", (L - 0.24, W - 0.24, 0.01), (0, 0, z0 + 0.005), M["ceiling"], st)
    for k, x in enumerate((-L / 4, L / 4)):
        box(f"led_{k}", (0.6, 0.6, 0.02), (x, 0, z0 - 0.01), M["led"], st)
    # 屋顶下的滑槽（端墙顶部沿它滑动）
    for sy in (-1, 1):
        box(f"roof_track_{'f' if sy < 0 else 'r'}", (L - 0.4, 0.06, 0.04), (0, sy * (YC + 0.004), z0 - 0.02 + 0.003), M["frame"], st)

def end_walls():
    for sx, tag in ((-1, "L"), (1, "R")):
        st = f"04_end_{tag}"
        pre = f"end{tag}"
        for sy in (-1, 1):
            box(f"{pre}_col_{'f' if sy < 0 else 'r'}", (CX, CY, HC), (sx * XE, sy * YC, HINGE_Z + HC / 2),
                M["frame"], st, 0.004)
        span = (-(YC - CY / 2), YC - CY / 2)
        ops = [("window", 0.0, FH + SILL)] if tag == "L" else []      # 推定：左端墙一扇窗
        wall(pre, "Y", sx * XE, sx, span, HINGE_Z, H - RH, ops, st)
        # 顶部滑轮
        for sy in (-1, 1):
            cylinder(f"{pre}_roller_{'f' if sy < 0 else 'r'}", 0.035, 0.05, (sx * XE, sy * YC, H - RH - 0.04),
                     "Y", M["bolt"], st)

def long_walls():
    for sy, tag in ((-1, "F"), (1, "R")):
        st = f"05_wall_{tag}"
        pre = f"wall{tag}"
        ops = [("door", -1.6, FH), ("window", 1.2, FH + SILL)] if tag == "F" else []   # 推定：门、窗在正面
        P = wall(pre, "X", sy * YL, sy, (-LW / 2, LW / 2), FH, H - RH, ops, st)
        if tag == "R":
            # 室内开关、插座（报价单：2 开关 3 插座；位置推定，放后墙，剖视时看得到）
            inner = -(WALL_T / 2 + 0.01)
            boxes(f"{pre}_switch", [P(-1.6 + 0.6 + k * 0.1, FH + 1.3, 0.086, 0.086, 0.02, inner) for k in (0, 1)],
                  M["elec"], st)
            boxes(f"{pre}_socket", [P(u, FH + 0.3, 0.086, 0.086, 0.02, inner) for u in (-0.4, 0.6, 2.2)], M["elec"], st)

def bolts():
    """立柱上下两端的连接螺栓（数量、规格推定，画面示意）"""
    st = "06_bolts"
    for i, j, sx, sy in CORNERS:
        x = sx * (XE + CX / 2)
        for end, zs in (("bot", (HINGE_Z - 0.06, HINGE_Z + 0.07)), ("top", (H - RH - 0.07, H - RH + 0.05))):
            for k, z in enumerate(zs):
                bolt(f"bolt_{i}{j}_{end}_{k}", (x, sy * YC, z), sx, st)

def bolt(name, center, sign, stage):
    out = Vector((sign, 0, 0))
    u = Vector((0, 0, 1))
    v = out.cross(u)
    bm = bmesh.new()
    for r, d, off, seg in ((0.0105, 0.008, 0.0105, 6), (0.012, 0.0025, 0.00475, 32), (0.006, 0.045, -0.019, 16)):
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=d)
        for p in res["verts"]:
            p.co = p.co.x * v + p.co.y * u + (p.co.z + off) * out
    ob = obj(name, bm, M["bolt"], stage, out=list(out), spin_axis="X")
    ob.location = center

def trims():
    """四角包柱收边条"""
    st = "07_trim"
    t = 0.0015
    for i, j, sx, sy in CORNERS:
        x, y = sx * XE, sy * YC
        h = HC + STUB
        zc = FH + h / 2
        boxes(f"trim_{i}{j}", [((CX + 0.03, t, h), (x, y + sy * (CY / 2 + t), zc)),
                               ((t, CY + 0.03, h), (x + sx * (CX / 2 + t), y, zc))], M["frame"], st,
              out=[sx * 0.707, sy * 0.707, 0])

def sealant():
    """前长墙顶部与顶框之间的密封胶（原点在起点，沿 X 生长）"""
    st = "08_seal"
    r = 0.022          # 画面上加粗，远景也看得见
    for name, y in (("seal_front", -(YL + WALL_T / 2 + r * 0.5 + 0.003)), ("seal_rear", YL + WALL_T / 2 + r * 0.5 + 0.008)):
        bm = bmesh.new()
        sl = LW - 0.006                 # 两端各缩 3 mm，端面不和墙板端面共面（防闪烁）
        bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=r, radius2=r, depth=sl)
        for vv in bm.verts:
            vv.co = Vector((vv.co.z + sl / 2, vv.co.x, vv.co.y))
        ob = obj(name, bm, M["sealant"], st, grow_axis="X")
        ob.location = (-sl / 2, y, H - RH - r * 0.5)

def rig():
    """吊具：吊钩 + 横梁框 + 钢丝绳。底部吊点那组绳子按折叠状态的长度建"""
    st = "20_rig"
    ex, ey = L / 2 + 0.04, W / 2 + 0.04
    corners = [(sx * ex, sy * ey) for sx in (-1, 1) for sy in (-1, 1)]
    t = 0.08
    boxes("rig_spreader", [((2 * ex, t, t), (0, -ey, SPREADER_Z)), ((2 * ex, t, t), (0, ey, SPREADER_Z)),
                           ((t, 2 * ey, t), (-ex, 0, SPREADER_Z)), ((t, 2 * ey, t), (ex, 0, SPREADER_Z))], M["rig"], st)
    for k, (x, y) in enumerate(corners):
        rod(f"rig_sling_{k}", (x, y, SPREADER_Z), (0, 0, HOOK_Z), 0.012, M["cable"], st)
    box("rig_hook", (0.25, 0.12, 0.35), (0, 0, HOOK_Z + 0.15), M["rig"], st, 0.02)
    rod("rig_line", (0, 0, HOOK_Z + 0.3), (0, 0, HOOK_Z + 12), 0.015, M["cable"], st)
    # 吊顶角件（展开用）
    for k, (sx, sy) in enumerate((sx, sy) for sx in (-1, 1) for sy in (-1, 1)):
        x, y = sx * (L / 2 - FIT[0] / 2), sy * (W / 2 - FIT[1] / 2)
        rod(f"rigtop_{k}", (sx * ex, sy * ey, SPREADER_Z), (x, y, H + 0.01), 0.01, M["cable"], "21_rig_top")
    # 吊底角件（落位用）：外侧垂直下到底角件，长度按折叠状态
    zb = 0.05 - roof_dz(FOLD_DEG)
    for k, (x, y) in enumerate(corners):
        rod(f"rigbot_{k}", (x, y, SPREADER_Z), (x, y, zb), 0.01, M["cable"], "22_rig_bot")
        box(f"rigbot_shackle_{k}", (0.06, 0.06, 0.08), (x, y, zb), M["rig"], "22_rig_bot")


def build():
    materials()
    foundation(); base(); roof(); end_walls(); long_walls()
    bolts(); trims(); sealant(); rig()
