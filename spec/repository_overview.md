# Pokemon-go-tools リポジトリ構成資料

## 1. 概要

ポケモンGOのPvP（トレーナーバトル）支援ツール群。
GitHubリポジトリ `hironso/Pokemon-go-tools` にて管理し、Streamlit Community Cloudにデプロイして運用する。

---

## 1.5 リファクタリング状況（2026-07-18〜）  ※移行完了

アプリを「種類で割る」新フォルダ構成（`src/`・`tests/`・`master_data/`）へ移行済み。**`id_generator`・`iv_strings_generator`・`masterdata_builder`・`slim_cache_builder`・`scp_checker` がすべて移行済み。**

- **移行済み（id_generator）**：純粋ロジック＝`src/id_generator/`、ファイル読み込み＝`src/esal/pokedex_reader.py`、テスト＝`tests/id_generator/`。データは `master_data/` を読む。エントリポイント `id_generator/app.py` は場所を変えず、`src/` を呼ぶ薄い UI 層に変更。
- **移行済み（iv_strings_generator）**：純粋ロジック＝`src/iv_strings_generator/`、ファイル読み込み＝`src/esal/iv_strings_reader.py`（進化マップ段構造・slim_cache）および `src/esal/pokedex_reader.py`（図鑑番号）、テスト＝`tests/iv_strings_generator/`。データは `master_data/`（`pokedex_numbers.txt`・`evolution_map.txt`・`slim_cache.json`・`iv_list_input_templete.txt`）を読む。エントリポイント `iv_strings_generator/app.py` は場所を変えず薄い UI 層に変更。
- **新規追加（masterdata_builder）**：`master_data/` の各ファイルへ新規ポケモンを追記するローカルツール（Streamlit）。純粋ロジック＝`src/masterdata_builder/`、ファイル読み書き＝`src/esal/masterdata_writer.py`（書き込み新設）および既存の `pokedex_reader.py`・`iv_strings_reader.py`（読み込み）、テスト＝`tests/masterdata_builder/`。エントリポイント `masterdata_builder/app.py`。Streamlit Community Cloud にはデプロイしない（ローカル実行専用）。**`master_data/` の3ファイル（pokedex_numbers.txt・evolution_map.txt・iv_list_input.txt）は、今後このツール経由でのみ更新する（手動でのテキスト直接編集はしない）方針。**
- **共通処理層（library）新設**：`src/library/` に複数アプリ・ツールから呼ばれる純粋関数を集約。現在のメンバー：`expand_targets`（O/M/L 展開ロジック）。テストは `tests/library/`。
- **esal の役割拡張**：`src/esal/` は読み込み専用層から、ファイルとの**読み書き両方**の境界層に拡張された（`masterdata_writer.py` の追加による）。
- **移行済み（slim_cache_builder）**：実行部＝`slim_cache_builder/slim_cache_builder.py`（リポジトリ直下の専用フォルダ）、純粋ロジック＝`src/slim_cache_builder/`（IV/CP/SCP計算・slim変換・iv_list_inputパース）、ファイル読み込み＝`src/esal/pokedex_reader.py`（`load_pokedex_full`）・`src/esal/iv_strings_reader.py`（`load_evolution_map_staged`・`load_iv_list_input_raw`）、書き込み＝`src/esal/slim_cache_writer.py`（新設）、テスト＝`tests/slim_cache_builder/`。旧 `tools/slim_cache_builder.py` は削除済み。実行は `python slim_cache_builder/slim_cache_builder.py`。
- **移行済み（scp_checker）**：純粋ロジック＝`src/scp_checker/`（SCP計算・タグ判定・出力フォーマット・一括置換）、ファイル読み込み＝`src/esal/pokedex_reader.py`（`load_pokedex_full`）・`src/esal/scp_checker_reader.py`（テンプレートファイル。新設）、テスト＝`tests/scp_checker/`。データは `master_data/`（`pokedex_numbers.txt`・`rank_cheker_input_templete.txt`）を読む。エントリポイント `scp_checker/app.py` は場所を変えず薄い UI 層に変更。
- **`shared/` 削除済み（2026-07-25）**：全アプリの移行完了に伴い、旧構成の共有データ置き場 `shared/` はリポジトリから削除した。全アプリが `master_data/` を読む。
- **`tools/data_checker.py` は現在使用不可（対応未着手）**：`shared/` のパスを直接参照する実装のままのため、`shared/` 削除により動作しない。今後 `master_data/` の3ファイルは masterdata_builder 経由でのみ作成される前提のため、data_checker が担っていたチェックのうち一部（pokedex/evolution_map の全体整合性監査、iv_list_input.txt の slim_cache 未収録チェック）を masterdata_builder に統合するかどうかは**今後の検討課題**（8章参照）。急ぎの対応ではない。

下記「2. フォルダ構成」以降は、現在の構成を記述している。

---
## 2. フォルダ構成

```
Pokemon-go-tools/
├── masterdata_builder/       # マスターデータ登録ツール（ローカル実行 Streamlit アプリ）
│   └── app.py
│
├── slim_cache_builder/       # slim_cache 生成ツール（ローカル実行。薄い実行部）
│   └── slim_cache_builder.py
│
├── scp_checker/              # SCPランクチェッカー（Streamlitアプリ）
│   ├── app.py
│   └── requirements.txt
│
├── iv_strings_generator/     # IVサーチ文字列ジェネレーター（Streamlitアプリ）
│   ├── app.py
│   └── requirements.txt
│
├── id_generator/             # ポケモンID生成ツール（Streamlitアプリ）
│   ├── app.py
│   └── requirements.txt
│
├── src/
│   ├── esal/                 # ファイル読み書き層（master_data/ との I/O を集約）
│   │   ├── __init__.py
│   │   ├── pokedex_reader.py       # load_pokedex / load_pokedex_full / load_evolution_map
│   │   ├── iv_strings_reader.py    # load_evolution_map_staged / load_slim_cache / load_iv_list_input_raw
│   │   ├── masterdata_writer.py    # 追記（書き込み）関数（masterdata_builder 向け）
│   │   ├── slim_cache_writer.py    # slim_cache.json 書き込み（slim_cache_builder 向け）
│   │   └── scp_checker_reader.py   # テンプレートファイル読み込み（scp_checker 向け）
│   ├── library/              # 共通処理層（2か所以上から使われる純粋関数）
│   │   ├── __init__.py
│   │   └── expand_targets.py
│   ├── id_generator/         # id_generator 機能層
│   │   └── id_generator.py
│   ├── iv_strings_generator/ # iv_strings_generator 機能層
│   │   └── iv_strings_generator.py
│   ├── masterdata_builder/   # masterdata_builder 機能層
│   │   └── masterdata_builder.py
│   ├── slim_cache_builder/   # slim_cache_builder 機能層（IV/CP/SCP計算・slim変換）
│   │   └── slim_cache_builder.py
│   └── scp_checker/          # scp_checker 機能層（SCP計算・タグ判定・出力フォーマット等）
│       └── scp_checker.py
│
├── tests/
│   ├── id_generator/
│   ├── iv_strings_generator/
│   ├── library/              # library 層のテスト
│   ├── masterdata_builder/   # masterdata_builder 機能層のテスト
│   ├── slim_cache_builder/   # slim_cache_builder 機能層のテスト
│   └── scp_checker/          # scp_checker 機能層のテスト
│
├── master_data/              # データファイル（masterdata_builder 経由でのみ更新）
│   ├── pokedex_numbers.txt
│   ├── evolution_map.txt
│   ├── iv_list_input.txt
│   ├── slim_cache.json
│   ├── iv_list_input_templete.txt
│   └── rank_cheker_input_templete.txt
│
├── tools/                    # ローカルPC実行ツール（slim_cache_builder は移行済み）
│   ├── data_checker.py       # ※現在使用不可（shared/ 参照のまま。1.5章参照）
│   ├── data_checker_support.txt
│   └── data_checker_result.txt
│
└── README.md
```

---

## 3. アプリ一覧

| アプリ | フォルダ | 用途 | 仕様書 |
|---|---|---|---|
| SCPランクチェッカー | `scp_checker/` | 手持ち個体のSCPランクとおすすめタグを計算 | `scp_checker_spec.md` |
| IVサーチ文字列ジェネレーター | `iv_strings_generator/` | ボックス整理用の検索キーワードを生成 | `iv_strings_generator_spec.md` |
| ポケモンID生成ツール | `id_generator/` | ポケモン名から図鑑番号リストを生成 | `id_generator_spec.md` |
| マスターデータ登録ツール | `masterdata_builder/` | 新規ポケモンを master_data/ の各ファイルへ追記（ローカル実行） | `masterdata_builder_spec.md` |
| slim_cache生成ツール | `slim_cache_builder/` | slim_cache.jsonを生成（ローカル実行） | `slim_cache_builder_spec.md` |
| 整合性チェックツール（※現在使用不可） | `tools/` | ファイル間の整合性をチェック（ローカル実行） | `data_checker_spec.md` |

---

## 4. 共通ファイルの説明

| ファイル | 用途 | 参照アプリ |
|---|---|---|
| `pokedex_numbers.txt` | ポケモンの種族値定義（図鑑番号・HP・攻撃・防御） | scp_checker / iv_strings_generator / id_generator / slim_cache_builder / masterdata_builder |
| `evolution_map.txt` | 進化ファミリー定義（O/M/L展開に使用） | iv_strings_generator / id_generator / slim_cache_builder / masterdata_builder |
| `iv_list_input.txt` | IVサーチ対象のポケモン・リーグ・TopN設定 | iv_strings_generator / slim_cache_builder / masterdata_builder |
| `slim_cache.json` | SCPランキング計算済みキャッシュ（軽量版） | iv_strings_generator |
| `rank_cheker_input_templete.txt` | scp_checker用入力ファイルのテンプレート | scp_checker（ダウンロード提供） |
| `iv_list_input_templete.txt` | iv_strings_generator用入力ファイルのテンプレート | iv_strings_generator（ダウンロード提供） |

`data_checker`（`tools/`）は上記ファイルを参照する実装だが、現在 `shared/` パス参照のまま動作しないため、参照アプリの一覧からは外している（1.5章参照）。

---

## 5. ファイル依存関係

```
pokedex_numbers.txt ──────────────────────────────────────┐
                                                           ├──► scp_checker
                                                           │
evolution_map.txt ─────────────────────────────────────┐  │
                                                        │  │
iv_list_input.txt ──────────────────────────────────┐  │  │
                                                     │  │  │
                                                     ▼  ▼  │
                                            slim_cache_builder.py
                                                     │
                                                     ▼
pokedex_numbers.txt ──┐                      slim_cache.json
evolution_map.txt ────┼──► iv_strings_generator ◄───┘
iv_list_input.txt ────┘

pokedex_numbers.txt ──┐
evolution_map.txt ────┼──► id_generator

pokedex_numbers.txt ──┐
evolution_map.txt ────┼──► masterdata_builder（追記）
iv_list_input.txt ────┘
```

---

## 6. データ更新フロー

### 新ポケモン追加時

`master_data/` の3ファイル（pokedex_numbers.txt・evolution_map.txt・iv_list_input.txt）は、**masterdata_builder経由でのみ更新する**（手動でのテキスト直接編集はしない）。

```
① masterdata_builder/app.py を起動し、新規ポケモンの種族値・進化系統・
   検索設定（リーグ・TopN・O/M/L）を入力
    ↓
② 確認画面で照合結果（既存との重複・展開結果）を確認し、OKで master_data/ へ追記
    ↓
③ slim_cache_builder/slim_cache_builder.py を実行
   → master_data/slim_cache.json が更新される
    ↓
④ GitHubにpush（変更した master_data/ の全ファイルをコミット）
    ↓
⑤ Streamlitが自動再デプロイ（1〜2分）
    ↓
⑥ スマホで動作確認
```

※旧フロー（`data_checker.py`によるチェックを挟む手順）は、`shared/`削除に伴い使用不可。data_checker が担っていたチェック（pokedex/evolution_mapの全体整合性監査・iv_list_input.txtのslim_cache未収録チェック）をmasterdata_builderへ統合するかは今後の検討課題（1.5章・8章参照）。

### アプリのコード修正時

```
① VS Codeでapp.pyを修正
    ↓
② GitHubにコミット＆push
    ↓
③ Streamlitが自動再デプロイ（1〜2分）
```

---

## 7. デプロイ情報

| アプリ | デプロイ先 | メインファイルパス |
|---|---|---|
| SCPランクチェッカー | Streamlit Community Cloud | `scp_checker/app.py` |
| IVサーチ文字列ジェネレーター | Streamlit Community Cloud | `iv_strings_generator/app.py` |
| ポケモンID生成ツール | Streamlit Community Cloud | `id_generator/app.py` |

- リポジトリ：`hironso/Pokemon-go-tools`（Public）
- ブランチ：`main`
- GitHubへのpushで自動再デプロイ

---

## 8. ローカル実行ツール

Streamlitアプリではなく、ローカルPCで直接実行するツール。GitHubには含まれているが、Streamlitにはデプロイされない。

### slim_cache_builder/

| ファイル | 実行タイミング |
|---|---|
| `slim_cache_builder/slim_cache_builder.py` | ポケモン追加時・iv_list_input.txt変更時 |

実行方法: `python slim_cache_builder/slim_cache_builder.py`（プロジェクトルートから）

### tools/（※現在使用不可）

| ファイル | 状態 |
|---|---|
| `data_checker.py` | `shared/` のパスを直接参照する実装のまま。`shared/` 削除（2026-07-25）により動作しない。急ぎの修正は不要（masterdata_builder経由の作成に一本化したため、data_checkerが検出していた入力ミスの多くは構造的に発生しにくくなっている）。ただし、pokedex/evolution_mapの全体整合性監査・iv_list_input.txtのslim_cache未収録チェックは、まだmasterdata_builderに引き継がれていない機能であり、今後の検討課題として残る。 |
| `data_checker_support.txt` | data_checker.pyの警告抑止設定（手動編集）。data_checker自体が使用不可のため、現在は参照されない。 |
| `data_checker_result.txt` | data_checker.pyの実行結果（自動生成）。同上。 |
