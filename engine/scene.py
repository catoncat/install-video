"""白棚场景、灯光、渲染设置、高亮材质。与产品无关。"""
import bpy, math

HL_COLOR = (1.0, 0.42, 0.05)       # 高亮橙

# 画面风格。产品可以在 shots.py 里写 STYLE = dict(...) 覆盖其中几项。
# 原则：浅色产品配深色背景和地面，主体靠亮度差跳出来；描边让白板和白板之间也分得清。
STYLE = dict(
    bg=(0.055, 0.065, 0.085),      # 相机看到的背景（深蓝灰）
    floor=(0.08, 0.09, 0.105),     # 无缝背景的地面
    ambient=(0.45, 0.47, 0.50),    # 环境光颜色（只用于照明，相机看不到）
    ambient_strength=0.35,
    lines=True,                    # 描边
    line_color=(0.10, 0.11, 0.13),
    line_opacity=0.75,
)

QUALITY = {
    # 名称: (输出分辨率百分比, EEVEE 采样)。内部按 SS 倍分辨率渲染再缩小（超采样），
    # 描边细而直、逐帧不闪；每个输出像素已有 SS² 倍样本，所以采样数可以低一些
    "draft": (25, 8),       # 输出 480×270
    "preview": (50, 16),    # 输出 960×540
    "final": (100, 8),      # 输出 1920×1080（内部 3840×2160）
}
SS = 2

def output_size(quality):
    pct = QUALITY[quality][0]
    return 1920 * pct // 100, 1080 * pct // 100


def setup(quality="preview", style=None):
    st = {**STYLE, **(style or {})}
    sc = bpy.context.scene
    pct, samples = QUALITY[quality]
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except TypeError as e:
        print("engine:", e)
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    sc.render.resolution_percentage = pct * SS
    sc.render.fps = 30
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    ee = sc.eevee
    ee.taa_render_samples = samples
    for attr, val in (("use_raytracing", False), ("use_shadows", True), ("use_gtao", True),   # 光追画面几乎无差别，多 30% 耗时
                      ("shadow_ray_count", 2)):     # 每个采样多打一根阴影光线，软阴影噪点明显减少
        if hasattr(ee, attr):
            setattr(ee, attr, val)
    vs = sc.view_settings
    vs.exposure = 0.0
    looks = [i.identifier for i in bpy.types.ColorManagedViewSettings.bl_rna.properties["view_transform"].enum_items]
    if "AgX" in looks:
        vs.view_transform = "AgX"
        try:
            vs.look = "AgX - Medium High Contrast"
        except TypeError:
            pass
    world(st)
    studio(st)
    patch_materials()
    lines(sc, st)

def world(st):
    """相机看到 bg，物体受到的环境光是 ambient：两者分开，背景再暗也不影响照明"""
    w = bpy.data.worlds.get("STUDIO") or bpy.data.worlds.new("STUDIO")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    amb, cam = nt.nodes.new("ShaderNodeBackground"), nt.nodes.new("ShaderNodeBackground")
    amb.inputs["Color"].default_value = (*st["ambient"], 1)
    amb.inputs["Strength"].default_value = st["ambient_strength"]
    cam.inputs["Color"].default_value = (*st["bg"], 1)
    lp, mix = nt.nodes.new("ShaderNodeLightPath"), nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(amb.outputs[0], mix.inputs[1])
    nt.links.new(cam.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    bpy.context.scene.world = w

def lines(sc, st):
    """GPU 合成器描边：物体随机值（AOV）、法线、深度三路 Sobel 边缘取最大值，叠成深色线。
       耗时只和分辨率有关，和场景复杂度无关（Freestyle 是 CPU 单线程，复杂场景一帧要好几秒）。"""
    sc.render.use_freestyle = False
    sc.render.use_compositing = st["lines"]
    if not st["lines"]:
        return
    vl = sc.view_layers[0]
    vl.use_pass_normal = vl.use_pass_z = True
    if "oid" not in [a.name for a in vl.aovs]:
        aov = vl.aovs.add(); aov.name = "oid"; aov.type = "VALUE"
    ng = bpy.data.node_groups.get("OUTLINE") or bpy.data.node_groups.new("OUTLINE", "CompositorNodeTree")
    ng.nodes.clear()
    if not ng.interface.items_tree:
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    N, L = ng.nodes.new, ng.links.new
    rl = N("CompositorNodeRLayers"); rl.scene = sc
    def sobel(sock):
        f = N("CompositorNodeFilter"); f.inputs["Type"].default_value = "Sobel"
        L(sock, f.inputs["Image"]); return f.outputs[0]
    def math(op, a, b=None, v=None, v2=None, clamp=False):
        m = N("ShaderNodeMath"); m.operation = op; m.use_clamp = clamp; L(a, m.inputs[0])
        if b is not None:
            L(b, m.inputs[1])
        elif v is not None:
            m.inputs[1].default_value = v
        if v2 is not None:
            m.inputs[2].default_value = v2
        return m.outputs[0]
    def ramp(x, t):
        """从 t 到 2t 线性过渡到 1：软阈值，线条自带抗锯齿，逐帧不闪"""
        return math("MULTIPLY_ADD", x, v=1 / t, v2=-1.0, clamp=True)
    e_id = ramp(sobel(rl.outputs["oid"]), 0.02)                                       # 不同零件的交界
    e_n = ramp(sobel(rl.outputs["Normal"]), 0.5)                                      # 折边
    e_z = ramp(math("DIVIDE", sobel(rl.outputs["Depth"]), rl.outputs["Depth"]), 0.06)  # 轮廓
    edge = math("MAXIMUM", math("MAXIMUM", e_id, e_n), e_z)
    mix = N("ShaderNodeMix"); mix.data_type = "RGBA"
    L(math("MULTIPLY", edge, v=st["line_opacity"]), mix.inputs["Factor"])
    L(rl.outputs["Image"], mix.inputs["A"])
    mix.inputs["B"].default_value = (*st["line_color"], 1)
    L(mix.outputs["Result"], N("NodeGroupOutput").inputs[0])
    sc.compositing_node_group = ng
    try:
        sc.render.compositor_device = "GPU"
    except TypeError:
        pass

def _light(name, kind, loc, rot, energy, size, color=(1, 1, 1)):
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, bpy.data.lights.new(name, kind))
        bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    ob.data.energy = energy
    ob.data.color = color
    ob.visible_camera = False
    if kind == "AREA":
        ob.data.size = size
    elif kind == "SUN":
        ob.data.angle = math.radians(size)
    return ob

def studio(st):
    """无缝背景 + 主光（太阳，给清晰阴影）+ 两盏面光补光"""
    for n in ("Light", "Cube", "Camera"):
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)
    if bpy.data.objects.get("CYC") is None:
        import bmesh
        bm = bmesh.new()
        # 地面 + 后方弧形上翻，无地平线
        r, depth, width, steps = 10.0, 120.0, 400.0, 16
        prof = [(-depth, -0.21)] + [(r * math.sin(a), -0.21 + r - r * math.cos(a))
                                     for a in [i / steps * math.pi / 2 for i in range(steps + 1)]] + [(r, 120)]
        prof = [(y + 25, z) for y, z in prof]
        rows = [[bm.verts.new((x, y, z)) for (y, z) in prof] for x in (-width / 2, width / 2)]
        for i in range(len(prof) - 1):
            bm.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1]))
        me = bpy.data.meshes.new("CYC"); bm.to_mesh(me); bm.free()
        cyc = bpy.data.objects.new("CYC", me)
        bpy.context.scene.collection.objects.link(cyc)
        m = bpy.data.materials.get("cyc") or bpy.data.materials.new("cyc")
        m.use_nodes = True
        cyc.data.materials.append(m)
        for p in cyc.data.polygons:
            p.use_smooth = True
    b = next(n for n in bpy.data.materials["cyc"].node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*st["floor"], 1)
    b.inputs["Roughness"].default_value = 0.9
    _light("KEY", "SUN", (0, 0, 10), (42, 0, -32), 4.5, 1.5)
    # 补光灯面不要太大：大灯面的软阴影要很多采样才不出噪点
    _light("FILL", "AREA", (-9, -8, 6), (60, 0, -50), 700, 3, (0.92, 0.95, 1.0))
    _light("RIM", "AREA", (8, 9, 7), (-55, 0, 140), 1400, 3, (1.0, 0.96, 0.9))

def patch_materials():
    """给每个材质接上：对象属性 hl（0~1）→ 底色混合高亮橙 + 少量自发光；
       物体随机值 → AOV "oid"（描边用来区分零件）。可重复调用"""
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        nt = m.node_tree
        if "OID_AOV" not in nt.nodes:
            oi, aov = nt.nodes.new("ShaderNodeObjectInfo"), nt.nodes.new("ShaderNodeOutputAOV")
            aov.name, aov.aov_name = "OID_AOV", "oid"
            nt.links.new(oi.outputs["Random"], aov.inputs["Value"])
        if m.name == "cyc":
            continue
        if "HL_ATTR" in nt.nodes:
            continue
        b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b is None:
            continue
        attr = nt.nodes.new("ShaderNodeAttribute"); attr.name = "HL_ATTR"
        attr.attribute_type = "OBJECT"; attr.attribute_name = "hl"
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
        mix.inputs["A"].default_value = b.inputs["Base Color"].default_value
        mix.inputs["B"].default_value = (*HL_COLOR, 1)
        scale = nt.nodes.new("ShaderNodeMath"); scale.operation = "MULTIPLY"; scale.inputs[1].default_value = 0.65
        nt.links.new(attr.outputs["Fac"], scale.inputs[0])
        nt.links.new(scale.outputs[0], mix.inputs["Factor"])
        nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
        if b.inputs["Emission Strength"].default_value == 0:
            b.inputs["Emission Color"].default_value = (*HL_COLOR, 1)
            em = nt.nodes.new("ShaderNodeMath"); em.operation = "MULTIPLY"; em.inputs[1].default_value = 0.35
            nt.links.new(attr.outputs["Fac"], em.inputs[0])
            nt.links.new(em.outputs[0], b.inputs["Emission Strength"])
