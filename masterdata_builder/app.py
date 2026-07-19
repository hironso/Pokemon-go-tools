"""
masterdata_builder/app.py

Streamlit エントリポイント（UI 層）。
ロジックは src/masterdata_builder/masterdata_builder.py（features）、
ファイル読み書きは src/esal/ に委譲する薄い UI 層。

起動:
    cd C:\\GitHub\\Pokemon-go-tools
    streamlit run masterdata_builder/app.py
"""

import sys
from pathlib import Path
from typing import Any

import streamlit as st

# streamlit run はこの app.py があるフォルダ（masterdata_builder/）を起点に import を探すため、
# 1つ上のプロジェクトルートを import 経路に加える。
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.esal.iv_strings_reader import load_evolution_map_staged  # noqa: E402
from src.esal.masterdata_writer import (  # noqa: E402
    append_evolution_line,
    append_iv_list_lines,
    append_pokedex_lines,
)
from src.esal.pokedex_reader import load_pokedex  # noqa: E402
from src.masterdata_builder.masterdata_builder import (  # noqa: E402
    MemberInput,
    SearchRow,
    build_combined_evo_map,
    collect_all_iv_lines,
    extract_evo_map_names,
    find_duplicates,
    format_evolution_line,
    format_pokedex_line,
    get_all_names,
    get_search_targets,
    is_solo,
    validate_search_row,
)

# ============================================================
# ページ設定
# ============================================================
st.set_page_config(page_title="マスターデータ登録ツール", layout="wide")
st.title("マスターデータ登録ツール")
st.caption(
    "master_data/ の各ファイル（pokedex_numbers.txt・evolution_map.txt・iv_list_input.txt）"
    "へ新規ポケモンを追記します。"
)

# ============================================================
# session_state の初期化
# ============================================================
if "screen" not in st.session_state:
    st.session_state["screen"] = "input"
if "member_count" not in st.session_state:
    st.session_state["member_count"] = 1
if "stage_count" not in st.session_state:
    st.session_state["stage_count"] = 1
if "search_count" not in st.session_state:
    st.session_state["search_count"] = 1


# ============================================================
# ヘルパー：フォームデータ収集
# ============================================================


def _collect_members() -> list[MemberInput]:
    """現在のフォーム入力からメンバーリストを組み立てる。"""
    members: list[MemberInput] = []
    for i in range(st.session_state["member_count"]):
        members.append(
            MemberInput(
                name=str(st.session_state.get(f"member_name_{i}", "")).strip(),
                dex=int(st.session_state.get(f"member_dex_{i}", 0)),
                hp=int(st.session_state.get(f"member_hp_{i}", 0)),
                atk=int(st.session_state.get(f"member_atk_{i}", 0)),
                defense=int(st.session_state.get(f"member_def_{i}", 0)),
            )
        )
    return members


def _collect_stages() -> list[list[str]]:
    """現在のフォーム入力から段構造を組み立てる（空選択の段はスキップ）。"""
    stages: list[list[str]] = []
    for i in range(st.session_state["stage_count"]):
        selected: list[str] = list(st.session_state.get(f"stage_{i}_members", []))
        if selected:
            stages.append(selected)
    return stages


def _collect_search_rows() -> list[SearchRow]:
    """現在のフォーム入力から検索設定の行リストを組み立てる。"""
    rows: list[SearchRow] = []
    for i in range(st.session_state["search_count"]):
        target_name = str(st.session_state.get(f"search_{i}_target") or "").strip()
        leagues = list(st.session_state.get(f"search_{i}_leagues", []))
        topn = int(st.session_state.get(f"search_{i}_topn", 1000))
        targets = list(st.session_state.get(f"search_{i}_targets", []))
        rows.append(SearchRow(target_name=target_name, leagues=leagues, topn=topn, targets=targets))
    return rows


def _get_member_names() -> list[str]:
    """現在入力済みのメンバー名リストを返す（空欄は除外）。段・検索設定の選択肢に使う。"""
    names: list[str] = []
    for i in range(st.session_state["member_count"]):
        name = str(st.session_state.get(f"member_name_{i}", "")).strip()
        if name:
            names.append(name)
    return names


def _get_stage_label(i: int, total: int) -> str:
    """段番号と総段数から段ラベルを返す。最初=進化前、最後=最終進化、間=中間進化。"""
    if i == 0:
        return "進化前"
    elif i == total - 1:
        return "最終進化"
    else:
        return "中間進化"


def _reset_form() -> None:
    """フォームの入力状態をリセットする（「続けて追加する」ボタン用）。"""
    member_count = st.session_state.get("member_count", 1)
    stage_count = st.session_state.get("stage_count", 1)
    search_count = st.session_state.get("search_count", 1)

    for i in range(member_count):
        for key in [
            f"member_name_{i}",
            f"member_dex_{i}",
            f"member_hp_{i}",
            f"member_atk_{i}",
            f"member_def_{i}",
        ]:
            st.session_state.pop(key, None)

    for i in range(stage_count):
        st.session_state.pop(f"stage_{i}_members", None)

    for i in range(search_count):
        for key in [
            f"search_{i}_target",
            f"search_{i}_leagues",
            f"search_{i}_topn",
            f"search_{i}_targets",
        ]:
            st.session_state.pop(key, None)

    st.session_state.pop("pending", None)
    st.session_state["member_count"] = 1
    st.session_state["stage_count"] = 1
    st.session_state["search_count"] = 1


# ============================================================
# 入力画面
# ============================================================


def _show_input_screen() -> None:
    # ---- 1. メンバー登録 ----
    st.subheader("1. メンバー登録")
    st.caption(
        "系統の全メンバー（起点・進化先・分岐先すべて）を入力してください。"
        "単体（進化なし）の場合は1匹だけ登録します。"
    )

    # 表示順: 名前・図鑑番号・攻撃・防御・HP（書き込み順は名前・図鑑番号・HP・攻撃・防御）
    for i in range(st.session_state["member_count"]):
        col_name, col_dex, col_atk, col_def, col_hp = st.columns([3, 1, 1, 1, 1])
        with col_name:
            st.text_input(
                f"名前 #{i + 1}",
                key=f"member_name_{i}",
                placeholder="例：フシギダネ",
            )
        with col_dex:
            st.number_input(f"図鑑番号 #{i + 1}", min_value=0, step=1, key=f"member_dex_{i}")
        with col_atk:
            st.number_input(f"攻撃 #{i + 1}", min_value=0, step=1, key=f"member_atk_{i}")
        with col_def:
            st.number_input(f"防御 #{i + 1}", min_value=0, step=1, key=f"member_def_{i}")
        with col_hp:
            st.number_input(f"HP #{i + 1}", min_value=0, step=1, key=f"member_hp_{i}")

    col_add, col_remove = st.columns([1, 1])
    with col_add:
        if st.button("＋ メンバーを追加"):
            st.session_state["member_count"] += 1
            st.rerun()
    with col_remove:
        if st.session_state["member_count"] > 1:
            if st.button("－ 最後のメンバーを削除"):
                st.session_state["member_count"] -= 1
                st.rerun()

    # ---- 2. 進化先設定 ----
    st.subheader("2. 進化先設定")
    st.caption(
        "段ごとにメンバーを選択してください。"
        "同一段に複数を選ぶと分岐（/）になります。"
        "段が1つのみなら「単体（進化なし）」と判定します。"
    )

    member_name_options = _get_member_names()
    total_stages = st.session_state["stage_count"]

    for i in range(total_stages):
        label = _get_stage_label(i, total_stages)
        st.multiselect(
            label,
            options=member_name_options,
            key=f"stage_{i}_members",
            help=f"{label}に属するポケモンを選んでください。複数選択で分岐になります。",
        )

    col_stage_add, col_stage_remove = st.columns([1, 1])
    with col_stage_add:
        if st.button("＋ 段を追加"):
            st.session_state["stage_count"] += 1
            st.rerun()
    with col_stage_remove:
        if st.session_state["stage_count"] > 1:
            if st.button("－ 最後の段を削除"):
                st.session_state["stage_count"] -= 1
                st.rerun()

    # ---- 3. 検索設定 ----
    st.subheader("3. 検索設定")
    st.caption(
        "対象ポケモン・リーグ・TopN・対象指定を行ごとに指定してください。"
        "複数のポケモンや異なる TopN を設定したい場合は行を追加します。"
    )

    # 対象ポケモンの選択肢（名前が未入力の場合はプレースホルダーを出す）
    target_options = member_name_options if member_name_options else ["（先にメンバーを登録してください）"]

    for i in range(st.session_state["search_count"]):
        col_target, col_leagues, col_topn, col_targets = st.columns([3, 2, 1, 3])
        with col_target:
            st.selectbox(
                f"対象ポケモン #{i + 1}",
                options=target_options,
                key=f"search_{i}_target",
            )
        with col_leagues:
            st.multiselect(
                f"リーグ #{i + 1}",
                options=["S", "H"],
                key=f"search_{i}_leagues",
                help="S = スーパーリーグ（CP1500）、H = ハイパーリーグ（CP2500）",
            )
        with col_topn:
            st.number_input(
                f"TopN #{i + 1}",
                min_value=1,
                max_value=4096,
                value=1000,
                step=1,
                key=f"search_{i}_topn",
            )
        with col_targets:
            st.multiselect(
                "対象指定（O/M/L）",
                options=["O", "M", "L"],
                key=f"search_{i}_targets",
                help="O=自身、M=中間進化、L=最終進化（展開ルールは library.md 参照）",
            )

    col_search_add, col_search_remove = st.columns([1, 1])
    with col_search_add:
        if st.button("＋ 行を追加"):
            st.session_state["search_count"] += 1
            st.rerun()
    with col_search_remove:
        if st.session_state["search_count"] > 1:
            if st.button("－ 最後の行を削除"):
                st.session_state["search_count"] -= 1
                st.rerun()

    # ---- 生成ボタン ----
    st.divider()
    if st.button("生成", type="primary"):
        _on_generate()


def _on_generate() -> None:
    """「生成」ボタン押下時の処理：バリデーション → 重複チェック → 確認画面へ遷移。"""
    members = _collect_members()
    stages = _collect_stages()
    search_rows = _collect_search_rows()

    # ---- 基本バリデーション ----
    errors: list[str] = []

    if not stages:
        errors.append("進化構造の段を1つ以上設定してください（段を追加し、メンバーを選択）。")

    member_names_entered = [m.name for m in members if m.name]
    if not member_names_entered:
        errors.append("メンバーの名前を入力してください。")

    if stages:
        all_names_in_stages = get_all_names(stages)
        entered_set = set(member_names_entered)
        # 段に選ばれたが種族値が未登録（欄が空）のケースを検出する
        unregistered = [n for n in all_names_in_stages if n not in entered_set]
        if unregistered:
            errors.append(
                f"段に選択されたが種族値が未登録のメンバーがいます: {', '.join(unregistered)}"
            )
    else:
        all_names_in_stages = []

    solo = is_solo(stages) if stages else True

    # ---- 検索設定バリデーション ----
    if not search_rows:
        errors.append("検索設定を1行以上追加してください。")

    # 重複チェック前に esal を読み込む（バリデーション全部終えてから書き込むため）
    existing_evo_map: list[list[list[str]]] = []
    if not errors:
        try:
            existing_pokedex = load_pokedex()
            existing_evo_map = load_evolution_map_staged()
        except Exception as exc:
            st.error(f"既存データの読み込みエラー: {exc}")
            return

        existing_names = set(existing_pokedex.keys()) | extract_evo_map_names(existing_evo_map)
        duplicates = find_duplicates(all_names_in_stages, existing_names)
        if duplicates:
            st.error(
                f"以下のポケモンは既存データにすでに存在します。"
                f"追記を中止します: {', '.join(duplicates)}"
            )
            return

    # ---- 検索設定の詳細バリデーション（O/M/L の妥当性） ----
    # 新系統はまだファイルにないため、既存マップと合成して validate_search_row に渡す
    combined_evo_map = build_combined_evo_map(existing_evo_map, stages) if not solo else existing_evo_map

    for i, row in enumerate(search_rows):
        if not row.target_name or row.target_name == "（先にメンバーを登録してください）":
            errors.append(f"検索設定 {i + 1} 行目：対象ポケモンを選択してください。")
            continue
        if not row.leagues:
            errors.append(f"検索設定 {i + 1} 行目：リーグを1つ以上選択してください。")
        if not row.targets:
            errors.append(f"検索設定 {i + 1} 行目：対象指定（O/M/L）を1つ以上選択してください。")
            continue
        err = validate_search_row(i, row.target_name, row.targets, stages, combined_evo_map)
        if err:
            errors.append(err)

    if errors:
        for msg in errors:
            st.error(msg)
        return

    # ---- 確認画面へ遷移 ----
    # 確認画面で使うデータを session_state に保存する（入力ウィジェットが非表示になるため）
    st.session_state["pending"] = {
        "members": members,
        "stages": stages,
        "search_rows": search_rows,
        "solo": solo,
        "evo_map": existing_evo_map,
    }
    st.session_state["screen"] = "confirm"
    st.rerun()


# ============================================================
# 確認画面
# ============================================================


def _show_confirm_screen() -> None:
    pending: dict[str, Any] = st.session_state.get("pending", {})
    members: list[MemberInput] = pending.get("members", [])
    stages: list[list[str]] = pending.get("stages", [])
    search_rows: list[SearchRow] = pending.get("search_rows", [])
    solo: bool = pending.get("solo", True)
    evo_map: list[list[list[str]]] = pending.get("evo_map", [])

    st.subheader("確認画面")
    st.caption("内容を確認して「OK（追記実行）」を押してください。")

    # ---- 進化構造の表示 ----
    st.markdown("**進化構造**")
    stage_strs = [" / ".join(stage) for stage in stages]
    st.write(" → ".join(stage_strs))
    if solo:
        st.write("（単体：進化なし）")

    # ---- メンバー一覧テーブル ----
    st.markdown("**メンバー一覧（種族値）**")
    all_names = get_all_names(stages)
    member_map = {m.name: m for m in members}
    table_data = [
        {
            "名前": member_map[n].name,
            "図鑑番号": member_map[n].dex,
            "攻撃": member_map[n].atk,
            "防御": member_map[n].defense,
            "HP": member_map[n].hp,
        }
        for n in all_names
        if n in member_map
    ]
    st.table(table_data)

    # ---- 検索設定（行ごとの対象展開を含む） ----
    st.markdown("**検索設定**")
    # 新系統はまだ evolution_map.txt に書かれていないため、既存マップと合成して渡す
    combined_map = build_combined_evo_map(evo_map, stages) if not solo else evo_map
    search_table = []
    for i, row in enumerate(search_rows):
        expanded = get_search_targets(row.target_name, row.targets, combined_map)
        search_table.append(
            {
                "行": i + 1,
                "対象ポケモン": row.target_name,
                "リーグ": " / ".join(row.leagues),
                "TopN": row.topn,
                "対象指定": " / ".join(row.targets),
                "実際の検索対象": ", ".join(expanded) if expanded else "（なし）",
            }
        )
    st.table(search_table)

    # ---- 追記プレビュー（折りたたみ） ----
    with st.expander("追記される内容（プレビュー）"):
        pokedex_lines = [format_pokedex_line(member_map[n]) for n in all_names if n in member_map]
        st.markdown("**pokedex_numbers.txt**")
        st.code("\n".join(pokedex_lines), language="text")

        if not solo:
            evo_line = format_evolution_line(stages)
            st.markdown("**evolution_map.txt**")
            st.code(evo_line, language="text")

        iv_lines = collect_all_iv_lines(search_rows)
        st.markdown("**iv_list_input.txt**")
        st.code("\n".join(iv_lines), language="text")

    # ---- OK / 修正ボタン ----
    st.divider()
    col_ok, col_back = st.columns([1, 1])
    with col_ok:
        if st.button("OK（追記実行）", type="primary"):
            _on_ok(pending)
    with col_back:
        if st.button("修正（入力画面へ戻る）"):
            # 前回の入力は session_state のウィジェットキーに残っているため、
            # 入力画面に戻ると自動的に復元される
            st.session_state["screen"] = "input"
            st.rerun()


def _on_ok(pending: dict[str, Any]) -> None:
    """「OK（追記実行）」ボタン押下時：各ファイルへ追記する。"""
    members: list[MemberInput] = pending["members"]
    stages: list[list[str]] = pending["stages"]
    search_rows: list[SearchRow] = pending["search_rows"]
    solo: bool = pending["solo"]

    all_names = get_all_names(stages)
    member_map = {m.name: m for m in members}

    try:
        # pokedex_numbers.txt に全メンバーを追記（書き込み順: 名前・図鑑番号・HP・攻撃・防御）
        pokedex_lines = [format_pokedex_line(member_map[n]) for n in all_names if n in member_map]
        append_pokedex_lines(pokedex_lines)

        # evolution_map.txt に系統行を追記（単体は書かない）
        if not solo:
            append_evolution_line(format_evolution_line(stages))

        # iv_list_input.txt に全検索設定行を追記
        iv_lines = collect_all_iv_lines(search_rows)
        append_iv_list_lines(iv_lines)

    except Exception as exc:
        st.error(f"ファイル書き込みエラー: {exc}")
        return

    st.session_state["screen"] = "done"
    st.rerun()


# ============================================================
# 完了画面
# ============================================================


def _show_done_screen() -> None:
    st.success("追記が完了しました。")

    pending: dict[str, Any] = st.session_state.get("pending", {})
    stages: list[list[str]] = pending.get("stages", [])
    solo: bool = pending.get("solo", True)
    all_names = get_all_names(stages) if stages else []

    st.markdown(f"追記したポケモン: **{', '.join(all_names)}**")
    if solo:
        st.markdown("追記先: `pokedex_numbers.txt`・`iv_list_input.txt`")
    else:
        st.markdown("追記先: `pokedex_numbers.txt`・`evolution_map.txt`・`iv_list_input.txt`")
    st.info(
        "slim_cache.json の更新は別工程です。"
        "slim_cache_builder.py を実行して slim_cache.json を再生成してください。"
    )

    if st.button("続けてポケモンを追加する"):
        _reset_form()
        st.session_state["screen"] = "input"
        st.rerun()


# ============================================================
# 画面ルーティング
# ============================================================
_screen = st.session_state["screen"]
if _screen == "input":
    _show_input_screen()
elif _screen == "confirm":
    _show_confirm_screen()
elif _screen == "done":
    _show_done_screen()
