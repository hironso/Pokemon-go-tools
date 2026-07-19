"""
src/slim_cache_builder/slim_cache_builder.py

slim_cache_builder 固有の純粋ロジック（features 層）。
ファイル I/O・datetime・print 依存なし。すべての関数は同じ入力に対して常に同じ出力を返す。
"""

from __future__ import annotations

import math
from typing import Any

from src.library.expand_targets import expand_targets

# ============================================================
# 定数
# ============================================================

SCRIPT_VERSION = "1.0"

# リーグ名 → CP 上限（None はマスターリーグ：上限なし）
LEAGUE_CAPS: dict[str, int | None] = {
    "S": 1500,
    "H": 2500,
    "M": None,
}

# レベル → CPM テーブル（ゲーム内の公式値）
CPM: dict[float, float] = {
    1.0: 0.094,
    1.5: 0.135137432,
    2.0: 0.16639787,
    2.5: 0.192650919,
    3.0: 0.21573247,
    3.5: 0.236572661,
    4.0: 0.25572005,
    4.5: 0.273530381,
    5.0: 0.29024988,
    5.5: 0.306057377,
    6.0: 0.3210876,
    6.5: 0.335445036,
    7.0: 0.34921268,
    7.5: 0.362457751,
    8.0: 0.37523559,
    8.5: 0.387592406,
    9.0: 0.39956728,
    9.5: 0.411193551,
    10.0: 0.42250001,
    10.5: 0.432926419,
    11.0: 0.44310755,
    11.5: 0.4530599578,
    12.0: 0.46279839,
    12.5: 0.472336083,
    13.0: 0.48168495,
    13.5: 0.4908558,
    14.0: 0.49985844,
    14.5: 0.508701765,
    15.0: 0.51739395,
    15.5: 0.525942511,
    16.0: 0.53435433,
    16.5: 0.542635767,
    17.0: 0.55079269,
    17.5: 0.558830576,
    18.0: 0.56675452,
    18.5: 0.574569153,
    19.0: 0.58227891,
    19.5: 0.589887917,
    20.0: 0.59740001,
    20.5: 0.604818814,
    21.0: 0.61215729,
    21.5: 0.619404122,
    22.0: 0.62656713,
    22.5: 0.633649143,
    23.0: 0.64065295,
    23.5: 0.647580967,
    24.0: 0.65443563,
    24.5: 0.661219252,
    25.0: 0.667934,
    25.5: 0.674581896,
    26.0: 0.68116492,
    26.5: 0.687684904,
    27.0: 0.69414365,
    27.5: 0.70054287,
    28.0: 0.70688421,
    28.5: 0.713169109,
    29.0: 0.71939909,
    29.5: 0.725575614,
    30.0: 0.7317,
    30.5: 0.734741009,
    31.0: 0.73776948,
    31.5: 0.740785574,
    32.0: 0.74378943,
    32.5: 0.746781211,
    33.0: 0.74976104,
    33.5: 0.752729087,
    34.0: 0.75568551,
    34.5: 0.758630378,
    35.0: 0.76156384,
    35.5: 0.764486065,
    36.0: 0.76739717,
    36.5: 0.770297266,
    37.0: 0.7731865,
    37.5: 0.776064962,
    38.0: 0.77893275,
    38.5: 0.781790055,
    39.0: 0.784637,
    39.5: 0.787473608,
    40.0: 0.7903,
    40.5: 0.792803968,
    41.0: 0.79530001,
    41.5: 0.797803922,
    42.0: 0.8003,
    42.5: 0.802803893,
    43.0: 0.8053,
    43.5: 0.807803866,
    44.0: 0.81029999,
    44.5: 0.81280383,
    45.0: 0.81529999,
    45.5: 0.817803799,
    46.0: 0.82029999,
    46.5: 0.822803751,
    47.0: 0.82529999,
    47.5: 0.827803694,
    48.0: 0.83029999,
    48.5: 0.832803687,
    49.0: 0.83529999,
    49.5: 0.83780365,
    50.0: 0.84029999,
    50.5: 0.842803624,
    51.0: 0.8453,
}


# ============================================================
# バケット変換（仕様書 4章）
# ============================================================


def iv_to_bucket(iv: int) -> int:
    """攻撃・防御・HP の IV（0〜15）を 5段階バケット（0〜4）に変換する。

    バケット定義: 0=IV0, 1=IV1〜5, 2=IV6〜10, 3=IV11〜14, 4=IV15
    """
    if iv == 0:
        return 0
    elif iv <= 5:
        return 1
    elif iv <= 10:
        return 2
    elif iv <= 14:
        return 3
    else:
        return 4


# ============================================================
# CP / SCP 計算
# ============================================================


def calc_cp(
    base_atk: int,
    base_def: int,
    base_sta: int,
    iv_atk: int,
    iv_def: int,
    iv_hp: int,
    level: float,
) -> int:
    """指定レベル・IV の CP を計算して返す（ゲーム内の計算式に準拠）。"""
    cpm = CPM[level]
    return math.floor(
        (
            (base_atk + iv_atk)
            * math.sqrt(base_def + iv_def)
            * math.sqrt(base_sta + iv_hp)
            * (cpm**2)
        )
        / 10.0
    )


def calc_stats(
    base_atk: int,
    base_def: int,
    base_sta: int,
    iv_atk: int,
    iv_def: int,
    iv_hp: int,
    level: float,
) -> tuple[float, float, int]:
    """指定レベル・IV の実数値（攻撃・防御・HP）を返す。HP は floor 済み整数。"""
    cpm = CPM[level]
    atk = (base_atk + iv_atk) * cpm
    deff = (base_def + iv_def) * cpm
    hp = math.floor((base_sta + iv_hp) * cpm)
    return atk, deff, hp


def calc_scp(atk: float, deff: float, hp: int) -> int:
    """SCP（ステータス積のスコア）を計算して返す。"""
    return int(math.floor(((atk * deff * hp) ** (2.0 / 3.0)) / 10.0))


def best_within_cap(
    base_atk: int,
    base_def: int,
    base_sta: int,
    iv_atk: int,
    iv_def: int,
    iv_hp: int,
    cap_cp: int | None,
) -> dict[str, float | int] | None:
    """CP 上限以下で SCP が最大となるレベルを探索して返す。

    cap_cp=None はマスターリーグ（上限なし）。上限を超えた時点で探索を打ち切る。
    SCP が 1 つも得られない場合（すべてのレベルで CP 超過など）は None を返す。
    """
    best: dict[str, float | int] | None = None
    # 0.5 刻みのレベルを昇順に走査する（CPM テーブルに含まれるレベルのみ）
    for level in [x * 0.5 for x in range(2, 103)]:
        if level not in CPM:
            continue
        cp = calc_cp(base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, level)
        if cap_cp is not None and cp > cap_cp:
            break  # レベルが上がると CP は単調増加するため、超えたら以降は不要
        atk, deff, hp = calc_stats(base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, level)
        scp = calc_scp(atk, deff, hp)
        if best is None or scp > best["scp"]:
            best = {
                "level": level,
                "cp": cp,
                "atk": atk,
                "def": deff,
                "hp": hp,
                "scp": scp,
            }
    return best


# ============================================================
# 全 IV 計算 → TopN 件を slim 形式に変換
# ============================================================


def calc_slim_entries(
    base_stat: dict[str, int],
    cap_cp: int | None,
    topn: int,
) -> list[str]:
    """対象ポケモン×リーグの全 4096 通りの IV を計算し、TopN 件を slim 形式で返す。

    slim 形式（仕様書 4章）: "rank,atk_bucket,def_bucket,hp_bucket,atk_real"
    SCP 降順・攻撃実数値降順・CP 降順・レベル降順でソートしてから TopN に絞る。
    """
    base_atk = base_stat["atk_base"]
    base_def = base_stat["def_base"]
    base_sta = base_stat["hp_base"]

    results: list[dict[str, float | int]] = []
    for iv_atk in range(16):
        for iv_def in range(16):
            for iv_hp in range(16):
                best = best_within_cap(
                    base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, cap_cp
                )
                if best is None:
                    continue
                results.append(
                    {
                        "iv_atk": iv_atk,
                        "iv_def": iv_def,
                        "iv_hp": iv_hp,
                        "atk": best["atk"],
                        "scp": best["scp"],
                        "cp": best["cp"],
                        "level": best["level"],
                    }
                )

    # SCP → 攻撃実数値 → CP → レベル の優先順位で降順ソート
    results.sort(
        key=lambda x: (x["scp"], x["atk"], x["cp"], x["level"]),
        reverse=True,
    )

    # TopN 件に絞ってから slim 形式（CSV 文字列）に変換する
    slim: list[str] = []
    for rank, r in enumerate(results[:topn], 1):
        atk_b = iv_to_bucket(int(r["iv_atk"]))
        def_b = iv_to_bucket(int(r["iv_def"]))
        hp_b = iv_to_bucket(int(r["iv_hp"]))
        atk_real = f"{r['atk']:.2f}"
        slim.append(f"{rank},{atk_b},{def_b},{hp_b},{atk_real}")

    return slim


# ============================================================
# iv_list_input.txt のパース（esal から受け取った行リストを処理）
# ============================================================


def parse_input(
    iv_list_lines: list[str],
    evo_map_staged: list[list[list[str]]],
    pokedex_full: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]]:
    """iv_list_input.txt の行リストをパースし、計算対象ポケモン×リーグを確定する。

    Args:
        iv_list_lines: esal の load_iv_list_input_raw が返す、空行・コメント除外済みの行リスト。
        evo_map_staged: load_evolution_map_staged の返り値（段構造を保持した進化マップ）。
        pokedex_full: load_pokedex_full の返り値（ポケモン名 → 種族値辞書）。

    Returns:
        {ポケモン名: {リーグ: topn}} の辞書。
        同じポケモン×リーグで複数行ある場合は最大 TopN を採用。

    Raises:
        ValueError: 行の書式不正・不正リーグ・不正 TopN・pokedex 未収録ポケモン。
    """
    target_map: dict[str, dict[str, int]] = {}

    for line_number, line in enumerate(iv_list_lines, 1):
        parts = [p.strip() for p in line.split("/")]
        if len(parts) < 3:
            raise ValueError(f"iv_list_input.txt {line_number}行目: 形式不正（/ 区切りが不足）")

        original_name = parts[0]
        leagues_str = parts[1]
        topn_str = parts[2]
        # 4フィールド目が無い場合はデフォルト "L"
        targets_str = parts[3].strip() if len(parts) >= 4 and parts[3].strip() else "L"

        # ポケモン名チェック
        if original_name not in pokedex_full:
            raise ValueError(
                f"iv_list_input.txt {line_number}行目: "
                f"pokedex_numbers.txt に「{original_name}」が見つかりません"
            )

        # リーグパース（カンマ区切り。重複除去・順序保持）
        leagues: list[str] = []
        for lg in leagues_str.split(","):
            lg = lg.strip()
            if lg not in LEAGUE_CAPS:
                raise ValueError(
                    f"iv_list_input.txt {line_number}行目: 不正なリーグ指定: {lg}"
                )
            if lg not in leagues:
                leagues.append(lg)

        # TopN パース
        try:
            topn = int(topn_str)
        except ValueError:
            raise ValueError(
                f"iv_list_input.txt {line_number}行目: TopN が整数ではありません"
            )
        if not (1 <= topn <= 4096):
            raise ValueError(
                f"iv_list_input.txt {line_number}行目: TopN は 1〜4096 で指定してください"
            )

        # 対象指定パース（O/M/L）。カンマ区切りと旧形式（連結文字列）の両方に対応
        if "," in targets_str:
            # 新書式: "M,L" など
            raw_targets = [t.strip() for t in targets_str.split(",") if t.strip()]
        else:
            # 旧書式: "ML" など（1文字ずつ）
            raw_targets = list(targets_str)

        targets: list[str] = []
        for t in raw_targets:
            if t not in ("O", "M", "L"):
                raise ValueError(
                    f"iv_list_input.txt {line_number}行目: 不正な対象指定: {t}"
                )
            if t not in targets:
                targets.append(t)

        # O/M/L 展開 → 対象ポケモン種を確定（library.expand_targets に委譲）
        target_species = expand_targets(original_name, targets, evo_map_staged)

        # target_map に登録（同じポケモン×リーグは最大 TopN を採用）
        for sp_name in target_species:
            if sp_name not in pokedex_full:
                raise ValueError(
                    f"iv_list_input.txt {line_number}行目: "
                    f"pokedex_numbers.txt に「{sp_name}」が見つかりません"
                )
            if sp_name not in target_map:
                target_map[sp_name] = {}
            for lg in leagues:
                existing = target_map[sp_name].get(lg, 0)
                target_map[sp_name][lg] = max(existing, topn)

    return target_map


# ============================================================
# 出力 JSON オブジェクトの組み立て
# ============================================================


def build_cache_object(
    pokemon_entries: list[dict[str, Any]],
    total_entries: int,
    created_at: str,
) -> dict[str, Any]:
    """slim_cache.json として書き出す JSON オブジェクトを組み立てる（純粋関数）。

    created_at は呼び出し元（実行部）が生成した ISO 形式の文字列を受け取る。
    """
    return {
        "meta": {
            "script_version": SCRIPT_VERSION,
            "created_at": created_at,
            "total_pokemon": len(pokemon_entries),
            "total_entries": total_entries,
        },
        "pokemon": pokemon_entries,
    }
