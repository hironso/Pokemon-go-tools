# -*- coding: utf-8 -*-
"""
scp_checker/app.py

Streamlit版 SCPランクチェッカー
- input.txt をアップロードして SCPランク・おすすめタグを計算・表示する
- scp_cache.json は使わず、リアルタイム計算に変更
- pokedex_numbers.txt は shared/ フォルダから参照
"""

import math
import os
import hashlib
import streamlit as st
from collections import defaultdict
from io import StringIO

# ============================================================
# パス定義
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POKEDEX_FILE = os.path.join(BASE_DIR, "..", "shared", "pokedex_numbers.txt")

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

LEAGUE_CAPS = {"S": 1500, "H": 2500, "M": None}
LEAGUE_NAMES = {"S": "スーパー", "H": "ハイパー", "M": "マスター"}

# ============================================================
# 計算ロジック（scp_cache_builder.py から移植）
# ============================================================
def calc_stats(base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, level):
    cpm = CPM[level]
    atk = (base_atk + iv_atk) * cpm
    deff = (base_def + iv_def) * cpm
    hp = math.floor((base_sta + iv_hp) * cpm)
    return atk, deff, hp

def calc_cp(base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, level):
    cpm = CPM[level]
    return math.floor(
        ((base_atk + iv_atk)
         * math.sqrt(base_def + iv_def)
         * math.sqrt(base_sta + iv_hp)
         * (cpm ** 2)) / 10.0
    )

def calc_scp(atk, deff, hp):
    return math.floor(((atk * deff * hp) ** (2.0 / 3.0)) / 10.0)

def best_within_cap(base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, cap_cp):
    best = None
    for level in [x * 0.5 for x in range(2, 103)]:
        if level not in CPM:
            continue
        cp = calc_cp(base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, level)
        if (cap_cp is not None) and (cp > cap_cp):
            break
        atk, deff, hp = calc_stats(base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, level)
        scp = calc_scp(atk, deff, hp)
        if best is None or scp > best["scp"]:
            best = {"level": level, "cp": cp, "atk": atk, "def": deff, "hp": hp, "scp": scp}
    return best

def get_rank(base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, cap_cp):
    """指定IVのSCPランクを計算して返す（全4096IVを評価）"""
    target = best_within_cap(base_atk, base_def, base_sta, iv_atk, iv_def, iv_hp, cap_cp)
    if target is None:
        return None

    target_scp = target["scp"]
    target_atk = target["atk"]

    rank = 1
    for a in range(16):
        for d in range(16):
            for h in range(16):
                if (a, d, h) == (iv_atk, iv_def, iv_hp):
                    continue
                other = best_within_cap(base_atk, base_def, base_sta, a, d, h, cap_cp)
                if other is None:
                    continue
                if (other["scp"], other["atk"]) > (target_scp, target_atk):
                    rank += 1
    return {**target, "rank": rank}

# ============================================================
# pokedex_numbers.txt 読み込み（キャッシュ付き）
# ============================================================
@st.cache_data
def load_pokedex():
    if not os.path.exists(POKEDEX_FILE):
        return None, f"pokedex_numbers.txt が見つかりません: {POKEDEX_FILE}"
    pokedex = {}
    with open(POKEDEX_FILE, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("\t")]
            if len(parts) < 5:
                continue
            name = parts[0]
            try:
                dex = int(parts[1])
                hp_base = int(parts[2])
                atk_base = int(parts[3])
                def_base = int(parts[4])
            except ValueError:
                continue
            pokedex[name] = {"dex": dex, "hp_base": hp_base, "atk_base": atk_base, "def_base": def_base}
    return pokedex, None

# ============================================================
# input.txt パース
# ============================================================
def parse_input(text):
    requests = []
    errors = []
    for i, line in enumerate(text.splitlines(), 1):
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        parts = raw.split("/")
        if len(parts) != 5:
            errors.append(f"{i}行目: 形式不正 → {raw}")
            continue
        name, league = parts[0].strip(), parts[1].strip()
        if league not in LEAGUE_CAPS:
            errors.append(f"{i}行目: 不正なリーグ → {league}")
            continue
        try:
            iv_a, iv_d, iv_h = map(int, parts[2:])
        except ValueError:
            errors.append(f"{i}行目: IVが数値ではありません → {raw}")
            continue
        if not all(0 <= v <= 15 for v in (iv_a, iv_d, iv_h)):
            errors.append(f"{i}行目: IV範囲不正(0-15) → {raw}")
            continue
        requests.append((name, league, iv_a, iv_d, iv_h))
    return requests, errors

# ============================================================
# おすすめタグ判定（scp_rank_calc.py から移植）
# ============================================================
def ceil_percent(value, rate):
    return math.ceil(value * rate)

def pick_best(candidates):
    return sorted(
        candidates,
        key=lambda x: (-x["atk"], -x["scp"], -x["hp"], x["rank"], x["input_index"])
    )[0]

def judge_tags(group):
    tags = defaultdict(set)
    max_scp = max(p["scp"] for p in group)
    scp_max_candidates = [p for p in group if p["scp"] == max_scp]
    best = pick_best(scp_max_candidates)
    tags[best["idx"]].add("★SCP最大")

    ref_scp1 = min(group, key=lambda x: x["rank"])["scp"]

    t = ceil_percent(ref_scp1, 0.99)
    cands = [p for p in group if p["scp"] >= t]
    best = pick_best(cands) if cands else min(group, key=lambda x: x["rank"])
    tags[best["idx"]].add("★SCP重視")

    t1 = ceil_percent(ref_scp1, 0.988)
    c1 = [p for p in group if p["scp"] >= t1]
    tmp = pick_best(c1)
    t2 = ceil_percent(tmp["scp"], 0.9975)
    c2 = [p for p in group if p["scp"] >= t2]
    best = pick_best(c2) if c2 else tmp
    tags[best["idx"]].add("★バランス")

    t1 = ceil_percent(ref_scp1, 0.985)
    c1 = [p for p in group if p["scp"] >= t1]
    tmp = pick_best(c1)
    t2 = ceil_percent(tmp["scp"], 0.996)
    c2 = [p for p in group if p["scp"] >= t2]
    best = pick_best(c2) if c2 else tmp
    tags[best["idx"]].add("★攻撃重視")

    return tags

# ============================================================
# Streamlit UI
# ============================================================
st.set_page_config(page_title="SCPランクチェッカー", page_icon="🎮", layout="wide")
st.title("🎮 SCPランクチェッカー")
st.caption("rank_cheker_input.txt をアップロードして、SCPランクとおすすめタグを確認できます。")

# pokedex読み込み
pokedex, pokedex_error = load_pokedex()
if pokedex_error:
    st.error(pokedex_error)
    st.stop()

st.success(f"図鑑データ読み込み済み（{len(pokedex)}種）")

# テンプレートダウンロード
TEMPLATE_FILE = os.path.join(BASE_DIR, "..", "shared", "rank_cheker_input_templete.txt")
if os.path.exists(TEMPLATE_FILE):
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        template_text = f.read()
    st.download_button(
        label="📥 テンプレートをダウンロード（rank_cheker_input_templete.txt）",
        data=template_text.encode("utf-8"),
        file_name="rank_cheker_input_templete.txt",
        mime="text/plain",
    )

# ファイルアップロード
uploaded = st.file_uploader("rank_cheker_input.txt をアップロード", type=["txt"])

# サンプルフォーマット表示
with st.expander("rank_cheker_input.txt のフォーマット"):
    st.code(
        "# ポケモン名/リーグ(S/H/M)/攻撃IV/防御IV/HPIV\n"
        "# リーグ: S=スーパー(1500) H=ハイパー(2500) M=マスター\n"
        "# IV範囲: 0〜15\n"
        "プクリン/S/1/12/6\n"
        "プクリン/S/2/14/6\n"
        "ラッキー/H/15/15/15",
        language="text"
    )

if uploaded is not None:
    text = uploaded.read().decode("utf-8")
    requests, errors = parse_input(text)

    if errors:
        st.error("入力エラーがあります：")
        for e in errors:
            st.write(f"- {e}")
        st.stop()

    if not requests:
        st.warning("有効な行がありません。")
        st.stop()

    st.info(f"{len(requests)}件を計算します。しばらくお待ちください...")
    progress = st.progress(0)

    rows = []
    for idx, (name, league, iv_a, iv_d, iv_h) in enumerate(requests):
        entry = pokedex.get(name)
        if not entry:
            st.error(f"ポケモンが見つかりません: {name}")
            st.stop()

        cap_cp = LEAGUE_CAPS[league]
        result = get_rank(entry["atk_base"], entry["def_base"], entry["hp_base"], iv_a, iv_d, iv_h, cap_cp)
        if result is None:
            st.error(f"計算失敗: {name}/{league}/{iv_a}/{iv_d}/{iv_h}")
            st.stop()

        rows.append({
            "idx": idx,
            "input": f"{name}/{league}/{iv_a}/{iv_d}/{iv_h}",
            "input_index": idx,
            "league": league,
            "name": name,
            **result,
        })
        progress.progress((idx + 1) / len(requests))

    # おすすめタグ判定
    groups = defaultdict(list)
    for r in rows:
        groups[(r["name"], r["league"])].append(r)

    tag_map = defaultdict(set)
    for g in groups.values():
        t = judge_tags(g)
        for k, v in t.items():
            tag_map[k].update(v)

    # 結果表示
    st.success("計算完了！")

    # output.txt 生成
    input_width = max(len(r["input"]) for r in rows) + 2
    HEADER_OFFSET = 5
    header_left = input_width + HEADER_OFFSET

    lines = []
    lines.append("# おすすめタグの選定条件")
    lines.append("# ★SCP最大  : 入力個体の中でSCPが最も高い個体")
    lines.append("# ★SCP重視  : SCP1位の99%以上の中で攻撃実数値が最も高い個体")
    lines.append("# ★バランス : SCP1位の98.8%以上の中で攻撃実数値最大の個体を基準に")
    lines.append("#              そのSCPの99.75%以上の中で攻撃実数値が最も高い個体")
    lines.append("# ★攻撃重視 : SCP1位の98.5%以上の中で攻撃実数値最大の個体を基準に")
    lines.append("#              そのSCPの99.6%以上の中で攻撃実数値が最も高い個体")
    lines.append("")
    header = (
        f"{'':<{header_left}}"
        f"{'SCPRANK':<8} {'SCP':<4} {'ATK':<6} {'DEF':<6} {'HP':<3} {'CP':<4} {'Level':<5}"
    )
    lines.append(header)

    prev_name = None
    prev_league = None
    for r in rows:
        if prev_name is not None and (r["name"] != prev_name or r["league"] != prev_league):
            lines.append("")
        prev_name = r["name"]
        prev_league = r["league"]

        line = (
            f"{r['input']:<{input_width}}"
            f"{r['rank']:04d}     {r['scp']:<4} "
            f"{r['atk']:<6.2f} {r['def']:<6.2f} "
            f"{r['hp']:<3} {r['cp']:<4} {r['level']:<5.1f}"
        )
        tags = " ".join(sorted(tag_map[r["idx"]]))
        if tags:
            line += "  " + tags
        lines.append(line)

    output_text = "\n".join(lines)

    # 画面表示
    st.subheader("結果")
    st.code(output_text, language="text")

    # ダウンロード
    st.download_button(
        label="📥 output.txt をダウンロード",
        data=output_text.encode("utf-8"),
        file_name="output.txt",
        mime="text/plain",
    )
