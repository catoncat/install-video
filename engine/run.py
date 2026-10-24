"""Blender 里的渲染入口：建模 → 布置场景 → 分镜生成动画 → 导出 timeline.json → 渲染帧。
一般由 cli.py 调用。产品目录（任意位置）里要有 model.py（提供 build()）和 shots.py（提供 SHOTS），
目录名要是合法的 Python 标识符（如 kpx2）。输出写到 <产品目录>/out/<画幅>/（如 out/16x9/）。

在已打开的 Blender 里（MCP）只搭场景、不渲染：
  p = "<skill>/engine/run.py"; g = {"__file__": p, "__name__": "mcp"}
  exec(open(p).read(), g); g["main"](["<产品目录>", "--no-render"])
"""
import sys, os, json, shutil, argparse, importlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(product):
    """加载 engine 和产品模块；每次都重新加载，方便反复修改后再运行"""
    product = os.path.abspath(product)
    for p in (ROOT, os.path.dirname(product)):
        if p not in sys.path:
            sys.path.insert(0, p)
    pkg = os.path.basename(product)
    if not pkg.isidentifier():
        raise ValueError(f"产品目录名 {pkg!r} 必须是合法的 Python 标识符（字母、数字、下划线，不以数字开头）")
    mods = ["engine.geo", "engine.anim", "engine.scene", f"{pkg}.model", f"{pkg}.shots"]
    for name in [n for n in sys.modules if n == pkg or n.startswith(pkg + ".")]:
        del sys.modules[name]          # 同名产品可能在别的目录，产品模块每次都从指定路径重新导入
    sys.path.remove(os.path.dirname(product))
    sys.path.insert(0, os.path.dirname(product))
    for name in mods:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)
    return [sys.modules[n] for n in mods]


def formats(shots):
    """产品要出的画幅，默认国际站营销三种"""
    return list(getattr(shots, "FORMATS", ["16:9", "1:1", "9:16"]))

def out_dir(product, fmt):
    from engine.scene import tag
    return os.path.join(os.path.abspath(product), "out", tag(fmt))

def versions(shots):
    """VERSIONS = {"60s": None, "30s": [shot 前缀...], "15s": dict(shots=[...], target=(12, 18))} 统一成
       {名: {"shots": [...] 或 None（全片）, "target": (最短, 最长) 或 None}}"""
    out = {}
    for k, v in getattr(shots, "VERSIONS", {}).items():
        v = v if isinstance(v, dict) else dict(shots=v)
        out[k] = dict(shots=v.get("shots"), target=v.get("target"))
    return out


# 卡片在画面里大致占的区域（归一化，y 向下）：x 范围, {位置: y 范围}
CARD_BANDS = {"top": (0.05, 0.30), "center": (0.38, 0.62), "bottom": (0.60, 0.87)}

def subject_box(frames):
    """这几帧里可见主体（模型 + 复制品）在画面上的包围框（归一化，y 向下），看不到就返回 None"""
    import bpy
    from mathutils import Vector
    from bpy_extras.object_utils import world_to_camera_view
    from engine.anim import model_objects
    sc, cam = bpy.context.scene, bpy.context.scene.camera
    xs, ys = [], []
    for fr in frames:
        sc.frame_set(fr)
        ok = lambda o: o.type == "MESH" and not o.hide_render and not o.get("bg") and "ground" not in o.get("stage", "")
        objs = [(o, o.matrix_world) for o in model_objects() if ok(o)]
        for e in [o for o in sc.objects if o.get("copies") and not o.hide_render and o.instance_collection]:
            objs += [(o, e.matrix_world @ o.matrix_world) for o in e.instance_collection.objects if ok(o)]
        for o, mw in objs:
            for c in o.bound_box:
                p = world_to_camera_view(sc, cam, mw @ Vector(c))
                if p.z > 0:
                    xs.append(min(max(p.x, 0), 1))
                    ys.append(min(max(1 - p.y, 0), 1))
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None

def card_overlap(box, pos, fmt):
    """主体伸进卡片区域（上下各多留 3% 余量）的深度占卡片区域高度的比例；左右不相交就是 0"""
    half = 0.42 if fmt == "9:16" else 0.33
    y0, y1 = CARD_BANDS[pos][0] - 0.03, CARD_BANDS[pos][1] + 0.03
    if min(0.5 + half, box[2]) <= max(0.5 - half, box[0]):
        return 0.0
    return max(0.0, min(y1, box[3]) - max(y0, box[1])) / (y1 - y0)

def reframe(start, end, box, pos):
    """让主体避开卡片：先把相机沿视线拉远到主体放得下，再把相机和注视点一起平移，主体移出卡片区域"""
    import bpy, math
    from mathutils import Vector
    from engine.anim import fcurves
    sc = bpy.context.scene
    cam, tgt = sc.camera, bpy.data.objects["CAM_TGT"]
    lo, hi = (0.05, CARD_BANDS["bottom"][0] - 0.06) if pos == "bottom" else (CARD_BANDS["top"][1] + 0.06, 0.95)
    k = max(1.0, (box[3] - box[1]) / (hi - lo))             # 主体太高就拉远 k 倍（画面里约缩小到 1/k）
    y0, y1 = 0.5 + (box[1] - 0.5) / k, 0.5 + (box[3] - 0.5) / k
    dy = (y1 - hi) if pos == "bottom" else (y0 - lo)          # 需要把主体在画面里上移（>0）/ 下移（<0）多少
    frames = sorted({round(kp.co.x) for fc in fcurves(cam) if fc.data_path == "location"
                     for kp in fc.keyframe_points if start <= kp.co.x < end})
    rw, rh = sc.render.resolution_x, sc.render.resolution_y
    moved = []
    for fr in frames:
        sc.frame_set(fr)
        c, t = cam.matrix_world.translation.copy(), tgt.matrix_world.translation.copy()
        fwd = (t - c).normalized()
        right = fwd.cross(Vector((0, 0, 1))).normalized()
        up = right.cross(fwd)
        d = (t - c).length * k
        half_h = d * math.tan(cam.data.angle_x / 2) * rh / rw          # 注视点处画面半高（米）
        shift = -up * dy * 2 * half_h                                 # 主体上移 = 相机和注视点下移
        moved.append((fr, t - fwd * d + shift, t + shift))
    for fr, c, t in moved:
        cam.location, tgt.location = c, t
        cam.keyframe_insert("location", frame=fr)
        tgt.keyframe_insert("location", frame=fr)

def place_card(tl, s, start, end):
    """card_pos="auto"：选主体遮挡最少的位置（优先底部，再顶部）；还挡着就调机位让开；仍超过 10% 才警告"""
    pos = s.get("card_pos", "auto")
    if any(isinstance(a, dict) and a.get("kind") == "photo" for a in s["do"]):     # 照片铺满画面，不用避让
        return "bottom" if pos == "auto" else pos
    frames = [start, (start + end) // 2, end - 1]
    box = subject_box(frames)
    if box is None:
        return "bottom" if pos == "auto" else pos
    auto = pos == "auto"
    if auto:
        pos = min(("bottom", "top"), key=lambda p: (round(card_overlap(box, p, tl.fmt), 2), p != "bottom"))
        if card_overlap(box, pos, tl.fmt) > 0.10:
            reframe(start, end, box, pos)
            box = subject_box(frames)
    ov = card_overlap(box, pos, tl.fmt)
    if ov > 0.10:
        tl.warnings.append(f"{s['id']}：卡片（{pos}）和主体重叠 {ov:.0%}。把 cam 的注视点往卡片那一侧挪、或拉远，"
                           f"或换 card_pos")
    return pos


def place_cards(tl):
    """所有进程（含并行渲染进程）建完时间线后都要跑：决定卡片位置，必要时改机位关键帧"""
    for s, start, end in tl.shots:
        if s["title"] and s["card"]:
            s["_card_pos"] = place_card(tl, s, start, end)


def export_timeline(tl, path, extra):
    """把字幕、标注和标注锚点的屏幕坐标写成 JSON，给 overlay / compose 用"""
    import bpy
    from bpy_extras.object_utils import world_to_camera_view
    from engine.anim import FPS, resolve, bbox_center
    sc, cam = bpy.context.scene, bpy.context.scene.camera
    items = []
    for s, start, end in tl.shots:
        f = lambda sec: start + round(sec * FPS)
        if s["title"]:
            items.append(dict(type="card" if s["card"] else "step", frames=[start, end - 1], step=s["step"],
                              zh=s["title"][0], en=s["title"][1],
                              pos=s.get("_card_pos"),
                              sub=list(s["subtitle"]) if s.get("subtitle") else None, shot=s["id"]))
        for n in s["notes"]:
            items.append(dict(type="note", frames=[f(n["at"]), min(end - 1, f(n["at"] + n["dur"]))], zh=n["zh"], en=n["en"],
                              shot=s["id"]))
        for c in s["callouts"]:
            a, b = f(c["at"]), min(end - 1, f(c["at"] + c["dur"]))
            objs = resolve(c["sel"])
            track = {}
            for fr in range(a, b + 1):
                sc.frame_set(fr)
                p = world_to_camera_view(sc, cam, bbox_center(objs, c.get("anchor", "center")))
                track[fr] = [round(p.x, 4), round(1 - p.y, 4), p.z > 0]
            items.append(dict(type="callout", frames=[a, b], zh=c["zh"], en=c["en"], side=c["side"], track=track,
                              shot=s["id"]))
    data = dict(fps=FPS, frame_end=tl.frame_end, items=items,
                shots=[dict(id=s["id"], start=a, end=b - 1, module=s.get("module")) for s, a, b in tl.shots], **extra)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("product")
    ap.add_argument("--quality", default="preview")
    ap.add_argument("--shots", default="", help="只渲染这些 shot（id 前缀，逗号分隔）")
    ap.add_argument("--step", type=int, default=1, help="每隔几帧渲染一帧（预览用 2）")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--part", default="", help="并行渲染时本进程负责的份额 i/n：只渲每 n 帧里的第 i 帧，不清空帧目录")
    ap.add_argument("--format", default="", help="画幅 16:9 / 1:1 / 9:16，默认取 shots.FORMATS 的第一个")
    args = ap.parse_args(argv)

    import bpy
    geo, anim, scene, model, shots = load(args.product)
    fmt = args.format or formats(shots)[0]
    geo.reset()
    model.build()
    if hasattr(shots, "prepare"):          # 模型建好后的额外准备：材质变体等
        shots.prepare()
    scene.setup(args.quality, getattr(shots, "STYLE", None), fmt)
    tl = anim.Timeline(fmt, getattr(shots, "FORMAT_ZOOM", None), os.path.abspath(args.product)).build(shots.SHOTS)
    tl.frame_end = bpy.context.scene.frame_end
    place_cards(tl)

    out = out_dir(args.product, fmt)
    os.makedirs(out, exist_ok=True)
    if not args.part:
        name = f"{args.quality}_{scene.tag(fmt)}" + ("_" + args.shots.replace(",", "_") if args.shots else "")
        export_timeline(tl, os.path.join(out, "timeline.json"),
                        dict(music=getattr(shots, "MUSIC", {}), size=scene.output_size(args.quality, fmt),
                             design=scene.design(fmt), format=fmt, quality=args.quality, shots_arg=args.shots,
                             lang=getattr(shots, "LANG", "en"), text=getattr(shots, "TEXT", {}),
                             max_words=getattr(shots, "MAX_WORDS", 8), versions=versions(shots),
                             module_max=getattr(shots, "MODULE_MAX", {"options": 0.2}), name=name))
    sc = bpy.context.scene
    ranges = [(sc.frame_start, sc.frame_end)]
    if args.shots:   # 只渲选中的 shot，不连带中间的
        want = args.shots.split(",")
        ranges = [(a, b - 1) for s, a, b in tl.shots if any(s["id"].startswith(w) for w in want)]
        if not ranges:
            raise ValueError(f"--shots {args.shots} 没匹配到任何 shot：{[s['id'] for s, _, _ in tl.shots]}")
    sc.frame_step = args.step
    if not args.part:
        from engine.log import say
        say(f"timeline: {', '.join(f'{a}-{b}' for a, b in ranges)} ({sum(b - a + 1 for a, b in ranges) / anim.FPS:.1f}s)")
        for w in dict.fromkeys(tl.warnings):
            say("警告：" + w)
    if args.no_render:
        return tl
    frames = os.path.join(out, "frames")
    # 并行时按帧号确定性分工（第 i 个进程渲 a+i*step, a+(i+n)*step ...），不靠占位文件，不会两个进程写同一帧
    i, n = (int(x) for x in args.part.split("/")) if args.part else (0, 1)
    if not args.part:
        shutil.rmtree(frames, ignore_errors=True)
    sc.render.filepath = os.path.join(frames, "f_")
    sc.frame_step = args.step * n
    for a, b in ranges:
        if a + i * args.step > b:
            continue
        sc.frame_start, sc.frame_end = a + i * args.step, b
        bpy.ops.render.render(animation=True)
    return tl


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
