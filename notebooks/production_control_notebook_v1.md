# L.U.M.U.S.-8 Production Control Notebook v1.0

Google Colab で **Market Amedas → El Shaddai production audit → Parallax Engine** を毎回同じ順序で実行し、quality gate・manifest・安全境界まで確認するための正式な3セル管制卓テンプレートです。

- このNotebookは投資判断ロジック、スコア、Parallax判定を変更しません。
- 出力は `advisory_only` です。自動売買・自動売却・自動配分変更へ接続しないでください。
- 本番では、下記のGitHub URLと必要に応じてbranch/tag/commitを承認済みの値へ置き換えてください。既存Runbookと同様、固定tagまたはcommit SHAを推奨します。
- 各見出し直下のコードブロックを、それぞれ1つのColabコードセルとして実行してください。

## Cell 1: 環境セットアップ・GitHub取得・FRED APIキー設定

```python
from datetime import date
from getpass import getpass
from pathlib import Path
import os
import subprocess
import sys

RUN_DATE = date.today().isoformat()
BASE_DIR = Path("/content/lumus8_production")
OUTPUT_DIR = BASE_DIR / "artifacts" / RUN_DATE
EL_SHADDAI_REPO = BASE_DIR / "el-shaddai"
MARKET_AMEDAS_REPO = BASE_DIR / "market-amedas"

# 承認済みURLへ置換する。再現性を厳密にする場合は clone/pull 後に固定tag/commitを checkoutする。
EL_SHADDAI_REPO_URL = "https://github.com/YOUR_ORG/YOUR_REPOSITORY.git"
MARKET_AMEDAS_REPO_URL = "https://github.com/YOUR_ORG/YOUR_MARKET_AMEDAS_REPOSITORY.git"


def run(command, *, cwd=None):
    printable = " ".join(map(str, command))
    print(f"+ {printable}")
    subprocess.run(list(map(str, command)), cwd=cwd, check=True)


def clone_or_pull(url, destination):
    destination = Path(destination)
    if "YOUR_" in url:
        raise ValueError(f"承認済みGitHub URLへ置換してください: {url}")
    if (destination / ".git").is_dir():
        run(["git", "pull", "--ff-only"], cwd=destination)
    elif destination.exists():
        raise RuntimeError(f"Git repositoryではない既存パスがあります: {destination}")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", url, destination])


clone_or_pull(EL_SHADDAI_REPO_URL, EL_SHADDAI_REPO)
clone_or_pull(MARKET_AMEDAS_REPO_URL, MARKET_AMEDAS_REPO)

for repo in (EL_SHADDAI_REPO, MARKET_AMEDAS_REPO):
    requirements = repo / "requirements.txt"
    if requirements.is_file():
        run([sys.executable, "-m", "pip", "install", "-r", requirements])
run([sys.executable, "-m", "pip", "install", "fredapi"])

# Colab Secretを優先し、未登録・空値の場合だけ画面で手入力する。キー自体は表示しない。
fred_api_key = ""
try:
    from google.colab import userdata
    fred_api_key = userdata.get("FRED_API_KEY") or ""
except Exception as exc:
    print(f"Colab Secret FRED_API_KEYを取得できませんでした。手入力へ切り替えます: {type(exc).__name__}")
if not fred_api_key:
    fred_api_key = getpass("FRED_API_KEY: ").strip()
if not fred_api_key:
    raise RuntimeError("FRED_API_KEYが設定されていません")
os.environ["FRED_API_KEY"] = fred_api_key

from fredapi import Fred

dgs10 = Fred(api_key=os.environ["FRED_API_KEY"]).get_series("DGS10").dropna()
if dgs10.empty:
    raise RuntimeError("FRED接続テストに失敗しました: DGS10が空です")
print(f"FRED DGS10 latest: {dgs10.index[-1].date()} = {dgs10.iloc[-1]}")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"RUN_DATE   : {RUN_DATE}")
print(f"OUTPUT_DIR : {OUTPUT_DIR}")
```

## Cell 2: Market Amedas CLI実行・snapshot検証

```python
import json
import subprocess
import sys
from pathlib import Path

subprocess.run(
    [sys.executable, "run_market_amedas.py", "--output-dir", str(OUTPUT_DIR)],
    cwd=MARKET_AMEDAS_REPO,
    check=True,
)

MARKET_AMEDAS_SNAPSHOT = OUTPUT_DIR / "market_amedas_snapshot.json"
if not MARKET_AMEDAS_SNAPSHOT.is_file():
    raise FileNotFoundError(f"Market Amedas snapshotが生成されませんでした: {MARKET_AMEDAS_SNAPSHOT}")
try:
    market_snapshot = json.loads(MARKET_AMEDAS_SNAPSHOT.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    raise RuntimeError(f"Market Amedas snapshotが有効なJSONではありません: {exc}") from exc
if market_snapshot.get("schema_version") != "market_amedas_snapshot.v1":
    raise RuntimeError(
        "Market Amedas schema_version不一致: "
        f"expected=market_amedas_snapshot.v1 actual={market_snapshot.get('schema_version')}"
    )

print(f"Market Amedas snapshot: {MARKET_AMEDAS_SNAPSHOT}")
print(f"schema_version         : {market_snapshot['schema_version']}")
print(f"file_size_bytes        : {MARKET_AMEDAS_SNAPSHOT.stat().st_size:,}")
```

## Cell 3: El Shaddai production audit → Parallax → quality gate / manifest / Markdown表示

```python
import json
import shutil
import subprocess
import sys
from pathlib import Path
from pprint import pprint

subprocess.run(
    [
        sys.executable,
        "run_el_shaddai_production.py",
        "--config", "configs/production_lumus8.yaml",
        "--output-dir", str(OUTPUT_DIR),
    ],
    cwd=EL_SHADDAI_REPO,
    check=True,
)
subprocess.run(
    [
        sys.executable,
        "run_parallax.py",
        "--market-amedas", str(OUTPUT_DIR / "market_amedas_snapshot.json"),
        "--el-shaddai", str(OUTPUT_DIR / "el_shaddai_lumus8_audit.json"),
        "--output-dir", str(OUTPUT_DIR),
    ],
    cwd=EL_SHADDAI_REPO,
    check=True,
)

expected_files = [
    "market_amedas_snapshot.json",
    "el_shaddai_lumus8_audit.json",
    "el_shaddai_lumus8_audit.md",
    "el_shaddai_report.md",
    "el_shaddai_scores.csv",
    "el_shaddai_dashboard.html",
    "parallax_context_report.json",
    "parallax_context_report.md",
    "production_run_manifest.json",
]
missing_files = [name for name in expected_files if not (OUTPUT_DIR / name).is_file()]
if missing_files:
    raise FileNotFoundError(f"主要成果物が不足しています: {missing_files}")

print("\n=== Generated artifacts ===")
for path in sorted(OUTPUT_DIR.iterdir()):
    kind = "dir " if path.is_dir() else "file"
    size = "-" if path.is_dir() else f"{path.stat().st_size:,} bytes"
    print(f"{kind:4} {path.name:40} {size}")

parallax = json.loads((OUTPUT_DIR / "parallax_context_report.json").read_text(encoding="utf-8"))
manifest = json.loads((OUTPUT_DIR / "production_run_manifest.json").read_text(encoding="utf-8"))

print("\n=== Parallax Summary ===")
pprint(parallax.get("summary", {}), sort_dicts=False)
print("\n=== Asset contexts ===")
pprint(parallax.get("asset_contexts", []), sort_dicts=False)
print("\n=== Warnings ===")
pprint(parallax.get("warnings", []), sort_dicts=False)

quality_gate = manifest.get("quality_gate", {})
checks = quality_gate.get("checks", {})
print("\n" + "=" * 60)
print("PRODUCTION QUALITY GATE")
print("=" * 60)
print(f"Status          : {quality_gate.get('status', 'unknown')}")
print(f"Label           : {quality_gate.get('label', 'unknown')}")
print(f"Reasons         : {'; '.join(map(str, quality_gate.get('reasons', []))) or 'None'}")
print(f"Market Amedas   : {checks.get('market_amedas', 'MISSING')}")
print(f"El Shaddai      : {checks.get('el_shaddai', 'MISSING')}")
print(f"Parallax        : {checks.get('parallax', 'MISSING')}")
print(f"Price data      : {checks.get('price_data_status', 'unknown')}")
print(f"FRED data       : {checks.get('fred_data_status', 'unknown')} via {checks.get('fred_provider', 'unknown')}")
print(f"Failed adapters : {checks.get('failed_adapters', [])}")
print(f"Safety          : {checks.get('safety', 'NG')}")
print(f"Output dir      : {OUTPUT_DIR}")
print("=" * 60)

print("\n=== Manifest: quality_gate / safety / warnings ===")
pprint({key: manifest.get(key) for key in ("quality_gate", "safety", "warnings")}, sort_dicts=False)

required_safety = {
    "advisory_only": True,
    "automatic_trading": False,
    "automatic_selling": False,
    "allocation_change": False,
}
safety = manifest.get("safety", {})
unsafe = {key: (safety.get(key), expected) for key, expected in required_safety.items() if safety.get(key) != expected}
if unsafe:
    raise RuntimeError(f"安全境界が安全側ではありません: {unsafe}")
if quality_gate.get("status") == "fail":
    raise RuntimeError(f"Production quality gate failed: {quality_gate.get('reasons', [])}")
if quality_gate.get("status") == "warn":
    print("NOTICE: status=warn は失敗ではなく警告付き完了です。warningsを確認してください。")

from IPython.display import Markdown, display
display(Markdown((OUTPUT_DIR / "parallax_context_report.md").read_text(encoding="utf-8")))
```

## Optional Cell 4: Production Archive / Google Drive保存

quality gate確認後に実行する任意セルです。Driveをmountすると日付/実行時刻別履歴、`latest/`、JSON/CSV indexをDriveへ保存します。Driveをmountしない場合やmount先が利用できない場合は、自動的に `/content/lumus8_production/archive` へ保存します。Archiveは監査証跡の保存だけを行い、判定・スコア・売買・配分を変更しません。

```python
# Drive保存を使う場合だけ次の2行を有効化する。
# from google.colab import drive
# drive.mount("/content/drive")

import sys
sys.path.insert(0, str(EL_SHADDAI_REPO))

from el_shaddai.production_archive import archive_production_run

archive_result = archive_production_run(
    output_dir=OUTPUT_DIR,
    archive_root="/content/drive/MyDrive/lumus8_production",
    update_latest=True,
)
archive_result
```

## Optional Cell 5: L.U.M.U.S.-8 History Lens / 監査履歴確認

Optional Cell 4でArchiveを保存した後に実行する任意セルです。蓄積された監査ログを集計し、観測履歴を文脈化します。監査判定や資産配分を変更するセルではありません。

```python
from el_shaddai.history_lens import run_history_lens, render_cli_summary

history_result = run_history_lens(
    archive_index="/content/drive/MyDrive/lumus8_production/archive_index.json",
    output_dir="/content/drive/MyDrive/lumus8_production/history_lens",
    recent_n=5,
    output_format="both",
)
print(render_cli_summary(history_result))
history_result["report"]
```

`history_lens_report.json` と `history_lens_report.md` が出力されます。`persistent_recent` は、存在する直近N回中N-1回以上（1回のみなら1回）で継続的に出現した高注意資産です。
