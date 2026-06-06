"""Market Amedas を弱い外部文脈へ変換する安全なアダプター。"""

from __future__ import annotations

from .models import MarketAmedasInput, MarketContext

ASSETS = ("VT", "BTC", "TLT", "TIP", "GLDM", "XLRE", "BNDX", "DBC")
AIR_MASS_LABELS_JA = {"yield": "利回り気団", "growth": "成長気団", "defense": "防衛気団", "inflation": "インフレ気団"}
FLOW_LABELS_JA = {
    "vt": "世界株式", "btc": "BTC", "tlt": "米国長期国債", "tip": "物価連動債", "gldm": "金",
    "xlre": "米国不動産", "bndx": "国際債券", "dbc": "商品", "gold": "金", "commodity": "商品",
    "smallcap": "小型株", "junk": "低格付け債", "usd": "米ドル", "oil": "原油",
}
MARKET_CONTEXT_FLAG_LABELS_JA = {
    "neutral_market_context": "中立市場文脈", "yield_air_mass_dominant": "利回り気団が優勢",
    "growth_air_mass_strong": "成長気団が強い", "defense_air_mass_absent": "防衛気団が弱い",
    "inflation_air_mass_absent": "インフレ気団が弱い", "junk_oxygen_healthy": "低格付け信用環境は健全",
    "smallcap_geothermal_warm": "小型株環境は温暖", "btc_negative_divergence": "BTCに負の乖離",
    "gold_commodity_weakness": "金・商品が弱い",
}


def _strength(value: float) -> float:
    """0..1 と 0..100 の入力を 0..1 に正規化する。"""
    return max(0.0, min(1.0, float(value) / 100 if abs(float(value)) > 1 else float(value)))


def _strength_label(value: float) -> str:
    if value >= 0.70: return "強い"
    if value >= 0.55: return "やや強い"
    if value > 0.45: return "中立"
    if value > 0.30: return "やや弱い"
    return "弱い"


def _top_flows(flows: dict[str, float], limit: int = 5) -> list[dict[str, float | str]]:
    ranked = sorted(((str(name), _strength(value)) for name, value in flows.items()), key=lambda item: item[1], reverse=True)
    return [{"name": FLOW_LABELS_JA.get(name.lower(), name), "strength": round(value * 100, 1)} for name, value in ranked[:limit]]


def adapt_market_context(market: MarketAmedasInput | None) -> MarketContext:
    """市場気象を文脈化する。結果は運用判断レベルを直接決定しない。"""
    if market is None:
        return MarketContext(
            "Market Amedas入力なし。中立の市場文脈で監査した。", ["neutral_market_context"], {},
            {asset: 1.0 for asset in ASSETS}, {}, {}, {}, [], [], "",
        )

    air = {key: _strength(market.air_mass.get(key, 0.5)) for key in AIR_MASS_LABELS_JA}
    air_total = sum(air.values())
    ratios = {AIR_MASS_LABELS_JA[key]: round(value / air_total * 100, 1) if air_total else 25.0 for key, value in air.items()}
    strengths = {AIR_MASS_LABELS_JA[key]: f"{_strength_label(value)}（{value * 100:.1f}）" for key, value in air.items()}
    flags: list[str] = []
    if air["yield"] >= 0.65: flags.append("yield_air_mass_dominant")
    if air["growth"] >= 0.65: flags.append("growth_air_mass_strong")
    if air["defense"] <= 0.35: flags.append("defense_air_mass_absent")
    if air["inflation"] <= 0.35: flags.append("inflation_air_mass_absent")

    atmos = {str(k).lower(): str(v).lower() for k, v in market.atmospheric_conditions.items()}
    if "healthy" in atmos.get("junk_oxygen", ""): flags.append("junk_oxygen_healthy")
    if "warm" in atmos.get("smallcap_geothermal", ""): flags.append("smallcap_geothermal_warm")
    btc_negative = bool(market.btc_sensor and any(token in market.btc_sensor.lower() for token in ("negative", "弱", "divergence", "逆行")))
    if btc_negative: flags.append("btc_negative_divergence")
    if _strength(market.downdrafts.get("gold", 0)) >= 0.6 and _strength(market.downdrafts.get("commodity", 0)) >= 0.6:
        flags.append("gold_commodity_weakness")

    # 小幅な局面適合補正に限定し、必ず 0.90..1.10 に収める。
    adjustments = {asset: 1.0 for asset in ASSETS}
    for asset in ("VT", "BTC", "XLRE"): adjustments[asset] += (air["growth"] - 0.5) * 0.12
    for asset in ("TLT", "BNDX", "GLDM"): adjustments[asset] += (air["defense"] - 0.5) * 0.12
    for asset in ("TIP", "DBC", "GLDM"): adjustments[asset] += (air["inflation"] - 0.5) * 0.12
    adjustments = {asset: round(max(0.90, min(1.10, value)), 3) for asset, value in adjustments.items()}

    priority = {
        "成長・攻撃": "高" if air["growth"] >= 0.65 else "通常", "景気後退防衛": "高" if air["defense"] >= 0.65 else "通常",
        "インフレ防衛": "高" if air["inflation"] >= 0.65 else "通常",
    }
    notes: dict[str, str] = {}
    btc_note = ""
    if btc_negative:
        notes["BTC"] = "BTCセンサーに負の乖離。役割健全性を継続確認する。"
        if air["growth"] >= 0.65:
            btc_note = "BTCは成長気団が強い中で逆行しているため、次回監査で成長資産としての再連動を確認する。"
    if "gold_commodity_weakness" in flags:
        notes["GLDM"] = "金と商品に弱さ。市場気象だけで役割不全とは判定しない。"
        notes["DBC"] = "金と商品に弱さ。インフレ防衛機能を次回確認する。"
    flag_summary = "、".join(MARKET_CONTEXT_FLAG_LABELS_JA[flag] for flag in flags) if flags else "顕著な気象フラグなし"
    summary = f"Market Amedas市場文脈：{flag_summary}。市場気象は売却判断に直結させない。"
    return MarketContext(summary, flags, priority, adjustments, notes, ratios, strengths, _top_flows(market.updrafts), _top_flows(market.downdrafts), btc_note)
