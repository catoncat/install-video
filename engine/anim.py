"""分镜 -> 关键帧。

分镜是一个 list，每项由 shot() 生成（就是普通 dict，也可以手写）。
时间单位都是秒，相对于所在 shot 的开头。选择器 sel 可以是：
  "post_*"（对象名通配）、"@04_posts"（整个 stage）、或它们组成的 list。
不够用时，在 do 里放一个普通函数 fn(ctx)，引擎会在该 shot 里调用它（见 Ctx）。
"""
import bpy, math, fnmatch, difflib
from mathutils import Vector
from . import geo

FPS = 30
HL_IN, HL_OUT = 0.2, 0.5          # 高亮淡入 / 淡出秒数


# ---------------- 分镜数据构造（只是返回 dict，方便书写） ----------------
def shot(id, dur, title=None, cam=None, do=(), show=None, hide=(), notes=(), callouts=(), step=None, card=False):
    """title=(中, 英)；show=该 shot 开头可见的选择器（不给则沿用上一个 shot 结束时的状态）；
       hide=只在本 shot 内临时隐藏；step=左上角步骤编号；card=True 时标题居中大字显示（片头片尾）。
       cam=None 时沿用上一个 shot 结束时的机位。"""
    return dict(id=id, dur=dur, title=title, cam=cam, do=list(do), show=show, hide=list(hide),
                notes=list(notes), callouts=list(callouts), step=step, card=card)

def cam(target, az, el, dist, lens=35, target_end=None):
    """相机围绕 target（选择器或 (x,y,z)）的球坐标。az/el 为度（az=0 在 -Y 正前方，逆时针为正），dist 为米。
       az/el/dist/lens 给 (起, 止) 就在本 shot 内平滑过渡；target_end 让注视点也移动。"""
    return dict(target=target, target_end=target_end, az=az, el=el, dist=dist, lens=lens)

def move(sel, at, dur, frm=(0, 0, 0), to=(0, 0, 0), out=None, spin=0, stagger=0.0, hl=None, exit=False):
    """把对象从 静止位置+frm 移到 静止位置+to。
       out=距离：沿对象的 ["out"] 方向偏移（螺栓、墙板用）；spin=绕 ["spin_axis"] 转的圈数；
       stagger=每个对象依次延后的秒数；exit=结束后隐藏。本来不可见的对象在开始时出现。
       hl 默认：装上去的高亮，退场的不高亮。"""
    return dict(kind="move", sel=sel, at=at, dur=dur, frm=frm, to=to, out=out, spin=spin,
                stagger=stagger, hl=(not exit) if hl is None else hl, exit=exit)

def drop(sel, at, dur=1.5, h=1.2, **kw):
    return move(sel, at, dur, frm=(0, 0, h), **kw)

def lift(sel, at, dur=1.5, h=1.2, **kw):
    return move(sel, at, dur, to=(0, 0, h), **kw)

def screw(sel, at, dur=1.0, dist=0.12, turns=3, stagger=0.08, **kw):
    return move(sel, at, dur, out=dist, spin=turns, stagger=stagger, **kw)

def grow(sel, at, dur=1.5, stagger=0.0, hl=True):
    """沿对象的 ["grow_axis"] 从 0 长到原长（打胶、走线、画线）。原点要在起点"""
    return dict(kind="grow", sel=sel, at=at, dur=dur, stagger=stagger, hl=hl)

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
def model_objects():
    root = bpy.data.collections[geo.ROOT]
    return [o for c in [root, *root.children_recursive] for o in c.objects]

def resolve(sel, allow_empty=False):
    sels = [sel] if isinstance(sel, str) else list(sel)
    objs = model_objects()
    out = []
    for s in sels:
        hit = ([o for o in objs if o.get("stage") == s[1:]] if s.startswith("@")
               else [o for o in objs if fnmatch.fnmatchcase(o.name, s)])
        if not hit and not allow_empty:
            pool = sorted({"@" + o["stage"] for o in objs}) if s.startswith("@") else [o.name for o in objs]
            near = difflib.get_close_matches(s, pool, n=5, cutoff=0.4)
            raise ValueError(f"选择器 {s!r} 没有匹配任何对象。相近的有：{near}")
        out += [o for o in hit if o not in out]
    return out

def bbox_center(objs, anchor="center"):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    c = (lo + hi) / 2
    if anchor != "center":
        c.z = lo.z + (hi.z - lo.z) * (0.92 if anchor == "top" else 0.08)
    return c

def point(target):
    if isinstance(target, (tuple, list)) and len(target) == 3 and all(isinstance(v, (int, float)) for v in target):
        return Vector(target)
    return bbox_center(resolve(target))


# ---------------- 关键帧 ----------------
class Ctx:
    """传给自定义函数的上下文：ctx.f(秒) 转帧号；ctx.resolve(sel)；ctx.vis(obj, 秒, True/False)"""
    def __init__(self, start, timeline):
        self.start = start
        self.t = timeline
        self.resolve = resolve
    def f(self, sec):
        return self.start + round(sec * FPS)
    def vis(self, ob, sec, on):
        self.t.vis_events.setdefault(ob, []).append((self.f(sec), on))


class Timeline:
    def __init__(self):
        self.vis_events = {}       # obj -> [(frame, visible)]
        self.hold = {}             # obj -> {frame}：这些关键帧之后保持不动，直到下一次 move
        self.shots = []            # [(shot dict, start frame, end frame)]

    def build(self, shots):
        objs = model_objects()
        for ob in scene_camera():
            ob.animation_data_clear()
        bpy.data.objects["CAM"].data.animation_data_clear()
        for o in objs:
            o["rest"] = list(o.location)
            o["hl"] = 0.0
            o.animation_data_clear()
        state = set()
        frame = 1
        for s in shots:
            start, end = frame, frame + round(s["dur"] * FPS)
            ctx = Ctx(start, self)
            ctx.moved = set()
            if s["show"] is not None:
                state = set(resolve(s["show"]))
            tmp_hidden = set(resolve(s["hide"])) if s["hide"] else set()
            for o in objs:
                self.vis_events.setdefault(o, []).append((start, o in state and o not in tmp_hidden))
            for a in s["do"]:
                if callable(a):
                    a(ctx)
                    continue
                targets = resolve(a["sel"])
                for i, o in enumerate(targets):
                    at = a["at"] + i * a.get("stagger", 0.0)
                    entering = o not in state and o not in tmp_hidden   # hide 优先于入场
                    if a["kind"] == "move":
                        self._move(ctx, o, a, at)
                        if entering:
                            ctx.vis(o, at, True)
                        if a["exit"]:
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
                    if a["kind"] == "vanish" or a.get("exit"):
                        state.discard(o)
                    else:
                        state.add(o)
            self._camera(ctx, s, start, end)
            self.shots.append((s, start, end))
            frame = end
        self._write_vis()
        for o, frames in self.hold.items():
            for fc in fcurves(o):
                if fc.data_path in ("location", "rotation_euler"):
                    for k in fc.keyframe_points:
                        if round(k.co.x) in frames:
                            k.interpolation = "CONSTANT"
        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = frame - 1
        return self

    def _move(self, ctx, o, a, at):
        rest = Vector(o["rest"])
        frm, to = Vector(a["frm"]), Vector(a["to"])
        if a["out"]:
            frm = frm + Vector(o["out"]) * a["out"]
        f0, f1 = ctx.f(at), ctx.f(at + a["dur"])
        keys = [(f0, frm), (f1, to)]
        hold = self.hold.setdefault(o, set())
        if not any(fc.data_path == "location" for fc in fcurves(o)):   # 第一次动之前停在静止位置
            o.location = rest
            o.keyframe_insert("location", frame=1)
            hold.add(1)
        if o not in ctx.moved and f0 > ctx.start:     # 本 shot 第一次动：从 shot 开头就摆在起始位置
            keys.insert(0, (ctx.start, frm))
            hold.add(ctx.start)
        ctx.moved.add(o)
        hold.add(f1)
        for fr, off in keys:
            o.location = rest + off
            o.keyframe_insert("location", frame=fr)
        if a["spin"]:
            idx = "XYZ".index(o["spin_axis"])
            for fr, ang in ((f0, a["spin"] * 2 * math.pi), (f1, 0.0)):
                o.rotation_euler[idx] = ang
                o.keyframe_insert("rotation_euler", index=idx, frame=fr)
        o.location = rest

    def _hl(self, ctx, o, at, dur):
        for sec, v in ((at - HL_IN, 0.0), (at, 1.0), (at + dur, 1.0), (at + dur + HL_OUT, 0.0)):
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
        pair = lambda v: tuple(v) if isinstance(v, (tuple, list)) else (v, v)
        p0 = point(c["target"])
        p1 = point(c["target_end"]) if c["target_end"] is not None else p0
        az, el, di, ln = (pair(c[k]) for k in ("az", "el", "dist", "lens"))
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
    bpy.context.scene.camera = cam
    return cam, bpy.data.objects["CAM_TGT"]
