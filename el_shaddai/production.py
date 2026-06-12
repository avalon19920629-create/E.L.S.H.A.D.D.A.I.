"""Google Colab から実行する El Shaddai 最小本番監査オーケストレーター。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .arcadia_adapter import latest_xlre_role_inputs
from .atlas_adapter import latest_bndx_role_inputs
from .aura_adapter import latest_gldm_role_inputs
from .config import ASSETS, DEFAULT_ROLE_INPUTS
from .fred_data import resolve_fred_provider
from .gaia_adapter import latest_dbc_role_inputs
from .inferno_adapter import latest_tip_role_inputs
from .integrated_audit import run_integrated_audit
from .integrated_audit_json import build_integrated_audit_json, write_integrated_audit_json
from .lode_adapter import latest_tlt_role_inputs
from .models import AssetAuditInput, PortfolioInput
from .oracle_adapter import latest_oracle_inputs
from .report import write_csv, write_markdown
from .scoring import AssetScore, score_all
from .visualization import write_html

AUDIT_ENGINES = {
    "VT": "O.R.A.C.L.E.", "BTC": "O.R.A.C.L.E.", "BNDX": "A.T.L.A.S.",
    "TLT": "L.O.D.E.", "TIP": "I.N.F.E.R.N.O.", "GLDM": "A.U.R.A.",
    "XLRE": "A.R.C.A.D.I.A.", "DBC": "G.A.I.A.",
}
ROLE_ADAPTERS: Mapping[str, Callable[[], Any]] = {
    "BNDX": latest_bndx_role_inputs, "TLT": latest_tlt_role_inputs,
    "TIP": latest_tip_role_inputs, "GLDM": latest_gldm_role_inputs,
    "XLRE": latest_xlre_role_inputs, "DBC": latest_dbc_role_inputs,
}


@dataclass(frozen=True)
class ProductionConfig:
    price_period: str
    target_weights: Mapping[str, float]
    enabled_role_adapters: tuple[str, ...]
    use_oracle: bool
    fred_retry_count: int = 3
    fred_pause: float = 1.0
    fred_timeout: float = 60.0
    fred_cache_dir: str | None = None
    fred_provider: str = "pandas_datareader"


def load_production_config(path: str | Path) -> ProductionConfig:
    """YAML を読み、production実行に必要な設定を厳格に検証する。"""
    import yaml

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    price_data = raw.get("price_data", {})
    if price_data.get("provider") != "yfinance":
        raise ValueError("price_data.provider は yfinance のみサポートします")
    weights = raw.get("portfolio", {}).get("target_weights", {})
    if set(weights) != set(ASSETS):
        raise ValueError(f"portfolio.target_weights は8資産すべてを含めてください: {', '.join(ASSETS)}")
    normalized = {asset: float(weights[asset]) for asset in ASSETS}
    if any(value < 0 for value in normalized.values()) or abs(sum(normalized.values()) - 1.0) > 0.001:
        raise ValueError("portfolio.target_weights は非負で、合計を1.0にしてください")
    enabled = tuple(raw.get("role_adapters", {}).get("enabled", ROLE_ADAPTERS))
    unknown = set(enabled) - set(ROLE_ADAPTERS)
    if unknown:
        raise ValueError(f"未対応の role adapter: {', '.join(sorted(unknown))}")
    fred = raw.get("fred", {})
    provider = str(fred.get("provider", "pandas_datareader"))
    if provider not in {"pandas_datareader", "fredapi"}:
        raise ValueError("fred.provider は pandas_datareader または fredapi のみサポートします")
    return ProductionConfig(
        price_period=str(price_data.get("period", "5y")),
        target_weights=normalized,
        enabled_role_adapters=enabled,
        use_oracle=bool(raw.get("oracle", {}).get("enabled", True)),
        fred_retry_count=int(fred.get("retry_count", 3)),
        fred_pause=float(fred.get("pause", 1.0)),
        fred_timeout=float(fred.get("timeout", 60)),
        fred_cache_dir=fred.get("cache_dir"),
        fred_provider=provider,
    )


def fetch_live_prices(period: str) -> tuple[dict[str, list[float]], str]:
    """全8資産の価格履歴を取得する。productionではサンプル値へフォールバックしない。"""
    import pandas as pd
    import yfinance as yf

    data = yf.download(list(ASSETS), period=period, progress=False, auto_adjust=False)
    if data.empty:
        raise RuntimeError("yfinance から価格履歴を取得できませんでした")
    close = data["Close"] if isinstance(data.columns, pd.MultiIndex) else data
    prices: dict[str, list[float]] = {}
    missing: list[str] = []
    for asset in ASSETS:
        if asset not in close:
            missing.append(asset)
            continue
        values = [float(value) for value in close[asset].dropna().tolist()]
        if not values:
            missing.append(asset)
        else:
            prices[asset] = values
    if missing:
        raise RuntimeError(f"価格履歴が欠損しているため本番監査を中止します: {', '.join(missing)}")
    data_date = close.dropna(how="all").index[-1].date().isoformat()
    return prices, data_date


def _asset_audits(scores: list[AssetScore]) -> list[AssetAuditInput]:
    return [
        AssetAuditInput(
            asset=score.asset,
            audit_engine=AUDIT_ENGINES[score.asset],
            role_health_score=score.role_score if score.role_score is not None else score.el_shaddai_score,
            raw_score=score.el_shaddai_score,
            confidence_level=3,
            diagnosis_summary=score.main_reason,
            supporting_metrics={
                "price_score": score.price_score, "role_score": score.role_score, "final_score": score.el_shaddai_score, "data_date": score.data_date,
                "price_components": dict(score.price_details.components), "role_components": dict(score.role_details.components),
                "core_score": score.role_details.core_score, "rental_cashflow": score.role_details.components.get("rental_cashflow"),
            },
        )
        for score in scores
    ]


def _adapter_succeeded(result: Any) -> bool:
    """Return whether a role adapter produced non-neutral adapter data."""
    for attribute in ("used_lode", "used_inferno"):
        if hasattr(result, attribute):
            return bool(getattr(result, attribute))
    return True


def run_production(config_path: str | Path, output_dir: str | Path) -> dict[str, Path]:
    """ライブデータ監査を1回実行し、指定ディレクトリへ監査成果物を保存する。"""
    config = load_production_config(config_path)
    destination = Path(output_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)

    prices, data_date = fetch_live_prices(config.price_period)
    role_inputs = {asset: dict(values) for asset, values in DEFAULT_ROLE_INPUTS.items()}
    adapter_results: dict[str, Any] = {}
    warnings: list[str] = []
    for asset in config.enabled_role_adapters:
        if asset in {"TLT", "TIP"}:
            result = ROLE_ADAPTERS[asset](
                retry_count=config.fred_retry_count, pause=config.fred_pause, timeout=config.fred_timeout,
                cache_dir=config.fred_cache_dir or str(destination / "fred_cache"), fred_provider=config.fred_provider,
            )
        else:
            result = ROLE_ADAPTERS[asset]()
        adapter_results[asset] = result
        role_inputs[asset] = dict(result.role_inputs[asset])
        warnings.extend(result.warnings)

    oracle_result = latest_oracle_inputs(prices) if config.use_oracle else None
    if oracle_result is not None:
        warnings.extend(oracle_result.warnings)
        for asset_result in oracle_result.assets.values():
            warnings.extend(asset_result.warnings)

    scores = score_all(prices, role_inputs, data_date, oracle_results=None if oracle_result is None else oracle_result.assets)
    source_summary = f"production live run; prices=yfinance ({config.price_period}); role adapters={','.join(config.enabled_role_adapters)}"
    paths = {
        "scores_csv": write_csv(scores, destination),
        "asset_report_markdown": write_markdown(
            scores, destination, source_summary,
            atlas_result=adapter_results.get("BNDX"), lode_result=adapter_results.get("TLT"),
            inferno_result=adapter_results.get("TIP"), aura_result=adapter_results.get("GLDM"),
            gaia_result=adapter_results.get("DBC"), arcadia_result=adapter_results.get("XLRE"),
            oracle_result=oracle_result,
        ),
        "dashboard_html": write_html(
            scores, destination, aura_result=adapter_results.get("GLDM"),
            gaia_result=adapter_results.get("DBC"), arcadia_result=adapter_results.get("XLRE"),
            oracle_result=oracle_result,
        ),
    }
    degraded_assets = [asset for asset, result in adapter_results.items() if getattr(result, "degraded", False)]
    failed_adapters = [
        asset for asset, result in adapter_results.items()
        if getattr(result, "degraded", False) and not _adapter_succeeded(result)
    ]
    effective_fred_provider = resolve_fred_provider(config.fred_provider)
    integrated = run_integrated_audit(
        _asset_audits(scores), PortfolioInput(dict(config.target_weights)),
        data_runtime={
            "fred_provider": effective_fred_provider,
            "degraded_assets": degraded_assets,
            "failed_adapters": failed_adapters,
        },
    )
    integrated_path = destination / "el_shaddai_lumus8_audit.md"
    integrated_path.write_text(integrated["report_text"], encoding="utf-8")
    paths["lumus8_report_markdown"] = integrated_path

    # The machine-readable canonical audit is intentionally not added to the
    # first-version manifest artifacts. Failure must not block legacy outputs.
    try:
        audit_json = build_integrated_audit_json(
            integrated, scores, adapter_results=adapter_results, warnings=warnings, data_date=data_date,
        )
        write_integrated_audit_json(audit_json, destination / "el_shaddai_lumus8_audit.json")
    except Exception as exc:  # pragma: no cover - exact I/O failures are environment-dependent
        warnings.append(f"warning: failed to write el_shaddai_lumus8_audit.json ({exc})")

    manifest_path = destination / "production_run_manifest.json"
    manifest_path.write_text(json.dumps({
        "run_type": "production_single_audit",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_date": data_date,
        "config": asdict(config),
        "output_dir": str(destination),
        "warnings": warnings,
        "degraded_assets": degraded_assets,
        "failed_adapters": failed_adapters,
        "adapter_status": {asset: {
            "source": result.source, "degraded": getattr(result, "degraded", False),
            "stale_days": getattr(result, "stale_days", None),
        } for asset, result in adapter_results.items()},
        "artifacts": {name: str(path) for name, path in paths.items()},
        "safety": {"advisory_only": True, "automatic_trading": False, "continuous_monitoring": False},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["manifest_json"] = manifest_path
    return paths
