"""
tests/library/test_expand_targets.py

expand_targets の単体テスト（仕様書 spec/library.md 3章）。
esal（ファイル読み込み）はテスト対象外。evo_map_staged はテスト内で直接用意する。
"""

from src.library.expand_targets import expand_targets

# ============================================================
# 共通テストデータ
# ============================================================

# 段構造を保持した進化マップ（load_evolution_map_staged の返り値と同じ形式）
_EVO_MAP: list[list[list[str]]] = [
    [["フシギダネ"], ["フシギソウ"], ["フシギバナ"]],  # 3段・直線
    [["ヒトカゲ"], ["リザード"], ["リザードン"]],  # 3段・直線
    [["ヤドン"], ["ヤドラン", "ヤドキング"]],  # 2段・分岐
    [["ラルトス"], ["キルリア"], ["サーナイト", "エルレイド"]],  # 3段・最終段分岐
    [["イーブイ"], ["シャワーズ", "サンダース"]],  # 2段・多分岐（簡略版）
]


# ============================================================
# テストクラス
# ============================================================


class TestExpandTargets:
    # ---- L 指定 ----

    def test_L_3stage_linear_returns_last(self) -> None:
        """L指定・3段直線: 最終段のポケモンのみ返す（library.md 3.3）"""
        result = expand_targets("フシギダネ", ["L"], _EVO_MAP)
        assert result == ["フシギバナ"]

    def test_L_2stage_branching_returns_all_final(self) -> None:
        """L指定・2段分岐: 最終段（分岐先すべて）を返す（library.md 3.5 ヤドン/L）"""
        result = expand_targets("ヤドン", ["L"], _EVO_MAP)
        assert set(result) == {"ヤドラン", "ヤドキング"}

    def test_L_3stage_final_branching_returns_all_branches(self) -> None:
        """L指定・3段・最終段に分岐: 分岐先すべてを返す（library.md 3.5 ラルトス/L）"""
        result = expand_targets("ラルトス", ["L"], _EVO_MAP)
        assert set(result) == {"サーナイト", "エルレイド"}

    def test_L_2stage_multibranch_all_returned(self) -> None:
        """L指定・2段多分岐: 分岐先すべてを返す（library.md 3.5 イーブイ型）"""
        result = expand_targets("イーブイ", ["L"], _EVO_MAP)
        assert set(result) == {"シャワーズ", "サンダース"}

    # ---- M 指定 ----

    def test_M_3stage_linear_returns_middle(self) -> None:
        """M指定・3段直線: 2番目の段のポケモンを返す（library.md 3.5 フシギダネ/M）"""
        result = expand_targets("フシギダネ", ["M"], _EVO_MAP)
        assert result == ["フシギソウ"]

    def test_M_2stage_returns_same_as_L(self) -> None:
        """M指定・2段ファミリー: 最終段（L と同じ）を返す（library.md 3.4 2段行）"""
        result = expand_targets("ヤドン", ["M"], _EVO_MAP)
        assert set(result) == {"ヤドラン", "ヤドキング"}

    def test_M_3stage_no_final_branching(self) -> None:
        """M指定・3段・中間段に分岐なし: キルリアのみを返す（library.md 3.5 ラルトス/M）"""
        result = expand_targets("ラルトス", ["M"], _EVO_MAP)
        assert result == ["キルリア"]

    # ---- O 指定 ----

    def test_O_returns_original(self) -> None:
        """O指定: 入力したポケモン本人のみを返す（library.md 3.3）"""
        result = expand_targets("フシギダネ", ["O"], _EVO_MAP)
        assert result == ["フシギダネ"]

    def test_O_returns_original_regardless_of_stage(self) -> None:
        """O指定は段数に関わらず本人のみ（library.md 3.4 O行）"""
        result = expand_targets("ラルトス", ["O"], _EVO_MAP)
        assert result == ["ラルトス"]

    # ---- 未収録ポケモン ----

    def test_not_in_evo_map_L_returns_self(self) -> None:
        """evo_map 未収録ポケモン（単体）に L 指定: 本人のみを返す（library.md 3.3 未収録）"""
        result = expand_targets("ピカチュウ", ["L"], _EVO_MAP)
        assert result == ["ピカチュウ"]

    def test_not_in_evo_map_M_returns_self(self) -> None:
        """evo_map 未収録ポケモンに M 指定: 本人のみを返す（library.md 3.4 未収録行）"""
        result = expand_targets("ピカチュウ", ["M"], _EVO_MAP)
        assert result == ["ピカチュウ"]

    def test_not_in_evo_map_O_returns_self(self) -> None:
        """evo_map 未収録ポケモンに O 指定: 本人のみを返す"""
        result = expand_targets("ピカチュウ", ["O"], _EVO_MAP)
        assert result == ["ピカチュウ"]

    # ---- 重複除去・複数指定 ----

    def test_O_and_L_same_pokemon_deduplicated(self) -> None:
        """O+L が同じポケモンを指す場合、重複除去して1件を返す（library.md 3.2 初出優先）"""
        # フシギバナ自身が最終進化: O=フシギバナ, L=フシギバナ
        result = expand_targets("フシギバナ", ["O", "L"], _EVO_MAP)
        assert result == ["フシギバナ"]

    def test_multiple_targets_no_dedup_when_different(self) -> None:
        """O+L が別のポケモンを指す場合、両方を返す（指定順に並ぶ）"""
        result = expand_targets("フシギダネ", ["O", "L"], _EVO_MAP)
        # O=フシギダネ, L=フシギバナ
        assert result == ["フシギダネ", "フシギバナ"]

    def test_order_follows_target_then_map_order(self) -> None:
        """出力順序: 対象指定の指定順 → 各段はマップ収録順（library.md 3.2）"""
        # L 指定で分岐: マップ収録順（ヤドラン が先）で返る
        result = expand_targets("ヤドン", ["L"], _EVO_MAP)
        assert result == ["ヤドラン", "ヤドキング"]
