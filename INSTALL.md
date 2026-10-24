# 安装指南（写给 agent）

用户让你"按这个文件安装"时，从头到尾照做。每一步都要检查结果，出错就把完整输出给用户看，**不要绕过，也不要改工具代码**。

## 0. 前提

- 你必须能在用户的电脑上执行命令行。做不到就直接告诉用户，然后停下。
- 第一次在一个新目录里运行时，有的 agent 会弹出"是否信任此目录"，请用户确认。

## 1. 安装

1. **git**：没有就先装。Windows 用 `winget install --id Git.Git -e`，macOS 用 `xcode-select --install`。
2. **克隆**：问用户想把工具放在哪里。用户没有特别要求时，Windows 默认放在 `%USERPROFILE%\tools\install-video`，macOS / Linux 默认放在 `~/tools/install-video`。
   ```
   git clone https://github.com/catoncat/install-video <目录>
   ```
   GitHub 连不上（国内网络常见）时，请用户从 https://github.com/catoncat/install-video/archive/refs/heads/main.zip 下载 zip 包，解压到同一个位置。
3. **阅读**：完整读一遍 `SKILL.md` 和 `reference.md`。之后做视频都按 `SKILL.md` 的流程来。每次开始新对话时，也先重新读一遍 `SKILL.md`。
4. **环境**：在工具目录里运行 `setup`。
   - Windows（PowerShell）：`.\video.cmd setup`
   - macOS / Linux：`./video.sh setup`

   没有 Blender 时会自动安装：Windows 用 winget，macOS 用 Homebrew，Linux 用 snap。Windows 安装时系统会弹出权限确认，提前告诉用户点"是"。
   - **成功的标志**：输出里有一行以 `| ok` 结尾。之后 Blender 还会打印一行退出信息，不用管。
   - winget 不可用（老版本 Windows 10）时，请用户从 https://www.blender.org/download/ 下载 Blender 4.4 以上的版本（选 LTS），装完再运行一次 `setup`。Blender 装在非默认位置时，设置环境变量 `BLENDER=<blender 可执行文件路径>`。
   - pip 下载太慢或失败时，设置国内镜像再重试：`PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple`。
   - `setup` 输出里列出了字幕要用的中文和英文字体。如果报找不到字体，把报错原样告诉用户。

## 2. 验证（必须做）

运行示例：`video make kpx2 draft 05a`（Windows 用 `.\video.cmd`，macOS / Linux 用 `./video.sh`）。

然后**打开并查看** `examples/kpx2/out/review/05a_post.jpg`，检查三点：
- 6 张小图各不相同，能看到角柱落下、螺栓拧入的过程；
- 左上角有步骤标题，底部有中英双语字幕；
- 画面完整，没有被放大裁切，也不是全黑。

再把 `examples/kpx2/out/video.mp4` 的位置告诉用户，请用户自己打开看一下。有任何一项不对，就停下来，把情况告诉用户。

## 3. 工作目录

- 工作目录要放在工具目录**之外**，比如 `D:\videos\` 或 `~/videos/`。
- 新建产品：`video init <工作目录>/<产品名>`。产品名只能用英文字母、数字和下划线，例如 `zfold_house`。
- 用户的资料（图片、PDF、表格、视频）放在 `<工作目录>/资料/`。
- 用户的需求文字存成 `<工作目录>/requirements.md`。

## 4. 开始

按 `SKILL.md` 的流程，和用户一起：整理资料 → 推导安装步骤 → 写分镜（先给用户看，同意后再建模和出片）。

**每次正式出片前**，先运行 `git -C <工具目录> pull` 更新工具（用的是 zip 包就重新下载）。
