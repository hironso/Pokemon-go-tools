"""
tests/id_generator/test_id_generator.py

id_generator の純粋ロジック（generate_ids）の単体テスト。
esal（ファイル読み込み）はテスト対象外：generate_ids はデータをパラメータで受け取るため
モック不要でテストできる。
"""

import pytest

from src.id_generator.id_generator import (
    NoValidInputError,
    UnknownPokemonError,
    generate_ids,
)

# ============================================================
# テスト用データ（最小限の固定値）
# ============================================================

# フシギダネ(1)・フシギソウ(2)・フシギバナ(3)、ヒトカゲ(4)・リザード(5)・リザードン(6)、
# ピカチュウ(25)（evo_map に載っていない単体ポケモンとして使う）
_POKEDEX: dict[str, int] = {
    "フシギダネ": 1,
    "フシギソウ": 2,
    "フシギバナ": 3,
    "ヒトカゲ": 4,
    "リザード": 5,
    "リザードン": 6,
    "ピカチュウ": 25,
}

_EVO_MAP: list[list[str]] = [
    ["フシギダネ", "フシギソウ", "フシギバナ"],
    ["ヒトカゲ", "リザード", "リザードン"],
]


# ============================================================
# 正常系
# ============================================================


class TestGenerateIds:
    def test_single_pokemon_expands_to_full_family(self) -> None:
        """ヒトカゲだけを入力 → 進化ファミリー全員の番号を返す"""
        result = generate_ids("ヒトカゲ", _POKEDEX, _EVO_MAP)
        assert result == "4,5,6"

    def test_two_different_families_spec_example(self) -> None:
        """仕様の具体例：ヒトカゲ＋フシギダネ → 1,2,3,4,5,6"""
        result = generate_ids("ヒトカゲ\nフシギダネ", _POKEDEX, _EVO_MAP)
        assert result == "1,2,3,4,5,6"

    def test_same_family_deduplication_spec_example(self) -> None:
        """仕様 5.2 具体例：フシギダネ＋フシギバナ（同ファミリー）→ 1,2,3"""
        result = generate_ids("フシギダネ\nフシギバナ", _POKEDEX, _EVO_MAP)
        assert result == "1,2,3"

    def test_pokemon_not_in_evo_map_treated_as_solo(self) -> None:
        """evo_map に載っていないポケモンは単体扱い（自身の番号のみ）"""
        result = generate_ids("ピカチュウ", _POKEDEX, _EVO_MAP)
        assert result == "25"

    def test_blank_lines_are_skipped(self) -> None:
        """空行はスキップされ、ヒトカゲのファミリーのみが出力される"""
        result = generate_ids("\nヒトカゲ\n\n", _POKEDEX, _EVO_MAP)
        assert result == "4,5,6"

    def test_comment_lines_are_skipped(self) -> None:
        """# で始まる行はコメントとしてスキップされる"""
        result = generate_ids("# ヒトカゲ\nフシギダネ\n# コメント", _POKEDEX, _EVO_MAP)
        assert result == "1,2,3"

    def test_output_is_sorted_ascending(self) -> None:
        """出力は昇順ソートされる（入力順に依存しない）"""
        result = generate_ids("ヒトカゲ\nフシギダネ", _POKEDEX, _EVO_MAP)
        numbers = [int(x) for x in result.split(",")]
        assert numbers == sorted(numbers)


# ============================================================
# 境界ケース：NoValidInputError（仕様 5.3）
# ============================================================


class TestNoValidInput:
    def test_empty_string_raises(self) -> None:
        """空文字列 → NoValidInputError"""
        with pytest.raises(NoValidInputError):
            generate_ids("", _POKEDEX, _EVO_MAP)

    def test_only_blank_lines_raises(self) -> None:
        """空行のみ → NoValidInputError"""
        with pytest.raises(NoValidInputError):
            generate_ids("\n\n\n", _POKEDEX, _EVO_MAP)

    def test_only_comment_lines_raises(self) -> None:
        """# コメントのみ → NoValidInputError"""
        with pytest.raises(NoValidInputError):
            generate_ids("# ヒトカゲ\n# フシギダネ", _POKEDEX, _EVO_MAP)

    def test_blank_and_comment_mixed_raises(self) -> None:
        """空行と # コメントの混在のみ → NoValidInputError"""
        with pytest.raises(NoValidInputError):
            generate_ids("\n# コメント\n\n", _POKEDEX, _EVO_MAP)


# ============================================================
# 境界ケース：UnknownPokemonError（仕様 5.1）
# ============================================================


class TestUnknownPokemon:
    def test_single_unknown_name_raises(self) -> None:
        """仕様 5.1：未収録名 1つ → UnknownPokemonError（その名前が unknown_names に入る）"""
        with pytest.raises(UnknownPokemonError) as exc_info:
            generate_ids("ミュウツーZ", _POKEDEX, _EVO_MAP)
        assert "ミュウツーZ" in exc_info.value.unknown_names

    def test_multiple_unknowns_all_listed(self) -> None:
        """仕様 5.1：未収録名が複数あればすべて列挙される"""
        with pytest.raises(UnknownPokemonError) as exc_info:
            generate_ids("ミュウツーZ\nフシギダネ\nメガリザードン", _POKEDEX, _EVO_MAP)
        unknown = exc_info.value.unknown_names
        assert "ミュウツーZ" in unknown
        assert "メガリザードン" in unknown
        assert "フシギダネ" not in unknown  # 収録済みなので含まれない

    def test_known_and_unknown_mixed_raises_without_partial_output(self) -> None:
        """仕様 5.1：収録済みと未収録が混在しても、部分出力せずに raise する"""
        with pytest.raises(UnknownPokemonError):
            generate_ids("ヒトカゲ\nミュウツーZ", _POKEDEX, _EVO_MAP)
