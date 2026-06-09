#!/usr/bin/env python3
"""El Shaddai の単発 production 監査を実行する入口。"""

from __future__ import annotations

import argparse
from pathlib import Path

from el_shaddai.production import run_production


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one advisory-only El Shaddai production audit.")
    parser.add_argument("--config", default="configs/production_lumus8.yaml", help="Production YAML configuration path.")
    parser.add_argument("--output-dir", required=True, help="Artifact destination, including a mounted Google Drive directory.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = run_production(args.config, args.output_dir)
    print("El Shaddai production audit completed (advisory only; no automatic trading).")
    for name, path in paths.items():
        print(f"Wrote {name}: {Path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
