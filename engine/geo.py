"""建模小工具（与产品无关）。

所有对象都放进 ROOT 集合下按 stage 分的子集合，对象上记录 ["stage"]。
动画按对象名或 "@stage" 选取对象，所以命名要稳定。
"""
import bpy, bmesh
from mathutils import Vector

ROOT = "MODEL"


# ---------------- 集合 / 对象 ----------------
def reset():
    root = bpy.data.collections.get(ROOT)
    if root:
        for c in [root, *root.children_recursive]:
            for o in list(c.objects):
                bpy.data.objects.remove(o, do_unlink=True)
        for c in list(root.children_recursive):
            bpy.data.collections.remove(c)
        bpy.data.collections.remove(root)
    for m in list(bpy.data.meshes):
        if m.users == 0:
            bpy.data.meshes.remove(m)
    root = bpy.data.collections.new(ROOT)
    bpy.context.scene.collection.children.link(root)

def coll(stage):
    c = bpy.data.collections.get(stage)
    if c is None:
        c = bpy.data.collections.new(stage)
        bpy.data.collections[ROOT].children.link(c)
    return c

def obj(name, bm, material, stage, bevel=0.0, **props):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(material)
    coll(stage).objects.link(ob)
    ob["stage"] = stage
    for k, v in props.items():
        ob[k] = v
    if bevel:
        add_bevel(ob, bevel)
    return ob

def add_bevel(ob, width):
    mod = ob.modifiers.new("bevel", "BEVEL")
    mod.width = width
    mod.segments = 2
    mod.limit_method = "ANGLE"


# ---------------- 材质 ----------------
def mat(name, color, metallic=0.0, rough=0.5, transmission=0.0, emission=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    if transmission:
        b.inputs["Transmission Weight"].default_value = transmission
        b.inputs["IOR"].default_value = 1.45
    if emission:
        b.inputs["Emission Color"].default_value = (*color, 1)
        b.inputs["Emission Strength"].default_value = emission
    m.diffuse_color = (*color, 1)
    return m


def variant(sel, tag, material):
    """材质变体：把 sel（对象列表或选择器）复制一份换成 material，放进 stage "variant_<tag>"，默认不可见。
       复制品和原件共用网格（材质挂在对象上），名字是 "<原名>@<tag>"。分镜里用 swap(sel, tag, 秒) 切换。
       在 shots.py 的 prepare() 里调用（模型建好之后、时间线之前）。"""
    if isinstance(sel, (str, list, tuple)) and not isinstance(next(iter(sel), None), bpy.types.Object):
        from .anim import resolve              # 运行时再导入，避免和 anim 循环引用
        sel = resolve(sel)
    stage = f"variant_{tag}"
    out = []
    for o in sel:
        c = o.copy()                           # 共用网格数据和修改器设置
        c.name = f"{o.name}@{tag}"
        c["stage"], c["variant"], c["variant_of"] = stage, tag, o.name
        for slot in c.material_slots:
            slot.link = "OBJECT"
            slot.material = material
        coll(stage).objects.link(c)
        out.append(c)
    return out


# ---------------- 几何 ----------------
def _add_box(bm, size, center):
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r["verts"]:
        v.co = Vector((v.co.x * size[0] + center[0], v.co.y * size[1] + center[1], v.co.z * size[2] + center[2]))

def box(name, size, center, material, stage, bevel=0.0, **props):
    return boxes(name, [(size, center)], material, stage, bevel, **props)

def boxes(name, parts, material, stage, bevel=0.0, **props):
    """多个长方体合成一个对象，parts = [(size, center), ...]"""
    bm = bmesh.new()
    for size, center in parts:
        _add_box(bm, size, center)
    return obj(name, bm, material, stage, bevel, **props)

def _map(axis, a, b, s):
    """截面坐标 (a,b) + 沿轴坐标 s -> 世界坐标。X:(y,z) Y:(x,z) Z:(x,y)，都是正交旋转"""
    return {"X": (s, a, b), "Y": (-a, s, b), "Z": (a, b, s)}[axis]

def profile(name, pts, length, axis, origin, material, stage, **props):
    """2D 截面 pts 沿 axis 拉伸 length（以 origin 为中点）。Y 轴时截面 a 取反"""
    bm = bmesh.new()
    o = Vector(origin)
    ring = lambda s: [bm.verts.new(o + Vector(_map(axis, a, b, s))) for a, b in pts]
    v0, v1 = ring(-length / 2), ring(length / 2)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((v0[i], v0[j], v1[j], v1[i]))
    bm.faces.new(v0[::-1])
    bm.faces.new(v1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj(name, bm, material, stage, **props)

def cylinder(name, radius, depth, center, axis, material, stage, segments=24, **props):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius, depth=depth)
    for v in bm.verts:
        v.co = Vector(center) + Vector(_map(axis, v.co.x, v.co.y, v.co.z))
    return obj(name, bm, material, stage, **props)

def c_pts(h, f, t, d=1):
    """C 型钢截面：腹板在 a=0，翼缘朝 d 方向伸出，高 h"""
    pts = [(0, 0), (f, 0), (f, t), (t, t), (t, h - t), (f, h - t), (f, h), (0, h)]
    return [(a * d, b) for a, b in pts]

def cut(ob, cutters):
    """从 ob 减掉一组孔并应用。cutters = [(kind, size, center, axis)]
       kind "cyl": size = (直径, 深)；"slot" 长圆孔: size = (宽, 深, 高)。孔深沿 axis，孔高沿世界 Z"""
    tmp = []
    for kind, size, center, axis in cutters:
        w, d, h = (size[0], size[1], size[0]) if kind == "cyl" else size
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.5, radius2=0.5, depth=1.0)
        for v in bm.verts:
            v.co = Vector(center) + Vector(_map(axis, v.co.x * w, v.co.y * h, v.co.z * d))
        me = bpy.data.meshes.new("cutter"); bm.to_mesh(me); bm.free()
        c = bpy.data.objects.new("cutter", me)
        bpy.context.scene.collection.objects.link(c)
        tmp.append(c)
    bevel = next((m.width for m in ob.modifiers if m.type == "BEVEL"), 0)
    for m in [m for m in ob.modifiers if m.type == "BEVEL"]:
        ob.modifiers.remove(m)
    for c in tmp:
        m = ob.modifiers.new("cut", "BOOLEAN")
        m.object = c
        m.solver = "EXACT"
        with bpy.context.temp_override(object=ob, active_object=ob):
            bpy.ops.object.modifier_apply(modifier=m.name)
    for c in tmp:
        me = c.data
        bpy.data.objects.remove(c, do_unlink=True)
        bpy.data.meshes.remove(me)
    if bevel:
        add_bevel(ob, bevel)
