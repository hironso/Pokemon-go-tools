"""Stop フック：Claude Code の作業終了時に mypy / pytest を全体に実行する。

Claude Code が「完了」しようとした瞬間に自動実行される（settings.json 参照）。
失敗があれば終了コード 2 で Claude を作業に引き戻し、自己修正させる。
全チェックが通って初めて作業を終えられる ＝ 品質チェックの機械的強制。

無限ループ防止:
  フックが Claude を引き戻した後の再終了時は、入力 JSON の stop_hook_active が
  True になる。その場合に再びブロックし続けると修正不能な問題で永久ループするため、
  2回目は警告だけ出して通す（最終判断は人間の検収に委ねる）。
"""

import json
import subprocess
import sys

# Windows の標準出力・標準エラーは既定が cp932 のため、UTF-8 の日本語メッセージが
# 文字化けする。フックが Claude へ返す指示（テストを弱めるな 等）が読めないと
# 自己修正が正しく働かないため、出力を UTF-8 に再設定する。
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}

    # ループ防止：一度引き戻した後の終了はブロックしない
    already_blocked_once = payload.get("stop_hook_active", False)

    failures: list[str] = []

    # mypy：型チェック（対象は src/ のみ。Streamlit のエントリポイント
    # （id_generator/app.py 等）は src/ の外にある薄い UI 層のため対象外とする）。
    # encoding="utf-8"：Windows 既定の cp932 で UTF-8 出力を読むと
    # UnicodeDecodeError で落ちるため必ず明示する。
    mypy = subprocess.run(
        ["mypy", "src/"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if mypy.returncode != 0:
        failures.append(f"--- mypy 失敗 ---\n{mypy.stdout}")

    # pytest：全テスト実行（-q で簡潔表示）
    pytest = subprocess.run(
        ["pytest", "tests/", "-q"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if pytest.returncode != 0:
        failures.append(f"--- pytest 失敗 ---\n{pytest.stdout}")

    if not failures:
        return 0

    message = "\n".join(failures)

    if already_blocked_once:
        # 2回目：永久ループを避けるため通すが、未解決である事実を明示する
        print(
            "警告: 品質チェックが未解決のまま作業を終了します。"
            "完了報告に失敗内容を必ず記載してください。\n" + message,
            file=sys.stderr,
        )
        return 0

    # 1回目：Claude を引き戻して自己修正させる
    print(
        "品質チェックが失敗しています。修正してから完了してください。\n"
        "注意: テスト側を弱める変更（assert の緩和・skip 化・削除）は禁止。\n"
        "テストが誤りと判断した場合は変更せず、理由を報告して確認を求めること。\n"
        + message,
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
    