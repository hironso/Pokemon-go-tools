# Pokemon-go-tools リポジトリ構成資料

## 1. 概要

ポケモンGOのPvP（トレーナーバトル）支援ツール群。
GitHubリポジトリ `hironso/Pokemon-go-tools` にて管理し、Streamlit Community Cloudにデプロイして運用する。

---

## 1.5 リファクタリング状況（2026-07-18〜）  ※移行中

現在、アプリを「種類で割る」新フォルダ構成（`src/`・`tests/`・`master_data/`）へ段階的に移行している。**`id_generator` と `iv_strings_generator` が移行済み**。他アプリ（`scp_checker`・`tools`）は旧構成のまま。

- **移行済み（id_generator）**：純粋ロジック＝`src/id_generator/`、ファイル読み込み＝`src/esal/pokedex_reader.py`、テスト＝`tests/id_generator/`。データは `master_data/` を読む。エントリポイント `id_generator/app.py` は場所を変えず、`src/` を呼ぶ薄い UI 層に変更。
- **移行済み（iv_strings_generator）**：純粋ロジック＝`src/iv_strings_generator/`、ファイル読み込み＝`src/esal/iv_strings_reader.py`（進化マップ段構造・slim_cache）および `src/esal/pokedex_reader.py`（図鑑番号）、テスト＝`tests/iv_strings_generator/`。データは `master_data/`（`pokedex_numbers.txt`・`evolution_map.txt`・`slim_cache.json`・`iv_list_input_templete.txt`）を読む。エントリポイント `iv_strings_generator/app.py` は場所を変えず薄い UI 層に変更。
- **新規追加（masterdata_builder）**：`master_data/` の各ファイルへ新規ポケモンを追記するローカルツール（Streamlit）。純粋ロジック＝`src/masterdata_builder/`、ファイル読み書き＝`src/esal/masterdata_writer.py`（書き込み新設）および既存の `pokedex_reader.py`・`iv_strings_reader.py`（読み込み）、テスト＝`tests/masterdata_builder/`。エントリポイント `masterdata_builder/app.py`。Streamlit Community Cloud にはデプロイしない（ローカル実行専用）。
- **共通処理層（library）新設**：`src/library/` に複数アプリ・ツールから呼ばれる純粋関数を集約。現在のメンバー：`expand_targets`（O/M/L 展開ロジック）。テストは `tests/library/`。
- **esal の役割拡張**：`src/esal/` は読み込み専用層から、ファイルとの**読み書き両方**の境界層に拡張された（`masterdata_writer.py` の追加による）。
- **移行済み（slim_cache_builder）**：実行部＝`slim_cache_builder/slim_cache_builder.py`（リポジトリ直下の専用フォルダ）、純粋ロジック＝`src/slim_cache_builder/`（IV/CP/SCP計算・slim変換・iv_list_inputパース）、ファイル読み込み＝`src/esal/pokedex_reader.py`（`load_pokedex_full`）・`src/esal/iv_strings_reader.py`（`load_evolution_map_staged`・`load_iv_list_input_raw`）、書き込み＝`src/esal/slim_cache_writer.py`（新設）、テスト＝`tests/slim_cache_builder/`。旧 `tools/slim_cache_builder.py` は削除済み。実行は `python slim_cache_builder/slim_cache_builder.py`。
- **旧構成（未移行）**：`scp_checker` は従来どおり各フォルダの `app.py` に一体で実装し、`shared/` を参照する。
- **一時的な二重管理**：`master_data/`（新）と `shared/`（旧）にデータが重複している。これは移行中の意図的な状態で、**全アプリ移行が完了したら `shared/` を削除**して解消する。

下記「2. フォルダ構成」以降は、主に旧構成（未移行アプリ）を記述している。移行が進むごとに本資料を更新する。

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
│   │   └── slim_cache_writer.py    # slim_cache.json 書き込み（slim_cache_builder 向け）
│   ├── library/              # 共通処理層（2か所以上から使われる純粋関数）
│   │   ├── __init__.py
│   │   └── expand_targets.py
│   ├── id_generator/         # id_generator 機能層
│   │   └── id_generator.py
│   ├── iv_strings_generator/ # iv_strings_generator 機能層
│   │   └── iv_strings_generator.py
│   ├── masterdata_builder/   # masterdata_builder 機能層
│   │   └── masterdata_builder.py
│   └── slim_cache_builder/   # slim_cache_builder 機能層（IV/CP/SCP計算・slim変換）
│       └── slim_cache_builder.py
│
├── tests/
│   ├── id_generator/
│   ├── iv_strings_generator/
│   ├── library/              # library 層のテスト
│   ├── masterdata_builder/   # masterdata_builder 機能層のテスト
│   └── slim_cache_builder/   # slim_cache_builder 機能層のテスト
│
├── master_data/              # データファイル（shared/ からの移行先）
│   ├── pokedex_numbers.txt
│   ├── evolution_map.txt
│   ├── iv_list_input.txt
│   ├── slim_cache.json
│   └── iv_list_input_templete.txt
│
├── shared/                   # 旧構成（移行完了後に削除予定）
│   ├── pokedex_numbers.txt
│   ├── evolution_map.txt
│   ├── iv_list_input.txt
│   ├── slim_cache.json
│   ├── rank_cheker_input_templete.txt
│   └── iv_list_input_templete.txt
│
├── tools/                    # ローカルPC実行ツール（slim_cache_builder は移行済み）
│   ├── data_checker.py
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
| 整合性チェックツール | `tools/` | ファイル間の整合性をチェック（ローカル実行） | `data_checker_spec.md` |

---

## 4. 共通ファイルの説明

| ファイル | 用途 | 参照アプリ |
|---|---|---|
| `pokedex_numbers.txt` | ポケモンの種族値定義（図鑑番号・HP・攻撃・防御） | scp_checker / iv_strings_generator / id_generator / slim_cache_builder / data_checker |
| `evolution_map.txt` | 進化ファミリー定義（O/M/L展開に使用） | iv_strings_generator / id_generator / slim_cache_builder / data_checker |
| `iv_list_input.txt` | IVサーチ対象のポケモン・リーグ・TopN設定 | iv_strings_generator / slim_cache_builder / data_checker |
| `slim_cache.json` | SCPランキング計算済みキャッシュ（軽量版） | iv_strings_generator / data_checker |
| `rank_cheker_input_templete.txt` | scp_checker用入力ファイルのテンプレート | scp_checker（ダウンロード提供） |
| `iv_list_input_templete.txt` | iv_strings_generator用入力ファイルのテンプレート | iv_strings_generator（ダウンロード提供） |

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
```

---

## 6. データ更新フロー

### 新ポケモン追加時

```
① shared/pokedex_numbers.txt に追記
② shared/evolution_map.txt に追記（進化系統がある場合）
③ shared/iv_list_input.txt に追記
    ↓
④ tools/data_checker.py を実行
   → ④のslim_cache未収録エラーは無視してOK
   → それ以外のERRORが0件であることを確認
    ↓
⑤ tools/slim_cache_builder.py を実行
   → shared/slim_cache.json が更新される
    ↓
⑥ tools/data_checker.py を再実行
   → 全ERRORが0件であることを確認
    ↓
⑦ GitHubにpush（変更した全ファイルをコミット）
    ↓
⑧ Streamlitが自動再デプロイ（1〜2分）
    ↓
⑨ スマホで動作確認
```

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

### tools/

| ファイル | 実行タイミング |
|---|---|
| `data_checker.py` | ポケモン追加時（slim_cache生成の前後） |
| `data_checker_support.txt` | data_checker.pyの警告抑止設定（手動編集） |
| `data_checker_result.txt` | data_checker.pyの実行結果（自動生成） |
