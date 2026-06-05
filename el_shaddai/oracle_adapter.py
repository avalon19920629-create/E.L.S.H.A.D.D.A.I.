"""O.R.A.C.L.E. adapter for VT/BTC spot-buy opportunity signals.

O.R.A.C.L.E. (Opportunity Radar for Accumulation & Cycle-Level Entries)
audits permanent holdings differently from Role-audited assets.  VT and BTC do
not receive Role Scores; the only question is whether conditions favor an
incremental spot buy.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Mapping, Optional, Sequence

from .price_score import score_price

ORACLE_ASSETS = ("VT", "BTC")
ORACLE_WEIGHTS: Mapping[str, Mapping[str, float]] = {
    "VT": {"value_score": 0.35, "sentiment_score": 0.25, "drawdown_momentum_score": 0.25, "cycle_score": 0.15},
    "BTC": {"value_score": 0.35, "sentiment_score": 0.25, "drawdown_momentum_score": 0.25, "cycle_score": 0.15},
}

ORACLE_INPUT_COLUMNS = (
    "cape",
    "market_cap_gdp",
    "earnings_yield",
    "equity_risk_premium",
    "fear_greed",
    "vix",
    "put_call",
    "rsi",
    "dma_200_deviation",
    "dma_200w_deviation",
    "range_52w_position",
    "drawdown_from_ath",
    "mvrv_z",
    "puell_multiple",
    "reserve_risk",
    "rhodl_ratio",
    "yardstick",
    "crypto_fear_greed",
    "funding_rate",
    "days_since_halving",
    "distance_from_previous_cycle_high",
    "bitcoin_dominance",
)


@dataclass(frozen=True)
class OracleAssetResult:
    asset: str
    opportunity_score: float
    oracle_signal: str
    oracle_reason: str
    value_score: float
    sentiment_score: float
    drawdown_momentum_score: float
    cycle_score: float
    components: Mapping[str, Mapping[str, float]]
    reasons: Mapping[str, List[str]]
    warnings: List[str]
    data_date: str
    source: str
    used_oracle: bool


@dataclass(frozen=True)
class OracleResult:
    assets: Mapping[str, OracleAssetResult]
    source: str
    used_oracle: bool
    warnings: List[str]


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _to_float(value: object) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _weighted_average(scores: Mapping[str, float], weights: Mapping[str, float]) -> float:
    total = sum(weights.get(name, 0.0) for name in scores)
    if total == 0:
        return 50.0
    return sum(scores[name] * weights.get(name, 0.0) for name in scores) / total


def _score_low_good(value: Optional[float], low: float, high: float) -> Optional[float]:
    if value is None:
        return None
    if high == low:
        return 50.0
    return _clamp((high - value) / (high - low) * 100.0)


def _score_high_good(value: Optional[float], low: float, high: float) -> Optional[float]:
    if value is None:
        return None
    if high == low:
        return 50.0
    return _clamp((value - low) / (high - low) * 100.0)


def _score_abs_low_good(value: Optional[float], low: float, high: float) -> Optional[float]:
    if value is None:
        return None
    return _score_low_good(abs(value), low, high)


def _bucket_signal(score: float) -> str:
    if score >= 80.0:
        return "神は云っている、ここで買う定めなのだと……"
    if score >= 60.0:
        return "近い。備えよ"
    if score >= 40.0:
        return "まだその時ではない"
    if score >= 20.0:
        return "高値圏。待て"
    return "慢心の極み"


def _component_average(asset: str, group: str, values: Mapping[str, Optional[float]], warnings: List[str]) -> float:
    available = {name: round(float(value), 3) for name, value in values.items() if value is not None}
    if not available:
        warnings.append(f"warning: O.R.A.C.L.E. {asset} {group} inputs unavailable; neutral 50 fallback applied.")
        return 50.0
    return round(sum(available.values()) / len(available), 2)


def _price_drawdown_components(price_history: Optional[Sequence[float]]) -> Dict[str, float]:
    if not price_history:
        return {}
    price = score_price("ORACLE", price_history)
    components = {name: float(value) for name, value in price.components.items() if value is not None}
    return {
        "price_rsi": components.get("rsi", 50.0),
        "price_dma_200_deviation": components.get("dma_200_deviation", 50.0),
        "price_range_52w_position": components.get("range_52w_position", 50.0),
        "price_weekly_drawdown": components.get("weekly_drawdown", 50.0),
    }


def _row_has_numeric_inputs(row: Mapping[str, object], asset: str) -> bool:
    if asset == "VT":
        names = ("cape", "market_cap_gdp", "earnings_yield", "equity_risk_premium", "fear_greed", "vix", "put_call", "rsi", "dma_200_deviation", "range_52w_position", "drawdown_from_ath")
    else:
        names = ("mvrv_z", "puell_multiple", "reserve_risk", "rhodl_ratio", "yardstick", "crypto_fear_greed", "funding_rate", "rsi", "dma_200_deviation", "dma_200w_deviation", "range_52w_position", "drawdown_from_ath", "days_since_halving", "distance_from_previous_cycle_high", "bitcoin_dominance")
    return any(_to_float(row.get(name)) is not None for name in names)

def _vt_scores(row: Mapping[str, object], price_history: Optional[Sequence[float]], warnings: List[str]) -> tuple[Dict[str, object], Dict[str, List[str]]]:
    cape = _to_float(row.get("cape"))
    market_cap_gdp = _to_float(row.get("market_cap_gdp"))
    earnings_yield = _to_float(row.get("earnings_yield"))
    equity_risk_premium = _to_float(row.get("equity_risk_premium"))
    fear_greed = _to_float(row.get("fear_greed"))
    vix = _to_float(row.get("vix"))
    put_call = _to_float(row.get("put_call"))
    rsi = _to_float(row.get("rsi"))
    dma_200_deviation = _to_float(row.get("dma_200_deviation"))
    range_52w_position = _to_float(row.get("range_52w_position"))
    drawdown_from_ath = _to_float(row.get("drawdown_from_ath"))

    value_components = {
        "cape": _score_low_good(cape, 12.0, 35.0),
        "market_cap_gdp": _score_low_good(market_cap_gdp, 70.0, 220.0),
        "earnings_yield": _score_high_good(earnings_yield, 2.0, 8.0),
        "equity_risk_premium": _score_high_good(equity_risk_premium, 0.0, 6.0),
    }
    sentiment_components = {
        "fear_greed": _score_low_good(fear_greed, 10.0, 90.0),
        "vix": _score_high_good(vix, 12.0, 45.0),
        "put_call": _score_high_good(put_call, 0.6, 1.4),
    }
    drawdown_components = {
        "rsi": _score_low_good(rsi, 25.0, 75.0),
        "dma_200_deviation": _score_low_good(dma_200_deviation, -0.30, 0.30),
        "range_52w_position": _score_low_good(range_52w_position, 0.0, 100.0),
        "drawdown_from_ath": _score_high_good(abs(drawdown_from_ath) if drawdown_from_ath is not None else None, 0.0, 0.45),
    }
    drawdown_components.update(_price_drawdown_components(price_history))
    cycle_components = {
        "cycle_neutral": 50.0,
    }

    components = {
        "value_score": {k: v for k, v in value_components.items() if v is not None},
        "sentiment_score": {k: v for k, v in sentiment_components.items() if v is not None},
        "drawdown_momentum_score": {k: v for k, v in drawdown_components.items() if v is not None},
        "cycle_score": cycle_components,
    }
    scores = {
        "value_score": _component_average("VT", "value", value_components, warnings),
        "sentiment_score": _component_average("VT", "sentiment", sentiment_components, warnings),
        "drawdown_momentum_score": _component_average("VT", "drawdown/momentum", drawdown_components, warnings),
        "cycle_score": _component_average("VT", "cycle", cycle_components, warnings),
    }
    reasons = {
        "value_score": [f"CAPE={cape}, MarketCap/GDP={market_cap_gdp}, earnings_yield={earnings_yield}, ERP={equity_risk_premium}; cheaper equity valuation raises opportunity."],
        "sentiment_score": [f"Fear&Greed={fear_greed}, VIX={vix}, put/call={put_call}; fear/stress raises spot-buy opportunity."],
        "drawdown_momentum_score": [f"RSI={rsi}, 200DMA deviation={dma_200_deviation}, 52w position={range_52w_position}, drawdown_from_ATH={drawdown_from_ath}; colder price action raises opportunity."],
        "cycle_score": ["VT cycle inputs are not required in v1.7 manual MVP; neutral cycle fallback is retained unless future macro cycle fields are connected."],
    }
    return {"scores": scores, "components": components}, reasons


def _btc_scores(row: Mapping[str, object], price_history: Optional[Sequence[float]], warnings: List[str]) -> tuple[Dict[str, object], Dict[str, List[str]]]:
    mvrv_z = _to_float(row.get("mvrv_z"))
    puell_multiple = _to_float(row.get("puell_multiple"))
    reserve_risk = _to_float(row.get("reserve_risk"))
    rhodl_ratio = _to_float(row.get("rhodl_ratio"))
    yardstick = _to_float(row.get("yardstick"))
    crypto_fear_greed = _to_float(row.get("crypto_fear_greed"))
    funding_rate = _to_float(row.get("funding_rate"))
    rsi = _to_float(row.get("rsi"))
    dma_200_deviation = _to_float(row.get("dma_200_deviation"))
    dma_200w_deviation = _to_float(row.get("dma_200w_deviation"))
    range_52w_position = _to_float(row.get("range_52w_position"))
    drawdown_from_ath = _to_float(row.get("drawdown_from_ath"))
    days_since_halving = _to_float(row.get("days_since_halving"))
    distance_prev_high = _to_float(row.get("distance_from_previous_cycle_high"))
    bitcoin_dominance = _to_float(row.get("bitcoin_dominance"))

    value_components = {
        "mvrv_z": _score_low_good(mvrv_z, 0.0, 7.0),
        "puell_multiple": _score_low_good(puell_multiple, 0.4, 4.0),
        "reserve_risk": _score_low_good(reserve_risk, 0.001, 0.020),
        "rhodl_ratio": _score_low_good(rhodl_ratio, 500.0, 50000.0),
        "yardstick": _score_low_good(yardstick, 0.0, 4.0),
    }
    sentiment_components = {
        "crypto_fear_greed": _score_low_good(crypto_fear_greed, 10.0, 95.0),
        "funding_rate": _score_low_good(funding_rate, -0.02, 0.08),
    }
    drawdown_components = {
        "rsi": _score_low_good(rsi, 25.0, 80.0),
        "dma_200_deviation": _score_low_good(dma_200_deviation, -0.55, 1.20),
        "dma_200w_deviation": _score_abs_low_good(dma_200w_deviation, 0.0, 1.5),
        "range_52w_position": _score_low_good(range_52w_position, 0.0, 100.0),
        "drawdown_from_ath": _score_high_good(abs(drawdown_from_ath) if drawdown_from_ath is not None else None, 0.0, 0.85),
    }
    drawdown_components.update(_price_drawdown_components(price_history))
    cycle_components = {
        "days_since_halving": _score_low_good(days_since_halving, 150.0, 1100.0),
        "distance_from_previous_cycle_high": _score_abs_low_good(distance_prev_high, 0.0, 1.0),
        "bitcoin_dominance": _score_low_good(bitcoin_dominance, 35.0, 65.0),
    }

    components = {
        "value_score": {k: v for k, v in value_components.items() if v is not None},
        "sentiment_score": {k: v for k, v in sentiment_components.items() if v is not None},
        "drawdown_momentum_score": {k: v for k, v in drawdown_components.items() if v is not None},
        "cycle_score": {k: v for k, v in cycle_components.items() if v is not None},
    }
    scores = {
        "value_score": _component_average("BTC", "value", value_components, warnings),
        "sentiment_score": _component_average("BTC", "sentiment", sentiment_components, warnings),
        "drawdown_momentum_score": _component_average("BTC", "drawdown/momentum", drawdown_components, warnings),
        "cycle_score": _component_average("BTC", "cycle", cycle_components, warnings),
    }
    reasons = {
        "value_score": [f"MVRV Z={mvrv_z}, Puell={puell_multiple}, Reserve Risk={reserve_risk}, RHODL={rhodl_ratio}, Yardstick={yardstick}; lower on-chain valuation stress raises BTC opportunity."],
        "sentiment_score": [f"Crypto Fear&Greed={crypto_fear_greed}, funding_rate={funding_rate}; fear and low/negative leverage premia raise spot-buy opportunity."],
        "drawdown_momentum_score": [f"RSI={rsi}, 200DMA deviation={dma_200_deviation}, 200WMA deviation={dma_200w_deviation}, 52w position={range_52w_position}, drawdown_from_ATH={drawdown_from_ath}; colder BTC price action raises opportunity."],
        "cycle_score": [f"days_since_halving={days_since_halving}, distance_from_previous_cycle_high={distance_prev_high}, bitcoin_dominance={bitcoin_dominance}; proximity to previous-cycle high is treated as a constructive cycle-level entry zone when euphoria is absent."],
    }
    return {"scores": scores, "components": components}, reasons


def compute_oracle_asset(asset: str, row: Mapping[str, object], source: str, price_history: Optional[Sequence[float]] = None) -> OracleAssetResult:
    asset = asset.upper()
    if asset not in ORACLE_ASSETS:
        raise ValueError(f"O.R.A.C.L.E. only supports VT/BTC, got {asset}")
    warnings: List[str] = []
    if asset == "VT":
        data, reasons = _vt_scores(row, price_history, warnings)
    else:
        data, reasons = _btc_scores(row, price_history, warnings)
    layer_scores = data["scores"]  # type: ignore[assignment]
    components = data["components"]  # type: ignore[assignment]
    opportunity_score = round(_weighted_average(layer_scores, ORACLE_WEIGHTS[asset]), 2)  # type: ignore[arg-type]
    signal = _bucket_signal(opportunity_score)
    reason = (
        f"value={layer_scores['value_score']:.2f}; sentiment={layer_scores['sentiment_score']:.2f}; "  # type: ignore[index]
        f"drawdown_momentum={layer_scores['drawdown_momentum_score']:.2f}; cycle={layer_scores['cycle_score']:.2f}"
    )
    return OracleAssetResult(
        asset=asset,
        opportunity_score=opportunity_score,
        oracle_signal=signal,
        oracle_reason=reason,
        value_score=round(float(layer_scores["value_score"]), 2),  # type: ignore[index]
        sentiment_score=round(float(layer_scores["sentiment_score"]), 2),  # type: ignore[index]
        drawdown_momentum_score=round(float(layer_scores["drawdown_momentum_score"]), 2),  # type: ignore[index]
        cycle_score=round(float(layer_scores["cycle_score"]), 2),  # type: ignore[index]
        components=components,  # type: ignore[arg-type]
        reasons=reasons,
        warnings=warnings,
        data_date=str(row.get("date", "unknown")),
        source=source,
        used_oracle=True,
    )


def load_oracle_inputs_csv(path: str) -> Dict[str, Mapping[str, object]]:
    """Load latest VT/BTC manual O.R.A.C.L.E. rows from CSV."""

    latest: Dict[str, Mapping[str, object]] = {}
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw_row in reader:
            row = {str(key).strip().lower(): value for key, value in raw_row.items() if key is not None}
            asset = str(row.get("asset", "")).strip().upper()
            if asset in ORACLE_ASSETS:
                latest[asset] = row
    return latest


def oracle_inputs_from_csv(path: str, price_histories: Optional[Mapping[str, Sequence[float]]] = None) -> OracleResult:
    rows = load_oracle_inputs_csv(path)
    warnings: List[str] = []
    assets: Dict[str, OracleAssetResult] = {}
    for asset in ORACLE_ASSETS:
        row = rows.get(asset)
        if row is None:
            warnings.append(f"warning: O.R.A.C.L.E. manual CSV missing {asset}; existing price_score fallback will be used.")
            continue
        if not _row_has_numeric_inputs(row, asset):
            warnings.append(f"warning: O.R.A.C.L.E. manual CSV has insufficient {asset} inputs; existing price_score fallback will be used.")
            continue
        assets[asset] = compute_oracle_asset(asset, row, f"manual O.R.A.C.L.E. CSV: {path}", (price_histories or {}).get(asset))
    used = bool(assets)
    return OracleResult(assets=assets, source=f"manual O.R.A.C.L.E. CSV: {path}", used_oracle=used, warnings=warnings)


def latest_oracle_inputs(price_histories: Optional[Mapping[str, Sequence[float]]] = None, period: str = "2y") -> OracleResult:
    """Best-effort live O.R.A.C.L.E. route.

    v1.7 treats manual CSV as the primary route.  Live mode only uses yfinance
    price-derived drawdown/momentum and VIX when available; on-chain and CAPE
    data remain neutral until supplied manually.
    """

    try:
        import yfinance as yf  # type: ignore[import-not-found]

        tickers = ["VT", "BTC-USD", "^VIX"]
        data = yf.download(tickers, period=period, progress=False, auto_adjust=False)
        close = data["Close"] if hasattr(data, "__getitem__") else data
        vt = [float(value) for value in close["VT"].ffill().dropna().tolist()]
        btc = [float(value) for value in close["BTC-USD"].ffill().dropna().tolist()]
        vix_series = [float(value) for value in close["^VIX"].ffill().dropna().tolist()]
        histories = dict(price_histories or {}) | {"VT": vt, "BTC": btc}
        today = str(date.today())
        rows = {
            "VT": {"date": today, "asset": "VT", "vix": vix_series[-1] if vix_series else ""},
            "BTC": {"date": today, "asset": "BTC"},
        }
        assets = {asset: compute_oracle_asset(asset, row, "O.R.A.C.L.E. yfinance", histories.get(asset)) for asset, row in rows.items()}
        warnings = ["warning: O.R.A.C.L.E. live mode uses price/VIX only in v1.7; unavailable valuation/on-chain/cycle fields use neutral fallback."]
        return OracleResult(assets=assets, source="O.R.A.C.L.E. yfinance", used_oracle=True, warnings=warnings)
    except Exception as exc:  # noqa: BLE001 - CLI must not stop on live data failure.
        return OracleResult(
            assets={},
            source="O.R.A.C.L.E. yfinance",
            used_oracle=False,
            warnings=[f"warning: failed to fetch O.R.A.C.L.E. live data ({exc}); VT/BTC existing price_score fallback will be used."],
        )
