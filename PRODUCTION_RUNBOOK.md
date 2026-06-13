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
