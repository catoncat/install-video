"""20FT 可扩展集装箱房 · 国际站营销片。对应 storyboard.md。

按用途出三条片子（VERSIONS）：main 16:9 主图视频、detail 1:1 详情页、ad 9:16 广告（钩子在前）。
字幕只写报价单里的数据或行业通用说法；展开机构是推定的，字幕里不写具体操作细节。
模型按展开状态建，运输状态在 model.py 里登记为 pose("folded")。
注意：geo.variant 建的材质副本名叫 "<原名>@<tag>"，通配符会匹配到它们，所以动画里的选择器都写全名。
"""
from engine.anim import *
from engine import geo, library
from . import model as m

LANG = "en"
MAX_WORDS = 8
STYLE = dict(hl=(0.10, 0.65, 1.0))          # 产品有木色地板，高亮改用青色，和"本来就是木色"分开

VERSIONS = {
    "main":   dict(format="16:9", shots=None, target=(45, 60)),
    "detail": dict(format="1:1", shots=["00a", "s1", "s2", "s3", "s4", "s5", "s6", "09a", "cta_oem", "cta_contact"],
                   target=(25, 35)),
    "ad":     dict(format="9:16", shots=["ad_hook", "ad_walls", "ad_ready", "ad_options", "cta_oem", "cta_contact"],
                   target=(12, 16)),
}

# ---------------- 选择器 ----------------
UNIT = ["@02_core", "@03_roof_wing", "@04_floor_wing", "@06_end_walls", "@07_side_walls"]
SITE = ["@01_foundation", "@05_supports"] + UNIT
FINAL = SITE + ["@08_seal"]
ROOF = ["core_roof", "roof_wing_f", "roof_wing_r", "roof_wing_f_fascia", "roof_wing_r_fascia", "seal_f", "seal_r",
        "core_top_front", "core_top_rear", "core_top_door", "core_top_back"]
EXT_WALLS = ["side_wall_f", "side_wall_r", "end_wall_f_door", "end_wall_r_door", "end_wall_f_back", "end_wall_r_back",
             "core_wall_door", "core_wall_back"]
FLOORS = ["core_floor", "floor_wing_f_deck", "floor_wing_r_deck"]
C = (0, 0, 1.2)
CAMP_C = (7.5, 4.0, 0.5)
CAMP = [(dx, dy, 0) for dy in (0, 8.0) for dx in (0, 7.5, 15.0)][1:]     # 2 排 × 3 台，原箱在 (0,0)
TAG = {-1: "f", 1: "r"}
ET = {-1: "door", 1: "back"}
END_ORDER = ((-1, -1), (1, -1), (-1, 1), (1, 1))

def roof_sel(s):
    return [f"roof_wing_{TAG[s]}", f"roof_wing_{TAG[s]}_fascia"]

def floor_sel(s):
    return [f"floor_wing_{TAG[s]}", f"floor_wing_{TAG[s]}_deck"]

def end_sel(s, e):
    return [f"end_wall_{TAG[s]}_{ET[e]}", f"end_window_{TAG[s]}_{ET[e]}_frame", f"end_window_{TAG[s]}_{ET[e]}_glass"]

def side_sel(s):
    t = TAG[s]
    return [f"side_wall_{t}", f"side_wall_{t}_trim"] + [f"side_window_{t}_{k}_{p}" for k in (0, 1) for p in ("frame", "glass")]

ROOF_WINGS = roof_sel(-1) + roof_sel(1)
FLOOR_WINGS = floor_sel(-1) + floor_sel(1)
END_WALLS = [o for s, e in END_ORDER for o in end_sel(s, e)]
SIDE_WALLS = side_sel(-1) + side_sel(1)


# ---------------- 材质变体（材料库） ----------------
def prepare():
    """定制选项：同一箱体换外墙、地板。只做展示，不代表全部常备"""
    geo.variant(EXT_WALLS, "stone", library.material("flexible_stone"))
    geo.variant(EXT_WALLS, "metal", library.material("metal_dark"))
    geo.variant(FLOORS, "oak", library.material("spc_oak"))
    geo.variant(FLOORS, "tile", library.material("tile"))
    geo.variant(FLOORS, "wpc", library.material("wpc_floor"))


SHOTS = [
    # ---------- 片头 ----------
    shot("00a_intro", 2.5, title=("可扩展集装箱房", "Expandable Container House"), card=True, module="intro",
         subtitle=("快速安装 · 预制 · 模块化", "Fast Installation · Prefab · Modular"),
         show=SITE, cam=cam((0, 0, -0.9), az=(-62, -48), el=(21, 18), dist=(17, 16))),

    shot("00b_uses", 2, module="intro", cam=cam(C, az=(-48, -38), el=(13, 11), dist=(15.5, 15)),
         notes=[note(0.1, 1.9, "适用于营地、办公、宿舍和仓库", "For Camps, Offices, Dormitories & Warehouses")]),

    shot("01_ship", 3, module="intro", show=UNIT + ["@90_container"],
         cam=cam((m.L / 2, 0, 1.2), az=(-32, -26), el=16, dist=(19, 17.5)),
         do=[set_pose("folded"), copies(UNIT, [(m.L + 0.15, 0, 0)], at=0, until=3)],
         notes=[note(0.2, 2.7, "折叠运输 · 一个 40HQ 装 2 台", "Ships Folded · 2 Units per 40HQ")]),

    # ---------- 安装 8 步 ----------
    shot("s1_foundation", 3.5, title=("基础找平", "Prepare Foundation"), step=1, module="install",
         show=["@01_foundation"], cam=cam((0, 0, 0), az=(-38, -32), el=32, dist=12),
         do=[move("@01_foundation", 0.2, 0.7, frm=(0, 0, 0.5), stagger=0.12)],
         notes=[note(1.0, 2.5, "混凝土墩或基础找平", "Level concrete pads or footings")]),

    shot("s2_position", 4, title=("吊装就位", "Lift & Position"), step=2, module="install",
         show=["@01_foundation"] + UNIT, cam=cam(C, az=(-36, -30), el=22, dist=14.5),
         do=[set_pose("folded"), drop(UNIT, 0.3, 2.4, h=3.5, relative="current", hl=False)],
         notes=[note(1.0, 3.0, "吊装到基础上并调平", "Crane onto pads, then level")]),

    shot("s3_roof", 4, title=("屋顶展开", "Raise Roof Wings"), step=3, module="install",
         cam=cam(C, az=(-62, -56), el=26, dist=15),
         do=[to_pose("rest", 0.3, 2.4, sel=roof_sel(1)), to_pose("rest", 0.6, 2.4, sel=roof_sel(-1))]),

    shot("s4_floor", 4, title=("地板展开", "Lower Expansion Floors"), step=4, module="install",
         cam=cam(C, az=(-58, -52), el=20, dist=15),
         do=[drop("@05_supports", 0.2, 0.7, h=0.6, stagger=0.05),
             to_pose("rest", 1.0, 2.2, sel=floor_sel(1)), to_pose("rest", 1.2, 2.2, sel=floor_sel(-1))]),

    shot("s5_end_walls", 4, title=("端墙展开", "Unfold End Walls"), step=5, module="install",
         cam=cam(C, az=(-52, -46), el=22, dist=14.5),
         do=[to_pose("rest", 0.3 + k * 0.35, 2.0, sel=end_sel(s, e)) for k, (s, e) in enumerate(END_ORDER)]),

    shot("s6_side_walls", 4, title=("侧墙就位", "Extend Side Walls"), step=6, module="install",
         cam=cam(C, az=(-40, -34), el=22, dist=15),
         do=[to_pose("rest", 0.3, 2.2, sel=side_sel(-1)), to_pose("rest", 0.5, 2.2, sel=side_sel(1))],
         notes=[note(2.0, 1.9, "门窗出厂预装", "Windows come pre-installed")]),

    shot("s7_seal", 4.5, title=("锁紧密封", "Lock, Bolt & Seal"), step=7, module="install",
         cam=cam((-m.L / 2 + 1.0, -m.CW / 2, m.H), az=(-62, -52), el=(30, 26), dist=(3.6, 3.2), lens=35),
         do=[grow("seal_f", 0.4, 3.0), grow("seal_r", 0.4, 3.0, hl=False)],
         notes=[note(0.6, 3.7, "所有接缝锁紧并密封", "All joints bolted and sealed")]),

    shot("s8_ready", 4.5, title=("完成", "Ready for Use"), step=8, module="install",
         cam=cam((0, 0, 0.6), az=(-70, -40), el=(21, 18), dist=(16, 15)),
         notes=[note(0.2, 2.0, "水电出厂预装", "Plumbing and wiring factory-fitted"),
                note(2.3, 2.1, "20FT · 5.85 × 6.3 × 2.5 m", "20FT · 5.85 × 6.3 × 2.5 m")]),

    # ---------- 定制（材料库：外墙 夹芯板 → 柔性石材 → 金属板；地板 PVC → SPC 橡木 → 瓷砖 → WPC） ----------
    shot("09a_exterior", 3, title=("可定制选项", "Customizable Options"), module="options",
         cam=cam(C, az=(-50, -44), el=14, dist=14.5),
         do=[swap(EXT_WALLS, "stone", 0.9), swap(EXT_WALLS, "metal", 1.9)],
         notes=[note(0.2, 2.7, "外墙饰面", "Exterior wall finishes")]),

    shot("09b_floor", 3, title=("可定制选项", "Customizable Options"), module="options",
         show=FINAL, hide=ROOF, cam=cam((0, 0, 0.2), az=(-30, -26), el=58, dist=14),
         do=[swap(FLOORS, "oak", 0.5), swap(FLOORS, "tile", 1.3), swap(FLOORS, "wpc", 2.1)],
         notes=[note(0.2, 2.7, "地板饰面", "Flooring finishes")]),

    # ---------- 场景 + 交付 + 询盘 ----------
    shot("10_projects", 4, title=("项目应用", "Project Applications"), module="scenes", show=FINAL,
         cam=cam(CAMP_C, az=(-34, -28), el=(26, 30), dist=(30, 33)),
         do=[copies(FINAL, CAMP, at=0.2, until=11.5, drop=2.0, dur=0.9, stagger=0.18)],     # 留到询盘结尾
         notes=[note(0.3, 1.7, "劳务营地 · 现场办公 · 工人宿舍", "Labor Camp · Site Office · Worker Dormitory"),
                note(2.2, 1.7, "临时仓库 · 商业售货亭 · 度假屋", "Warehouse · Commercial Kiosk · Resort Unit")]),

    shot("11_delivery", 2.5, title=("定金后 30 个工作日交货", "Delivery: 30 Business Days After Deposit"), card=True,
         module="cta", subtitle=("结构质保 5 年", "5-Year Structural Warranty"),
         cam=cam(CAMP_C, az=(-28, -26), el=30, dist=(33, 31))),

    shot("12a_oem", 2.5, title=("支持 OEM / ODM", "OEM / ODM Available"), card=True, module="cta",
         subtitle=("批发与项目供货", "Wholesale & Project Supply"),
         cam=cam(CAMP_C, az=(-26, -24), el=30, dist=(31, 29))),

    shot("12b_contact", 2.5, title=("联系我们", "Contact Us"), subtitle=("获取目录和报价", "for Catalog & Price"),
         card=True, module="cta", cam=cam(CAMP_C, az=(-24, -22), el=30, dist=(29, 27.5))),

    # ---------- 9:16 广告专用：钩子在前，近景快切 ----------
    shot("ad_hook", 2.5, module="install", only=["ad"], show=SITE,
         cam=cam(C, az=(-52, -40), el=(14, 18), dist=(9.5, 10.5)),
         do=[set_pose("folded"), to_pose("rest", 0.15, 0.9, sel=ROOF_WINGS),
             to_pose("rest", 0.95, 0.9, sel=FLOOR_WINGS)]),

    shot("ad_walls", 2.5, module="install", only=["ad"],
         cam=cam(C, az=(-22, -30), el=12, dist=(10, 10.8)),
         do=[to_pose("rest", 0.1, 0.9, sel=END_WALLS, stagger=0.08), to_pose("rest", 1.1, 0.9, sel=SIDE_WALLS)],
         notes=[note(0.3, 2.1, "现场展开 · 门窗出厂预装", "Unfolds On Site · Windows Pre-installed")]),

    shot("ad_ready", 2.5, title=("可扩展集装箱房", "Expandable Container House"), card=True, module="intro", only=["ad"],
         subtitle=("折叠运输 · 一个 40HQ 装 2 台", "Ships Folded · 2 Units per 40HQ"),
         cam=cam(C, az=(-72, -52), el=(18, 22), dist=(14, 15))),

    shot("ad_options", 2.4, title=("可定制选项", "Customizable Options"), module="options", only=["ad"], show=FINAL,
         cam=cam(C, az=(-46, -40), el=14, dist=13),
         do=[swap(EXT_WALLS, "stone", 0.7), swap(EXT_WALLS, "metal", 1.5)]),

    # ---------- detail / ad 共用的短询盘结尾（自带营地，不依赖 10_projects 的复制品） ----------
    shot("cta_oem", 2.5, title=("支持 OEM / ODM", "OEM / ODM Available"), card=True, module="cta",
         only=["detail", "ad"], subtitle=("批发与项目供货", "Wholesale & Project Supply"), show=FINAL,
         cam=cam(CAMP_C, az=(-30, -26), el=30, dist=(32, 30)),
         do=[copies(FINAL, CAMP, at=0, until=5.0)]),

    shot("cta_contact", 2.5, title=("联系我们", "Contact Us"), subtitle=("获取目录和报价", "for Catalog & Price"),
         card=True, module="cta", only=["detail", "ad"]),          # 沿用 cta_oem 结尾的机位，切过来不跳
]
