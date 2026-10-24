"""分镜 -> 关键帧。

分镜是一个 list，每项由 shot() 生成（就是普通 dict，也可以手写）。
时间单位都是秒，相对于所在 shot 的开头。选择器 sel 可以是：
  "post_*"（对象名通配）、"@04_posts"（整个 stage）、或它们组成的 list。
不够用时，在 do 里放一个普通函数 fn(ctx)，引擎会在该 shot 里调用它（见 Ctx）。
"""
import bpy, math
from mathutils import Vector, Matrix, Euler
from . import geo

FPS = 30
HL_IN, HL_OUT = 0.2, 0.5          # 高亮淡入 / 淡出秒数
# 非 16:9 画幅的镜头放大倍数（相机按水平视野对齐，竖屏 / 方屏上下空间多，适当推近）。
# 产品可在 shots.py 写 FORMAT_ZOOM 覆盖，单个镜头用 cam(..., fmt={"9:16": dict(dist=..., lens=...)}) 覆盖
FORMAT_ZOOM = {"16:9": 1.0, "1:1": 1.15, "9:16": 1.3}


# ---------------- 分镜数据构造（只是返回 dict，方便书写） ----------------
def shot(id, dur, title=None, cam=None, do=(), show=None, hide=(), notes=(), callouts=(), step=None, card=False,
         card_pos="bottom", subtitle=None, module=None):
    """title=(中, 英)；show=该 shot 开头可见的选择器（不给则沿用上一个 shot 结束时的状态）；
       hide=只在本 shot 内临时隐藏；step=左上角步骤编号；card=True 时标题居中大字显示（片头片尾），
       card_pos=top / center / bottom 决定卡片在画面里的位置，subtitle=(中, 英) 是卡片的第二行小字。
       module：这个镜头属于哪一段（如 "intro" / "install" / "options" / "scenes" / "cta"），出片时统计各段时长占比。
       cam=None 时沿用上一个 shot 结束时的机位。"""
    return dict(id=id, dur=dur, title=title, cam=cam, do=list(do), show=show, hide=list(hide),
                notes=list(notes), callouts=list(callouts), step=step, card=card, card_pos=card_pos, subtitle=subtitle,
                module=module)

def cam(target, az, el, dist, lens=35, target_end=None, fmt=None):
    """相机围绕 target（选择器或 (x,y,z)）的球坐标。az/el 为度（az=0 在 -Y 正前方，逆时针为正），dist 为米。
       az/el/dist/lens 给 (起, 止) 就在本 shot 内平滑过渡；target_end 让注视点也移动。
       fmt={"9:16": dict(dist=..., lens=..., el=...)}：某个画幅单独改机位（给了 lens 就不再乘 FORMAT_ZOOM）。"""
    return dict(target=target, target_end=target_end, az=az, el=el, dist=dist, lens=lens, fmt=fmt or {})

def move(sel, at, dur, frm=(0, 0, 0), to=(0, 0, 0), out=None, spin=0, stagger=0.0, hl=None, exit=False,
         relative="rest"):
    """把对象从 基准+frm 移到 基准+to。基准默认是静止位置；relative="current" 时是对象当前的动画位置
       （比如先 set_pose("folded") 再整体吊落：drop(UNIT, 0.3, h=3, relative="current")）。
       out=距离：沿对象的 ["out"] 方向偏移（螺栓、墙板用）；spin=绕 ["spin_axis"] 转的圈数；
       stagger=每个对象依次延后的秒数；exit=结束后隐藏。本来不可见的对象在开始时出现。
       hl 默认：装上去的高亮，退场的不高亮。"""
    return dict(kind="move", sel=sel, at=at, dur=dur, frm=frm, to=to, out=out, spin=spin,
                stagger=stagger, hl=(not exit) if hl is None else hl, exit=exit, relative=relative)

def drop(sel, at, dur=1.5, h=1.2, **kw):
    return move(sel, at, dur, frm=(0, 0, h), **kw)

def lift(sel, at, dur=1.5, h=1.2, **kw):
    return move(sel, at, dur, to=(0, 0, h), **kw)

def screw(sel, at, dur=1.0, dist=0.12, turns=3, stagger=0.08, **kw):
    return move(sel, at, dur, out=dist, spin=turns, stagger=stagger, **kw)

def rotate(sel, at, dur, axis="Z", pivot=None, edge=None, frm=0.0, to=90.0, stagger=0.0, hl=None, exit=False):
    """绕世界坐标里的一条轴转动（开门、翻板、铰链）。角度单位为度，从 静止姿态转 frm 度 过渡到 转 to 度。
       pivot：轴经过的点，(x,y,z) 或选择器（取其静止包围盒）；不给就用 sel 自己的包围盒。
       edge："-x" / "+x" / "-y" / "+y" / "-z" / "+z"，取包围盒那一侧的面中心作为轴心（门的铰链边）。
       多个对象一起转时轴心只算一次，所以门扇和把手会作为一个整体转。"""
    return dict(kind="rotate", sel=sel, at=at, dur=dur, axis=axis, pivot=pivot, edge=edge, frm=frm, to=to,
                stagger=stagger, hl=(not exit) if hl is None else hl, exit=exit)

def set_pose(name, at=0.0, sel=None):
    """在 at 秒硬切到 model.py 里用 pose() 登记的姿态（"rest" = 装好后的静止姿态）。
       sel 不给就是登记了该姿态的全部对象。常用在运输 / 吊装镜头开头：set_pose("folded")"""
    return dict(kind="set_pose", name=name, sel=sel, at=at)

def to_pose(name, at, dur, sel=None, stagger=0.0, hl=None):
    """从当前姿态动画过渡到 name（"rest" 或登记的姿态名）。沿登记的转动路径走（和 rotate 同一套算法，
       是弧线不是直线），所以 to_pose("rest", 1, 2, sel="roof_wing_*") 就是"屋顶翼板展开"。
       当前姿态不在这条路径上时（比如被 rotate 转过），退化成位置直线 + 旋转球面插值。hl 默认高亮"""
    return dict(kind="to_pose", name=name, sel=sel, at=at, dur=dur, stagger=stagger, hl=True if hl is None else hl)

def copies(sel, spots, at=0.0, until=None, drop=0.0, dur=1.2, stagger=0.0, name=None):
    """把 sel 整体复制到 spots=[(x,y,z) 偏移, ...]（集合实例，几乎不占渲染时间）：拼箱、叠箱、货包。
       at 秒出现（drop>0 时从上方 drop 米落下，用时 dur），until 秒消失（秒数相对本 shot 开头，可以超出本 shot；
       不给就一直留到片尾）。stagger：每个副本依次延后。"""
    return dict(kind="copies", sel=sel, spots=[tuple(s) for s in spots], at=at, until=until, drop=drop, dur=dur,
                stagger=stagger, name=name)

def grow(sel, at, dur=1.5, stagger=0.0, hl=True):
    """沿对象的 ["grow_axis"] 从 0 长到原长（打胶、走线、画线）。原点要在起点"""
    return dict(kind="grow", sel=sel, at=at, dur=dur, stagger=stagger, hl=hl)

def photo(path, at=0.0, dur=None, zoom=(1.0, 1.08)):
    """全屏照片（用户自己的场景图、实拍图）：贴在相机前，按画幅铺满（多出的部分裁掉），
       zoom=(起, 止) 缓慢推近。只在本 shot 的 [at, at+dur] 可见。路径相对产品目录；文件不存在时跳过并提示。
       常和 shot(card=True, title=...) 一起用：照片打底，卡片写场景名。"""
    return dict(kind="photo", path=path, at=at, dur=dur, zoom=zoom)

def swap(sel, tag, at, hl=0.0):
    """把 sel 换成用 geo.variant() 做好的另一种材质版本（tag），tag=None 换回原样。
       用于"同一箱体 + 不同外墙 / 地板"的定制选项展示。变体跟着原件的静止位置，不跟原件的动画"""
    return dict(kind="swap", sel=sel, tag=tag, at=at, hl=hl)

def appear(sel, at, hl=0.0):
    """直接出现；hl>0 时高亮 hl 秒"""
    return dict(kind="appear", sel=sel, at=at, hl=hl)

def vanish(sel, at):
    return dict(kind="vanish", sel=sel, at=at)

def highlight(sel, at, dur):
    return dict(kind="hl", sel=sel, at=at, dur=dur)

def note(at, dur, zh, en):
    """底部说明字幕"""
    return dict(at=at, dur=dur, zh=zh, en=en)

def callout(sel, at, dur, zh, en, side="right", anchor="center"):
    """指向 sel 的标注。side：标签在锚点的 right / left / up / down；
       anchor：指向包围盒的 center / top / bottom（零件被挡住一部分时用）"""
    return dict(sel=sel, at=at, dur=dur, zh=zh, en=en, side=side, anchor=anchor)


# ---------------- 选择 ----------------
model_objects, resolve = geo.model_objects, geo.resolve        # 实现放在 geo，model.py 里也能用选择器

def pose_after_rotate(loc, rot, axis, pivot, deg):
    """绕经过 pivot 的世界轴 axis 转 deg 度：返回新的 (位置 Vector, 旋转 3×3 矩阵)。rot 是 3×3 矩阵。
       rotate / to_pose / 自定义动画都用这一套，衔接时不会跳"""
    R = Matrix.Rotation(math.radians(deg), 3, axis)
    p = Vector(pivot)
    return p + R @ (Vector(loc) - p), R @ rot

def pose_tf(o, name, f=1.0):
    """对象在姿态 name 下（f=0~1 表示走到一半）的 (位置, 旋转矩阵)；"rest" 或没登记该姿态的对象返回静止姿态"""
    loc, rot = Vector(o["rest"]), Euler(o.get("rest_rot", (0, 0, 0))).to_matrix()
    for op in ([] if name == "rest" else geo.POSES.get(name, {}).get(o.name, [])):
        if op[0] == "rotate":
            loc, rot = pose_after_rotate(loc, rot, op[1], op[2], op[3] * f)
        else:
            loc = loc + Vector(op[1]) * f
    return loc, rot

def rest_matrix(o):
    """静止姿态的世界矩阵（建时间线时记下的位置和旋转），不受动画当前状态影响"""
    if "rest" not in o:
        return o.matrix_world
    return Matrix.LocRotScale(Vector(o["rest"]), Euler(o.get("rest_rot", (0, 0, 0))), o.scale)

def bbox(objs, rest=False):
    pts = [(rest_matrix(o) if rest else o.matrix_world) @ Vector(c) for o in objs for c in o.bound_box]
    return (Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)]))

def bbox_center(objs, anchor="center", rest=False):
    lo, hi = bbox(objs, rest)
    c = (lo + hi) / 2
    if anchor != "center":
        c.z = lo.z + (hi.z - lo.z) * (0.92 if anchor == "top" else 0.08)
    return c

def point(target):
    """坐标原样返回；选择器取静止姿态的包围盒中心（和动画进行到哪无关）"""
    if isinstance(target, (tuple, list)) and len(target) == 3 and all(isinstance(v, (int, float)) for v in target):
        return Vector(target)
    return bbox_center(resolve(target), rest=True)


# ---------------- 关键帧 ----------------
class Ctx:
    """传给自定义函数的上下文（秒数都相对本 shot 开头）：
       ctx.f(秒) 转帧号；ctx.dur 本 shot 时长；ctx.resolve(sel) 取对象；
       ctx.vis(obj, 秒, True/False) 显隐；ctx.key(obj, 秒, loc=, rot=, interp=) 打关键帧；
       ctx.cut(objs, 秒) 在该时刻硬切（上一个关键帧之后保持不动）；ctx.only_in_shot(objs) 只在本 shot 里可见。"""
    def __init__(self, start, timeline, dur=0.0):
        self.start = start
        self.t = timeline
        self.dur = dur
        self.resolve = resolve
    def f(self, sec):
        return self.start + round(sec * FPS)
    def vis(self, ob, sec, on):
        self.t.vis_events.setdefault(ob, []).append((self.f(sec), on))
    def key(self, ob, sec, loc=None, rot=None, interp=None):
        """loc=(x,y,z) 世界坐标；rot=(x,y,z) 弧度；interp="LINEAR" / "CONSTANT" / None（默认缓动）"""
        self.t._ensure_rest(ob)
        fr = self.f(sec)
        if loc is not None:
            ob.location = loc
            ob.keyframe_insert("location", frame=fr)
        if rot is not None:
            ob.rotation_euler = rot
            ob.keyframe_insert("rotation_euler", frame=fr)
        if interp:
            self.t._mark(ob, fr, interp)
    def cut(self, objs, sec=0.0):
        for ob in ([objs] if isinstance(objs, bpy.types.Object) else objs):
            self.t.cuts.append((ob, self.f(sec)))
    def only_in_shot(self, objs, frm=0.0, to=None):
        """模型之外、自定义函数里新建的对象（空物体、实例）只在 [frm, to] 秒可见，片头起默认隐藏"""
        for ob in ([objs] if isinstance(objs, bpy.types.Object) else objs):
            self.t.vis_events.setdefault(ob, []).extend(
                [(1, False), (self.f(frm), True), (self.f(self.dur if to is None else to), False)])


class Timeline:
    def __init__(self, fmt="16:9", zoom=None, base_dir=""):
        self.fmt = fmt
        self.zoom = {**FORMAT_ZOOM, **(zoom or {})}.get(fmt, 1.0)
        self.base_dir = base_dir           # photo() 相对路径的起点（产品目录）
        self.vis_events = {}       # obj -> [(frame, visible)]
        self.interp = {}           # obj -> {frame: "CONSTANT"/"LINEAR"}：CONSTANT 表示该关键帧之后保持不动
        self.cuts = []             # [(obj, frame)]：该帧之前最后一个关键帧改成 CONSTANT（硬切）
        self.shots = []            # [(shot dict, start frame, end frame)]
        self.warnings = []
        self.n_copies = 0
        self.cur = {}              # obj -> 当前姿态 dict(pose=(姿态名, 进度)|None, loc, rot, eul)，给 relative / to_pose 用

    def _mark(self, o, frame, mode):
        self.interp.setdefault(o, {})[frame] = mode

    def _cur(self, o):
        if o not in self.cur:
            e = Euler(o.get("rest_rot", (0, 0, 0)))
            self.cur[o] = dict(pose=None, loc=Vector(o["rest"]), rot=e.to_matrix(), eul=e)
        return self.cur[o]

    def _key_tf(self, o, fr, loc, rot, prev=None):
        """打一帧位置 + 旋转（rot 为 3×3 矩阵），欧拉角接着 prev 走，避免 ±180° 跳变"""
        eul = rot.to_euler("XYZ", prev) if prev is not None else rot.to_euler("XYZ")
        o.location, o.rotation_euler = loc, eul
        o.keyframe_insert("location", frame=fr)
        o.keyframe_insert("rotation_euler", frame=fr)
        return eul

    def _ensure_rest(self, o):
        """第一次打关键帧之前，先在第 1 帧记下静止姿态并保持，免得片头沿用后面某个关键帧的值"""
        if "rest" not in o:
            return
        paths = {fc.data_path for fc in fcurves(o)}
        for path, val in (("location", o["rest"]), ("rotation_euler", o.get("rest_rot", (0, 0, 0)))):
            if path not in paths:
                cur = tuple(getattr(o, path))
                setattr(o, path, val)
                o.keyframe_insert(path, frame=1)
                setattr(o, path, cur)
        self._mark(o, 1, "CONSTANT")

    def build(self, shots):
        objs = model_objects()
        for ob in scene_camera():
            ob.animation_data_clear()
        bpy.data.objects["CAM"].data.animation_data_clear()
        for ob in [o for o in bpy.data.objects if o.get("copies") or o.get("photo")]:      # 上次建的副本、照片
            bpy.data.objects.remove(ob, do_unlink=True)
        for c in [c for c in bpy.data.collections if c.name.startswith("COPIES_")]:
            bpy.data.collections.remove(c)
        for o in objs:
            o["rest"] = list(o.location)
            o["rest_rot"] = list(o.rotation_euler)
            o["hl"] = 0.0
            o.animation_data_clear()
        state = set()
        frame = 1
        for s in shots:
            start, end = frame, frame + round(s["dur"] * FPS)
            ctx = Ctx(start, self, s["dur"])
            ctx.moved = set()
            if s["show"] is not None:
                state = set(resolve(s["show"]))
            tmp_hidden = set(resolve(s["hide"])) if s["hide"] else set()
            for o in objs:
                self.vis_events.setdefault(o, []).append((start, o in state and o not in tmp_hidden))
            photos = []
            for a in s["do"]:
                if callable(a):
                    a(ctx)
                    continue
                if a["kind"] == "copies":
                    self._copies(ctx, a)
                    continue
                if a["kind"] == "photo":           # 要用到本 shot 的镜头参数，等相机设好再做
                    photos.append(a)
                    continue
                if a["kind"] == "swap":
                    self._swap(ctx, a, state)
                    continue
                if a["kind"] in ("set_pose", "to_pose") and a["sel"] is None:
                    targets = self._pose_targets(a["name"])
                else:
                    targets = resolve(a["sel"])
                pivot = self._pivot(a, targets) if a["kind"] == "rotate" else None
                for i, o in enumerate(targets):
                    at = a["at"] + i * a.get("stagger", 0.0)
                    entering = o not in state and o not in tmp_hidden   # hide 优先于入场
                    if a["kind"] == "set_pose":
                        self._set_pose(ctx, o, a["name"], at)
                    elif a["kind"] in ("move", "rotate", "to_pose"):
                        if a["kind"] == "move":
                            self._move(ctx, o, a, at)
                        elif a["kind"] == "rotate":
                            self._rotate(ctx, o, a, at, pivot)
                        else:
                            self._to_pose(ctx, o, a, at)
                        if entering:
                            ctx.vis(o, at, True)
                        if a.get("exit"):
                            ctx.vis(o, at + a["dur"], False)
                        if a["hl"]:
                            self._hl(ctx, o, at, a["dur"])
                    elif a["kind"] == "grow":
                        idx = "XYZ".index(o["grow_axis"])
                        for sec, v in ((at, 0.001), (at + a["dur"], 1.0)):
                            o.scale[idx] = v
                            o.keyframe_insert("scale", index=idx, frame=ctx.f(sec))
                        o.scale[idx] = 1.0
                        if entering:
                            ctx.vis(o, at, True)
                        if a["hl"]:
                            self._hl(ctx, o, at, a["dur"])
                    elif a["kind"] == "appear":
                        ctx.vis(o, at, True)
                        if a["hl"]:
                            self._hl(ctx, o, at, a["hl"])
                    elif a["kind"] == "vanish":
                        ctx.vis(o, at, False)
                    elif a["kind"] == "hl":
                        self._hl(ctx, o, at, a["dur"])
                for o in targets:
                    if a["kind"] == "set_pose":            # 只改姿态，不改显隐
                        continue
                    if a["kind"] == "vanish" or a.get("exit"):
                        state.discard(o)
                    else:
                        state.add(o)
            self._camera(ctx, s, start, end)
            for a in photos:
                self._photo(ctx, a)
            self.shots.append((s, start, end))
            frame = end
        self._write_vis()
        paths = ("location", "rotation_euler", "scale")
        for o, marks in self.interp.items():
            for fc in fcurves(o):
                if fc.data_path in paths:
                    for k in fc.keyframe_points:
                        if round(k.co.x) in marks:
                            k.interpolation = marks[round(k.co.x)]
        for o, fr in self.cuts:
            for fc in fcurves(o):
                if fc.data_path in paths:
                    prev = [k for k in fc.keyframe_points if k.co.x < fr - 0.5]
                    if prev:
                        max(prev, key=lambda k: k.co.x).interpolation = "CONSTANT"
        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = frame - 1
        return self

    def _pose_targets(self, name):
        if name == "rest":                          # 回到静止：所有当前不在静止姿态的对象
            return [o for o, c in self.cur.items() if c["pose"]]
        if name not in geo.POSES:
            raise ValueError(f"姿态 {name!r} 没有登记，model.py 里用 pose({name!r}, 选择器, rotate=..., move=...) 登记。"
                             f"已有：{sorted(geo.POSES)}")
        return resolve(list(geo.POSES[name]))

    def _set_pose(self, ctx, o, name, at):
        """硬切到姿态：该帧打关键帧并保持，之前的关键帧到这里截断"""
        self._ensure_rest(o)
        fr = ctx.f(at)
        loc, rot = pose_tf(o, name)
        eul = self._key_tf(o, fr, loc, rot, self._cur(o)["eul"])
        self._mark(o, fr, "CONSTANT")
        self.cuts.append((o, fr))
        self.cur[o] = dict(pose=None if name == "rest" else (name, 1.0), loc=loc, rot=rot, eul=eul)
        o.location, o.rotation_euler = Vector(o["rest"]), Euler(o.get("rest_rot", (0, 0, 0)))

    def _to_pose(self, ctx, o, a, at):
        """沿登记的转动路径过渡；路径对不上时退化为直线 + 球面插值。相对路径的平移偏移（如还吊在空中）保留"""
        name, c = a["name"], self._cur(o)
        if c["pose"]:
            pn, fs = c["pose"]
            fe = 0.0 if name == "rest" else (1.0 if name == pn else None)
        else:
            pn, fs, fe = name, 0.0, (None if name == "rest" else 1.0)
            rest_rot = pose_tf(o, "rest")[1]
            if max(abs(c["rot"][i][j] - rest_rot[i][j]) for i in range(3) for j in range(3)) > 1e-4:
                fe = None                                   # 被 rotate 转过，不在路径上
        if fe is not None:
            off = c["loc"] - pose_tf(o, pn, fs)[0]
            def tf(e):
                loc, rot = pose_tf(o, pn, fs + (fe - fs) * e)
                return loc + off, rot
        else:
            t_loc, t_rot = pose_tf(o, name)
            q0, q1 = c["rot"].to_quaternion(), t_rot.to_quaternion()
            tf = lambda e: (c["loc"].lerp(t_loc, e), q0.slerp(q1, e).to_matrix())
        f0, f1 = ctx.f(at), ctx.f(at + a["dur"])
        self._ensure_rest(o)
        frames = list(range(f0, f1, 2)) + [f1]
        if o not in ctx.moved and f0 > ctx.start:
            frames.insert(0, ctx.start)
            self._mark(o, ctx.start, "CONSTANT")
        ctx.moved.add(o)
        eul = c["eul"]
        for fr in frames:
            u = 0.0 if fr <= f0 else (fr - f0) / max(1, f1 - f0)
            loc, rot = tf(u * u * (3 - 2 * u))
            eul = self._key_tf(o, fr, loc, rot, eul)
            if fr >= f0:
                self._mark(o, fr, "LINEAR")
        self._mark(o, f1, "CONSTANT")
        self.cur[o] = dict(pose=None if name == "rest" else (name, 1.0), loc=loc, rot=rot, eul=eul)
        o.location, o.rotation_euler = Vector(o["rest"]), Euler(o.get("rest_rot", (0, 0, 0)))

    def _move(self, ctx, o, a, at):
        c = self._cur(o)
        rest = c["loc"].copy() if a.get("relative") == "current" else Vector(o["rest"])
        frm, to = Vector(a["frm"]), Vector(a["to"])
        if a["out"]:
            frm = frm + Vector(o["out"]) * a["out"]
        f0, f1 = ctx.f(at), ctx.f(at + a["dur"])
        keys = [(f0, frm), (f1, to)]
        self._ensure_rest(o)
        if o not in ctx.moved and f0 > ctx.start:     # 本 shot 第一次动：从 shot 开头就摆在起始位置
            keys.insert(0, (ctx.start, frm))
            self._mark(o, ctx.start, "CONSTANT")
        ctx.moved.add(o)
        self._mark(o, f1, "CONSTANT")
        for fr, off in keys:
            o.location = rest + off
            o.keyframe_insert("location", frame=fr)
        c["loc"] = rest + to
        if a.get("relative") != "current":
            c["pose"] = None
        if a["spin"]:
            idx = "XYZ".index(o["spin_axis"])
            for fr, ang in ((f0, a["spin"] * 2 * math.pi), (f1, 0.0)):
                o.rotation_euler[idx] = ang
                o.keyframe_insert("rotation_euler", index=idx, frame=fr)
        o.location = Vector(o["rest"])

    def _pivot(self, a, targets):
        pv = a["pivot"]
        if pv is not None and not isinstance(pv, str) and all(isinstance(v, (int, float)) for v in pv):
            return Vector(pv)                                   # 直接给坐标
        lo, hi = bbox(resolve(pv) if pv is not None else targets, rest=True)
        p = (lo + hi) / 2
        if a["edge"]:                                           # 取包围盒某一侧的面中心
            i = "xyz".index(a["edge"][1])
            p[i] = lo[i] if a["edge"][0] == "-" else hi[i]
        return p

    def _rotate(self, ctx, o, a, at, pivot):
        """绕 pivot 转动：逐 2 帧打位置 + 旋转关键帧（线性），结束后保持"""
        L0, E0 = Vector(o["rest"]), Euler(o.get("rest_rot", (0, 0, 0)))
        f0, f1 = ctx.f(at), ctx.f(at + a["dur"])
        self._ensure_rest(o)
        frames = list(range(f0, f1, 2)) + [f1]
        if o not in ctx.moved and f0 > ctx.start:
            frames.insert(0, ctx.start)
        ctx.moved.add(o)
        prev = None
        for fr in frames:
            u = 0.0 if fr <= f0 else (fr - f0) / max(1, f1 - f0)
            e = u * u * (3 - 2 * u)
            loc, rot = pose_after_rotate(L0, E0.to_matrix(), a["axis"], pivot, a["frm"] + (a["to"] - a["frm"]) * e)
            prev = self._key_tf(o, fr, loc, rot, prev)
            self._mark(o, fr, "LINEAR")
        if frames[0] < f0:
            self._mark(o, frames[0], "CONSTANT")
        self._mark(o, f1, "CONSTANT")
        self.cur[o] = dict(pose=None, loc=loc, rot=rot, eul=prev)
        o.location, o.rotation_euler = L0, E0

    def _copies(self, ctx, a):
        """集合实例：每个副本一个空物体，片头起隐藏，at 出现，until 消失"""
        self.n_copies += 1
        name = a["name"] or f"copies{self.n_copies}"
        unit = bpy.data.collections.new("COPIES_" + name)      # 不链接进场景，只给实例引用
        for o in resolve(a["sel"]):
            unit.objects.link(o)
        for k, spot in enumerate(a["spots"]):
            e = bpy.data.objects.new(f"{name}_{k}", None)
            bpy.context.scene.collection.objects.link(e)
            e["copies"] = True
            e.instance_type, e.instance_collection = "COLLECTION", unit
            at = a["at"] + k * a["stagger"]
            for sec, dz in (((at, a["drop"]), (at + a["dur"], 0.0)) if a["drop"] else ((at, 0.0),)):
                e.location = Vector(spot) + Vector((0, 0, dz))
                e.keyframe_insert("location", frame=ctx.f(sec))
            self._mark(e, ctx.f(at + (a["dur"] if a["drop"] else 0)), "CONSTANT")
            ev = [(1, False), (ctx.f(at), True)]
            if a["until"] is not None:
                ev.append((ctx.f(a["until"]), False))
            self.vis_events.setdefault(e, []).extend(ev)

    def _swap(self, ctx, a, state):
        """原件和它的各个材质变体之间切换显隐：只显示 tag 指定的那一个"""
        objs = model_objects()
        for base in [o for o in resolve(a["sel"]) if not o.get("variant_of")]:
            group = [base] + [o for o in objs if o.get("variant_of") == base.name]
            want = base if a["tag"] is None else next((o for o in group if o.get("variant") == a["tag"]), None)
            if want is None:
                raise ValueError(f"{base.name} 没有材质变体 {a['tag']!r}，先在 shots.py 的 prepare() 里用 geo.variant() 建")
            for o in group:
                ctx.vis(o, a["at"], o is want)
                (state.add if o is want else state.discard)(o)
            if a["hl"]:
                self._hl(ctx, want, a["at"], a["hl"])

    def _photo(self, ctx, a):
        """相机前贴一张铺满画面的照片（自发光，不受灯光影响），只在本 shot 里可见"""
        import os
        path = a["path"] if os.path.isabs(a["path"]) else os.path.join(self.base_dir, a["path"])
        if not os.path.exists(path):
            self.warnings.append(f"照片不存在，已跳过：{path}")
            return
        cam, _ = scene_camera()
        img = bpy.data.images.load(path, check_existing=True)
        sc = bpy.context.scene
        d = 1.0
        fr = cam.data.view_frame(scene=sc)                      # 相机画框四角（相机坐标，z<0），按比例换算到距离 d
        k = d / abs(fr[0].z)
        fw = (max(v.x for v in fr) - min(v.x for v in fr)) * k * 1.01   # 多 1% 防止边缘露缝
        fh = (max(v.y for v in fr) - min(v.y for v in fr)) * k * 1.01
        u0, v0, u1, v1 = _content_box(path)                     # 去掉宣传图常见的白边 / 纯色边
        ia = img.size[0] * (u1 - u0) / max(1, img.size[1] * (v1 - v0))
        pw = max(fw, fh * ia)                                   # cover：铺满画面，多出的部分裁掉
        ph = pw / ia
        me = bpy.data.meshes.new("photo")
        me.from_pydata([(-pw / 2, -ph / 2, 0), (pw / 2, -ph / 2, 0), (pw / 2, ph / 2, 0), (-pw / 2, ph / 2, 0)], [], [(0, 1, 2, 3)])
        uv = me.uv_layers.new()
        for li, (u, v) in zip(range(4), ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
            uv.data[li].uv = (u, v)
        ob = bpy.data.objects.new(f"photo_{os.path.splitext(os.path.basename(path))[0]}", me)
        sc.collection.objects.link(ob)
        ob["photo"] = True
        ob.parent = cam
        ob.location = (0, 0, -d)
        m = bpy.data.materials.new("photo_" + os.path.basename(path))
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        tex, em, out = nt.nodes.new("ShaderNodeTexImage"), nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeOutputMaterial")
        tex.image = img
        em.inputs["Strength"].default_value = 1.25              # 色调映射会把照片压暗一点，补回来
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        me.materials.append(m)
        t0 = a["at"]
        t1 = ctx.dur if a["dur"] is None else a["at"] + a["dur"]
        z0, z1 = a["zoom"]
        for sec, z in ((t0, z0), (t1, z1)):
            ob.scale = (z, z, 1)
            ob.keyframe_insert("scale", frame=ctx.f(sec))
        self._mark(ob, ctx.f(t0), "LINEAR")
        ctx.only_in_shot(ob, t0, t1)

    def _hl(self, ctx, o, at, dur):
        """高亮最晚在本 shot 结束时淡完，不拖进下一个镜头"""
        end = ctx.dur
        if at + dur > end + 1e-6:
            self.warnings.append(f"高亮超出 shot 结尾，已截断：{o.name}（{at:.1f}+{dur:.1f}s > {end:.1f}s）")
        t_end = min(at + dur + HL_OUT, end)
        t_hold = max(at, min(at + dur, t_end - 0.1))
        for sec, v in ((at - HL_IN, 0.0), (at, 1.0), (t_hold, 1.0), (t_end, 0.0)):
            o["hl"] = v
            o.keyframe_insert('["hl"]', frame=max(1, ctx.f(sec)))
        o["hl"] = 0.0

    def _write_vis(self):
        for o, ev in self.vis_events.items():
            ev.sort(key=lambda e: e[0])
            last = None
            for fr, on in ev:
                if on == last:
                    continue
                o.hide_render = o.hide_viewport = not on
                o.keyframe_insert("hide_render", frame=fr)
                o.keyframe_insert("hide_viewport", frame=fr)
                last = on
            for fc in fcurves(o):
                if fc.data_path.startswith("hide"):
                    for k in fc.keyframe_points:
                        k.interpolation = "CONSTANT"

    def _camera(self, ctx, s, start, end):
        c = s["cam"]
        if c is None:
            return
        cam, tgt = scene_camera()
        over = c.get("fmt", {}).get(self.fmt, {})
        c = {**c, **over}
        pair = lambda v: tuple(v) if isinstance(v, (tuple, list)) else (v, v)
        p0 = point(c["target"])
        p1 = point(c["target_end"]) if c["target_end"] is not None else p0
        az, el, di, ln = (pair(c[k]) for k in ("az", "el", "dist", "lens"))
        if "lens" not in over:                  # 非 16:9 画幅按 FORMAT_ZOOM 推近
            ln = tuple(v * self.zoom for v in ln)
        n = max(1, (end - 1 - start) // 6)
        for k in range(n + 1):
            u = k / n
            e = u * u * (3 - 2 * u)             # smoothstep
            lerp = lambda ab: ab[0] + (ab[1] - ab[0]) * e
            p = p0.lerp(p1, e)
            a, b, d = math.radians(lerp(az)), math.radians(lerp(el)), lerp(di)
            fr = start + round(u * (end - 1 - start))
            tgt.location = p
            cam.location = p + Vector((math.sin(a) * math.cos(b), -math.cos(a) * math.cos(b), math.sin(b))) * d
            cam.data.lens = lerp(ln)
            tgt.keyframe_insert("location", frame=fr)
            cam.keyframe_insert("location", frame=fr)
            cam.data.keyframe_insert("lens", frame=fr)
        for ob in (cam, tgt, cam.data):
            for fc in fcurves(ob):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"


def _content_box(path, tol=12):
    """照片四周和角上颜色一致的边（白边、黑边）裁掉，返回 UV 范围 (u0, v0, u1, v1)。读不了就不裁"""
    try:
        from PIL import Image, ImageChops
        im = Image.open(path).convert("RGB")
        bg = Image.new("RGB", im.size, im.getpixel((0, 0)))
        box = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > tol else 0).getbbox()
    except Exception:
        return 0.0, 0.0, 1.0, 1.0
    if not box:
        return 0.0, 0.0, 1.0, 1.0
    w, h = im.size
    x0, y0, x1, y1 = box
    return x0 / w, 1 - y1 / h, x1 / w, 1 - y0 / h             # 图片 y 向下，UV 的 v 向上


def fcurves(idb):
    """兼容 Blender 4.4+ 的分层 action"""
    ad = idb.animation_data
    if not ad or not ad.action:
        return []
    from bpy_extras.anim_utils import action_get_channelbag_for_slot
    bag = action_get_channelbag_for_slot(ad.action, ad.action_slot)
    return list(bag.fcurves) if bag else []

def scene_camera():
    cam = bpy.data.objects.get("CAM")
    if cam is None:
        cam = bpy.data.objects.new("CAM", bpy.data.cameras.new("CAM"))
        bpy.context.scene.collection.objects.link(cam)
        tgt = bpy.data.objects.new("CAM_TGT", None)
        bpy.context.scene.collection.objects.link(tgt)
        con = cam.constraints.new("TRACK_TO")
        con.target = tgt
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"
        cam.data.clip_start = 0.02
        cam.data.clip_end = 200
    bpy.data.objects["CAM"].data.sensor_fit = "HORIZONTAL"     # 各画幅水平视野一致，竖屏只是上下多出空间
    bpy.context.scene.camera = cam
    return cam, bpy.data.objects["CAM_TGT"]
