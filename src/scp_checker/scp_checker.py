"""
src/scp_checker/scp_checker.py

SCPランクチェッカーの features 層。
純粋ロジックのみ。Streamlit・ファイル I/O 依存なし。
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Callable

# 内部で使う混合型辞書・リクエストタプルの型エイリアス
_Row = dict[str, Any]          # rows の各要素（idx/name/scp_cont/atk 等を持つ）
_Entry = dict[str, Any]        # pokedex の各要素（atk_base/def_base/hp_base 等）
_Pokedex = dict[str, _Entry]   # ポケモン名 → 種族値辞書
_Request = tuple[str, str, int, int, int, bool]  # (name, league, iv_a, iv_d, iv_h, shadow)

# ============================================================
# 定数（外部仕様で決まる値。ゲーム公式データ）
# ============================================================

# レベル → CPM テーブル（ポケモンGO公式値）
_CPM: dict[float, float] = {
    1.0: 0.094, 1.5: 0.135137432, 2.0: 0.16639787, 2.5: 0.192650919,
    3.0: 0.21573247, 3.5: 0.236572661, 4.0: 0.25572005, 4.5: 0.273530381,
    5.0: 0.29024988, 5.5: 0.306057377, 6.0: 0.3210876, 6.5: 0.335445036,
    7.0: 0.34921268, 7.5: 0.362457751, 8.0: 0.37523559, 8.5: 0.387592406,
    9.0: 0.39956728, 9.5: 0.411193551, 10.0: 0.42250001, 10.5: 0.432926419,
    11.0: 0.44310755, 11.5: 0.4530599578, 12.0: 0.46279839, 12.5: 0.472336083,
    13.0: 0.48168495, 13.5: 0.4908558, 14.0: 0.49985844, 14.5: 0.508701765,
    15.0: 0.51739395, 15.5: 0.525942511, 16.0: 0.53435433, 16.5: 0.542635767,
    17.0: 0.55079269, 17.5: 0.558830576, 18.0: 0.56675452, 18.5: 0.574569153,
    19.0: 0.58227891, 19.5: 0.589887917, 20.0: 0.59740001, 20.5: 0.604818814,
    21.0: 0.61215729, 21.5: 0.619404122, 22.0: 0.62656713, 22.5: 0.633649143,
    23.0: 0.64065295, 23.5: 0.647580967, 24.0: 0.65443563, 24.5: 0.661219252,
    25.0: 0.667934, 25.5: 0.674581896, 26.0: 0.68116492, 26.5: 0.687684904,
    27.0: 0.69414365, 27.5: 0.70054287, 28.0: 0.70688421, 28.5: 0.713169109,
    29.0: 0.71939909, 29.5: 0.725575614, 30.0: 0.7317, 30.5: 0.734741009,
    31.0: 0.73776948, 31.5: 0.740785574, 32.0: 0.74378943, 32.5: 0.746781211,
    33.0: 0.74976104, 33.5: 0.752729087, 34.0: 0.75568551, 34.5: 0.758630378,
    35.0: 0.76156384, 35.5: 0.764486065, 36.0: 0.76739717, 36.5: 0.770297266,
    37.0: 0.7731865, 37.5: 0.776064962, 38.0: 0.77893275, 38.5: 0.781790055,
    39.0: 0.784637, 39.5: 0.787473608, 40.0: 0.7903, 40.5: 0.792803968,
    41.0: 0.79530001, 41.5: 0.797803922, 42.0: 0.8003, 42.5: 0.802803893,
    43.0: 0.8053, 43.5: 0.807803866, 44.0: 0.81029999, 44.5: 0.81280383,
    45.0: 0.81529999, 45.5: 0.817803799, 46.0: 0.82029999, 46.5: 0.822803751,
    47.0: 0.82529999, 47.5: 0.827803694, 48.0: 0.83029999, 48.5: 0.832803687,
    49.0: 0.83529999, 49.5: 0.83780365, 50.0: 0.84029999, 50.5: 0.842803624,
    51.0: 0.8453,
}

# リーグ名 → CP 上限（None はマスターリーグ：上限なし）
_LEAGUE_CAPS: dict[str, int | None] = {"S": 1500, "H": 2500, "M": None}

# おすすめタグの固定並び順（SCP 閾値が高いグループを左から。仕様書 5-2 章）
_TAG_ORDER: list[str] = [
    "★SCP最大",
    "★SCP重視1位",
    "★SCP重視2位",
    "★バランス1位",
    "★バランス2位",
    "★攻撃重視1位",
    "★攻撃重視2位",
]

# output.txt 冒頭の固定コメントブロック（仕様書 6-2 章。1文字も変更しない）
_OUTPUT_HEADER_COMMENT = (
    "# おすすめタグの選定条件\n"
    "# ★SCP最大  : 入力個体の中でSCPが最も高い個体\n"
    "#\n"
    "# ★SCP重視1位・2位 : SCP1位の99%以上の中で攻撃実数値が高い順に2体\n"
    "#              用途：あまり使われないポケモンで攻撃実数値も無視したくない場合\n"
    "#\n"
    "# ★バランス1位・2位 : SCP1位の98.8%以上の中で攻撃実数値最大の個体を基準に\n"
    "#              そのSCPの99.75%以上の中で攻撃実数値が高い順に2体\n"
    "#              ※2段階絞り込みの理由：SCPがほぼ同じ（99.75%以内）なら\n"
    "#               攻撃実数値を優先するため。SCPを犠牲にしすぎない設計。\n"
    "#              用途：多用されるポケモンでミラー対面の同発を意識する場合\n"
    "#\n"
    "# ★攻撃重視1位・2位 : SCP1位の98.5%以上の中で攻撃実数値最大の個体を基準に\n"
    "#              そのSCPの99.6%以上の中で攻撃実数値が高い順に2体\n"
    "#              ※2段階絞り込みの理由：バランスより許容範囲を広げ（99.6%）\n"
    "#               より積極的に攻撃実数値を優先する設計。\n"
    "#              用途：攻撃実数値重視の相手にも同発で勝ちたい場合"
)

# ============================================================
# 内部：SCP 計算ロジック
# ============================================================


def _calc_stats(
    base_atk: int, base_def: int, base_sta: int,
    iv_atk: int, iv_def: int, iv_hp: int,
    level: float,
) -> tuple[float, float, int]:
    """攻撃・防御（連続値）と HP（floor 整数）を返す。"""
    cpm = _CPM[level]
    atk = (base_atk + iv_atk) * cpm
    deff = (base_def + iv_def) * cpm
    hp = math.floor((base_sta + iv_hp) * cpm)  # HP はゲーム仕様で floor 整数化
    return atk, deff, hp


def _calc_cp(
    base_atk: int, base_def: int, base_sta: int,
    iv_atk: int, iv_def: int, iv_hp: int,
    level: float,
) -> int:
    """CP を計算して返す（ゲーム仕様で floor 整数化）。"""
    cpm = _CPM[level]
    return math.floor(
        ((base_atk + iv_atk)
         * math.sqrt(base_def + iv_def)
         * math.sqrt(base_sta + iv_hp)
         * (cpm ** 2)) / 10.0
    )


def _calc_scp_floor(atk: float, deff: float, hp: int) -> int:
    """表示用 SCP（floor 後整数）。画面表示・output.txt の SCP 列に使用する。"""
    # float ** float の型推論が曖昧なため float() で明示的にキャストしてから floor する
    return math.floor(float(((atk * deff * hp) ** (2.0 / 3.0)) / 10.0))


def _calc_scp_continuous(atk: float, deff: float, hp: int) -> float:
    """
    順位付け・タグ判定用の連続値 SCP（floor しない）。
    Rev1.1 変更点：ランキング・タグ判定はすべてこの値を基準に行う。
    """
    # float ** float の型推論が曖昧なため float() で明示的にキャストする
    return float(((atk * deff * hp) ** (2.0 / 3.0)) / 10.0)


def _best_within_cap(
    base_atk: int, base_def: int, base_sta: int,
    iv_atk: int, iv_def: int, iv_hp: int,
    cap_cp: int | None,
    max_level: float = 51.0,
) -> _Row | None:
    """
    CP 上限以下で連続値 SCP が最大になるレベルを探索して返す。

    レベル 1.0〜max_level（0.5 刻み）を昇順に走査し、CP 上限を超えた時点で打ち切る。
    有効なレベルが 1 つも無い場合は None を返す。

    引数 max_level：探索するレベルの上限（デフォルト 51.0）。
      51.0 → 1.0〜51.0（全母集団）、50.0 → 1.0〜50.0（XL不要母集団）。

    返値のキー：level, cp, atk, def, hp, scp（floor 後・表示用）, scp_cont（連続値・判定用）
    """
    best: _Row | None = None
    max_steps = round(max_level * 2)  # 51.0 → 102、50.0 → 100
    for level in (x * 0.5 for x in range(2, max_steps + 1)):  # 1.0〜max_level を 0.5 刻みで生成
        if level not in _CPM:
            continue
        cp = _calc_cp(base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, level)
        if cap_cp is not None and cp > cap_cp:
            break  # CP 上限超過：レベルが上がるほど CP は増加するため以降を打ち切り
        atk, deff, hp = _calc_stats(
            base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, level
        )
        scp_cont = _calc_scp_continuous(atk, deff, hp)
        if best is None or scp_cont > best["scp_cont"]:
            best = {
                "level": level,
                "cp": cp,
                "atk": atk,
                "def": deff,
                "hp": hp,
                "scp": _calc_scp_floor(atk, deff, hp),  # 表示用（floor 後）
                "scp_cont": scp_cont,                     # 判定用（floor 前）
            }
    return best


def _get_rank_result(
    base_atk: int, base_def: int, base_sta: int,
    iv_atk: int, iv_def: int, iv_hp: int,
    cap_cp: int | None,
    max_level: float = 51.0,
) -> _Row | None:
    """
    指定 IV の SCP ランクを計算して返す。全 4096 IV（0〜15 の 3 乗）を評価。

    Rev1.1 変更点：ランク付けは連続値 SCP の降順のみ（1 次元比較）。
    旧実装の「floor 後 SCP → 攻撃実数値」の 2 段階比較から変更。

    引数 max_level：母集団のレベル上限（_best_within_cap に pass-through）。
      51.0 → 全母集団（[RB]対象）、50.0 → XL不要母集団（[RB]非対象）。
    """
    target = _best_within_cap(
        base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, cap_cp, max_level
    )
    if target is None:
        return None

    rank = 1
    for a in range(16):
        for d in range(16):
            for h in range(16):
                if (a, d, h) == (iv_atk, iv_def, iv_hp):
                    continue
                other = _best_within_cap(base_atk, base_def, base_sta, a, d, h, cap_cp, max_level)
                if other is None:
                    continue
                # 連続値 SCP が大きい方が上位（Rev1.1 変更点）
                if other["scp_cont"] > target["scp_cont"]:
                    rank += 1
    return {**target, "rank": rank}


def _get_top1_scp_continuous(
    base_atk: int, base_def: int, base_sta: int, cap_cp: int | None
) -> float:
    """
    全 4096 IV 中の連続値 SCP 最大値を返す。おすすめタグ判定の基準値に使用する。

    Rev1.1 変更点：floor 後 SCP 最大値ではなく、連続値 SCP 最大値を返す。
    """
    top1: float = 0.0
    for a in range(16):
        for d in range(16):
            for h in range(16):
                result = _best_within_cap(base_atk, base_def, base_sta, a, d, h, cap_cp)
                if result and result["scp_cont"] > top1:
                    top1 = result["scp_cont"]
    return top1


# ============================================================
# 内部：おすすめタグ判定
# ============================================================


def _pick_best(candidates: list[_Row]) -> _Row:
    """
    候補の中から「攻撃実数値が高い方、それも同じなら連続値 SCP が高い方」で 1 体を選ぶ。

    Rev1.1 変更点：旧実装の「攻撃→SCP→HP→ランク→入力順」の 5 段階から
    「攻撃→連続値 SCP」の 2 段階に簡素化（連続値採用で HP 以降が不要になったため）。
    """
    return sorted(candidates, key=lambda x: (-x["atk"], -x["scp_cont"]))[0]


def _pick_top2(candidates: list[_Row]) -> list[_Row]:
    """
    候補の中から「攻撃実数値が高い順（同点は連続値 SCP）」で上位 2 体を返す。
    候補が 1 体しかない場合は 1 体のみ返す。
    """
    return sorted(candidates, key=lambda x: (-x["atk"], -x["scp_cont"]))[:2]


def _judge_tags_for_group(
    group: list[_Row], top1_scp_cont: float
) -> dict[int, set[str]]:
    """
    同一ポケモン×リーグ×シャドウのグループ内でおすすめタグを判定する。

    Rev1.1 変更点：すべての比較を連続値 SCP（scp_cont）で行う。
    floor 後 SCP はタグ判定には使わず、画面表示にのみ使う。

    引数：
      group         : 同一グループの rows エントリ一覧（scp_cont・atk・rank・idx を持つ）
      top1_scp_cont : 全 4096 IV 中の連続値 SCP 最大値（タグ閾値の基準）

    返値のキーは row の idx（通し番号）。
    """
    tags: dict[int, set[str]] = defaultdict(set)

    # ★SCP最大：連続値 SCP が最も高い 1 体。同点は攻撃→連続値 SCP で絞る
    max_cont = max(p["scp_cont"] for p in group)
    scp_max_cands = [p for p in group if p["scp_cont"] == max_cont]
    best = _pick_best(scp_max_cands)
    tags[best["idx"]].add("★SCP最大")

    # ★SCP重視（1位・2位）：連続値 SCP1位の 99% 以上
    t = top1_scp_cont * 0.99
    cands = [p for p in group if p["scp_cont"] >= t]
    if not cands:
        # フォールバック：グループ内で全体ランク（5-1章）が最良の 1 体を候補とする
        cands = [min(group, key=lambda x: x["rank"])]
    top2 = _pick_top2(cands)
    tags[top2[0]["idx"]].add("★SCP重視1位")
    if len(top2) >= 2:
        tags[top2[1]["idx"]].add("★SCP重視2位")

    # ★バランス（1位・2位）：2 段階絞り込み
    t1 = top1_scp_cont * 0.988
    c1 = [p for p in group if p["scp_cont"] >= t1]
    # 1 段階目フォールバック：グループ内全体ランク最良を基準個体として採用
    base = _pick_best(c1) if c1 else min(group, key=lambda x: x["rank"])
    t2 = base["scp_cont"] * 0.9975
    c2 = [p for p in group if p["scp_cont"] >= t2]
    cands = c2 if c2 else [base]
    top2 = _pick_top2(cands)
    tags[top2[0]["idx"]].add("★バランス1位")
    if len(top2) >= 2:
        tags[top2[1]["idx"]].add("★バランス2位")

    # ★攻撃重視（1位・2位）：2 段階絞り込み
    t1 = top1_scp_cont * 0.985
    c1 = [p for p in group if p["scp_cont"] >= t1]
    base = _pick_best(c1) if c1 else min(group, key=lambda x: x["rank"])
    t2 = base["scp_cont"] * 0.996
    c2 = [p for p in group if p["scp_cont"] >= t2]
    cands = c2 if c2 else [base]
    top2 = _pick_top2(cands)
    tags[top2[0]["idx"]].add("★攻撃重視1位")
    if len(top2) >= 2:
        tags[top2[1]["idx"]].add("★攻撃重視2位")

    return tags


# ============================================================
# 公開：シャドウユーティリティ
# ============================================================


def is_shadow(name: str, pokedex: _Pokedex) -> bool:
    """
    ポケモン名の先頭が S かつ S 除き名が pokedex に存在する場合にシャドウと判定する。
    ポケモン名はカタカナのため、先頭 S は常にシャドウの識別子として機能する。
    """
    return name.startswith("S") and name[1:] in pokedex


def base_name(name: str, pokedex: _Pokedex) -> str:
    """シャドウ名から通常名を返す（通常名はそのまま返す）。pokedex 参照時のキーに使用。"""
    if is_shadow(name, pokedex):
        return name[1:]
    return name


# ============================================================
# 公開：ファイルアップロードのパース
# ============================================================


def parse_rank_input(
    text: str, pokedex: _Pokedex
) -> tuple[list[_Request], list[str]]:
    """
    rank_cheker_input.txt のテキストをパースし、(リクエスト一覧, エラー一覧) を返す。

    コメント行（#）・空行はスキップ。エラー行が 1 件でもある場合は errors に追加する。
    IV は 10 進数として失敗した値を 16 進数としてフォールバック解釈する
    （ファイルアップロード経路のみの仕様。フォーム入力では 16 進数非対応）。
    """
    requests: list[_Request] = []
    errors: list[str] = []

    def parse_iv_value(v: str) -> int:
        """IV 文字列を整数に変換する。10 進数失敗時に 16 進数でリトライ。"""
        try:
            return int(v, 10)
        except ValueError:
            return int(v, 16)  # 例：'f' → 15

    for i, line in enumerate(text.splitlines(), 1):
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue  # コメント行・空行はスキップ

        parts = raw.split("/")
        if len(parts) != 5:
            errors.append(f"{i}行目: 形式不正 → {raw}")
            continue

        name, league = parts[0].strip(), parts[1].strip()
        shadow = is_shadow(name, pokedex)

        if league not in _LEAGUE_CAPS:
            errors.append(f"{i}行目: 不正なリーグ → {league}")
            continue

        try:
            iv_a, iv_d, iv_h = (parse_iv_value(v) for v in parts[2:])
        except ValueError:
            errors.append(f"{i}行目: IVが数値ではありません → {raw}")
            continue

        if not all(0 <= v <= 15 for v in (iv_a, iv_d, iv_h)):
            errors.append(f"{i}行目: IV範囲不正(0-15) → {raw}")
            continue

        requests.append((name, league, iv_a, iv_d, iv_h, shadow))

    return requests, errors


# ============================================================
# 公開：SCP ランク計算
# ============================================================


def calculate_results(
    requests: list[_Request],
    pokedex: _Pokedex,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[_Row]:
    """
    リクエスト一覧の SCP ランクを計算し、結果行のリストを返す。

    各要素のキー：idx, input, league, name, shadow, level, cp, atk, def, hp,
                  scp（floor 後・表示用）, scp_cont（連続値・判定用）, rank

    ポケモンが pokedex に見つからない場合は ValueError を raise する。
    有効レベルが 1 つも無く計算できない場合も ValueError を raise する。
    on_progress は計算 1 件完了ごとに on_progress(完了件数, 総件数) で呼ばれる
    コールバック（省略可。UI 層の進捗バー更新用）。
    """
    rows: list[_Row] = []
    total = len(requests)

    for idx, (name, league, iv_a, iv_d, iv_h, shadow) in enumerate(requests):
        lookup = base_name(name, pokedex)
        entry = pokedex.get(lookup)
        if entry is None:
            raise ValueError(f"ポケモンが見つかりません: {name}")

        cap_cp = _LEAGUE_CAPS[league]

        # 対象個体の表示統計値をレベル上限 51 で取得し、[RB] 判定に使う（仕様書 5-1 章 Rev1.2）
        best = _best_within_cap(
            entry["atk_base"], entry["def_base"], entry["hp_base"],
            iv_a, iv_d, iv_h, cap_cp,
        )
        if best is None:
            raise ValueError(f"計算失敗: {name}/{league}/{iv_a}/{iv_d}/{iv_h}")

        # [RB] 判定：最適レベルが 50 超（50.5 または 51.0）なら上限 51 の母集団、
        # 50 以下なら上限 50 の母集団で SCP 順位を数える。
        # タグ判定基準（_get_top1_scp_continuous）はレベル上限 51 のまま変更しない。
        rank_max_level = 51.0 if best["level"] > 50.0 else 50.0

        result = _get_rank_result(
            entry["atk_base"], entry["def_base"], entry["hp_base"],
            iv_a, iv_d, iv_h, cap_cp,
            max_level=rank_max_level,
        )
        if result is None:
            # best が non-None の場合はここに到達しないが、型上 _Row | None のため確認する
            raise ValueError(f"計算失敗: {name}/{league}/{iv_a}/{iv_d}/{iv_h}")

        rows.append({
            "idx": idx,
            "input": f"{name}/{iv_a}/{iv_d}/{iv_h}",
            "league": league,
            "name": name,
            "shadow": shadow,
            **best,               # 表示統計値（level/cp/atk/def/hp/scp/scp_cont）
            "rank": result["rank"],  # SCP 順位（母集団レベル上限 50 または 51）
        })

        if on_progress is not None:
            on_progress(idx + 1, total)

    return rows


# ============================================================
# 公開：おすすめタグ判定
# ============================================================


def assign_recommend_tags(
    rows: list[_Row], pokedex: _Pokedex
) -> dict[int, set[str]]:
    """
    rows を同一ポケモン×リーグ×シャドウでグループ化し、タグを判定して返す。

    おすすめタグの詳細は仕様書 5-2 章を参照。
    返値のキーは rows[i]["idx"]（calculate_results が付与した通し番号）。
    """
    # グループ化。判定は入力順序に関わらず、同じグループ内の全個体を対象とする
    groups: dict[tuple[str, str, bool], list[_Row]] = defaultdict(list)
    for r in rows:
        groups[(r["name"], r["league"], r["shadow"])].append(r)

    tag_map: dict[int, set[str]] = defaultdict(set)
    for (name, league, _shadow), group in groups.items():
        lookup = base_name(name, pokedex)
        entry = pokedex[lookup]
        cap_cp = _LEAGUE_CAPS[league]
        top1_cont = _get_top1_scp_continuous(
            entry["atk_base"], entry["def_base"], entry["hp_base"], cap_cp
        )
        group_tags = _judge_tags_for_group(group, top1_cont)
        for k, v in group_tags.items():
            tag_map[k].update(v)

    return tag_map


# ============================================================
# 公開：出力テキスト生成
# ============================================================


def format_output(rows: list[_Row], tag_map: dict[int, set[str]]) -> str:
    """
    rows と tag_map から output.txt 形式の文字列を生成して返す。

    列幅・整列規則・空行挿入・タグ並び順は仕様書 6-2 章に従う。
    Rev1.1 変更点：タグ並び順を sorted() から固定順リスト（_TAG_ORDER）に変更。
    """
    # 入力表示列の幅：全結果行のうち最長の文字数＋2（仕様書 6-2 章）
    input_width = max(len(r["input"]) for r in rows) + 2
    header_left = input_width + 5  # ヘッダー先頭の空白幅：入力表示列の幅＋5

    lines: list[str] = []
    lines.append(_OUTPUT_HEADER_COMMENT)
    lines.append("")  # 固定コメントブロック後の空行 1 行

    # ヘッダー行
    header = (
        f"{'':<{header_left}}"
        f"{'League':<7} {'SCPRANK':<8} {'SCP':<4} {'ATK':<6} {'DEF':<6} "
        f"{'HP':<3} {'CP':<4} {'Level':<5}"
    )
    lines.append(header)

    prev_name: str | None = None
    prev_league: str | None = None
    prev_shadow: bool | None = None

    for r in rows:
        # 直前行と比較し、ポケモン名・リーグ・シャドウフラグのいずれかが変わったら空行挿入
        if prev_name is not None and (
            r["name"] != prev_name
            or r["league"] != prev_league
            or r["shadow"] != prev_shadow
        ):
            lines.append("")
        prev_name = r["name"]
        prev_league = r["league"]
        prev_shadow = r["shadow"]

        data_part = (
            f"{r['input']:<{input_width}}"
            f"{r['league']:<7} {r['rank']:04d}     {r['scp']:<4} "
            f"{r['atk']:<6.2f} {r['def']:<6.2f} "
            f"{r['hp']:<3} {r['cp']:<4} {r['level']:<5.1f}"
        )

        # タグ欄：[RB]（レベル 50 超のとき）+ ★タグを固定順で連結
        rb = "[RB] " if r["level"] > 50.0 else ""
        star_tags = " ".join(
            t for t in _TAG_ORDER if t in tag_map.get(r["idx"], set())
        )
        tag_str = rb + star_tags
        line = data_part + ("  " + tag_str if tag_str else "")
        lines.append(line)

    return "\n".join(lines)


# ============================================================
# 公開：一括置換
# ============================================================


def apply_bulk_replace(
    requests: list[_Request],
    name_from: str,
    league_from: str,
    name_to: str,
    league_to: str,
    pokedex: _Pokedex,
) -> tuple[list[_Request], str | None, str | None]:
    """
    リクエストリストに対して一括置換を適用する。

    引数：
      name_from  : 置換前ポケモン名（空文字 = 全名前が対象）
      league_from: 置換前リーグ（"変更なし" = 全リーグが対象）
      name_to    : 置換後ポケモン名（空文字 = 名前は変更しない）
      league_to  : 置換後リーグ（"変更なし" = リーグは変更しない）

    返値：(新リスト, 成功メッセージ or None, エラー/警告メッセージ or None)
    エラー/警告がある場合は新リストは元のリストをそのまま返す。
    """
    if not name_from and league_from == "変更なし":
        return requests, None, "置換前のポケモン名またはリーグを指定してください。"

    if not name_to and league_to == "変更なし":
        return requests, None, "置換後のポケモン名またはリーグを指定してください。"

    if name_to:
        lookup_to = base_name(name_to, pokedex)
        if lookup_to not in pokedex:
            return requests, None, f"「{name_to}」はpokedex_numbers.txtに存在しません。"

    def is_target(n: str, lg: str) -> bool:
        name_match = (not name_from) or (n == name_from)
        league_match = (league_from == "変更なし") or (lg == league_from)
        return name_match and league_match

    count = sum(1 for n, lg, *_ in requests if is_target(n, lg))
    if count == 0:
        return requests, None, "条件に一致する行がリストに存在しません。"

    def apply_to(entry: _Request) -> _Request:
        n, lg, iv_a, iv_d, iv_h, sw = entry
        if not is_target(n, lg):
            return entry
        new_name = name_to if name_to else n
        new_league = league_to if league_to != "変更なし" else lg
        new_shadow = is_shadow(new_name, pokedex)  # 置換後の名前で先頭 S を再判定
        return (new_name, new_league, iv_a, iv_d, iv_h, new_shadow)

    new_requests = [apply_to(e) for e in requests]

    # 成功メッセージ：指定された項目（name_from 非空 / league_from != "変更なし"）のみ列挙
    msg_parts: list[str] = []
    if name_from:
        msg_parts.append(f"名前「{name_from}」→「{name_to if name_to else '変更なし'}」")
    if league_from != "変更なし":
        msg_parts.append(
            f"リーグ「{league_from}」→「{league_to if league_to != '変更なし' else '変更なし'}」"
        )
    success_msg = f"{' / '.join(msg_parts)} を{count}件置換しました。"

    return new_requests, success_msg, None
