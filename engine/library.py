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
    "sandwich_white": ("Sandwich Panel 白色夹芯板", dict(color=(0.86, 0.86, 0.84), rough=0.6, bump=("noise", 60, 0.05))),
    "sandwich_grey": ("Sandwich Panel 灰色夹芯板", dict(color=(0.45, 0.47, 0.50), rough=0.6, bump=("noise", 60, 0.05))),
    "metal_dark": ("Metal Panel 深色金属板", dict(color=(0.10, 0.11, 0.13), metal=0.6, rough=0.35, bump=("ribs_x", 8, 0.25))),
    "flexible_stone": ("Flexible Stone 柔性石材", dict(color=(0.62, 0.55, 0.45), color2=(0.78, 0.72, 0.62), noise=6, rough=0.85,
                                                    bump=("noise", 18, 0.3))),
    "soft_stone": ("Soft Stone 软瓷", dict(color=(0.55, 0.45, 0.34), color2=(0.74, 0.64, 0.50), noise=2.5, rough=0.8,
                                         bump=("noise", 10, 0.25))),
    "cement": ("Cement Texture 水泥质感", dict(color=(0.42, 0.42, 0.41), color2=(0.55, 0.55, 0.53), noise=12, rough=0.9,
                                            bump=("noise", 40, 0.15))),
    "wpc_wall": ("WPC Wall Panel 木塑墙板", dict(color=(0.30, 0.17, 0.09), color2=(0.45, 0.28, 0.15), wood=6,
                                            rough=0.55, bump=("ribs_x", 7, 0.4))),
    "spc_oak": ("SPC Floor 橡木纹石塑地板", dict(color=(0.42, 0.28, 0.16), color2=(0.60, 0.43, 0.27), wood=3, rough=0.45,
                                             tiles=(1.22, 0.18))),
    "wpc_floor": ("WPC Floor 木塑地板", dict(color=(0.22, 0.13, 0.08), color2=(0.33, 0.21, 0.12), wood=3, rough=0.6,
                                         tiles=(2.2, 0.14))),
    "tile": ("Tile 瓷砖", dict(color=(0.80, 0.80, 0.78), color2=(0.55, 0.55, 0.54), rough=0.25, tiles=(0.6, 0.6))),
    "gypsum": ("Gypsum Ceiling 石膏板吊顶", dict(color=(0.92, 0.92, 0.90), rough=0.95)),
    "pvc_ceiling": ("PVC Ceiling 扣板吊顶", dict(color=(0.90, 0.90, 0.88), rough=0.4, bump=("ribs_x", 5, 0.3))),
    "led_panel": ("LED Panel 平板灯", dict(color=(1.0, 0.98, 0.94), rough=0.3, emission=6.0)),
}


def _nodes(m):
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    return nt, b, coord.outputs["Object"]


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
        w.inputs["Distortion"].default_value = 6
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
        br.inputs["Mortar Size"].default_value = 0.004
        br.inputs["Mortar"].default_value = (0.08, 0.06, 0.05, 1)
        base = b.inputs["Base Color"]
        if base.is_linked:                # 木纹颜色进砖块颜色，缝线叠在上面
            src = base.links[0].from_socket
            L(src, br.inputs["Color1"]); L(src, br.inputs["Color2"])
        else:
            br.inputs["Color1"].default_value = c1
            br.inputs["Color2"].default_value = (*p.get("color2", p["color"]), 1)
        L(co, br.inputs["Vector"])
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
