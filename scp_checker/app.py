# -*- coding: utf-8 -*-
"""
scp_checker/app.py

SCPランクチェッカー - Streamlit エントリポイント（薄い UI 層）。
ロジックは src/scp_checker/scp_checker.py（features 層）に委譲する。
ファイル読み込みは src/esal/ に委譲する。
例外の捕捉と画面表示はこの層に集約する。
"""

import sys
from pathlib import Path

import streamlit as st

# streamlit run はこの app.py があるフォルダ（scp_checker/）を起点に import を探すため、
# 1つ上のプロジェクトルート（src/ がある場所）を import 経路に加える。
# Path(__file__) 基準で解決するので、どこから起動しても・Streamlit Cloud でも動く。
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.esal.pokedex_reader import load_pokedex_full  # noqa: E402
from src.esal.scp_checker_reader import load_rank_checker_template  # noqa: E402
from src.scp_checker.scp_checker import (  # noqa: E402
    apply_bulk_replace,
    assign_recommend_tags,
    base_name,
    calculate_results,
    format_output,
    is_shadow,
    parse_rank_input,
)

# ============================================================
# ページ設定
# ============================================================
st.set_page_config(
    page_title="SCPランクチェッカー",
    page_icon="🎮",
    layout="wide",  # 画面幅いっぱいに表示（仕様書 9-1 章）
)
st.title("🎮 SCPランクチェッカー")

# ============================================================
# 起動時データ読み込み（@st.cache_data でセッション内キャッシュ）
# エラーが出た時点で画面にエラーを表示し、以降の処理を停止する
# ============================================================


@st.cache_data
def _cached_load_pokedex() -> dict:
    return load_pokedex_full()


@st.cache_data
def _cached_load_template() -> bytes:
    return load_rank_checker_template()


try:
    _pokedex = _cached_load_pokedex()
except FileNotFoundError as e:
    # load_pokedex_full は open() を直接呼ぶため、e.filename にパスが入る
    path = e.filename if e.filename else str(e)
    st.error(f"pokedex_numbers.txt が見つかりません: {path}")
    st.stop()

try:
    _template_bytes = _cached_load_template()
except FileNotFoundError as e:
    # load_rank_checker_template は仕様書文言のメッセージを raise する
    st.error(str(e))
    st.stop()

st.success(f"図鑑データ読み込み済み（{len(_pokedex)}種）")

# ============================================================
# Session state 初期化
# ============================================================
if "form_requests" not in st.session_state:
    st.session_state.form_requests = []
if "form_name" not in st.session_state:
    st.session_state.form_name = ""
if "form_league" not in st.session_state:
    st.session_state.form_league = "S"
if "form_shadow" not in st.session_state:
    st.session_state.form_shadow = False

requests: list[tuple] = []

# ============================================================
# 入力方法の選択
# ============================================================
input_mode = st.radio(
    "入力方法を選択",
    ["フォームで入力", "ファイルをアップロード"],
    horizontal=True,
)

# ============================================================
# フォーム入力モード
# ============================================================
if input_mode == "フォームで入力":

    # ポケモン名・リーグ一括置換パネル
    # Rev1.1 変更点：「入力方法を選択」の直後・ポケモン名入力欄の直前に配置
    # 表示条件：リストの件数に関わらず常に表示（旧実装では 1 件以上のときのみ）
    with st.expander("ポケモン名・リーグを一括置換"):
        _LEAGUE_OPTIONS = ["変更なし", "S", "H", "M"]
        col1, col2 = st.columns(2)
        with col1:
            st.caption("置換前")
            replace_name_from = st.text_input(
                "ポケモン名（空欄=全対象）",
                placeholder="例：リザードン",
                key="replace_name_from",
            )
            replace_league_from = st.selectbox(
                "リーグ", _LEAGUE_OPTIONS, key="replace_league_from"
            )
        with col2:
            st.caption("置換後")
            replace_name_to = st.text_input(
                "ポケモン名（空欄=変更なし）",
                placeholder="例：リザードン",
                key="replace_name_to",
            )
            replace_league_to = st.selectbox(
                "リーグ", _LEAGUE_OPTIONS, key="replace_league_to"
            )

        if st.button("置換実行"):
            name_from = replace_name_from.strip()
            name_to = replace_name_to.strip()
            new_list, success_msg, err_msg = apply_bulk_replace(
                st.session_state.form_requests,
                name_from,
                replace_league_from,
                name_to,
                replace_league_to,
                _pokedex,
            )
            if err_msg:
                if err_msg == "条件に一致する行がリストに存在しません。":
                    st.warning(err_msg)
                else:
                    st.error(err_msg)
            else:
                st.session_state.form_requests = new_list
                st.success(success_msg)
                st.rerun()

    # ポケモン名・リーグ・シャドウ（フォーム外に置き、送信後も値を保持）
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        name_input = st.text_input(
            "ポケモン名",
            value=st.session_state.form_name,
            placeholder="例：カメックス",
            key="name_input_field",
        )
    with col2:
        league_input = st.selectbox(
            "リーグ",
            ["S", "H", "M"],
            index=["S", "H", "M"].index(st.session_state.form_league),
            key="league_input_field",
        )
    with col3:
        st.write("")
        shadow_input = st.checkbox(
            "シャドウ",
            value=st.session_state.form_shadow,
            key="shadow_input_field",
        )

    st.session_state.form_name = name_input
    st.session_state.form_league = league_input
    st.session_state.form_shadow = shadow_input

    # IV 入力フォーム
    # Rev1.1 変更点：text_input から number_input に変更。初期値は未入力（value=None）。
    # clear_on_submit=True により、追加後に IV 欄は未入力状態に戻る。
    with st.form("iv_form", clear_on_submit=True):
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
        with col1:
            iv_a = st.number_input(
                "攻撃IV", min_value=0, max_value=15, value=None, step=1, placeholder="0〜15"
            )
        with col2:
            iv_d = st.number_input(
                "防御IV", min_value=0, max_value=15, value=None, step=1, placeholder="0〜15"
            )
        with col3:
            iv_h = st.number_input(
                "HP IV", min_value=0, max_value=15, value=None, step=1, placeholder="0〜15"
            )
        with col4:
            st.write("")
            st.write("")
            submitted = st.form_submit_button("追加")

        if submitted:
            name = st.session_state.form_name.strip()

            if not name:
                st.error("ポケモン名を入力してください。")
            elif iv_a is None or iv_d is None or iv_h is None:
                # Rev1.1 変更点：未入力 IV がある場合はエラー（旧実装では 0 として扱っていた）
                st.error("未入力のIVがあります")
            else:
                # シャドウ判定：チェックボックスまたはポケモン名先頭 S
                cb_shadow = st.session_state.form_shadow
                name_is_shadow = is_shadow(name, _pokedex)
                if cb_shadow or name_is_shadow:
                    display_name = name if name_is_shadow else "S" + name
                    shadow_flag = True
                else:
                    display_name = name
                    shadow_flag = False

                # pokedex バリデーション（S 除き名で検索）
                # エラーメッセージにはシャドウ補完前の入力値をそのまま表示する（仕様書 2 章）
                lookup = base_name(display_name, _pokedex)
                if lookup not in _pokedex:
                    st.error(f"「{name}」はpokedex_numbers.txtに存在しません。")
                else:
                    st.session_state.form_requests.append(
                        (display_name, league_input, int(iv_a), int(iv_d), int(iv_h), shadow_flag)
                    )

    # 追加済みリスト（1 件以上のときのみ見出しと一覧を表示）
    if st.session_state.form_requests:
        st.subheader(f"追加済みリスト（{len(st.session_state.form_requests)}件）")
        for i, (n, lg, a, d, h, sw) in enumerate(st.session_state.form_requests):
            col1, col2 = st.columns([6, 1])
            with col1:
                st.text(f"{n}/{lg}/{a}/{d}/{h}")
            with col2:
                if st.button("✕", key=f"del_{i}"):
                    st.session_state.form_requests.pop(i)
                    st.rerun()

    # クリア・計算実行ボタン（件数に関わらず常に表示）
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🗑️ リストをクリア"):
            st.session_state.form_requests = []
            st.rerun()
    with col2:
        if st.button("✅ 計算実行", type="primary"):
            if not st.session_state.form_requests:
                # Rev1.1 変更点：0 件のまま計算実行した場合は警告を表示する
                st.warning("有効な行がありません。")
            else:
                requests = list(st.session_state.form_requests)

# ============================================================
# ファイルアップロードモード
# ============================================================
else:
    uploaded = st.file_uploader("rank_cheker_input.txt をアップロード", type=["txt"])
    with st.expander("rank_cheker_input.txt のフォーマット"):
        st.code(
            "# ポケモン名/リーグ(S/H/M)/攻撃IV/防御IV/HPIV\n"
            "# リーグ: S=スーパー(1500) H=ハイパー(2500) M=マスター\n"
            "# IV範囲: 0〜15\n"
            "# シャドウはポケモン名の先頭にSをつける\n"
            "プクリン/S/1/12/6\n"
            "プクリン/S/2/14/6\n"
            "Sプクリン/S/1/13/6\n"
            "ラッキー/H/15/15/15",
            language="text",
        )
    st.download_button(
        label="📥 テンプレートをダウンロード（rank_cheker_input_templete.txt）",
        data=_template_bytes,
        file_name="rank_cheker_input_templete.txt",
        mime="text/plain",
    )

    if uploaded is not None:
        text = uploaded.read().decode("utf-8")
        parsed, errors = parse_rank_input(text, _pokedex)
        if errors:
            st.error("入力エラーがあります：")
            for e in errors:
                st.write(f"- {e}")
            st.stop()
        if not parsed:
            st.warning("有効な行がありません。")
            st.stop()
        requests = parsed

# ============================================================
# 計算処理（共通）
# ============================================================
if requests:
    st.info(f"{len(requests)}件を計算します。しばらくお待ちください...")
    _progress_bar = st.progress(0)

    try:
        rows = calculate_results(
            requests,
            _pokedex,
            on_progress=lambda curr, total: _progress_bar.progress(curr / total),
        )
    except ValueError as e:
        st.error(str(e))
        st.stop()

    tag_map = assign_recommend_tags(rows, _pokedex)
    output_text = format_output(rows, tag_map)

    st.success("計算完了！")
    st.subheader("結果")
    st.code(output_text, language="text")

    st.download_button(
        label="📥 output.txt をダウンロード",
        data=output_text.encode("utf-8"),
        file_name="output.txt",
        mime="text/plain",
    )
