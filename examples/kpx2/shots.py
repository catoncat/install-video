"""快拼箱 2.0 分镜。对应 分镜_快拼箱2.0.md。

字幕只写配置表里的数据或行业通用做法；没核实的数字不上字幕。
"""
from engine.anim import *
from . import model as m

# 这个示例是中英双语说明版，不是默认的国际站营销版
LANG = "zh+en"
FORMATS = ["16:9"]
MAX_WORDS = None

FULL = ["@00_ground", "@01_foundation", "@02_floor_frame", "@03_floor_deck", "@04_posts", "@05_roof_frame",
        "@06_walls", "@07_door_window", "@08_trim", "@09_fasteners", "@10_services"]
FLOOR = ["@02_floor_frame", "@03_floor_deck"]
OTHER_POSTS = ["post_01", "post_10", "post_11"]
OTHER_PIPES = ["downpipe_01", "downpipe_10", "downpipe_11"]
OTHER_BOTS = ["bolt_01_bot_*", "bolt_10_bot_*", "bolt_11_bot_*"]
OTHER_TOPS = ["bolt_01_top_*", "bolt_10_top_*", "bolt_11_top_*"]
DOOR = ["front_wall_1_door", "front_door_*"]
DOOR_LEAF = ["front_door_leaf", "front_door_handle"]
WIN_F = ["front_wall_3_window", "front_window_*"]
WIN_R = ["rear_wall_2_window", "rear_window_*"]
CENTER = (0, 0, 1.3)

# 拼箱 / 叠箱：横向再拼 2 台，上面再叠 3 台（相对原箱的偏移）
COMBO = [(0, m.W, 0), (0, 2 * m.W, 0), (0, 0, m.H), (0, m.W, m.H), (0, 2 * m.W, m.H)]


SHOTS = [
    shot("00_intro", 4, title=("快拼箱 2.0 安装指南", "Quick-Assembly Container House 2.0 · Installation Guide"),
         card=True, show=FULL, subtitle=("外尺寸 6055 × 2990 × 2896 mm", "External size 6055 × 2990 × 2896 mm"),
         cam=cam((0, 0, 0.5), (-40, -25), 14, (13, 11.5))),

    shot("01_overview", 10, title=("结构组成", "Main components"),
         show=[x for x in FULL if x not in ("@08_trim", "@09_fasteners", "@10_services")],
         cam=cam(CENTER, (-35, -28), 30, 13.5),
         do=[move("@05_roof_frame", 5.5, 2.5, frm=(0, 0, 1.6), hl=False),
             move(["@06_walls", "@07_door_window"], 5.5, 2.5, out=0.9, hl=False),
             move(["@04_posts"], 5.5, 2.5, frm=(0, 0, 0.7), hl=False)],
         callouts=[callout("roof_sheet", 0.6, 4.6, "顶框：屋面、保温、吊顶、灯具预装", "Roof frame: roofing, insulation, ceiling, lights pre-fitted", "up"),
                   callout("post_10", 1.0, 4.2, "角柱 ×4", "Corner posts ×4", "right", anchor="top"),
                   callout("front_wall_0_panel", 1.4, 3.8, "50 mm 岩棉夹芯墙板", "50 mm rock-wool sandwich panels", "left"),
                   callout("floor_corner_00", 1.8, 3.4, "底框：地板预装", "Floor frame: flooring pre-fitted", "left")]),

    shot("02_foundation", 7, title=("基础找平", "Prepare the foundation"), step=1,
         show=["@00_ground"],
         cam=cam((0, 0, 0), (-30, -15), 32, (10, 9)),
         do=[move("@01_foundation", 0.5, 0.8, frm=(0, 0, 0.5), stagger=0.25)],
         notes=[note(2.5, 4.3, "混凝土墩基础，顶面找平，误差 ≤ ±5 mm", "Concrete piers, top surfaces levelled within ±5 mm")]),

    shot("03_delivery", 10, title=("到货就位", "Set down and unpack"), step=2,
         cam=cam((0, 0, 0.6), (-28, -18), 26, 10.5),
         do=[move(FLOOR + ["@91_bundle"], 0.3, 2.5, frm=(0, 0, 1.8), hl=False),
             move("@05_roof_frame", 0.3, 2.5, frm=(0, 0, m.BUNDLE_DROP + 1.8), to=(0, 0, m.BUNDLE_DROP), hl=False),
             move("@05_roof_frame", 3.4, 2.0, frm=(0, 0, m.BUNDLE_DROP), to=(0, 0, 1.8), exit=True),
             move("@91_bundle", 5.2, 1.4, to=(8, 0, 0), exit=True),
             appear("diag_*", 6.6), vanish("diag_*", 9.8)],
         notes=[note(0.4, 5.6, "货包吊放到基础上，吊走顶框，取出夹层部件", "Set the bundle on the piers, lift off the roof frame, unpack the parts"),
                note(6.3, 3.5, "底框留在原位，调平并复核两条对角线相等", "Level the floor frame and check both diagonals are equal")]),

    shot("03b_floor_beams", 6, title=("到货就位", "Set down and unpack"), step=2,
         hide=["@03_floor_deck"],
         cam=cam((0, 0, 0.1), (-20, -8), 52, 8.5),
         do=[highlight("floor_beam_*", 0.3, 1.6), highlight("floor_joist_*", 1.6, 4.0)],
         callouts=[callout("floor_beam_front", 0.5, 2.0, "底框主梁 160 mm", "Floor main beam 160 mm", "down"),
                   callout("floor_joist_4", 2.0, 3.8, "分配梁 方管 100×50 ×9", "Floor joists 100×50 tube ×9", "up")],
         notes=[note(0.4, 5.4, "透视：地板下是主梁 + 9 根分配梁", "X-ray: main beams + 9 joists under the floor")]),

    shot("05a_post", 6, title=("安装角柱", "Install corner posts"), step=3,
         cam=cam("floor_corner_00", (-50, -40), 24, (1.25, 1.05), lens=40),
         do=[drop(["post_00", "downpipe_00"], 0.5, 2.0, h=0.9), screw("bolt_00_bot_*", 3.0, stagger=0.2)],
         callouts=[callout("floor_corner_00_ears", 0.3, 2.0, "角件耳板", "Corner fitting lugs", "right"),
                   callout("bolt_00_bot_1", 4.0, 2.0, "高强螺栓", "High-strength bolts", "right")],
         notes=[note(2.6, 3.4, "角柱套入耳板，螺栓先不拧死", "Slide the post over the lugs; keep bolts hand-tight")]),

    shot("05b_posts", 6, title=("安装角柱", "Install corner posts"), step=3,
         cam=cam(CENTER, (-42, -30), 26, 11),
         do=[drop([f"post_{k}", f"downpipe_{k}"], 0.4 + i * 0.8, 1.2, h=1.5) for i, k in enumerate(("10", "11", "01"))] +
            [screw(OTHER_BOTS, 3.4, stagger=0.03), highlight("post_*", 4.4, 1.2)],
         callouts=[callout(f"post_{k}", 0.2 + i * 0.8, 5.6 - i * 0.8, str(i + 1), "", "up", anchor="top")
                   for i, k in enumerate(("00", "10", "11", "01"))],
         notes=[note(3.0, 2.9, "4 根角柱 210 × 150，逐根就位", "4 corner posts 210 × 150, set one by one")]),

    shot("06a0_roof_beams", 6, title=("吊装顶框", "Lift the roof frame on"), step=4,
         hide=["roof_sheet", "roof_insulation"],
         cam=cam((0, 0, m.H + 1.8), (-25, -12), 40, 9.5),
         do=[move("@05_roof_frame", 0, 0.1, frm=(0, 0, 1.8), to=(0, 0, 1.8), hl=False),
             highlight("roof_beam_*", 0.4, 1.6), highlight("roof_purlin_*", 1.8, 3.8)],
         callouts=[callout("roof_beam_front", 0.6, 2.0, "顶框主梁 180 mm", "Roof main beam 180 mm", "down"),
                   callout("roof_purlin_3", 2.2, 3.6, "分配梁 C80×40 ×6", "Roof purlins C80×40 ×6", "up")],
         notes=[note(0.4, 5.4, "透视：屋面板下是主梁 + 6 根分配梁", "X-ray: main beams + 6 purlins under the roof sheet")]),

    shot("06a_roof", 6, title=("吊装顶框", "Lift the roof frame on"), step=4,
         cam=cam(CENTER, -30, 26, 11.5),
         do=[drop("@05_roof_frame", 0.4, 3.0, h=1.8)],
         notes=[note(0.6, 5.2, "顶框吊装，四角对准角柱", "Lower the roof frame onto the four posts")]),

    shot("06b_roof_bolts", 6, title=("吊装顶框", "Lift the roof frame on"), step=4,
         cam=cam("roof_corner_00", (-50, -40), -16, 1.3, lens=40),
         do=[screw("bolt_00_top_*", 0.5, stagger=0.2), screw(OTHER_TOPS, 0.5, stagger=0.02, hl=False),
             highlight("bolt_*", 3.2, 1.6)],
         notes=[note(2.8, 3.2, "校正垂直度和对角线后，全部螺栓统一拧紧", "Square up, then fully tighten all bolts")]),

    shot("07_walls", 10, title=("安装墙板", "Install wall panels"), step=5,
         cam=cam(CENTER, (-30, 10), 20, 11),
         do=[move("*_wall_*_panel", 0.4, 1.2, out=0.8, stagger=0.3)],
         callouts=[callout("front_wall_0_panel", 5.0, 4.6, "50 mm 岩棉夹芯板 · 1150 型", "50 mm rock-wool sandwich panel · 1150 type", "up")],
         notes=[note(4.6, 5.2, "墙板下端插入底槽，板间企口拼接，顶部固定", "Seat panels in the bottom channel, interlock the joints, fix at the top")]),

    shot("08_openings", 8, title=("安装门窗", "Fit door and windows"), step=6,
         cam=cam(CENTER, (25, -10), 14, 10),
         do=[move(DOOR, 0.4, 1.4, out=0.8), move(WIN_F, 1.4, 1.4, out=0.8), move(WIN_R, 1.6, 1.4, out=0.8, hl=False),
             rotate(DOOR_LEAF, 3.0, 1.0, axis="Z", edge="-x", frm=0, to=-70),       # 开门：绕铰链边转向外
             rotate(DOOR_LEAF, 6.2, 1.0, axis="Z", edge="-x", frm=-70, to=0, hl=False)],
         callouts=[callout("front_door_leaf", 3.2, 4.6, "钢门 920 × 2030", "Steel door 920 × 2030", "up"),
                   callout("front_window_frame", 3.6, 4.2, "塑钢窗 1130 × 1100，带防盗杆", "uPVC window 1130 × 1100 with security bars", "right")]),

    shot("09_trim", 10, title=("收边密封", "Flashing and sealing"), step=7,
         cam=cam(CENTER, (35, 50), 22, 10.5),
         do=[move("post_wrap_*", 0.4, 1.2, out=0.5, stagger=0.2), drop("roof_wrap", 1.6, 1.4, h=0.8),
             appear("skirting", 3.0, hl=2.0)],
         notes=[note(3.2, 6.6, "装包柱件、顶部包边和踢脚线，接缝打胶密封", "Fit post and roof flashings and skirting; seal all joints")]),

    shot("09b_seal", 5, title=("收边密封", "Flashing and sealing"), step=7,
         cam=cam((-m.L / 2 + 0.9, -m.W / 2 + 0.25, m.H), (-40, -30), 34, (1.5, 1.25), lens=40),
         do=[grow("seal_front", 0.5, 4.0)],
         callouts=[callout("seal_front", 1.2, 3.6, "防水密封胶", "Waterproof sealant", "up")],
         notes=[note(0.4, 4.4, "顶框四边接缝打防水密封胶", "Seal all four roof edges with waterproof sealant")]),

    shot("09c_seal_all", 5, title=("收边密封", "Flashing and sealing"), step=7,
         cam=cam((0, 0, m.H), (-30, -15), 55, 8.5),
         do=[grow(["seal_right", "seal_rear", "seal_left"], 0.3, 1.1, stagger=1.1), highlight("seal_*", 3.8, 1.0)],
         notes=[note(0.3, 4.5, "四边全部打胶，不留缝隙", "All four edges sealed, no gaps")]),

    shot("10a_drain", 5, title=("排水与电气", "Drainage and electrics"), step=8,
         hide=["post_*", "post_wrap_*", "roof_wrap"],
         cam=cam((-m.L / 2 + 1, -m.W / 2, 1.3), (-50, -40), 12, 7.5),
         do=[highlight("downpipe_*", 0.3, 4.2)],
         callouts=[callout("downpipe_00", 0.8, 3.8, "角柱内落水管", "Downpipe inside the corner post", "right")],
         notes=[note(0.5, 4.3, "屋面有组织内排水，雨水经角柱内落水管排出", "Internal roof drainage through pipes inside the corner posts")]),

    shot("10b_elec", 5, title=("排水与电气", "Drainage and electrics"), step=8,
         hide=["front_wall_*", "front_door_*", "front_window_*", "post_wrap_00", "post_wrap_10", "post_00", "post_10",
               "downpipe_00", "downpipe_10", "bolt_00_*", "bolt_10_*"],
         cam=cam((0, 0.3, 1.4), 0, 8, 6.5, lens=28),
         do=[appear("@10_services", 0.4, hl=3.0)],
         callouts=[callout("led_0_tube", 1.0, 3.8, "LED 灯 ×2", "LED lights ×2", "down"),
                   callout("ac_socket", 1.3, 3.5, "16A 空调插座", "16 A A/C socket", "left")],
         notes=[note(0.5, 4.3, "接通开关、插座和配电箱", "Connect switches, sockets and the breaker box")]),

    shot("11a_inside", 5, title=("完成", "Completed"),
         cam=cam((2.6, -0.4, 1.4), -90, 2, 4.6, lens=24, target_end=(2.6, 0.4, 1.4))),

    shot("11b_outside", 5, title=("完成", "Completed"),
         cam=cam(CENTER, (20, 55), 14, 11),
         notes=[note(0.5, 4.3, "6055 × 2990 × 2896 mm · 50 mm 岩棉夹芯板 · 可叠 3 层",
                     "6055 × 2990 × 2896 mm · 50 mm rock-wool panels · stacks up to 3 storeys")]),

    shot("12_combo", 8, title=("拼箱与叠箱", "Combine and stack"),
         cam=cam((0, m.W, m.H), (-40, -30), 18, (20, 18)),
         do=[copies(FULL[2:], COMBO, at=1.0, drop=2.0, dur=1.2, stagger=0.6)],
         notes=[note(4.0, 3.8, "可横向拼接，最多叠 3 层", "Join side by side; stack up to 3 storeys")]),
]
