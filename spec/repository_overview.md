# Pokemon-go-tools リポジトリ構成資料

## 1. 概要

ポケモンGOのPvP（トレーナーバトル）支援ツール群。
GitHubリポジトリ `hironso/Pokemon-go-tools` にて管理し、Streamlit Community Cloudにデプロイして運用する。

---

## 1.5 リファクタリング状況（2026-07-18〜）  ※移行中

現在、アプリを「種類で割る」新フォルダ構成（`src/`・`tests/`・`master_data/`）へ段階的に移行している。パイロットとして **`id_generator` のみ移行済み**。他アプリ（`scp_checker`・`iv_strings_generator`・`tools`）は旧構成のまま。

- **移行済み（id_generator）**：純粋ロジック＝`src/id_generator/`、共通のファイル読み込み＝`src/esal/`、テスト＝`tests/id_generator/`。データは `master_data/` を読む。エントリポイント `id_generator/app.py` は場所を変えず、`src/` を呼ぶ薄い UI 層に変更。
- **旧構成（未移行）**：他アプリは従来どおり各フォルダの `app.py` に一体で実装し、`shared/` を参照する。
- **一時的な二重管理**：`master_data/`（新）と `shared/`（旧）にデータが重複している。これは移行中の意図的な状態で、**全アプリ移行が完了したら `shared/` を削除**して解消する。

下記「2. フォルダ構成」以降は、主に旧構成（未移行アプリ）を記述している。移行が進むごとに本資料を更新する。

---
## 2. フォルダ構成

```
Pokemon-go-tools/
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
├── shared/                   # 全アプリ共通の参照ファイル
│   ├── pokedex_numbers.txt
│   ├── evolution_map.txt
│   ├── iv_list_input.txt
│   ├── slim_cache.json
│   ├── rank_cheker_input_templete.txt
│   └── iv_list_input_templete.txt
│
├── tools/                    # ローカルPC実行ツール（Streamlitアプリではない）
│   ├── slim_cache_builder.py
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
| slim_cache生成ツール | `tools/` | slim_cache.jsonを生成（ローカル実行） | `slim_cache_builder_spec.md` |
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

`tools/`フォルダ内のファイルはStreamlitアプリではなく、ローカルPCで直接実行するツール。
GitHubには含まれているが、Streamlitにはデプロイされない。

| ファイル | 実行タイミング |
|---|---|
| `slim_cache_builder.py` | ポケモン追加時・iv_list_input.txt変更時 |
| `data_checker.py` | ポケモン追加時（slim_cache生成の前後） |
| `data_checker_support.txt` | data_checker.pyの警告抑止設定（手動編集） |
| `data_checker_result.txt` | data_checker.pyの実行結果（自動生成） |
