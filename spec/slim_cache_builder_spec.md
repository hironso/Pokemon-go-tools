# slim_cache_builder 仕様書

## 改訂履歴

| Rev | 日付 | 主な変更点 |
|---|---|---|
| 1.0 | （初版） | 変更前の仕様。進化マップを独自に読み込み、O/M/L 展開もツール内に独自実装していた版。 |
| 1.1 | 2026-07-18 | 分岐進化の未収録バグに対応。進化マップの読み込みを esal（`load_evolution_map_staged`、段構造保持）に集約し、O/M/L 展開を library（`expand_targets`）に共通化した。ツール独自の「分岐を潰して 1 次元化し位置で展開する」方式は廃止。入出力パスを `shared/` から `master_data/` に統一。ツールが `src/`（esal・library）を参照する構成に変更。 |

---

## 1. 概要

`iv_strings_generator`アプリが参照する`slim_cache.json`を生成するローカル実行ツール。
`scp_cache.json`（704MB）の代替として、必要なポケモン×リーグ×TopN件のデータのみを抽出した軽量キャッシュ（約4MB）を生成する。

- **実行場所**: ローカルPC（Streamlitアプリではない）
- **配置場所**: `tools/slim_cache_builder.py`
- **実行方法**:
  ```bash
  cd C:\GitHub\Pokemon-go-tools\tools
  python slim_cache_builder.py
  ```

> **本改訂（Rev1.1）で変わるのは「対象ポケモン×リーグの特定」（4章 Step1）だけである。** 全IV計算（Step2）・slim 形式への変換（Step3）・出力フォーマット（5章）は変更しない。

---

## 2. 入力ファイル

| ファイル | 場所 | 用途 |
|---|---|---|
| `pokedex_numbers.txt` | `master_data/` | ポケモンの種族値取得 |
| `evolution_map.txt` | `master_data/` | O/M/L 展開のためのファミリー特定（読み込みは esal、展開は library） |
| `iv_list_input.txt` | `master_data/` | 計算対象のポケモン×リーグ×TopN を決定 |

> 参照データファイルのファイル形式の正は、それぞれのデータファイル spec とする（`pokedex_numbers_spec.md`・`evolution_map_spec.md`）。本書では形式を規定しない。

---

## 3. 出力ファイル

| ファイル | 場所 |
|---|---|
| `slim_cache.json` | `master_data/` |

---

## 4. 処理ロジック

### Step1：対象ポケモン×リーグの特定

`iv_list_input.txt`を読み込み、O/M/L 展開を行って計算対象を確定する。

- **進化マップの読み込み**：`evolution_map.txt` は **esal の `load_evolution_map_staged` を用いて段構造を保持したまま読み込む**（段のリスト、各段は同一段メンバー名のリスト）。カンマ＝段、スラッシュ＝同一段の分岐。
- **O/M/L 展開**：各入力行のポケモン名・対象指定（O/M/L）を、**library の `expand_targets` を用いて対象ポケモン種名リストへ展開する**。展開ルール（O＝本人／L＝最終段の全枝／M＝中間段〈3段のみ、2段は L と同義〉／未収録は本人）の正は `library.md`（3章）とする。本書では展開ルールを独自に定義しない。
- 同じポケモン×リーグが複数行ある場合は**最大TopN**を採用する。
- 計算対象は iv_list_input.txt で参照されるポケモン×リーグのみ（全ポケモンではない）。

> **本改訂の要点（なぜ変えるか）**：変更前はツールが独自に進化マップを読み込み、分岐（スラッシュ）を段情報ごと潰して 1 次元化し、位置（最後の要素・特定インデックス）で O/M/L を展開していた。この方式では分岐進化の一部の枝しかキャッシュ生成されず、アプリ本体（段構造で全枝を対象にする）と食い違って「未収録」警告が出ていた。読み込みと展開をアプリ本体と同じ部品（esal・library）に一本化することで、**キャッシュが生成する種と、アプリが参照する種を常に一致させる**。

### Step2：全IV計算

**本改訂で変更しない。** 対象ポケモン×リーグごとに全4096通りのIV（0〜15の3乗）を計算する。

- 各IVについてレベル1.0〜51.0（0.5刻み）でCP上限以下のSCP最大を探索
- SCP降順・攻撃実数値降順・CP降順・レベル降順でソート
- TopN件に絞る

### Step3：slim形式に変換

**本改訂で変更しない。** 各エントリを5フィールドのCSV文字列に変換する：

```
rank,atk_bucket,def_bucket,hp_bucket,atk_real
```

| フィールド | 内容 |
|---|---|
| rank | SCP降順の順位（1始まり） |
| atk_bucket | 攻撃IVのバケット（0〜4） |
| def_bucket | 防御IVのバケット（0〜4） |
| hp_bucket | HP IVのバケット（0〜4） |
| atk_real | 攻撃実数値（小数点以下2桁） |

#### バケット定義

| バケット | IV範囲 |
|---|---|
| 0 | 0 |
| 1 | 1〜5 |
| 2 | 6〜10 |
| 3 | 11〜14 |
| 4 | 15 |

---

## 5. slim_cache.jsonのフォーマット

**本改訂で変更しない。**

```json
{
  "meta": {
    "script_version": "1.0",
    "created_at": "2026-05-23T23:00:00",
    "total_pokemon": 405,
    "total_entries": 546
  },
  "pokemon": [
    {
      "name": "フシギバナ",
      "dex": 3,
      "leagues": {
        "S": {
          "cp_cap": 1500,
          "topn": 200,
          "entries": [
            "1,1,4,4,121.56",
            "2,1,3,4,121.34",
            ...
          ]
        },
        "H": { ... }
      }
    },
    ...
  ]
}
```

> `slim_cache.json` のキー構造・データ型などの具体的なファイル形式は `slim_cache_spec.md` を参照する。

---

## 6. scp_cache.jsonとの違い

**本改訂で変更しない。**

| 項目 | scp_cache.json（旧） | slim_cache.json（新） |
|---|---|---|
| ファイルサイズ | 704MB | 約4MB |
| 対象ポケモン | 全1020種 | iv_list_input.txtで参照される種のみ |
| フィールド数 | 10（rank, level, iv_atk, iv_def, iv_hp, cp, scp, atk_real, def_real, hp_real） | 5（rank, atk_bucket, def_bucket, hp_bucket, atk_real） |
| 件数 | 最大4096件 | TopN件（iv_list_input.txtの最大値まで） |
| 生成方法 | scp_cache_builder.py | slim_cache_builder.py |

---

## 7. 更新が必要なタイミング

- `pokedex_numbers.txt`に新ポケモンを追加したとき
- `iv_list_input.txt`に新しいポケモン・リーグを追加したとき

更新後はGitHubにpushすることでStreamlitアプリに自動反映される。

---

## 8. ファイル構成

```
tools/
└── slim_cache_builder.py   ← src/（esal・library）を参照する

src/
├── esal/
│   └── iv_strings_reader.py   ← load_evolution_map_staged（進化マップ読み込み）
└── library/
    └── （expand_targets を収録。仕様は library.md）

master_data/
├── pokedex_numbers.txt   ← 入力
├── evolution_map.txt     ← 入力
├── iv_list_input.txt     ← 入力
└── slim_cache.json       ← 出力
```

---

## 9. 制約

恒久的な前提を以下にまとめる。

- **リポジトリ構成（フォルダ・ファイル配置）の正は `spec/repository_overview.md` とする。** 本書はファイル構成図を参考として持つが、正ではない。
- **進化マップの読み込み（段構造への変換）の正は esal の `load_evolution_map_staged`** とする。本ツールは進化マップを独自に読み込まない。
- **O/M/L 展開の正は `library.md`（`expand_targets`）とする。** 本ツールは展開ロジックを独自に持たない。
- **本ツールは `src/`（esal・library）を参照する。** ローカル実行時に `src/` を解決できるようにする必要がある（解決方法は実装に委ねる）。
- **入出力はすべて `master_data/` を用いる**（Rev1.1 で `shared/` から統一）。データ二重管理期間（`shared/`＝旧・`master_data/`＝新）においても、本ツールの入出力は `master_data/` を正とする。
- 全IV計算（Step2）・slim 形式（Step3・5章）・バケット定義は本改訂で変更しない。
