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
