# slim_cache 仕様書

## 1. 概要

`slim_cache.json` は、SCPランキングを計算済みの軽量キャッシュファイル。
`scp_cache.json`（約704MB）の代替として、`iv_list_input.txt` で参照されるポケモン×リーグ×TopN件のデータのみを抽出した軽量版（約4MB）である。

- **配置場所**: `master_data/slim_cache.json`（移行前の旧構成では `shared/`）
- **文字コード**: UTF-8
- **生成方法**: `tools/slim_cache_builder.py`（ローカル実行）で生成する。
- **参照するアプリ・ツール**: iv_strings_generator / data_checker

---

## 2. ファイル形式の正

> **`slim_cache.json` のファイル形式（JSON のキー構造・各フィールドの意味・entries の CSV 形式など）の正は、生成ツールの仕様書 `slim_cache_builder_spec.md` とする。**

このファイルは `slim_cache_builder.py` が生成する成果物であり、その形式は生成ツールの仕様と一体である。二重管理を避けるため、本書では形式を再掲せず、`slim_cache_builder_spec.md`（特に「slim_cache.json のフォーマット」の章）を参照する。

参考までに、形式の要点のみ記す（詳細は上記を正とする）。

- トップレベルに `meta`（メタ情報）と `pokemon`（配列）を持つ。
- `pokemon` の各要素は `name`・`dex`・`leagues` を持つ。
- `leagues` はリーグ記号（S/H/M）ごとに `cp_cap`・`topn`・`entries` を持つ。
- `entries` は `"rank,atk_bucket,def_bucket,hp_bucket,atk_real"` 形式の文字列の配列。

---

## 3. 更新が必要なタイミング

- `pokedex_numbers.txt` に新ポケモンを追加したとき。
- `iv_list_input.txt` に新しいポケモン・リーグを追加したとき。

更新手順（data_checker との実行順など）は `repository_overview.md` の「データ更新フロー」に従う。

---

## 4. 関連文書

- `slim_cache_builder_spec.md` … 生成ツールの仕様。**本ファイルの形式の正**。
- `repository_overview.md` … データ更新フロー・依存関係。
- 各参照アプリの仕様書 … このデータの使い方。
