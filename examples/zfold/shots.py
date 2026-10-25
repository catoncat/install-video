"""Z 型折叠集装箱 · 国际站主版本分镜。对应 分镜_zfold.md（v2：跳过定制材料段）。

字幕只用英文（LANG="en"），每屏标题 + 字幕合计不超过 8 个英文单词，数字只用报价单上的。
中文一栏用于和用户核对。
折叠 / 展开不是平移，引擎的 move 做不了，用 pose() 直接给各组对象打关键帧：
  θ：端墙与水平面夹角（FOLD_DEG 折叠 → 90 立直）；φ：长墙倒下角（90 平躺 → 0 立直）；g：整体 Z 偏移；rig：吊具额外 Z。
"""
import math
from mathutils import Matrix, Vector
from engine.anim import *
from engine import geo, library
from . import model as m

LANG = "en"
MAX_WORDS = 8
TEXT = dict(card=1.5, note=1.5)   # 手机观看：卡片大字、底部字幕放大

# 按用途出三条片子：main 16:9 主图视频、detail 1:1 详情页、ad 9:16 广告（展开动作当钩子放最前）
VERSIONS = {
    "main":   dict(format="16:9", shots=None, target=(45, 60)),
    "detail": dict(format="1:1", shots=["00a", "02b", "03b", "04", "05", "07", "08b", "09", "cta_oem", "cta_contact"],
                   target=(25, 35)),
    "ad":     dict(format="9:16", shots=["ad_hook", "ad_walls", "ad_title", "ad_options", "cta_oem", "cta_contact"],
                   target=(12, 16)),
}

UNIT = ["@02_base", "@03_roof", "@04_end_L", "@04_end_R", "@05_wall_F", "@05_wall_R"]
FULL = ["@01_foundation"] + UNIT + ["@06_bolts", "@07_trim", "@08_seal"]
RIG = ["@20_rig", "@21_rig_top", "@22_rig_bot"]
CENTER = (0, 0, 1.2)
LOW = (0, 0, -0.9)             # 卡片镜头：注视点放低，主体在画面上半部，给居中的大字让位
FOLDED = m.FOLD_DEG
PANELS = ["endL_panel", "endR_panel", "wallF_panel", "wallR_panel"]     # 外墙板（门窗是单独的对象，不跟着换）


def prepare():
    """定制选项：同一箱体换外墙饰面。只做展示，不代表全部常备"""
    geo.variant(PANELS, "stone", library.material("flexible_stone"))
    geo.variant(PANELS, "metal", library.material("metal_dark"))
    geo.variant(PANELS, "wood", library.material("wpc_wall"))


# ---------------- 折叠姿态 ----------------
def _groups(ctx):
    return dict(base=resolve("@02_base"), roof=resolve("@03_roof"), rig=resolve(RIG),
                endL=resolve("@04_end_L"), endR=resolve("@04_end_R"),
                wallF=resolve("@05_wall_F"), wallR=resolve("@05_wall_R"))

def _key(ob, frame, loc, rot):
    ob.location = loc
    ob.rotation_euler = rot
    ob.keyframe_insert("location", frame=frame)
    ob.keyframe_insert("rotation_euler", frame=frame)

def _hinged(ob, frame, pivot, axis, ang, shift):
    """绕 pivot 沿 axis 转 ang（弧度）：对象原点在世界原点，所以 loc = pivot - R·pivot + shift"""
    R = Matrix.Rotation(ang, 3, axis)
    P = Vector(pivot)
    rot = [0.0, 0.0, 0.0]
    rot["XYZ".index(axis)] = ang
    _key(ob, frame, P - R @ P + Vector(shift), rot)

def pose(ctx, sec, theta, phi, g=0.0, rig=0.0, G=None):
    G = G or _groups(ctx)
    fr = ctx.f(sec)
    rd = m.roof_dz(theta)
    for ob in G["base"]:
        _key(ob, fr, (0, 0, g), (0, 0, 0))
    for ob in G["roof"]:
        _key(ob, fr, (0, 0, g + rd), (0, 0, 0))
    for ob in G["rig"]:
        _key(ob, fr, (0, 0, g + rd + rig), (0, 0, 0))
    tilt = math.radians(90 - theta)
    for ob in G["endL"]:
        _hinged(ob, fr, (-m.XE, 0, m.HINGE_Z), "Y", tilt, (0, 0, g))
    for ob in G["endR"]:
        _hinged(ob, fr, (m.XE, 0, m.HINGE_Z), "Y", -tilt, (0, 0, g))
    p = math.radians(phi)
    for ob in G["wallF"]:
        _hinged(ob, fr, (0, -m.YL, m.LONG_PIVOT_Z), "X", -p, (0, 0, g))
    for ob in G["wallR"]:
        _hinged(ob, fr, (0, m.YL, m.LONG_PIVOT_Z), "X", p, (0, 0, g + m.REAR_LIFT * phi / 90))

def linear(G, f0, f1):
    """[f0, f1] 内的姿态关键帧改成线性插值（逐帧都打了 key，避免贝塞尔过冲）"""
    for ob in [o for v in G.values() for o in v]:
        for fc in fcurves(ob):
            if fc.data_path in ("location", "rotation_euler"):
                for k in fc.keyframe_points:
                    if f0 - 0.5 <= k.co.x <= f1 + 0.5:
                        k.interpolation = "LINEAR"

def hold(theta, phi, g=0.0, rig=0.0):
    """shot 开头直接摆到某个姿态（和上一个 shot 之间是硬切）"""
    def fn(ctx):
        G = _groups(ctx)
        pose(ctx, 0, theta, phi, g, rig, G)
        _cut(ctx, G)
    return fn

def _cut(ctx, G):
    """上一帧的 key 设为 constant，让姿态在本 shot 第一帧瞬间切换"""
    fr = ctx.f(0)
    for ob in [o for v in G.values() for o in v]:
        for fc in fcurves(ob):
            if fc.data_path in ("location", "rotation_euler"):
                prev = [k for k in fc.keyframe_points if k.co.x < fr - 0.5]
                if prev:
                    max(prev, key=lambda k: k.co.x).interpolation = "CONSTANT"

def animate(at, dur, a, b, ease=True):
    """在 [at, at+dur] 内从姿态 a 过渡到 b，逐帧打 key。a / b = (theta, phi, g, rig)"""
    def fn(ctx):
        G = _groups(ctx)
        n = max(1, round(dur * 30))
        for k in range(n + 1):
            u = k / n
            e = u * u * (3 - 2 * u) if ease else u
            st = [x0 + (x1 - x0) * e for x0, x1 in zip(a, b)]
            pose(ctx, at + dur * u, *st, G=G)
        linear(G, ctx.f(at), ctx.f(at + dur))
    return fn

def unfold(at, dur):
    """吊起屋顶：屋顶高度匀顺上升，端墙角度由高度反算，墙顶始终顶在滑槽下"""
    def fn(ctx):
        G = _groups(ctx)
        z0, z1 = m.roof_dz(FOLDED), 0.0
        n = round(dur * 30)
        th = FOLDED
        for k in range(n + 1):
            u = k / n
            e = u * u * (3 - 2 * u)
            target = z0 + (z1 - z0) * e
            lo, hi = FOLDED, 90.0            # 二分求 θ：roof_dz 在 [FOLDED, 90] 上单调
            for _ in range(40):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if m.roof_dz(mid) < target else (lo, mid)
            th = (lo + hi) / 2
            pose(ctx, at + dur * u, th, 90, 0, 0, G)
        linear(G, ctx.f(at), ctx.f(at + dur))
    return fn

S_FOLDED = (FOLDED, 90, 0.0, 0.0)
S_OPEN_FLAT = (90, 90, 0.0, 0.0)          # 端墙立直，长墙还平躺
S_DONE = (90, 0, 0.0, 6.0)                # 全部展开，吊具移走


def copies(name, spots, sel, t_in, t_out, coll_name):
    """用集合实例复制整箱：spots=[(x,y,z)]，在 t_in 出现、t_out 消失"""
    def fn(ctx):
        import bpy
        unit = bpy.data.collections.get(coll_name) or bpy.data.collections.new(coll_name)
        for o in list(unit.objects):
            unit.objects.unlink(o)
        for o in ctx.resolve(sel):
            unit.objects.link(o)
        for k, loc in enumerate(spots):
            e = bpy.data.objects.get(f"{name}_{k}") or bpy.data.objects.new(f"{name}_{k}", None)
            if e.name not in bpy.context.scene.collection.objects:
                bpy.context.scene.collection.objects.link(e)
            e.instance_type = "COLLECTION"
            e.instance_collection = unit
            e.animation_data_clear()
            e.location = loc
            for fr, hide in ((1, True), (ctx.f(t_in), False), (ctx.f(t_out), True)):   # 只在本段出现
                e.hide_render = e.hide_viewport = hide
                e.keyframe_insert("hide_render", frame=fr)
                e.keyframe_insert("hide_viewport", frame=fr)
            for fc in fcurves(e):
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"
    return fn


# 运输：两列各 5 台（报价单：10 台 / 40HQ）。主箱在左列最下面
STACK = [(0, 0, k * m.FOLDED_H) for k in range(1, 5)] + [(m.L + 0.3, 0, k * m.FOLDED_H) for k in range(5)]
# 营地：沿 Y 排 4 台，叠 2 层（报价单：≤2 层）
CAMP = [(0, k * (m.W + 0.05), 0) for k in range(1, 4)] + [(0, k * (m.W + 0.05), m.H + 0.01) for k in range(4)]
CAMP_C = (0, 1.5 * (m.W + 0.05), -0.4)   # 同样放低，大字在下


SHOTS = [
    shot("00a_intro", 2, title=("Z 型折叠集装箱房", "Z-Type Foldable Container House"), card=True, show=FULL,
         cam=cam(LOW, (-40, -32), (16, 14), (13.5, 13)),
         do=[hold(90, 0, 0, 6)],
         notes=[note(0.3, 1.7, "扁平包装 · 快速安装", "Flat Pack · Fast Installation")]),
    shot("00b_intro", 2, title=("营地 · 办公 · 宿舍", "Camps · Offices · Dormitories"), card=True,
         cam=cam(LOW, (-32, -24), (14, 12), (13, 12.5))),

    shot("01_foundation", 3.5, title=("准备基础", "Prepare Foundation"), step=1, show=[],
         cam=cam((0, 0, 0), (-30, -22), 30, (10.5, 9.5)),
         do=[hold(*S_FOLDED[:2], 6.0, 0), move("@01_foundation", 0.3, 0.9, frm=(0, 0, -0.35), stagger=0.2)],
         notes=[note(0.8, 2.6, "场地找平，四角各设一个墩", "Level ground, pier at each corner")]),

    shot("02a_stack", 2.5, title=("吊装就位", "Place Folded Unit"), step=2, show=UNIT,
         cam=cam((m.L / 2 + 0.15, 0, 1.6), (-28, -24), 10, (15.5, 14.5)),
         do=[hold(*S_FOLDED[:2], -0.2, 0), copies("stack", STACK, UNIT, 0, 2.5, "UNIT_STACK")],
         notes=[note(0.3, 2.1, "扁平包装：每个 40HQ 装 10 台", "Flat pack: 10 units per 40HQ")]),
    shot("02b_place", 2, title=("吊装就位", "Place Folded Unit"), step=2,
         show=["@01_foundation"] + UNIT + ["@20_rig", "@22_rig_bot"],
         cam=cam((0, 0, 0.8), (-34, -30), 14, (11.5, 11)),
         do=[hold(FOLDED, 90, 2.2, 0), animate(0.1, 1.6, (FOLDED, 90, 2.2, 0), S_FOLDED)],
         notes=[note(0.2, 1.8, "吊车把箱体放到墩上", "Crane sets it on piers")]),

    shot("03a_hook", 2.5, title=("吊起展开", "Lift Roof to Unfold"), step=3,
         cam=cam((m.L / 2 - 0.3, -m.W / 2 + 0.2, m.FOLDED_H + 0.4), (25, 35), 22, (4.2, 3.8)),
         do=[vanish("@22_rig_bot", 0.3), appear("@21_rig_top", 0.4, hl=1.8)],
         notes=[note(0.4, 2.0, "挂住四个顶角件", "Hook the top corners")]),
    shot("03b_unfold", 5, title=("吊起展开", "Lift Roof to Unfold"), step=3,
         cam=cam((0, 0, 1.0), (-38, -20), (12, 18), (12.5, 12)),
         do=[unfold(0.3, 4.2), highlight(["@04_end_L", "@04_end_R"], 0.6, 3.6)],
         notes=[note(0.6, 4.2, "端墙随之立起到位", "End walls swing up")]),

    shot("04_bolts", 4, title=("固定立柱", "Fix Corner Posts"), step=4,
         cam=cam((-m.XE - 0.1, -m.YC, m.HINGE_Z), (-55, -60), 14, (1.7, 1.5), lens=40),
         do=[animate(0.0, 1.2, (90, 90, 0, 0), (90, 90, 0, 6)), vanish(RIG, 1.3),
             screw(["bolt_00_*", "bolt_01_*", "bolt_10_*", "bolt_11_*"], 0.6, stagger=0.02)],
         notes=[note(0.4, 3.4, "立柱上下两端用螺栓固定", "Bolt posts at both ends")]),

    shot("05_walls", 4, title=("立起长墙", "Raise Side Walls"), step=5,
         cam=cam(CENTER, (-25, -15), (40, 30), 12.5),
         do=[animate(0.3, 2.0, (90, 90, 0, 6), (90, 0, 0, 6)), highlight(["@05_wall_F", "@05_wall_R"], 0.3, 2.6)],
         notes=[note(0.4, 3.4, "从室内推起长墙并固定", "Push walls up, then secure")]),

    shot("06_openings", 3, title=("门窗", "Doors & Windows"), step=6,
         cam=cam((-0.2, -m.W / 2, 1.3), (-35, -20), 8, (8.5, 8)),
         do=[highlight(["wallF_door_*", "wallF_window_*", "endL_window_*"], 0.3, 2.2)],
         notes=[note(0.3, 2.6, "钢门、PVC 推拉窗", "Steel door, PVC sliding windows")]),

    shot("07_seal", 3.5, title=("检查结构与密封", "Check Structure & Sealing"), step=7,
         cam=cam((1.2, -m.W / 2, 1.7), (30, 38), 18, (7.5, 7)),
         do=[move("trim_*", 0.2, 0.9, out=0.4, stagger=0.15), grow(["seal_front", "seal_rear"], 1.0, 1.4),
             highlight("@02_base", 2.4, 0.5)],
         notes=[note(0.3, 3.1, "收边、打胶、检查水平", "Trims, sealant, level check")]),

    shot("08a_inside", 1.5, title=("交付使用", "Ready for Use"), step=8,
         hide=["@05_wall_F", "trim_00", "trim_10", "seal_front"],
         cam=cam((0, 0.3, 1.3), (-8, 8), 6, (6.8, 6.2), lens=26),
         notes=[note(0.1, 1.4, "含灯、开关、插座", "Lights, switches, sockets included")]),
    shot("08b_done", 2.5, title=("交付使用", "Ready for Use"), step=8,
         cam=cam(CENTER, (30, 50), (14, 12), 12),
         notes=[note(0.2, 2.2, "5900 × 2500 × 2470 mm", "5900 × 2500 × 2470 mm")]),

    shot("09_options", 3, title=("可定制外墙", "Customizable Options"), module="options", show=FULL,
         cam=cam(CENTER, az=(-38, -30), el=14, dist=12),
         do=[hold(90, 0, 0, 6), swap(PANELS, "stone", 0.6), swap(PANELS, "metal", 1.4), swap(PANELS, "wood", 2.2),
             swap(PANELS, None, 2.95)],
         notes=[note(0.3, 2.5, "多种外墙饰面可选", "Exterior wall finishes")]),

    # 卡片放大 1.5 倍后一行放不下 3 个场景（引擎不换行），拆成 3 张，每张 2 个
    shot("10a_scenes", 2, title=("工人营地 · 现场办公", "Labor Camp · Site Office"),
         card=True, cam=cam(CAMP_C, (-40, -34), 16, (27, 26)),
         do=[copies("camp", CAMP, UNIT + ["@06_bolts", "@07_trim", "@08_seal"], 0, 13, "UNIT_CAMP")]),
    shot("10b_scenes", 2, title=("员工宿舍 · 临时仓库", "Worker Dormitory · Warehouse"),
         card=True, cam=cam(CAMP_C, (-34, -27), 15, (26, 25))),
    shot("10c_scenes", 2, title=("商业亭 · 度假屋", "Commercial Kiosk · Resort Unit"),
         card=True, cam=cam(CAMP_C, (-27, -20), 14, (25, 24))),
    shot("11a_cta", 2.5, title=("支持 OEM/ODM", "OEM/ODM Available"), card=True,
         cam=cam(CAMP_C, (-20, -12), 14, (24, 26)),
         notes=[note(0.3, 2.1, "批发与项目供货", "Wholesale & Project Supply")]),
    shot("11b_cta", 2.5, title=("联系我们获取目录和报价", "Contact Us for Catalog & Price"), card=True,
         cam=cam(CAMP_C, (-12, -8), 14, (26, 28))),

    # ---------- 详情页 / 广告的询盘结尾：自带营地，不依赖 10a 的复制品 ----------
    shot("cta_oem", 2.5, title=("支持 OEM/ODM", "OEM/ODM Available"), card=True, module="cta",
         subtitle=("批发与项目供货", "Wholesale & Project Supply"), only=["detail", "ad"], show=FULL,
         cam=cam(CAMP_C, az=(-30, -24), el=15, dist=(26, 25)),
         do=[hold(90, 0, 0, 6), copies("camp2", CAMP, UNIT + ["@06_bolts", "@07_trim", "@08_seal"], 0, 5, "UNIT_CAMP2")]),
    shot("cta_contact", 2.5, title=("联系我们", "Contact Us"), subtitle=("获取目录和报价", "for Catalog & Price"),
         card=True, module="cta", only=["detail", "ad"], cam=cam(CAMP_C, az=(-24, -18), el=15, dist=(25, 24))),

    # ---------- 广告专属：钩子在前（吊起屋顶、端墙立起），近景快切 ----------
    shot("ad_hook", 4, module="install", only=["ad"], show=["@01_foundation"] + UNIT + ["@20_rig", "@21_rig_top"],
         cam=cam((0, 0, 1.0), az=(-36, -24), el=(14, 18), dist=(10.5, 9.5)),
         do=[hold(*S_FOLDED), unfold(0.2, 3.4), highlight(["@04_end_L", "@04_end_R"], 0.4, 3.0)],
         notes=[note(0.5, 3.3, "吊起屋顶，整箱展开", "Lift the roof, it unfolds")]),
    shot("ad_walls", 2.2, module="install", only=["ad"], show=FULL,
         cam=cam(CENTER, az=(-25, -18), el=(34, 28), dist=11),
         do=[hold(90, 90, 0, 6), animate(0.1, 1.6, (90, 90, 0, 6), (90, 0, 0, 6)),
             highlight(["@05_wall_F", "@05_wall_R"], 0.1, 1.8)],
         notes=[note(0.2, 1.9, "立起长墙，固定即可", "Raise walls, bolt in place")]),
    shot("ad_title", 2.2, title=("Z 型折叠集装箱房", "Z-Type Foldable Container House"), card=True, module="intro",
         subtitle=("每个 40HQ 装 10 台", "10 Units per 40HQ"), only=["ad"], show=FULL,
         cam=cam(LOW, az=(-34, -28), el=14, dist=(13, 12.5)), do=[hold(90, 0, 0, 6)]),
    shot("ad_options", 2.2, title=("可定制外墙", "Customizable Options"), module="options", only=["ad"], show=FULL,
         cam=cam(CENTER, az=(-30, -24), el=14, dist=11.5),
         do=[hold(90, 0, 0, 6), swap(PANELS, "stone", 0.4), swap(PANELS, "metal", 1.2), swap(PANELS, None, 2.15)]),
]
