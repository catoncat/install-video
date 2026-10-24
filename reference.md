# 引擎参考

一个产品就是一个目录（目录名必须是合法的 Python 标识符），里面有：

```
<产品>/
  model.py      必需：build() 建模
  shots.py      必需：SHOTS 分镜；FORMATS / VERSIONS / LANG / MAX_WORDS / TEXT / MUSIC / STYLE / FORMAT_ZOOM 和 prepare() 可选
  music.mp3     可选：指定背景音乐，不放就用程序合成
  photos/       可选：应用场景照片（photo() 用）
  out/<画幅>/   自动生成，每个画幅一个目录（16x9 / 1x1 / 9x16）：frames/ overlay/ review/ timeline.json log.txt text.md
                <档位>_<画幅>[_<shots>].mp4（如 draft_16x9.mp4、final_9x16_03b.mp4，小样不会覆盖全片）
                <档位>_<画幅>_<版本>.mp4（VERSIONS 里每个剪出来的版本，如 final_16x9_30s.mp4）
```
两个文件都是普通 Python。积木不够用时，直接写 bpy 代码。

## model.py

从 `engine.geo` 导入：

| 函数 | 作用 |
|---|---|
| `mat(name, color, metallic, rough, transmission=0, emission=0)` | 材质 |
| `box(name, size, center, mat, stage, bevel=0, **props)` | 长方体 |
| `boxes(name, [(size, center), ...], mat, stage, ...)` | 多个长方体合成一个对象（比如带洞口的墙板） |
| `profile(name, pts, length, axis, origin, mat, stage)` | 2D 截面沿 X/Y/Z 拉伸，用于型钢、槽 |
| `c_pts(h, f, t, d)` | C 型钢截面 |
| `cylinder(name, r, depth, center, axis, mat, stage)` | 圆柱 |
| `cut(obj, [("cyl", (直径, 深), 中心, 轴), ("slot", (宽, 深, 高), 中心, 轴)])` | 开圆孔或长圆孔（布尔运算） |
| `obj(name, bmesh, mat, stage)`、`add_bevel(obj, w)` | 自己用 bmesh 建模时用 |
| `pose(name, sel, rotate=dict(axis, pivot, deg) 或 [..], move=(dx,dy,dz))` | 登记具名姿态（运输时的折叠状态等），见"折叠类产品"。同一对象多次调用按顺序叠加 |
| `wire_box(name, size, center, stage, t=0.03, material=None, fill=None)` | 线框长方体（12 条边），`fill=ghost()` 再加半透明盒体：40HQ 轮廓、吊装范围、尺寸示意 |
| `ghost(name="ghost", color=..., alpha=0.18)` | 半透明说明材质 |
| `resolve(sel)`、`model_objects()` | 在 model.py 里也能用选择器 |

约定：
- 单位米，Z 朝上，-Y 是正面。尺寸参数放在文件开头。
- 每个对象带 `["stage"]`，stage 名建议用 `数字_名称`，比如 `04_posts`，按安装顺序编号。
- `**props` 会写成对象的自定义属性。`out=[x,y,z]` 是朝外方向，`move(out=...)` 和 `screw` 会用到；`spin_axis="X"` 指定旋转轴。
- 说明用的辅助物（对角线、打包状态等）单独放一个 stage，默认不出现，由分镜调出来。
- **地面不用自己建**：引擎自带深色无缝背景（地面在 z=-0.21，颜色由 STYLE 的 floor 控制）。产品自己建的大块地面会被灯照亮、边缘还会变成一条地平线，让浅色产品和背景分不开。示例里的 ground_pad 只是一小块工地地坪。
- 名字要稳定、能读出含义（`post_00`、`front_wall_1_door`），分镜靠名字选对象。
- 对象属性 `touch_ok=True`（或 `touch_ok="名字通配"`）：设计上就和别的零件贴在一起，`video check` 不报。`bg=True`：背景类大物体（地坪等），卡片避让时不算主体（stage 名里带 ground 的也不算）。

## shots.py

`from engine.anim import *`，然后写 `SHOTS = [...]`。时间单位是秒，相对于所在 shot 的开头。

**选择器 sel**：`"post_*"` 按名字通配，`"@04_posts"` 选整个 stage，也可以放进一个 list 组合。匹配不到会直接报错，并给出名字相近的对象。

| 积木 | 说明 |
|---|---|
| `shot(id, dur, title=(中,英), step=None, card=False, card_pos="auto", subtitle=None, show=None, hide=(), cam=None, do=(), notes=(), callouts=(), module=None)` | `show`：开头可见的内容，不给就沿用上一个 shot 结束时的状态。`hide`：只在本 shot 内临时隐藏（做透视用）。`step`：左上角的步骤编号。`card`：标题居中显示（片头、片尾），`card_pos="auto"`（默认）按主体在画面里的位置选上 / 下方，还挡着就自动拉远、平移机位让开，仍超过 10% 才警告；也可以指定 top / center / bottom，`subtitle=(中, 英)` 是卡片第二行小字（纯英文模式也有）。`cam=None` 时沿用上一个机位。`module`：属于哪一段（intro / install / options / scenes / cta），出片时统计各段占比 |
| `cam(target, az=, el=, dist=, lens=35, target_end=None, fmt=None)` | **建议用关键字写**（`cam(C, az=-40, el=20, dist=12)`），四个数挤在一起容易看错。相机绕 target（选择器或坐标）转。相机跑到地面以下会警告。az 是方位角（0° 在 -Y 正前方，逆时针为正），el 是俯仰角，单位都是度；dist 是距离，单位米。给 `(起, 止)` 就平滑过渡。选择器按零件的**静止位置**取中心，和动画进行到哪无关。`fmt={"9:16": dict(dist=14, el=20)}` 单独调某个画幅的机位 |
| `move(sel, at, dur, frm=(0,0,0), to=(0,0,0), out=None, spin=0, stagger=0, hl=None, exit=False, relative="rest")` | 从"基准 + frm"移到"基准 + to"。基准默认是静止位置；`relative="current"` 时是对象当前的动画位置（折叠状态下整体吊装：`drop(UNIT, 0.3, 2.4, h=3.5, relative="current")`）。原本不可见的对象，在移动开始时出现。`exit=True` 表示移完后隐藏。装上去的零件默认高亮 |
| `set_pose(name, at=0, sel=None)` | 硬切到 model.py 里登记的姿态（`"rest"` 是装好后的静止姿态）。sel 不给就是登记了该姿态的全部对象 |
| `to_pose(name, at, dur, sel=None, stagger=0, hl=None)` | 从当前姿态动画过渡到 name，沿登记的转动路径走（弧线）。`to_pose("rest", 1, 2, sel="roof_wing_*")` 就是"屋顶翼板展开"；`to_pose("folded", ...)` 折回去。当前姿态不在路径上时退化成直线 + 球面插值 |
| `drop(sel, at, dur=1.5, h=1.2)`、`lift(...)` | 从上方落下、往上吊走 |
| `screw(sel, at, dur=1, dist=0.12, turns=3, stagger=0.08)` | 沿 out 方向一边转一边拧入 |
| `rotate(sel, at, dur, axis="Z", pivot=None, edge=None, frm=0, to=90, stagger=0, hl=None, exit=False)` | 绕世界坐标里的一条轴转动（开门、翻板、铰链），角度为度。`pivot` 是轴经过的点：坐标或选择器（取静止包围盒中心），不给就用 sel 自己的；`edge="-x"` 等取包围盒那一侧的面中心（门的铰链边）。多个对象一起转时当作一个整体。转完保持姿态，可以在后面的 shot 里再转回来 |
| `copies(sel, spots, at=0, until=None, drop=0, dur=1.2, stagger=0)` | 把 sel 整体复制到 spots（相对偏移的列表）：拼箱、叠箱、货包、营地。集合实例，几乎不占渲染时间。`drop>0` 时从上方落下；`until` 秒消失（可以超出本 shot，不给就留到片尾） |
| `grow(sel, at, dur=1.5, stagger=0)` | 沿对象的 `grow_axis` 从 0 长到原长，用于打胶、走线。对象原点要放在起点 |
| `appear(sel, at, hl=0)`、`vanish(sel, at)`、`highlight(sel, at, dur)` | 出现、消失、橙色高亮 |
| `swap(sel, tag, at, hl=0)` | 把 sel 换成 `geo.variant()` 做好的材质版本 `tag`（`tag=None` 换回原样）。定制选项展示用 |
| `photo(path, at=0, dur=None, zoom=(1.0, 1.08))` | 全屏照片打底（用户的场景图、实拍图），按画幅铺满、自动裁掉宣传图常见的白边，`zoom` 缓慢推近。只在本 shot 里可见。路径相对产品目录，文件不存在时跳过并警告。常配合 `card=True` 写场景名 |
| `note(at, dur, 中, 英)` | 底部说明字幕。字幕自动排队：后一条等前一条淡完才出现（淡入 8 帧、淡出 6 帧，约 0.27 / 0.2 秒），所以首尾相接也不会叠在同一屏；排队后太短会警告 |
| `callout(sel, at, dur, 中, 英, side="right")` | 带引线的标注，跟着零件移动。side 取 right、left、up、down |
| 普通函数 `fn(ctx)` 放进 `do` | 自定义动画，见下面"写自定义动画" |

`TEXT = dict(card=1.5, note=1.2)`：按类型放大文字（step 步骤标题、card 居中卡片及其副标题、note 底部字幕、callout 标注），手机竖屏观看时常用。一行放不下会自动折行（最多两行），还放不下就缩小字号，并在输出里提示是哪条文字。
`FORMATS = ["16:9", "1:1", "9:16"]`：要出的画幅（默认三种）。draft / preview 默认只出第一个，final 出全部，`--format 9:16` / `--format all` 指定。设计尺寸短边都是 1080，所以字在各画幅里一样大；相机按水平视野对齐，竖屏、方屏上下多出空间。
`FORMAT_ZOOM = {"1:1": 1.15, "9:16": 1.3}`：方屏 / 竖屏相对 16:9 推近多少（乘到镜头焦距上）。单个镜头用 `cam(..., fmt=...)` 覆盖。
`VERSIONS = {"60s": dict(shots=None, target=(45, 60)), "30s": dict(shots=["00", "03", ...], target=(25, 35)), ...}`：从同一批渲染帧剪出多个版本，`shots` 是 shot id 前缀列表（按时间线顺序拼接），`None` 表示全片；`target` 给了就核对时长。也可以直接写 `"30s": ["00", "03"]`。只渲了部分 shot 时，用不全的版本会跳过。
`MODULE_MAX = {"options": 0.2}`：各段时长占比上限，超过就警告（默认定制选项 ≤ 20%）。
`MAX_WORDS = 8`：每屏（同时可见的标题 + 字幕 + 标注）英文单词上限，默认 8；`None` 不检查。出片和 `video text` 都会标出超过的那几屏。
`LANG = "en"`：纯英文字幕（英文升为主行，用英文字体），默认就是 `"en"`；说明版用 `"zh+en"` 中英双语。字幕的中文那一栏照样要填，方便和用户核对。
`def prepare():`：模型建好之后、时间线之前调用一次，用来做材质变体等（见下面"材料库和定制选项"）。
`MUSIC = dict(bpm=96, root=48, seed=1)`：调整合成音乐的速度、调性（MIDI 根音）和随机种子。
`STYLE = dict(bg=..., floor=..., ambient=..., ambient_strength=..., lines=True, line_color=..., line_opacity=0.75, hl=(1.0, 0.42, 0.05))`：覆盖画面风格，默认值见 `engine/scene.py` 里的 STYLE。背景色只给相机看，环境光单独设置，所以背景可以调得很暗，不会影响照明。`hl` 是高亮色，产品本身是木色 / 暖色时换成青色之类，免得"正在高亮"和"本来就是这个颜色"分不清。
背景是碗形无缝背景（半径 60 m 的平地，外圈以 40 m 圆弧上翻），任何仰角都看不到边；相机离产品别超过约 80 m。

几条经验：
- 卡片镜头：默认 `card_pos="auto"` 会自动避开主体（必要时拉远、平移机位）。主体特别大、怎么都让不开时会警告，这时把镜头拉远或换个角度。
- 高亮最晚在本 shot 结束时淡完，不会拖进下一个镜头；超出时输出里会有警告。
- 同一步可以拆成几个 shot（特写一个、全景一个），标题保持不变，切镜头时标题不会闪。
- 镜头之间优先直接切换。在一个 shot 里同时移动注视点又大幅拉远，容易穿过模型。
- 移动之间零件会保持不动；同一个零件可以在多个 shot 里先后移动，比如先吊走、后面再装回来。

## 材料库和定制选项

`engine/library.py` 有一组程序化材质预设（不需要贴图文件），`library.PRESETS` 列出全部：
sandwich_white / sandwich_grey（夹芯板）、metal_dark（金属板）、flexible_stone（柔性石材）、soft_stone（软瓷）、cement（水泥质感）、
wpc_wall（木塑墙板）、spc_oak（SPC 石塑地板）、wpc_floor（木塑地板）、tile（瓷砖）、gypsum（石膏板吊顶）、pvc_ceiling（扣板吊顶）、led_panel（平板灯）。
用户有材料实拍图时用 `library.mat_image(名字, 路径, scale=每米重复次数)` 当贴图。

```python
from engine import geo, library

def prepare():
    geo.variant("@06_walls", "stone", library.material("soft_stone"))    # 墙板复制一份换成软瓷，默认隐藏
    geo.variant("floor_pvc", "oak", library.material("spc_oak"))

# 分镜里：同一箱体快速切换
shot("09_options", 4, title=("可定制", "Customizable Options"), module="options",
     do=[swap("@06_walls", "stone", 0.4), swap("@06_walls", None, 3.0)])
```
变体和原件共用网格、放在原件的静止位置，不跟原件的动画；在箱体装好之后的镜头里切换。

## 写自定义动画

积木不够用时（联动机构、逐帧计算的姿态），在 `do` 里放一个普通函数 `fn(ctx)`。先知道引擎怎么处理关键帧：
- 建时间线时，所有模型对象的动画会被清掉，当前位置和旋转记为"静止姿态"（`o["rest"]`、`o["rest_rot"]`）。
- Blender 在第一个关键帧之前会沿用第一个关键帧的值。用 `ctx.key` 打关键帧，引擎会自动在第 1 帧补上静止姿态，免得片头就提前变了样。
- 积木打的关键帧在动作结束后保持不动（CONSTANT）。自己打的关键帧默认是缓动插值；逐帧计算的姿态用 `interp="LINEAR"`，镜头切换处用 `ctx.cut` 硬切。
- 模型之外新建的对象（空物体、集合实例），片头起默认可见。用 `ctx.only_in_shot` 只让它在需要的时间段出现。
- `move` / `rotate` / `to_pose`：本 shot 里第一次动某个零件时，会在 shot 开头补一帧起始姿态（所以镜头一开始就摆好，不会从上一个镜头的位置滑过来）。
- `rotate` 和 `to_pose` 每 2 帧打一个线性关键帧（转动是弧线，只打首尾会走直线）。
- `copies` 的副本跟着原件的动画和显隐走：原件在动，所有副本一起动；原件隐藏，副本也看不到。
- 引擎记着每个零件"当前姿态"（积木动过之后的位置和旋转），`relative="current"` 和 `to_pose` 都从这里出发。`ctx.key` 自己打的关键帧**不会**更新这个记录，混用时注意。
- 姿态算法是公开的：`pose_after_rotate(位置, 旋转矩阵, 轴, 轴心, 度)` 返回转过之后的 (位置, 旋转矩阵)，`pose_tf(obj, "folded", f=0.5)` 返回折到一半的姿态。自己写联动时用它们，和积木衔接不会跳。

`ctx` 提供（秒数都相对本 shot 开头）：

| 方法 | 作用 |
|---|---|
| `ctx.f(秒)`、`ctx.dur` | 转帧号；本 shot 时长 |
| `ctx.resolve(sel)` | 选择器转对象列表 |
| `ctx.key(obj, 秒, loc=(x,y,z), rot=(x,y,z) 弧度, interp=None/"LINEAR"/"CONSTANT")` | 打位置、旋转关键帧 |
| `ctx.cut(objs, 秒=0)` | 该时刻之前最后一个关键帧改成 CONSTANT（硬切到新姿态） |
| `ctx.vis(obj, 秒, True/False)` | 显隐 |
| `ctx.only_in_shot(objs, frm=0, to=None)` | 只在本 shot 的 [frm, to] 秒可见 |

最小示例：一块板边升边转，每帧算一次姿态。

```python
import math
def raise_panel(ctx):
    for o in ctx.resolve("panel_*"):
        x, y, z = o["rest"]
        n = round(ctx.dur * 30)
        for k in range(n + 1):
            u = k / n
            ctx.key(o, ctx.dur * u, loc=(x, y, z + 0.5 * u), rot=(0, 0, math.radians(90 * u)), interp="LINEAR")
        ctx.cut(o, 0)          # 和上一个镜头之间硬切

SHOTS = [..., shot("05_panel", 3, do=[raise_panel]), ...]
```

联动（比如墙顶顺着屋顶滑槽走，墙的角度由屋顶高度决定）没有现成积木：照这个写法，逐帧算出每个零件的位置和角度再 `ctx.key`。绕某条轴转的一段可以直接用 `rotate`。

## 折叠类产品（运输状态 → 吊装 → 展开）

模型照常按"装好后"建，在 model.py 里登记运输姿态，分镜里三行搞定：

```python
# model.py
for s, tag in ((-1, "f"), (1, "r")):
    box(f"wing_{tag}", (L, WING, 0.12), (0, s * (W / 2 + WING / 2), 0.06), M["deck"], "02_wings")
    # 运输时翼板绕主箱底边竖起来贴在侧面
    pose("folded", f"wing_{tag}", rotate=dict(axis="X", pivot=(0, s * W / 2, 0.12), deg=90 * s))
pose("folded", "end_panel", move=(-0.65, 0, 0))          # 端板收进箱内

# shots.py
ALL = ["@01_core", "@02_wings", "@03_panel"]
SHOTS = [
    shot("02_crane", 3, show=ALL, title=("吊装就位", "Lift & Position"), step=2, cam=cam(C, az=-35, el=22, dist=11),
         do=[set_pose("folded"), drop(ALL, 0.5, 2.0, h=2.5, relative="current", hl=False)]),
    shot("03_unfold", 4, title=("展开", "Unfold"), step=3, cam=cam(C, az=(-35, -20), el=24, dist=11),
         do=[to_pose("rest", 0.3, 1.6, sel="wing_*", stagger=0.4), to_pose("rest", 2.4, 1.2, sel="end_panel")]),
]
```
多个零件一层层折叠收纳时，用 `video check` 看收纳层次有没有互相穿过。

## 质量档位

| 档位 | 输出分辨率 | 帧 | 采样 | 用途 |
|---|---|---|---|---|
| draft | 480×270（竖屏 270×480，方屏 270×270） | 隔帧 | 8 | 快速检查全片结构 |
| preview | 960×540（竖屏 540×960，方屏 540×540） | 隔帧 | 16 | 检查细节、给用户看 |
| final | 1920×1080（竖屏 1080×1920，方屏 1080×1080） | 逐帧 | 8 | 成片 |

所有档位都按 2 倍分辨率渲染，合成时再缩小（超采样，`scene.SS`）。描边是对法线、深度、零件编号做边缘检测得到的，必须超采样才会细而直、逐帧不闪；超采样后每个输出像素已有 4 倍样本，采样数可以低一些。
噪点主要来自面光的软阴影：补光灯面保持在 3 m 左右，并设置 `shadow_ray_count=2`。灯面调大会重新出现颗粒感。

**并行渲染**：`make` 会同时开 N 个 Blender 进程，按帧号分工（第 i 个进程渲每 N 帧里的第 i 帧）。N 默认取 CPU 核数 / 4，限制在 1 到 3，可用环境变量 `VIDEO_WORKERS` 覆盖。EEVEE 每帧主要吃 GPU，多开进程只是把存图、合成这类 CPU 开销叠起来；每个进程又要占一份显存，开多了反而会爆显存或变慢。显卡显存小（4 GB 以下）就设 `VIDEO_WORKERS=1`。

## 输出和自查

- `make` 默认只显示摘要（时间线、渲染耗时、合成结果、各版本时长、各段占比、review 路径、警告和提示），Blender 的逐帧日志写进 `out/<画幅>/log.txt`。加 `-v` 或设 `VIDEO_VERBOSE=1` 显示完整输出。出错时会打印日志的最后 30 行。
- 每次出片后自动核对：视频尺寸、帧数、帧率要和时间线一致；review 截图不能是纯色帧，整条视频截到的帧不能完全一样。不通过就报错退出（review 图照样会生成，方便查原因）。单个 shot 的几张截图完全一样只提醒，因为可能是静止镜头。
- `video text <产品目录>` 按时间列出每一屏同时出现的文字、英文单词数、按当前字号算的宽度，写到 `out/<画幅>/text.md`。合成时也会自动生成并警告超过 `MAX_WORDS` 的屏。
- draft 的 review 拼图用内部 2 倍分辨率的渲染帧（960 宽）叠字幕层，特写里的小零件也看得清；纯色帧 / 全部相同的自查仍然用从成片里截的帧。
- `video check <产品目录> [帧号...]`：穿模检查。抽查（默认每 6 帧）不在静止位置的零件（正在动或处于折叠等姿态）和别的 stage 的零件网格是否相交，按 stage 两两归组报告，附 shot 和帧范围。设计上贴在一起的加 `touch_ok`。
- `video swatch [产品目录]`：材料库全部预设（给了产品目录再加上产品自己的材质、变体）在标准灯光下逐个渲染，拼成带名字的色卡 `out/swatch.jpg`。挑定制饰面时先看它：浅色在主光下会被提亮，两种饰面要拉开差别才看得出切换。
- `video compose <产品目录>` 会先按上次的档位重新导出时间线（所以改了字幕、`MAX_WORDS`、`VERSIONS` 都会生效），再重做字幕层、合成和各版本，不重新渲染。改了动画、机位、模型就要重新 `make`。

## 在打开的 Blender 里实时调试（可选，需要 Blender MCP）

```python
p = "<skill>/engine/run.py"; g = {"__file__": p, "__name__": "mcp"}
exec(open(p).read(), g); g["main"](["<产品目录>", "--no-render"])
```
然后用 MCP 的 look（`mode="frames", view="camera", frames=[...]`）抽帧看。每次运行都会重新加载 engine 和产品模块。
安装 MCP：`claude mcp add blender -e DISABLE_TELEMETRY=true -- uvx blender-mcp`，再把它配套的 addon.py 装进 Blender。装好后到插件偏好设置里**关掉 telemetry_consent**。

## 排错

- `选择器 'xxx' 没有匹配任何对象`：看报错里列出的相近名字，或者检查 stage 名有没有拼错。
- 字体缺失：设置 `OVERLAY_ZH` / `OVERLAY_ZH_BOLD` / `OVERLAY_EN` / `OVERLAY_EN_BOLD`，格式是 `"字体路径:索引"`。
- Windows 上找不到 Blender：设置 `BLENDER=C:\...\blender.exe`。
- 渲染太慢：先用 draft 或只出部分 shot，成片放到后台跑。改了材质后的第一次渲染要编译着色器，会明显慢一些，这是正常的。
- 画面有颗粒：检查是不是加了很大的面光，或者把档位采样调低了。
