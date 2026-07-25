"""
src/esal/scp_checker_reader.py

SCPランクチェッカー用のファイル読み込み層（esal）。
master_data/ 配下のファイルを読み込み、純粋なデータ構造として返す。
Streamlit 依存（@st.cache_data 等）は持ち込まない。
"""

from pathlib import Path

# このファイルは src/esal/ にあるので、.parent を3回たどるとリポジトリルートになる
_REPO_ROOT = Path(__file__).parent.parent.parent
_TEMPLATE_FILE = _REPO_ROOT / "master_data" / "rank_cheker_input_templete.txt"


def load_rank_checker_template() -> bytes:
    """
    rank_cheker_input_templete.txt を読み込み、バイト列で返す。

    ファイルが見つからない場合は FileNotFoundError を raise する。
    エラーメッセージは仕様書 2 章の起動時エラー文言に合わせた形式とする。
    """
    if not _TEMPLATE_FILE.exists():
        raise FileNotFoundError(
            f"rank_cheker_input_templete.txt が見つかりません: {_TEMPLATE_FILE}"
        )
    return _TEMPLATE_FILE.read_bytes()
