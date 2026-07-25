"""
tests/scp_checker/test_scp_checker.py

src/scp_checker/scp_checker.py（features 層）の単体テスト。
esal（ファイル読み込み）の呼び出しは calculate_results・assign_recommend_tags の
内部で pokedex を引数として受け取る設計のため、モック不要。
assign_recommend_tags 内部の _get_top1_scp_continuous は全 4096 IV を評価する
重い計算であるため、タグ判定テストでは patch して制御する。
"""

from __future__ import annotations

import math
from unittest.mock import patch

import pytest

from src.scp_checker.scp_checker import (
    apply_bulk_replace,
    assign_recommend_tags,
    base_name,
    calculate_results,
    format_output,
    is_shadow,
    parse_rank_input,
)

# ============================================================
# 共通テストデータ
# ============================================================

# シンプルな種族値（端数が出にくい値）
_POKEDEX: dict[str, dict] = {
    "カメックス": {"dex": 9, "hp_base": 188, "atk_base": 171, "def_base": 207},
    "プクリン": {"dex": 39, "hp_base": 207, "atk_base": 80, "def_base": 73},
    "ラッキー": {"dex": 113, "hp_base": 496, "atk_base": 60, "def_base": 176},
}


# ============================================================
# is_shadow
# ============================================================


class TestIsShadow:
    def test_shadow_name_with_s_prefix_in_pokedex(self) -> None:
        assert is_shadow("Sカメックス", _POKEDEX) is True

    def test_normal_name_returns_false(self) -> None:
        assert is_shadow("カメックス", _POKEDEX) is False

    def test_s_prefix_but_not_in_pokedex_returns_false(self) -> None:
        """先頭 S だが S 除き名が pokedex に無い場合はシャドウではない。"""
        assert is_shadow("Sミュウ", _POKEDEX) is False

    def test_empty_string_returns_false(self) -> None:
        assert is_shadow("", _POKEDEX) is False


# ============================================================
# base_name
# ============================================================


class TestBaseName:
    def test_shadow_name_returns_base(self) -> None:
        assert base_name("Sカメックス", _POKEDEX) == "カメックス"

    def test_normal_name_returns_as_is(self) -> None:
        assert base_name("カメックス", _POKEDEX) == "カメックス"

    def test_s_prefix_not_in_pokedex_returns_as_is(self) -> None:
        """pokedex に存在しない S 付き名は通常名として扱い、そのまま返す。"""
        assert base_name("Sミュウ", _POKEDEX) == "Sミュウ"


# ============================================================
# parse_rank_input
# ============================================================


class TestParseRankInput:
    def test_valid_single_line(self) -> None:
        requests, errors = parse_rank_input("カメックス/S/0/14/10", _POKEDEX)
        assert errors == []
        assert len(requests) == 1
        name, league, iv_a, iv_d, iv_h, shadow = requests[0]
        assert name == "カメックス"
        assert league == "S"
        assert (iv_a, iv_d, iv_h) == (0, 14, 10)
        assert shadow is False

    def test_shadow_pokemon_detected(self) -> None:
        requests, errors = parse_rank_input("Sカメックス/S/0/14/10", _POKEDEX)
        assert errors == []
        _name, _league, _a, _d, _h, shadow = requests[0]
        assert shadow is True

    def test_comment_and_blank_lines_skipped(self) -> None:
        text = "# コメント\n\nカメックス/S/0/14/10\n"
        requests, errors = parse_rank_input(text, _POKEDEX)
        assert errors == []
        assert len(requests) == 1

    def test_multiple_valid_lines(self) -> None:
        text = "プクリン/S/1/12/6\nプクリン/S/2/14/6\nラッキー/H/15/15/15"
        requests, errors = parse_rank_input(text, _POKEDEX)
        assert errors == []
        assert len(requests) == 3

    def test_error_wrong_field_count(self) -> None:
        _requests, errors = parse_rank_input("カメックス/S/0/14", _POKEDEX)
        assert len(errors) == 1
        assert "形式不正" in errors[0]
        assert "1行目" in errors[0]

    def test_error_invalid_league(self) -> None:
        _requests, errors = parse_rank_input("カメックス/X/0/14/10", _POKEDEX)
        assert len(errors) == 1
        assert "不正なリーグ" in errors[0]
        assert "X" in errors[0]

    def test_error_iv_not_numeric(self) -> None:
        _requests, errors = parse_rank_input("カメックス/S/Z/14/10", _POKEDEX)
        assert len(errors) == 1
        assert "IVが数値ではありません" in errors[0]

    def test_error_iv_out_of_range(self) -> None:
        _requests, errors = parse_rank_input("カメックス/S/0/16/10", _POKEDEX)
        assert len(errors) == 1
        assert "IV範囲不正" in errors[0]

    def test_hex_fallback_lowercase_f(self) -> None:
        """IV に 'f' が含まれる場合、16 進数として 15 に解釈する。"""
        requests, errors = parse_rank_input("カメックス/S/0/f/10", _POKEDEX)
        assert errors == []
        _name, _league, _a, iv_d, _h, _sw = requests[0]
        assert iv_d == 15

    def test_empty_content_only_comments(self) -> None:
        """コメント・空行しかない場合は requests が空になる（有効行 0 件）。"""
        requests, errors = parse_rank_input("# コメントのみ\n\n", _POKEDEX)
        assert requests == []
        assert errors == []

    def test_multiple_errors_collected(self) -> None:
        """複数のエラー行があれば、すべてのエラーが収集される。"""
        text = "カメックス/X/0/14/10\nカメックス/S/0/99/10"
        _requests, errors = parse_rank_input(text, _POKEDEX)
        assert len(errors) == 2

    def test_valid_and_error_lines_mixed(self) -> None:
        """エラー行と正常行が混在する場合、正常行のみ requests に入る。"""
        text = "プクリン/S/1/12/6\nカメックス/X/0/14/10"
        requests, errors = parse_rank_input(text, _POKEDEX)
        assert len(requests) == 1
        assert len(errors) == 1

    def test_master_league_no_cap(self) -> None:
        """マスターリーグ（M）は CP 上限なし。パース上は正常に通ること。"""
        requests, errors = parse_rank_input("カメックス/M/15/15/15", _POKEDEX)
        assert errors == []
        _name, league, *_rest = requests[0]
        assert league == "M"


# ============================================================
# calculate_results
# ============================================================


class TestCalculateResults:
    def test_returns_correct_structure(self) -> None:
        """正常系：1 件計算して rows の構造が正しいことを確認する。"""
        reqs = [("プクリン", "S", 1, 12, 6, False)]
        rows = calculate_results(reqs, _POKEDEX)
        assert len(rows) == 1
        row = rows[0]
        # 必須キーが揃っていること
        for key in ("idx", "input", "league", "name", "shadow",
                    "level", "cp", "atk", "def", "hp", "scp", "scp_cont", "rank"):
            assert key in row, f"キー '{key}' が rows に存在しない"

    def test_rank_is_within_valid_range(self) -> None:
        """ランクは 1 以上 4096 以下の整数であること。"""
        reqs = [("プクリン", "S", 1, 12, 6, False)]
        rows = calculate_results(reqs, _POKEDEX)
        assert 1 <= rows[0]["rank"] <= 4096

    def test_scp_is_floor_of_scp_cont(self) -> None:
        """scp（floor 後）が scp_cont（連続値）の floor と一致すること。"""
        reqs = [("プクリン", "S", 1, 12, 6, False)]
        rows = calculate_results(reqs, _POKEDEX)
        row = rows[0]
        assert row["scp"] == math.floor(row["scp_cont"])

    def test_cp_within_league_cap(self) -> None:
        """スーパーリーグの CP が 1500 以下であること。"""
        reqs = [("プクリン", "S", 1, 12, 6, False)]
        rows = calculate_results(reqs, _POKEDEX)
        assert rows[0]["cp"] <= 1500

    def test_idx_assigned_sequentially(self) -> None:
        """idx は 0 から連番で割り当てられること。"""
        reqs = [("プクリン", "S", 0, 14, 13, False), ("プクリン", "S", 1, 12, 6, False)]
        rows = calculate_results(reqs, _POKEDEX)
        assert rows[0]["idx"] == 0
        assert rows[1]["idx"] == 1

    def test_progress_callback_called_correctly(self) -> None:
        """on_progress が件数分だけ呼ばれ、最終呼び出しが (total, total) であること。"""
        reqs = [("プクリン", "S", 1, 12, 6, False), ("プクリン", "S", 2, 14, 6, False)]
        calls: list[tuple[int, int]] = []
        calculate_results(reqs, _POKEDEX, on_progress=lambda c, t: calls.append((c, t)))
        assert len(calls) == 2
        assert calls[-1] == (2, 2)

    def test_raises_for_unknown_pokemon(self) -> None:
        """pokedex に存在しないポケモン名は ValueError を raise すること。"""
        reqs = [("ミュウ", "S", 0, 14, 10, False)]
        with pytest.raises(ValueError, match="ポケモンが見つかりません: ミュウ"):
            calculate_results(reqs, _POKEDEX)

    def test_raises_for_calculation_failure(self) -> None:
        """
        _get_rank_result が None を返す場合は ValueError を raise すること。
        実際に None が返るケースは稀なので内部関数をパッチして再現する。
        （best が non-None の場合は到達しないが、型上の None チェックが存在するため検証する）
        """
        reqs = [("プクリン", "S", 0, 14, 10, False)]
        with patch("src.scp_checker.scp_checker._get_rank_result", autospec=True, return_value=None):
            with pytest.raises(ValueError, match="計算失敗"):
                calculate_results(reqs, _POKEDEX)

    def test_raises_for_calculation_failure_when_best_is_none(self) -> None:
        """
        _best_within_cap が None を返す場合（有効レベルなし）は ValueError を raise すること。
        実際に None が返るケースは稀なので内部関数をパッチして再現する。
        """
        reqs = [("プクリン", "S", 0, 14, 10, False)]
        with patch("src.scp_checker.scp_checker._best_within_cap", autospec=True, return_value=None):
            with pytest.raises(ValueError, match="計算失敗"):
                calculate_results(reqs, _POKEDEX)

    def test_rank_uses_level50_population_for_non_rb(self) -> None:
        """最適レベルが 50 以下の個体は、_get_rank_result を max_level=50.0 で呼ぶこと（Rev1.2）。"""
        reqs = [("プクリン", "S", 1, 12, 6, False)]
        mock_best = {
            "level": 29.5, "cp": 1497, "atk": 100.0, "def": 50.0,
            "hp": 200, "scp": 1500, "scp_cont": 1500.3,
        }
        mock_result = {**mock_best, "rank": 42}
        with (
            patch("src.scp_checker.scp_checker._best_within_cap", autospec=True, return_value=mock_best),
            patch("src.scp_checker.scp_checker._get_rank_result", autospec=True, return_value=mock_result) as mock_grr,
        ):
            calculate_results(reqs, _POKEDEX)
        assert mock_grr.call_args.kwargs["max_level"] == 50.0

    def test_rank_uses_level51_population_for_rb(self) -> None:
        """最適レベルが 50 超の個体（[RB] 対象）は、_get_rank_result を max_level=51.0 で呼ぶこと（Rev1.2）。"""
        reqs = [("プクリン", "S", 1, 12, 6, False)]
        mock_best = {
            "level": 51.0, "cp": 1499, "atk": 105.0, "def": 52.0,
            "hp": 210, "scp": 1550, "scp_cont": 1550.8,
        }
        mock_result = {**mock_best, "rank": 5}
        with (
            patch("src.scp_checker.scp_checker._best_within_cap", autospec=True, return_value=mock_best),
            patch("src.scp_checker.scp_checker._get_rank_result", autospec=True, return_value=mock_result) as mock_grr,
        ):
            calculate_results(reqs, _POKEDEX)
        assert mock_grr.call_args.kwargs["max_level"] == 51.0


# ============================================================
# assign_recommend_tags
# ============================================================

# タグ判定テスト用のダミー行生成ヘルパー
def _make_row(idx: int, scp_cont: float, atk: float, rank: int, **kwargs) -> dict:
    """assign_recommend_tags に渡す rows エントリを生成する。"""
    return {
        "idx": idx,
        "name": "プクリン",
        "league": "S",
        "shadow": False,
        "scp_cont": scp_cont,
        "scp": math.floor(scp_cont),
        "atk": atk,
        "def": 50.0,
        "hp": 200,
        "cp": 1400,
        "level": 29.5,
        "rank": rank,
        "input": f"プクリン/1/12/6",
        **kwargs,
    }


class TestAssignRecommendTags:
    """
    タグ判定テスト。_get_top1_scp_continuous をパッチして計算コストを回避しつつ、
    判定ロジックを実 scp_cont 値で検証する。
    """

    def test_scp_max_tag_assigned_to_highest_scp_cont(self) -> None:
        """★SCP最大は連続値 SCP が最も高い個体に付くこと。"""
        rows = [
            _make_row(0, scp_cont=1200.0, atk=100.0, rank=5),
            _make_row(1, scp_cont=1210.0, atk=95.0, rank=1),
        ]
        with patch(
            "src.scp_checker.scp_checker._get_top1_scp_continuous", autospec=True, return_value=1250.0
        ):
            tag_map = assign_recommend_tags(rows, _POKEDEX)
        assert "★SCP最大" in tag_map[1]
        assert "★SCP最大" not in tag_map.get(0, set())

    def test_scp_max_tiebreak_by_atk(self) -> None:
        """★SCP最大の同点は攻撃実数値が高い方に付くこと。"""
        scp_val = 1200.0
        rows = [
            _make_row(0, scp_cont=scp_val, atk=100.0, rank=2),
            _make_row(1, scp_cont=scp_val, atk=110.0, rank=1),
        ]
        with patch(
            "src.scp_checker.scp_checker._get_top1_scp_continuous", autospec=True, return_value=1250.0
        ):
            tag_map = assign_recommend_tags(rows, _POKEDEX)
        assert "★SCP最大" in tag_map[1]
        assert "★SCP最大" not in tag_map.get(0, set())

    def test_scp_jushi_tag_assigned_within_99_percent(self) -> None:
        """★SCP重視1位は top1_scp_cont の 99% 以上の個体に付くこと。"""
        top1 = 1000.0
        # 1000 * 0.99 = 990.0 → scp_cont >= 990.0 が対象
        rows = [
            _make_row(0, scp_cont=995.0, atk=100.0, rank=2),
            _make_row(1, scp_cont=980.0, atk=105.0, rank=5),  # 閾値未満
        ]
        with patch(
            "src.scp_checker.scp_checker._get_top1_scp_continuous", autospec=True, return_value=top1
        ):
            tag_map = assign_recommend_tags(rows, _POKEDEX)
        assert "★SCP重視1位" in tag_map[0]
        assert "★SCP重視1位" not in tag_map.get(1, set())

    def test_scp_jushi_fallback_when_no_candidate_meets_threshold(self) -> None:
        """★SCP重視：閾値を満たす個体がいない場合、ランク最良の 1 体が 1 位タグを得る。"""
        top1 = 2000.0
        # 2000 * 0.99 = 1980.0 → 誰も閾値を満たさない
        rows = [
            _make_row(0, scp_cont=1000.0, atk=100.0, rank=10),
            _make_row(1, scp_cont=1100.0, atk=90.0, rank=5),  # 最良ランク
        ]
        with patch(
            "src.scp_checker.scp_checker._get_top1_scp_continuous", autospec=True, return_value=top1
        ):
            tag_map = assign_recommend_tags(rows, _POKEDEX)
        assert "★SCP重視1位" in tag_map[1]
        assert "★SCP重視2位" not in tag_map.get(0, set())
        assert "★SCP重視2位" not in tag_map.get(1, set())

    def test_scp_jushi_boundary_scp_cont_between_float_and_ceil_threshold(self) -> None:
        """★SCP重視：閾値が小数になるケースで ceil との差が出る境界値テスト。

        top1=1000.5 → t = 1000.5 * 0.99 = 990.495
        rows[1].scp_cont=990.5 は float 閾値（990.495）以上だが ceil(990.495)=991 未満。
        ceil を使っていた旧実装では除外されたが、正しくは★SCP重視2位が付くべき。
        """
        top1 = 1000.5
        rows = [
            _make_row(0, scp_cont=1000.0, atk=100.0, rank=1),
            _make_row(1, scp_cont=990.5, atk=95.0, rank=3),  # 990.495 以上、ceil(990.495)=991 未満
        ]
        with patch(
            "src.scp_checker.scp_checker._get_top1_scp_continuous", autospec=True, return_value=top1
        ):
            tag_map = assign_recommend_tags(rows, _POKEDEX)
        assert "★SCP重視1位" in tag_map.get(0, set())
        assert "★SCP重視2位" in tag_map.get(1, set())

    def test_scp_jushi_2nd_tag_assigned_when_two_candidates_pass(self) -> None:
        """★SCP重視2位：99% 以上を満たす個体が 2 体いれば 2 位タグが付くこと。"""
        top1 = 1000.0
        # t = 990.0 → 両行が閾値以上
        rows = [
            _make_row(0, scp_cont=995.0, atk=100.0, rank=2),
            _make_row(1, scp_cont=992.0, atk=110.0, rank=5),
        ]
        with patch(
            "src.scp_checker.scp_checker._get_top1_scp_continuous", autospec=True, return_value=top1
        ):
            tag_map = assign_recommend_tags(rows, _POKEDEX)
        # _pick_top2 は (-atk, -scp_cont) 順なので atk=110 の rows[1] が 1 位
        assert "★SCP重視1位" in tag_map.get(1, set())
        assert "★SCP重視2位" in tag_map.get(0, set())

    def test_balance_top2_assigned_with_two_candidates(self) -> None:
        """★バランス1位・2位：条件を満たす個体が 2 体いれば両方に付くこと。

        閾値の計算：
          t1 = 1000.0 * 0.988 = 988.0 → 両行が 1 段階目を通過
          base（攻撃実数値最大）= rows[0]（atk=110）, scp_cont=995.0
          t2 = 995.0 * 0.9975 = 992.5125 → 992.5125 以上が 2 段階目を通過
          rows[1] の scp_cont は 994 であり閾値以上のため 2 段階目も通過する
        """
        top1 = 1000.0
        rows = [
            _make_row(0, scp_cont=995.0, atk=110.0, rank=1),
            _make_row(1, scp_cont=994.0, atk=100.0, rank=3),  # t2=992.5125 以上を満たす値
        ]
        with patch(
            "src.scp_checker.scp_checker._get_top1_scp_continuous", autospec=True, return_value=top1
        ):
            tag_map = assign_recommend_tags(rows, _POKEDEX)
        # 攻撃実数値が高い rows[0] が 1 位、rows[1] が 2 位
        assert "★バランス1位" in tag_map[0]
        assert "★バランス2位" in tag_map[1]

    def test_balance_boundary_scp_cont_between_float_and_ceil_threshold(self) -> None:
        """★バランス2段階目：閾値が小数になるケースで ceil との差が出る境界値テスト。

        base.scp_cont=995.0 → t2 = 995.0 * 0.9975 = 992.5125
        rows[1].scp_cont=992.6 は float 閾値（992.5125）以上だが ceil(992.5125)=993 未満。
        ceil を使っていた旧実装では除外されたが、正しくは★バランス2位が付くべき。
        """
        top1 = 1000.0
        rows = [
            _make_row(0, scp_cont=995.0, atk=110.0, rank=1),   # base（atk 最大）
            _make_row(1, scp_cont=992.6, atk=100.0, rank=3),   # 992.5125 以上、ceil(992.5125)=993 未満
        ]
        with patch(
            "src.scp_checker.scp_checker._get_top1_scp_continuous", autospec=True, return_value=top1
        ):
            tag_map = assign_recommend_tags(rows, _POKEDEX)
        assert "★バランス1位" in tag_map[0]
        assert "★バランス2位" in tag_map[1]

    def test_balance_first_stage_fallback_assigns_one_tag(self) -> None:
        """★バランス：1段階目を通過する個体がいない場合、ランク最良の 1 体が 1 位タグを得る。

        t1 = 2000.0 * 0.988 = 1976.0 → 誰も通過しない
        base = min_rank = rows[1]（rank=1）
        t2 = 998.0 * 0.9975 = 995.505 → rows[0].scp_cont=990.0 は除外
        c2 = [rows[1]] → top2 に 1 体のみ → 1 位のみ付与
        """
        top1 = 2000.0
        rows = [
            _make_row(0, scp_cont=990.0, atk=110.0, rank=5),
            _make_row(1, scp_cont=998.0, atk=100.0, rank=1),  # 最良ランク
        ]
        with patch(
            "src.scp_checker.scp_checker._get_top1_scp_continuous", autospec=True, return_value=top1
        ):
            tag_map = assign_recommend_tags(rows, _POKEDEX)
        assert "★バランス1位" in tag_map[1]
        assert "★バランス2位" not in tag_map.get(0, set())
        assert "★バランス2位" not in tag_map.get(1, set())

    def test_balance_second_stage_only_one_candidate_assigned(self) -> None:
        """★バランス：2段階目を通過する個体が 1 体のみの場合、1 位タグのみ付くこと。

        t1 = 1000.0 * 0.988 = 988.0 → rows[0] のみ通過（rows[1]=987.0 < 988.0）
        base = rows[0]（c1 の唯一の要素）, scp_cont=990.0
        t2 = 990.0 * 0.9975 = 987.525 → rows[1].scp_cont=987.0 は 987.525 未満で除外
        c2 = [rows[0]] → top2 に 1 体のみ → 1 位のみ付与
        """
        top1 = 1000.0
        rows = [
            _make_row(0, scp_cont=990.0, atk=110.0, rank=1),
            _make_row(1, scp_cont=987.0, atk=100.0, rank=3),  # t2=987.525 未満
        ]
        with patch(
            "src.scp_checker.scp_checker._get_top1_scp_continuous", autospec=True, return_value=top1
        ):
            tag_map = assign_recommend_tags(rows, _POKEDEX)
        assert "★バランス1位" in tag_map[0]
        assert "★バランス2位" not in tag_map.get(0, set())
        assert "★バランス2位" not in tag_map.get(1, set())

    def test_kogeki_jushi_top2_assigned_with_two_candidates(self) -> None:
        """★攻撃重視1位・2位：2 体とも両段階を通過する場合、1 位・2 位が付くこと。

        t1 = 1000.0 * 0.985 = 985.0 → 両行が 1 段階目を通過
        base（atk 最大）= rows[0]（atk=110）, scp_cont=990.0
        t2 = 990.0 * 0.996 = 986.04 → rows[1].scp_cont=987.0 は 986.04 以上のため通過
        """
        top1 = 1000.0
        rows = [
            _make_row(0, scp_cont=990.0, atk=110.0, rank=1),
            _make_row(1, scp_cont=987.0, atk=100.0, rank=3),
        ]
        with patch(
            "src.scp_checker.scp_checker._get_top1_scp_continuous", autospec=True, return_value=top1
        ):
            tag_map = assign_recommend_tags(rows, _POKEDEX)
        assert "★攻撃重視1位" in tag_map[0]
        assert "★攻撃重視2位" in tag_map[1]

    def test_kogeki_jushi_boundary_scp_cont_between_float_and_ceil_threshold(self) -> None:
        """★攻撃重視2段階目：閾値が小数になるケースで ceil との差が出る境界値テスト。

        base.scp_cont=997.0 → t2 = 997.0 * 0.996 = 993.012
        rows[1].scp_cont=993.1 は float 閾値（993.012）以上だが ceil(993.012)=994 未満。
        ceil を使っていた旧実装では除外されたが、正しくは★攻撃重視2位が付くべき。
        """
        top1 = 1000.0
        rows = [
            _make_row(0, scp_cont=997.0, atk=110.0, rank=1),   # base（atk 最大）
            _make_row(1, scp_cont=993.1, atk=100.0, rank=3),   # 993.012 以上、ceil(993.012)=994 未満
        ]
        with patch(
            "src.scp_checker.scp_checker._get_top1_scp_continuous", autospec=True, return_value=top1
        ):
            tag_map = assign_recommend_tags(rows, _POKEDEX)
        assert "★攻撃重視1位" in tag_map[0]
        assert "★攻撃重視2位" in tag_map[1]

    def test_kogeki_jushi_first_stage_fallback_assigns_one_tag(self) -> None:
        """★攻撃重視：1段階目を通過する個体がいない場合、ランク最良の 1 体が 1 位タグを得る。

        t1 = 2000.0 * 0.985 = 1970.0 → 誰も通過しない
        base = min_rank = rows[1]（rank=1）
        t2 = 998.0 * 0.996 = 994.008 → rows[0].scp_cont=990.0 は除外
        c2 = [rows[1]] → top2 に 1 体のみ → 1 位のみ付与
        """
        top1 = 2000.0
        rows = [
            _make_row(0, scp_cont=990.0, atk=110.0, rank=5),
            _make_row(1, scp_cont=998.0, atk=100.0, rank=1),  # 最良ランク
        ]
        with patch(
            "src.scp_checker.scp_checker._get_top1_scp_continuous", autospec=True, return_value=top1
        ):
            tag_map = assign_recommend_tags(rows, _POKEDEX)
        assert "★攻撃重視1位" in tag_map[1]
        assert "★攻撃重視2位" not in tag_map.get(0, set())
        assert "★攻撃重視2位" not in tag_map.get(1, set())

    def test_kogeki_jushi_second_stage_only_one_candidate_assigned(self) -> None:
        """★攻撃重視：2段階目を通過する個体が 1 体のみの場合、1 位タグのみ付くこと。

        t1 = 1000.0 * 0.985 = 985.0 → 両行が 1 段階目を通過
        base（atk 最大）= rows[0]（atk=110）, scp_cont=990.0
        t2 = 990.0 * 0.996 = 986.04 → rows[1].scp_cont=985.5 は 986.04 未満で除外
        c2 = [rows[0]] → top2 に 1 体のみ → 1 位のみ付与
        """
        top1 = 1000.0
        rows = [
            _make_row(0, scp_cont=990.0, atk=110.0, rank=1),
            _make_row(1, scp_cont=985.5, atk=100.0, rank=3),  # t2=986.04 未満
        ]
        with patch(
            "src.scp_checker.scp_checker._get_top1_scp_continuous", autospec=True, return_value=top1
        ):
            tag_map = assign_recommend_tags(rows, _POKEDEX)
        assert "★攻撃重視1位" in tag_map[0]
        assert "★攻撃重視2位" not in tag_map.get(0, set())
        assert "★攻撃重視2位" not in tag_map.get(1, set())

    def test_rb_tag_applied_in_format_output(self) -> None:
        """レベルが 50 超の個体は format_output 内で [RB] タグが付くこと。"""
        rows = [
            {**_make_row(0, scp_cont=1000.0, atk=100.0, rank=1), "level": 50.5}
        ]
        tag_map: dict[int, set[str]] = {}
        output = format_output(rows, tag_map)
        assert "[RB]" in output

    def test_no_rb_tag_for_level_50(self) -> None:
        """レベルがちょうど 50.0 の場合は [RB] タグが付かないこと（50 超が条件）。"""
        rows = [
            {**_make_row(0, scp_cont=1000.0, atk=100.0, rank=1), "level": 50.0}
        ]
        tag_map: dict[int, set[str]] = {}
        output = format_output(rows, tag_map)
        assert "[RB]" not in output

    def test_tag_map_groups_shadow_and_normal_separately(self) -> None:
        """通常個体とシャドウ個体は別グループとしてタグ判定されること。"""
        rows = [
            {**_make_row(0, scp_cont=1200.0, atk=100.0, rank=1), "name": "プクリン", "shadow": False},
            {**_make_row(1, scp_cont=1100.0, atk=110.0, rank=5), "name": "Sプクリン", "shadow": True},
        ]
        with patch(
            "src.scp_checker.scp_checker._get_top1_scp_continuous", autospec=True, return_value=1250.0
        ):
            tag_map = assign_recommend_tags(rows, _POKEDEX)
        # 通常とシャドウそれぞれに ★SCP最大 が付く
        assert "★SCP最大" in tag_map[0]
        assert "★SCP最大" in tag_map[1]

    def test_get_top1_scp_continuous_without_mock(self) -> None:
        """_get_top1_scp_continuous をモックせず実際の計算で検証する。

        全テストでモックしているため、このテストでのみモックを外して実際の計算を実行する。
        scp_cont=1000 の低ランク個体が ★SCP重視2位 を得ないことを確認する。
        _get_top1_scp_continuous が 0 を誤って返すと、top1=0 として両者が閾値を超え
        低ランク個体にも ★SCP重視2位 が付いてしまうため、この検証が内部計算の正しさを担保する。
        """
        rows = [
            _make_row(0, scp_cont=1580.0, atk=110.0, rank=1),
            _make_row(1, scp_cont=1000.0, atk=100.0, rank=4000),
        ]
        tag_map = assign_recommend_tags(rows, _POKEDEX)
        assert "★SCP重視1位" in tag_map[0]
        assert "★SCP重視2位" not in tag_map.get(1, set())


# ============================================================
# format_output
# ============================================================


class TestFormatOutput:
    def _make_simple_rows(self) -> list[dict]:
        """format_output テスト用の最小限の rows を返す。"""
        return [
            {
                "idx": 0,
                "input": "プクリン/1/12/6",
                "league": "S",
                "name": "プクリン",
                "shadow": False,
                "rank": 7,
                "scp": 1564,
                "scp_cont": 1564.3,
                "atk": 114.64,
                "def": 76.19,
                "hp": 224,
                "cp": 1500,
                "level": 29.5,
            }
        ]

    def test_fixed_comment_block_present(self) -> None:
        """固定コメントブロックが出力冒頭に含まれること。"""
        rows = self._make_simple_rows()
        output = format_output(rows, {})
        assert "# おすすめタグの選定条件" in output
        assert "# ★SCP最大  : " in output

    def test_header_contains_column_names(self) -> None:
        """ヘッダー行に全列名が含まれること。"""
        rows = self._make_simple_rows()
        output = format_output(rows, {})
        lines = output.splitlines()
        header = next(l for l in lines if "League" in l and "SCPRANK" in l)
        for col in ("League", "SCPRANK", "SCP", "ATK", "DEF", "HP", "CP", "Level"):
            assert col in header

    def test_rank_zero_padded_to_4_digits(self) -> None:
        """SCPRANK は 4 桁ゼロ埋めで出力されること（例：0007）。"""
        rows = self._make_simple_rows()
        output = format_output(rows, {})
        assert "0007" in output

    def test_blank_line_inserted_between_different_pokemon(self) -> None:
        """ポケモン名が変わる行の前に空行が挿入されること。"""
        rows = [
            {**self._make_simple_rows()[0], "idx": 0, "input": "プクリン/1/12/6",
             "name": "プクリン", "shadow": False},
            {**self._make_simple_rows()[0], "idx": 1, "input": "カメックス/0/14/10",
             "name": "カメックス", "shadow": False},
        ]
        output = format_output(rows, {})
        lines = output.splitlines()
        # 空行があること
        assert "" in lines

    def test_no_blank_line_between_same_group(self) -> None:
        """同一ポケモン×リーグ×シャドウが連続する場合は空行を挿入しないこと。"""
        rows = [
            {**self._make_simple_rows()[0], "idx": 0},
            {**self._make_simple_rows()[0], "idx": 1, "input": "プクリン/2/14/6"},
        ]
        output = format_output(rows, {})
        data_lines = [l for l in output.splitlines() if "プクリン" in l]
        # 2 件のデータ行の間に空行が無いこと（空行は挿入されない）
        assert len(data_lines) == 2

    def test_tag_order_is_fixed(self) -> None:
        """複数タグが付いた場合、固定順（SCP基準降順）で並ぶこと。"""
        rows = self._make_simple_rows()
        tag_map: dict[int, set[str]] = {
            0: {"★バランス1位", "★SCP最大", "★SCP重視1位"}
        }
        output = format_output(rows, tag_map)
        # 出力行からタグ欄を取り出す
        data_line = next(l for l in output.splitlines() if "プクリン/1/12/6" in l)
        tag_section = data_line.split("  ", 1)[1] if "  " in data_line else ""
        pos_scp_max = tag_section.find("★SCP最大")
        pos_scp_jushi = tag_section.find("★SCP重視1位")
        pos_balance = tag_section.find("★バランス1位")
        assert pos_scp_max < pos_scp_jushi < pos_balance

    def test_no_tag_line_when_no_tags(self) -> None:
        """タグが無い行はタグ欄自体を出力しないこと（末尾にスペースが付かない）。"""
        rows = self._make_simple_rows()
        output = format_output(rows, {})
        data_line = next(l for l in output.splitlines() if "プクリン/1/12/6" in l)
        assert not data_line.endswith("  ")
        assert "★" not in data_line

    def test_input_width_padded_to_longest_plus_2(self) -> None:
        """
        入力表示列の幅は全結果行の中で最長の文字数＋2 に揃うこと。
        """
        rows = [
            {**self._make_simple_rows()[0], "idx": 0, "input": "プクリン/1/12/6"},     # 11文字
            {**self._make_simple_rows()[0], "idx": 1, "input": "カメックス/0/14/10",   # 13文字
             "name": "カメックス", "shadow": False},
        ]
        output = format_output(rows, {})
        lines = [l for l in output.splitlines() if "プクリン" in l or "カメックス" in l]
        # 各データ行がリーグ列（League）の位置で揃っているか確認
        # 最長は 13 文字なので input_width = 15
        for line in lines:
            # League 値（S）は input_width（15）文字目以降にある
            assert line[15:16] == "S"


# ============================================================
# apply_bulk_replace
# ============================================================


class TestApplyBulkReplace:
    def _base_requests(self) -> list[tuple]:
        return [
            ("プクリン", "S", 1, 12, 6, False),
            ("プクリン", "H", 2, 14, 6, False),
            ("カメックス", "S", 0, 14, 10, False),
        ]

    def test_error_when_both_from_unspecified(self) -> None:
        reqs = self._base_requests()
        new_list, success, err = apply_bulk_replace(reqs, "", "変更なし", "ラッキー", "変更なし", _POKEDEX)
        assert err == "置換前のポケモン名またはリーグを指定してください。"
        assert success is None
        assert new_list is reqs  # リストは変更されない

    def test_error_when_both_to_unspecified(self) -> None:
        reqs = self._base_requests()
        new_list, success, err = apply_bulk_replace(reqs, "プクリン", "変更なし", "", "変更なし", _POKEDEX)
        assert err == "置換後のポケモン名またはリーグを指定してください。"
        assert success is None

    def test_error_when_to_name_not_in_pokedex(self) -> None:
        reqs = self._base_requests()
        new_list, success, err = apply_bulk_replace(reqs, "プクリン", "変更なし", "ミュウ", "変更なし", _POKEDEX)
        assert err == "「ミュウ」はpokedex_numbers.txtに存在しません。"
        assert success is None

    def test_warning_when_no_target_row(self) -> None:
        reqs = self._base_requests()
        new_list, success, err = apply_bulk_replace(
            reqs, "ゲンガー", "変更なし", "ラッキー", "変更なし", _POKEDEX
        )
        assert err == "条件に一致する行がリストに存在しません。"
        assert success is None

    def test_replace_name_only(self) -> None:
        """ポケモン名のみ置換する場合、リーグ・IV は変わらないこと。"""
        reqs = [("プクリン", "S", 1, 12, 6, False)]
        new_list, success, err = apply_bulk_replace(
            reqs, "プクリン", "変更なし", "カメックス", "変更なし", _POKEDEX
        )
        assert err is None
        assert new_list[0][0] == "カメックス"
        assert new_list[0][1] == "S"  # リーグ変わらず
        assert new_list[0][2:5] == (1, 12, 6)  # IV 変わらず

    def test_replace_league_only(self) -> None:
        """リーグのみ置換する場合、ポケモン名は変わらないこと。"""
        reqs = [("プクリン", "S", 1, 12, 6, False)]
        new_list, success, err = apply_bulk_replace(
            reqs, "", "S", "", "H", _POKEDEX
        )
        assert err is None
        assert new_list[0][0] == "プクリン"
        assert new_list[0][1] == "H"

    def test_replace_both_name_and_league(self) -> None:
        """名前とリーグを同時に置換できること。"""
        reqs = [("プクリン", "S", 1, 12, 6, False)]
        new_list, success, err = apply_bulk_replace(
            reqs, "プクリン", "S", "カメックス", "H", _POKEDEX
        )
        assert err is None
        assert new_list[0][0] == "カメックス"
        assert new_list[0][1] == "H"

    def test_replace_count_correct(self) -> None:
        """置換件数が成功メッセージに反映されること。"""
        reqs = self._base_requests()
        _new_list, success, err = apply_bulk_replace(
            reqs, "プクリン", "変更なし", "カメックス", "変更なし", _POKEDEX
        )
        assert err is None
        assert "2件" in success

    def test_success_message_name_only_format(self) -> None:
        """名前のみ指定時は名前項目のみがメッセージに含まれること。"""
        reqs = [("プクリン", "S", 1, 12, 6, False)]
        _new_list, success, err = apply_bulk_replace(
            reqs, "プクリン", "変更なし", "カメックス", "変更なし", _POKEDEX
        )
        assert err is None
        assert "名前「プクリン」→「カメックス」" in success
        assert "リーグ" not in success

    def test_success_message_league_only_format(self) -> None:
        """リーグのみ指定時はリーグ項目のみがメッセージに含まれること。"""
        reqs = [("プクリン", "S", 1, 12, 6, False)]
        _new_list, success, err = apply_bulk_replace(
            reqs, "", "S", "", "H", _POKEDEX
        )
        assert err is None
        assert "リーグ「S」→「H」" in success
        assert "名前" not in success

    def test_shadow_flag_recalculated_after_replace(self) -> None:
        """置換後のポケモン名に対してシャドウフラグが再判定されること。"""
        reqs = [("プクリン", "S", 1, 12, 6, False)]
        new_list, success, err = apply_bulk_replace(
            reqs, "プクリン", "変更なし", "Sカメックス", "変更なし", _POKEDEX
        )
        assert err is None
        assert new_list[0][0] == "Sカメックス"
        assert new_list[0][5] is True  # shadow フラグが True になっていること

    def test_non_target_rows_unchanged(self) -> None:
        """絞り込み条件に一致しない行は変更されないこと。"""
        reqs = self._base_requests()
        new_list, success, err = apply_bulk_replace(
            reqs, "プクリン", "S", "カメックス", "変更なし", _POKEDEX
        )
        assert err is None
        # プクリン/S のみ置換（2 件目のプクリン/H は対象外）
        assert new_list[0][0] == "カメックス"
        assert new_list[1][0] == "プクリン"  # H は変更されない
        assert new_list[2][0] == "カメックス"  # もともとカメックス（対象外のはず）
        # 実際には プクリン/S だけが対象なので カメックス/S の行は変わらない
        # 最後の行(カメックス)も対象外
        assert new_list[2] == reqs[2]

    def test_shadow_name_validated_without_s_prefix(self) -> None:
        """置換後にシャドウ名（Sプクリン等）を指定した場合、S 除き名で pokedex バリデーションされること。"""
        reqs = [("カメックス", "S", 0, 14, 10, False)]
        # Sプクリン → プクリンは pokedex に存在するのでエラーにならない
        new_list, success, err = apply_bulk_replace(
            reqs, "カメックス", "変更なし", "Sプクリン", "変更なし", _POKEDEX
        )
        assert err is None
        assert new_list[0][0] == "Sプクリン"
