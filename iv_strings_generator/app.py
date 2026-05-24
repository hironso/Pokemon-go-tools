# -*- coding: utf-8 -*-
"""
iv_strings_generator/app.py

Streamlit版 IVサーチ文字列ジェネレーター
- iv_list_input.txt をアップロードして
- slim_cache.json を参照し
- ポケモンGOボックス検索キーワード（iv_list_output.txt）を生成する
"""

import os
import json
import math
import streamlit as st
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from io import StringIO

# ============================================================
# パス定義
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.join(BASE_DIR, "..", "shared")

POKEDEX_FILE   = os.path.join(SHARED_DIR, "pokedex_numbers.txt")
EVOLUTION_FILE = os.path.join(SHARED_DIR, "evolution_map.txt")
SLIM_CACHE_FILE = os.path.join(SHARED_DIR, "slim_cache.json")

# ============================================================
# 定数
# ============================================================
LEAGUE_CAPS = {"S": 1500, "H": 2500, "M": None}

EXCLUDE_FILTER_GBL_RAID = "&!お気に入り&!#&!しゃどう&!だいまっくす&!きょだいまっくす"
EXCLUDE_FILTER_SEND     = "&!お気に入り&!#&!しゃどう&!色違い&!だいまっくす&!きょだいまっくす"
CONFIRM_FILTER          = "&お気に入り,#&!しゃどう&!だいまっくす&!きょだいまっくす"
EXCLUDE_TRADE_TAGS      = "&!#交換&!#内交換&!#100km&!#300km"

GROUP_PATTERNS = [
    (1,  {0,1},          {3,4},        {3,4}),
    (2,  {0,1},          {2,3,4},      {3,4}),
    (3,  {0,1},          {3,4},        {2,3,4}),
    (4,  {0,1},          {2,3,4},      {2,3,4}),
    (5,  {0,1},          {1,2,3,4},    {2,3,4}),
    (6,  {0,1},          {2,3,4},      {1,2,3,4}),
    (7,  {0,1,2},        {3,4},        {3,4}),
    (8,  {0,1,2},        {2,3,4},      {3,4}),
    (9,  {0,1,2},        {3,4},        {2,3,4}),
    (10, {0,1,2},        {2,3,4},      {2,3,4}),
    (11, {0,1,2},        {1,2,3,4},    {2,3,4}),
    (12, {0,1,2},        {2,3,4},      {1,2,3,4}),
    (13, {0,1,2,3},      {2,3,4},      {2,3,4}),
    (14, {0,1,2,3},      {1,2,3,4},    {2,3,4}),
    (15, {0,1,2,3},      {2,3,4},      {1,2,3,4}),
    (16, {0,1,2,3,4},    {3,4},        {3,4}),
    (17, {0,1,2,3,4},    {2,3,4},      {3,4}),
    (18, {0,1,2,3,4},    {3,4},        {2,3,4}),
    (19, {0,1,2,3,4},    {2,3,4},      {2,3,4}),
    (20, {0,1,2,3,4},    {1,2,3,4},    {2,3,4}),
    (21, {0,1,2,3,4},    {2,3,4},      {1,2,3,4}),
    (22, {0,1},          {1,2,3,4},    {1,2,3,4}),
    (23, {0,1,2},        {1,2,3,4},    {1,2,3,4}),
]

# ============================================================
# データ読み込み（キャッシュ付き）
# ============================================================
@st.cache_data
def load_pokedex():
    pokedex = {}
    with open(POKEDEX_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("\t")]
            if len(parts) < 5:
                continue
            try:
                pokedex[parts[0]] = {
                    "dex": int(parts[1]),
                    "hp_base": int(parts[2]),
                    "atk_base": int(parts[3]),
                    "def_base": int(parts[4]),
                }
            except ValueError:
                continue
    return pokedex

@st.cache_data
def load_evolution_map():
    evo_map = []
    with open(EVOLUTION_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            tokens = [p.strip() for p in line.split(",") if p.strip()]
            expanded = []
            for tok in tokens:
                if "/" in tok:
                    expanded.extend([x.strip() for x in tok.split("/") if x.strip()])
                else:
                    expanded.append(tok)
            seen = set()
            family = []
            for x in expanded:
                if x not in seen:
                    family.append(x)
                    seen.add(x)
            if family:
                evo_map.append(family)
    return evo_map

@st.cache_data
def load_slim_cache():
    with open(SLIM_CACHE_FILE, "r", encoding="utf-8") as f:
        cache = json.load(f)
    name_to_cache = {}
    for entry in cache["pokemon"]:
        name_to_cache[entry["name"]] = entry
    return name_to_cache

# ============================================================
# バケット変換
# ============================================================
def bucket_set_to_expr(bucket_set, kind: str) -> str:
    if not bucket_set:
        return ""
    parts = [f"{b}{kind}" for b in sorted(bucket_set)]
    return ",".join(parts)

# ============================================================
# slim_cache → バケット変換
# ============================================================
def expand_slim_entries(cache_entry, leagues, topn):
    """slim_cache.jsonから指定リーグ・TopN件のバケットデータを取得する"""
    leagues_result = {}
    league_map = cache_entry.get("leagues", {})

    for lg in leagues:
        lg_info = league_map.get(lg)
        if not lg_info:
            continue

        entries = lg_info.get("entries", [])
        # slim_cacheのtopnと要求topnの小さい方を使う
        cached_topn = lg_info.get("topn", len(entries))
        use_topn = min(topn, cached_topn, len(entries))

        converted = []
        for ent in entries[:use_topn]:
            parts = ent.split(",")
            if len(parts) < 5:
                continue
            try:
                rank     = int(parts[0])
                atk_b    = int(parts[1])
                def_b    = int(parts[2])
                hp_b     = int(parts[3])
                atk_real = float(parts[4])
            except ValueError:
                continue
            converted.append({
                "rank":     rank,
                "atk_bucket": atk_b,
                "def_bucket": def_b,
                "hp_bucket":  hp_b,
                "atk_real":   atk_real,
            })

        if converted:
            leagues_result[lg] = converted

    return leagues_result

# ============================================================
# バケット選抜ロジック
# ============================================================
def choose_buckets_from_results(results, topn, league_code, species_name):
    if not results:
        return set(), set(), set()

    total = len(results)
    top30_count = max(1, int(round(total * 0.30)))
    top30_results = results[:top30_count]

    atk_total = defaultdict(int)
    def_total = defaultdict(int)
    hp_total  = defaultdict(int)
    atk_top   = defaultdict(int)
    def_top   = defaultdict(int)
    hp_top    = defaultdict(int)

    for r in results:
        atk_total[r["atk_bucket"]] += 1
        def_total[r["def_bucket"]] += 1
        hp_total[r["hp_bucket"]]   += 1

    for r in top30_results:
        atk_top[r["atk_bucket"]] += 1
        def_top[r["def_bucket"]] += 1
        hp_top[r["hp_bucket"]]   += 1

    def select_by_10percent(total_map, top_map):
        selected = set()
        for b, cnt in total_map.items():
            if cnt / total >= 0.10:
                selected.add(b)
        if len(top30_results) > 0:
            for b, cnt in top_map.items():
                if cnt / len(top30_results) >= 0.10:
                    selected.add(b)
        return selected

    atk_sel = select_by_10percent(atk_total, atk_top)
    def_sel = select_by_10percent(def_total, def_top)
    hp_sel  = select_by_10percent(hp_total,  hp_top)

    # SCP70拡張＋攻撃実数値強化
    if total <= 70:
        scp_extended = list(results)
    else:
        last_rank_70 = results[69]["rank"]
        scp_extended = [r for r in results if r["rank"] <= last_rank_70]

    scp_extended_sorted = sorted(scp_extended, key=lambda r: r["atk_real"], reverse=True)
    if scp_extended_sorted:
        top_k = min(20, len(scp_extended_sorted))
        kth_value = scp_extended_sorted[top_k - 1]["atk_real"]
        forced_atk_buckets = {
            r["atk_bucket"] for r in scp_extended_sorted if r["atk_real"] >= kth_value
        }
        atk_sel |= forced_atk_buckets

    def fallback(selected, total_map, top_map):
        if selected:
            return selected
        if top_map:
            return {b for b, cnt in top_map.items() if cnt > 0}
        if total_map:
            return {b for b, cnt in total_map.items() if cnt > 0}
        return set()

    atk_sel = fallback(atk_sel, atk_total, atk_top)
    def_sel = fallback(def_sel, def_total, def_top)
    hp_sel  = fallback(hp_sel,  hp_total,  hp_top)

    return atk_sel, def_sel, hp_sel

# ============================================================
# input.txt パース
# ============================================================
def parse_input(text, pokedex, evo_map):
    name_to_family = {}
    for family in evo_map:
        for name in family:
            name_to_family[name] = family

    requests = []
    errors = []

    for line_number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = [p.strip() for p in line.split("/")]
        if len(parts) < 3:
            errors.append(f"{line_number}行目: 形式不正 → {line}")
            continue

        original_name = parts[0]
        leagues_str   = parts[1]
        topn_str      = parts[2]
        targets_str   = parts[3].strip() if len(parts) >= 4 and parts[3].strip() else "L"

        if original_name not in pokedex:
            errors.append(f"{line_number}行目: pokedex未収録 → {original_name}")
            continue

        leagues = []
        valid = True
        for lg in leagues_str.split(","):
            lg = lg.strip()
            if lg not in LEAGUE_CAPS:
                errors.append(f"{line_number}行目: 不正なリーグ → {lg}")
                valid = False
                break
            if lg not in leagues:
                leagues.append(lg)
        if not valid:
            continue

        try:
            topn = int(topn_str)
        except ValueError:
            errors.append(f"{line_number}行目: TopNが整数ではありません → {topn_str}")
            continue
        if not (1 <= topn <= 4096):
            errors.append(f"{line_number}行目: TopNは1〜4096で指定してください → {topn}")
            continue

        if "," in targets_str:
            raw_targets = [t.strip() for t in targets_str.split(",") if t.strip()]
        else:
            raw_targets = list(targets_str)

        targets = []
        valid = True
        for t in raw_targets:
            if t not in ("O", "M", "L"):
                errors.append(f"{line_number}行目: 不正な対象指定 → {t}")
                valid = False
                break
            if t not in targets:
                targets.append(t)
        if not valid:
            continue

        requests.append((original_name, leagues, topn, targets))

    return requests, errors

# ============================================================
# メイン処理
# ============================================================
def generate_output(requests, pokedex, evo_map, name_to_cache):
    name_to_family = {}
    for family in evo_map:
        for name in family:
            name_to_family[name] = family

    detail_map = {}
    missing_cache_names = set()
    progress = st.progress(0)
    total = len(requests)

    for i, (original_name, leagues, topn, targets) in enumerate(requests):
        progress.progress((i + 1) / total, text=f"処理中... {i+1}/{total} ({original_name})")

        family = name_to_family.get(original_name)
        fam = family if family else [original_name]
        n = len(fam)

        target_species = set()
        for t in targets:
            if t == "O":
                target_species.add(original_name)
            elif t == "M":
                target_species.add(fam[1] if n >= 3 else fam[-1])
            elif t == "L":
                target_species.add(fam[-1])

        req_atk_b = set()
        req_def_b = set()
        req_hp_b  = set()

        for sp_name in target_species:
            cache_entry = name_to_cache.get(sp_name)
            if not cache_entry:
                missing_cache_names.add(sp_name)
                continue

            leagues_results = expand_slim_entries(cache_entry, leagues, topn)
            for lg, results in leagues_results.items():
                atk_b, def_b, hp_b = choose_buckets_from_results(results, topn, lg, sp_name)
                req_atk_b.update(atk_b)
                req_def_b.update(def_b)
                req_hp_b.update(hp_b)

        if not req_def_b or not req_hp_b:
            continue

        family_names_unique = sorted(set(fam), key=lambda n: pokedex[n]["dex"])
        dex_list = [pokedex[n]["dex"] for n in family_names_unique if n in pokedex]
        key = tuple(dex_list)

        if key not in detail_map:
            detail_map[key] = [set(), set(), set()]
        detail_map[key][0].update(req_atk_b)
        detail_map[key][1].update(req_def_b)
        detail_map[key][2].update(req_hp_b)

    progress.empty()

    if not detail_map:
        return None, missing_cache_names

    # --------------------------------------------------------
    # detail_units 構築
    # --------------------------------------------------------
    detail_units = []
    for dex_tuple, (atk_b, def_b, hp_b) in sorted(detail_map.items(), key=lambda kv: kv[0]):
        dex_list = list(dex_tuple)
        dex_expr = ",".join(str(d) for d in dex_list)

        parts = [dex_expr]
        if atk_b and atk_b != {0,1,2,3,4}:
            atk_expr = bucket_set_to_expr(atk_b, "こうげき")
            if atk_expr:
                parts.append(atk_expr)

        def_expr = bucket_set_to_expr(def_b, "ぼうぎょ")
        hp_expr  = bucket_set_to_expr(hp_b, "HP")
        if def_expr:
            parts.append(def_expr)
        if hp_expr:
            parts.append(hp_expr)

        line = "&".join(parts)
        detail_units.append({
            "dex_list": dex_list,
            "atk_b": set(atk_b),
            "def_b": set(def_b),
            "hp_b":  set(hp_b),
            "line":  line,
        })

    # --------------------------------------------------------
    # グループ分け
    # --------------------------------------------------------
    pattern_to_unit_indices = {pid: [] for pid, _, _, _ in GROUP_PATTERNS}
    num_units = len(detail_units)

    for idx, unit in enumerate(detail_units):
        for pid, patt_atk, patt_def, patt_hp in GROUP_PATTERNS:
            if (patt_atk.issuperset(unit["atk_b"]) and
                patt_def.issuperset(unit["def_b"]) and
                patt_hp.issuperset(unit["hp_b"])):
                pattern_to_unit_indices[pid].append(idx)

    assigned = set()
    pattern_assigned_units = {pid: [] for pid, _, _, _ in GROUP_PATTERNS}

    for pid, patt_atk, patt_def, patt_hp in GROUP_PATTERNS:
        candidate_indices = [i for i in pattern_to_unit_indices[pid] if i not in assigned]
        min_required = 5 if pid >= 22 else 15
        if len(candidate_indices) < min_required:
            continue
        candidate_indices.sort(key=lambda i: min(detail_units[i]["dex_list"]))
        for idx in candidate_indices:
            pattern_assigned_units[pid].append(idx)
            assigned.add(idx)

    ungrouped_indices = [i for i in range(num_units) if i not in assigned]

    # --------------------------------------------------------
    # pokemon_search_groups.txt 出力（iv_list_output.txt）
    # --------------------------------------------------------
    active_group_pids = [pid for pid, _, _, _ in GROUP_PATTERNS if pattern_assigned_units[pid]]
    group_slots = len(active_group_pids)
    has_individual_slot = bool(ungrouped_indices)
    total_slots = group_slots + (1 if has_individual_slot else 0)
    slot_index = 0
    unit_count = len(detail_units)

    lines = []

    # ヘッダ
    now = datetime.now(timezone(timedelta(hours=9)))
    header_time = now.strftime("%Y/%m/%d %H:%M")
    lines.append(f"# {header_time} ユニット数：{unit_count}  ポケモンGO 検索キーワード")
    lines.append("")

    # 固定ブロック
    lines.append("# 100%個体")
    lines.append("4*")
    lines.append("")
    lines.append("# 0%個体")
    lines.append("0こうげき&0ぼうぎょ&0HP")
    lines.append("")
    lines.append("")

    # グループブロック
    for pid, patt_atk, patt_def, patt_hp in GROUP_PATTERNS:
        unit_indices = pattern_assigned_units[pid]
        if not unit_indices:
            continue

        slot_index += 1

        dex_set = set()
        for idx in unit_indices:
            dex_set.update(detail_units[idx]["dex_list"])
        dex_expr = ",".join(str(d) for d in sorted(dex_set))

        atk_expr = bucket_set_to_expr(patt_atk, "こうげき") if patt_atk != {0,1,2,3,4} else ""
        def_expr = bucket_set_to_expr(patt_def, "ぼうぎょ") if patt_def != {0,1,2,3,4} else ""
        hp_expr  = bucket_set_to_expr(patt_hp,  "HP")      if patt_hp  != {0,1,2,3,4} else ""

        iv_comment_parts = []
        if atk_expr:
            iv_comment_parts.append(atk_expr)
        if def_expr:
            iv_comment_parts.append(def_expr)
        if hp_expr:
            iv_comment_parts.append(hp_expr)
        iv_comment = (" IV:" + "&".join(iv_comment_parts)) if iv_comment_parts else ""

        label = f"G{pid:02d}"
        uc = len(unit_indices)

        # GBL用
        lines.append(f"# {label}-GBL用(位置:{slot_index}/{total_slots} ユニット数:{uc}{iv_comment})：SCP重視＋攻撃バランスを考慮した個体を残すための検索")
        gbl_parts = [dex_expr]
        if atk_expr:
            gbl_parts.append(atk_expr)
        if def_expr:
            gbl_parts.append(def_expr)
        if hp_expr:
            gbl_parts.append(hp_expr)
        lines.append("&".join(gbl_parts) + EXCLUDE_FILTER_GBL_RAID)
        lines.append("")

        # レイド用
        lines.append(f"# {label}-レイド用(位置:{slot_index}/{total_slots} ユニット数:{uc})：攻撃個体値が高く（3〜4バケ）、防御・HPも高い個体（3〜4バケ）を探すための検索")
        lines.append(f"{dex_expr}&3こうげき,4こうげき&3ぼうぎょ,4ぼうぎょ&3HP,4HP{EXCLUDE_FILTER_GBL_RAID}")
        lines.append("")

        # 確認用
        lines.append(f"# {label}-確認用(位置:{slot_index}/{total_slots} ユニット数:{uc})：検索範囲内の個体をすべて表示して手動で確認するための検索")
        lines.append(f"{dex_expr}{CONFIRM_FILTER}{EXCLUDE_TRADE_TAGS}")
        lines.append("")

        # 最終確認用
        lines.append(f"# {label}-最終確認用(位置:{slot_index}/{total_slots} ユニット数:{uc})：最終的なBOX整理のためにすべての個体を確認するための検索")
        lines.append(f"{dex_expr}{EXCLUDE_TRADE_TAGS}")
        lines.append("")

        # 博士送り用
        lines.append(f"# {label}-博士送り用(位置:{slot_index}/{total_slots} ユニット数:{uc})：厳選・保護が終わった残りを一括で博士に送るための検索")
        lines.append(f"{dex_expr}{EXCLUDE_FILTER_SEND}")
        lines.append("")
        lines.append("")

    # 個別枠
    if ungrouped_indices:
        slot_index += 1
        uc = len(ungrouped_indices)

        leftover_dex = set()
        for idx in ungrouped_indices:
            leftover_dex.update(detail_units[idx]["dex_list"])
        dex_expr_all = ",".join(str(d) for d in sorted(leftover_dex))

        lines.append(f"# 個別枠-GBL用(まとめて検索)(位置:{slot_index}/{total_slots} ユニット数:{uc})：グループに属さない図鑑番号をまとめて検索し、SCP重視＋攻撃バランスを考慮した個体を一括で確認するための検索")
        lines.append(f"{dex_expr_all}{EXCLUDE_FILTER_GBL_RAID}")
        lines.append("")

        lines.append(f"# 個別枠-レイド用(位置:{slot_index}/{total_slots} ユニット数:{uc})：グループに属さない図鑑番号のうち、攻撃個体値が高く（3〜4バケ）、防御・HPも高い個体（3〜4バケ）を探すための検索")
        lines.append(f"{dex_expr_all}&3こうげき,4こうげき&3ぼうぎょ,4ぼうぎょ&3HP,4HP{EXCLUDE_FILTER_GBL_RAID}")
        lines.append("")

        lines.append(f"# 個別枠-確認用(位置:{slot_index}/{total_slots} ユニット数:{uc})：グループに属さない図鑑番号をすべて表示し、手動で確認するための検索")
        lines.append(f"{dex_expr_all}{CONFIRM_FILTER}{EXCLUDE_TRADE_TAGS}")
        lines.append("")

        lines.append(f"# 個別枠-最終確認用(位置:{slot_index}/{total_slots} ユニット数:{uc})：グループに属さない図鑑番号をすべて表示し、最終的なBOX整理のために目視で確認するための検索")
        lines.append(f"{dex_expr_all}{EXCLUDE_TRADE_TAGS}")
        lines.append("")

        lines.append(f"# 個別枠-博士送り用(位置:{slot_index}/{total_slots} ユニット数:{uc})：グループに属さない図鑑番号のうち、厳選・保護が終わった残りを一括で博士に送るための検索")
        lines.append(f"{dex_expr_all}{EXCLUDE_FILTER_SEND}")
        lines.append("")
    else:
        lines.append("# 個別枠-該当なし")
        lines.append("")

    # 末尾固定ブロック
    lines.append("")
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

    output_text = "\n".join(lines)
    return output_text, missing_cache_names

# ============================================================
# Streamlit UI
# ============================================================
st.set_page_config(page_title="IVサーチ文字列ジェネレーター", page_icon="🎮", layout="wide")
st.title("🎮 IVサーチ文字列ジェネレーター")
st.caption("iv_list_input.txt をアップロードして、ポケモンGOボックス検索キーワードを生成します。")

# データ読み込み
try:
    pokedex      = load_pokedex()
    evo_map      = load_evolution_map()
    name_to_cache = load_slim_cache()
    st.success(f"データ読み込み済み（図鑑: {len(pokedex)}種 / キャッシュ: {len(name_to_cache)}種）")
except Exception as e:
    st.error(f"データ読み込みエラー: {e}")
    st.stop()

# ファイルアップロード
uploaded = st.file_uploader("iv_list_input.txt をアップロード", type=["txt"])

with st.expander("iv_list_input.txt のフォーマット"):
    st.code(
        "# ポケモン名/リーグ(S,H,M)/TopN/対象指定(O,M,L)\n"
        "フシギダネ/S,H/200/L\n"
        "ピカチュウ/S/300/L\n"
        "リオル/S,H/1000/L",
        language="text"
    )

if uploaded is not None:
    text = uploaded.read().decode("utf-8")
    requests, errors = parse_input(text, pokedex, evo_map)

    if errors:
        st.error("入力エラーがあります：")
        for e in errors:
            st.write(f"- {e}")
        st.stop()

    if not requests:
        st.warning("有効な行がありません。")
        st.stop()

    st.info(f"{len(requests)}件を処理します。")

    output_text, missing = generate_output(requests, pokedex, evo_map, name_to_cache)

    if missing:
        st.warning(f"slim_cache.jsonに未収録のポケモンがありました（{len(missing)}種）：{', '.join(sorted(missing))}")

    if output_text is None:
        st.error("出力対象がありません。")
        st.stop()

    st.success("生成完了！")

    # 結果表示
    st.subheader("結果プレビュー")
    st.code(output_text, language="text")

    # ダウンロード
    st.download_button(
        label="📥 iv_list_output.txt をダウンロード",
        data=output_text.encode("utf-8"),
        file_name="iv_list_output.txt",
        mime="text/plain",
    )
