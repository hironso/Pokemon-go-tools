# slim_cache_builder 仕様書

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

---

## 2. 入力ファイル

| ファイル | 場所 | 用途 |
|---|---|---|
| `pokedex_numbers.txt` | `shared/` | ポケモンの種族値取得 |
| `evolution_map.txt` | `shared/` | O/M/L展開のためのファミリー特定 |
| `iv_list_input.txt` | `shared/` | 計算対象のポケモン×リーグ×TopNを決定 |

---

## 3. 出力ファイル

| ファイル | 場所 |
|---|---|
| `slim_cache.json` | `shared/` |

---

## 4. 処理ロジック

### Step1：対象ポケモン×リーグの特定

`iv_list_input.txt`を読み込み、O/M/L展開を行って計算対象を確定する。

- 同じポケモン×リーグが複数行ある場合は**最大TopN**を採用
- 計算対象はiv_list_input.txtで参照されるポケモン×リーグのみ（全ポケモンではない）

### Step2：全IV計算

対象ポケモン×リーグごとに全4096通りのIV（0〜15の3乗）を計算する。

- 各IVについてレベル1.0〜51.0（0.5刻み）でCP上限以下のSCP最大を探索
- SCP降順・攻撃実数値降順・CP降順・レベル降順でソート
- TopN件に絞る

### Step3：slim形式に変換

各エントリを5フィールドのCSV文字列に変換する：

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

---

## 6. scp_cache.jsonとの違い

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
└── slim_cache_builder.py

shared/
├── pokedex_numbers.txt   ← 入力
├── evolution_map.txt     ← 入力
├── iv_list_input.txt     ← 入力
└── slim_cache.json       ← 出力
```
