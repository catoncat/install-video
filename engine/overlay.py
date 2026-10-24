"""读 timeline.json，为每个已渲染的帧生成透明 PNG 字幕层（步骤标题、底部说明、标注、片头卡片）。
由 cli.py 调用：overlay.main(<产品目录>/out)。依赖 Pillow。"""
import os, json, shutil
from PIL import Image, ImageDraw, ImageFont

ACCENT = (255, 108, 13)
INK, INK2 = (28, 30, 34), (80, 86, 94)
SS = 2                       # 超采样倍数，线条和圆角更平滑
FADE_IN, FADE_OUT = 8, 6     # 帧

# 字体按平台自动选第一个存在的；可用环境变量 OVERLAY_ZH / OVERLAY_ZH_BOLD / OVERLAY_EN / OVERLAY_EN_BOLD 指定（"路径:索引"）
WIN = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
CANDIDATES = {
    "zh": ["/System/Library/Fonts/Hiragino Sans GB.ttc:0", f"{WIN}/msyh.ttc:0", f"{WIN}/simhei.ttf:0",
           "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc:2", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc:2"],
    "zh_b": ["/System/Library/Fonts/Hiragino Sans GB.ttc:2", f"{WIN}/msyhbd.ttc:0", f"{WIN}/simhei.ttf:0",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc:2", "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc:2"],
    "en": ["/System/Library/Fonts/HelveticaNeue.ttc:0", f"{WIN}/segoeui.ttf:0", f"{WIN}/arial.ttf:0",
           "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:0"],
    "en_b": ["/System/Library/Fonts/HelveticaNeue.ttc:10", f"{WIN}/seguisb.ttf:0", f"{WIN}/arialbd.ttf:0",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:0"],
}
ENV = {"zh": "OVERLAY_ZH", "zh_b": "OVERLAY_ZH_BOLD", "en": "OVERLAY_EN", "en_b": "OVERLAY_EN_BOLD"}

def _pick(kind):
    for spec in ([os.environ[ENV[kind]]] if ENV[kind] in os.environ else []) + CANDIDATES[kind]:
        path, _, idx = spec.rpartition(":")
        if os.path.exists(path):
            return path, int(idx)
    raise FileNotFoundError(f"找不到 {kind} 字体，请设置环境变量 {ENV[kind]}=字体路径:索引")
FONTS = {k: _pick(k) for k in CANDIDATES}
_cache = {}
ALIAS = {}       # 纯英文模式下把中文字体角色映射到英文字体
def font(kind, px):
    kind = ALIAS.get(kind, kind)
    key = (kind, px)
    if key not in _cache:
        path, idx = FONTS[kind]
        _cache[key] = ImageFont.truetype(path, px, index=idx)
    return _cache[key]


class Painter:
    """所有尺寸按 1920×1080 设计，k 为实际缩放（含超采样）"""
    def __init__(self, w, h):
        self.k = w / 1920 * SS
        self.img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def S(self, v):
        return round(v * self.k)

    def text_size(self, txt, kind, px):
        b = self.d.textbbox((0, 0), txt, font=font(kind, self.S(px)))
        return (b[2] - b[0]) / self.k, (b[3] - b[1]) / self.k

    def text(self, xy, txt, kind, px, color, a):
        self.d.text((self.S(xy[0]), self.S(xy[1])), txt, font=font(kind, self.S(px)), fill=(*color, round(255 * a)))

    def rect(self, box, r, color, alpha):
        self.d.rounded_rectangle([self.S(v) for v in box], radius=self.S(r), fill=(*color, round(alpha)))

    def line(self, p, q, color, width, a):
        self.d.line([self.S(p[0]), self.S(p[1]), self.S(q[0]), self.S(q[1])], fill=(*color, round(255 * a)), width=self.S(width))

    def dot(self, p, r, color, a, ring=None):
        if ring:
            self.d.ellipse([self.S(p[0] - r - 3), self.S(p[1] - r - 3), self.S(p[0] + r + 3), self.S(p[1] + r + 3)],
                           fill=(*ring, round(255 * a)))
        self.d.ellipse([self.S(p[0] - r), self.S(p[1] - r), self.S(p[0] + r), self.S(p[1] + r)], fill=(*color, round(255 * a)))

    def result(self, w, h):
        return self.img.resize((w, h), Image.LANCZOS)


# 各类文字的（主行, 副行）字号，按 1920×1080 设计；产品可在 shots.py 里用 TEXT = dict(card=1.5) 按类型放大
SIZE = {"step": (40, 22), "card": (64, 30), "note": (34, 23), "callout": (28, 20)}
MAXW = {"step": 1300, "card": 1680, "note": 1640, "callout": 720}     # 每类文字一行的最大宽度
SCALE = {}
FITTED = set()     # 被自动折行或缩小过的文字，最后统一提示

def sz(kind):
    k = SCALE.get(kind, 1.0)
    return SIZE[kind][0] * k, SIZE[kind][1] * k

def wrap(P, text, kind, px, maxw):
    if P.text_size(text, kind, px)[0] <= maxw:
        return [text]
    sep = " " if " " in text else ""          # 有空格按词断（英文、中英混排），否则按字断（纯中文）
    lines, cur = [], ""
    for t in (text.split(" ") if sep else list(text)):
        cand = cur + sep + t if cur else t
        if not cur or P.text_size(cand, kind, px)[0] <= maxw:
            cur = cand
        else:
            lines.append(cur)
            cur = t
    return lines + [cur]

def fit(P, text, kind, px, maxw, max_lines=2):
    """太长就折行；折成两行还放不下就逐步缩小字号（最小到 60%）"""
    if not text:
        return [], px
    p = px
    lines = wrap(P, text, kind, p, maxw)
    while len(lines) > max_lines and p > px * 0.6:
        p *= 0.9
        lines = wrap(P, text, kind, p, maxw)
    if len(lines) > 1 or p != px:
        FITTED.add(text)
    return lines, p

def block(P, zh, en, kind, zk="zh_b", ek="en", zc=INK, ec=INK2):
    """中文（主行）在上、英文（副行）在下的文字块：返回 (行列表, 宽, 高)"""
    zp, ep = sz(kind)
    zl, zp = fit(P, zh, zk, zp, MAXW[kind])
    el, ep = fit(P, en, ek, ep, MAXW[kind])
    rows = [(t, zk, zp, zc, zp * 1.25) for t in zl] + [(t, ek, ep, ec, ep * 1.2) for t in el]
    w = max([P.text_size(t, k, px)[0] for t, k, px, _, _ in rows] or [0])
    return rows, w, sum(r[4] for r in rows)

def draw_rows(P, rows, x, y, a, center=None):
    for t, k, px, c, lh in rows:
        tx = center - P.text_size(t, k, px)[0] / 2 if center is not None else x
        P.text((tx, y), t, k, px, c, a)
        y += lh

def draw_step(P, it, a):
    x, y = 56, 48
    rows, w, h = block(P, it["zh"], it["en"], "step")
    hb = max(84, h + 18)
    if it.get("step"):
        P.rect((x, y, x + hb, y + hb), 14, ACCENT, 255 * a)
        num = f"{it['step']:02d}"
        nw, _ = P.text_size(num, "en_b", min(hb, 110) * 0.52)
        P.text((x + hb / 2 - nw / 2, y + hb / 2 - min(hb, 110) * 0.33), num, "en_b", min(hb, 110) * 0.52, (255, 255, 255), a)
        x += hb + 20
    P.rect((x - 16, y, x + w + 20, y + hb), 14, (255, 255, 255), 215 * a)
    draw_rows(P, rows, x, y + (hb - h) / 2, a)

def draw_card(P, it, a):
    rows, w, h = block(P, it["zh"], it["en"], "card", zc=(255, 255, 255), ec=(225, 228, 232))
    y = min(740, 1080 - 190 - h)          # 放大或折行后往上挪，给底部字幕留位置
    P.rect((960 - w / 2 - 40, y - 28, 960 + w / 2 + 40, y + h + 30), 20, (18, 20, 24), 170 * a)
    draw_rows(P, rows, 0, y, a, center=960)

def draw_note(P, it, a):
    rows, w, h = block(P, it["zh"], it["en"], "note", "zh", "en", (255, 255, 255), (220, 224, 230))
    y = 1080 - 70 - h
    P.rect((960 - w / 2 - 34, y - 20, 960 + w / 2 + 34, y + h + 14), 16, (18, 20, 24), 175 * a)
    draw_rows(P, rows, 0, y, a, center=960)

OFF = {"right": (150, -110), "left": (-150, -110), "up": (0, -170), "down": (0, 150)}

def draw_callout(P, it, a, fr):
    x, y, front = it["track"][str(fr)]
    if not front:
        return
    px, py = x * 1920, y * 1080
    rows, w, h = block(P, it["zh"], it["en"], "callout")
    pad = 16
    dx, dy = OFF[it["side"]]
    if it["side"] == "right":
        bx, by = px + dx, py + dy - h / 2
    elif it["side"] == "left":
        bx, by = px + dx - w - 2 * pad, py + dy - h / 2
    elif it["side"] == "up":
        bx, by = px - w / 2 - pad, py + dy - h - pad
    else:
        bx, by = px - w / 2 - pad, py + dy
    bx = min(max(bx, 30), 1920 - 30 - w - 2 * pad)
    by = min(max(by, 150), 1080 - 200 - h - pad)
    cx = min(max(px, bx), bx + w + 2 * pad)          # 引线连到标签边上离锚点最近的点
    cy = min(max(py, by), by + h + pad)
    P.line((px, py), (cx, cy), INK, 3, a)
    P.dot((px, py), 7, ACCENT, a, ring=(255, 255, 255))
    P.rect((bx, by, bx + w + 2 * pad, by + h + pad), 12, (255, 255, 255), 235 * a)
    P.rect((bx, by, bx + 6, by + h + pad), 3, ACCENT, 255 * a)
    draw_rows(P, rows, bx + pad + 2, by + pad * 0.6, a)


def alpha(fr, a, b):
    return max(0.0, min(1.0, (fr - a + 1) / FADE_IN, (b - fr + 1) / FADE_OUT))

def merge_steps(items):
    """相邻 shot 的同一步骤标题合并成一段，避免在镜头切换时闪一下"""
    out = []
    for it in items:
        prev = next((p for p in reversed(out) if p["type"] == it["type"]), None)
        if it["type"] in ("step", "card") and prev and prev["zh"] == it["zh"] and prev["frames"][1] + 1 >= it["frames"][0]:
            prev["frames"][1] = it["frames"][1]
        else:
            out.append(dict(it))
    return out


def main(out):
    tl = json.load(open(os.path.join(out, "timeline.json"), encoding="utf-8"))
    frames_dir, ov_dir = os.path.join(out, "frames"), os.path.join(out, "overlay")
    shutil.rmtree(ov_dir, ignore_errors=True)
    os.makedirs(ov_dir)
    files = sorted(f for f in os.listdir(frames_dir) if f.endswith(".png"))
    w, h = tl["size"]                  # 输出尺寸（渲染帧是超采样的大图）
    SCALE.update(tl.get("text", {}))
    if tl.get("lang") == "en":   # 纯英文：英文升为主行，用英文字体，不留空的第二行
        ALIAS.update(zh="en", zh_b="en_b")
        for it in tl["items"]:
            it["zh"], it["en"] = it["en"], ""
    items = merge_steps(tl["items"])
    seen = {}
    for name in files:
        fr = int(name[2:-4])
        live = [it for it in items if it["frames"][0] <= fr <= it["frames"][1]]
        key = tuple((id(it), round(alpha(fr, *it["frames"]), 2),
                     tuple(it["track"][str(fr)]) if it["type"] == "callout" else None) for it in live)
        dst = os.path.join(ov_dir, name)
        if key in seen:
            try:
                os.link(seen[key], dst)        # 相同画面直接硬链接，省时间和空间
            except OSError:
                shutil.copyfile(seen[key], dst)
            continue
        P = Painter(w, h)
        for it in sorted(live, key=lambda i: ["callout", "note", "step", "card"].index(i["type"])):
            a = alpha(fr, *it["frames"])
            if it["type"] == "step":
                draw_step(P, it, a)
            elif it["type"] == "card":
                draw_card(P, it, a)
            elif it["type"] == "note":
                draw_note(P, it, a)
            else:
                draw_callout(P, it, a, fr)
        P.result(w, h).save(dst)
        seen[key] = dst
    print(f"overlay: {len(files)} frames, {len(set(seen.values()))} unique")
    if FITTED:
        print("提示：下面这些文字一行放不下，已自动折行或缩小字号，看 review 图确认效果；想要更整齐就改短：")
        for t in sorted(FITTED):
            print("  -", t)

