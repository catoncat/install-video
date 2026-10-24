"""整理资料用的小工具（在 Blender 里运行）。

frames(video, every=2.0)：每隔 every 秒抽一帧到 <视频名>_frames/，再拼一张总览图 sheet.jpg
sheet(folder, per=16)：把目录里的图片拼成带文件名的总览图 <目录>_sheets/sheet_NN.jpg，方便逐张看
"""
import os, re
import bpy
from PIL import Image, ImageDraw, ImageOps
from .overlay import font


def sheet(folder, per=16, cols=4, w=420, h=330, out=None):
    key = lambda n: (int(m[0]) if (m := re.findall(r"\d+", n)) else 1 << 30, n)
    files = sorted([f for f in os.listdir(folder) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))], key=key)
    out = out or folder.rstrip("/\\") + "_sheets"
    os.makedirs(out, exist_ok=True)
    lab = font("zh", 20)
    paths = []
    for p in range(0, len(files), per):
        chunk = files[p:p + per]
        rows = (len(chunk) + cols - 1) // cols
        img = Image.new("RGB", (w * cols, (h + 30) * rows), "white")
        d = ImageDraw.Draw(img)
        for i, f in enumerate(chunk):
            im = ImageOps.exif_transpose(Image.open(os.path.join(folder, f))).convert("RGB")
            im.thumbnail((w - 10, h - 10))
            x, y = (i % cols) * w, (i // cols) * (h + 30)
            img.paste(im, (x + 5, y + 5))
            d.text((x + 5, y + h), f, fill=(220, 0, 60), font=lab)
        path = os.path.join(out, f"sheet_{p // per + 1:02d}.jpg")
        img.save(path, quality=82)
        paths.append(path)
    print(f"{len(files)} images -> {out}")
    return paths


def grab(video, indices, folder):
    """用视频编辑器从视频里截指定帧（从 1 开始计），返回 {帧: jpg 路径}"""
    os.makedirs(folder, exist_ok=True)
    sc = bpy.data.scenes.get("GRAB") or bpy.data.scenes.new("GRAB")
    clip = bpy.data.movieclips.load(video)
    (w, h), fps = clip.size, clip.fps
    bpy.data.movieclips.remove(clip)
    r = sc.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100   # 先设尺寸再加素材
    sc.sequence_editor_create()
    strips = sc.sequence_editor.strips if hasattr(sc.sequence_editor, "strips") else sc.sequence_editor.sequences
    for s in list(strips):
        strips.remove(s)
    st = strips.new_movie("v", video, 1, 1)
    sc.frame_end = st.frame_final_duration
    r.use_sequencer = True
    if hasattr(r.image_settings, "media_type"):
        r.image_settings.media_type = "IMAGE"
    r.image_settings.file_format = "JPEG"
    out = {}
    for f in indices:
        sc.frame_set(f)
        r.filepath = out[f] = os.path.join(folder, f"v{f:06d}.jpg")
        bpy.ops.render.render(write_still=True, scene=sc.name)
    return out, fps


def frames(video, every=2.0):
    """参考视频每隔 every 秒抽一帧，拼成总览图"""
    clip = bpy.data.movieclips.load(video)
    fps, n = clip.fps, clip.frame_duration
    bpy.data.movieclips.remove(clip)
    out = os.path.splitext(video)[0] + "_frames"
    step = max(1, round(every * fps))
    paths, _ = grab(video, list(range(1, n + 1, step)), out)
    for f, p in paths.items():
        os.replace(p, os.path.join(out, f"t{(f - 1) / fps:06.1f}s.jpg"))
    return sheet(out, per=20, out=out + "_sheets")
