"""合成（在 Blender 里运行，不需要 ffmpeg）：渲染帧 + 字幕层 + 音乐 → out/<档位>[_<shots>].mp4，
再按 shot 生成关键帧拼图 out/review/<shot>.jpg，供 agent 自查。

音乐：产品目录下有 music.*（mp3/wav/m4a/ogg）就用它，没有就用 music.py 程序合成。
"""
import os, glob, json
import bpy
from PIL import Image, ImageDraw, ImageChops, ImageStat
from . import music, overlay
from .log import say


def compose(out, product_dir):
    tl = json.load(open(os.path.join(out, "timeline.json"), encoding="utf-8"))
    files = sorted(glob.glob(os.path.join(out, "frames", "f_*.png")))
    if not files:
        raise RuntimeError(f"{out}/frames 里没有渲染好的帧")
    nums = [int(os.path.basename(f)[2:-4]) for f in files]
    step = nums[1] - nums[0] if len(nums) > 1 else 1
    fps = round(tl["fps"] / step)
    dur = len(files) / fps

    track = next(iter(sorted(glob.glob(os.path.join(product_dir, "music.*")))), None)
    if track is None:
        track = music.generate(os.path.join(out, "music.wav"), dur + 0.5, **tl.get("music", {}))

    w, h = tl["size"]
    sc = bpy.data.scenes.get("COMPOSE") or bpy.data.scenes.new("COMPOSE")
    r = sc.render
    # 必须先设输出尺寸再加素材：FIT 按"加素材那一刻"的场景尺寸算缩放，顺序反了超采样帧会被裁成放大的中间一块
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    sc.sequence_editor_create()
    strips = sc.sequence_editor.strips if hasattr(sc.sequence_editor, "strips") else sc.sequence_editor.sequences
    for s in list(strips):
        strips.remove(s)

    def seq(name, folder, channel):
        st = strips.new_image(name, os.path.join(out, folder, os.path.basename(files[0])), channel, 1, fit_method="FIT")
        for f in files[1:]:
            st.elements.append(os.path.basename(f))
        if hasattr(st, "transform") and "BOX" in [i.identifier for i in st.transform.bl_rna.properties["filter"].enum_items]:
            st.transform.filter = "BOX"      # 超采样大图缩小用盒式滤波
        return st
    seq("frames", "frames", 1)
    ov = seq("overlay", "overlay", 2)
    ov.blend_type = "ALPHA_OVER"
    snd = strips.new_sound("music", track, 3, 1)
    last = len(files)
    for fr, v in ((1, 0.0), (int(fps * 0.8), 1.0), (max(2, last - int(fps * 2.5)), 1.0), (last, 0.0)):
        snd.volume = v
        snd.keyframe_insert("volume", frame=fr)

    r.fps, r.fps_base = fps, 1
    sc.frame_start, sc.frame_end = 1, last
    r.use_sequencer = True
    if hasattr(r.image_settings, "media_type"):
        r.image_settings.media_type = "VIDEO"
    r.image_settings.file_format = "FFMPEG"
    ff = r.ffmpeg
    ff.format, ff.codec = "MPEG4", "H264"
    ff.constant_rate_factor, ff.ffmpeg_preset = "HIGH", "GOOD"
    ff.audio_codec, ff.audio_bitrate, ff.audio_channels, ff.audio_mixrate = "AAC", 192, "STEREO", 44100
    video = os.path.join(out, tl.get("name", "video") + ".mp4")     # 按档位和 shot 命名，小样不会覆盖全片
    if os.path.exists(video):
        os.remove(video)
    r.filepath = video
    r.use_file_extension = False
    bpy.ops.render.render(animation=True, scene=sc.name)
    check(video, (w, h), last, fps)
    say(f"video: {video}  ({w}x{h}, {dur:.1f}s @ {fps}fps, music: {os.path.basename(track)})")
    review(out, tl, video, nums)


def check(video, size, frames, fps):
    """成片核对：尺寸、帧数、帧率必须和时间线一致，否则报错，不留废片"""
    clip = bpy.data.movieclips.load(video)
    got = (tuple(clip.size), clip.frame_duration, round(clip.fps))
    bpy.data.movieclips.remove(clip)
    want = (tuple(size), frames, fps)
    if got[0] != want[0] or abs(got[1] - want[1]) > 1 or got[2] != want[2]:
        os.replace(video, video[:-4] + ".bad.mp4")
        raise RuntimeError(f"成片不符合预期：得到 尺寸{got[0]} 帧数{got[1]} 帧率{got[2]}，应为 尺寸{want[0]} 帧数{want[1]} 帧率{want[2]}。"
                           f"已改名为 {os.path.basename(video)[:-4]}.bad.mp4")


def review(out, tl, video, nums, per=6, tw=640):
    """从成片里按 shot 各截 per 帧，拼成 3 列：out/review/<shot>.jpg。
       截的是最终视频，所以合成、缩放、字幕层的问题都能在这里看到。"""
    from . import tools
    rdir = os.path.join(out, "review")
    os.makedirs(rdir, exist_ok=True)
    for f in glob.glob(os.path.join(rdir, "*.jpg")):
        os.remove(f)
    lab = overlay.font("en_b", 18)
    index = {n: k + 1 for k, n in enumerate(nums)}       # 时间线帧号 -> 视频第几帧
    picks = {}
    for s in tl["shots"]:
        have = [n for n in nums if s["start"] <= n <= s["end"]]
        if have:
            picks[s["id"]] = (s, [have[round(i * (len(have) - 1) / max(1, per - 1))] for i in range(min(per, len(have)))])
    grabbed, _ = tools.grab(video, sorted({index[n] for _, ns in picks.values() for n in ns}), os.path.join(rdir, "_tmp"))
    problems = self_check(tl, picks, {n: grabbed[index[n]] for _, ns in picks.values() for n in ns})
    for sid, (s, ns) in picks.items():
        tiles = []
        for n in ns:
            im = Image.open(grabbed[index[n]]).convert("RGB")
            im.thumbnail((tw, tw))
            ImageDraw.Draw(im).text((8, im.size[1] - 26), f"{sid}  f{n}  {(n - s['start']) / tl['fps']:.1f}s",
                                    fill=(255, 0, 80), font=lab)
            tiles.append(im)
        tw2, th = tiles[0].size
        sheet = Image.new("RGB", (tw2 * 3, th * ((len(tiles) + 2) // 3)), "black")
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % 3) * tw2, (i // 3) * th))
        sheet.save(os.path.join(rdir, f"{sid}.jpg"), quality=85)
    import shutil
    shutil.rmtree(os.path.join(rdir, "_tmp"), ignore_errors=True)
    say(f"review: {rdir}")
    if problems:
        raise RuntimeError("自查没通过（review 图已生成，可以打开看）：\n  " + "\n  ".join(problems))


def self_check(tl, picks, paths):
    """自查截图本身靠不靠得住：截到纯色（全黑 / 全白）的帧算错；整条视频截到的帧完全一样算错
       （截帧或合成坏了）；单个 shot 的几帧完全一样只提醒（可能是静止镜头）"""
    small = {n: Image.open(p).convert("L").resize((96, 54)) for n, p in paths.items()}
    same = lambda a, b: ImageStat.Stat(ImageChops.difference(small[a], small[b])).mean[0] < 0.6
    problems = []
    blank = [sid for sid, (_, ns) in picks.items() if any(ImageStat.Stat(small[n]).stddev[0] < 2.0 for n in ns)]
    if blank:
        problems.append(f"这些 shot 截到了纯色帧（全黑或全白）：{', '.join(blank)}")
    ns = sorted(small)
    if len(ns) > 2 and all(same(ns[0], n) for n in ns[1:]):
        problems.append("整条视频截到的帧全都一样，截帧或合成出了问题")
    else:
        for sid, (s, sn) in picks.items():
            if (s["end"] - s["start"]) / tl["fps"] > 1.0 and len(sn) > 2 and all(same(sn[0], n) for n in sn[1:]):
                say(f"提醒：{sid} 的几张截图完全一样，如果这个镜头本该有动作，请检查")
    return problems
