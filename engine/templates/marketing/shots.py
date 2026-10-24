"""国际站营销视频分镜模板（video init 默认生成）。

按用途出 3 条片子，每条有自己的画幅和镜头顺序（VERSIONS），不是同一条片子换尺寸：
  main   16:9，45–60 s：国际站主图视频。开场标题 → Step 1–8 安装 → Customizable Options（≤ 20%）→ 应用场景 → 询盘
  detail 1:1，25–35 s：详情页。精简的安装过程 + 卖点
  ad     9:16，12–16 s：广告素材。开头 2–3 秒先放最抓眼的画面（钩子），近景快切，结尾询盘
方屏 / 竖屏的机位由引擎按主体自动重新构图；想专门设计的镜头用 cam(..., fmt={"9:16": dict(...)})，或者写只给某个
版本用的镜头 shot(..., only=["ad"])。
模板先用示例模型（快拼箱）跑通，改成自己的产品时：换掉 model.py，把下面的对象名、选择器、机位、字幕换掉。
字幕默认纯英文、每屏 ≤ 8 个英文单词；中文那一栏也照填，方便和用户核对。
"""
from engine.anim import *
from engine import geo, library
from . import model as m

# ---------------- 输出设置 ----------------
LANG = "en"
MAX_WORDS = 8                              # 每屏（标题 + 字幕 + 标注同时可见的）英文单词上限
VERSIONS = {                               # 每条片子：画幅、用到的 shot（按这个顺序，id 前缀）、目标时长
    "main": dict(format="16:9", shots=None, target=(45, 60)),                                   # 不写 shots：全部（除了 only 别的版本的）
    "detail": dict(format="1:1", shots=["00", "01", "02", "03", "04", "05", "09a", "11a"], target=(25, 35)),
    "ad": dict(format="9:16", shots=["ad_hook", "04", "08", "11b"], target=(12, 16)),           # 钩子在前
}
# TEXT = dict(card=1.2, note=1.2)          # 手机上看嫌字小就放大
# FIT = {"9:16": dict(boost=1.35, max_w=0.92, max_h=0.60)}   # 竖屏主体放多大（宽度倍数、宽高上限）

# ---------------- 选择器（按自己的模型改） ----------------
FULL = ["@00_ground", "@01_foundation", "@02_floor_frame", "@03_floor_deck", "@04_posts", "@05_roof_frame",
        "@06_walls", "@07_door_window", "@08_trim", "@09_fasteners", "@10_services"]
FLOOR = ["@02_floor_frame", "@03_floor_deck"]
POSTS = ["post_*", "downpipe_*"]
DOOR = ["front_wall_1_door", "front_door_*"]
WINDOWS = ["front_wall_3_window", "front_window_*", "rear_wall_2_window", "rear_window_*"]
CENTER = (0, 0, 1.3)
COMBO = [(0, m.W, 0), (0, 2 * m.W, 0), (0, 0, m.H), (0, m.W, m.H), (0, 2 * m.W, m.H)]

# 应用场景照片：放在产品目录的 photos/ 里（用户自己的实拍图或效果图）。不存在时跳过，显示后面的 3D 画面
PHOTOS = {"Labor Camp": "photos/labor_camp.jpg", "Site Office": "photos/site_office.jpg"}


def prepare():
    """模型建好后：给定制选项做材质变体（见 engine/library.py 的 PRESETS）"""
    geo.variant("@06_walls", "stone", library.material("soft_stone"))
    geo.variant("@06_walls", "metal", library.material("metal_dark"))
    geo.variant("floor_pvc", "oak", library.material("spc_oak"))


def step(n, zh, en, dur, **kw):
    """安装步骤镜头：左上角步骤编号 + 标题，归入 install 段"""
    return shot(f"{n:02d}_{en.split()[0].lower()}", dur, title=(zh, en), step=n, module="install", **kw)


SHOTS = [
    # ---------------- 只给广告用：开头钩子（最抓眼的画面先上，近景快切） ----------------
    shot("ad_hook", 3, title=("拼装式集装箱房", "Detachable Container House"), subtitle=("快速安装", "Fast Installation"),
         card=True, module="intro", only=["ad"], show=[x for x in FULL if x not in ("@06_walls", "@07_door_window", "@08_trim")],
         cam=cam(CENTER, az=(-55, -25), el=16, dist=(9, 10.5)),
         do=[move(["@06_walls", "@07_door_window"], 0.2, 0.9, out=1.2, stagger=0.03, hl=False)]),

    shot("00_title", 4, title=("拼装式集装箱房", "Detachable Container House"),
         subtitle=("快速安装 · 平板包装 · 模块化", "Fast Installation · Flat Pack"), card=True,
         module="intro", show=FULL, cam=cam((0, 0, 2.2), az=(-40, -25), el=14, dist=(13, 11.5))),   # 注视点抬高，箱体在画面下半部，标题在上

    step(1, "基础找平", "Prepare Foundation", 3.5, show=["@00_ground"],
         cam=cam((0, 0, 0), az=-25, el=30, dist=9.5),
         do=[move("@01_foundation", 0.3, 0.8, frm=(0, 0, 0.5), stagger=0.15)],
         notes=[note(1.2, 2.2, "混凝土墩找平", "Level concrete piers")]),

    step(2, "安装底框", "Install Bottom Frame", 4.5,
         cam=cam((0, 0, 0.3), az=(-28, -18), el=30, dist=10),
         do=[drop(FLOOR, 0.3, 2.0, h=1.8)],
         notes=[note(2.0, 2.4, "吊装就位，核对角线", "Lift on, check diagonals")]),

    step(3, "安装角柱", "Fix Corner Posts", 4.5,
         cam=cam(CENTER, az=-40, el=24, dist=11),
         do=[drop(POSTS, 0.3, 1.2, h=1.5, stagger=0.15), screw("bolt_*_bot_*", 2.2, stagger=0.02)],
         notes=[note(2.2, 2.2, "高强螺栓连接", "High-strength bolted joints")]),

    step(4, "安装顶框", "Install Roof Frame", 4.5,
         cam=cam(CENTER, az=-30, el=26, dist=11.5),
         do=[drop("@05_roof_frame", 0.3, 2.2, h=1.8), screw("bolt_*_top_*", 2.6, stagger=0.02, hl=False)],
         notes=[note(2.6, 1.8, "顶框工厂预装", "Roof factory pre-fitted")]),

    step(5, "安装墙板", "Mount Wall Panels", 5,
         cam=cam(CENTER, az=(-30, 5), el=20, dist=11),
         do=[move("*_wall_*_panel", 0.3, 1.0, out=0.8, stagger=0.2)],
         notes=[note(2.8, 2.1, "50 mm 岩棉夹芯板", "50 mm sandwich panels")]),

    step(6, "安装门窗", "Install Doors & Windows", 4.5,
         cam=cam(CENTER, az=(20, 5), el=14, dist=10),
         do=[move(DOOR, 0.3, 1.0, out=0.8), move(WINDOWS, 0.8, 1.0, out=0.8),
             rotate(["front_door_leaf", "front_door_handle"], 2.4, 0.8, axis="Z", edge="-x", frm=0, to=-70, hl=False),
             rotate(["front_door_leaf", "front_door_handle"], 3.5, 0.7, axis="Z", edge="-x", frm=-70, to=0, hl=False)],
         notes=[note(1.8, 2.5, "钢门、塑钢窗", "Steel door, uPVC windows")]),

    step(7, "检查与密封", "Check Structure & Sealing", 4,
         cam=cam(CENTER, az=(35, 50), el=22, dist=10.5),
         do=[move("post_wrap_*", 0.3, 1.0, out=0.5, stagger=0.15), drop("roof_wrap", 1.2, 1.0, h=0.8)],
         notes=[note(2.0, 1.9, "接缝全部密封", "All joints sealed")]),

    step(8, "交付使用", "Ready for Use", 3,
         cam=cam(CENTER, az=(50, 70), el=14, dist=11)),

    # ---------------- 定制选项（≤ 20%）：同一箱体快速换外墙 / 地板 ----------------
    shot("09a_options_wall", 4, title=("可定制", "Customizable Options"), module="options",
         cam=cam(CENTER, az=-25, el=12, dist=10.5),
         do=[swap("@06_walls", "stone", 0.4), swap("@06_walls", "metal", 2.2)],
         notes=[note(0.4, 1.7, "外墙：软瓷", "Exterior: Soft Stone"), note(2.2, 1.7, "外墙：金属板", "Exterior: Metal Panel")]),

    shot("09b_options_floor", 3, title=("可定制", "Customizable Options"), module="options",
         cam=cam((2.6, 0, 0.6), az=-90, el=8, dist=4.6, lens=24),
         do=[swap("@06_walls", None, 0), appear("led_*", 0), swap("floor_pvc", "oak", 0.6)],   # 开灯，室内才亮
         notes=[note(0.6, 2.3, "地板：SPC 石塑", "Floor: SPC / WPC / Tile")]),

    # ---------------- 应用场景：用户照片打底 + 场景名 ----------------
    *[shot(f"10{chr(97 + i)}_scene", 2.5, title=("", name), card=True, module="scenes",
           cam=cam((0, m.W, m.H), az=-35, el=18, dist=20), do=[photo(path)] + ([copies(FULL[2:], COMBO, at=0)] if i == 0 else []))
      for i, (name, path) in enumerate(PHOTOS.items())],

    shot("10c_scene", 2.5, title=("", "Worker Dormitory"), card=True, module="scenes",
         cam=cam((0, m.W, m.H), az=(-40, -30), el=18, dist=20)),

    # ---------------- 询盘结尾 ----------------
    shot("11a_cta", 3, title=("支持 OEM/ODM", "OEM/ODM Available"), subtitle=("批发与项目供货", "Wholesale & Project Supply"),
         card=True, module="cta", cam=cam((0, m.W, m.H), az=(-30, -20), el=18, dist=21)),

    shot("11b_cta", 2.5, title=("联系我们获取目录和报价", "Contact Us for Catalog & Price"), card=True,
         module="cta"),

]
