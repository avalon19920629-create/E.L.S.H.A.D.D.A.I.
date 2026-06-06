"""Market Amedas の実測値を、弱い外部文脈へ変換する安全なアダプター。"""

from __future__ import annotations

from .models import MarketAmedasInput, MarketContext

ASSETS = ("VT", "BTC", "TLT", "TIP", "GLDM", "XLRE", "BNDX", "DBC")
AIR_MASS_LABELS_JA = {"yield": "利回り気団", "growth": "成長気団", "defense": "防衛気団", "inflation": "インフレ気団"}
FLOW_LABELS_JA = {
    "vt": "世界株式", "btc": "BTC", "tlt": "長期債", "tip": "物価連動", "gldm": "金", "xlre": "REIT",
    "bndx": "国際債券", "dbc": "商品", "gold": "金", "commodity": "商品", "cash": "現金",
    "value": "バリュー", "nasdaq": "ナスダック", "high_dividend": "高配当", "reit": "REIT", "us_equity": "米国株",
    "smallcap": "小型株", "junk": "ジャンク", "developed": "先進国", "emerging": "新興国", "corporate_bond": "社債",
    "inflation_linked": "物価連動", "usd": "米ドル", "oil": "原油",
}
MARKET_CONTEXT_FLAG_LABELS_JA = {
    "neutral_market_context": "中立市場文脈", "yield_air_mass_dominant": "利回り気団が強い",
    "growth_air_mass_strong": "成長気団が強い", "defense_air_mass_absent": "防衛気団が弱い",
    "inflation_air_mass_absent": "インフレ気団が弱い", "usd_wind_calm": "米ドルは凪",
    "junk_oxygen_healthy": "低格付け信用環境は健全", "smallcap_geothermal_warm": "小型株環境は温暖",
    "btc_negative_divergence": "BTCに負の乖離", "gold_commodity_weakness": "金・商品が弱い",
}


def _strength(value: float) -> float:
    """0..1 と 0..100 の気団入力を、内部計算用 0..1 に正規化する。"""
    return max(0.0, min(1.0, float(value) / 100 if abs(float(value)) > 1 else float(value)))


def _observed_percent(value: float) -> float:
    """ユーザー向け表示では、入力された観測比率を百分率として保持する。"""
    value = float(value)
    return value * 100 if abs(value) <= 1 else value


def _strength_label(value: float) -> str:
    if value >= 0.70: return "強い"
    if value >= 0.55: return "やや強い"
    if value > 0.45: return "中立"
    if value > 0.30: return "やや弱い"
    return "弱い"


def _top_flows(flows: dict[str, float], *, descending: bool, limit: int = 5) -> list[dict[str, float | str]]:
    """符号付き実測値を保ったまま、上昇流または下降流を順位化する。"""
    ranked = sorted(((str(name), float(value)) for name, value in flows.items()), key=lambda item: item[1], reverse=descending)
    return [{"name": FLOW_LABELS_JA.get(name.lower(), name), "observed_value": value} for name, value in ranked[:limit]]


def adapt_market_context(market: MarketAmedasInput | None) -> MarketContext:
    """市場気象を文脈化する。市場文脈は負傷判定や売却判断を直接決定しない。"""
    if market is None:
        return MarketContext(
            "Market Amedas入力なし。中立の市場文脈で監査した。", ["neutral_market_context"], {},
            {asset: 1.0 for asset in ASSETS}, {}, {}, {}, [], [], "", [], "",
        )

    raw_air = {key: float(market.air_mass.get(key, 0.5)) for key in AIR_MASS_LABELS_JA}
    # 合計が百分率スケールなら 0.7 も 0.7% と解釈し、入力観測値をそのまま保持する。
    percentage_scale = sum(abs(value) for value in raw_air.values()) > 4.0
    air = {key: max(0.0, min(1.0, value / 100 if percentage_scale else value)) for key, value in raw_air.items()}
    observed_ratios = {AIR_MASS_LABELS_JA[key]: round(value if percentage_scale else value * 100, 1) for key, value in raw_air.items()}
    leaders = sorted(air, key=air.get, reverse=True)[:2]
    strengths = {
        AIR_MASS_LABELS_JA[key]: (f"強い（相対主導・内部正規化値 {value * 100:.1f}）" if key in leaders and value >= 0.40 else f"{_strength_label(value)}（内部正規化値 {value * 100:.1f}）")
        for key, value in air.items()
    }
    flags: list[str] = []
    # 絶対強度に加えて、今回のような相対主導気団も「強い」として文脈化する。
    if air["yield"] >= 0.65 or ("yield" in leaders and air["yield"] >= 0.40): flags.append("yield_air_mass_dominant")
    if air["growth"] >= 0.65 or ("growth" in leaders and air["growth"] >= 0.40): flags.append("growth_air_mass_strong")
    if air["defense"] <= 0.35: flags.append("defense_air_mass_absent")
    if air["inflation"] <= 0.35: flags.append("inflation_air_mass_absent")

    atmos = {str(k).lower(): str(v).lower() for k, v in market.atmospheric_conditions.items()}
    usd_condition = atmos.get("usd_wind", atmos.get("米ドル風向き", ""))
    junk_condition = atmos.get("junk_oxygen", atmos.get("ジャンク酸素濃度", ""))
    smallcap_condition = atmos.get("smallcap_geothermal", atmos.get("小型株地熱", ""))
    if any(token in usd_condition for token in ("calm", "凪", "影響なし")): flags.append("usd_wind_calm")
    if any(token in junk_condition for token in ("healthy", "normal", "正常", "健全")): flags.append("junk_oxygen_healthy")
    if any(token in smallcap_condition for token in ("warm", "温暖", "本物")): flags.append("smallcap_geothermal_warm")

    btc_negative = bool(market.btc_sensor and any(token in market.btc_sensor.lower() for token in ("negative", "弱", "divergence", "逆行"))) or float(market.downdrafts.get("BTC", market.downdrafts.get("btc", 0))) < 0
    if btc_negative: flags.append("btc_negative_divergence")
    if float(market.downdrafts.get("gold", market.downdrafts.get("金", 0))) < 0 and float(market.downdrafts.get("commodity", market.downdrafts.get("商品", 0))) < 0:
        flags.append("gold_commodity_weakness")

    # 小幅な局面適合補正に限定し、必ず 0.90..1.10 に収める。
    adjustments = {asset: 1.0 for asset in ASSETS}
    for asset in ("VT", "BTC", "XLRE"): adjustments[asset] += (air["growth"] - 0.5) * 0.12
    for asset in ("TLT", "BNDX", "GLDM"): adjustments[asset] += (air["defense"] - 0.5) * 0.12
    for asset in ("TIP", "DBC", "GLDM"): adjustments[asset] += (air["inflation"] - 0.5) * 0.12
    adjustments = {asset: round(max(0.90, min(1.10, value)), 3) for asset, value in adjustments.items()}

    priority = {"成長・攻撃": "高" if "growth_air_mass_strong" in flags else "通常", "景気後退防衛": "高" if air["defense"] >= 0.65 else "通常", "インフレ防衛": "高" if air["inflation"] >= 0.65 else "通常"}
    notes: dict[str, str] = {}
    btc_note = ""
    if btc_negative:
        notes["BTC"] = "BTCは下降流。市場文脈だけで負傷とは判定せず、役割健全性を継続確認する。"
        if "growth_air_mass_strong" in flags: btc_note = "BTCは成長気団が強い中で下降流にあるため、次回監査で成長資産としての再連動を確認する。"
    if "gold_commodity_weakness" in flags:
        notes["GLDM・DBC"] = "金・商品は下降流。弱さが局面不適合か役割劣化かを次回監査で確認する。"

    narratives = [
        f"利回り気団 {observed_ratios['利回り気団']:.1f}% と成長気団 {observed_ratios['成長気団']:.1f}% が市場を主導している。",
        f"防衛気団 {observed_ratios['防衛気団']:.1f}% とインフレ気団 {observed_ratios['インフレ気団']:.1f}% は非常に弱く、現在は防衛資産・インフレ防衛資産の出番が少ない局面である。",
    ]
    conditions = []
    if "usd_wind_calm" in flags: conditions.append("米ドルは凪で、強いドル逆風は出ていない")
    if "junk_oxygen_healthy" in flags: conditions.append("低格付け信用環境は健全")
    if "smallcap_geothermal_warm" in flags: conditions.append("小型株環境は温暖で、景気回復期待は維持されている")
    if conditions: narratives.append("。".join(conditions) + "。")
    flag_summary = "、".join(MARKET_CONTEXT_FLAG_LABELS_JA[flag] for flag in flags) if flags else "顕著な気象フラグなし"
    summary = f"Market Amedas市場文脈：{flag_summary}。市場気象は売却判断に直結させない。"
    return MarketContext(summary, flags, priority, adjustments, notes, observed_ratios, strengths, _top_flows(market.updrafts, descending=True), _top_flows(market.downdrafts, descending=False), btc_note, narratives, market.btc_sensor or "入力なし")
