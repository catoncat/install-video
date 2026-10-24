"""引擎给用户看的摘要信息统一用 say() 打印（带 "» " 前缀）。
video make 默认只把这些行显示在终端，Blender 的逐帧日志写进 out/log.txt。"""
import sys

PREFIX = "» "

def say(*args):
    print(PREFIX + " ".join(str(a) for a in args), flush=True)
    sys.stdout.flush()
