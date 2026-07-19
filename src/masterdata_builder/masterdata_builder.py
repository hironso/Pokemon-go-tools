"""
src/masterdata_builder/masterdata_builder.py

masterdata_builder 固有の純粋ロジック（features 層）。
ファイル I/O・Streamlit 依存なし。すべての関数は同じ入力に対して常に同じ出力を返す。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.library.expand_targets import expand_targets


@dataclass
class MemberInput:
    """ポケモン1匹の入力データ（pokedex_numbers.txt の1行分に対応）。"""

    name: str
    dex: int
    hp: int
    atk: int
    defense: int  # "def" は Python 予約語のため "defense" を使う


@dataclass
class SearchRow:
    """検索設定の1行分（iv_list_input.txt の複数行に展開される）。"""

    target_name: str
    leagues: list[str] = field(default_factory=list)
    topn: int = 1000
    targets: list[str] = field(default_factory=list)


# ============================================================
# 判定
# ============================================================


def is_solo(stages: list[list[str]]) -> bool:
    """段数が1なら単体（True）、2以上なら系統（False）。

    単体と系統では追記先ファイルと対象指定（O固定か否か）が変わる（仕様書3.2）。
    """
    return len(stages) == 1


def get_all_names(stages: list[list[str]]) -> list[str]:
    """段構造から全メンバー名を重複なし・出現順でフラットに返す。

    重複チェックや pokedex_numbers.txt への追記対象の確定に使う。
    段 → メンバーの順に走査し、初出のみを保持する。
    """
    seen: set[str] = set()
    result: list[str] = []
    for stage in stages:
        for name in stage:
            if name not in seen:
                result.append(name)
                seen.add(name)
    return result


# ============================================================
# 重複チェック
# ============================================================


def extract_evo_map_names(evo_map_staged: list[list[list[str]]]) -> set[str]:
    """evo_map_staged から全ポケモン名の set を返す。

    重複チェックで「既存 evolution_map.txt の名前」を照合するために使う。
    3重リスト（ファミリー → 段 → メンバー）をフラット化して set にまとめる。
    """
    return {name for family in evo_map_staged for stage in family for name in stage}


def find_duplicates(
    input_names: list[str],
    existing_names: set[str],
) -> list[str]:
    """入力名と既存名を照合し、重複している名前リストを返す（入力順）。

    1件でも重複があれば書き込まない（仕様書7章）。
    """
    return [n for n in input_names if n in existing_names]


# ============================================================
# フォーマット（入力 → 追記行への整形）
# ============================================================


def format_pokedex_line(member: MemberInput) -> str:
    """pokedex_numbers.txt に追記する1行（タブ区切り）を返す。

    書式: 名前<TAB>図鑑番号<TAB>HP<TAB>攻撃<TAB>防御（pokedex_numbers_spec.md）。
    """
    return f"{member.name}\t{member.dex}\t{member.hp}\t{member.atk}\t{member.defense}"


def format_evolution_line(stages: list[list[str]]) -> str:
    """evolution_map.txt に追記する1行を返す。

    カンマで段を区切り、同一段の複数メンバーはスラッシュで区切る
    （evolution_map_spec.md）。
    例: [["ラルトス"], ["キルリア"], ["サーナイト", "エルレイド"]]
        → "ラルトス,キルリア,サーナイト/エルレイド"
    """
    # 各段内のメンバーをスラッシュで連結 → 段をカンマで連結
    return ",".join("/".join(stage) for stage in stages)


def format_iv_list_lines(
    origin_name: str,
    leagues: list[str],
    topn: int,
    targets: list[str],
) -> str:
    """iv_list_input.txt に追記する1行を返す（検索設定の1行 = 出力の1行）。

    複数リーグはカンマ連結、複数対象指定もカンマ連結してまとめる（仕様書4.3）。
    書式: 起点名/リーグ/TopN/指定
    例: leagues=["S","H"], targets=["M","L"] → "起点/S,H/1000/M,L"
    """
    leagues_str = ",".join(leagues)
    targets_str = ",".join(targets)
    return f"{origin_name}/{leagues_str}/{topn}/{targets_str}"


# ============================================================
# 確認画面用
# ============================================================


def build_combined_evo_map(
    existing_evo_map_staged: list[list[list[str]]],
    new_stages: list[list[str]],
) -> list[list[list[str]]]:
    """既存 evo_map に入力中の新系統を合成したマップを返す。

    新系統はまだ evolution_map.txt に書かれていないため、
    確認画面で expand_targets を正しく動かすには既存マップとの合成が必要（仕様書6.1）。
    元のリストは変更しない（新しいリストを生成して返す）。
    """
    return existing_evo_map_staged + [new_stages]


def get_search_targets(
    origin_name: str,
    targets: list[str],
    combined_evo_map: list[list[list[str]]],
) -> list[str]:
    """O/M/L 指定を展開して実際の検索対象ポケモン名リストを返す。

    展開ロジックは library.expand_targets に完全委譲する（正は library.md）。
    """
    return expand_targets(origin_name, targets, combined_evo_map)


# ============================================================
# 検索設定の検証（Rev1.2）
# ============================================================


def _get_stage_position(name: str, stages: list[list[str]]) -> str:
    """段構造の中でのポケモンの位置を返す（エラーメッセージ生成専用）。

    Returns:
        "solo" / "first" / "middle" / "last" / "unknown"
    """
    n = len(stages)
    if n == 1 and name in stages[0]:
        return "solo"
    for i, stage in enumerate(stages):
        if name in stage:
            if i == 0:
                return "first"
            elif i == n - 1:
                return "last"
            else:
                return "middle"
    return "unknown"


def _find_stage_index(
    name: str,
    evo_map_staged: list[list[list[str]]],
) -> tuple[int, list[list[str]]] | None:
    """進化マップからポケモン名の段番号とファミリー段構造を返す。

    見つからない（進化系統に属さない単体ポケモンなど）場合は None を返す。
    """
    for family in evo_map_staged:
        for i, stage in enumerate(family):
            if name in stage:
                return i, family
    return None


def validate_search_row(
    row_idx: int,
    target_name: str,
    targets: list[str],
    stages: list[list[str]],
    combined_evo_map: list[list[list[str]]],
) -> str | None:
    """検索設定の1行が有効かを検証し、無効なら理由付きエラーメッセージを返す。

    O は常に有効。M/L は expand_targets の展開結果に「target_name より後の段の
    ポケモン」が含まれる場合のみ有効（仕様書 3.3.1）。

    Args:
        row_idx: 行番号（0始まり）。エラーメッセージの「N行目」に使う。
        target_name: 対象ポケモン名。
        targets: 対象指定リスト（O/M/L）。
        stages: 今回入力した新系統の段構造。段位置のエラーメッセージ生成に使う。
        combined_evo_map: 既存 evo_map と新系統を合成した進化マップ。

    Returns:
        有効なら None、無効ならエラーメッセージ文字列。
    """
    found = _find_stage_index(target_name, combined_evo_map)

    if found is None:
        # 進化系統に属さない単体ポケモン → O のみ有効
        no_family_invalids = [t for t in targets if t != "O"]
        if no_family_invalids:
            spec_str = "・".join(no_family_invalids)
            return (
                f"検索設定 {row_idx + 1} 行目："
                f"{target_name} は進化系統に属していないため、対象指定できるのは O のみです。"
                f"（{spec_str} は無効）"
            )
        return None

    stage_idx, family_stages = found
    # target_name の段より後にあるポケモンの集合（「展開先」候補）
    forward_members: set[str] = {
        member
        for stage in family_stages[stage_idx + 1 :]
        for member in stage
    }

    # M/L それぞれについて expand_targets を呼び、展開先に forward_members が含まれるか確認する
    invalid_specs: list[str] = []
    for t in targets:
        if t == "O":
            continue  # O は常に有効
        expanded = expand_targets(target_name, [t], combined_evo_map)
        # 展開結果に forward_members のメンバーが1つも含まれなければ無効
        if not any(member in forward_members for member in expanded):
            invalid_specs.append(t)

    if invalid_specs:
        pos = _get_stage_position(target_name, stages)
        pos_map = {
            "first": "進化前",
            "middle": "中間進化",
            "last": "最終進化",
            "solo": "単体",
            "unknown": "不明",
        }
        pos_ja = pos_map.get(pos, pos)
        spec_label_map = {"M": "中間進化（M）", "L": "最終進化（L）"}
        invalid_str = "・".join(spec_label_map.get(t, t) for t in invalid_specs)
        origin_name = family_stages[0][0] if family_stages else ""
        return (
            f"検索設定 {row_idx + 1} 行目："
            f"{target_name}（{pos_ja}）には {invalid_str} の展開先がありません。"
            f" O（本人）を指定するか、起点の {origin_name} を選んで M・L を指定してください。"
        )

    return None


def collect_all_iv_lines(search_rows: list[SearchRow]) -> list[str]:
    """複数行の検索設定から iv_list_input.txt に追記する全行を生成する。

    検索設定の行数＝出力行数（1対1）。各 SearchRow が1行に対応する（仕様書4.3）。
    """
    return [
        format_iv_list_lines(row.target_name, row.leagues, row.topn, row.targets)
        for row in search_rows
    ]
