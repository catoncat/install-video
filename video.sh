#!/usr/bin/env bash
# 安装说明视频工具（macOS / Linux）。用法：
#   ./video.sh setup                        首次使用：没有 Blender 就安装（macOS 用 Homebrew，Linux 用 snap），再装 Pillow
#   ./video.sh make kpx2 preview [05a,05b]  出片
#   ./video.sh compose kpx2                 只重做字幕和合成
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

find_blender() {
  [[ -n "${BLENDER:-}" ]] && return
  BLENDER=$(command -v blender || true)
  [[ -z "$BLENDER" && -x /Applications/Blender.app/Contents/MacOS/Blender ]] && BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
  [[ -z "$BLENDER" && -x /snap/bin/blender ]] && BLENDER=/snap/bin/blender
  return 0
}
find_blender
if [[ -z "$BLENDER" && "${1:-}" == setup ]]; then
  echo "Blender not found, installing ..."
  if [[ "$(uname)" == Darwin ]]; then brew install --cask blender; else sudo snap install blender --classic; fi
  find_blender
fi
if [[ -z "$BLENDER" ]]; then
  echo 'Blender not found. Run "./video.sh setup", or install Blender 4.4+ and set BLENDER=/path/to/blender'
  exit 1
fi
exec "$BLENDER" -b --factory-startup --python-exit-code 1 -P "$HERE/engine/cli.py" -- "$@"
