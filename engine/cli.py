"""统一入口，运行在 Blender 自带的 Python 里，除 Blender 外不依赖任何软件。
通过 video.cmd（Windows）或 video.sh（macOS / Linux）调用：

  video setup                                   首次使用：装依赖到 .deps/，检查字体，再渲染一个示例镜头自检
  video init <工作目录>/<产品名> [kpx2]          新建产品：默认是国际站营销视频模板；加 kpx2 复制中英说明版示例
  video make <产品目录> [preview|final] [shot前缀,...] [--version ad] [--format 9:16|all]
                                                渲染 → 字幕层 → 合成 MP4 → 自查拼图。按用途出片（VERSIONS 写了
                                                format）时每个版本单独渲染，输出到 out/<版本>/；--version 只做一个。
                                                preview：960p，自查和给用户看；final：1080p 成片，用户点头后再出。
                                                老写法（FORMATS）：preview 只出第一个画幅，final 出全部
  video compose <产品目录> [--format ...]        只重做字幕和合成（改了字幕、版本或音乐，不用重新渲染）
  video text <产品目录>                         列出每一屏同时出现的文字、英文单词数、宽度（写到 out/<画幅>/text.md）
  加 -v（或环境变量 VIDEO_VERBOSE=1）显示 Blender 的完整输出；默认只显示摘要，完整日志在 out/log.txt
  video frames <视频文件> [间隔秒数]             参考视频抽帧并生成总览图
  video sheet <图片目录>                        照片总览图（带文件名），方便逐张看
  video check <产品目录> [帧号...]              穿模检查：动起来的零件和别的零件有没有相交
  video swatch [产品目录]                       材料库（和产品材质）在标准灯光下的色卡，挑饰面用
  video pdf <PDF 文件>                          PDF 转成每页图片 + 内嵌原图 + 全文文字，再拼一张总览图
"""
import sys, os, subprocess, time
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPS = os.path.join(ROOT, ".deps")
PKGS = {"PIL": "pillow==12.3.0", "pypdfium2": "pypdfium2==5.13.0"}   # 锁定版本，各平台都有现成的 wheel


def ensure_deps():
    """Pillow、pypdfium2 装到 <skill>/.deps/，不需要管理员权限，不碰系统 Python"""
    import importlib
    for p in (DEPS, ROOT):
        if p not in sys.path:
            sys.path.insert(0, p)
    missing = []
    for mod, pkg in PKGS.items():
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(pkg)
    if not missing:
        return
    print(f"installing {' '.join(missing)} into .deps/ ...")
    py = sys.executable
    if subprocess.run([py, "-m", "pip", "--version"], capture_output=True).returncode != 0:
        subprocess.run([py, "-m", "ensurepip", "--user"], check=True)
    subprocess.run([py, "-m", "pip", "install", "--disable-pip-version-check", "--no-warn-script-location",
                    "--target", DEPS, *missing], check=True)
    importlib.invalidate_caches()
    for mod in PKGS:
        importlib.import_module(mod)


def product_dir(arg):
    p = os.path.abspath(arg)
    if not os.path.isdir(p) and os.path.isdir(os.path.join(ROOT, "examples", arg)):
        p = os.path.join(ROOT, "examples", arg)
    for f in ("model.py", "shots.py"):
        if not os.path.exists(os.path.join(p, f)):
            raise SystemExit(f"{p} 里没有 {f}。产品目录要包含 model.py 和 shots.py，可以复制 {ROOT}/examples/kpx2 作为起点")
    return p


def cmd_setup(_):
    """装依赖、查字体和版本，再用示例渲染一个镜头、合成、截图自查，全部通过才打印 SETUP OK"""
    import shutil, tempfile
    try:
        ensure_deps()
        import bpy
        from engine import overlay
        for k, (path, idx) in overlay.FONTS.items():
            print(f"font {k}: {path} [{idx}]")
        if bpy.app.version < (4, 4, 0):
            raise RuntimeError(f"Blender {bpy.app.version_string} 太旧，需要 4.4 以上")
        print(f"blender {bpy.app.version_string} | python {sys.version.split()[0]}")
        print("自检：用示例渲染一个镜头（约半分钟）...", flush=True)
        tmp = tempfile.mkdtemp(prefix="video_selftest_")
        demo = os.path.join(tmp, "kpx2")
        shutil.copytree(os.path.join(ROOT, "examples", "kpx2"), demo, ignore=shutil.ignore_patterns("out", "__pycache__"))
        log = deque(maxlen=30)
        pr = subprocess.Popen(blender_cmd() + ["make", demo, "preview", "05a"], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in pr.stdout:
            log.append(line.rstrip())
        if pr.wait() or not os.path.exists(os.path.join(demo, "out", "16x9", "preview_16x9_05a.mp4")) \
                or not os.path.exists(os.path.join(demo, "out", "16x9", "review", "05a_post.jpg")):
            raise RuntimeError("示例渲染自检失败，最后的输出：\n" + "\n".join(log))
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception as e:
        print(f"SETUP FAILED: {e}", flush=True)
        os._exit(1)            # 直接退出，让这一行就是最后一行（Blender 正常退出还会再打印两行）
    print("SETUP OK", flush=True)
    os._exit(0)


def blender_cmd():
    """以后台模式再起一个 Blender 跑本文件的命令前缀"""
    import bpy
    return [bpy.app.binary_path, "-b", "--factory-startup", "--python-exit-code", "1", "-P", os.path.abspath(__file__), "--"]


def verbose(args):
    """-v 或 VIDEO_VERBOSE=1：显示完整输出。返回 (是否详细, 去掉 -v 的参数)"""
    return ("-v" in args or os.environ.get("VIDEO_VERBOSE") == "1"), [a for a in args if a != "-v"]


def run_logged(cmd, log, loud):
    """跑子进程：完整输出追加到 log；终端只显示 say() 打印的摘要行（loud 时全部显示）。失败时打印最后 30 行"""
    from engine.log import PREFIX
    tail = deque(maxlen=30)
    with open(log, "a", encoding="utf-8") as fh:
        pr = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                              errors="replace")
        for line in pr.stdout:
            fh.write(line)
            tail.append(line.rstrip())
            if loud or line.startswith(PREFIX):
                print(line, end="", flush=True)
    if pr.wait():
        if not loud:
            print("\n".join(tail))
        raise SystemExit(f"出错了，完整日志：{log}")


def workers():
    """并行进程数：环境变量 VIDEO_WORKERS，默认 CPU 核数 / 4，限制在 1~3。
       每个进程都要占一份显存；EEVEE 每帧主要吃 GPU，多开进程只是把每帧的 CPU 开销（存图、合成、场景求值）
       叠起来，开太多反而抢显存。保守默认，机器好的自己调高"""
    return int(os.environ.get("VIDEO_WORKERS", max(1, min(3, (os.cpu_count() or 4) // 4))))

def opt(args, flag):
    """取出 --flag 值，返回 (值或 None, 其余参数)"""
    if flag in args:
        i = args.index(flag)
        return args[i + 1], args[:i] + args[i + 2:]
    return None, args

def render_argv(args):
    p = product_dir(args[0])
    quality = args[1] if len(args) > 1 else "preview"
    from engine import scene
    if quality in scene.QUALITY_ALIAS:
        print(f"» 提示：{quality} 档已取消，按 {scene.QUALITY_ALIAS[quality]} 出（只有 preview 和 final 两档）", flush=True)
        quality = scene.QUALITY_ALIAS[quality]
    if quality not in scene.QUALITY:
        raise SystemExit(f"质量档位只能是 {list(scene.QUALITY)}")
    argv = [p, "--quality", quality, "--step", "1"]      # 逐帧 30fps，隔帧会让运动一卡一卡
    if len(args) > 2 and args[2]:
        argv += ["--shots", args[2]]
    return p, argv

def pick_formats(p, quality, want):
    """--format all / 某个画幅；不给时 final 出全部，preview 只出第一个"""
    from engine import run
    shots = run.load(p)[-1]
    fs = run.formats(shots)
    if want == "all":
        return fs
    if want:
        return [want]
    return fs if quality == "final" else fs[:1]

def jobs(p, want_fmt, want_ver):
    """要渲染的片子：[(画幅, 版本名或 None)]。按用途出片时每个版本一条（相同画幅 + 相同镜头序列的只渲一次）"""
    from engine import run
    shots = run.load(p)[-1]
    uses = run.use_versions(shots)
    if not uses:
        return None
    names = [want_ver] if want_ver else list(uses)
    out, seen = [], {}
    for n in names:
        if n not in uses:
            raise SystemExit(f"没有版本 {n!r}，VERSIONS 里有：{list(uses)}")
        key = (uses[n]["format"], tuple(s["id"] for s in run.version_shots(shots, n, uses[n])))
        if key in seen:
            print(f"» 版本 {n} 和 {seen[key]} 画幅、镜头完全一样，只渲一次（拷贝 {seen[key]} 的成片）")
            out.append((uses[n]["format"], n, seen[key]))
            continue
        seen[key] = n
        out.append((uses[n]["format"], n, None))
    return out

def cmd_make(args):
    """每条片子（画幅，或按用途的版本）：主进程导出时间线、清空帧目录，开 N 个 Blender 进程一起渲染，
       最后在新进程里合成"""
    ensure_deps()
    import shutil
    from engine import run
    from engine.log import say
    loud, args = verbose(args)
    want, args = opt(args, "--format")
    ver, args = opt(args, "--version")
    p, argv = render_argv(args)
    todo = jobs(p, want, ver) or [(f, None, None) for f in pick_formats(p, argv[2], want)]
    for k, (fmt, vname, same_as) in enumerate(todo):
        vflag = ["--version", vname] if vname else []
        if same_as:
            src = run.out_dir(p, fmt, same_as)
            dst = run.out_dir(p, fmt, vname)
            os.makedirs(dst, exist_ok=True)
            for f in os.listdir(src):
                if f.endswith(".mp4"):
                    shutil.copy(os.path.join(src, f), os.path.join(dst, f.replace(same_as, vname)))
            continue
        t = time.time()
        tl = run.main(argv + ["--no-render", "--format", fmt] + vflag)
        if k == 0:                       # 共面重叠（Z-fighting）会让画面逐帧闪烁，渲染前先查
            from engine import tools
            want_ids = argv[argv.index("--shots") + 1].split(",") if "--shots" in argv else None
            mids = [(a + b) // 2 for s, a, b in tl.shots if not want_ids or any(s["id"].startswith(w) for w in want_ids)]
            zf = tools.zfight(mids)
            tools.report_zfight(zf, say)
            if zf and argv[2] == "final" and "--force" not in sys.argv:
                raise SystemExit("成片档不渲染有共面重叠的模型（会闪烁）。先按上面的列表把面错开，或者确认可以接受后加 --force")
        out = run.out_dir(p, fmt, vname)
        frames = os.path.join(out, "frames")
        shutil.rmtree(frames, ignore_errors=True)
        os.makedirs(frames)
        log = os.path.join(out, "log.txt")
        open(log, "w").close()
        n = workers()
        out_to = None if loud else open(log, "a", encoding="utf-8")
        procs = [subprocess.Popen(blender_cmd() + ["worker", f"{i}/{n}", *args, "--format", fmt] + vflag, stdout=out_to,
                                  stderr=subprocess.STDOUT) for i in range(n)]
        failed = [pr.wait() for pr in procs]
        if out_to:
            out_to.close()
        if any(failed):
            if not loud:
                print("".join(deque(open(log, encoding="utf-8", errors="replace"), maxlen=30)))
            raise SystemExit(f"渲染进程出错，完整日志：{log}")
        say(f"render {vname or fmt}: {time.time() - t:.0f}s with {n} workers")
        # 合成放到干净的新进程：本进程已搭过 3D 场景，残留状态会让截帧变黑
        run_logged(blender_cmd() + ["_compose", out, p], log, loud)
        say(f"完整日志：{log}")

def cmd_worker(args):
    """args: <第几个/共几个> <产品> <质量> [shots] --format <画幅>"""
    ensure_deps()
    from engine import run
    fmt, args = opt(args, "--format")
    ver, args = opt(args, "--version")
    _, argv = render_argv(args[1:])
    run.main(argv + ["--part", args[0], "--format", fmt] + (["--version", ver] if ver else []))


def cmd_text(args):
    ensure_deps()
    from engine import run, overlay
    want, args = opt(args, "--format")
    ver, args = opt(args, "--version")
    p = product_dir(args[0])
    uses = run.use_versions(run.load(p)[-1])
    for vname in ([ver] if ver else list(uses)) if uses else [None]:
        fmt = uses[vname]["format"] if uses else (want or run.formats(run.load(p)[-1])[0])
        run.main([p, "--no-render", "--quality", "preview", "--format", fmt] + (["--version", vname] if vname else []))
        overlay.text_report(run.out_dir(p, fmt, vname))


def cmd_compose(args):
    """改了字幕 / 版本 / 音乐后重新合成：先按上次的档位重新导出时间线（新进程），再合成（再一个新进程）"""
    ensure_deps()
    import glob, json
    loud, args = verbose(args)
    want, args = opt(args, "--format")
    p = product_dir(args[0])
    from engine.scene import tag
    outs = [os.path.join(p, "out", tag(want))] if want else sorted(os.path.dirname(f) for f in
                                                                   glob.glob(os.path.join(p, "out", "*", "timeline.json")))
    if not outs:
        raise SystemExit("还没有渲染过，先运行 video make")
    for out in outs:
        tl = json.load(open(os.path.join(out, "timeline.json"), encoding="utf-8"))
        log = os.path.join(out, "log.txt")
        run_logged(blender_cmd() + ["_export", p, tl["quality"], tl.get("shots_arg", ""), "--format", tl["format"]]
                   + (["--version", tl["version"]] if tl.get("version") else []), log, loud)
        run_logged(blender_cmd() + ["_compose", out, p], log, loud)

def cmd_export(args):
    """内部：只重新导出时间线（字幕、标注位置），不渲染"""
    ensure_deps()
    from engine import run
    fmt, args = opt(args, "--format")
    ver, args = opt(args, "--version")
    _, argv = render_argv(args)
    run.main(argv + ["--no-render", "--format", fmt] + (["--version", ver] if ver else []))

def cmd_compose_only(args):
    """内部：字幕层 + 合成 + 版本 + 自查，在干净进程里跑。args: <out 目录> <产品目录>"""
    ensure_deps()
    from engine import overlay, compose
    out, p = args
    overlay.main(out)
    overlay.text_report(out)
    compose.compose(out, p)


def cmd_init(args):
    """默认：国际站营销模板（示例模型 + 营销分镜骨架）；第二个参数给示例名（如 kpx2）则原样复制该示例"""
    import shutil
    dst = os.path.abspath(args[0])
    if not os.path.basename(dst).isidentifier():
        raise SystemExit("产品目录名只能用字母、数字、下划线，且不以数字开头，例如 house_a")
    if os.path.exists(dst):
        raise SystemExit(f"{dst} 已存在")
    if len(args) > 1:
        shutil.copytree(os.path.join(ROOT, "examples", args[1]), dst, ignore=shutil.ignore_patterns("out", "__pycache__"))
    else:
        tpl = os.path.join(ROOT, "engine", "templates", "marketing")
        os.makedirs(dst)
        for f in ("__init__.py", "model.py"):        # 模型先用示例的，跑通后换成自己的产品
            shutil.copy(os.path.join(ROOT, "examples", "kpx2", f), dst)
        for f in os.listdir(tpl):
            shutil.copy(os.path.join(tpl, f), dst)
    print(f"created {dst}：改写 model.py / shots.py / storyboard.md，然后 video make {dst} preview")

def cmd_frames(args):
    ensure_deps()
    from engine import tools
    tools.frames(os.path.abspath(args[0]), float(args[1]) if len(args) > 1 else 2.0)


def cmd_pdf(args):
    ensure_deps()
    from engine import tools
    tools.pdf(os.path.abspath(args[0]))


def cmd_swatch(args):
    ensure_deps()
    from engine import tools
    tools.swatch(product_dir(args[0]) if args else None)


def cmd_check(args):
    """video check <产品> [帧号...]"""
    ensure_deps()
    from engine import tools
    hits = tools.check(product_dir(args[0]), [int(a) for a in args[1:]] or None)
    from engine import anim
    sc = __import__("bpy").context.scene
    tools.report_zfight(tools.zfight(list(range(sc.frame_start, sc.frame_end + 1, 15))), limit=100)
    return hits


def cmd_sheet(args):
    ensure_deps()
    from engine import tools
    tools.sheet(os.path.abspath(args[0]))


def main(argv):
    cmds = {"setup": cmd_setup, "init": cmd_init, "make": cmd_make, "compose": cmd_compose, "frames": cmd_frames, "sheet": cmd_sheet, "pdf": cmd_pdf, "swatch": cmd_swatch, "check": cmd_check,
            "worker": cmd_worker, "text": cmd_text, "_export": cmd_export, "_compose": cmd_compose_only}
    if not argv or argv[0] not in cmds:
        print(__doc__)
        sys.exit(1)
    cmds[argv[0]](argv[1:])


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
