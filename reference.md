# 引擎参考

一个产品就是一个目录（目录名必须是合法的 Python 标识符），里面有：

```
<产品>/
  model.py      必需：build() 建模
  shots.py      必需：SHOTS 分镜；MUSIC 可选，用来调音乐
  music.mp3     可选：指定背景音乐，不放就用程序合成
  out/          自动生成：frames/ overlay/ review/ timeline.json music.wav video.mp4
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

约定：
- 单位米，Z 朝上，-Y 是正面。尺寸参数放在文件开头。
- 每个对象带 `["stage"]`，stage 名建议用 `数字_名称`，比如 `04_posts`，按安装顺序编号。
- `**props` 会写成对象的自定义属性。`out=[x,y,z]` 是朝外方向，`move(out=...)` 和 `screw` 会用到；`spin_axis="X"` 指定旋转轴。
- 说明用的辅助物（对角线、打包状态等）单独放一个 stage，默认不出现，由分镜调出来。
- 名字要稳定、能读出含义（`post_00`、`front_wall_1_door`），分镜靠名字选对象。

## shots.py

`from engine.anim import *`，然后写 `SHOTS = [...]`。时间单位是秒，相对于所在 shot 的开头。

**选择器 sel**：`"post_*"` 按名字通配，`"@04_posts"` 选整个 stage，也可以放进一个 list 组合。匹配不到会直接报错，并给出名字相近的对象。

| 积木 | 说明 |
|---|---|
| `shot(id, dur, title=(中,英), step=None, card=False, show=None, hide=(), cam=None, do=(), notes=(), callouts=())` | `show`：开头可见的内容，不给就沿用上一个 shot 结束时的状态。`hide`：只在本 shot 内临时隐藏（做透视用）。`step`：左上角的步骤编号。`card`：标题居中显示（片头、片尾）。`cam=None` 时沿用上一个机位 |
| `cam(target, az, el, dist, lens=35, target_end=None)` | 相机绕 target（选择器或坐标）转。az 是方位角（0° 在 -Y 正前方，逆时针为正），el 是俯仰角，单位都是度；dist 是距离，单位米。给 `(起, 止)` 就平滑过渡 |
| `move(sel, at, dur, frm=(0,0,0), to=(0,0,0), out=None, spin=0, stagger=0, hl=None, exit=False)` | 从"静止位置 + frm"移到"静止位置 + to"。原本不可见的对象，在移动开始时出现。`exit=True` 表示移完后隐藏。装上去的零件默认高亮 |
| `drop(sel, at, dur=1.5, h=1.2)`、`lift(...)` | 从上方落下、往上吊走 |
| `screw(sel, at, dur=1, dist=0.12, turns=3, stagger=0.08)` | 沿 out 方向一边转一边拧入 |
| `grow(sel, at, dur=1.5, stagger=0)` | 沿对象的 `grow_axis` 从 0 长到原长，用于打胶、走线。对象原点要放在起点 |
| `appear(sel, at, hl=0)`、`vanish(sel, at)`、`highlight(sel, at, dur)` | 出现、消失、橙色高亮 |
| `note(at, dur, 中, 英)` | 底部说明字幕 |
| `callout(sel, at, dur, 中, 英, side="right")` | 带引线的标注，跟着零件移动。side 取 right、left、up、down |
| 普通函数 `fn(ctx)` 放进 `do` | 自定义动画：`ctx.f(秒)` 返回帧号，`ctx.resolve(sel)` 返回对象，`ctx.vis(obj, 秒, True/False)` 控制显隐。示例 `unit_copies` 用集合实例做了拼箱效果 |

`TEXT = dict(card=1.5, note=1.2)`：按类型放大文字（step 步骤标题、card 居中卡片、note 底部字幕、callout 标注），手机竖屏观看时常用。
`LANG = "en"`：只出英文字幕（英文升为主行，用英文字体）。默认 `"zh+en"`，中英双语。字幕的中文那一栏照样要填，方便和用户核对。
`MUSIC = dict(bpm=96, root=48, seed=1)`：调整合成音乐的速度、调性（MIDI 根音）和随机种子。
`STYLE = dict(bg=..., floor=..., ambient=..., ambient_strength=..., lines=True, line_color=..., line_opacity=0.75)`：覆盖画面风格，默认值见 `engine/scene.py` 里的 STYLE。背景色只给相机看，环境光单独设置，所以背景可以调得很暗，不会影响照明。

几条经验：
- 同一步可以拆成几个 shot（特写一个、全景一个），标题保持不变，切镜头时标题不会闪。
- 镜头之间优先直接切换。在一个 shot 里同时移动注视点又大幅拉远，容易穿过模型。
- 移动之间零件会保持不动；同一个零件可以在多个 shot 里先后移动，比如先吊走、后面再装回来。

## 质量档位

| 档位 | 输出分辨率 | 帧 | 采样 | 用途 |
|---|---|---|---|---|
| draft | 480×270 | 隔帧 | 8 | 快速检查全片结构 |
| preview | 960×540 | 隔帧 | 16 | 检查细节、给用户看 |
| final | 1920×1080 | 逐帧 | 8 | 成片 |

所有档位都按 2 倍分辨率渲染，合成时再缩小（超采样，`scene.SS`）。描边是对法线、深度、零件编号做边缘检测得到的，必须超采样才会细而直、逐帧不闪；超采样后每个输出像素已有 4 倍样本，采样数可以低一些。
噪点主要来自面光的软阴影：补光灯面保持在 3 m 左右，并设置 `shadow_ray_count=2`。灯面调大会重新出现颗粒感。

**并行渲染**：`make` 会同时开 N 个 Blender 进程，靠占位文件分帧。N 默认取 CPU 核数 / 4，限制在 1 到 3，可用环境变量 `VIDEO_WORKERS` 覆盖。EEVEE 每帧主要吃 GPU，多开进程只是把存图、合成这类 CPU 开销叠起来；每个进程又要占一份显存，开多了反而会爆显存或变慢。显卡显存小（4 GB 以下）就设 `VIDEO_WORKERS=1`。

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
