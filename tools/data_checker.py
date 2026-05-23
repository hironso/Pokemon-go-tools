# -*- coding: utf-8 -*-
"""
data_checker.py

pokedex_numbers.txt / evolution_map.txt / iv_list_input.txt / slim_cache.json
の整合性チェックツール。

チェック内容：
  ① pokedex_numbers.txt のフォーマット・重複チェック
  ② evolution_map.txt のフォーマット・整合性チェック
  ③ iv_list_input.txt のフォーマット・整合性チェック
  ④ slim_cache.json との整合性チェック
     - iv_list_input.txt の O/M/L 展開後の target_species が
       slim_cache.json に存在するか

出力先: tools/data_checker_result.txt
"""

import os
import sys
import json
from datetime import datetime

# ============================================================
# パス定義
# ============================================================
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.join(BASE_DIR, "..", "shared")

POKEDEX_FILE   = os.path.join(SHARED_DIR, "pokedex_numbers.txt")
EVOLUTION_FILE = os.path.join(SHARED_DIR, "evolution_map.txt")
INPUT_FILE     = os.path.join(SHARED_DIR, "iv_list_input.txt")
SLIM_CACHE_FILE = os.path.join(SHARED_DIR, "slim_cache.json")
SUPPORT_FILE   = os.path.join(BASE_DIR, "data_checker_support.txt")
OUTPUT_FILE    = os.path.join(BASE_DIR, "data_checker_result.txt")

# ============================================================
# ユーティリティ
# ============================================================
def read_lines(path):
    """UTF-8でファイルを読み、空行と#始まりを除いた行と元の行番号を返す。"""
    lines = []
    with open(path, "r", encoding="utf-8") as f:
        for idx, raw in enumerate(f, start=1):
            line = raw.rstrip("\n\r")
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            lines.append((idx, line))
    return lines

# ============================================================
# 抑止ファイル読み込み
# ============================================================
def parse_support_file():
    """data_checker_support.txt から抑止対象を取得する。"""
    support = {
        "evol_missing": set(),
        "pokedex_dup":  set(),
    }
    if not os.path.exists(SUPPORT_FILE):
        return support

    current_cat = None
    with open(SUPPORT_FILE, "r", encoding="utf-8") as f:
        for raw in f:
            stripped = raw.strip()
            if stripped.startswith("##"):
                header = stripped.lstrip("#").strip()
                if "図鑑番号" in header:
                    current_cat = "pokedex_dup"
                elif "無いポケモン" in header or "進化系がない" in header:
                    current_cat = "evol_missing"
                else:
                    current_cat = None
                continue
            if stripped.startswith("#") or not stripped:
                continue
            if current_cat == "evol_missing":
                support["evol_missing"].add(stripped)
            elif current_cat == "pokedex_dup":
                support["pokedex_dup"].add(stripped)
    return support

# ============================================================
# ① pokedex_numbers.txt チェック
# ============================================================
def check_pokedex(support):
    errors = []
    warnings = []
    suppressed = []

    if not os.path.exists(POKEDEX_FILE):
        errors.append(f"[ERROR] pokedex_numbers.txt が見つかりません: {POKEDEX_FILE}")
        return set(), errors, warnings, suppressed

    lines = read_lines(POKEDEX_FILE)
    pokedex_names = set()
    name_count = {}
    dex_to_names = {}

    for lineno, line in lines:
        parts = line.split("\t")
        if len(parts) != 5:
            errors.append(f"[ERROR] pokedex_numbers.txt 行{lineno}: 列数が5ではありません -> {line}")
            continue

        name, dex_str, hp_str, atk_str, def_str = (p.strip() for p in parts)

        if not name:
            errors.append(f"[ERROR] pokedex_numbers.txt 行{lineno}: ポケモン名が空です -> {line}")
            continue

        try:
            dex  = int(dex_str)
            hp   = int(hp_str)
            atk  = int(atk_str)
            defe = int(def_str)
        except ValueError:
            errors.append(f"[ERROR] pokedex_numbers.txt 行{lineno}: 数値が不正です -> {line}")
            continue

        if dex < 1 or hp < 1 or atk < 1 or defe < 1:
            errors.append(f"[ERROR] pokedex_numbers.txt 行{lineno}: 1未満の値があります -> {line}")
            continue

        pokedex_names.add(name)
        name_count[name] = name_count.get(name, 0) + 1
        dex_to_names.setdefault(dex, []).append(name)

    for nm, count in name_count.items():
        if count > 1:
            warnings.append(f"[WARN ] pokedex_numbers.txt: ポケモン名が重複しています -> {nm}")

    for dex, names in dex_to_names.items():
        unique_names = sorted(set(names))
        if len(unique_names) > 1:
            combo_str = f"{dex}:{','.join(unique_names)}"
            if combo_str in support.get("pokedex_dup", set()):
                suppressed.append(combo_str)
            else:
                warnings.append(f"[WARN ] pokedex_numbers.txt: 図鑑番号が重複しています -> {combo_str}")

    return pokedex_names, errors, warnings, suppressed

# ============================================================
# ② evolution_map.txt チェック
# ============================================================
def check_evolution_map(pokedex_names):
    errors = []
    warnings = []

    if not os.path.exists(EVOLUTION_FILE):
        errors.append(f"[ERROR] evolution_map.txt が見つかりません: {EVOLUTION_FILE}")
        return set(), errors, warnings

    lines = read_lines(EVOLUTION_FILE)
    evo_names = set()
    name_to_family_idx = {}

    for family_idx, (lineno, line) in enumerate(lines):
        names_in_line = set()
        stages = line.split(",")
        for stage in stages:
            parts = stage.split("/")
            for part in parts:
                name = part.strip()
                if not name:
                    errors.append(f"[ERROR] evolution_map.txt 行{lineno}: 空のポケモン名があります -> {line}")
                    continue
                if name in names_in_line:
                    errors.append(f"[ERROR] evolution_map.txt 行{lineno}: 同一行内で重複しています -> {name}")
                else:
                    names_in_line.add(name)
                if name in name_to_family_idx:
                    prev_idx = name_to_family_idx[name]
                    errors.append(
                        f"[ERROR] evolution_map.txt: 複数のファミリーに属しています -> {name} "
                        f"(行{lineno}, ファミリー行インデックス {prev_idx})"
                    )
                else:
                    name_to_family_idx[name] = family_idx
                evo_names.add(name)
                if name not in pokedex_names:
                    errors.append(f"[ERROR] evolution_map.txt: pokedex_numbers.txt に存在しません -> {name}")

    return evo_names, errors, warnings

# ============================================================
# ③ iv_list_input.txt チェック
# ============================================================
def check_input(pokedex_names, evo_names):
    errors = []
    warnings = []
    suppressed = []

    if not os.path.exists(INPUT_FILE):
        errors.append(f"[ERROR] iv_list_input.txt が見つかりません: {INPUT_FILE}")
        return set(), errors, warnings, suppressed, []

    lines = read_lines(INPUT_FILE)
    input_names = set()
    seen_keys = {}
    entries = []

    for lineno, line in lines:
        parts = [p.strip() for p in line.split("/")]
        if len(parts) < 3 or len(parts) > 4:
            errors.append(f"[ERROR] iv_list_input.txt 行{lineno}: 区切り数が不正 -> {line}")
            continue

        name       = parts[0]
        leagues_str = parts[1]
        topn_str   = parts[2]
        target_str = parts[3] if len(parts) == 4 else ""

        if not name:
            errors.append(f"[ERROR] iv_list_input.txt 行{lineno}: ポケモン名が空です -> {line}")
            continue

        if name not in pokedex_names:
            errors.append(f"[ERROR] iv_list_input.txt: pokedex_numbers.txt に存在しません -> {name}")

        input_names.add(name)

        league_tokens = [t.strip() for t in leagues_str.split(",") if t.strip()]
        if not league_tokens:
            errors.append(f"[ERROR] iv_list_input.txt 行{lineno}: リーグ指定が空です -> {line}")
        for lg in league_tokens:
            if lg not in {"S", "H", "M"}:
                errors.append(f"[ERROR] iv_list_input.txt 行{lineno}: 不正なリーグ指定 -> {lg}")
                break

        try:
            topn = int(topn_str)
            if not (1 <= topn <= 4096):
                errors.append(f"[ERROR] iv_list_input.txt 行{lineno}: TopNが範囲外(1-4096) -> {line}")
        except ValueError:
            errors.append(f"[ERROR] iv_list_input.txt 行{lineno}: TopNが数値ではありません -> {line}")
            topn = None

        if target_str:
            target_tokens = [t.strip() for t in target_str.split(",") if t.strip()]
            # 1文字ずつの指定も許容（例: "M,L" -> ["M","L"] / "ML" -> ["M","L"]）
            if len(target_tokens) == 1 and len(target_tokens[0]) > 1:
                target_tokens = list(target_tokens[0])
        else:
            target_tokens = ["L"]

        for tgt in target_tokens:
            if tgt not in {"O", "M", "L"}:
                errors.append(f"[ERROR] iv_list_input.txt 行{lineno}: 不正な対象指定 -> {tgt}")
                break

        key = (name, ",".join(league_tokens), topn, ",".join(target_tokens))
        if key in seen_keys:
            first_lineno = seen_keys[key]
            warnings.append(f"[WARN ] iv_list_input.txt: 完全重複行があります -> 行{first_lineno} と 行{lineno}")
        else:
            seen_keys[key] = lineno

        entries.append((lineno, name, target_tokens, line))

    # evolution_map にないポケモンへのM/L指定チェック
    for lineno, nm, targets, line in entries:
        if nm not in evo_names:
            if any(t in {"M", "L"} for t in targets):
                errors.append(
                    f"[ERROR] iv_list_input.txt: 進化しないポケモンに M/L が指定されています -> 行{lineno}: {line}"
                )

    return input_names, errors, warnings, suppressed, entries

# ============================================================
# evolution_map.txtからファミリー構造を構築
# ============================================================
def build_evolution_families():
    families = []
    name_to_family_index = {}

    if not os.path.exists(EVOLUTION_FILE):
        return families, name_to_family_index

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
            if not family:
                continue
            idx = len(families)
            families.append(family)
            for nm in family:
                if nm not in name_to_family_index:
                    name_to_family_index[nm] = idx

    return families, name_to_family_index

# ============================================================
# ④ slim_cache.json との整合性チェック
# ============================================================
def check_slim_cache(input_entries):
    errors = []

    if not os.path.exists(SLIM_CACHE_FILE):
        errors.append(f"[ERROR] slim_cache.json が見つかりません: {SLIM_CACHE_FILE}")
        return errors

    try:
        with open(SLIM_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except Exception as e:
        errors.append(f"[ERROR] slim_cache.json の読み込みに失敗しました -> {e}")
        return errors

    if not isinstance(cache, dict) or "pokemon" not in cache:
        errors.append("[ERROR] slim_cache.json の形式が不正です（pokemon が見つかりません）。")
        return errors

    cache_names = {entry["name"] for entry in cache["pokemon"] if isinstance(entry, dict) and "name" in entry}

    families, name_to_family_index = build_evolution_families()

    for lineno, nm, targets, line in input_entries:
        if nm in name_to_family_index:
            fam = families[name_to_family_index[nm]]
        else:
            fam = [nm]

        n = len(fam)
        target_species = set()

        for t in targets:
            if t == "O":
                target_species.add(nm)
            elif t == "M":
                target_species.add(fam[1] if n >= 3 else fam[-1])
            elif t == "L":
                target_species.add(fam[-1])

        for sp in sorted(target_species):
            if sp not in cache_names:
                errors.append(
                    f"[ERROR] slim_cache.json: SCP計算対象ポケモンがキャッシュに存在しません -> "
                    f"行{lineno}: {sp}（slim_cache_builder.pyを再実行してください）"
                )

    return errors

# ============================================================
# evolution_map.txtにないポケモン名の警告
# ============================================================
def warn_input_not_in_evo(input_names, evo_names, support):
    warnings = []
    suppressed = []
    suppressed_set = support.get("evol_missing", set())
    for name in sorted(input_names):
        if name not in evo_names:
            if name in suppressed_set:
                suppressed.append(name)
            else:
                warnings.append(f"[WARN ] evolution_map.txt に無いポケモン名です。正しいですか？ -> {name}")
    return warnings, suppressed

# ============================================================
# メイン処理
# ============================================================
def main():
    output_lines = []
    error_count = 0
    warn_count = 0
    suppressed_warn_count = 0

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    support = parse_support_file()

    # ① pokedex_numbers.txt
    pokedex_names, errors, warnings, suppressed = check_pokedex(support)
    output_lines.extend(errors)
    output_lines.extend(warnings)
    error_count += len(errors)
    warn_count += len(warnings)
    suppressed_warn_count += len(suppressed)

    # ② evolution_map.txt
    evo_names, errors, warnings = check_evolution_map(pokedex_names)
    output_lines.extend(errors)
    output_lines.extend(warnings)
    error_count += len(errors)
    warn_count += len(warnings)

    # ③ iv_list_input.txt
    input_names, errors, warnings, suppressed, input_entries = check_input(pokedex_names, evo_names)
    output_lines.extend(errors)
    output_lines.extend(warnings)
    error_count += len(errors)
    warn_count += len(warnings)
    suppressed_warn_count += len(suppressed)

    # evolution_map.txtにないポケモン名の警告
    warnings, suppressed = warn_input_not_in_evo(input_names, evo_names, support)
    output_lines.extend(warnings)
    warn_count += len(warnings)
    suppressed_warn_count += len(suppressed)

    # ④ slim_cache.json との整合性チェック
    errors = check_slim_cache(input_entries)
    output_lines.extend(errors)
    error_count += len(errors)

    # 出力組み立て
    final_lines = []
    final_lines.append("=" * 40)
    final_lines.append(f"{timestamp} 実行結果")
    final_lines.append("=" * 40)
    final_lines.append("")
    if output_lines:
        final_lines.extend(output_lines)
    else:
        final_lines.append("問題は見つかりませんでした。")
    final_lines.append("")
    final_lines.append("-" * 40)
    final_lines.append(f"ERROR: {error_count} 件")
    final_lines.append(f"WARN : {warn_count} 件")
    final_lines.append(f"SUPPRESS WARN: {suppressed_warn_count} 件")
    final_lines.append("")
    if error_count == 0:
        final_lines.append("すべてのファイルの整合性チェックが完了しました。問題は見つかりませんでした。")
    else:
        final_lines.append("すべてのファイルの整合性チェックが完了しました。修正が必要な問題があります。")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(final_lines))

    for line in final_lines:
        print(line)

    sys.exit(1 if error_count > 0 else 0)


if __name__ == "__main__":
    main()
