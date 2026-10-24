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
                              zh=s["title"][0], en=s["title"][1], pos=s.get("card_pos", "bottom"),
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
