# -*- coding: utf-8 -*-
"""
iv_strings_generator/app.py

Streamlit エントリポイント（UI 層）。
ロジックは src/iv_strings_generator/iv_strings_generator.py、
データ読み込みは src/esal/iv_strings_reader.py と src/esal/pokedex_reader.py に委譲する。
"""

import sys
from pathlib import Path

import streamlit as st

# streamlit run はこの app.py があるフォルダ（iv_strings_generator/）を起点に import を探すため、
# 1つ上のプロジェクトルートを import 経路に加える。
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.esal.iv_strings_reader import load_evolution_map_staged, load_slim_cache  # noqa: E402
from src.esal.pokedex_reader import load_pokedex  # noqa: E402
from src.iv_strings_generator.iv_strings_generator import (  # noqa: E402
    NoValidUnitsError,
    generate_iv_strings,
    parse_input,
)

_TEMPLATE_FILE = _PROJECT_ROOT / "master_data" / "iv_list_input_templete.txt"

# ============================================================
# ページ設定
# ============================================================
st.set_page_config(page_title="IVサーチ文字列ジェネレーター", page_icon="🎮", layout="wide")
st.title("🎮 IVサーチ文字列ジェネレーター")
st.caption("iv_list_input.txt をアップロードして、ポケモンGOボックス検索キーワードを生成します。")

# ============================================================
# データ読み込み（@st.cache_data でセッション内キャッシュ）
# ============================================================


@st.cache_data
def _cached_pokedex() -> dict[str, int]:
    return load_pokedex()


@st.cache_data
def _cached_evo_map() -> list[list[list[str]]]:
    return load_evolution_map_staged()


@st.cache_data
def _cached_slim_cache() -> dict[str, dict]:  # type: ignore[type-arg]
    return load_slim_cache()


try:
    pokedex = _cached_pokedex()
    evo_map = _cached_evo_map()
    slim_cache = _cached_slim_cache()
    st.success(f"データ読み込み済み（図鑑: {len(pokedex)}種 / キャッシュ: {len(slim_cache)}種）")
except Exception as e:
    st.error(f"データ読み込みエラー: {e}")
    st.stop()

# ============================================================
# テンプレートダウンロード
# ============================================================
if _TEMPLATE_FILE.exists():
    with open(_TEMPLATE_FILE, encoding="utf-8") as f:
        template_text = f.read()
    st.download_button(
        label="📥 テンプレートをダウンロード（iv_list_input_templete.txt）",
        data=template_text.encode("utf-8"),
        file_name="iv_list_input_templete.txt",
        mime="text/plain",
    )

# ============================================================
# ファイルアップロード
# ============================================================
with st.expander("iv_list_input.txt のフォーマット"):
    st.code(
        "# ポケモン名/リーグ(S,H,M)/TopN/対象指定(O,M,L)\n"
        "フシギダネ/S,H/200/L\n"
        "ピカチュウ/S/300/L\n"
        "リオル/S,H/1000/L",
        language="text",
    )

uploaded = st.file_uploader("iv_list_input.txt をアップロード", type=["txt"])

# ============================================================
# 出力オプション（確認用・最終確認用のON/OFF）
# ============================================================
col1, col2 = st.columns(2)
with col1:
    show_confirm = st.checkbox("確認用を出力する", value=False)
with col2:
    show_final_confirm = st.checkbox("最終確認用を出力する", value=False)

# ============================================================
# 処理実行
# ============================================================
if uploaded is not None:
    text = uploaded.read().decode("utf-8")
    requests, errors = parse_input(text, pokedex)

    if errors:
        st.error("入力エラーがあります：")
        for e in errors:
            st.write(f"- {e}")
        st.stop()

    if not requests:
        st.warning("有効な行がありません。")
        st.stop()

    st.info(f"{len(requests)}件を処理します。")

    # 進捗バーを作成してコールバックで更新する
    progress_bar = st.progress(0, text="処理中...")

    def _progress(current: int, total: int) -> None:
        progress_bar.progress(current / total, text=f"処理中... {current}/{total}")

    try:
        output_text, missing = generate_iv_strings(
            requests,
            pokedex,
            evo_map,
            slim_cache,
            show_confirm=show_confirm,
            show_final_confirm=show_final_confirm,
            progress_callback=_progress,
        )
    except NoValidUnitsError as exc:
        progress_bar.empty()
        if exc.missing_cache_names:
            st.warning(
                f"slim_cache.json に未収録のポケモンがありました"
                f"（{len(exc.missing_cache_names)}種）："
                f" {', '.join(sorted(exc.missing_cache_names))}"
            )
        st.error("出力対象がありません。")
        st.stop()
    except Exception as e:
        progress_bar.empty()
        st.error(f"処理中にエラーが発生しました: {e}")
        st.stop()

    progress_bar.empty()

    if missing:
        st.warning(
            f"slim_cache.json に未収録のポケモンがありました"
            f"（{len(missing)}種）： {', '.join(sorted(missing))}"
        )

    st.success("生成完了！")

    st.subheader("結果プレビュー")
    st.code(output_text, language="text")

    st.download_button(
        label="📥 iv_list_output.txt をダウンロード",
        data=output_text.encode("utf-8"),
        file_name="iv_list_output.txt",
        mime="text/plain",
    )
