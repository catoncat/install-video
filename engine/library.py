"""材料库：常见墙面、地面、吊顶的程序化材质预设（不需要贴图文件），用于"定制选项"展示。

用法（在 shots.py 的 prepare() 里）：
    from engine import library, geo
    geo.variant("@06_walls", "stone", library.material("soft_stone"))
    geo.variant("floor_pvc", "oak", library.material("spc_oak"))
    geo.variant("@06_walls", "photo", library.mat_image("my_panel", "资料/墙板.jpg", scale=1.2))
然后在分镜里 swap("@06_walls", "stone", 秒)。

纹理按对象自身坐标（米）铺，所以同一个预设在不同大小的零件上纹理尺度一致。
预设名见 PRESETS；每个预设都是 Principled BSDF，能正常参与高亮和描边。
"""
import os
import bpy

# 名称: (说明, 构造参数)。颜色都是线性 RGB
PRESETS = {
    # 颜色在引擎灯光（AgX + 主光）下实测过：浅色会被提亮，所以石材 / 水泥 / 木纹都取中低反照率，彼此和白色夹芯板拉开。
    # 用 video swatch 出色卡核对
    "sandwich_white": ("Sandwich Panel 白色夹芯板", dict(color=(0.80, 0.80, 0.78), rough=0.6, bump=("noise", 60, 0.05))),
    "sandwich_grey": ("Sandwich Panel 灰色夹芯板", dict(color=(0.30, 0.32, 0.35), rough=0.6, bump=("noise", 60, 0.05))),
    "metal_dark": ("Metal Panel 深色金属板", dict(color=(0.06, 0.065, 0.075), metal=0.6, rough=0.35, bump=("ribs_x", 8, 0.25))),
    "flexible_stone": ("Flexible Stone 柔性石材", dict(color=(0.24, 0.17, 0.10), color2=(0.46, 0.36, 0.24), noise=4, rough=0.85,
                                                    tiles=(1.2, 0.6), mortar=(0.10, 0.08, 0.06), bump=("noise", 18, 0.35))),
    "soft_stone": ("Soft Stone 软瓷", dict(color=(0.30, 0.13, 0.07), color2=(0.46, 0.25, 0.14), noise=8, rough=0.85,
                                         tiles=(0.6, 0.2), mortar=(0.55, 0.52, 0.48), bump=("noise", 25, 0.35))),
    "cement": ("Cement Texture 水泥质感", dict(color=(0.13, 0.13, 0.13), color2=(0.26, 0.26, 0.25), noise=3, rough=0.9,
                                            tiles=(1.2, 2.4), mortar=(0.05, 0.05, 0.05), bump=("noise", 40, 0.2))),
    "wpc_wall": ("WPC Wall Panel 木塑墙板", dict(color=(0.16, 0.08, 0.035), color2=(0.30, 0.17, 0.08), wood=10, rough=0.55,
                                            bump=("ribs_x", 7, 0.5))),
    "spc_oak": ("SPC Floor 橡木纹石塑地板", dict(color=(0.30, 0.18, 0.09), color2=(0.48, 0.32, 0.18), wood=6, rough=0.45,
                                             tiles=(1.22, 0.18))),
    "wpc_floor": ("WPC Floor 木塑地板", dict(color=(0.10, 0.06, 0.035), color2=(0.20, 0.12, 0.06), wood=6, rough=0.6,
                                         tiles=(2.2, 0.14))),
    "tile": ("Tile 瓷砖", dict(color=(0.42, 0.42, 0.40), color2=(0.50, 0.50, 0.48), rough=0.25, tiles=(0.6, 0.6),
                              mortar=(0.12, 0.12, 0.12))),
    "gypsum": ("Gypsum Ceiling 石膏板吊顶", dict(color=(0.86, 0.86, 0.84), rough=0.95)),
    "pvc_ceiling": ("PVC Ceiling 扣板吊顶", dict(color=(0.78, 0.80, 0.82), rough=0.4, bump=("ribs_x", 5, 0.3))),
    "led_panel": ("LED Panel 平板灯", dict(color=(1.0, 0.98, 0.94), rough=0.3, emission=6.0)),
}


def _nodes(m):
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    return nt, b, coord.outputs["Object"]


def _plane_coords(nt, co):
    """拼缝纹理的平面坐标：地面 / 顶面用 (x, y)，立面用 (x+y, z)，墙上的砖缝、板缝也是横平竖直的"""
    N, L = nt.nodes.new, nt.links.new
    sep, wall, floor = N("ShaderNodeSeparateXYZ"), N("ShaderNodeCombineXYZ"), N("ShaderNodeCombineXYZ")
    add = N("ShaderNodeMath"); add.operation = "ADD"
    L(co, sep.inputs[0])
    L(sep.outputs["X"], add.inputs[0]); L(sep.outputs["Y"], add.inputs[1])
    L(add.outputs[0], wall.inputs["X"]); L(sep.outputs["Z"], wall.inputs["Y"])
    L(sep.outputs["X"], floor.inputs["X"]); L(sep.outputs["Y"], floor.inputs["Y"])
    gn, nsep, ab = N("ShaderNodeNewGeometry"), N("ShaderNodeSeparateXYZ"), N("ShaderNodeMath")
    ab.operation = "ABSOLUTE"
    L(gn.outputs["Normal"], nsep.inputs[0]); L(nsep.outputs["Z"], ab.inputs[0])
    mix = N("ShaderNodeMix"); mix.data_type = "VECTOR"
    gt = N("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = 0.7
    L(ab.outputs[0], gt.inputs[0]); L(gt.outputs[0], mix.inputs["Factor"])
    L(wall.outputs[0], mix.inputs["A"]); L(floor.outputs[0], mix.inputs["B"])
    return mix.outputs["Result"]


def material(preset, name=None):
    """按预设名建（或取已有的）材质"""
    if preset not in PRESETS:
        raise ValueError(f"没有预设 {preset!r}，可选：{list(PRESETS)}")
    name = name or f"lib_{preset}"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    p = PRESETS[preset][1]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt, b, co = _nodes(m)
    L = nt.links.new
    c1 = (*p["color"], 1)
    b.inputs["Base Color"].default_value = c1
    b.inputs["Roughness"].default_value = p.get("rough", 0.5)
    b.inputs["Metallic"].default_value = p.get("metal", 0.0)
    m.diffuse_color = c1
    fac = None
    if "noise" in p:                      # 石材 / 水泥：噪声斑驳
        n = nt.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = p["noise"]
        n.inputs["Detail"].default_value = 8
        L(co, n.inputs["Vector"])
        fac = n.outputs["Fac"]
    if "wood" in p:                       # 木纹：拉长的波纹 + 扰动
        w = nt.nodes.new("ShaderNodeTexWave")
        w.wave_type, w.bands_direction = "BANDS", "X"
        w.inputs["Scale"].default_value = p["wood"]
        w.inputs["Distortion"].default_value = 2.5
        w.inputs["Detail"].default_value = 4
        L(co, w.inputs["Vector"])
        fac = w.outputs["Fac"]
    if fac is not None:
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
        mix.inputs["A"].default_value = c1
        mix.inputs["B"].default_value = (*p["color2"], 1)
        L(fac, mix.inputs["Factor"])
        L(mix.outputs["Result"], b.inputs["Base Color"])
    if "tiles" in p:                      # 地板拼缝 / 瓷砖缝：砖块纹理当缝线
        br = nt.nodes.new("ShaderNodeTexBrick")
        w, h = p["tiles"]
        br.inputs["Scale"].default_value = 1.0
        br.inputs["Brick Width"].default_value = w
        br.inputs["Row Height"].default_value = h
        br.inputs["Mortar Size"].default_value = 0.006
        br.inputs["Mortar"].default_value = (*p.get("mortar", (0.08, 0.06, 0.05)), 1)
        base = b.inputs["Base Color"]
        if base.is_linked:                # 木纹颜色进砖块颜色，缝线叠在上面
            src = base.links[0].from_socket
            L(src, br.inputs["Color1"]); L(src, br.inputs["Color2"])
        else:
            br.inputs["Color1"].default_value = c1
            br.inputs["Color2"].default_value = (*p.get("color2", p["color"]), 1)
        L(_plane_coords(nt, co), br.inputs["Vector"])
        L(br.outputs["Color"], b.inputs["Base Color"])
    if "bump" in p:                       # 表面起伏：橘皮 / 压型肋 / 凹槽
        kind, scale, strength = p["bump"]
        if kind == "noise":
            t = nt.nodes.new("ShaderNodeTexNoise"); t.inputs["Scale"].default_value = scale
            out = t.outputs["Fac"]
        else:
            t = nt.nodes.new("ShaderNodeTexWave"); t.wave_type, t.bands_direction = "BANDS", "X"
            t.wave_profile = "SAW"; t.inputs["Scale"].default_value = scale
            out = t.outputs["Fac"]
        L(co, t.inputs["Vector"])
        bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = strength
        bp.inputs["Distance"].default_value = 0.002
        L(out, bp.inputs["Height"])
        L(bp.outputs["Normal"], b.inputs["Normal"])
    if p.get("emission"):
        b.inputs["Emission Color"].default_value = c1
        b.inputs["Emission Strength"].default_value = p["emission"]
    return m


def mat_image(name, path, scale=1.0, rough=0.6):
    """用户自己的照片当贴图（墙板、地板实拍图），按对象坐标盒式投影平铺，scale 为每米重复几次"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"贴图不存在：{path}")
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt, b, co = _nodes(m)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.abspath(path), check_existing=True)
    tex.projection, tex.projection_blend = "BOX", 0.2
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    nt.links.new(co, mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    return m
