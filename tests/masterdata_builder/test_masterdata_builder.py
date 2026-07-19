"""
tests/masterdata_builder/test_masterdata_builder.py

masterdata_builder（features 層）の単体テスト。
features の各公開関数はファイル I/O を持たない純粋関数のため、モック不要。
expand_targets は純粋関数なので get_search_targets・validate_search_row のテストでも実データで呼ぶ。
"""

from src.masterdata_builder.masterdata_builder import (
    MemberInput,
    SearchRow,
    build_combined_evo_map,
    collect_all_iv_lines,
    extract_evo_map_names,
    find_duplicates,
    format_evolution_line,
    format_iv_list_lines,
    format_pokedex_line,
    get_all_names,
    get_search_targets,
    is_solo,
    validate_search_row,
)

# ============================================================
# 共通テストデータ
# ============================================================

# 段構造の進化マップ（load_evolution_map_staged の返り値と同じ形式）
_EVO_MAP: list[list[list[str]]] = [
    [["フシギダネ"], ["フシギソウ"], ["フシギバナ"]],  # 3段・直線
    [["ヤドン"], ["ヤドラン", "ヤドキング"]],  # 2段・分岐
    [["ラルトス"], ["キルリア"], ["サーナイト", "エルレイド"]],  # 3段・最終段分岐
]


# ============================================================
# is_solo
# ============================================================


class TestIsSolo:
    def test_one_stage_is_solo(self) -> None:
        """段が1つのみなら単体（True）"""
        assert is_solo([["ガルーラ"]]) is True

    def test_two_stages_is_not_solo(self) -> None:
        """段が2つなら系統（False）"""
        assert is_solo([["コラッタ"], ["ラッタ"]]) is False

    def test_three_stages_is_not_solo(self) -> None:
        """段が3つなら系統（False）"""
        assert is_solo([["フシギダネ"], ["フシギソウ"], ["フシギバナ"]]) is False


# ============================================================
# get_all_names
# ============================================================


class TestGetAllNames:
    def test_solo(self) -> None:
        """単体：1段1メンバー → そのまま返す"""
        assert get_all_names([["ガルーラ"]]) == ["ガルーラ"]

    def test_linear_three_stages(self) -> None:
        """3段直線：出現順でフラットに返す"""
        stages = [["フシギダネ"], ["フシギソウ"], ["フシギバナ"]]
        assert get_all_names(stages) == ["フシギダネ", "フシギソウ", "フシギバナ"]

    def test_branched_last_stage(self) -> None:
        """最終段に分岐あり：分岐先をすべて含む"""
        stages = [["ラルトス"], ["キルリア"], ["サーナイト", "エルレイド"]]
        assert get_all_names(stages) == ["ラルトス", "キルリア", "サーナイト", "エルレイド"]

    def test_deduplicates_same_name(self) -> None:
        """重複する名前は初出のみ残す（実運用では起きないが、堅牢性の確認）"""
        stages = [["A"], ["A", "B"]]
        assert get_all_names(stages) == ["A", "B"]


# ============================================================
# extract_evo_map_names
# ============================================================


class TestExtractEvoMapNames:
    def test_returns_all_names_as_set(self) -> None:
        """全ファミリーの全メンバー名を set で返す"""
        result = extract_evo_map_names(_EVO_MAP)
        expected = {
            "フシギダネ",
            "フシギソウ",
            "フシギバナ",
            "ヤドン",
            "ヤドラン",
            "ヤドキング",
            "ラルトス",
            "キルリア",
            "サーナイト",
            "エルレイド",
        }
        assert result == expected

    def test_empty_map_returns_empty_set(self) -> None:
        """空の進化マップ → 空の set"""
        assert extract_evo_map_names([]) == set()


# ============================================================
# find_duplicates
# ============================================================


class TestFindDuplicates:
    def test_no_overlap_returns_empty(self) -> None:
        """重複なし → 空リスト"""
        assert find_duplicates(["A", "B"], {"C", "D"}) == []

    def test_partial_overlap_returns_duplicated_names(self) -> None:
        """一部重複 → 重複名のみ・入力順で返す"""
        result = find_duplicates(["A", "B", "C"], {"B", "D"})
        assert result == ["B"]

    def test_all_overlap_returns_all(self) -> None:
        """全件重複 → 全名前を入力順で返す"""
        result = find_duplicates(["A", "B"], {"A", "B", "C"})
        assert result == ["A", "B"]

    def test_empty_input_returns_empty(self) -> None:
        """入力が空 → 空リスト"""
        assert find_duplicates([], {"A", "B"}) == []

    def test_preserves_input_order(self) -> None:
        """重複名の順序は入力リストの順に従う"""
        result = find_duplicates(["C", "A", "B"], {"A", "C"})
        assert result == ["C", "A"]


# ============================================================
# format_pokedex_line
# ============================================================


class TestFormatPokedexLine:
    def test_tab_separated_columns(self) -> None:
        """タブ区切り・5列・順序が正しいことを確認"""
        member = MemberInput(name="フシギダネ", dex=1, hp=90, atk=118, defense=111)
        result = format_pokedex_line(member)
        assert result == "フシギダネ\t1\t90\t118\t111"

    def test_large_values(self) -> None:
        """図鑑番号・種族値が大きい値でも正しく整形される"""
        member = MemberInput(name="ハピナス", dex=242, hp=496, atk=129, defense=169)
        result = format_pokedex_line(member)
        assert result == "ハピナス\t242\t496\t129\t169"

    def test_no_spaces_between_columns(self) -> None:
        """区切りはタブのみで空白が入らない（TSV 仕様）"""
        member = MemberInput(name="テスト", dex=999, hp=100, atk=200, defense=300)
        parts = format_pokedex_line(member).split("\t")
        assert len(parts) == 5
        assert parts == ["テスト", "999", "100", "200", "300"]


# ============================================================
# format_evolution_line
# ============================================================


class TestFormatEvolutionLine:
    def test_two_stages_linear(self) -> None:
        """2段直線: カンマ1つで区切る"""
        stages = [["コラッタ"], ["ラッタ"]]
        assert format_evolution_line(stages) == "コラッタ,ラッタ"

    def test_three_stages_linear(self) -> None:
        """3段直線: カンマ2つで区切る"""
        stages = [["フシギダネ"], ["フシギソウ"], ["フシギバナ"]]
        assert format_evolution_line(stages) == "フシギダネ,フシギソウ,フシギバナ"

    def test_two_stages_branched_second(self) -> None:
        """2段・2段目が分岐: スラッシュで分岐先を区切る"""
        stages = [["ヤドン"], ["ヤドラン", "ヤドキング"]]
        assert format_evolution_line(stages) == "ヤドン,ヤドラン/ヤドキング"

    def test_three_stages_branched_last(self) -> None:
        """3段・最終段に分岐: 3.2 の入力構造をそのまま文字列化"""
        stages = [["ラルトス"], ["キルリア"], ["サーナイト", "エルレイド"]]
        assert format_evolution_line(stages) == "ラルトス,キルリア,サーナイト/エルレイド"

    def test_many_branches(self) -> None:
        """同一段に多数の分岐: スラッシュで全分岐先を連結"""
        stages = [
            ["イーブイ"],
            ["シャワーズ", "サンダース", "ブースター"],
        ]
        assert format_evolution_line(stages) == "イーブイ,シャワーズ/サンダース/ブースター"


# ============================================================
# format_iv_list_lines
# ============================================================


class TestFormatIvListLines:
    def test_single_league_single_target(self) -> None:
        """1リーグ・1対象 → そのまま1行"""
        result = format_iv_list_lines("フシギダネ", ["S"], 200, ["L"])
        assert result == "フシギダネ/S/200/L"

    def test_two_leagues_single_target(self) -> None:
        """2リーグ・1対象 → リーグをカンマ連結して1行"""
        result = format_iv_list_lines("フシギダネ", ["S", "H"], 200, ["L"])
        assert result == "フシギダネ/S,H/200/L"

    def test_single_league_two_targets(self) -> None:
        """1リーグ・2対象 → 対象指定をカンマ連結して1行"""
        result = format_iv_list_lines("ラルトス", ["S"], 1000, ["M", "L"])
        assert result == "ラルトス/S/1000/M,L"

    def test_two_leagues_two_targets(self) -> None:
        """2リーグ・2対象 → リーグと対象指定それぞれカンマ連結して1行"""
        result = format_iv_list_lines("ケムッソ", ["S", "H"], 500, ["M", "L"])
        assert result == "ケムッソ/S,H/500/M,L"

    def test_solo_o_fixed(self) -> None:
        """単体（O固定）: 1行"""
        result = format_iv_list_lines("ガルーラ", ["S"], 1000, ["O"])
        assert result == "ガルーラ/S/1000/O"


# ============================================================
# build_combined_evo_map
# ============================================================


class TestBuildCombinedEvoMap:
    def test_new_stages_appended(self) -> None:
        """新系統が既存マップの末尾に追加される"""
        existing = [
            [["フシギダネ"], ["フシギソウ"], ["フシギバナ"]],
        ]
        new_stages = [["コラッタ"], ["ラッタ"]]
        result = build_combined_evo_map(existing, new_stages)
        assert len(result) == 2
        assert result[0] == [["フシギダネ"], ["フシギソウ"], ["フシギバナ"]]
        assert result[1] == [["コラッタ"], ["ラッタ"]]

    def test_original_not_mutated(self) -> None:
        """元のリストを変更しない（新しいリストを返す）"""
        existing = [[["フシギダネ"], ["フシギソウ"], ["フシギバナ"]]]
        new_stages = [["コラッタ"], ["ラッタ"]]
        result = build_combined_evo_map(existing, new_stages)
        assert len(existing) == 1  # 元のリストは変わらない
        assert len(result) == 2

    def test_empty_existing_map(self) -> None:
        """既存マップが空でも動作する"""
        result = build_combined_evo_map([], [["ガルーラ"]])
        assert result == [[["ガルーラ"]]]


# ============================================================
# get_search_targets
# ============================================================


class TestGetSearchTargets:
    def test_O_returns_origin(self) -> None:
        """O 指定: 起点ポケモン本人のみを返す"""
        result = get_search_targets("フシギダネ", ["O"], _EVO_MAP)
        assert result == ["フシギダネ"]

    def test_L_two_stages_returns_both_branches(self) -> None:
        """L 指定・2段分岐: 最終段の全分岐先を返す"""
        result = get_search_targets("ヤドン", ["L"], _EVO_MAP)
        assert result == ["ヤドラン", "ヤドキング"]

    def test_L_three_stages_returns_last_stage(self) -> None:
        """L 指定・3段直線: 最終段のみ返す"""
        result = get_search_targets("フシギダネ", ["L"], _EVO_MAP)
        assert result == ["フシギバナ"]

    def test_M_three_stages_returns_middle(self) -> None:
        """M 指定・3段: 2番目の段（中間進化）を返す"""
        result = get_search_targets("ラルトス", ["M"], _EVO_MAP)
        assert result == ["キルリア"]

    def test_solo_not_in_evo_map_O_returns_self(self) -> None:
        """evo_map 未収録の単体ポケモン（O指定）: 本人のみ返す"""
        result = get_search_targets("ガルーラ", ["O"], _EVO_MAP)
        assert result == ["ガルーラ"]

    def test_new_family_via_combined_map(self) -> None:
        """build_combined_evo_map と組み合わせて新系統の展開が正しく動く"""
        new_stages = [["コラッタ"], ["ラッタ"]]
        combined = build_combined_evo_map(_EVO_MAP, new_stages)
        result = get_search_targets("コラッタ", ["L"], combined)
        assert result == ["ラッタ"]

    def test_L_three_stages_final_branched(self) -> None:
        """L 指定・3段・最終段に分岐: 分岐先すべてを返す"""
        result = get_search_targets("ラルトス", ["L"], _EVO_MAP)
        assert result == ["サーナイト", "エルレイド"]


# ============================================================
# 段位置・展開テスト用の共通段構造
# ============================================================

_STAGES_3 = [["フシギダネ"], ["フシギソウ"], ["フシギバナ"]]
_STAGES_2 = [["ヤドン"], ["ヤドラン", "ヤドキング"]]
_STAGES_3_BRANCH = [["ラルトス"], ["キルリア"], ["サーナイト", "エルレイド"]]
_STAGES_SOLO = [["ガルーラ"]]


# ============================================================
# validate_search_row
# ============================================================


class TestValidateSearchRow:
    def test_O_always_valid_for_last_stage(self) -> None:
        """最終進化に O → 常に有効"""
        result = validate_search_row(0, "フシギバナ", ["O"], _STAGES_3, _EVO_MAP)
        assert result is None

    def test_O_always_valid_for_solo(self) -> None:
        """単体に O → 常に有効"""
        result = validate_search_row(0, "ガルーラ", ["O"], _STAGES_SOLO, _EVO_MAP)
        assert result is None

    def test_L_invalid_for_last_stage(self) -> None:
        """最終進化に L → 展開先がないため無効"""
        result = validate_search_row(0, "フシギバナ", ["L"], _STAGES_3, _EVO_MAP)
        assert result is not None
        assert "フシギバナ" in result

    def test_M_invalid_for_last_stage(self) -> None:
        """最終進化に M → 展開先がないため無効"""
        result = validate_search_row(0, "フシギバナ", ["M"], _STAGES_3, _EVO_MAP)
        assert result is not None

    def test_L_valid_for_first_stage(self) -> None:
        """進化前に L → 最終段が存在するため有効"""
        result = validate_search_row(0, "フシギダネ", ["L"], _STAGES_3, _EVO_MAP)
        assert result is None

    def test_M_valid_for_first_stage_three_stages(self) -> None:
        """進化前に M（3段）→ 中間段が存在するため有効"""
        result = validate_search_row(0, "フシギダネ", ["M"], _STAGES_3, _EVO_MAP)
        assert result is None

    def test_M_valid_for_first_stage_two_stages(self) -> None:
        """進化前に M（2段）→ M=L として最終段を返すため有効"""
        result = validate_search_row(0, "ヤドン", ["M"], _STAGES_2, _EVO_MAP)
        assert result is None

    def test_L_valid_for_middle_stage(self) -> None:
        """中間進化に L → 最終段が forward_members に含まれるため有効"""
        result = validate_search_row(0, "キルリア", ["L"], _STAGES_3_BRANCH, _EVO_MAP)
        assert result is None

    def test_M_invalid_for_middle_stage(self) -> None:
        """中間進化に M → expand_targets が中間段本人を返し forward_members に含まれないため無効"""
        result = validate_search_row(0, "キルリア", ["M"], _STAGES_3_BRANCH, _EVO_MAP)
        assert result is not None

    def test_ML_invalid_for_solo_not_in_evo_map(self) -> None:
        """単体（evo_map 未収録）に M・L → 進化系統外のため無効"""
        result = validate_search_row(0, "ガルーラ", ["M", "L"], _STAGES_SOLO, _EVO_MAP)
        assert result is not None
        assert "ガルーラ" in result

    def test_error_message_includes_row_number(self) -> None:
        """エラーメッセージに row_idx + 1 の行番号が含まれる"""
        result = validate_search_row(2, "フシギバナ", ["L"], _STAGES_3, _EVO_MAP)
        assert result is not None
        assert "3" in result  # row_idx=2 → 3行目

    def test_O_and_invalid_L_returns_error(self) -> None:
        """O は有効でも L が無効なら → エラーを返す（L の分だけ弾く）"""
        result = validate_search_row(0, "フシギバナ", ["O", "L"], _STAGES_3, _EVO_MAP)
        assert result is not None

    def test_new_family_via_combined_map_valid(self) -> None:
        """build_combined_evo_map で合成した新系統の起点に L → 有効"""
        new_stages = [["コラッタ"], ["ラッタ"]]
        combined = build_combined_evo_map(_EVO_MAP, new_stages)
        result = validate_search_row(0, "コラッタ", ["L"], new_stages, combined)
        assert result is None

    def test_new_family_via_combined_map_last_stage_invalid(self) -> None:
        """build_combined_evo_map で合成した新系統の最終段に L → 無効"""
        new_stages = [["コラッタ"], ["ラッタ"]]
        combined = build_combined_evo_map(_EVO_MAP, new_stages)
        result = validate_search_row(0, "ラッタ", ["L"], new_stages, combined)
        assert result is not None


# ============================================================
# collect_all_iv_lines
# ============================================================


class TestCollectAllIvLines:
    def test_single_row(self) -> None:
        """1行の SearchRow → 出力も1行"""
        rows = [SearchRow("フシギダネ", ["S"], 200, ["L"])]
        result = collect_all_iv_lines(rows)
        assert result == ["フシギダネ/S/200/L"]

    def test_multiple_rows_mapped_one_to_one(self) -> None:
        """2行 → 出力も2行（行数1対1）"""
        rows = [
            SearchRow("フシギダネ", ["S"], 200, ["L"]),
            SearchRow("ガルーラ", ["H"], 1000, ["O"]),
        ]
        result = collect_all_iv_lines(rows)
        assert result == ["フシギダネ/S/200/L", "ガルーラ/H/1000/O"]

    def test_empty_list(self) -> None:
        """行リストが空 → 空リスト"""
        assert collect_all_iv_lines([]) == []

    def test_row_with_multiple_leagues_and_targets(self) -> None:
        """1行でリーグ2・対象2 → カンマ連結して出力も1行"""
        rows = [SearchRow("ラルトス", ["S", "H"], 500, ["M", "L"])]
        result = collect_all_iv_lines(rows)
        assert result == ["ラルトス/S,H/500/M,L"]

    def test_two_rows_with_combined_leagues(self) -> None:
        """2行、うち1行がリーグ2 → 出力も2行（分割されない）"""
        rows = [
            SearchRow("フシギダネ", ["S", "H"], 200, ["L"]),
            SearchRow("ガルーラ", ["S"], 1000, ["O"]),
        ]
        result = collect_all_iv_lines(rows)
        assert result == [
            "フシギダネ/S,H/200/L",
            "ガルーラ/S/1000/O",
        ]
