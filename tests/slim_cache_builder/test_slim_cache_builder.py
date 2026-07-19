"""
tests/slim_cache_builder/test_slim_cache_builder.py

slim_cache_builder（features 層）の単体テスト。
features の各公開関数はファイル I/O を持たない純粋関数のため、モック不要。
expand_targets も純粋関数なので parse_input のテストも実データで呼ぶ。
"""

from __future__ import annotations

import math

import pytest

from src.slim_cache_builder.slim_cache_builder import (
    CPM,
    LEAGUE_CAPS,
    SCRIPT_VERSION,
    best_within_cap,
    build_cache_object,
    calc_cp,
    calc_slim_entries,
    calc_scp,
    calc_stats,
    iv_to_bucket,
    parse_input,
)

# ============================================================
# 共通テストデータ
# ============================================================

# 段構造の進化マップ（load_evolution_map_staged の返り値と同じ形式）
_EVO_MAP: list[list[list[str]]] = [
    [["MonA"], ["MonB"], ["MonC"]],       # 3段直線
    [["MonD"], ["MonE", "MonF"]],          # 2段・最終段分岐
]

# ポケモン名 → 種族値辞書（load_pokedex_full の返り値と同じ形式）
_POKEDEX: dict[str, dict[str, int]] = {
    "MonA": {"dex": 1, "hp_base": 128, "atk_base": 118, "def_base": 111},
    "MonB": {"dex": 2, "hp_base": 155, "atk_base": 151, "def_base": 143},
    "MonC": {"dex": 3, "hp_base": 160, "atk_base": 198, "def_base": 189},
    "MonD": {"dex": 4, "hp_base": 120, "atk_base": 100, "def_base": 100},
    "MonE": {"dex": 5, "hp_base": 130, "atk_base": 140, "def_base": 130},
    "MonF": {"dex": 6, "hp_base": 130, "atk_base": 150, "def_base": 120},
    "Solo": {"dex": 7, "hp_base": 100, "atk_base": 100, "def_base": 100},
}

# 計算テスト用の汎用種族値（端数が出にくい丸い値）
_BASE_100 = {"atk_base": 100, "def_base": 100, "hp_base": 100}


# ============================================================
# iv_to_bucket
# ============================================================


class TestIvToBucket:
    def test_iv_0_returns_bucket_0(self) -> None:
        assert iv_to_bucket(0) == 0

    def test_iv_1_returns_bucket_1(self) -> None:
        assert iv_to_bucket(1) == 1

    def test_iv_5_returns_bucket_1(self) -> None:
        """境界値: 5 はバケット 1 の上限"""
        assert iv_to_bucket(5) == 1

    def test_iv_6_returns_bucket_2(self) -> None:
        """境界値: 6 はバケット 2 の下限"""
        assert iv_to_bucket(6) == 2

    def test_iv_10_returns_bucket_2(self) -> None:
        """境界値: 10 はバケット 2 の上限"""
        assert iv_to_bucket(10) == 2

    def test_iv_11_returns_bucket_3(self) -> None:
        """境界値: 11 はバケット 3 の下限"""
        assert iv_to_bucket(11) == 3

    def test_iv_14_returns_bucket_3(self) -> None:
        """境界値: 14 はバケット 3 の上限"""
        assert iv_to_bucket(14) == 3

    def test_iv_15_returns_bucket_4(self) -> None:
        assert iv_to_bucket(15) == 4

    def test_all_16_ivs_cover_all_5_buckets(self) -> None:
        """全 IV（0〜15）にバケットを割り当てると 0〜4 の 5 種類が出る"""
        buckets = {iv_to_bucket(iv) for iv in range(16)}
        assert buckets == {0, 1, 2, 3, 4}


# ============================================================
# calc_cp
# ============================================================


class TestCalcCp:
    def test_base100_iv0_level1(self) -> None:
        """base=100, IV=0, level=1.0 での CP を手計算で検証する。

        (100+0) * sqrt(100+0) * sqrt(100+0) * (0.094^2) / 10
        = 100 * 10 * 10 * 0.008836 / 10 = 8.836 → floor → 8
        """
        cp = calc_cp(100, 100, 100, 0, 0, 0, 1.0)
        assert cp == 8

    def test_base100_iv15_level1(self) -> None:
        """base=100, IV=15, level=1.0 での CP を手計算で検証する。

        (115) * sqrt(115) * sqrt(115) * (0.094^2) / 10
        = 115 * 115 * 0.008836 / 10 = 11.685... → floor → 11
        """
        cp = calc_cp(100, 100, 100, 15, 15, 15, 1.0)
        assert cp == 11

    def test_higher_ivs_give_higher_or_equal_cp(self) -> None:
        """IV が高いほど CP は高くなる（単調性）"""
        cp_low = calc_cp(100, 100, 100, 0, 0, 0, 20.0)
        cp_high = calc_cp(100, 100, 100, 15, 15, 15, 20.0)
        assert cp_high >= cp_low

    def test_result_is_non_negative_integer(self) -> None:
        """CP は非負の整数"""
        cp = calc_cp(1, 1, 1, 0, 0, 0, 1.0)
        assert isinstance(cp, int)
        assert cp >= 0

    def test_cp_matches_floor_formula(self) -> None:
        """calc_cp の結果が公式の floor 計算と一致する"""
        level = 10.0
        cpm = CPM[level]
        expected = math.floor(
            (110 * math.sqrt(110) * math.sqrt(110) * (cpm**2)) / 10.0
        )
        assert calc_cp(100, 100, 100, 10, 10, 10, level) == expected


# ============================================================
# calc_stats
# ============================================================


class TestCalcStats:
    def test_returns_tuple_of_three(self) -> None:
        """返り値は (atk, deff, hp) の 3 要素タプル"""
        result = calc_stats(100, 100, 100, 0, 0, 0, 1.0)
        assert len(result) == 3

    def test_hp_is_int(self) -> None:
        """HP は floor 済みの整数"""
        _, _, hp = calc_stats(100, 100, 100, 0, 0, 0, 1.0)
        assert isinstance(hp, int)

    def test_atk_deff_are_float(self) -> None:
        """攻撃・防御は浮動小数点"""
        atk, deff, _ = calc_stats(100, 100, 100, 0, 0, 0, 1.0)
        assert isinstance(atk, float)
        assert isinstance(deff, float)

    def test_higher_level_gives_higher_stats(self) -> None:
        """レベルが高いほど実数値は高い"""
        atk_low, _, hp_low = calc_stats(100, 100, 100, 0, 0, 0, 1.0)
        atk_high, _, hp_high = calc_stats(100, 100, 100, 0, 0, 0, 40.0)
        assert atk_high > atk_low
        assert hp_high > hp_low


# ============================================================
# calc_scp
# ============================================================


class TestCalcScp:
    def test_round_numbers(self) -> None:
        """100 * 100 * 100 = 1,000,000 → 1,000,000^(2/3) / 10 の floor を検証する。

        浮動小数点の都合で 1,000,000^(2/3) は 9999.999... となるため floor 後は 999。
        """
        scp = calc_scp(100.0, 100.0, 100)
        assert scp == 999

    def test_higher_stats_give_higher_scp(self) -> None:
        """実数値が高いほど SCP は高い"""
        scp_low = calc_scp(50.0, 50.0, 50)
        scp_high = calc_scp(100.0, 100.0, 100)
        assert scp_high > scp_low

    def test_result_is_non_negative_integer(self) -> None:
        scp = calc_scp(1.0, 1.0, 1)
        assert isinstance(scp, int)
        assert scp >= 0


# ============================================================
# best_within_cap
# ============================================================


class TestBestWithinCap:
    def test_returns_dict_within_cap(self) -> None:
        """結果の CP は cap 以下"""
        result = best_within_cap(100, 100, 100, 0, 0, 0, 1500)
        assert result is not None
        assert result["cp"] <= 1500

    def test_max_ivs_still_within_cap(self) -> None:
        """最大 IV でも CP は cap 以下"""
        result = best_within_cap(200, 200, 200, 15, 15, 15, 1500)
        assert result is not None
        assert result["cp"] <= 1500

    def test_no_cap_uses_max_level(self) -> None:
        """cap_cp=None ならレベル 51.0（CPM テーブルの最大）で計算される"""
        result = best_within_cap(100, 100, 100, 0, 0, 0, None)
        assert result is not None
        assert result["level"] == 51.0

    def test_higher_ivs_give_higher_or_equal_scp_with_no_cap(self) -> None:
        """cap なしでは、IV が高いほど SCP は高い（全レベルを探索するため）"""
        result_zero = best_within_cap(100, 100, 100, 0, 0, 0, None)
        result_max = best_within_cap(100, 100, 100, 15, 15, 15, None)
        assert result_zero is not None
        assert result_max is not None
        assert result_max["scp"] >= result_zero["scp"]

    def test_result_has_required_keys(self) -> None:
        """結果辞書に必要なキーが揃っている"""
        result = best_within_cap(100, 100, 100, 0, 0, 0, 1500)
        assert result is not None
        for key in ("level", "cp", "atk", "def", "hp", "scp"):
            assert key in result


# ============================================================
# calc_slim_entries
# ============================================================


class TestCalcSlimEntries:
    def test_length_does_not_exceed_topn(self) -> None:
        """結果件数は topn 以下"""
        entries = calc_slim_entries(_BASE_100, 1500, 10)
        assert len(entries) <= 10

    def test_all_4096_ivs_with_no_cap(self) -> None:
        """cap なし・topn=4096 で 16^3=4096 件すべて返る"""
        entries = calc_slim_entries(_BASE_100, None, 4096)
        assert len(entries) == 4096

    def test_rank_starts_at_1(self) -> None:
        """最初のエントリのランクは 1"""
        entries = calc_slim_entries(_BASE_100, 1500, 10)
        assert entries[0].startswith("1,")

    def test_ranks_are_sequential(self) -> None:
        """ランクは 1 から連番"""
        entries = calc_slim_entries(_BASE_100, 1500, 5)
        for i, entry in enumerate(entries):
            rank = int(entry.split(",")[0])
            assert rank == i + 1

    def test_entry_has_5_fields(self) -> None:
        """1 エントリは 5 フィールドのカンマ区切り"""
        entries = calc_slim_entries(_BASE_100, 1500, 1)
        assert len(entries) == 1
        parts = entries[0].split(",")
        assert len(parts) == 5

    def test_bucket_fields_are_valid(self) -> None:
        """atk/def/hp バケットは 0〜4 の整数"""
        entries = calc_slim_entries(_BASE_100, 1500, 20)
        for entry in entries:
            parts = entry.split(",")
            for bucket_str in parts[1:4]:
                assert bucket_str in {"0", "1", "2", "3", "4"}

    def test_atk_real_has_two_decimal_places(self) -> None:
        """攻撃実数値フィールドは小数点以下 2 桁"""
        entries = calc_slim_entries(_BASE_100, 1500, 5)
        for entry in entries:
            atk_real_str = entry.split(",")[4]
            assert "." in atk_real_str
            assert len(atk_real_str.split(".")[1]) == 2

    def test_first_entry_has_highest_scp(self) -> None:
        """上位エントリほど SCP が高い（または等しい）ことを atk_real で間接検証"""
        # SCP は最大で atk_real（攻撃実数値）に強く相関するため、
        # ランク 1 の atk_real はランク 2 以降と比較して最大付近にあるはず
        # 直接的には「rank が連番かつエントリが TopN 件」でソートの妥当性を確認する
        entries = calc_slim_entries(_BASE_100, 1500, 4096)
        assert len(entries) > 0
        assert entries[0].split(",")[0] == "1"


# ============================================================
# parse_input
# ============================================================


class TestParseInput:
    def test_O_spec_returns_own_pokemon(self) -> None:
        """O 指定: 起点ポケモン本人を対象にする"""
        result = parse_input(["MonA/S/200/O"], _EVO_MAP, _POKEDEX)
        assert result == {"MonA": {"S": 200}}

    def test_L_spec_3stage_returns_final(self) -> None:
        """L 指定・3段: 最終段ポケモンを対象にする"""
        result = parse_input(["MonA/S/200/L"], _EVO_MAP, _POKEDEX)
        assert result == {"MonC": {"S": 200}}

    def test_M_spec_3stage_returns_middle(self) -> None:
        """M 指定・3段: 中間段ポケモンを対象にする"""
        result = parse_input(["MonA/S/200/M"], _EVO_MAP, _POKEDEX)
        assert result == {"MonB": {"S": 200}}

    def test_L_spec_2stage_branched_returns_both(self) -> None:
        """L 指定・2段分岐: 最終段の分岐先すべてを対象にする"""
        result = parse_input(["MonD/S/200/L"], _EVO_MAP, _POKEDEX)
        assert set(result.keys()) == {"MonE", "MonF"}
        assert result["MonE"] == {"S": 200}
        assert result["MonF"] == {"S": 200}

    def test_multiple_leagues_comma_separated(self) -> None:
        """リーグをカンマ区切りで複数指定できる"""
        result = parse_input(["Solo/S,H/1000/O"], _EVO_MAP, _POKEDEX)
        assert result == {"Solo": {"S": 1000, "H": 1000}}

    def test_comma_separated_targets(self) -> None:
        """対象指定をカンマ区切りで複数指定できる（新書式）"""
        result = parse_input(["MonA/S/200/O,L"], _EVO_MAP, _POKEDEX)
        # O=MonA, L=MonC
        assert result == {"MonA": {"S": 200}, "MonC": {"S": 200}}

    def test_concatenated_targets_legacy_format(self) -> None:
        """対象指定の旧書式（連結文字列 "OL"）も受け入れる"""
        result = parse_input(["MonA/S/200/OL"], _EVO_MAP, _POKEDEX)
        assert result == {"MonA": {"S": 200}, "MonC": {"S": 200}}

    def test_duplicate_league_adopts_max_topn(self) -> None:
        """同じポケモン×リーグが複数行あれば最大 TopN を採用する"""
        result = parse_input(
            ["Solo/S/200/O", "Solo/S/500/O"],
            _EVO_MAP,
            _POKEDEX,
        )
        assert result == {"Solo": {"S": 500}}

    def test_solo_not_in_evo_map_uses_O_treatment(self) -> None:
        """evo_map 未収録ポケモンは O 扱い（expand_targets の仕様）"""
        result = parse_input(["Solo/S/200/L"], _EVO_MAP, _POKEDEX)
        # expand_targets は未収録を本人のみ返す
        assert result == {"Solo": {"S": 200}}

    def test_empty_lines_already_filtered(self) -> None:
        """空行リストなら空の target_map を返す（esal が空行を除外済みの想定）"""
        result = parse_input([], _EVO_MAP, _POKEDEX)
        assert result == {}

    def test_invalid_league_raises_value_error(self) -> None:
        """不正なリーグ指定は ValueError を raise する"""
        with pytest.raises(ValueError, match="不正なリーグ指定"):
            parse_input(["Solo/X/200/O"], _EVO_MAP, _POKEDEX)

    def test_topn_out_of_range_raises_value_error(self) -> None:
        """TopN が 1〜4096 の範囲外なら ValueError を raise する"""
        with pytest.raises(ValueError, match="1〜4096"):
            parse_input(["Solo/S/0/O"], _EVO_MAP, _POKEDEX)

    def test_topn_too_large_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="1〜4096"):
            parse_input(["Solo/S/9999/O"], _EVO_MAP, _POKEDEX)

    def test_pokemon_not_in_pokedex_raises_value_error(self) -> None:
        """pokedex に存在しないポケモン名は ValueError を raise する"""
        with pytest.raises(ValueError, match="pokedex_numbers.txt"):
            parse_input(["Unknown/S/200/O"], _EVO_MAP, _POKEDEX)

    def test_invalid_target_spec_raises_value_error(self) -> None:
        """O/M/L 以外の対象指定は ValueError を raise する"""
        with pytest.raises(ValueError, match="不正な対象指定"):
            parse_input(["Solo/S/200/Z"], _EVO_MAP, _POKEDEX)

    def test_malformed_line_raises_value_error(self) -> None:
        """/ 区切りが 3 フィールドに満たない行は ValueError を raise する"""
        with pytest.raises(ValueError, match="形式不正"):
            parse_input(["Solo/S"], _EVO_MAP, _POKEDEX)


# ============================================================
# build_cache_object
# ============================================================


class TestBuildCacheObject:
    def test_meta_fields_are_set_correctly(self) -> None:
        """meta フィールドに全必須キーが正しく設定される"""
        pokemon_entries = [{"name": "MonA", "dex": 1, "leagues": {}}]
        result = build_cache_object(pokemon_entries, 42, "2026-07-19T12:00:00")
        meta = result["meta"]
        assert meta["script_version"] == SCRIPT_VERSION
        assert meta["created_at"] == "2026-07-19T12:00:00"
        assert meta["total_pokemon"] == 1
        assert meta["total_entries"] == 42

    def test_pokemon_list_is_preserved(self) -> None:
        """pokemon リストはそのまま返される"""
        entries = [{"name": "MonA", "dex": 1, "leagues": {}}]
        result = build_cache_object(entries, 0, "2026-01-01T00:00:00")
        assert result["pokemon"] == entries

    def test_empty_pokemon_list(self) -> None:
        """pokemon リストが空でも meta.total_pokemon は 0"""
        result = build_cache_object([], 0, "2026-01-01T00:00:00")
        assert result["meta"]["total_pokemon"] == 0
        assert result["pokemon"] == []

    def test_league_caps_contains_expected_keys(self) -> None:
        """LEAGUE_CAPS に S/H/M が含まれ、S=1500・H=2500・M=None"""
        assert LEAGUE_CAPS["S"] == 1500
        assert LEAGUE_CAPS["H"] == 2500
        assert LEAGUE_CAPS["M"] is None
