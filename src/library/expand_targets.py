"""
src/library/expand_targets.py

O/M/L 展開の共通ロジック（仕様書 spec/library.md 3章）。
iv_strings_generator アプリと slim_cache_builder ツールの両方から呼ばれる。

Streamlit・ファイル読み込みに依存しない純粋関数。
進化マップは呼び出し元から受け取る（esal の load_evolution_map_staged の返り値形式）。
"""

from __future__ import annotations


def expand_targets(
    original_name: str,
    targets: list[str],
    evo_map_staged: list[list[list[str]]],
) -> list[str]:
    """
    O/M/L 指定を展開して、対象ポケモン名のリストを返す（仕様書 library.md 3章）。

    展開ルール（library.md 3.3・3.4）:
      O → 入力ポケモン本人のみ。
      M → 3段以上なら2番目の段（中間進化）、2段なら最終段（= L と同じ）。
      L → 最終段。
      指定した段に分岐（スラッシュ）が複数あるときは、その段の全ポケモンを対象にする。
      evo_map 未収録のポケモンは本人のみを対象にする（O 扱い）。

    Args:
        original_name: 展開の起点となるポケモン名。
        targets: 対象指定のリスト（'O'・'M'・'L'、重複除去済みを想定）。
        evo_map_staged: 段構造を保持した進化マップ（load_evolution_map_staged の返り値）。
                        各要素は1ファミリー = [[段1メンバー...], [段2メンバー...], ...]。

    Returns:
        展開後のポケモン種名リスト。重複は初出優先で除去。
        順序は「対象指定の指定順 → 各段はマップ収録順」（library.md 3.2）。
    """
    # evo_map_staged から original_name が属するファミリーを検索する
    family_stages: list[list[str]] | None = None
    for stages in evo_map_staged:
        for stage in stages:
            if original_name in stage:
                family_stages = stages
                break
        if family_stages is not None:
            break

    result: list[str] = []
    for t in targets:
        if t == "O":
            result.append(original_name)
        elif t == "L":
            if family_stages is None:
                # 進化しないポケモン（evo_map 未収録）→ 本人のみ（O 扱い）
                result.append(original_name)
            else:
                # 最終段の全メンバー（分岐があれば全枝）を対象にする
                result.extend(family_stages[-1])
        elif t == "M":
            if family_stages is None:
                result.append(original_name)
            elif len(family_stages) >= 3:
                # 3段以上 → 2番目の段（インデックス 1）の全メンバー
                result.extend(family_stages[1])
            else:
                # 2段 → 最終段（= L と同じ）
                result.extend(family_stages[-1])

    # 順序を保ちつつ重複を除去する（library.md 3.2「初出優先」）
    seen: set[str] = set()
    unique: list[str] = []
    for name in result:
        if name not in seen:
            unique.append(name)
            seen.add(name)
    return unique
