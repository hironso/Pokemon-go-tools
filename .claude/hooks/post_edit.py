"""PostToolUse フック：編集されたファイルに black / ruff を即時適用する。

Claude Code がファイルを Edit / Write するたびに自動実行される（settings.json 参照）。
対象は .py のみ。軽いチェックだけをここで行い、重いチェック（mypy / pytest）は
作業終了時の on_stop.py に任せる（編集のたびに重い処理を回すと作業全体が遅くなるため）。

終了コードの意味（Claude Code のフック仕様）:
  0 = 問題なし
  2 = 問題あり（stderr の内容が Claude にフィードバックされ、自己修正を促す）
"""

import json
import subprocess
import sys

# Windows の標準出力・標準エラーは既定が cp932 のため、UTF-8 の日本語メッセージが
# 文字化けする。ruff 違反を Claude へ返すメッセージが読めるよう UTF-8 に再設定する。
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def main() -> int:
    # フックは標準入力で JSON を受け取る（どのツールが・どのファイルを操作したか）
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # 入力が読めない場合はブロックしない（フック自体の故障で作業を止めない）

    file_path = payload.get("tool_input", {}).get("file_path", "")

    # Python ファイル以外（.md, .toml 等）はチェック対象外
    if not file_path.endswith(".py"):
        return 0

    # black：整形（-q で出力を抑制。整形は自動適用なので失敗扱いにしない）
    # encoding="utf-8"：Windows 既定の cp932 だと UTF-8 出力（日本語）を
    # デコードできず UnicodeDecodeError で落ちるため必ず明示する。
    subprocess.run(
        ["black", "-q", file_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    # ruff：リント（--fix で自動修正できるものは直す。残った違反は Claude に返す）
    result = subprocess.run(
        ["ruff", "check", "--fix", file_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        print(f"ruff 違反が残っています:\n{result.stdout}", file=sys.stderr)
        return 2  # Claude に違反内容をフィードバックして修正させる

    return 0


if __name__ == "__main__":
    sys.exit(main())
    