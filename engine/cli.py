"""统一入口，运行在 Blender 自带的 Python 里，除 Blender 外不依赖任何软件。
通过 video.cmd（Windows）或 video.sh（macOS / Linux）调用：

  video setup                                   首次使用：装依赖到 .deps/，检查字体，再渲染一个示例镜头自检
  video init <工作目录>/<产品名> [示例名]         从示例复制出一个新产品（默认示例 kpx2）
  video make <产品目录> [draft|preview|final] [shot前缀,...]   渲染 → 字幕层 → 合成 MP4 → 自查拼图
  video compose <产品目录>                      只重做字幕层和合成（改了字幕或音乐，不用重新渲染）
  video text <产品目录>                         列出每一屏同时出现的文字、英文单词数、宽度（写到 out/text.md）
  加 -v（或环境变量 VIDEO_VERBOSE=1）显示 Blender 的完整输出；默认只显示摘要，完整日志在 out/log.txt
  video frames <视频文件> [间隔秒数]             参考视频抽帧并生成总览图
  video sheet <图片目录>                        照片总览图（带文件名），方便逐张看
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
        pr = subprocess.Popen(blender_cmd() + ["make", demo, "draft", "05a"], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in pr.stdout:
            log.append(line.rstrip())
        if pr.wait() or not os.path.exists(os.path.join(demo, "out", "draft_05a.mp4")) \
                or not os.path.exists(os.path.join(demo, "out", "review", "05a_post.jpg")):
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

def render_argv(args):
    p = product_dir(args[0])
    quality = args[1] if len(args) > 1 else "preview"
    from engine import scene
    if quality not in scene.QUALITY:
        raise SystemExit(f"质量档位只能是 {list(scene.QUALITY)}")
    argv = [p, "--quality", quality, "--step", "1" if quality == "final" else "2"]
    if len(args) > 2 and args[2]:
        argv += ["--shots", args[2]]
    return p, argv

def cmd_make(args):
    """主进程导出时间线、清空帧目录，再开 N 个 Blender 进程一起渲染，最后在新进程里合成"""
    ensure_deps()
    import shutil
    from engine import run
    from engine.log import say
    loud, args = verbose(args)
    p, argv = render_argv(args)
    t = time.time()
    run.main(argv + ["--no-render"])
    frames = os.path.join(p, "out", "frames")
    shutil.rmtree(frames, ignore_errors=True)
    os.makedirs(frames)
    log = os.path.join(p, "out", "log.txt")
    open(log, "w").close()
    n = workers()
    out_to = None if loud else open(log, "a", encoding="utf-8")
    procs = [subprocess.Popen(blender_cmd() + ["worker", f"{i}/{n}", *args], stdout=out_to, stderr=subprocess.STDOUT)
             for i in range(n)]
    failed = [pr.wait() for pr in procs]
    if out_to:
        out_to.close()
    if any(failed):
        if not loud:
            print("".join(deque(open(log, encoding="utf-8", errors="replace"), maxlen=30)))
        raise SystemExit(f"渲染进程出错，完整日志：{log}")
    say(f"render: {time.time() - t:.0f}s with {n} workers")
    # 合成放到干净的新进程：本进程已搭过 3D 场景，残留状态会让截帧变黑
    run_logged(blender_cmd() + ["compose", p], log, loud)
    say(f"完整日志：{log}")

def cmd_worker(args):
    """args: <第几个/共几个> <产品> <质量> [shots]"""
    ensure_deps()
    from engine import run
    _, argv = render_argv(args[1:])
    run.main(argv + ["--part", args[0]])


def cmd_text(args):
    ensure_deps()
    from engine import run, overlay
    p = product_dir(args[0])
    run.main([p, "--no-render", "--quality", "draft"])
    overlay.text_report(os.path.join(p, "out"))


def cmd_compose(args):
    args = verbose(args)[1]
    p = product_dir(args[0])
    ensure_deps()
    from engine import overlay, compose
    out = os.path.join(p, "out")
    overlay.main(out)
    compose.compose(out, p)


def cmd_init(args):
    import shutil
    dst = os.path.abspath(args[0])
    src = os.path.join(ROOT, "examples", args[1] if len(args) > 1 else "kpx2")
    if not os.path.basename(dst).isidentifier():
        raise SystemExit("产品目录名只能用字母、数字、下划线，且不以数字开头，例如 house_a")
    if os.path.exists(dst):
        raise SystemExit(f"{dst} 已存在")
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("out", "__pycache__", "storyboard.md"))
    with open(os.path.join(dst, "storyboard.md"), "w", encoding="utf-8") as fh:   # 分镜从空白开始，示例的留在 skill 里参考
        fh.write("# 分镜 v1\n\n- 时长：\n- 画幅：\n- 字幕语言：\n\n"
                 "| # | 段落 | 时长 | 画面 | 字幕 |\n|---|---|---|---|---|\n\n## 需要确认\n")
    print(f"created {dst}：改写 model.py / shots.py / storyboard.md，然后 video make {dst} draft")

def cmd_frames(args):
    ensure_deps()
    from engine import tools
    tools.frames(os.path.abspath(args[0]), float(args[1]) if len(args) > 1 else 2.0)


def cmd_pdf(args):
    ensure_deps()
    from engine import tools
    tools.pdf(os.path.abspath(args[0]))


def cmd_sheet(args):
    ensure_deps()
    from engine import tools
    tools.sheet(os.path.abspath(args[0]))


def main(argv):
    cmds = {"setup": cmd_setup, "init": cmd_init, "make": cmd_make, "compose": cmd_compose, "frames": cmd_frames, "sheet": cmd_sheet, "pdf": cmd_pdf,
            "worker": cmd_worker, "text": cmd_text}
    if not argv or argv[0] not in cmds:
        print(__doc__)
        sys.exit(1)
    cmds[argv[0]](argv[1:])


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
