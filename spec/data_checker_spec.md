# data_checker 仕様書

## 1. 概要

ポケモンGO関連ファイルの整合性をチェックするローカル実行ツール。
新ポケモン追加時や設定変更後に実行して、ファイル間の矛盾やフォーマット不正を検出する。

- **実行場所**: ローカルPC（Streamlitアプリではない）
- **配置場所**: `tools/data_checker.py`
- **実行方法**:
  ```bash
  cd C:\GitHub\Pokemon-go-tools\tools
  python data_checker.py
  ```
- **結果出力**: `tools/data_checker_result.txt`

---

## 2. チェック対象ファイル

| ファイル | 場所 |
|---|---|
| `pokedex_numbers.txt` | `shared/` |
| `evolution_map.txt` | `shared/` |
| `iv_list_input.txt` | `shared/` |
| `slim_cache.json` | `shared/` |
| `data_checker_support.txt` | `tools/`（抑止リスト） |

---

## 3. チェック内容

### ① pokedex_numbers.txtのチェック

- 列数が5であるか（タブ区切り）
- 数値（図鑑番号・HP・攻撃・防御種族値）が正しく変換できるか
- 1以上の値であるか
- ポケモン名の重複
- 図鑑番号の重複（フォルム違いは`data_checker_support.txt`で抑止）

### ② evolution_map.txtのチェック

- 同一行内でのポケモン名重複
- 複数ファミリーへの所属（1ポケモンが2行以上に登場）
- pokedex_numbers.txtに存在しないポケモン名

### ③ iv_list_input.txtのチェック

- フォーマットが正しいか（3〜4項目のスラッシュ区切り）
- ポケモン名がpokedex_numbers.txtに存在するか
- リーグ指定がS/H/Mであるか
- TopNが1〜4096の整数であるか
- 対象指定がO/M/Lであるか
- 完全重複行の検出
- evolution_map.txtに存在しないポケモンへのM/L指定（進化しないポケモン）

### ④ slim_cache.jsonとの整合性チェック

- iv_list_input.txtのO/M/L展開後のtarget_speciesが`slim_cache.json`に存在するか
- 存在しない場合は「slim_cache_builder.pyを再実行してください」とエラー表示

---

## 4. 抑止ファイル（data_checker_support.txt）

意図的な設定（フォルム違いによる図鑑番号重複など）をWARNINGとして出力しないよう抑止するファイル。

### フォーマット

```
## 1. evolution_map.txt に無いポケモン(進化系がないポケモン)
アローラガラガラ
カイロス
...

## 2. pokedex_numbers.txt で図鑑番号が重複するポケモン
718:ジガルデ(10％フォルム),ジガルデ(50%フォルム),ジガルデ(パーフェクトフォルム)
888:ザシアン(けんのおう),ザシアン(れきせんのゆうしゃ)
...
```

---

## 5. 実行タイミング（推奨フロー）

新ポケモン追加時の手順：

```
Step1: 各ファイル編集
  - shared/pokedex_numbers.txt に追記
  - shared/evolution_map.txt に追記（進化系統がある場合）
  - shared/iv_list_input.txt に追記

Step2: data_checker.py を実行
  → ④以外のERRORが0件であることを確認
  → ④のERROR（slim_cache未収録）はこの段階では無視してよい

Step3: slim_cache_builder.py を実行

Step4: data_checker.py を再実行
  → 全てのERRORが0件であることを確認

Step5: GitHubにpush
  → 変更した全ファイルをコミット＆push

Step6: スマホで動作確認
```

---

## 6. 出力フォーマット（data_checker_result.txt）

```
========================================
2026-05-23 23:41:21 実行結果
========================================

[ERROR] iv_list_input.txt: pokedex_numbers.txt に存在しません -> サッチムシ
[WARN ] pokedex_numbers.txt: 図鑑番号が重複しています -> 59:ウインディ,ヒスイウインディ

----------------------------------------
ERROR: 1 件
WARN : 1 件
SUPPRESS WARN: 15 件
```

---

## 7. ファイル構成

```
tools/
├── data_checker.py
├── data_checker_support.txt   ← 抑止リスト
└── data_checker_result.txt    ← 実行結果（自動生成）

shared/
├── pokedex_numbers.txt
├── evolution_map.txt
├── iv_list_input.txt
└── slim_cache.json
```
