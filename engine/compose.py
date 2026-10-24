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

    r = sc.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
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
    review(out, tl, dict(zip(nums, files)))


def review(out, tl, frames, per=6, tw=640):
    """每个 shot 抽 per 帧，叠上字幕层，拼成 3 列：out/review/<shot>.jpg"""
    rdir = os.path.join(out, "review")
    os.makedirs(rdir, exist_ok=True)
    for f in glob.glob(os.path.join(rdir, "*.jpg")):
        os.remove(f)
    lab = overlay.font("en_b", 18)
    for s in tl["shots"]:
        have = [n for n in frames if s["start"] <= n <= s["end"]]
        if not have:
            continue
        pick = [have[round(i * (len(have) - 1) / max(1, per - 1))] for i in range(min(per, len(have)))]
        tiles = []
        for n in pick:
            im = Image.open(frames[n]).convert("RGBA").resize(tuple(tl["size"]), Image.BOX)
            ov = os.path.join(out, "overlay", os.path.basename(frames[n]))
            if os.path.exists(ov):
                im.alpha_composite(Image.open(ov))
            im = im.convert("RGB")
            im.thumbnail((tw, tw))
            ImageDraw.Draw(im).text((8, im.size[1] - 26), f"{s['id']}  f{n}  {(n - s['start']) / tl['fps']:.1f}s",
                                    fill=(255, 0, 80), font=lab)
            tiles.append(im)
        th = tiles[0].size[1]
        sheet = Image.new("RGB", (tw * 3, th * ((len(tiles) + 2) // 3)), "black")
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % 3) * tw, (i // 3) * th))
        sheet.save(os.path.join(rdir, f"{s['id']}.jpg"), quality=85)
    print(f"review: {rdir}")
