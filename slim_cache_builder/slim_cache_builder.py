"""
slim_cache_builder/slim_cache_builder.py

slim_cache.json を生成する薄い実行部。
計算ロジックは src/slim_cache_builder/、ファイル I/O は src/esal/ に委譲する。

実行方法:
    cd C:\\GitHub\\Pokemon-go-tools
    python slim_cache_builder/slim_cache_builder.py
"""

import sys
from datetime import datetime
from pathlib import Path

# プロジェクトルートを import パスに追加し、src/（esal・library・slim_cache_builder）を解決する
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.esal.iv_strings_reader import (  # noqa: E402
    load_evolution_map_staged,
    load_iv_list_input_raw,
)
from src.esal.pokedex_reader import load_pokedex_full  # noqa: E402
from src.esal.slim_cache_writer import write_slim_cache  # noqa: E402
from src.slim_cache_builder.slim_cache_builder import (  # noqa: E402
    LEAGUE_CAPS,
    build_cache_object,
    calc_slim_entries,
    parse_input,
)


def main() -> None:
    print("=== slim_cache 生成開始 ===")

    # ---- esal：ファイル読み込み ----
    print("pokedex_numbers.txt を読み込み中...")
    pokedex_full = load_pokedex_full()
    print(f"  ポケモン種類数: {len(pokedex_full)}")

    print("evolution_map.txt を読み込み中...")
    evo_map_staged = load_evolution_map_staged()

    print("iv_list_input.txt を解析中...")
    iv_list_lines = load_iv_list_input_raw()

    # ---- features：パース（対象ポケモン×リーグの確定） ----
    target_map = parse_input(iv_list_lines, evo_map_staged, pokedex_full)

    total = sum(len(leagues) for leagues in target_map.values())
    print(f"  計算対象: {len(target_map)}種 × リーグ合計 {total}件")

    # ---- features：IV 全計算 → slim 形式への変換（進捗表示は実行部の責務） ----
    pokemon_entries = []
    count = 0
    # 図鑑番号の昇順で処理する（出力 JSON の pokemon リスト順）
    for name, league_topn in sorted(target_map.items(), key=lambda x: pokedex_full[x[0]]["dex"]):
        base_stat = pokedex_full[name]
        leagues_data = {}

        for lg, topn in league_topn.items():
            count += 1
            print(f"[{count}/{total}] {name} / {lg} (TopN={topn}) 計算中...")
            cap_cp = LEAGUE_CAPS[lg]
            entries = calc_slim_entries(base_stat, cap_cp, topn)
            leagues_data[lg] = {
                "cp_cap": cap_cp,
                "topn": topn,
                "entries": entries,
            }

        pokemon_entries.append(
            {
                "name": name,
                "dex": base_stat["dex"],
                "leagues": leagues_data,
            }
        )

    # ---- features：JSON オブジェクト組み立て ----
    created_at = datetime.now().isoformat(timespec="seconds")
    cache_object = build_cache_object(pokemon_entries, total, created_at)

    # ---- esal：書き込み ----
    write_slim_cache(cache_object)

    print("=== slim_cache 生成完了 ===")


if __name__ == "__main__":
    main()
