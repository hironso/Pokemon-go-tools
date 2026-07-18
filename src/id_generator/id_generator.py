"""
src/id_generator/id_generator.py

id_generator アプリの純粋ロジック層（features）。
Streamlit・ファイル読み込みに依存しない。
データ（pokedex・evo_map）は呼び出し元から受け取る。
"""


class NoValidInputError(ValueError):
    """有効なポケモン名が1つもない場合に raise する。"""

    pass


class UnknownPokemonError(ValueError):
    """図鑑データに存在しないポケモン名が含まれる場合に raise する。"""

    def __init__(self, unknown_names: list[str]) -> None:
        self.unknown_names = unknown_names  # 呼び出し元がエラー表示に使う
        super().__init__(f"未収録のポケモン名: {unknown_names}")


def generate_ids(
    input_text: str,
    pokedex: dict[str, int],
    evo_map: list[list[str]],
) -> str:
    """
    入力テキスト（1行1ポケモン名）から図鑑番号のカンマ区切り文字列を生成する。

    処理の流れ：
      1. 空行・# コメント行を除去して有効な名前リストを作る。
      2. 有効名が1つもなければ NoValidInputError を raise する。
      3. 図鑑データに存在しない名前があれば UnknownPokemonError を raise する
         （一部だけ処理して残りを返すことはしない）。
      4. 各名前の進化ファミリーを展開し、図鑑番号を収集・重複除去・昇順ソートする。
      5. カンマ区切りの文字列を返す。

    Args:
        input_text: テキストエリアの生の入力（改行区切り）。
        pokedex: ポケモン名 → 図鑑番号の辞書（esal から渡す）。
        evo_map: 進化ファミリーのリスト（esal から渡す）。

    Returns:
        "1,2,3,4,5,6" のような図鑑番号のカンマ区切り文字列。

    Raises:
        NoValidInputError: 有効なポケモン名が1つもない。
        UnknownPokemonError: 図鑑データに存在しない名前がある（unknown_names に格納）。
    """
    # 空行・コメント行を除去して有効名だけ残す
    names = [
        line.strip()
        for line in input_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    if not names:
        raise NoValidInputError("有効なポケモン名がありません。入力を確認してください。")

    # 未収録名をすべて洗い出してから raise する（一部だけ処理しない）
    unknown = [name for name in names if name not in pokedex]
    if unknown:
        raise UnknownPokemonError(unknown)

    # 各名前のファミリーを展開して図鑑番号を収集する（set で自動的に重複除去）
    dex_set: set[int] = set()
    for name in names:
        family = _find_family(name, evo_map)
        for member in family:
            if member in pokedex:
                dex_set.add(pokedex[member])

    return ",".join(str(d) for d in sorted(dex_set))


def _find_family(name: str, evo_map: list[list[str]]) -> list[str]:
    """
    evo_map の中から name が属するファミリーを返す。
    どのファミリーにも属さない場合は [name] を返す（その名前単体を1ファミリーとして扱う）。
    """
    for family in evo_map:
        if name in family:
            return family
    return [name]
