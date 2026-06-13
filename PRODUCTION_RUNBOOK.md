# El Shaddai Google Colab Production Runbook

このRunbookは、GitHub上のコードをGoogle Colabから取得し、**単発・助言専用**のL.U.M.U.S.-8監査を実行して、Google Driveへ監査レポートを保存する最小本番手順です。自動売買、注文執行、常時監視、スケジューラーは含みません。

## 1. 前提と安全境界

- ColabからGitHubリポジトリをcloneできること。
- Google Driveへ保存できるGoogleアカウントを使うこと。
- `configs/production_lumus8.yaml` の目標配分を、実行前に承認済みの値へ更新すること。
- production入口は価格データをyfinanceから取得します。全8資産の価格履歴が揃わない場合、サンプルデータへ切り替えず監査を中止します。
- Role adapterが取得に失敗した場合は、既存adapterの中立fallbackと警告を監査manifestへ記録します。レポートを利用する前に `production_run_manifest.json` の `warnings` を必ず確認してください。

## 2. Colabで実行するセル

### セル1: Google Driveをmount

```python
from google.colab import drive
drive.mount('/content/drive')
```

### セル2: GitHubからコードを取得

`YOUR_ORG/YOUR_REPOSITORY` とbranch/tagは、承認済みのものへ置き換えてください。再現性のため、本番では固定tagまたはcommit SHAを推奨します。

```bash
%cd /content
!git clone https://github.com/YOUR_ORG/YOUR_REPOSITORY.git el-shaddai
%cd /content/el-shaddai
!git checkout YOUR_APPROVED_TAG_OR_COMMIT
```

### セル3: 依存関係を導入

```bash
!python -m pip install -r requirements.txt
```

### セル4: 設定を確認

```bash
!cat configs/production_lumus8.yaml
```

`portfolio.target_weights` は8資産すべてを含め、非負かつ合計 `1.0` にします。必要ならDrive上に承認済みYAMLを置き、次のセルの `--config` で指定してください。

### セル5: 単発production監査を実行してDriveへ保存

```bash
!python run_el_shaddai_production.py \
  --config configs/production_lumus8.yaml \
  --output-dir /content/drive/MyDrive/el_shaddai/production_reports
```

`--output-dir` はGoogle Drive mount配下の任意の保存先に変更できます。ディレクトリが存在しない場合は作成されます。

### セル6: 保存結果と警告を確認

```bash
!find /content/drive/MyDrive/el_shaddai/production_reports -maxdepth 1 -type f -printf '%f\n' | sort
!cat /content/drive/MyDrive/el_shaddai/production_reports/production_run_manifest.json
```

## 3. 生成物

- `el_shaddai_scores.csv`: 資産別スコア
- `el_shaddai_report.md`: 資産別監査レポート
- `el_shaddai_dashboard.html`: 閲覧用ダッシュボード
- `el_shaddai_lumus8_audit.md`: L.U.M.U.S.-8統合監査レポート
- `production_run_manifest.json`: 実行日時、データ日付、設定、警告、安全境界、成果物一覧

## 4. 障害時の判断

1. コマンドが非0終了した場合は、本番監査未完了として扱います。
2. 価格欠損エラーの場合はネットワークとyfinance応答を確認し、再実行します。サンプルデータで代替しません。
3. 実行成功後もmanifestの `warnings` が空でなければ、該当adapterのデータ取得状況を確認してからレポートを利用します。
4. 出力は助言専用です。レポートを注文や売買へ自動接続しません。

## 5. ローカル事前確認

```bash
python -m pytest -q
python run_el_shaddai_production.py --help
```

## FRED resilience (L.O.D.E. / I.N.F.E.R.N.O.)

When the `FRED_API_KEY` environment variable is non-empty, production automatically prefers `fredapi` for both L.O.D.E. and I.N.F.E.R.N.O., regardless of the configured keyless provider. In Colab, install `fredapi` and set the secret before running El Shaddai:

```python
%pip install -q fredapi
import os
from google.colab import userdata
os.environ["FRED_API_KEY"] = userdata.get("FRED_API_KEY")
```

Without a key, production preserves the provider configured under `fred` in `configs/production_lumus8.yaml` (`pandas_datareader` by default). The shared settings also include `retry_count` (default `3`), `pause` (default `1.0` seconds), `timeout` (default `60` seconds), and `cache_dir`. If `cache_dir` is omitted, the runner stores last-successful responses under `<output_dir>/fred_cache`; a Google Drive path can be configured directly in Colab.

The fallback order is live FRED, last-successful cache, then neutral proxy. Warnings identify the failed live provider. Cache-backed results are reported with `source=cache`, `degraded=true`, and `stale_days`; neutral results are also marked degraded and appear in manifest `failed_adapters`, which may reduce downstream Parallax confidence. No automatic trading, automatic selling, or continuous monitoring is performed.

Parallax Engine v0.1.2 renders internal `severity` values as Japanese confirmation-priority labels in Markdown. `critical` is displayed as `最重要確認`, but this is not a trading, selling, or allocation-change decision. JSON keeps the machine-readable `context_label`, `severity`, and `confidence` values unchanged.

Parallax Engine v0.1.1 scopes non-critical warnings through each asset context’s `relevant_warnings`: O.R.A.C.L.E. warnings primarily qualify VT/BTC confidence, I.N.F.E.R.N.O. severe-penalty warnings primarily qualify TIP, and Market Amedas BTC/inflation warnings qualify their related assets. Only global critical input failures, including an NG FRED/price status or non-empty `failed_adapters`, reduce every asset to low confidence. A successful `fredapi` result with empty degraded/failed adapter lists does not lower TLT/TIP/BNDX solely for FRED reasons.

## Production manifest and quality gate

`production_run_manifest.json` は、単なる成果物一覧ではなく、各 production 監査の「表紙・証跡」です。実行コードの Git commit / branch / dirty 状態、Market Amedas・El Shaddai・Parallax の入力状態、price / FRED / adapter 状態、生成ファイルとサイズ、安全境界、最終 quality gate を一か所で確認できます。Git 情報を取得できない環境でも、監査成果物の生成は継続します。

Parallax runner の最後には `PRODUCTION QUALITY GATE` が表示され、同じ結果が manifest の `quality_gate` に保存されます。

- `pass`: 主要 JSON、price / FRED、adapter、安全境界が正常で、warning がない状態。
- `warn`: 主要監査は利用可能だが、既知 fallback、degraded adapter、その他の warning を確認すべき状態。
- `fail`: 主要 JSON 欠損、price / FRED NG、failed adapter、安全境界不整合のいずれかがある未完了状態。

Parallax Markdown の「本日の読みどころ」は、市場文脈との乖離や説明可能な弱さなど、確認優先度を短く要約したものです。売買判断、売却判断、追加投資、配分変更の指示ではありません。

## 6. L.U.M.U.S.-8 Production Control Notebook v1.0（正式3セル管制卓）

毎回同じ手順で三層通し本番監査を実行する場合は、[`notebooks/production_control_notebook_v1.md`](notebooks/production_control_notebook_v1.md) の3セルテンプレートを使用します。実行順序は必ず次の通りです。

1. **Cell 1 — 環境セットアップ**: `RUN_DATE` / `OUTPUT_DIR` を定義し、El ShaddaiとMarket Amedasをcloneまたはpullし、requirementsと`fredapi`を導入します。Colab Secretまたは手入力で`FRED_API_KEY`を設定し、FRED `DGS10`取得テストを通します。
2. **Cell 2 — Market Amedas**: Market Amedas repositoryで `python run_market_amedas.py --output-dir <OUTPUT_DIR>` を実行し、`market_amedas_snapshot.json` の存在、`schema_version == market_amedas_snapshot.v1`、ファイルサイズを検証します。
3. **Cell 3 — El Shaddai → Parallax**: El Shaddai repositoryで次の順序を守って実行し、成果物、Parallax Summary、asset contexts、warnings、quality gate、manifest safety flags、Markdownレポートを表示します。

```bash
python run_el_shaddai_production.py --config configs/production_lumus8.yaml --output-dir <OUTPUT_DIR>
python run_parallax.py --market-amedas <OUTPUT_DIR>/market_amedas_snapshot.json --el-shaddai <OUTPUT_DIR>/el_shaddai_lumus8_audit.json --output-dir <OUTPUT_DIR>
```

### 6.1 GitHub URLとFRED_API_KEY

既存の本Runbook方針と同様に、テンプレート内の `YOUR_ORG/...` は承認済みGitHub URLへ置き換えます。本番の再現性を厳密にする場合は、clone/pull後に承認済みtagまたはcommit SHAをcheckoutしてください。

`FRED_API_KEY` はColabの「Secrets」で同名キーを登録する方法を推奨します。テンプレートはSecretを優先し、取得できない場合だけ非表示の手入力へ切り替えます。キー文字列をNotebook出力、Git、manifestへ書き込まないでください。Cell 1の`DGS10`接続テストが失敗した場合はCell 2以降へ進みません。

### 6.2 Quality gateと安全境界の読み方

- `status: pass`: 主要入力・成果物・price/FRED・adapter・安全境界が正常で、warningがありません。
- `status: warn`: **失敗ではなく警告付き完了**です。成果物は生成されていますが、`quality_gate.reasons` と `warnings` を確認してから利用します。
- `status: fail`: 主要入力、price/FRED状態、failed adapter、または安全境界に未完了があります。監査完了として扱わず、原因を解消して再実行します。

最後に `production_run_manifest.json` の `quality_gate` / `warnings` と、次のsafety flagsがすべて安全側であることを必ず確認します。

```text
advisory_only: true
automatic_trading: false
automatic_selling: false
allocation_change: false
```

### 6.3 成果物と用途

| 成果物 | 用途 |
| --- | --- |
| `market_amedas_snapshot.json` | Market Amedasの市場天候入力。schema v1を検証します。 |
| `el_shaddai_lumus8_audit.json` | Parallaxへ渡す機械可読なL.U.M.U.S.-8統合監査。 |
| `el_shaddai_lumus8_audit.md` | L.U.M.U.S.-8統合監査の閲覧用Markdown。 |
| `el_shaddai_report.md` | El Shaddai資産別レポート。 |
| `el_shaddai_scores.csv` | 資産別スコアの表形式出力。 |
| `el_shaddai_dashboard.html` | 閲覧用HTMLダッシュボード。 |
| `parallax_context_report.json` | Parallax Summary、asset contexts、warnings、安全境界の機械可読出力。 |
| `parallax_context_report.md` | Colab上でMarkdown表示する「本日の読みどころ」を含む照合レポート。 |
| `production_run_manifest.json` | Git provenance、入力状態、成果物、warnings、quality gate、safetyをまとめた監査証跡。 |
| `fred_cache/` | live FRED失敗時に利用するlast-successful cache。 |

### 6.4 Google Drive保存（オプション）

標準出力先は `/content/lumus8_production/artifacts/YYYY-MM-DD/` です。Drive保存またはlocal archiveへの履歴保存が必要な場合だけ、三層監査とquality gate確認後に optional Cell 4 の `archive_production_run()` を実行します。Driveをmountしなくても三層監査とlocal archiveは完了します。

## Production Archive v1.0（監査証跡の継続保存）

Production Archive は、Market Amedas → El Shaddai → Parallax Engine の実行後に、`OUTPUT_DIR` の成果物を履歴として保存・索引化する仕組みです。投資判断、スコアリング、気団計算、監査判定、context判定を変更せず、自動売買・自動売却・配分変更にも接続しません。

Google Driveをmount済みの場合の推奨構造は次のとおりです。同日複数回の実行は `run_HHMMSS`（衝突時は連番suffix）で分離されます。

```text
/content/drive/MyDrive/lumus8_production/
├── YYYY-MM-DD/run_HHMMSS/   # 変更しない実行時点の監査証跡
├── latest/                  # 最後にarchiveした成果物一式
├── archive_index.json       # 完全な履歴・safety・missing files
└── archive_index.csv        # Google Sheets等で比較しやすい主要列
```

```bash
python -m el_shaddai.production_archive \
  --output-dir /content/lumus8_production/artifacts/2026-06-13 \
  --archive-root /content/drive/MyDrive/lumus8_production \
  --update-latest
```

`/content/drive/MyDrive` が利用できない状態でDrive配下を指定した場合は、`/content/lumus8_production/archive` へ自動fallbackします。`latest/` は直近成果物の閲覧用であり、日付/時刻別フォルダが変更されない履歴です。`archive_index.json` / `archive_index.csv` は quality gate status、warning数、Parallax状態、データ状態、adapter状態、安全境界を実行ごとに蓄積し、履歴比較と改善分析に利用します。

主要成果物の欠損や安全境界の不一致はarchiveを止めず、結果とindexに `warning` として明記します。破損したJSON indexは `.bak` へ退避してから新規indexを作ります。Archive結果が `warning` の場合は、`missing_files`、`archive_warnings`、`safety_ok` を確認してください。

## History Lens v0.1（監査履歴の文脈化）

Optional Cell 4 で Production Archive を更新した後、Optional Cell 5 で History Lens を実行します。History Lens は `archive_index.json` または `archive_index.csv` を読み、quality gate、warning数、Parallax状態、市場regime、高注意資産、データ取得、adapter、安全境界の継続状況を確認する補助ビューアです。監査判定や資産配分は変更しません。

```bash
python -m el_shaddai.history_lens \
  --archive-index /content/drive/MyDrive/lumus8_production/archive_index.json \
  --output-dir /content/drive/MyDrive/lumus8_production/history_lens \
  --recent-n 5 \
  --format both
```

`history_lens_report.json` は機械可読な集計、`history_lens_report.md` は人間向け履歴レポートです。`persistent_recent` は、存在する直近N回中N-1回以上（窓が1回なら1回）出現した高注意資産を示し、継続確認の対象を文脈化します。CSV indexには安全境界の完全情報がないため、その履歴は `unknown` になります。完全な安全境界履歴の確認にはJSON indexを使用してください。
