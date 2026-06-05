"""Command-line interface for El Shaddai v1.7."""

from __future__ import annotations

import argparse
from pathlib import Path

from .arcadia_adapter import latest_xlre_role_inputs, xlre_role_inputs_from_csv
from .aura_adapter import gldm_role_inputs_from_csv, latest_gldm_role_inputs
from .config import DataSourceConfig
from .data_loader import load_inputs
from .inferno_adapter import latest_tip_role_inputs, tip_role_inputs_from_csv
from .lode_adapter import latest_tlt_role_inputs, tlt_role_inputs_from_csv
from .oracle_adapter import latest_oracle_inputs, oracle_inputs_from_csv
from .report import write_csv, write_markdown
from .scoring import score_all
from .visualization import write_html


def diagnose_data_sources() -> int:
    """Print adapter dependency and provider diagnostics without failing the CLI."""

    print("Data source diagnostics")
    try:
        __import__("yfinance")
        print("yfinance import: ok")
    except Exception as exc:  # noqa: BLE001
        print(f"yfinance import: unavailable ({exc})")
    try:
        import urllib.request

        with urllib.request.urlopen("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y", timeout=10) as response:
            print(f"FRED endpoint: ok (HTTP {response.status})")
    except Exception as exc:  # noqa: BLE001
        print(f"FRED endpoint: unavailable ({exc})")
    lode = latest_tlt_role_inputs()
    print(f"L.O.D.E. fetch: {'ok' if lode.used_lode else 'fallback'}")
    for warning in lode.warnings:
        print(warning)
    inferno = latest_tip_role_inputs()
    print(f"I.N.F.E.R.N.O. fetch: {'ok' if inferno.used_inferno else 'fallback'}")
    for warning in inferno.warnings:
        print(warning)
    aura = latest_gldm_role_inputs()
    print(f"A.U.R.A. fetch: {'ok' if aura.used_aura else 'fallback'}")
    for warning in aura.warnings:
        print(warning)
    arcadia = latest_xlre_role_inputs()
    print(f"A.R.C.A.D.I.A. fetch: {'ok' if arcadia.used_arcadia else 'fallback'}")
    for warning in arcadia.warnings:
        print(warning)
    oracle = latest_oracle_inputs()
    print(f"O.R.A.C.L.E. fetch: {'ok' if oracle.used_oracle else 'fallback'}")
    for warning in oracle.warnings:
        print(warning)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run El Shaddai health diagnostics.")
    parser.add_argument("--output-dir", default="artifacts/el_shaddai", help="Directory for CSV, Markdown, and HTML artifacts.")
    parser.add_argument("--prices-csv", help="Optional CSV with columns date, asset, close.")
    parser.add_argument("--role-inputs-json", help="Optional JSON role proxy overrides by asset.")
    parser.add_argument("--sample-days", type=int, default=320, help="Number of built-in sample price days when no CSV is supplied.")
    parser.add_argument("--use-lode-tlt-role", action="store_true", help="Fetch FRED L.O.D.E. data and overwrite TLT role proxy inputs.")
    parser.add_argument("--use-inferno-tip-role", action="store_true", help="Fetch I.N.F.E.R.N.O. inflation data and overwrite TIP role proxy inputs.")
    parser.add_argument("--inferno-inputs-csv", help="Manual I.N.F.E.R.N.O. CSV for TIP role proxies; takes priority over live FRED.")
    parser.add_argument("--use-aura-gldm-role", action="store_true", help="Fetch A.U.R.A. market data and overwrite GLDM role proxy inputs.")
    parser.add_argument("--lode-inputs-csv", help="Manual L.O.D.E. CSV with raw FRED-style columns for TLT role proxies.")
    parser.add_argument("--aura-prices-csv", help="Manual A.U.R.A. prices CSV (long date,ticker,close or wide ticker columns) for GLDM role proxies.")
    parser.add_argument("--use-arcadia-xlre-role", action="store_true", help="Fetch A.R.C.A.D.I.A. market data and overwrite XLRE role proxy inputs.")
    parser.add_argument("--arcadia-prices-csv", help="Manual A.R.C.A.D.I.A. prices CSV for XLRE role proxies; takes priority over live yfinance.")
    parser.add_argument("--use-oracle", action="store_true", help="Generate VT/BTC O.R.A.C.L.E. spot-buy opportunity signals.")
    parser.add_argument("--oracle-inputs-csv", help="Manual O.R.A.C.L.E. inputs CSV for VT/BTC; takes priority over live yfinance.")
    parser.add_argument("--diagnose-data-sources", action="store_true", help="Check optional dependencies and live adapter availability, then exit.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.diagnose_data_sources:
        return diagnose_data_sources()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    prices, role_inputs, data_date, source_summary = load_inputs(
        DataSourceConfig(prices_csv=args.prices_csv, role_inputs_json=args.role_inputs_json, sample_days=args.sample_days)
    )
    lode_result = None
    inferno_result = None
    aura_result = None
    arcadia_result = None
    oracle_result = None
    if args.lode_inputs_csv or args.use_lode_tlt_role:
        lode_result = tlt_role_inputs_from_csv(args.lode_inputs_csv) if args.lode_inputs_csv else latest_tlt_role_inputs()
        role_inputs = {asset: dict(values) for asset, values in role_inputs.items()}
        role_inputs["TLT"] = dict(lode_result.role_inputs["TLT"])
        source_summary += "; TLT Role inputs generated by L.O.D.E. FRED adapter"
        for warning in lode_result.warnings:
            print(warning)

    if args.inferno_inputs_csv or args.use_inferno_tip_role:
        inferno_result = tip_role_inputs_from_csv(args.inferno_inputs_csv) if args.inferno_inputs_csv else latest_tip_role_inputs()
        role_inputs = {asset: dict(values) for asset, values in role_inputs.items()}
        role_inputs["TIP"] = dict(inferno_result.role_inputs["TIP"])
        source_summary += f"; TIP Role inputs generated by {inferno_result.source}"
        for warning in inferno_result.warnings:
            print(warning)

    if args.aura_prices_csv or args.use_aura_gldm_role:
        aura_result = gldm_role_inputs_from_csv(args.aura_prices_csv) if args.aura_prices_csv else latest_gldm_role_inputs()
        role_inputs = {asset: dict(values) for asset, values in role_inputs.items()}
        role_inputs["GLDM"] = dict(aura_result.role_inputs["GLDM"])
        source_summary += "; GLDM Role inputs generated by A.U.R.A. adapter"
        for warning in aura_result.warnings:
            print(warning)

    if args.arcadia_prices_csv or args.use_arcadia_xlre_role:
        arcadia_result = xlre_role_inputs_from_csv(args.arcadia_prices_csv) if args.arcadia_prices_csv else latest_xlre_role_inputs()
        role_inputs = {asset: dict(values) for asset, values in role_inputs.items()}
        role_inputs["XLRE"] = dict(arcadia_result.role_inputs["XLRE"])
        source_summary += "; XLRE Role inputs generated by A.R.C.A.D.I.A. adapter"
        for warning in arcadia_result.warnings:
            print(warning)

    if args.oracle_inputs_csv or args.use_oracle:
        oracle_result = oracle_inputs_from_csv(args.oracle_inputs_csv, prices) if args.oracle_inputs_csv else latest_oracle_inputs(prices)
        source_summary += f"; VT/BTC Opportunity generated by {oracle_result.source}"
        for warning in oracle_result.warnings:
            print(warning)
        for asset_result in oracle_result.assets.values():
            for warning in asset_result.warnings:
                print(warning)

    scores = score_all(prices, role_inputs, data_date, oracle_results=None if oracle_result is None else oracle_result.assets)
    csv_path = write_csv(scores, output_dir)
    md_path = write_markdown(scores, output_dir, source_summary, lode_result=lode_result, inferno_result=inferno_result, aura_result=aura_result, arcadia_result=arcadia_result, oracle_result=oracle_result)
    html_path = write_html(scores, output_dir, aura_result=aura_result, arcadia_result=arcadia_result, oracle_result=oracle_result)
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
