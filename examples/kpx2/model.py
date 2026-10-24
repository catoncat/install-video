"""快拼箱 2.0 参数化模型。

单位米。原点在箱体底面中心，X 为长度方向，Y 为宽度方向，-Y 为正面（带门）。
尺寸来自 source/快拼箱2.0/快拼箱2.0配置.xls；标注"推定"的是没有资料、按行业通用做法推的。
"""
from engine.geo import *

# ---------------- 尺寸 ----------------
L, W, H = 6.055, 2.990, 2.896      # 外尺寸
PX, PY = 0.210, 0.150              # 角柱截面 210×150
FH, RH = 0.160, 0.180              # 地面主梁高 160，屋面主梁高 180
T = 0.003                          # 型钢壁厚（实际 2.0，略加厚便于渲染）
BEAM_F = 0.12                      # 主梁翼缘宽（推定）
JOIST = (0.05, 0.10, 9)            # 地面次梁 方管 100×50，9 根
PURLIN = (0.08, 0.04, 6)           # 屋面次梁 C80×40，6 根
BOARD_T, PVC_T = 0.018, 0.0016     # 水泥纤维板 18 + 地板革 1.6
WALL_T = 0.05                      # 50 岩棉夹芯板
WALL_OFF = 0.01                    # 墙板外表面离框架外边的缩进
DOOR = (0.92, 2.03)
WINDOW = (1.13, 1.10)
SILL = 0.90                        # 窗台高度（推定）
PIPE_D = 0.05                      # 落水管 φ50（推定）

# 角柱节点（推定，参考视频 + 行业通用做法）：角件伸出两片耳板插进空心角柱，螺栓横向穿过柱壁和耳板
EAR_H = 0.12
BOLT_Z = 0.06                      # 螺栓孔离角件面的距离
BOLT_D = 0.012                     # M12
HOLE_U = (0.05, 0.035)             # 每个外面两孔间距的一半（X 面, Y 面）

FLOOR_TOP = FH + BOARD_T + PVC_T
ROOF_BOT = H - RH
POST_H = ROOF_BOT - FH
LONG_SPAN = L - 2 * PX
SHORT_SPAN = W - 2 * PY
BUNDLE_GAP = 0.38                  # 打包时顶框、底框之间夹层高度（推定）
BUNDLE_DROP = -(ROOF_BOT - FH - BUNDLE_GAP)   # 打包状态下顶框相对安装位置的 Z 偏移

# 墙板分格（沿墙从左到右的每段宽度），合计等于柱间净距
FRONT = [("panel", 1.15), ("door", 1.15), ("panel", 1.15), ("window", 1.30), ("panel", LONG_SPAN - 4.75)]
REAR = [("panel", LONG_SPAN - 4.75), ("panel", 1.15), ("window", 1.30), ("panel", 1.15), ("panel", 1.15)]
END = [("panel", SHORT_SPAN / 2), ("panel", SHORT_SPAN / 2)]

CORNERS = [(i, j, sx, sy) for i, sx in enumerate((-1, 1)) for j, sy in enumerate((-1, 1))]

def corner_xy(sx, sy):
    return sx * (L - PX) / 2, sy * (W - PY) / 2


# ---------------- 材质 ----------------
M = {}
def materials():
    M["frame"] = mat("frame_RAL9002", (0.80, 0.81, 0.78), 0.35, 0.42)
    M["panel"] = mat("wall_panel", (0.86, 0.86, 0.84), 0.1, 0.62)
    M["core"] = mat("rockwool", (0.80, 0.68, 0.42), 0.0, 0.95)
    M["board"] = mat("fiber_cement", (0.55, 0.55, 0.52), 0.0, 0.85)
    M["pvc"] = mat("pvc_floor", (0.62, 0.63, 0.64), 0.0, 0.45)
    M["roof"] = mat("aluzinc", (0.78, 0.79, 0.80), 0.9, 0.32)
    M["ceiling"] = mat("ceiling_831", (0.90, 0.90, 0.88), 0.2, 0.5)
    M["wool"] = mat("glass_wool", (0.92, 0.78, 0.38), 0.0, 0.95)
    M["door"] = mat("steel_door", (0.90, 0.90, 0.88), 0.3, 0.4)
    M["upvc"] = mat("upvc_white", (0.93, 0.93, 0.92), 0.0, 0.35)
    M["glass"] = mat("glass", (0.75, 0.85, 0.90), 0.0, 0.05, transmission=1.0)
    M["bar"] = mat("bar_galv", (0.70, 0.71, 0.72), 0.9, 0.35)
    M["handle"] = mat("handle", (0.20, 0.20, 0.21), 0.8, 0.3)
    M["concrete"] = mat("concrete", (0.40, 0.40, 0.39), 0.0, 0.9)
    M["site"] = mat("site_ground", (0.13, 0.135, 0.14), 0.0, 0.95)
    M["bolt"] = mat("bolt_zinc", (0.78, 0.77, 0.70), 1.0, 0.3)
    M["pipe"] = mat("pvc_pipe", (0.55, 0.57, 0.60), 0.0, 0.4)
    M["elec"] = mat("switch_white", (0.95, 0.95, 0.94), 0.0, 0.3)
    M["led"] = mat("led", (1.0, 0.97, 0.92), 0.0, 0.3, emission=4.0)
    M["guide"] = mat("guide_line", (1.0, 0.45, 0.05), 0.0, 0.5, emission=3.0)
    M["pack"] = mat("pack_wrap", (0.72, 0.74, 0.76), 0.0, 0.6)
    M["sealant"] = mat("sealant", (0.88, 0.88, 0.86), 0.0, 0.3)   # 浅色硅酮胶，和灰色屋面拉开


# ---------------- 部件 ----------------
def bolt_holes(sx, sy, z):
    """一个节点上的 4 个螺栓：[(位置, 轴, 朝外符号)]"""
    cx, cy = corner_xy(sx, sy)
    return ([((cx + du, sy * W / 2, z), "Y", sy) for du in (-HOLE_U[0], HOLE_U[0])] +
            [((sx * L / 2, cy + du, z), "X", sx) for du in (-HOLE_U[1], HOLE_U[1])])

def corner_fitting(name, sx, sy, z0, h, up, stage):
    """角件：实心冲压件 + 外侧长圆孔 + 朝 up 方向伸出的两片耳板"""
    cx, cy = corner_xy(sx, sy)
    zc = z0 + h / 2
    ob = box(name, (PX, PY, h), (cx, cy, zc), M["frame"], stage, 0.003)
    cut(ob, [("slot", (0.035, 0.03, h * 0.55), (cx + d, sy * W / 2, zc), "Y") for d in (-0.05, 0.05)] +
            [("slot", (0.035, 0.03, h * 0.55), (sx * L / 2, cy, zc), "X")])
    t, g = 0.006, 0.006
    ez = (z0 + h if up > 0 else z0 - EAR_H) + EAR_H / 2
    ear = boxes(name + "_ears", [((PX - 0.04, t, EAR_H), (cx, sy * (W / 2 - g - t / 2), ez)),
                                 ((t, PY - 0.04, EAR_H), (sx * (L / 2 - g - t / 2), cy, ez))], M["frame"], stage)
    zb = z0 + h + BOLT_Z if up > 0 else z0 - BOLT_Z
    cut(ear, [("cyl", (BOLT_D + 0.002, 0.05), c, a) for c, a, _ in bolt_holes(sx, sy, zb)])

def bolt(name, center, axis, sign):
    """六角头螺栓 + 垫片，头朝外。原点在柱外壁表面，["out"] 为朝外方向（动画用）"""
    out = Vector((sign, 0, 0) if axis == "X" else (0, sign, 0))
    u = Vector((0, 0, 1))
    v = out.cross(u)
    bm = bmesh.new()
    for r, d, off, seg in ((0.0105, 0.008, 0.0105, 6), (0.012, 0.0025, 0.00475, 32), (BOLT_D / 2, 0.045, -0.019, 16)):
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=d)
        for p in res["verts"]:
            p.co = p.co.x * v + p.co.y * u + (p.co.z + off) * out
    ob = obj(name, bm, M["bolt"], "09_fasteners", out=list(out), spin_axis=axis)
    ob.location = center
    return ob

def ground():
    # 现场混凝土地坪（深色，给基础一个"工地"的感觉）。引擎自带无缝背景地面（z=-0.21，颜色由 STYLE 的 floor 控制），
    # 一般产品不需要再建地面；要建就做成比产品暗的小块，别做大，不然边缘会变成一条地平线
    box("ground_pad", (14, 9, 0.02), (0, 0, -0.21), M["site"], "00_ground")

def foundation():
    # 推定：四角 + 长边中部混凝土墩，顶面找平到 ±0
    for i, x in enumerate((-L / 2 + 0.2, 0, L / 2 - 0.2)):
        for j, y in enumerate((-W / 2 + 0.2, W / 2 - 0.2)):
            box(f"pier_{i}{j}", (0.5, 0.5, 0.2), (x, y, -0.1), M["concrete"], "01_foundation", 0.005)

def floor_frame():
    st = "02_floor_frame"
    for i, j, sx, sy in CORNERS:
        corner_fitting(f"floor_corner_{i}{j}", sx, sy, 0, FH, 1, st)
    for sy, tag in ((-1, "front"), (1, "rear")):
        profile(f"floor_beam_{tag}", c_pts(FH, BEAM_F, T, -sy), LONG_SPAN, "X", (0, sy * W / 2, 0), M["frame"], st)
    for sx, tag in ((-1, "left"), (1, "right")):
        profile(f"floor_beam_{tag}", c_pts(FH, BEAM_F, T, sx), SHORT_SPAN, "Y", (sx * L / 2, 0, 0), M["frame"], st)
    w, h, n = JOIST
    for k in range(n):
        x = -LONG_SPAN / 2 + LONG_SPAN * (k + 0.5) / n
        box(f"floor_joist_{k}", (w, W - 2 * BEAM_F, h), (x, 0, FH - T - h / 2), M["frame"], st)
    channels(st, FH - 0.0015, up=True)

def floor_deck():
    st = "03_floor_deck"
    ix, iy = L / 2 - WALL_OFF - WALL_T, W / 2 - WALL_OFF - WALL_T
    nx, ny = PX - WALL_OFF - WALL_T, PY - WALL_OFF - WALL_T   # 角柱占掉的缺口
    n = 5
    bw = 2 * ix / n
    z = FH + BOARD_T / 2
    for k in range(n):
        x0, x1 = -ix + k * bw, -ix + (k + 1) * bw
        if k in (0, n - 1):
            e = x0 + nx if k == 0 else x1 - nx
            notch, full = ((x0, e), (e, x1)) if k == 0 else ((e, x1), (x0, e))
            boxes(f"floor_board_{k}", [((notch[1] - notch[0], 2 * (iy - ny), BOARD_T), (sum(notch) / 2, 0, z)),
                                       ((full[1] - full[0], 2 * iy, BOARD_T), (sum(full) / 2, 0, z))], M["board"], st)
        else:
            box(f"floor_board_{k}", (bw - 0.002, 2 * iy, BOARD_T), ((x0 + x1) / 2, 0, z), M["board"], st)
    zp = FH + BOARD_T + PVC_T / 2
    boxes("floor_pvc", [((2 * ix - 2 * nx, 2 * iy, PVC_T), (0, 0, zp)),
                        ((nx, 2 * (iy - ny), PVC_T), (-ix + nx / 2, 0, zp)),
                        ((nx, 2 * (iy - ny), PVC_T), (ix - nx / 2, 0, zp))], M["pvc"], st)

def posts():
    st = "04_posts"
    t = 0.004
    hx, hy = PX / 2, PY / 2
    outer = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    inner = [(-hx + t, -hy + t), (hx - t, -hy + t), (hx - t, hy - t), (-hx + t, hy - t)]
    for i, j, sx, sy in CORNERS:
        cx, cy = corner_xy(sx, sy)
        bm = bmesh.new()
        o0, i0, o1, i1 = [[bm.verts.new((cx + a, cy + b, z)) for a, b in ring]
                          for z in (FH, ROOF_BOT) for ring in (outer, inner)]
        for k in range(4):
            n = (k + 1) % 4
            bm.faces.new((o0[k], o0[n], o1[n], o1[k]))
            bm.faces.new((i0[n], i0[k], i1[k], i1[n]))
            bm.faces.new((o0[n], o0[k], i0[k], i0[n]))
            bm.faces.new((o1[k], o1[n], i1[n], i1[k]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        ob = obj(f"post_{i}{j}", bm, M["frame"], st)
        holes = bolt_holes(sx, sy, FH + BOLT_Z) + bolt_holes(sx, sy, ROOF_BOT - BOLT_Z)
        cut(ob, [("cyl", (BOLT_D + 0.002, 0.03), c, a) for c, a, _ in holes])
        add_bevel(ob, 0.002)
        # 落水管藏在角柱里（推定）
        cylinder(f"downpipe_{i}{j}", PIPE_D / 2, ROOF_BOT + 0.15, (cx - sx * 0.03, cy - sy * 0.02, (ROOF_BOT - 0.15) / 2),
                 "Z", M["pipe"], st)

def roof_frame():
    st = "05_roof_frame"
    for i, j, sx, sy in CORNERS:
        corner_fitting(f"roof_corner_{i}{j}", sx, sy, ROOF_BOT, RH, -1, st)
    for sy, tag in ((-1, "front"), (1, "rear")):
        profile(f"roof_beam_{tag}", c_pts(RH, BEAM_F, T, -sy), LONG_SPAN, "X", (0, sy * W / 2, ROOF_BOT), M["frame"], st)
    for sx, tag in ((-1, "left"), (1, "right")):
        profile(f"roof_beam_{tag}", c_pts(RH, BEAM_F, T, sx), SHORT_SPAN, "Y", (sx * L / 2, 0, ROOF_BOT), M["frame"], st)
    ph, pf, n = PURLIN
    for k in range(n):
        x = -LONG_SPAN / 2 + LONG_SPAN * (k + 0.5) / n
        profile(f"roof_purlin_{k}", c_pts(ph, pf, 0.002, -1), W - 2 * BEAM_F, "Y", (x - pf / 2, 0, H - 0.04 - ph),
                M["frame"], st)
    # 屋面板：360° 咬口，肋沿宽度方向
    ix, iy = L / 2 - BEAM_F, W / 2 - BEAM_F
    zr = H - 0.04
    ribs = int(2 * ix / 0.47)
    boxes("roof_sheet", [((2 * ix, 2 * iy, 0.0005), (0, 0, zr))] +
          [((0.012, 2 * iy, 0.03), (-ix + 2 * ix * k / ribs, 0, zr + 0.015)) for k in range(ribs + 1)], M["roof"], st)
    box("roof_insulation", (2 * ix, 2 * iy, 0.05), (0, 0, ROOF_BOT + 0.045), M["wool"], st)   # 吊顶之上
    # 831 吊顶板（推定在主梁下翼缘高度）
    cx, cy = L / 2 - WALL_OFF - WALL_T, W / 2 - WALL_OFF - WALL_T
    zc = ROOF_BOT + 0.005
    boxes("ceiling_831", [((2 * cx, 2 * cy, 0.0005), (0, 0, zc))] +
          [((0.02, 2 * cy, 0.008), (-cx + 0.277 * k, 0, zc - 0.004)) for k in range(int(2 * cx / 0.277) + 1)],
          M["ceiling"], st)
    # LED 灯 ×2，随顶框出厂预装
    for k, x in enumerate((-L / 4, L / 4)):
        box(f"led_{k}", (1.2, 0.08, 0.03), (x, 0, ROOF_BOT - 0.03), M["frame"], st)
        box(f"led_{k}_tube", (1.16, 0.05, 0.006), (x, 0, ROOF_BOT - 0.047), M["led"], st)
        # 灯管真正照亮室内（自发光只会让灯管本身变亮）
        lt = bpy.data.lights.new(f"led_{k}_light", "AREA")
        lt.shape, lt.size, lt.size_y, lt.energy = "RECTANGLE", 1.16, 0.05, 120
        lt.use_shadow = False      # 室内补光不投影：省阴影缓冲，拼箱时不会爆
        ob = bpy.data.objects.new(f"led_{k}_light", lt)
        ob.location = (x, 0, ROOF_BOT - 0.06)
        ob["stage"] = "10_services"   # 接电之后才亮；打包、吊装时不该照亮夹层
        coll("10_services").objects.link(ob)
    channels(st, ROOF_BOT + 0.0015, up=False)

def channels(stage, z, up):
    """墙板 U 形槽：底槽开口朝上，顶槽开口朝下"""
    t, h = 0.0015, 0.03
    w = WALL_T + 2 * t + 0.002
    u = [(-w / 2, 0), (w / 2, 0), (w / 2, h), (w / 2 - t, h), (w / 2 - t, t), (-w / 2 + t, t), (-w / 2 + t, h), (-w / 2, h)]
    pts = u if up else [(a, -b) for a, b in u]
    tag = "floor" if up else "roof"
    yc, xc = W / 2 - WALL_OFF - WALL_T / 2, L / 2 - WALL_OFF - WALL_T / 2
    for sy, side in ((-1, "front"), (1, "rear")):
        profile(f"{tag}_channel_{side}", pts, LONG_SPAN, "X", (0, sy * yc, z), M["frame"], stage)
    for sx, side in ((-1, "left"), (1, "right")):
        profile(f"{tag}_channel_{side}", pts, SHORT_SPAN, "Y", (sx * xc, 0, z), M["frame"], stage)

def walls():
    yc, xc = W / 2 - WALL_OFF - WALL_T / 2, L / 2 - WALL_OFF - WALL_T / 2
    wall_run("front", FRONT, "X", -yc, -1, -LONG_SPAN / 2)
    wall_run("rear", REAR, "X", yc, 1, -LONG_SPAN / 2)
    wall_run("left", END, "Y", -xc, -1, -SHORT_SPAN / 2)
    wall_run("right", END, "Y", xc, 1, -SHORT_SPAN / 2)

def wall_run(prefix, layout, axis, fixed, ns, start):
    z0, z1 = FH, ROOF_BOT
    gap = 0.003
    def P(u, v, du, dv, dd=WALL_T, off=0.0):
        n = fixed + ns * off
        return ((du, dd, dv), (u, n, v)) if axis == "X" else ((dd, du, dv), (n, u, v))
    s = start
    for k, (kind, w) in enumerate(layout):
        a0, a1 = s + gap / 2, s + w - gap / 2
        s += w
        mid, ww = (a0 + a1) / 2, a1 - a0
        if kind == "panel":
            parts = [P(mid, (z0 + z1) / 2, ww, z1 - z0)]
        else:
            ow, oh = DOOR if kind == "door" else WINDOW
            ob = FLOOR_TOP if kind == "door" else FLOOR_TOP + SILL
            ot = ob + oh
            side = (ww - ow) / 2
            parts = [P(a0 + side / 2, (z0 + z1) / 2, side, z1 - z0), P(a1 - side / 2, (z0 + z1) / 2, side, z1 - z0),
                     P(mid, (ot + z1) / 2, ow, z1 - ot)]
            if ob > z0:
                parts.append(P(mid, (z0 + ob) / 2, ow, ob - z0))
            opening(f"{prefix}_{kind}", kind, P, mid, ob, ow, oh, _out(axis, ns))
        boxes(f"{prefix}_wall_{k}_{kind}", parts, M["panel"], "06_walls", 0.002, out=_out(axis, ns))

def _out(axis, ns):
    return [ns, 0, 0] if axis == "Y" else [0, ns, 0]

def opening(name, kind, P, mid, ob, ow, oh, out):
    st = "07_door_window"
    kw = dict(out=out)
    fw, fd = 0.05, 0.07
    frame = [P(mid - ow / 2 + fw / 2, ob + oh / 2, fw, oh, fd), P(mid + ow / 2 - fw / 2, ob + oh / 2, fw, oh, fd),
             P(mid, ob + oh - fw / 2, ow, fw, fd)]
    if kind == "window":
        frame += [P(mid, ob + fw / 2, ow, fw, fd), P(mid, ob + oh / 2, 0.04, oh - 2 * fw, fd)]
        boxes(f"{name}_frame", frame, M["upvc"], st, 0.002, **kw)
        gw = (ow - 2 * fw - 0.04) / 2
        for k, sg in enumerate((-1, 1)):
            boxes(f"{name}_glass_{k}", [P(mid + sg * (gw / 2 + 0.02), ob + oh / 2, gw, oh - 2 * fw, 0.006, 0.01 * sg)],
                  M["glass"], st, **kw)
        n = 6
        bars = [P(mid - ow / 2 + fw + (ow - 2 * fw) * (k + 0.5) / n, ob + oh / 2, 0.014, oh - 2 * fw, 0.014, 0.05)
                for k in range(n)]
        bars += [P(mid, ob + oh * f, ow - 2 * fw, 0.03, 0.006, 0.05) for f in (0.33, 0.67)]
        boxes(f"{name}_bars", bars, M["bar"], st, **kw)
    else:
        boxes(f"{name}_frame", frame, M["door"], st, 0.002, **kw)
        lw, lh = ow - 2 * fw - 0.006, oh - fw - 0.01
        boxes(f"{name}_leaf", [P(mid, ob + 0.005 + lh / 2, lw, lh, 0.045)], M["door"], st, 0.003, **kw)
        boxes(f"{name}_handle", [P(mid + lw / 2 - 0.08, ob + 1.0, 0.13, 0.025, 0.025, s) for s in (0.05, -0.05)],
              M["handle"], st, **kw)

def trim():
    st = "08_trim"
    t = 0.0015
    for i, j, sx, sy in CORNERS:
        cx, cy = corner_xy(sx, sy)
        zc = FH + POST_H / 2
        boxes(f"post_wrap_{i}{j}", [((PX + 0.04, t, POST_H), (cx - sx * 0.02, sy * (W / 2 + t / 2), zc)),
                                   ((t, PY + 0.04, POST_H), (sx * (L / 2 + t / 2), cy - sy * 0.02, zc))], M["frame"], st,
              out=[sx * 0.707, sy * 0.707, 0])
    hh, zc = RH + 0.02, ROOF_BOT + RH / 2 + 0.01
    boxes("roof_wrap", [((L + 2 * t, t, hh), (0, -W / 2 - t / 2, zc)), ((L + 2 * t, t, hh), (0, W / 2 + t / 2, zc)),
                        ((t, W, hh), (-L / 2 - t / 2, 0, zc)), ((t, W, hh), (L / 2 + t / 2, 0, zc))], M["frame"], st)
    ix, iy = L / 2 - WALL_OFF - WALL_T, W / 2 - WALL_OFF - WALL_T
    z = FLOOR_TOP + 0.04
    boxes("skirting", [((2 * ix, 0.012, 0.08), (0, -iy + 0.006, z)), ((2 * ix, 0.012, 0.08), (0, iy - 0.006, z)),
                       ((0.012, 2 * iy, 0.08), (-ix + 0.006, 0, z)), ((0.012, 2 * iy, 0.08), (ix - 0.006, 0, z))],
          M["upvc"], st)

def fasteners():
    for i, j, sx, sy in CORNERS:
        for end, z in (("bot", FH + BOLT_Z), ("top", ROOF_BOT - BOLT_Z)):
            for k, (c, a, sg) in enumerate(bolt_holes(sx, sy, z)):
                bolt(f"bolt_{i}{j}_{end}_{k}", c, a, sg)

def services():
    st = "10_services"
    iy, ix = W / 2 - WALL_OFF - WALL_T, L / 2 - WALL_OFF - WALL_T
    door_x = -LONG_SPAN / 2 + 1.15 + 0.575
    dev = [("switch", (door_x + DOOR[0] / 2 + 0.2, -iy + 0.01, FLOOR_TOP + 1.3), "Y"),
           ("breaker", (door_x - DOOR[0] / 2 - 0.35, -iy + 0.04, FLOOR_TOP + 1.8), "Y"),
           ("ac_socket", (ix - 0.01, 0.6, FLOOR_TOP + 2.1), "X"),
           ("socket_0", (1.0, iy - 0.01, FLOOR_TOP + 0.3), "Y"),
           ("socket_1", (-1.5, iy - 0.01, FLOOR_TOP + 0.3), "Y"),
           ("socket_2", (-ix + 0.01, -0.6, FLOOR_TOP + 0.3), "X")]
    for name, c, a in dev:
        size = (0.30, 0.08, 0.40) if name == "breaker" else (0.086, 0.02, 0.086)
        if a == "X":
            size = (size[1], size[0], size[2])
        box(name, size, c, M["elec"], st, 0.003)
        h = ROOF_BOT - 0.01 - (c[2] + 0.05)
        box(name + "_conduit", (0.02, 0.012, h) if a == "Y" else (0.012, 0.02, h),
            (c[0], c[1], c[2] + 0.05 + h / 2), M["elec"], st)

def sealant():
    """顶框四边接缝防水胶：屋面板与顶梁内沿的交缝。原点在每条边的起点，沿 X/Y 伸展，方便做"挤胶"动画"""
    st = "08b_sealant"
    r = 0.02
    ix, iy, z = L / 2 - BEAM_F - r, W / 2 - BEAM_F - r, H - 0.04 + r   # 放在屋面板与梁内沿的阴角里，不被翼缘盖住
    for name, start, axis, length in (("seal_front", (-ix, -iy, z), "X", 2 * ix), ("seal_right", (ix, -iy, z), "Y", 2 * iy),
                                      ("seal_rear", (ix, iy, z), "X", -2 * ix), ("seal_left", (-ix, iy, z), "Y", -2 * iy)):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r, radius2=r, depth=abs(length))
        for v in bm.verts:   # 圆柱沿 Z → 沿 axis，起点在原点
            s = v.co.z + abs(length) / 2
            s = s if length > 0 else -s
            v.co = Vector((s, v.co.x, v.co.y)) if axis == "X" else Vector((v.co.x, s, v.co.y))
        ob = obj(name, bm, M["sealant"], st, grow_axis=axis)
        ob.location = start

def guides():
    """说明用辅助物（默认隐藏，由分镜调出）：对角线"""
    st = "90_guides"
    import math
    d = math.hypot(L, W)
    ang = math.atan2(W, L)
    for k, s in enumerate((1, -1)):
        ob = box(f"diag_{k}", (d - 0.3, 0.025, 0.025), (0, 0, FH + 0.03), M["guide"], st)
        ob.rotation_euler.z = s * ang

def bundle():
    """打包状态的夹层（推定）：顶框、底框之间夹着角柱、墙板、门窗、配件"""
    st = "91_bundle"
    box("bundle_pack", (L - 0.5, W - 0.4, BUNDLE_GAP - 0.04), (0, 0, FH + BUNDLE_GAP / 2), M["pack"], st, 0.01)


def build():
    materials()
    ground(); foundation(); floor_frame(); floor_deck(); posts(); roof_frame()
    walls(); trim(); sealant(); fasteners(); services(); guides(); bundle()
