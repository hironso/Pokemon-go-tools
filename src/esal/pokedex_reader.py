"""
src/esal/pokedex_reader.py

データファイルの読み込み層（esal）。
master_data/ 配下のファイルを読み込み、純粋なデータ構造として返す。
Streamlit 依存（@st.cache_data 等）は持ち込まない。
"""

from pathlib import Path

# このファイルは src/esal/ にあるので、.parent を3回たどるとリポジトリルートになる
_REPO_ROOT = Path(__file__).parent.parent.parent
_POKEDEX_FILE = _REPO_ROOT / "master_data" / "pokedex_numbers.txt"
_EVOLUTION_FILE = _REPO_ROOT / "master_data" / "evolution_map.txt"


def load_pokedex() -> dict[str, int]:
    """
    pokedex_numbers.txt を読み込み、ポケモン名 → 図鑑番号 の辞書を返す。

    書式（タブ区切り）：<名前>\\t<図鑑番号>\\t...（3列目以降は無視）
    空行・# コメント行はスキップ。図鑑番号が整数でない行もスキップ。
    """
    pokedex: dict[str, int] = {}
    with open(_POKEDEX_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("\t")]
            if len(parts) < 2:
                continue
            try:
                pokedex[parts[0]] = int(parts[1])
            except ValueError:
                continue
    return pokedex


def load_pokedex_full() -> dict[str, dict[str, int]]:
    """
    pokedex_numbers.txt を読み込み、ポケモン名 → 種族値辞書 の辞書を返す。

    書式（タブ区切り）：<名前>\\t<図鑑番号>\\t<HP>\\t<攻撃>\\t<防御>
    空行・# コメント行はスキップ。不正な行は ValueError を raise する。
    slim_cache_builder など、種族値（HP・攻撃・防御）が必要な用途向け。
    既存の load_pokedex()（図鑑番号のみ）とは返り値の形式が異なる。
    """
    pokedex: dict[str, dict[str, int]] = {}
    with open(_POKEDEX_FILE, encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("\t")]
            if len(parts) < 5:
                raise ValueError(
                    f"pokedex_numbers.txt {line_number}行目: 列数不足（5列必要）"
                )
            try:
                pokedex[parts[0]] = {
                    "dex": int(parts[1]),
                    "hp_base": int(parts[2]),
                    "atk_base": int(parts[3]),
                    "def_base": int(parts[4]),
                }
            except ValueError:
                raise ValueError(
                    f"pokedex_numbers.txt {line_number}行目: 数値変換失敗"
                )
    return pokedex


def load_evolution_map() -> list[list[str]]:
    """
    evolution_map.txt を読み込み、進化ファミリーのリストを返す。

    書式：ポケモン名をカンマ区切り。「/」はフォルム違い（例：「ヒスイのすがた/通常のすがた」）
    を同一ファミリーとして展開する。空行・# コメント行はスキップ。重複エントリは除去する。

    返り値の各要素がひとつの進化ファミリー（例：["フシギダネ", "フシギソウ", "フシギバナ"]）。
    """
    evo_map: list[list[str]] = []
    with open(_EVOLUTION_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            tokens = [p.strip() for p in line.split(",") if p.strip()]
            # "/" で区切られた表記を展開してフォルム違いも同ファミリーに含める
            expanded: list[str] = []
            for tok in tokens:
                if "/" in tok:
                    expanded.extend(x.strip() for x in tok.split("/") if x.strip())
                else:
                    expanded.append(tok)
            # 順序を保ちつつ重複を除去する
            seen: set[str] = set()
            family: list[str] = []
            for name in expanded:
                if name not in seen:
                    family.append(name)
                    seen.add(name)
            if family:
                evo_map.append(family)
    return evo_map
