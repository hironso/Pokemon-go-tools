"""
src/esal/masterdata_writer.py

master_data/ への書き込み層（esal）。masterdata_builder 向け。
3 ファイル（pokedex_numbers.txt・evolution_map.txt・iv_list_input.txt）の
末尾への追記を担当する。
Streamlit 依存（@st.cache_data 等）は持ち込まない。
"""

from pathlib import Path

# このファイルは src/esal/ にあるので、.parent を3回たどるとリポジトリルートになる
_REPO_ROOT = Path(__file__).parent.parent.parent
_POKEDEX_FILE = _REPO_ROOT / "master_data" / "pokedex_numbers.txt"
_EVOLUTION_FILE = _REPO_ROOT / "master_data" / "evolution_map.txt"
_IV_LIST_FILE = _REPO_ROOT / "master_data" / "iv_list_input.txt"


def _ensure_trailing_newline(filepath: Path) -> None:
    """ファイルの末尾が改行で終わっていなければ改行を1つ補う。

    既存の最終行と追記する新行が同一行に連結するのを防ぐための配慮。
    バイナリモードで末尾1バイトを読むことで、テキストモードの CRLF 変換を回避する。
    ファイルが存在しない・空の場合は何もしない。
    """
    if not filepath.exists() or filepath.stat().st_size == 0:
        return
    with open(filepath, "rb") as f:
        f.seek(-1, 2)  # ファイル末尾から1バイト前へ（SEEK_END = 2）
        last_byte = f.read(1)
    if last_byte != b"\n":
        # 末尾が改行でない場合のみ補う
        with open(filepath, "a", encoding="utf-8") as f:
            f.write("\n")


def append_pokedex_lines(lines: list[str]) -> None:
    """pokedex_numbers.txt の末尾に行リストを追記する。

    追記前に末尾改行を保証し、既存最終行との連結を防ぐ。
    """
    _ensure_trailing_newline(_POKEDEX_FILE)
    with open(_POKEDEX_FILE, "a", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def append_evolution_line(line: str) -> None:
    """evolution_map.txt の末尾に1行追記する。

    追記前に末尾改行を保証し、既存最終行との連結を防ぐ。
    """
    _ensure_trailing_newline(_EVOLUTION_FILE)
    with open(_EVOLUTION_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def append_iv_list_lines(lines: list[str]) -> None:
    """iv_list_input.txt の末尾に行リストを追記する。

    追記前に末尾改行を保証し、既存最終行との連結を防ぐ。
    """
    _ensure_trailing_newline(_IV_LIST_FILE)
    with open(_IV_LIST_FILE, "a", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
