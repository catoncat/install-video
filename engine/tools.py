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


def frames(video, every=2.0):
    out = os.path.splitext(video)[0] + "_frames"
    os.makedirs(out, exist_ok=True)
    sc = bpy.data.scenes.new("FRAMES")
    sc.sequence_editor_create()
    strips = sc.sequence_editor.strips if hasattr(sc.sequence_editor, "strips") else sc.sequence_editor.sequences
    st = strips.new_movie("v", video, 1, 1)
    clip = bpy.data.movieclips.load(video)
    (w, h), fps, n = clip.size, clip.fps, st.frame_final_duration
    print(f"{w}x{h} {fps}fps {n / fps:.1f}s")
    r = sc.render
    r.resolution_x, r.resolution_y = w, h
    r.resolution_percentage = 50 if max(w, h) > 1280 else 100
    r.use_sequencer = True
    r.image_settings.file_format = "JPEG"
    f = 1
    while f <= n:
        sc.frame_set(f)
        r.filepath = os.path.join(out, f"t{(f - 1) / fps:06.1f}s.jpg")
        bpy.ops.render.render(write_still=True, scene=sc.name)
        f += max(1, round(every * fps))
    return sheet(out, per=20, out=out + "_sheets")
