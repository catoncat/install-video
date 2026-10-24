"""整理资料用的小工具（在 Blender 里运行）。

pdf(path)：PDF → <名字>_pdf/ 下的 page_NN.png（整页）、img_NN_MM.png（内嵌原图）、text.txt（全文），外加总览图

frames(video, every=2.0)：每隔 every 秒抽一帧到 <视频名>_frames/，再拼一张总览图 sheet.jpg
sheet(folder, per=16)：把目录里的图片拼成带文件名的总览图 <目录>_sheets/sheet_NN.jpg，方便逐张看
"""
import os, re, sys
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
    sc.frame_start = sc.frame_end = sc.frame_current = 1
    r.use_sequencer = True
    if hasattr(r.image_settings, "media_type"):
        r.image_settings.media_type = "IMAGE"
    r.image_settings.file_format = "JPEG"
    out = {}
    for f in indices:
        # 场景帧号固定在 1，平移素材让第 f 帧落在 1 上（指定 scene 渲染时 frame_set 不生效）
        st.frame_start = 2 - f
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


def pdf(path, scale=2.0):
    """用 pypdfium2 处理 PDF：整页渲染、内嵌图片、全文文字（各平台通用，不依赖系统工具）"""
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw
    out = os.path.splitext(path)[0] + "_pdf"
    os.makedirs(out, exist_ok=True)
    doc = pdfium.PdfDocument(path)
    texts, n_img = [], 0
    for i, page in enumerate(doc, 1):
        page.render(scale=scale).to_pil().save(os.path.join(out, f"page_{i:02d}.png"))
        texts.append(f"===== 第 {i} 页 =====\n" + page.get_textpage().get_text_bounded())
        for j, ob in enumerate(page.get_objects(filter=[raw.FPDF_PAGEOBJ_IMAGE], max_depth=2), 1):
            try:
                im = ob.get_bitmap(render=False).to_pil()
            except Exception:
                continue
            if min(im.size) >= 120:          # 跳过图标、线条之类的小图
                im.convert("RGB").save(os.path.join(out, f"img_{i:02d}_{j:02d}.png"))
                n_img += 1
    with open(os.path.join(out, "text.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(texts))
    print(f"{len(doc)} pages, {n_img} images, text.txt -> {out}")
    return sheet(out, per=16)


def swatch(product=None, size=400):
    """材质色卡：材料库全部预设（给了产品目录就再加上产品自己的材质和变体），在标准灯光下逐个渲染，
       拼成带名字的总览图。用来挑能拉开差别的饰面，不用反复出片试色。"""
    from engine import run
    geo, anim, scene, model, shots = run.load(product) if product else (None,) * 5
    if geo is None:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from engine import geo, anim, scene
    from engine import library
    geo.reset()
    items = [(k, d, library.material(k)) for k, (d, _) in library.PRESETS.items()]
    if product:
        model.build()
        if hasattr(shots, "prepare"):
            shots.prepare()
        seen = {m.name for _, _, m in items}
        for o in geo.model_objects():
            for slot in o.material_slots:
                if slot.material and slot.material.name not in seen:
                    seen.add(slot.material.name)
                    items.append((slot.material.name, "产品材质", slot.material))
            o.hide_render = True
    scene.setup("preview", getattr(shots, "STYLE", None) if product else None, "1:1")
    sc = bpy.context.scene
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.render.resolution_percentage = 100 * scene.SS
    me = bpy.data.meshes.get("SWATCH") or bpy.data.meshes.new("SWATCH")
    import bmesh
    bm = bmesh.new()
    geo._add_box(bm, (1.0, 0.05, 1.0), (0, 0.3, 0.5))        # 立面
    geo._add_box(bm, (1.0, 0.6, 0.02), (0, -0.02, 0.01))     # 地面
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.get("SWATCH") or bpy.data.objects.new("SWATCH", me)
    if ob.name not in sc.collection.objects:
        sc.collection.objects.link(ob)
    cam, tgt = anim.scene_camera()
    tgt.location = (0, 0.1, 0.42)
    cam.location = (-1.25, -2.3, 1.35)
    cam.data.lens = 50
    tmp = os.path.join(os.path.abspath(product) if product else os.getcwd(), "out", "swatch")
    os.makedirs(tmp, exist_ok=True)
    from PIL import Image, ImageDraw
    from .overlay import font
    tiles = []
    for name, desc, m in items:
        ob.data.materials.clear()
        ob.data.materials.append(m)
        scene.patch_materials((getattr(shots, "STYLE", None) or {}).get("hl", scene.HL_COLOR) if product else scene.HL_COLOR)
        sc.render.filepath = os.path.join(tmp, f"{name}.png")
        bpy.ops.render.render(write_still=True)
        im = Image.open(sc.render.filepath).convert("RGB").resize((size, size), Image.LANCZOS)
        lab = Image.new("RGB", (size, 54), "white")
        d = ImageDraw.Draw(lab)
        d.text((8, 4), name, fill=(20, 20, 20), font=font("en_b", 18))
        d.text((8, 28), desc, fill=(90, 90, 90), font=font("zh", 15))
        t = Image.new("RGB", (size, size + 54), "white")
        t.paste(im, (0, 0)); t.paste(lab, (0, size))
        tiles.append(t)
    cols = 4
    sheet = Image.new("RGB", (cols * size, ((len(tiles) + cols - 1) // cols) * (size + 54)), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * size, (i // cols) * (size + 54)))
    path = os.path.join(os.path.dirname(tmp), "swatch.jpg")
    sheet.save(path, quality=88)
    print(f"swatch: {len(tiles)} 种材质 -> {path}")
    return path


def check(product, frames=None, every=6):
    """穿模检查：抽查帧（默认每 every 帧）里，不在静止位置的零件（正在动或处于折叠等姿态）和别的 stage 的零件
       网格是否相交。设计上就贴在一起的，在对象上写 touch_ok=True（全部放过）或 touch_ok="post_*"（只放过匹配的）。"""
    import fnmatch
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from engine import run
    geo, anim, scene, model, shots = run.load(product)
    geo.reset()
    model.build()
    if hasattr(shots, "prepare"):
        shots.prepare()
    tl = anim.Timeline("16:9", None, product).build(shots.SHOTS)
    sc = bpy.context.scene
    frames = frames or list(range(sc.frame_start, sc.frame_end + 1, every))
    objs = [o for o in anim.model_objects() if o.type == "MESH"]

    def allowed(a, b):
        for x, y in ((a, b), (b, a)):
            t = x.get("touch_ok")
            if t is True or (isinstance(t, str) and fnmatch.fnmatchcase(y.name, t)):
                return True
        return False

    def aabb(o):
        pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
        return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])

    hits = {}
    dg = bpy.context.evaluated_depsgraph_get()
    for fr in frames:
        sc.frame_set(fr)
        dg.update()
        vis = [o for o in objs if not o.hide_render]
        moving = [o for o in vis if (o.matrix_world.translation - Vector(o["rest"])).length > 1e-4
                  or any(abs(a - b) > 1e-4 for a, b in zip(o.rotation_euler, o.get("rest_rot", (0, 0, 0))))]
        boxes = {o: aabb(o) for o in vis}
        trees = {}
        for a in moving:
            for b in vis:
                if b is a or b.get("stage") == a.get("stage") or allowed(a, b):
                    continue
                key = tuple(sorted((a.name, b.name)))
                (la, ha), (lb, hb) = boxes[a], boxes[b]
                if any(ha[i] < lb[i] or hb[i] < la[i] for i in range(3)):
                    continue
                for o in (a, b):
                    if o not in trees:
                        me = o.evaluated_get(dg).data          # 世界坐标下建树，两棵树才能直接比
                        trees[o] = BVHTree.FromPolygons([o.matrix_world @ v.co for v in me.vertices],
                                                        [p.vertices[:] for p in me.polygons])
                if trees[a].overlap(trees[b]):
                    hits.setdefault(key, []).append(fr)
    shot_of = lambda fr: next((s["id"] for s, a, b in tl.shots if a <= fr < b), "?")
    if not hits:
        print(f"check: {len(frames)} 帧，没有发现穿模")
        return []
    stage = {o.name: o.get("stage", "?") for o in objs}
    groups = {}
    for (a, b), frs in hits.items():
        g = groups.setdefault(tuple(sorted((stage[a], stage[b]))), dict(pairs=[], frames=[]))
        g["pairs"].append((a, b))
        g["frames"] += frs
    print(f"check: {len(frames)} 帧里发现 {len(hits)} 对零件相交，按 stage 归成 {len(groups)} 组（只查不在静止位置的零件）：")
    for (sa, sb), g in sorted(groups.items(), key=lambda kv: min(kv[1]["frames"])):
        f0, f1 = min(g["frames"]), max(g["frames"])
        eg = "、".join(f"{a} × {b}" for a, b in g["pairs"][:2])
        print(f"  - {sa} × {sb}：{len(g['pairs'])} 对，{shot_of(f0)}（帧 {f0}–{f1}）。例：{eg}")
    print("  设计上本来就贴在一起的，给对象加 touch_ok=True 或 touch_ok=\"名字通配\" 放过")
    return hits
