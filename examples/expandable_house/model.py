"""20FT 可扩展集装箱房（Expandable Container House）参数化模型。

单位米。原点在主箱底面中心，X 为长度方向，Y 为宽度方向（两侧侧翼沿 ±Y 展开），-X 端是带玻璃推拉门的正门。
尺寸来自 资料/Expandable Container Quotation 261016.pdf（20FT：展开 5.85×6.3×2.5，折叠 5.85×2.25×2.5）。
展开机构没有资料，按同类产品推定（见 分镜_expandable_house.md）：
  侧翼屋顶绕主箱顶边上翻；侧翼地板绕主箱底边放平；端墙绕主箱角部转出；侧墙从箱内平推到外沿。
模型按"展开后"建模，运输时的折叠状态用 pose("folded", ...) 登记，分镜里 set_pose / to_pose 切换。
"""
from engine.geo import *

# ---------------- 尺寸 ----------------
L, CW, H = 5.85, 2.25, 2.5          # 主箱（= 折叠运输尺寸）
WW = (6.3 - CW) / 2                 # 单侧侧翼宽 2.025
POST = 0.16                         # 加强柱 160×160
FH = 0.18                           # 底框高
FLOOR = 0.20                        # 地板面标高
RB = 0.15                           # 主箱顶框高
RT = 0.03                           # 主箱屋面板厚
GAP = 0.004                         # 相邻零件错开的距离（防共面闪烁）
WR = 0.10                           # 侧翼屋顶厚
WALL_T = 0.075                      # 75 mm EPS 夹芯板
WALL_TOP = H - WR                   # 墙顶（侧翼屋顶底面）
WIN = (1.13, 1.0)                   # 铝合金推拉窗 1130×1000
SILL = 0.9                          # 窗台高（推定）
DOOR = (1.52, 2.1)                  # 入户推拉门（报价 1520×2200，主箱净高不够，按比例略矮）
SIDE_WIN_X = (-1.45, 1.45)          # 侧墙两扇窗
SIDES = (-1, 1)                     # -1 = 前侧（-Y），+1 = 后侧
ENDS = (-1, 1)                      # -1 = 正门端（-X）

# 折叠收纳的层次（从主箱外沿往里，推定）：屋顶垂下在外，地板竖在内，端墙再往里，侧墙最里面
FLOOR_PIVOT_Z = 0.0
END_PIVOT = (L / 2 + 0.0625, CW / 2 - 0.1375)      # 端墙转轴 (|x|, |y|)，收起后贴在地板内侧
SIDE_WALL_IN = CW / 2 + WW - WALL_T - 0.70         # 侧墙收进箱内的平移量


# ---------------- 材质 ----------------
M = {}
def materials():
    M["panel"] = mat("sandwich_white", (0.86, 0.86, 0.84), 0.1, 0.55)
    M["frame"] = mat("frame_black", (0.05, 0.05, 0.055), 0.4, 0.45)
    M["roof"] = mat("roof_white", (0.80, 0.81, 0.80), 0.3, 0.45)
    M["glass"] = mat("glass", (0.55, 0.65, 0.72), 0.0, 0.05, transmission=1.0)
    M["wood"] = mat("pvc_wood", (0.42, 0.22, 0.11), 0.0, 0.5)
    M["concrete"] = mat("concrete", (0.40, 0.40, 0.39), 0.0, 0.9)
    M["steel"] = mat("steel_galv", (0.55, 0.56, 0.58), 0.8, 0.4)
    M["sealant"] = mat("sealant", (0.95, 0.95, 0.93), 0.0, 0.3)


# ---------------- 工具 ----------------
def holes_split(u0, u1, v0, v1, holes):
    """矩形 [u0,u1]×[v0,v1] 挖掉若干洞口 (uc, w, vb, h)，返回剩下的小矩形 (ua, ub, va, vb)"""
    out, u = [], u0
    for uc, w, vb, h in sorted(holes):
        a, b = uc - w / 2, uc + w / 2
        out.append((u, a, v0, v1))
        if vb > v0:
            out.append((a, b, v0, vb))
        if vb + h < v1:
            out.append((a, b, vb + h, v1))
        u = b
    out.append((u, u1, v0, v1))
    return [r for r in out if r[1] - r[0] > 1e-4 and r[3] - r[2] > 1e-4]

def plane_parts(axis, n, t, rects):
    """axis="X"：墙沿 X 展开、法向 Y，n 为墙中心 y；axis="Y" 反之"""
    parts = []
    for ua, ub, va, vb in rects:
        size_u, uc, vc, size_v = ub - ua, (ua + ub) / 2, (va + vb) / 2, vb - va
        parts.append(((size_u, t, size_v), (uc, n, vc)) if axis == "X" else ((t, size_u, size_v), (n, uc, vc)))
    return parts

def wall(name, axis, n, u0, u1, holes, stage, out, mat_key="panel", t=WALL_T, v0=FLOOR, v1=WALL_TOP):
    return boxes(name, plane_parts(axis, n, t, holes_split(u0, u1, v0, v1, holes)), M[mat_key], stage, 0.002,
                 out=out)

def window(name, axis, n, uc, vb, w, h, stage, out, t=WALL_T):
    """黑色铝框 + 中梃 + 玻璃（推拉窗）"""
    f = 0.05
    rects = [(uc - w / 2, uc - w / 2 + f, vb, vb + h), (uc + w / 2 - f, uc + w / 2, vb, vb + h),
             (uc - w / 2, uc + w / 2, vb, vb + f), (uc - w / 2, uc + w / 2, vb + h - f, vb + h),
             (uc - 0.02, uc + 0.02, vb, vb + h)]
    boxes(name + "_frame", plane_parts(axis, n, t + 0.01, rects), M["frame"], stage, 0.002, out=out)
    boxes(name + "_glass", plane_parts(axis, n, 0.01, [(uc - w / 2 + f, uc + w / 2 - f, vb + f, vb + h - f)]),
          M["glass"], stage, out=out)


# ---------------- 部件 ----------------
def foundation():
    st = "01_foundation"
    for i, x in enumerate((-L / 2 + 0.3, 0, L / 2 - 0.3)):
        for j, y in enumerate((-CW / 2 + 0.3, CW / 2 - 0.3)):
            box(f"pad_{i}{j}", (0.5, 0.5, 0.2), (x, y, -0.1), M["concrete"], st, 0.005)

def core():
    st = "02_core"
    px, py = L / 2 - POST / 2, CW / 2 - POST / 2
    for i, sx in enumerate((-1, 1)):
        for j, sy in enumerate((-1, 1)):
            box(f"core_post_{i}{j}", (POST, POST, H - RT), (sx * px, sy * py, (H - RT) / 2), M["frame"], st, 0.003)
    for sy, tag in ((-1, "front"), (1, "rear")):
        box(f"core_base_{tag}", (L - 2 * POST, POST, FH), (0, sy * py, FH / 2), M["frame"], st, 0.003)
        box(f"core_top_{tag}", (L - 2 * POST, POST, RB - RT), (0, sy * py, H - RT - (RB - RT) / 2), M["frame"], st, 0.003)
    for sx, tag in ((-1, "door"), (1, "back")):
        box(f"core_base_{tag}", (POST, CW - 2 * POST, FH), (sx * px, 0, FH / 2), M["frame"], st, 0.003)
        box(f"core_top_{tag}", (POST, CW - 2 * POST, RB - RT), (sx * px, 0, H - RT - (RB - RT) / 2), M["frame"], st, 0.003)
    box("core_roof", (L, CW, RT), (0, 0, H - RT / 2), M["roof"], st, 0.002)       # 角柱、顶梁收在它下面，侧面不共面
    box("core_floor", (L - 2 * POST, CW - 0.02, 0.02), (0, 0, FLOOR - 0.01), M["wood"], st)
    # 正门端：玻璃推拉门；后端：小窗（卫生间）
    xw = -L / 2 + WALL_T / 2
    wall("core_wall_door", "Y", xw, -CW / 2 + POST, CW / 2 - POST, [(0, DOOR[0], FLOOR, DOOR[1])], st, [-1, 0, 0],
         v1=H - RB)
    f = 0.05
    rects = [(-DOOR[0] / 2, DOOR[0] / 2, FLOOR, FLOOR + f), (-DOOR[0] / 2, DOOR[0] / 2, FLOOR + DOOR[1] - f, FLOOR + DOOR[1]),
             (-DOOR[0] / 2, -DOOR[0] / 2 + f, FLOOR, FLOOR + DOOR[1]), (DOOR[0] / 2 - f, DOOR[0] / 2, FLOOR, FLOOR + DOOR[1]),
             (-0.02, 0.02, FLOOR, FLOOR + DOOR[1])]
    boxes("entry_door_frame", plane_parts("Y", xw, WALL_T + 0.01, rects), M["frame"], st, 0.002)
    boxes("entry_door_glass", plane_parts("Y", xw, 0.01, [(-DOOR[0] / 2 + f, DOOR[0] / 2 - f, FLOOR + f, FLOOR + DOOR[1] - f)]),
          M["glass"], st)
    xb = L / 2 - WALL_T / 2
    wall("core_wall_back", "Y", xb, -CW / 2 + POST, CW / 2 - POST, [(0, 0.6, FLOOR + 1.4, 0.6)], st, [1, 0, 0], v1=H - RB)
    window("core_back_window", "Y", xb, 0, FLOOR + 1.4, 0.6, 0.6, st, [1, 0, 0])

def roof_wings():
    st = "03_roof_wing"
    for s in SIDES:
        tag = "f" if s < 0 else "r"
        yc = s * (CW / 2 + WW / 2)
        box(f"roof_wing_{tag}", (L - 0.06, WW - 0.03, WR - 0.02), (0, s * (CW / 2 + (WW - 0.03) / 2), H - WR / 2 - 0.01),
            M["roof"], st, 0.002)                                     # 两端、外沿缩进包边，不和包边共面
        # 黑色檐口包边：外沿 + 两端
        yo = s * (CW / 2 + WW - 0.015)
        boxes(f"roof_wing_{tag}_fascia", [((L, 0.03, WR + 0.02), (0, yo, H - WR / 2)),
                                          ((0.03, WW, WR + 0.02), (-L / 2 + 0.015, yc, H - WR / 2)),
                                          ((0.03, WW, WR + 0.02), (L / 2 - 0.015, yc, H - WR / 2))],
              M["frame"], st, 0.002)
        # 运输时绕主箱顶边垂下，盖住侧面（推定）
        pose("folded", [f"roof_wing_{tag}", f"roof_wing_{tag}_fascia"],
             rotate=dict(axis="X", pivot=(0, s * CW / 2, H - WR), deg=-90.0 * s))

def floor_wings():
    st = "04_floor_wing"
    for s in SIDES:
        tag = "f" if s < 0 else "r"
        yc = s * (CW / 2 + WW / 2)
        # 可展开地板框：外框 + 50×50 方管格栅（只看得到外框）
        box(f"floor_wing_{tag}", (L - 0.004, WW - GAP, FH - GAP), (0, s * (CW / 2 + GAP + (WW - GAP) / 2), (FH + GAP) / 2),
            M["frame"], st, 0.003)                                    # 底面、内侧边离开 GAP，折起后不和主箱共面
        box(f"floor_wing_{tag}_deck", (L - 0.02, WW - 0.01, 0.02), (0, yc, FLOOR - 0.01), M["wood"], st)
        # 运输时绕主箱底边竖起，收在箱内侧（推定）
        pose("folded", [f"floor_wing_{tag}", f"floor_wing_{tag}_deck"],
             rotate=dict(axis="X", pivot=(0, s * CW / 2, FLOOR_PIVOT_Z), deg=90.0 * s))

def supports():
    st = "05_supports"
    for s in SIDES:
        tag = "f" if s < 0 else "r"
        for k, x in enumerate((-L / 2 + 0.3, 0, L / 2 - 0.3)):
            boxes(f"support_{tag}_{k}", [((0.30, 0.30, 0.01), (x, s * (CW / 2 + WW - 0.25), -0.195)),
                                         ((0.08, 0.08, 0.19), (x, s * (CW / 2 + WW - 0.25), -0.095))],
                  M["steel"], st, 0.002)

def end_walls():
    st = "06_end_walls"
    for s in SIDES:
        tag = "f" if s < 0 else "r"
        yc = s * (CW / 2 + WW / 2)
        for e in ENDS:
            et = "door" if e < 0 else "back"
            x = e * (L / 2 - WALL_T / 2)
            out = [e, 0, 0]
            u0, u1 = sorted((s * CW / 2, s * (CW / 2 + WW)))
            wall(f"end_wall_{tag}_{et}", "Y", x, u0, u1, [(yc, WIN[0], FLOOR + SILL, WIN[1])], st, out)
            window(f"end_window_{tag}_{et}", "Y", x, yc, FLOOR + SILL, WIN[0], WIN[1], st, out)
            # 运输时绕主箱角部转进箱内，贴在地板内侧（推定）
            pose("folded", [f"end_wall_{tag}_{et}", f"end_window_{tag}_{et}_*"],
                 rotate=dict(axis="Z", pivot=(e * END_PIVOT[0], s * END_PIVOT[1], 0), deg=90.0 * s * e))

def side_walls():
    st = "07_side_walls"
    for s in SIDES:
        tag = "f" if s < 0 else "r"
        y = s * (CW / 2 + WW - WALL_T / 2)
        out = [0, s, 0]
        u0, u1 = -L / 2 + WALL_T, L / 2 - WALL_T
        wall(f"side_wall_{tag}", "X", y, u0, u1, [(x, WIN[0], FLOOR + SILL, WIN[1]) for x in SIDE_WIN_X], st, out,
             v0=FLOOR + 0.003, v1=WALL_TOP - 0.003)                    # 上下各让 3 mm，滑过端墙时不共面
        for k, x in enumerate(SIDE_WIN_X):
            window(f"side_window_{tag}_{k}", "X", y, x, FLOOR + SILL, WIN[0], WIN[1], st, out)
        # 侧翼外角黑色竖框
        tw, th = 0.093, WALL_TOP - FLOOR - 0.012                       # 比墙板、窗框外凸 8 mm，上下缩 6 mm，不共面
        boxes(f"side_wall_{tag}_trim", [((tw, tw, th), (sx * (L / 2 + 0.008 - tw / 2), s * (CW / 2 + WW + 0.008 - tw / 2),
                                         (FLOOR + WALL_TOP) / 2)) for sx in (-1, 1)], M["frame"], st, 0.002)
        # 运输时整面收进箱内最里层（推定）
        pose("folded", [f"side_wall_{tag}", f"side_wall_{tag}_trim", f"side_window_{tag}_*"], move=(0, -s * SIDE_WALL_IN, 0))

def sealant():
    """侧翼屋顶和主箱顶的接缝打胶（推定）。原点在起点，沿 X 伸展，做"挤胶"动画"""
    st = "08_seal"
    r = 0.03
    for s in SIDES:
        tag = "f" if s < 0 else "r"
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r, radius2=r, depth=L - 0.06)
        for v in bm.verts:
            z = v.co.z + (L - 0.06) / 2
            v.co = Vector((z, v.co.x, v.co.y))
        ob = obj(f"seal_{tag}", bm, M["sealant"], st, grow_axis="X")
        ob.location = (-L / 2 + 0.03, s * CW / 2, H + r * 0.3)

def container_40hq():
    """运输说明：40HQ 外轮廓（行业标准外尺寸 12.192 × 2.438 × 2.896），两台折叠箱首尾相接放在里面"""
    gap = 0.15
    wire_box("hq40", (12.192, 2.438, 2.896), ((L + gap) / 2, 0, 2.896 / 2 - 0.02), "90_container", t=0.035,
             fill=ghost("hq40_ghost", alpha=0.10))


def build():
    materials()
    foundation(); core(); roof_wings(); floor_wings(); supports(); end_walls(); side_walls(); sealant(); container_40hq()
