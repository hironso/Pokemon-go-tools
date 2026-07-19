"""
src/esal/slim_cache_writer.py

slim_cache.json の書き込み層（esal）。
slim_cache_builder が生成した JSON オブジェクトをファイルへ保存する。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).parent.parent.parent
_SLIM_CACHE_FILE = _REPO_ROOT / "master_data" / "slim_cache.json"


def write_slim_cache(cache_object: dict[str, Any]) -> None:
    """
    slim_cache.json を上書き保存する。

    JSON は ensure_ascii=False・separators=(",",":")（空白なし）で書き出す。
    既存ファイルがあれば上書きする。
    """
    with open(_SLIM_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_object, f, ensure_ascii=False, separators=(",", ":"))
