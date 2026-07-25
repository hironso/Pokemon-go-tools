"""
src/iv_strings_generator/iv_strings_generator.py

iv_strings_generator アプリの純粋ロジック層（features）。
Streamlit・ファイル読み込みに依存しない。
データ（pokedex, evo_map_staged, slim_cache）は呼び出し元から受け取る。

処理の流れ（仕様書 1章）:
  1. parse_input: 入力テキストを解析してリクエストリストを作る（3章）。
  2. generate_iv_strings: リクエストからIVバケットを決定し（6章）、
     27パターンへ割り当てて（7章）、丸めて（8章）、出力テキストを生成する（9章）。
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.library.expand_targets import expand_targets

# ============================================================
# 出力フォーマット定数（仕様書 9.1）
# ============================================================
_FILTER_GBL_RAID = "&!お気に入り&!#&!しゃどう&!だいまっくす&!きょだいまっくす"
_FILTER_CONFIRM = "&お気に入り,#&!しゃどう&!だいまっくす&!きょだいまっくす"
_FILTER_TRADE_TAGS = "&!#交換&!#内交換&!#リモート交換&!#100km&!#300km"
_FILTER_SEND = "&!お気に入り&!#&!しゃどう&!色違い&!だいまっくす&!きょだいまっくす"

# ============================================================
# バリデーション定数
# ============================================================
_VALID_LEAGUES: frozenset[str] = frozenset({"S", "H", "M"})
_VALID_TARGETS: frozenset[str] = frozenset({"O", "M", "L"})
_TOPN_MIN = 1
_TOPN_MAX = 4096

# ============================================================
# 27パターン定義（PID昇順, 仕様書 7.5 の並び）
# 各要素: (pid, a, d, h)
#   a: こうげき上限バケット (1..3)  → こうげきバケット集合 = {0..a}
#   d: ぼうぎょ下限バケット (1..3)  → ぼうぎょバケット集合 = {d..4}
#   h: HP下限バケット     (1..3)  → HPバケット集合      = {h..4}
# ============================================================
_PATTERNS: list[tuple[int, int, int, int]] = [
    (1, 1, 3, 3),
    (2, 1, 3, 2),
    (3, 1, 2, 3),
    (4, 1, 2, 2),
    (5, 2, 3, 3),
    (6, 1, 3, 1),
    (7, 1, 1, 3),
    (8, 1, 2, 1),
    (9, 1, 1, 2),
    (10, 2, 3, 2),
    (11, 2, 2, 3),
    (12, 1, 1, 1),
    (13, 2, 2, 2),
    (14, 3, 3, 3),
    (15, 2, 3, 1),
    (16, 2, 1, 3),
    (17, 2, 2, 1),
    (18, 2, 1, 2),
    (19, 3, 3, 2),
    (20, 3, 2, 3),
    (21, 2, 1, 1),
    (22, 3, 2, 2),
    (23, 3, 3, 1),
    (24, 3, 1, 3),
    (25, 3, 2, 1),
    (26, 3, 1, 2),
    (27, 3, 1, 1),
]

# (a, d, h) → PID の逆引き辞書（丸め処理の「くっつけ先 PID」特定に使う）
_ADH_TO_PID: dict[tuple[int, int, int], int] = {(a, d, h): pid for pid, a, d, h in _PATTERNS}

# PID → (a, d, h) の辞書（1手計算の起点取得に使う）
_PID_TO_ADH: dict[int, tuple[int, int, int]] = {pid: (a, d, h) for pid, a, d, h in _PATTERNS}


# ============================================================
# 内部データクラス
# ============================================================
@dataclass(frozen=True)
class _FamilyUnit:
    """
    グループ分けの最小単位。
    同一ファミリー（同一 dex_list キー）に属するすべてのユニット（ポケモン×リーグ）の
    バケット要求をまとめたもの（仕様書 6章）。
    """

    dex_list: tuple[int, ...]  # ファミリーの全図鑑番号（重複除去・昇順）
    atk_buckets: frozenset[int]  # こうげきバケット集合
    def_buckets: frozenset[int]  # ぼうぎょバケット集合
    hp_buckets: frozenset[int]  # HPバケット集合


# ============================================================
# 例外クラス
# ============================================================
class NoValidUnitsError(ValueError):
    """
    IV 決定後に有効なユニットが 1 件もなかった場合に raise する。
    slim_cache 未収録のポケモン名は missing_cache_names に格納される。
    """

    def __init__(self, missing_cache_names: set[str] | None = None) -> None:
        self.missing_cache_names: set[str] = missing_cache_names or set()
        super().__init__("有効なユニットがありません。処理対象となるポケモンが存在しません。")


# ============================================================
# 公開関数
# ============================================================

# parse_input の返り値に含まれるリクエストの型エイリアス
# (original_name, leagues, topn, targets)
Request = tuple[str, list[str], int, list[str]]


def parse_input(
    text: str,
    pokedex: dict[str, int],
) -> tuple[list[Request], list[str]]:
    """
    iv_list_input.txt 形式のテキストを解析し、リクエストリストとエラーリストを返す。

    書式（1行）: ポケモン名/リーグ/TopN[/対象指定]
    エラーがあっても処理を中断せずに全行を走査し、エラー行を列挙する（仕様書 3章）。

    Args:
        text: アップロードされたテキストの文字列。
        pokedex: ポケモン名 → 図鑑番号の辞書（名前の存在チェックに使う）。

    Returns:
        (requests, errors):
            requests: 有効な行から作成したリクエストのリスト。
            errors: エラーメッセージのリスト（空ならエラーなし）。
    """
    requests: list[Request] = []
    errors: list[str] = []

    for line_no, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = [p.strip() for p in line.split("/")]
        if len(parts) < 3:
            errors.append(f"{line_no}行目: 形式不正（'/' で区切られた項目が3つ未満） → {line}")
            continue

        original_name = parts[0]
        leagues_str = parts[1]
        topn_str = parts[2]
        # 対象指定は省略時 "L" とする
        targets_str = parts[3].strip() if len(parts) >= 4 and parts[3].strip() else "L"

        # ポケモン名チェック
        if original_name not in pokedex:
            errors.append(f"{line_no}行目: pokedex未収録 → {original_name}")
            continue

        # リーグチェック（重複は除去）
        leagues: list[str] = []
        valid = True
        for lg in leagues_str.split(","):
            lg = lg.strip()
            if lg not in _VALID_LEAGUES:
                errors.append(f"{line_no}行目: 不正なリーグ → {lg}")
                valid = False
                break
            if lg not in leagues:
                leagues.append(lg)
        if not valid:
            continue

        # TopN チェック
        try:
            topn = int(topn_str)
        except ValueError:
            errors.append(f"{line_no}行目: TopNが整数ではありません → {topn_str}")
            continue
        if not (_TOPN_MIN <= topn <= _TOPN_MAX):
            errors.append(
                f"{line_no}行目: TopNは{_TOPN_MIN}〜{_TOPN_MAX}で指定してください → {topn}"
            )
            continue

        # 対象指定チェック（重複は除去）
        # カンマ区切りと連続文字の両方を許容（例: "L,M" または "LM"）
        if "," in targets_str:
            raw_targets = [t.strip() for t in targets_str.split(",") if t.strip()]
        else:
            raw_targets = list(targets_str)

        targets: list[str] = []
        valid = True
        for t in raw_targets:
            if t not in _VALID_TARGETS:
                errors.append(f"{line_no}行目: 不正な対象指定 → {t}")
                valid = False
                break
            if t not in targets:
                targets.append(t)
        if not valid:
            continue

        requests.append((original_name, leagues, topn, targets))

    return requests, errors


def generate_iv_strings(
    requests: list[Request],
    pokedex: dict[str, int],
    evo_map_staged: list[list[list[str]]],
    slim_cache: dict[str, dict],  # type: ignore[type-arg]
    show_confirm: bool = False,
    show_final_confirm: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> tuple[str, set[str]]:
    """
    iv_list_input のリクエストから出力テキストを生成する（仕様書 1〜9章）。

    Args:
        requests: parse_input が返したリクエストリスト。
        pokedex: ポケモン名 → 図鑑番号の辞書。
        evo_map_staged: 段構造を保った進化マップ（load_evolution_map_staged の返り値）。
        slim_cache: ポケモン名 → slim_cache エントリの辞書（load_slim_cache の返り値）。
        show_confirm: True のとき確認用を出力する（仕様書 9.7）。
        show_final_confirm: True のとき最終確認用を出力する（仕様書 9.7）。
        progress_callback: 進捗通知コールバック (current, total) → None。

    Returns:
        (output_text, missing_cache_names):
            output_text: 生成されたテキスト。
            missing_cache_names: slim_cache に未収録だったポケモン名のセット。

    Raises:
        NoValidUnitsError: IV 決定後に有効なユニットが 1 件もない場合。
                           例外の missing_cache_names に未収録名が格納される。
    """
    units, missing_cache_names = _build_family_units(
        requests, pokedex, evo_map_staged, slim_cache, progress_callback
    )

    if not units:
        raise NoValidUnitsError(missing_cache_names)

    groups, individual_slot = _assign_and_round(units)
    output = _build_output(
        units, groups, individual_slot, len(units), show_confirm, show_final_confirm
    )
    return output, missing_cache_names


# ============================================================
# 内部実装（_ プレフィックス）
# ============================================================


def _parse_slim_entries(entries: list[str], use_topn: int) -> list[dict[str, int | float]]:
    """
    slim_cache の entries（CSV 文字列リスト）を辞書リストにパースする。

    書式: "rank,atk_bucket,def_bucket,hp_bucket,atk_real"
    use_topn 件まで取り出す。変換できない行はスキップする。
    """
    result: list[dict[str, int | float]] = []
    for ent in entries[:use_topn]:
        parts = ent.split(",")
        if len(parts) < 5:
            continue
        try:
            result.append(
                {
                    "rank": int(parts[0]),
                    "atk_bucket": int(parts[1]),
                    "def_bucket": int(parts[2]),
                    "hp_bucket": int(parts[3]),
                    "atk_real": float(parts[4]),
                }
            )
        except ValueError:
            continue
    return result


def _choose_buckets(
    results: list[dict[str, int | float]],
) -> tuple[frozenset[int], frozenset[int], frozenset[int]]:
    """
    slim_cache エントリのリストから採用バケット集合を選択する（仕様書 6章）。

    適用ルール（和を取る）:
      1. 全体10%ルール: TopN全体で出現率 10% 以上のバケットを採用。
      2. 上位30%10%ルール: 上位30% の中で出現率 10% 以上のバケットを採用。
      3. SCP70拡張: SCP上位70位以内の個体のうち攻撃実数値トップ20件のこうげきバケットを強制採用。
      4. フォールバック: 上記すべてで採用なしの場合、出現バケットを全採用。

    Returns:
        (atk_buckets, def_buckets, hp_buckets) の3つの frozenset。
    """
    if not results:
        return frozenset(), frozenset(), frozenset()

    total = len(results)
    # 上位30%の件数（最低1件）
    top30_count = max(1, int(round(total * 0.30)))
    top30 = results[:top30_count]

    # 全体カウント
    atk_total: dict[int, int] = defaultdict(int)
    def_total: dict[int, int] = defaultdict(int)
    hp_total: dict[int, int] = defaultdict(int)
    for r in results:
        atk_total[int(r["atk_bucket"])] += 1
        def_total[int(r["def_bucket"])] += 1
        hp_total[int(r["hp_bucket"])] += 1

    # 上位30%カウント
    atk_top: dict[int, int] = defaultdict(int)
    def_top: dict[int, int] = defaultdict(int)
    hp_top: dict[int, int] = defaultdict(int)
    for r in top30:
        atk_top[int(r["atk_bucket"])] += 1
        def_top[int(r["def_bucket"])] += 1
        hp_top[int(r["hp_bucket"])] += 1

    def _select_10pct(total_map: dict[int, int], top_map: dict[int, int]) -> set[int]:
        """全体・上位30%それぞれで 10% 以上のバケットを採用する。"""
        selected: set[int] = set()
        for b, cnt in total_map.items():
            if cnt / total >= 0.10:
                selected.add(b)
        for b, cnt in top_map.items():
            if cnt / len(top30) >= 0.10:
                selected.add(b)
        return selected

    atk_sel = _select_10pct(atk_total, atk_top)
    def_sel = _select_10pct(def_total, def_top)
    hp_sel = _select_10pct(hp_total, hp_top)

    # SCP70拡張＋攻撃実数値強化:
    # SCP上位70位以内の個体 → 攻撃実数値トップ20件のこうげきバケットを強制採用
    if total <= 70:
        scp70 = list(results)
    else:
        last_rank_70 = int(results[69]["rank"])
        scp70 = [r for r in results if int(r["rank"]) <= last_rank_70]

    scp70_sorted = sorted(scp70, key=lambda r: float(r["atk_real"]), reverse=True)
    if scp70_sorted:
        k = min(20, len(scp70_sorted))
        threshold = float(scp70_sorted[k - 1]["atk_real"])
        # 実数値がちょうど閾値のものも含む（同値タイが k 件以上ある場合を吸収する）
        forced_atk = {
            int(r["atk_bucket"]) for r in scp70_sorted if float(r["atk_real"]) >= threshold
        }
        atk_sel |= forced_atk

    def _fallback(
        selected: set[int],
        total_map: dict[int, int],
        top_map: dict[int, int],
    ) -> frozenset[int]:
        """上記ルールで採用なしの場合、出現したバケットを全採用する（フォールバック）。"""
        if selected:
            return frozenset(selected)
        # 上位30%に出現したものを優先、なければ全体から採用
        if top_map:
            return frozenset(b for b, cnt in top_map.items() if cnt > 0)
        return frozenset(b for b, cnt in total_map.items() if cnt > 0)

    return (
        _fallback(atk_sel, atk_total, atk_top),
        _fallback(def_sel, def_total, def_top),
        _fallback(hp_sel, hp_total, hp_top),
    )


def _build_family_units(
    requests: list[Request],
    pokedex: dict[str, int],
    evo_map_staged: list[list[list[str]]],
    slim_cache: dict[str, dict],  # type: ignore[type-arg]
    progress_callback: Callable[[int, int], None] | None,
) -> tuple[list[_FamilyUnit], set[str]]:
    """
    リクエストから _FamilyUnit リストを構築する（仕様書 6章）。

    同一ファミリー（同一 dex_list キー）に属するリクエストのバケット要求は軸ごとに和を取る。
    ぼうぎょまたは HP のバケット集合が空になったエントリは除外する。
    """
    # dex_list キー → (atk_set, def_set, hp_set) の積算辞書
    family_map: dict[tuple[int, ...], tuple[set[int], set[int], set[int]]] = {}
    missing_cache_names: set[str] = set()
    total = len(requests)

    for i, (original_name, leagues, topn, targets) in enumerate(requests):
        if progress_callback is not None:
            progress_callback(i + 1, total)

        # O/M/L 展開で slim_cache を参照するポケモン名リストを取得する
        target_names = expand_targets(original_name, targets, evo_map_staged)

        req_atk: set[int] = set()
        req_def: set[int] = set()
        req_hp: set[int] = set()

        for sp_name in target_names:
            cache_entry = slim_cache.get(sp_name)
            if cache_entry is None:
                missing_cache_names.add(sp_name)
                continue

            leagues_data: dict[str, object] = cache_entry.get("leagues", {})
            for lg in leagues:
                lg_data = leagues_data.get(lg)
                if not isinstance(lg_data, dict):
                    continue
                entries: list[str] = lg_data.get("entries", [])
                cached_topn: int = lg_data.get("topn", len(entries))
                use_topn = min(topn, cached_topn, len(entries))
                parsed = _parse_slim_entries(entries, use_topn)
                if not parsed:
                    continue
                a_b, d_b, h_b = _choose_buckets(parsed)
                req_atk |= set(a_b)
                req_def |= set(d_b)
                req_hp |= set(h_b)

        # ぼうぎょまたは HP バケットが空のユニットは除外する（仕様書 6章）
        if not req_def or not req_hp:
            continue

        # ファミリーキー: original_name が属するファミリーの全図鑑番号（昇順タプル）
        all_stages: list[list[str]] | None = None
        for stages in evo_map_staged:
            for stage in stages:
                if original_name in stage:
                    all_stages = stages
                    break
            if all_stages is not None:
                break

        if all_stages is not None:
            all_names = [nm for stage in all_stages for nm in stage]
        else:
            all_names = [original_name]

        dex_list = tuple(sorted({pokedex[nm] for nm in all_names if nm in pokedex}))

        if dex_list not in family_map:
            family_map[dex_list] = (set(), set(), set())
        family_map[dex_list][0].update(req_atk)
        family_map[dex_list][1].update(req_def)
        family_map[dex_list][2].update(req_hp)

    # dex_list 昇順で FamilyUnit リストを構築する
    units = [
        _FamilyUnit(
            dex_list=dex_list,
            atk_buckets=frozenset(a_set),
            def_buckets=frozenset(d_set),
            hp_buckets=frozenset(h_set),
        )
        for dex_list, (a_set, d_set, h_set) in sorted(family_map.items())
    ]
    return units, missing_cache_names


def _unit_fits_pattern(unit: _FamilyUnit, a: int, d: int, h: int) -> bool:
    """
    ユニットがパターン (a, d, h) に収まるか判定する（仕様書 8.2）。

    収まる条件: 各軸のバケット集合がパターンの許容範囲に含まれること。
      atk_buckets ⊆ {0..a}、def_buckets ⊆ {d..4}、hp_buckets ⊆ {h..4}
    """
    return (
        unit.atk_buckets <= frozenset(range(a + 1))
        and unit.def_buckets <= frozenset(range(d, 5))
        and unit.hp_buckets <= frozenset(range(h, 5))
    )


def _one_step(a: int, d: int, h: int) -> tuple[int, int, int] | None:
    """
    パターン (a, d, h) から 1 手でくっつけ先パターンを求める（仕様書 8.3）。

    「段」で状態を表す（仕様書 2章）:
      こうげき段 = a - 1、ぼうぎょ段 = 3 - d、HP段 = 3 - h

    第1段階（ぼうぎょ段 ≠ HP段）: 段の小さい軸を 1 段緩める。
    第2段階（ぼうぎょ段 = HP段）: HP → ぼうぎょ → こうげきの順で緩める。

    Returns:
        くっつけ先の (a', d', h')。対象外（こうげき4・ぼうぎょ0・HP0）なら None。
    """
    def_step = 3 - d  # ぼうぎょ段（値が大きいほど「多く緩めた」状態）
    hp_step = 3 - h  # HP段

    if def_step != hp_step:
        # 第1段階: 段が小さい（より厳しい）軸を 1 段緩める
        if def_step < hp_step:
            # ぼうぎょを 1 段緩める（d を 1 下げる）
            new_d = d - 1
            return None if new_d < 1 else (a, new_d, h)
        else:
            # HP を 1 段緩める（h を 1 下げる）
            new_h = h - 1
            return None if new_h < 1 else (a, d, new_h)
    else:
        # 第2段階: ぼうぎょ段 = HP段 → HP優先で順に試みる
        if h > 1:
            return (a, d, h - 1)
        if d > 1:
            return (a, d - 1, h)
        new_a = a + 1
        return None if new_a > 3 else (new_a, d, h)


def _assign_and_round(
    units: list[_FamilyUnit],
) -> tuple[dict[int, list[int]], list[int]]:
    """
    全ユニットを 27 パターンへ割り当て、丸め処理を行う（仕様書 8章）。

    割り当て（8.2）:
      PID 昇順で最初に収まるパターンへ割り当てる。
      どのパターンにも収まらないユニットは個別枠へ入れる。

    丸め込み（巡回＝ラウンド方式, 8.5）:
      有効閾値 = floor(総ユニット数 × 0.065) を 1 度だけ算出し固定する。
      1 巡ごとに閾値未満のグループを全部集め、ユニット数昇順に各 1 回だけ緩める。
      合流先になったグループはその巡では保護し、再び緩めない。
      閾値未満のグループが無くなるまで巡を繰り返す。
      グループ数の上限は設けない（Rev1.2 で 6 上限を廃止）。

    Returns:
        (groups, individual_slot):
            groups: PID → ユニットインデックスリスト（アクティブなグループのみ収録）。
            individual_slot: 個別枠のユニットインデックスリスト。
    """
    # ---- 割り当て（8.2）: PID 昇順で最初に収まるパターンへ ----
    groups: dict[int, list[int]] = {pid: [] for pid, _a, _d, _h in _PATTERNS}
    individual_slot: list[int] = []

    for idx, unit in enumerate(units):
        assigned = False
        for pid, a, d, h in _PATTERNS:
            if _unit_fits_pattern(unit, a, d, h):
                groups[pid].append(idx)
                assigned = True
                break
        if not assigned:
            # どのパターンにも収まらない（こうげき4 等）→ 個別枠へ
            individual_slot.append(idx)

    # ---- 丸め込み（巡回＝ラウンド方式, 8.5）----
    # 有効閾値: floor(総ユニット数 × 0.065)。個別枠のユニットも総数に含む。
    # int() は正の値に対して floor と等価（Python は 0 方向への整数切り捨て）。
    threshold = int(len(units) * 0.065)

    while True:
        # 巡の開始: 閾値未満のアクティブグループを全部集める
        candidates = [pid for pid, ui in groups.items() if ui and len(ui) < threshold]
        if not candidates:
            break

        # ユニット数昇順（同数なら PID 昇順 = より厳しいグループ優先）
        candidates.sort(key=lambda pid: (len(groups[pid]), pid))

        # この巡で合流先になった PID を保護するセット
        protected: set[int] = set()

        for pid in candidates:
            # 合流先になったグループはこの巡では緩めない（仕様書 8.5）
            if pid in protected:
                continue
            # この巡の先行処理で空になった場合もスキップ
            if not groups[pid]:
                continue

            a, d, h = _PID_TO_ADH[pid]
            next_adh = _one_step(a, d, h)
            if next_adh is None:
                # 対象外領域に到達 → 個別枠へ（仕様書 8.4）
                individual_slot.extend(groups[pid])
                groups[pid] = []
            else:
                next_pid = _ADH_TO_PID[next_adh]
                # 空パターンでもくっつけ先にできる（仕様書 8.4）
                groups[next_pid].extend(groups[pid])
                groups[pid] = []
                # 合流先を保護: この巡ではもう緩めない
                protected.add(next_pid)

    # 空グループを除いて返す
    return {pid: ui for pid, ui in groups.items() if ui}, individual_slot


def _iv_expr(a: int, d: int, h: int) -> str:
    """
    パターン (a, d, h) から IV 式文字列を生成する（仕様書 9.6）。

    こうげき・ぼうぎょ・HP の順に軸ごとのバケット列を '&' で連結する。
    例: (1, 2, 2) → "0こうげき,1こうげき&2ぼうぎょ,3ぼうぎょ,4ぼうぎょ&2HP,3HP,4HP"
    """
    atk_part = ",".join(f"{b}こうげき" for b in range(a + 1))
    def_part = ",".join(f"{b}ぼうぎょ" for b in range(d, 5))
    hp_part = ",".join(f"{b}HP" for b in range(h, 5))
    return f"{atk_part}&{def_part}&{hp_part}"


def _dex_expr(unit_indices: list[int], units: list[_FamilyUnit]) -> str:
    """グループ内の全図鑑番号を重複除去・昇順・カンマ区切りの文字列にする（仕様書 9.4）。"""
    all_dex: set[int] = set()
    for i in unit_indices:
        all_dex.update(units[i].dex_list)
    return ",".join(str(d) for d in sorted(all_dex))


def _build_output(
    units: list[_FamilyUnit],
    groups: dict[int, list[int]],
    individual_slot: list[int],
    total_unit_count: int,
    show_confirm: bool,
    show_final_confirm: bool,
) -> str:
    """出力テキスト全体を組み立てる（仕様書 9章）。"""
    lines: list[str] = []

    # ---- ヘッダ（9.2）----
    now = datetime.now(timezone(timedelta(hours=9)))
    header_time = now.strftime("%Y/%m/%d %H:%M")
    lines.append(f"# {header_time} ユニット数：{total_unit_count}  ポケモンGO 検索キーワード")
    lines.append("")

    # ---- 冒頭固定ブロック（9.3）----
    lines.append("# 100%個体")
    lines.append("4*")
    lines.append("")
    lines.append("# 0%個体")
    lines.append("0こうげき&0ぼうぎょ&0HP")
    # 0%個体の後はブロック区切り（空行2行）
    lines.append("")
    lines.append("")

    # ---- グループブロック（9.4）----
    active_pids = sorted(groups.keys())  # PID 昇順
    has_individual = bool(individual_slot)
    total_slots = len(active_pids) + (1 if has_individual else 0)
    slot_index = 0

    for pid in active_pids:
        slot_index += 1
        unit_indices = groups[pid]
        a, d, h = _PID_TO_ADH[pid]
        iv = _iv_expr(a, d, h)
        dex = _dex_expr(unit_indices, units)
        uc = len(unit_indices)
        label = f"G{pid:02d}"
        pos = f"{slot_index}/{total_slots}"

        # GBL用（IV式を含む）
        lines.append(f"# {label}-GBL用(位置：{pos} ユニット数：{uc} IV：{iv})：SCP重視の検索")
        lines.append(f"{dex}&{iv}{_FILTER_GBL_RAID}")
        lines.append("")

        # レイド用（固定式。グループのパターンに関わらず常に 3,4バケの式）
        lines.append(
            f"# {label}-レイド用(位置：{pos} ユニット数：{uc})"
            "：高個体(3,4こうげき&3,4ぼうぎょ&3,4HP)の検索"
        )
        lines.append(f"{dex}&3こうげき,4こうげき&3ぼうぎょ,4ぼうぎょ&3HP,4HP{_FILTER_GBL_RAID}")
        lines.append("")

        # 確認用（チェックボックス ON 時のみ）
        if show_confirm:
            lines.append(
                f"# {label}-確認用(位置：{pos} ユニット数：{uc})"
                "：お気に入り、タグ付けをしたポケモン検索"
            )
            lines.append(f"{dex}{_FILTER_CONFIRM}{_FILTER_TRADE_TAGS}")
            lines.append("")

        # 最終確認用（チェックボックス ON 時のみ）
        if show_final_confirm:
            lines.append(
                f"# {label}-最終確認用(位置：{pos} ユニット数：{uc})：すべてのポケモン検索"
            )
            lines.append(f"{dex}{_FILTER_TRADE_TAGS}")
            lines.append("")

        # 博士送り用（グループ末尾。この後はブロック区切り2行）
        lines.append(
            f"# {label}-博士送り用(位置：{pos} ユニット数：{uc})"
            "：お気に入り、タグ付けをしなかったポケモン検索"
        )
        lines.append(f"{dex}{_FILTER_SEND}")
        lines.append("")  # 1行目の空行
        lines.append("")  # 2行目の空行（ブロック区切り）

    # ---- 個別枠ブロック（9.5）----
    if has_individual:
        slot_index += 1
        pos = f"{slot_index}/{total_slots}"
        uc = len(individual_slot)
        dex = _dex_expr(individual_slot, units)

        # 個別枠 GBL用（IV式なし。仕様書 9.5）
        lines.append(f"# 個別枠-GBL用(位置：{pos} ユニット数：{uc})：SCP重視の検索")
        lines.append(f"{dex}{_FILTER_GBL_RAID}")
        lines.append("")

        lines.append(
            f"# 個別枠-レイド用(位置：{pos} ユニット数：{uc})"
            "：高個体(3,4こうげき&3,4ぼうぎょ&3,4HP)の検索"
        )
        lines.append(f"{dex}&3こうげき,4こうげき&3ぼうぎょ,4ぼうぎょ&3HP,4HP{_FILTER_GBL_RAID}")
        lines.append("")

        if show_confirm:
            lines.append(
                f"# 個別枠-確認用(位置：{pos} ユニット数：{uc})"
                "：お気に入り、タグ付けをしたポケモン検索"
            )
            lines.append(f"{dex}{_FILTER_CONFIRM}{_FILTER_TRADE_TAGS}")
            lines.append("")

        if show_final_confirm:
            lines.append(f"# 個別枠-最終確認用(位置：{pos} ユニット数：{uc})：すべてのポケモン検索")
            lines.append(f"{dex}{_FILTER_TRADE_TAGS}")
            lines.append("")

        lines.append(
            f"# 個別枠-博士送り用(位置：{pos} ユニット数：{uc})"
            "：お気に入り、タグ付けをしなかったポケモン検索"
        )
        lines.append(f"{dex}{_FILTER_SEND}")
        # 個別枠末尾は空行1行（= 末尾固定ブロック前の空行 と兼用、仕様書 9.8・9.9）
        lines.append("")
    else:
        lines.append("# 個別枠-該当なし")
        # 個別枠-該当なし後も空行1行
        lines.append("")

    # ---- 末尾固定ブロック（9.8）----
    lines.append("# 最後の確認用")
    lines.append("!お気に入り&!#&!しゃどう&!色違い&!だいまっくす&!きょだいまっくす")
    lines.append("")
    lines.append("# 伝説,幻,ウルトラビースト")
    lines.append("伝説のポケモン,まぼろし,ウルトラビースト&!お気に入り&!#")
    lines.append("")
    lines.append("# ダイマックス、キョダイマックス")
    lines.append("だいまっくす,きょだいまっくす&!お気に入り&!#")
    lines.append("")
    lines.append("# 色違い")
    lines.append("色違い&!お気に入り&!#")
    # 色違いの後は空行なし（仕様書 9.9）

    return "\n".join(lines)
