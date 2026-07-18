# -*- coding: utf-8 -*-
"""
id_generator/app.py

Streamlit エントリポイント（UI 層）。
ロジックは src/id_generator/id_generator.py、
データ読み込みは src/esal/pokedex_reader.py に委譲する。
"""

import sys
from pathlib import Path

import streamlit as st

# streamlit run はこの app.py があるフォルダ（id_generator/）を起点に import を探すため、
# 1つ上のプロジェクトルート（src/ がある場所）を import 経路に加える。
# これがないと `from src...` が ModuleNotFoundError になる。
# Path(__file__) 基準で解決するので、どこから起動しても・Streamlit Cloud でも動く。
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.esal.pokedex_reader import load_evolution_map, load_pokedex  # noqa: E402
from src.id_generator.id_generator import (  # noqa: E402
    NoValidInputError,
    UnknownPokemonError,
    generate_ids,
)

# ============================================================
# ページ設定
# ============================================================
st.set_page_config(page_title="ポケモンID生成ツール", page_icon="🎮", layout="wide")
st.title("🎮 ポケモンID生成ツール")
st.caption("ポケモン名を入力すると、進化ファミリー全員の図鑑番号を出力します。")

# ============================================================
# データ読み込み（@st.cache_data でセッション内キャッシュ）
# ============================================================


@st.cache_data
def _cached_pokedex() -> dict[str, int]:
    return load_pokedex()


@st.cache_data
def _cached_evo_map() -> list[list[str]]:
    return load_evolution_map()


try:
    pokedex = _cached_pokedex()
    evo_map = _cached_evo_map()
    st.success(f"図鑑データ読み込み済み（{len(pokedex)}種）")
except Exception as e:
    st.error(f"データ読み込みエラー: {e}")
    st.stop()

# ============================================================
# テキストエリア入力
# ============================================================
input_text = st.text_area(
    "ポケモン名を入力（1行1ポケモン）",
    height=200,
    placeholder="ヒトカゲ\nフシギダネ\nピカチュウ",
)

if st.button("生成"):
    try:
        result = generate_ids(input_text, pokedex, evo_map)
    except NoValidInputError as e:
        st.warning(str(e))
        st.stop()
    except UnknownPokemonError as e:
        st.error("以下のポケモン名は図鑑データに存在しません：")
        for name in e.unknown_names:
            st.write(f"- 「{name}」")
        st.stop()
    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
        st.stop()

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