# install-video

一个 agent skill：用 Blender 把产品资料做成 3D 安装视频。默认产出阿里国际站等 B2B 平台用的营销视频：安装动画 + 定制选项 + 应用场景 + 询盘结尾，英文字幕，16:9 / 1:1 / 9:16 三种画幅，60 / 30 / 15 秒三个版本，程序合成背景音乐。也能做中英双语的安装说明视频。
由 agent 和用户讨论后编写产品模型与分镜，引擎负责渲染、字幕、合成和自查。

## 安装

```bash
git clone https://github.com/catoncat/install-video <任意目录>/install-video
```
- Claude Code：克隆到 `~/.claude/skills/install-video`，会自动识别为 skill。
- 其他 agent（Codex、Cursor 等）：直接对它说"按 https://github.com/catoncat/install-video/blob/main/INSTALL.md 安装"。agent 需要能在本机执行命令。

然后运行一次环境安装（最后一行是 `SETUP OK` 才算成功）。唯一的依赖是 Blender（已在 5.2.x 上测试，4.4 以上应该可用），找不到会自动安装（Windows 用 winget，macOS 用 Homebrew，Linux 用 snap）：

```bash
<目录>/install-video/video.sh setup     # macOS / Linux
<目录>\install-video\video.cmd setup    # Windows
```

更新：`git -C <目录>/install-video pull`

## 用法

见 [SKILL.md](SKILL.md)（工作流程）和 [reference.md](reference.md)（API）。示例产品在 `examples/kpx2/`（快拼箱 2.0）。

```
video init <工作目录>/<产品名>          新建产品（国际站营销模板；加 kpx2 是说明版示例）
video make <产品目录> preview|final [shot前缀] [--version main|detail|ad]
```

状态：v0.1，正在快速迭代。
