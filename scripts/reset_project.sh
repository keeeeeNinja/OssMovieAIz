#!/bin/bash
# プロジェクト初期化スクリプト
# 次の動画制作に入る前に実行し、前回の動画のコード・素材をリセットする

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== プロジェクト初期化 ==="
echo "Project: $PROJECT_DIR"
echo ""

# 1. AdVideo.tsx を空テンプレートに戻す（B+共通アーキテクチャ）
echo "[1/3] AdVideo.tsx をテンプレートにリセット..."
cat <<'EOF' > "$PROJECT_DIR/src/compositions/AdVideo.tsx"
import React from "react";
import { AdVideoBase, Clip } from "./shared";

// bs_composition.json から telop-baseline / telop-design がここを上書きする
const clips: Clip[] = [];

export const AdVideo: React.FC = () => (
  <AdVideoBase clips={clips} />
);

export const adVideoClips = clips;
export const adVideoTotalFrames = clips.reduce((s, c) => s + c.durationInFrames, 0) || 30;
EOF
echo "  -> done"

# 2. public/ から前回の動画素材を削除（bgm/narrationも含む）
echo "[2/3] public/ の動画・音声素材をクリア..."
rm -f "$PROJECT_DIR"/public/scene_*.mp4
rm -f "$PROJECT_DIR"/public/bgm.mp3
rm -f "$PROJECT_DIR"/public/narration.wav
echo "  -> done"

# 3. 作業中動画/ をクリア（theme1〜5フォルダは再作成）
echo "[3/3] 作業中動画/ をクリア..."
rm -rf "$PROJECT_DIR/作業中動画/"
mkdir -p "$PROJECT_DIR/作業中動画/theme1"
mkdir -p "$PROJECT_DIR/作業中動画/theme2"
mkdir -p "$PROJECT_DIR/作業中動画/theme3"
mkdir -p "$PROJECT_DIR/作業中動画/theme4"
mkdir -p "$PROJECT_DIR/作業中動画/theme5"
echo "  -> done"

echo ""
echo "=== 初期化完了 ==="
echo "AdVideo.tsx: テンプレート状態"
echo "public/: 素材クリア済み"
echo "作業中動画/: theme1〜5フォルダ作成済み"
echo ""
echo "次の動画制作を始めてください。"
