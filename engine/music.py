"""程序合成背景音乐（无版权问题）：铺底和弦 + 拨弦琶音 + 低音 + 轻鼓，带简单混响。

generate(path, seconds, bpm=96, root=48, seed=1)  写出 44.1kHz 立体声 WAV。
在产品的 shots.py 里可以写 MUSIC = dict(bpm=..., root=..., seed=...) 调整；产品目录放 music.* 则直接用那个文件。
只依赖 numpy（Blender 自带）。
"""
import wave
import numpy as np

SR = 44100
# I – vi – IV – V（大调，明亮、中性，适合说明类视频）。数字是相对根音的半音
PROGRESSION = [(0, 4, 7, 11), (-3, 0, 4, 7), (-7, -3, 0, 4), (-5, -1, 2, 7)]


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)

def env(n, a, r):
    """线性起音 a 秒、指数释放到结尾"""
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-3))
    return e * np.exp(-np.maximum(0, t - a) / max(r, 1e-3))

def tone(f, n, shape="sine", detune=0.0):
    t = np.arange(n) / SR
    ph = 2 * np.pi * f * (1 + detune) * t
    if shape == "sine":
        return np.sin(ph)
    if shape == "tri":
        return 2 / np.pi * np.arcsin(np.sin(ph))
    return np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph)   # "pluck"

def reverb(x, seconds=1.8, mix=0.25, seed=7):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 4.0)
    ir[: int(0.02 * SR)] = 0
    ir /= np.sqrt((ir ** 2).sum())
    m = len(x) + n
    size = 1 << (m - 1).bit_length()
    wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x)]
    return x * (1 - mix) + wet * mix

def place(buf, start, sig, gain=1.0):
    s = int(start * SR)
    if s >= len(buf):
        return
    e = min(len(buf), s + len(sig))
    buf[s:e] += sig[: e - s] * gain


def generate(path, seconds, bpm=96, root=48, seed=1):
    rng = np.random.default_rng(seed)
    beat = 60 / bpm
    bar = 4 * beat
    n = int((seconds + 3) * SR)
    pad, arp_l, arp_r, bass, drums = (np.zeros(n) for _ in range(5))
    bars = int(seconds / bar) + 2
    for b in range(bars):
        t0 = b * bar
        chord = PROGRESSION[b % 4]
        # 铺底：每个和弦音两个略微失谐的三角波
        ln = int(bar * SR * 1.15)
        for iv in chord:
            f = hz(root + 12 + iv)
            s = (tone(f, ln, "tri", 0.002) + tone(f, ln, "tri", -0.002)) * env(ln, 0.5, bar * 0.9)
            place(pad, t0, s, 0.08)
        # 琶音：第 2 小节后进入，八分音符，在和弦音上上下行
        if b >= 2:
            notes = [chord[0], chord[1], chord[2], chord[3], chord[2] + 12, chord[3], chord[2], chord[1]]
            for k, iv in enumerate(notes):
                ln = int(beat * SR * 1.6)
                s = tone(hz(root + 24 + iv), ln, "pluck") * env(ln, 0.004, 0.22)
                vel = 0.10 + 0.03 * rng.random()
                place(arp_l if k % 2 == 0 else arp_r, t0 + k * beat / 2, s, vel)
        # 低音：一拍和三拍
        if b >= 2:
            for k in (0, 2):
                ln = int(beat * SR * 1.8)
                s = np.tanh(1.5 * tone(hz(root - 12 + chord[0]), ln)) * env(ln, 0.01, 0.5)
                place(bass, t0 + k * beat, s, 0.15)
        # 鼓：第 4 小节到结尾前 2 小节，轻柔的底鼓 + 反拍镲
        if 4 <= b < bars - 3:
            for k in range(4):
                if k in (0, 2):
                    ln = int(0.25 * SR)
                    t = np.arange(ln) / SR
                    kick = np.sin(2 * np.pi * (50 * t + 60 * (1 - np.exp(-t * 30)) / 30)) * np.exp(-t * 14)
                    place(drums, t0 + k * beat, kick, 0.26)
                ln = int(0.05 * SR)
                hat = np.diff(rng.standard_normal(ln + 1)) * np.exp(-np.arange(ln) / SR * 90)
                place(drums, t0 + k * beat + beat / 2, hat, 0.035)
    music = reverb(pad + 0.5 * (arp_l + arp_r), 2.2, 0.35)
    left = music + 0.5 * arp_l * 0.6 + bass + drums
    right = music + 0.5 * arp_r * 0.6 + bass + drums
    st = np.stack([left, right], 1)[: int(seconds * SR)]
    # 首尾淡入淡出，峰值归一到 -3 dBFS
    fade = np.ones(len(st))
    fi, fo = int(1.5 * SR), int(3.0 * SR)
    fade[:fi] = np.linspace(0, 1, fi)
    fade[-fo:] = np.linspace(1, 0, fo)
    st *= fade[:, None]
    st *= 10 ** (-3 / 20) / max(1e-9, np.abs(st).max())
    pcm = (st * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path
