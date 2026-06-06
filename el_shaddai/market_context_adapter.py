"""Market Amedas を弱い外部文脈へ変換する安全なアダプター。"""

from __future__ import annotations

from .models import MarketAmedasInput, MarketContext

ASSETS = ("VT", "BTC", "TLT", "TIP", "GLDM", "XLRE", "BNDX", "DBC")

MARKET_CONTEXT_FLAG_LABELS_JA = {
    "neutral_market_context": "中立市場文脈",
    "yield_air_mass_dominant": "金利気団が優勢",
    "growth_air_mass_strong": "成長気団が強い",
    "defense_air_mass_absent": "防衛気団が弱い",
    "inflation_air_mass_absent": "インフレ気団が弱い",
    "junk_oxygen_healthy": "低格付け信用環境は健全",
    "smallcap_geothermal_warm": "小型株環境は温暖",
    "btc_negative_divergence": "BTCに負の乖離",
    "gold_commodity_weakness": "金・商品が弱い",
}


def _strength(value: float) -> float:
    """0..1 と 0..100 の入力を 0..1 に正規化する。"""
    return max(0.0, min(1.0, float(value) / 100 if abs(float(value)) > 1 else float(value)))


def adapt_market_context(market: MarketAmedasInput | None) -> MarketContext:
    """市場気象を文脈化する。結果は運用判断レベルを直接決定しない。"""
    if market is None:
        return MarketContext(
            "Market Amedas入力なし。中立の市場文脈で監査した。",
            ["neutral_market_context"],
            {}, {asset: 1.0 for asset in ASSETS}, {},
        )

    air = {key: _strength(market.air_mass.get(key, 0.5)) for key in ("yield", "growth", "defense", "inflation")}
    flags: list[str] = []
    if air["yield"] >= 0.65: flags.append("yield_air_mass_dominant")
    if air["growth"] >= 0.65: flags.append("growth_air_mass_strong")
    if air["defense"] <= 0.35: flags.append("defense_air_mass_absent")
    if air["inflation"] <= 0.35: flags.append("inflation_air_mass_absent")

    atmos = {str(k).lower(): str(v).lower() for k, v in market.atmospheric_conditions.items()}
    if "healthy" in atmos.get("junk_oxygen", ""): flags.append("junk_oxygen_healthy")
    if "warm" in atmos.get("smallcap_geothermal", ""): flags.append("smallcap_geothermal_warm")
    if market.btc_sensor and any(token in market.btc_sensor.lower() for token in ("negative", "弱", "divergence")):
        flags.append("btc_negative_divergence")
    if _strength(market.downdrafts.get("gold", 0)) >= 0.6 and _strength(market.downdrafts.get("commodity", 0)) >= 0.6:
        flags.append("gold_commodity_weakness")

    # 小幅な局面適合補正に限定し、必ず 0.90..1.10 に収める。
    adjustments = {asset: 1.0 for asset in ASSETS}
    for asset in ("VT", "BTC", "XLRE"):
        adjustments[asset] += (air["growth"] - 0.5) * 0.12
    for asset in ("TLT", "BNDX", "GLDM"):
        adjustments[asset] += (air["defense"] - 0.5) * 0.12
    for asset in ("TIP", "DBC", "GLDM"):
        adjustments[asset] += (air["inflation"] - 0.5) * 0.12
    adjustments = {asset: round(max(0.90, min(1.10, value)), 3) for asset, value in adjustments.items()}

    priority = {
        "成長・攻撃": "高" if air["growth"] >= 0.65 else "通常",
        "景気後退防衛": "高" if air["defense"] >= 0.65 else "通常",
        "インフレ防衛": "高" if air["inflation"] >= 0.65 else "通常",
    }
    notes: dict[str, str] = {}
    if "btc_negative_divergence" in flags: notes["BTC"] = "BTCセンサーに負の乖離。役割健全性を継続確認する。"
    if "gold_commodity_weakness" in flags:
        notes["GLDM"] = "金と商品に弱さ。市場気象だけで役割不全とは判定しない。"
        notes["DBC"] = "金と商品に弱さ。インフレ防衛機能を次回確認する。"
    flag_summary = "、".join(MARKET_CONTEXT_FLAG_LABELS_JA[flag] for flag in flags) if flags else "顕著な気象フラグなし"
    summary = f"Market Amedas市場文脈：{flag_summary}。市場気象は売却判断に直結させない。"
    return MarketContext(summary, flags, priority, adjustments, notes)
