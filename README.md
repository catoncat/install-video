# install-video

一个 agent skill：用 Blender 把产品资料做成 3D 安装 / 组装说明视频，带中英双语字幕和程序合成的背景音乐。
由 agent 和用户讨论后编写产品模型与分镜，引擎负责渲染、字幕、合成和自查。

## 安装

```bash
git clone https://github.com/catoncat/install-video <任意目录>/install-video
```
- Claude Code：克隆到 `~/.claude/skills/install-video`，会自动识别为 skill。
- Codex、Cursor 等其他 agent：克隆到任意目录，agent 会读 `AGENTS.md`；或者直接告诉 agent 先读 `SKILL.md`。agent 需要能在本机执行命令。

然后运行一次环境安装。唯一的依赖是 Blender 4.4 以上，找不到会自动安装（Windows 用 winget，macOS 用 Homebrew，Linux 用 snap）：

```bash
<目录>/install-video/video.sh setup     # macOS / Linux
<目录>\install-video\video.cmd setup    # Windows
```

更新：`git -C <目录>/install-video pull`

## 用法

见 [SKILL.md](SKILL.md)（工作流程）和 [reference.md](reference.md)（API）。示例产品在 `examples/kpx2/`（快拼箱 2.0）。

```
video init <工作目录>/<产品名>          新建产品
video make <产品目录> draft|preview|final [shot前缀]
```

状态：v0.1，正在快速迭代。
