# -*- coding: utf-8 -*-
"""
poke_id_generator/app.py

Streamlit版 ポケモンID生成ツール
- テキストエリアにポケモン名を入力して
- 進化ファミリー全員の図鑑番号をカンマ区切りで出力する
"""

import os
import streamlit as st

# ============================================================
# パス定義
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.join(BASE_DIR, "..", "shared")

POKEDEX_FILE   = os.path.join(SHARED_DIR, "pokedex_numbers.txt")
EVOLUTION_FILE = os.path.join(SHARED_DIR, "evolution_map.txt")

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
            if len(parts) < 2:
                continue
            try:
                pokedex[parts[0]] = int(parts[1])
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

# ============================================================
# ファミリー検索
# ============================================================
def find_family(name, evo_map):
    for family in evo_map:
        if name in family:
            return family
    return [name]

# ============================================================
# Streamlit UI
# ============================================================
st.set_page_config(page_title="ポケモンID生成ツール", page_icon="🎮", layout="wide")
st.title("🎮 ポケモンID生成ツール")
st.caption("ポケモン名を入力すると、進化ファミリー全員の図鑑番号を出力します。")

# データ読み込み
try:
    pokedex = load_pokedex()
    evo_map = load_evolution_map()
    st.success(f"図鑑データ読み込み済み（{len(pokedex)}種）")
except Exception as e:
    st.error(f"データ読み込みエラー: {e}")
    st.stop()

# テキストエリア入力
input_text = st.text_area(
    "ポケモン名を入力（1行1ポケモン）",
    height=200,
    placeholder="ヒトカゲ\nフシギダネ\nピカチュウ",
)

if st.button("生成"):
    if not input_text.strip():
        st.warning("ポケモン名を入力してください。")
        st.stop()

    input_names = [
        line.strip()
        for line in input_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    if not input_names:
        st.warning("有効なポケモン名がありません。")
        st.stop()

    # エラーチェック
    errors = []
    for name in input_names:
        if name not in pokedex:
            errors.append(f"「{name}」はpokedex_numbers.txtに存在しません")

    if errors:
        st.error("エラーがあります：")
        for e in errors:
            st.write(f"- {e}")
        st.stop()

    # 図鑑番号収集
    dex_set = set()
    for name in input_names:
        family = find_family(name, evo_map)
        for member in family:
            if member in pokedex:
                dex_set.add(pokedex[member])

    result = ",".join(str(d) for d in sorted(dex_set))
    output_text = f"ポケモンID\n{result}\n"

    st.success("生成完了！")
    st.subheader("結果")
    st.code(result, language="text")

    st.download_button(
        label="📥 poke_id.txt をダウンロード",
        data=output_text.encode("utf-8"),
        file_name="poke_id.txt",
        mime="text/plain",
    )
