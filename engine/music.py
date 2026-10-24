"""程序合成背景音乐（无版权问题）：按视频长度排成 前奏 → A → B → A' → 尾声，
各段换和弦进行、琶音型、鼓和旋律，避免同一小节循环到底；按平均响度归一化到背景音乐的音量。

generate(path, seconds, bpm=96, root=48, seed=1, volume=0)  写出 44.1kHz 立体声 WAV。
volume 是相对默认音量的 dB 调整（如 -3 更轻、+3 更响）。
在产品的 shots.py 里可以写 MUSIC = dict(bpm=..., root=..., seed=..., volume=...)；产品目录放 music.* 则直接用那个文件。
只依赖 numpy（Blender 自带）。
"""
import wave
import numpy as np

SR = 44100
TARGET_RMS_DB = -26.0     # 背景音乐的平均响度（约等于 -24 LUFS），不和画面抢
PEAK_DB = -6.0            # 峰值上限

# 和弦进行（相对根音的半音），大调，明亮中性
PROG = {
    "A": [(0, 4, 7, 11), (-5, -1, 2, 7), (-3, 0, 4, 7), (-7, -3, 0, 4)],     # I – V – vi – IV
    "B": [(-3, 0, 4, 7), (-7, -3, 0, 4), (0, 4, 7, 11), (-5, -1, 2, 5)],     # vi – IV – I – V7
    "C": [(-7, -3, 0, 4), (-5, -1, 2, 7), (-8, -5, -1, 2), (-3, 0, 4, 7)],   # IV – V – iii – vi
}
# 每段：和弦进行、琶音型、是否有鼓 / 旋律、琶音力度
SECTIONS = {
    "intro": dict(prog="A", arp=None, drums=False, melody=False, level=0.0),
    "A": dict(prog="A", arp="up", drums=False, melody=False, level=0.8),
    "B": dict(prog="B", arp="updown16", drums=True, melody=True, level=1.0),
    "A2": dict(prog="C", arp="broken", drums=True, melody=True, level=0.95),
    "outro": dict(prog="A", arp="up", drums=False, melody=False, level=0.5),
}


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)

def env(n, a, r):
    """线性起音 a 秒、指数释放"""
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-3)) * np.exp(-np.maximum(0, t - a) / max(r, 1e-3))

def tone(f, n, shape="sine", detune=0.0):
    t = np.arange(n) / SR
    ph = 2 * np.pi * f * (1 + detune) * t
    if shape == "sine":
        return np.sin(ph)
    if shape == "tri":
        return 2 / np.pi * np.arcsin(np.sin(ph))
    if shape == "bell":
        return np.sin(ph) + 0.4 * np.sin(2.76 * ph) * np.exp(-t * 6) + 0.2 * np.sin(5.4 * ph) * np.exp(-t * 12)
    return np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph)   # pluck

def reverb(x, seconds=1.8, mix=0.25, seed=7):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 4.0)
    ir[: int(0.02 * SR)] = 0
    ir /= np.sqrt((ir ** 2).sum())
    size = 1 << (len(x) + n - 1).bit_length()
    wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x)]
    return x * (1 - mix) + wet * mix

def place(buf, start, sig, gain=1.0):
    s = int(start * SR)
    if s >= len(buf):
        return
    e = min(len(buf), s + len(sig))
    buf[s:e] += sig[: e - s] * gain

def layout(bars):
    """按总小节数分段：短片段也保留 起 → 主体 → 收 的结构"""
    if bars <= 6:
        return ["intro"] + ["A"] * max(1, bars - 2) + ["outro"]
    intro, outro = (1, 1) if bars < 12 else (2, 2)
    body = bars - intro - outro
    a = max(2, round(body * 0.35))
    b = max(2, round(body * 0.35))
    a2 = max(0, body - a - b)
    return ["intro"] * intro + ["A"] * a + ["B"] * b + ["A2"] * a2 + ["outro"] * outro

def arp_notes(chord, kind):
    up = [chord[0], chord[1], chord[2], chord[3]]
    if kind == "up":
        return [(k * 0.5, n) for k, n in enumerate(up + [chord[2] + 12, chord[3], chord[2], chord[1]])]
    if kind == "updown16":
        seq = up + [chord[1] + 12, chord[3], chord[2], chord[1]]
        return [(k * 0.25, n) for k, n in enumerate(seq + seq[::-1])]
    # broken：切分节奏
    return [(t, n) for t, n in zip((0, 0.75, 1.5, 2, 2.75, 3.5), (chord[0], chord[2], chord[1] + 12, chord[3], chord[2], chord[1]))]


def generate(path, seconds, bpm=96, root=48, seed=1, volume=0.0):
    rng = np.random.default_rng(seed)
    beat = 60 / bpm
    bar = 4 * beat
    n = int((seconds + 3) * SR)
    pad, arp_l, arp_r, bass, drums, mel = (np.zeros(n) for _ in range(6))
    bars = int(np.ceil(seconds / bar)) + 1
    plan = layout(bars)
    motif = rng.choice([0, 1, 2, 3], size=8)          # 旋律动机：每段复用、按和弦移调
    for b, sec_name in enumerate(plan):
        sec = SECTIONS[sec_name]
        t0 = b * bar
        chord = PROG[sec["prog"]][b % 4]
        last_bar_of_section = b + 1 >= len(plan) or plan[b + 1] != sec_name
        # 铺底：两个略失谐的三角波
        ln = int(bar * SR * 1.15)
        for iv in chord:
            f = hz(root + 12 + iv)
            place(pad, t0, (tone(f, ln, "tri", 0.002) + tone(f, ln, "tri", -0.002)) * env(ln, 0.5, bar * 0.9), 0.07)
        # 琶音
        if sec["arp"]:
            octave = 24 if sec_name != "A2" else 36
            for k, (tb, iv) in enumerate(arp_notes(chord, sec["arp"])):
                ln = int(beat * SR * 1.4)
                s = tone(hz(root + octave + iv), ln, "pluck") * env(ln, 0.004, 0.2)
                vel = (0.08 + 0.04 * rng.random()) * sec["level"]
                place(arp_l if k % 2 == 0 else arp_r, t0 + tb * beat, s, vel)
        # 低音：A 段一、三拍；B 段加八分推动
        if sec_name not in ("intro",):
            hits = (0, 2) if sec_name in ("A", "outro") else (0, 1.5, 2, 3.5)
            for k in hits:
                ln = int(beat * SR * 1.6)
                place(bass, t0 + k * beat, np.tanh(1.5 * tone(hz(root - 12 + chord[0]), ln)) * env(ln, 0.01, 0.45), 0.13)
        # 旋律：B / A2 段，铃音，两拍一个音
        if sec["melody"]:
            for k in range(2):
                iv = chord[motif[(b * 2 + k) % len(motif)]] + 24
                ln = int(beat * SR * 2.2)
                place(mel, t0 + k * 2 * beat, tone(hz(root + 12 + iv), ln, "bell") * env(ln, 0.01, 0.7), 0.06)
        # 鼓：底鼓一三拍、拍手二四拍、反拍镲；段落最后一小节加镲片过门
        if sec["drums"]:
            for k in range(4):
                if k in (0, 2):
                    ln = int(0.25 * SR)
                    t = np.arange(ln) / SR
                    place(drums, t0 + k * beat, np.sin(2 * np.pi * (50 * t + 2 * (1 - np.exp(-t * 30)))) * np.exp(-t * 14), 0.2)
                else:
                    ln = int(0.12 * SR)
                    place(drums, t0 + k * beat, rng.standard_normal(ln) * np.exp(-np.arange(ln) / SR * 35), 0.03)
                hat_n = 2 if not last_bar_of_section or k < 3 else 4
                for h in range(hat_n):
                    ln = int(0.04 * SR)
                    hat = np.diff(rng.standard_normal(ln + 1)) * np.exp(-np.arange(ln) / SR * 90)
                    place(drums, t0 + k * beat + (h + 0.5) * beat / hat_n, hat, 0.02 + 0.01 * (hat_n == 4))
    wet = reverb(pad + 0.5 * (arp_l + arp_r) + mel, 2.2, 0.35)
    left = wet + 0.3 * arp_l + bass + drums
    right = wet + 0.3 * arp_r + bass + drums
    st = np.stack([left, right], 1)[: int(seconds * SR)]
    fade = np.ones(len(st))
    fi, fo = int(min(1.5, seconds / 6) * SR), int(min(3.0, seconds / 4) * SR)
    fade[:fi] = np.linspace(0, 1, fi)
    fade[-fo:] = np.linspace(1, 0, fo)
    st *= fade[:, None]
    # 按平均响度归一化（背景音乐不该按峰值拉满），再限制峰值
    rms = np.sqrt(np.mean(st ** 2)) + 1e-9
    st *= 10 ** ((TARGET_RMS_DB + volume) / 20) / rms
    peak = np.abs(st).max()
    if peak > 10 ** (PEAK_DB / 20):
        st *= 10 ** (PEAK_DB / 20) / peak
    pcm = (np.clip(st, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path
