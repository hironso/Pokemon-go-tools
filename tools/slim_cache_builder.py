# -*- coding: utf-8 -*-
"""
slim_cache_builder.py

役割：
- iv_list_input.txt / pokedex_numbers.txt / evolution_map.txt を入力として
- iv_list_input.txt で参照されるポケモン×リーグの組み合わせに限定して
- SCPランキング上位TopN件を計算し
- slim_cache.json として出力する

出力フォーマット（entries の1要素は 1行のCSV文字列）：
    "rank,atk_bucket,def_bucket,hp_bucket,atk_real"

  - rank       : 1始まりの順位（SCP降順）
  - atk_bucket : 攻撃IVのバケット (0〜4)
  - def_bucket : 防御IVのバケット (0〜4)
  - hp_bucket  : HPIVのバケット   (0〜4)
  - atk_real   : 攻撃実数値（小数点以下2桁）

バケット定義：
  0: IV=0
  1: IV=1〜5
  2: IV=6〜10
  3: IV=11〜14
  4: IV=15

配置：
  このファイルは tools/ フォルダに置く。
  参照ファイル：
    ../shared/pokedex_numbers.txt
    ../shared/evolution_map.txt
    ../shared/iv_list_input.txt  ← iv_strings_generatorと共通
  出力ファイル：
    ../shared/slim_cache.json
"""

import os
import json
import math
from datetime import datetime

# ============================================================
# パス定義
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.join(BASE_DIR, "..", "shared")

POKEDEX_FILE   = os.path.join(SHARED_DIR, "pokedex_numbers.txt")
EVOLUTION_FILE = os.path.join(SHARED_DIR, "evolution_map.txt")
INPUT_FILE     = os.path.join(SHARED_DIR, "iv_list_input.txt")
OUTPUT_FILE    = os.path.join(SHARED_DIR, "slim_cache.json")

# ============================================================
# 定数
# ============================================================
LEAGUE_CAPS = {
    "S": 1500,
    "H": 2500,
    "M": None,
}

SCRIPT_VERSION = "1.0"

# ============================================================
# CPM テーブル
# ============================================================
CPM = {
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

# ============================================================
# バケット変換
# ============================================================
def iv_to_bucket(iv: int) -> int:
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
def calc_cp(base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, level):
    cpm = CPM[level]
    return math.floor(
        ((base_atk + iv_atk)
         * math.sqrt(base_def + iv_def)
         * math.sqrt(base_sta + iv_hp)
         * (cpm ** 2)) / 10.0
    )

def calc_stats(base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, level):
    cpm = CPM[level]
    atk  = (base_atk + iv_atk) * cpm
    deff = (base_def + iv_def) * cpm
    hp   = math.floor((base_sta + iv_hp) * cpm)
    return atk, deff, hp

def calc_scp(atk, deff, hp):
    return math.floor(((atk * deff * hp) ** (2.0 / 3.0)) / 10.0)

def best_within_cap(base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, cap_cp):
    best = None
    for level in [x * 0.5 for x in range(2, 103)]:
        if level not in CPM:
            continue
        cp = calc_cp(base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, level)
        if cap_cp is not None and cp > cap_cp:
            break
        atk, deff, hp = calc_stats(base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, level)
        scp = calc_scp(atk, deff, hp)
        if best is None or scp > best["scp"]:
            best = {"level": level, "cp": cp, "atk": atk, "def": deff, "hp": hp, "scp": scp}
    return best

# ============================================================
# 全IV計算 → TopN件をslim形式に変換
# ============================================================
def calc_slim_entries(base_stat, cap_cp, topn):
    base_atk = base_stat["atk_base"]
    base_def = base_stat["def_base"]
    base_sta = base_stat["hp_base"]

    results = []
    for iv_atk in range(16):
        for iv_def in range(16):
            for iv_hp in range(16):
                best = best_within_cap(base_atk, base_def, base_sta,
                                       iv_atk, iv_def, iv_hp, cap_cp)
                if best is None:
                    continue
                results.append({
                    "iv_atk": iv_atk,
                    "iv_def": iv_def,
                    "iv_hp":  iv_hp,
                    "atk":    best["atk"],
                    "scp":    best["scp"],
                    "cp":     best["cp"],
                    "level":  best["level"],
                })

    # SCP → atk → cp → level の優先順位で降順ソート
    results.sort(
        key=lambda x: (x["scp"], x["atk"], x["cp"], x["level"]),
        reverse=True,
    )

    # TopN件に絞る
    results = results[:topn]

    # slim形式に変換: "rank,atk_bucket,def_bucket,hp_bucket,atk_real"
    entries = []
    for rank, r in enumerate(results, 1):
        atk_b = iv_to_bucket(r["iv_atk"])
        def_b = iv_to_bucket(r["iv_def"])
        hp_b  = iv_to_bucket(r["iv_hp"])
        atk_real = f"{r['atk']:.2f}"
        entries.append(f"{rank},{atk_b},{def_b},{hp_b},{atk_real}")

    return entries

# ============================================================
# pokedex_numbers.txt 読み込み
# ============================================================
def load_pokedex():
    if not os.path.exists(POKEDEX_FILE):
        raise FileNotFoundError(f"[ERROR] pokedex_numbers.txt が見つかりません: {POKEDEX_FILE}")

    pokedex = {}
    with open(POKEDEX_FILE, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "\t" not in line:
                raise ValueError(f"[ERROR] pokedex_numbers.txt {line_number}行目: タブ区切りではありません")
            parts = [p.strip() for p in line.split("\t")]
            if len(parts) < 5:
                raise ValueError(f"[ERROR] pokedex_numbers.txt {line_number}行目: 列数不足")
            name = parts[0]
            try:
                dex      = int(parts[1])
                hp_base  = int(parts[2])
                atk_base = int(parts[3])
                def_base = int(parts[4])
            except ValueError:
                raise ValueError(f"[ERROR] pokedex_numbers.txt {line_number}行目: 数値変換失敗")
            pokedex[name] = {
                "dex": dex, "hp_base": hp_base,
                "atk_base": atk_base, "def_base": def_base,
            }
    return pokedex

# ============================================================
# evolution_map.txt 読み込み
# ============================================================
def load_evolution_map():
    if not os.path.exists(EVOLUTION_FILE):
        raise FileNotFoundError(f"[ERROR] evolution_map.txt が見つかりません: {EVOLUTION_FILE}")

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

# ============================================================
# iv_list_input.txt パース
# ============================================================
def parse_input(evo_map, pokedex):
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"[ERROR] iv_list_input.txt が見つかりません: {INPUT_FILE}")

    # name -> family のマップを構築
    name_to_family = {}
    for family in evo_map:
        for name in family:
            name_to_family[name] = family

    # 計算対象: {ポケモン名: {リーグ: topn}} を収集
    # 同じポケモン×リーグで複数行ある場合は最大TopNを採用
    target_map = {}  # key: ポケモン名, value: {league: topn}

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = [p.strip() for p in line.split("/")]
            if len(parts) < 3:
                raise ValueError(f"[ERROR] iv_list_input.txt {line_number}行目: 形式不正")

            original_name = parts[0]
            leagues_str   = parts[1]
            topn_str      = parts[2]
            targets_str   = parts[3].strip() if len(parts) >= 4 and parts[3].strip() else "L"

            # ポケモン名チェック
            if original_name not in pokedex:
                raise ValueError(f"[ERROR] pokedex_numbers.txt に「{original_name}」が見つかりません")

            # リーグパース
            leagues = []
            for lg in leagues_str.split(","):
                lg = lg.strip()
                if lg not in LEAGUE_CAPS:
                    raise ValueError(f"[ERROR] iv_list_input.txt {line_number}行目: 不正なリーグ指定: {lg}")
                if lg not in leagues:
                    leagues.append(lg)

            # TopNパース
            try:
                topn = int(topn_str)
            except ValueError:
                raise ValueError(f"[ERROR] iv_list_input.txt {line_number}行目: TopNが整数ではありません")
            if not (1 <= topn <= 4096):
                raise ValueError(f"[ERROR] iv_list_input.txt {line_number}行目: TopNは1〜4096で指定してください")

            # 対象指定パース（O/M/L）
            if "," in targets_str:
                raw_targets = [t.strip() for t in targets_str.split(",") if t.strip()]
            else:
                raw_targets = list(targets_str)

            targets = []
            for t in raw_targets:
                if t not in ("O", "M", "L"):
                    raise ValueError(f"[ERROR] iv_list_input.txt {line_number}行目: 不正な対象指定: {t}")
                if t not in targets:
                    targets.append(t)

            # O/M/L展開 → 対象ポケモン種を確定
            family = name_to_family.get(original_name)
            fam = family if family else [original_name]
            n = len(fam)

            target_species = set()
            for t in targets:
                if t == "O":
                    target_species.add(original_name)
                elif t == "M":
                    if n >= 3:
                        target_species.add(fam[1])
                    else:
                        target_species.add(fam[-1])
                elif t == "L":
                    target_species.add(fam[-1])

            # target_mapに登録（同じポケモン×リーグは最大TopNを採用）
            for sp_name in target_species:
                if sp_name not in pokedex:
                    raise ValueError(f"[ERROR] pokedex_numbers.txt に「{sp_name}」が見つかりません")
                if sp_name not in target_map:
                    target_map[sp_name] = {}
                for lg in leagues:
                    existing = target_map[sp_name].get(lg, 0)
                    target_map[sp_name][lg] = max(existing, topn)

    return target_map

# ============================================================
# メイン処理
# ============================================================
def main():
    print("=== slim_cache 生成開始 ===")

    # ファイル読み込み
    print("pokedex_numbers.txt を読み込み中...")
    pokedex = load_pokedex()
    print(f"  ポケモン種類数: {len(pokedex)}")

    print("evolution_map.txt を読み込み中...")
    evo_map = load_evolution_map()

    print("iv_list_input.txt を解析中...")
    target_map = parse_input(evo_map, pokedex)

    total = sum(len(leagues) for leagues in target_map.values())
    print(f"  計算対象: {len(target_map)}種 × リーグ合計 {total}件")

    # 計算
    pokemon_entries = []
    count = 0
    for name, league_topn in sorted(target_map.items(),
                                     key=lambda x: pokedex[x[0]]["dex"]):
        base_stat = pokedex[name]
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

        pokemon_entries.append({
            "name": name,
            "dex":  base_stat["dex"],
            "leagues": leagues_data,
        })

    # JSON出力
    cache_object = {
        "meta": {
            "script_version": SCRIPT_VERSION,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "total_pokemon": len(pokemon_entries),
            "total_entries": total,
        },
        "pokemon": pokemon_entries,
    }

    print(f"slim_cache.json を保存中: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_object, f, ensure_ascii=False, separators=(",", ":"))

    print("=== slim_cache 生成完了 ===")
    print(f"  出力先: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
