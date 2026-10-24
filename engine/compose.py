"""合成（在 Blender 里运行，不需要 ffmpeg）：渲染帧 + 字幕层 + 音乐 → out/video.mp4，
再按 shot 生成关键帧拼图 out/review/<shot>.jpg，供 agent 自查。

音乐：产品目录下有 music.*（mp3/wav/m4a/ogg）就用它，没有就用 music.py 程序合成。
"""
import os, glob, json
import bpy
from PIL import Image, ImageDraw
from . import music, overlay


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
    video = os.path.join(out, "video.mp4")
    if os.path.exists(video):
        os.remove(video)
    r.filepath = video
    r.use_file_extension = False
    bpy.ops.render.render(animation=True, scene=sc.name)
    print(f"video: {video}  ({dur:.1f}s @ {fps}fps, music: {os.path.basename(track)})")
    review(out, tl, video, nums)


def review(out, tl, video, nums, per=6, tw=640):
    """从成片 video.mp4 里按 shot 各截 per 帧，拼成 3 列：out/review/<shot>.jpg。
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
    print(f"review: {rdir}")
