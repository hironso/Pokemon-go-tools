"""
src/esal/iv_strings_reader.py

データファイルの読み込み層（esal）。iv_strings_generator 向け。
master_data/ 配下のファイルを読み込み、純粋なデータ構造として返す。
Streamlit 依存（@st.cache_data 等）は持ち込まない。
"""

from __future__ import annotations

import json
from pathlib import Path

# このファイルは src/esal/ にあるので、.parent を3回たどるとリポジトリルートになる
_REPO_ROOT = Path(__file__).parent.parent.parent
_EVOLUTION_FILE = _REPO_ROOT / "master_data" / "evolution_map.txt"
_SLIM_CACHE_FILE = _REPO_ROOT / "master_data" / "slim_cache.json"
_IV_LIST_FILE = _REPO_ROOT / "master_data" / "iv_list_input.txt"


def load_evolution_map_staged() -> list[list[list[str]]]:
    """
    evolution_map.txt を読み込み、進化ファミリーの段構造を保ったまま返す。

    書式: ポケモン名をカンマで「段」区切り、スラッシュで「同一段の分岐」区切り。
    返り値: ファミリーのリスト。各ファミリーは [段0のポケモンリスト, 段1のポケモンリスト, ...]
    例: "ラルトス,キルリア,サーナイト/エルレイド"
        → [["ラルトス"], ["キルリア"], ["サーナイト", "エルレイド"]]

    iv_strings_generator では O/M/L 展開に段番号・分岐先の情報が必要なため、
    id_generator の load_evolution_map（フラット化済み）とは別にこちらを使う。
    """
    evo_map: list[list[list[str]]] = []
    with open(_EVOLUTION_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # カンマで「段」を分割する（例: "ラルトス,キルリア,サーナイト/エルレイド"）
            stage_tokens = [tok.strip() for tok in line.split(",") if tok.strip()]
            stages: list[list[str]] = []
            for tok in stage_tokens:
                # スラッシュで「同一段の分岐先」を分割する
                members = [m.strip() for m in tok.split("/") if m.strip()]
                if members:
                    stages.append(members)
            if stages:
                evo_map.append(stages)
    return evo_map


def load_iv_list_input_raw() -> list[str]:
    """
    iv_list_input.txt を読み込み、空行・# コメント行を除いた生テキスト行リストを返す。

    行のトリムのみ行い、パース（フィールド分割・バリデーション）は呼び出し元（features 層）に任せる。
    slim_cache_builder の parse_input などが対象。
    """
    lines: list[str] = []
    with open(_IV_LIST_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
    return lines


def load_slim_cache() -> dict[str, dict]:  # type: ignore[type-arg]
    """
    slim_cache.json を読み込み、ポケモン名 → キャッシュエントリの辞書を返す。

    返り値: {"ポケモン名": {"name": ..., "dex": ..., "leagues": {...}}, ...}
    leagues の構造は slim_cache_builder_spec.md を参照。
    """
    with open(_SLIM_CACHE_FILE, encoding="utf-8") as f:
        cache: dict[str, object] = json.load(f)
    pokemon_list = cache.get("pokemon", [])
    assert isinstance(pokemon_list, list)
    return {entry["name"]: entry for entry in pokemon_list}
