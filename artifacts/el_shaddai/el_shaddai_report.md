# El Shaddai Health Diagnostic Report

Data sources: prices=deterministic built-in sample price history; roles=neutral built-in role proxy inputs

## Asset Scores

| asset | price_score | role_score | el_shaddai_score | label | main_reason | data_date |
| --- | ---: | ---: | ---: | --- | --- | --- |
| VT | 93.04 | N/A | 93.04 | Spot Buy Candidate | RSI=0.0; 200DMA deviation=-16.9%; 52w range position=0.0 | 2026-06-03 |
| BNDX | 90.25 | 50.00 | 50.00 | Neutral | RSI=0.0; 200DMA deviation=-12.3%; 52w range position=0.0; role: dxy [core] proxy=+0.00 => 50.0; us_10y_yield [core] proxy=+0.00 => 50.0 | 2026-06-03 |
| TLT | 62.43 | 50.00 | 50.00 | Neutral | RSI=100.0; 200DMA deviation=-4.9%; 52w range position=7.4; role: recession_pressure [core] proxy=+0.00 => 50.0; us_10y_yield [support] proxy=+0.00 => 50.0 | 2026-06-03 |
| TIP | 36.50 | 50.00 | 36.50 | Weak | RSI=100.0; 200DMA deviation=1.5%; 52w range position=55.6; role: inflation_threat [core] proxy=+0.00 => 50.0; inflation_expectation_gap [core] proxy=+0.00 => 50.0 | 2026-06-03 |
| XLRE | 36.31 | 50.00 | 36.31 | Weak | RSI=33.4; 200DMA deviation=3.8%; 52w range position=95.6; role: reit_trend [core] proxy=+0.00 => 50.0; interest_rate_pressure [core] proxy=+0.00 => 50.0 | 2026-06-03 |
| GLDM | 46.03 | 50.00 | 46.03 | Neutral | RSI=0.0; 200DMA deviation=2.2%; 52w range position=77.6; role: safe_haven_pressure [core] proxy=+0.00 => 50.0; real_rate [context] proxy=+0.00 => 50.0 | 2026-06-03 |
| DBC | 53.13 | 50.00 | 50.00 | Neutral | RSI=0.0; 200DMA deviation=0.3%; 52w range position=65.3; role: crb [core] proxy=+0.00 => 50.0; gsci [core] proxy=+0.00 => 50.0 | 2026-06-03 |
| BTC | 27.80 | N/A | 27.80 | Not Attractive | RSI=100.0; 200DMA deviation=1.3%; 52w range position=75.1 | 2026-06-03 |

## Role Component Weights

| asset | component | weight | group |
| --- | --- | ---: | --- |
| BNDX | dxy | 0.25 | core |
| BNDX | us_10y_yield | 0.25 | core |
| BNDX | global_bond_trend | 0.30 | core |
| BNDX | fx_environment | 0.20 | core |
| TLT | recession_pressure | 0.20 | core |
| TLT | us_10y_yield | 0.10 | support |
| TLT | us_30y_yield | 0.10 | support |
| TLT | yield_curve | 0.15 | core |
| TLT | real_rate | 0.15 | core |
| TLT | debt_sustainability | 0.10 | risk_penalty |
| TLT | interest_burden | 0.10 | risk_penalty |
| TLT | foreign_demand | 0.10 | risk_penalty |
| TIP | inflation_threat | 0.18 | core |
| TIP | inflation_expectation_gap | 0.18 | core |
| TIP | purchasing_power_protection | 0.18 | core |
| TIP | stagflation_pressure | 0.11 | support |
| TIP | inflation_regime_strength | 0.11 | support |
| TIP | real_rate_shock | 0.08 | risk_penalty |
| TIP | deflation_pressure | 0.08 | risk_penalty |
| TIP | macro_submission | 0.08 | risk_penalty |
| GLDM | safe_haven_pressure | 0.15 | core |
| GLDM | real_rate | 0.10 | context |
| GLDM | dxy | 0.10 | context |
| GLDM | central_bank_buying | 0.10 | context |
| GLDM | geopolitical_risk | 0.10 | context |
| GLDM | inflation_regime | 0.10 | core |
| GLDM | currency_hedge | 0.10 | core |
| GLDM | liquidity_regime | 0.10 | support |
| GLDM | macro_independence | 0.10 | core |
| GLDM | dominant_anchor_strength | 0.05 | support |
| XLRE | reit_trend | 0.40 | core |
| XLRE | interest_rate_pressure | 0.35 | core |
| XLRE | sector_relative_strength | 0.25 | core |
| DBC | crb | 0.20 | core |
| DBC | gsci | 0.20 | core |
| DBC | bcom | 0.20 | core |
| DBC | oil | 0.15 | core |
| DBC | metals | 0.15 | core |
| DBC | agriculture | 0.10 | core |

## Genki-dama Candidate Ranking

| rank | asset | score | label |
| ---: | --- | ---: | --- |
| 1 | VT | 93.04 | Spot Buy Candidate |
| 2 | BNDX | 50.00 | Neutral |
| 3 | TLT | 50.00 | Neutral |
| 4 | DBC | 50.00 | Neutral |
| 5 | GLDM | 46.03 | Neutral |
| 6 | TIP | 36.50 | Weak |
| 7 | XLRE | 36.31 | Weak |
| 8 | BTC | 27.80 | Not Attractive |

## Score Details

### VT

Price components: {'rsi': 100.0, 'dma_200_deviation': 83.86814220486723, 'range_52w_position': 100.0, 'z_score': 100.0, 'weekly_drawdown': 62.70590306135, 'range_5y_position': 100.0}
Price reasons: RSI=0.0; 200DMA deviation=-16.9%; 52w range position=0.0; z-score=-3.33; weekly return=-2.5%; 5y range position=0.0
Role components: N/A
Role raw_weighted_score: N/A
Role penalty_adjusted_score: N/A
Role core_score: N/A
Role support_score: N/A
Role penalty_score: N/A
Role applied_caps: N/A
Role interpretation: N/A
Role reasons: Role diagnosis is not applied to permanent holding assets.

### BNDX

Price components: {'rsi': 100.0, 'dma_200_deviation': 74.50863366398004, 'range_52w_position': 100.0, 'z_score': 100.0, 'weekly_drawdown': 53.50103484721986, 'range_5y_position': 100.0}
Price reasons: RSI=0.0; 200DMA deviation=-12.3%; 52w range position=0.0; z-score=-2.70; weekly return=-0.7%; 5y range position=0.0
Role components: {'dxy': 50.0, 'us_10y_yield': 50.0, 'global_bond_trend': 50.0, 'fx_environment': 50.0}
Role raw_weighted_score: 50.0
Role penalty_adjusted_score: 50.0
Role core_score: 50.0
Role support_score: None
Role penalty_score: None
Role applied_caps: []
Role interpretation: Role Score uses component weights; all components are treated as core for v1.5 structure.
Role reasons: dxy [core] proxy=+0.00 => 50.0; us_10y_yield [core] proxy=+0.00 => 50.0; global_bond_trend [core] proxy=+0.00 => 50.0; fx_environment [core] proxy=+0.00 => 50.0; raw_weighted_score=50.00; penalty_adjusted_score=50.00; core_score=50.00; support_score=N/A; penalty_score=N/A; role_interpretation=Role Score uses component weights; all components are treated as core for v1.5 structure.

### TLT

Price components: {'rsi': 0.0, 'dma_200_deviation': 59.804930640397735, 'range_52w_position': 92.5728757865133, 'z_score': 87.86266886140336, 'weekly_drawdown': 47.74120965390723, 'range_5y_position': 93.3258115470166}
Price reasons: RSI=100.0; 200DMA deviation=-4.9%; 52w range position=7.4; z-score=-1.51; weekly return=0.5%; 5y range position=6.7
Role components: {'recession_pressure': 50.0, 'us_10y_yield': 50.0, 'us_30y_yield': 50.0, 'yield_curve': 50.0, 'real_rate': 50.0, 'debt_sustainability': 50.0, 'interest_burden': 50.0, 'foreign_demand': 50.0}
Role raw_weighted_score: 50.0
Role penalty_adjusted_score: 50.0
Role core_score: 50.0
Role support_score: 50.0
Role penalty_score: 50.0
Role applied_caps: []
Role interpretation: raw_weighted=50.00; structured core/support/context/penalty aggregation applied for TLT.
Role reasons: recession_pressure [core] proxy=+0.00 => 50.0; us_10y_yield [support] proxy=+0.00 => 50.0; us_30y_yield [support] proxy=+0.00 => 50.0; yield_curve [core] proxy=+0.00 => 50.0; real_rate [core] proxy=+0.00 => 50.0; debt_sustainability [risk_penalty] proxy=+0.00 => 50.0; interest_burden [risk_penalty] proxy=+0.00 => 50.0; foreign_demand [risk_penalty] proxy=+0.00 => 50.0; raw_weighted_score=50.00; penalty_adjusted_score=50.00; core_score=50.00; support_score=50.00; penalty_score=50.00; role_interpretation=raw_weighted=50.00; structured core/support/context/penalty aggregation applied for TLT.

### TIP

Price components: {'rsi': 0.0, 'dma_200_deviation': 47.00004425781765, 'range_52w_position': 44.41400108492781, 'z_score': 45.06481737222107, 'weekly_drawdown': 47.97259694210805, 'range_5y_position': 44.41400108492781}
Price reasons: RSI=100.0; 200DMA deviation=1.5%; 52w range position=55.6; z-score=0.20; weekly return=0.4%; 5y range position=55.6
Role components: {'inflation_threat': 50.0, 'inflation_expectation_gap': 50.0, 'purchasing_power_protection': 50.0, 'stagflation_pressure': 50.0, 'inflation_regime_strength': 50.0, 'real_rate_shock': 50.0, 'deflation_pressure': 50.0, 'macro_submission': 50.0}
Role raw_weighted_score: 50.0
Role penalty_adjusted_score: 50.0
Role core_score: 50.0
Role support_score: 50.0
Role penalty_score: 50.0
Role applied_caps: []
Role interpretation: raw_weighted=50.00; structured core/support/context/penalty aggregation applied for TIP.
Role reasons: inflation_threat [core] proxy=+0.00 => 50.0; inflation_expectation_gap [core] proxy=+0.00 => 50.0; purchasing_power_protection [core] proxy=+0.00 => 50.0; stagflation_pressure [support] proxy=+0.00 => 50.0; inflation_regime_strength [support] proxy=+0.00 => 50.0; real_rate_shock [risk_penalty] proxy=+0.00 => 50.0; deflation_pressure [risk_penalty] proxy=+0.00 => 50.0; macro_submission [risk_penalty] proxy=+0.00 => 50.0; raw_weighted_score=50.00; penalty_adjusted_score=50.00; core_score=50.00; support_score=50.00; penalty_score=50.00; role_interpretation=raw_weighted=50.00; structured core/support/context/penalty aggregation applied for TIP.

### XLRE

Price components: {'rsi': 91.56215161649928, 'dma_200_deviation': 42.45986422915418, 'range_52w_position': 4.399679755583435, 'z_score': 19.044184162111467, 'weekly_drawdown': 51.508274302041755, 'range_5y_position': 4.127030713188063}
Price reasons: RSI=33.4; 200DMA deviation=3.8%; 52w range position=95.6; z-score=1.24; weekly return=-0.3%; 5y range position=95.9
Role components: {'reit_trend': 50.0, 'interest_rate_pressure': 50.0, 'sector_relative_strength': 50.0}
Role raw_weighted_score: 50.0
Role penalty_adjusted_score: 50.0
Role core_score: 50.0
Role support_score: None
Role penalty_score: None
Role applied_caps: []
Role interpretation: Role Score uses component weights; all components are treated as core for v1.5 structure.
Role reasons: reit_trend [core] proxy=+0.00 => 50.0; interest_rate_pressure [core] proxy=+0.00 => 50.0; sector_relative_strength [core] proxy=+0.00 => 50.0; raw_weighted_score=50.00; penalty_adjusted_score=50.00; core_score=50.00; support_score=N/A; penalty_score=N/A; role_interpretation=Role Score uses component weights; all components are treated as core for v1.5 structure.

### GLDM

Price components: {'rsi': 100.0, 'dma_200_deviation': 45.543121622284, 'range_52w_position': 22.4194758100585, 'z_score': 27.0658474650627, 'weekly_drawdown': 53.92855381285079, 'range_5y_position': 19.930998201548803}
Price reasons: RSI=0.0; 200DMA deviation=2.2%; 52w range position=77.6; z-score=0.92; weekly return=-0.8%; 5y range position=80.1
Role components: {'safe_haven_pressure': 50.0, 'real_rate': 50.0, 'dxy': 50.0, 'central_bank_buying': 50.0, 'geopolitical_risk': 50.0, 'inflation_regime': 50.0, 'currency_hedge': 50.0, 'liquidity_regime': 50.0, 'macro_independence': 50.0, 'dominant_anchor_strength': 50.0}
Role raw_weighted_score: 50.0
Role penalty_adjusted_score: 50.0
Role core_score: 50.0
Role support_score: 50.0
Role penalty_score: None
Role applied_caps: []
Role interpretation: raw_weighted=50.00; structured core/support/context/penalty aggregation applied for GLDM.
Role reasons: safe_haven_pressure [core] proxy=+0.00 => 50.0; real_rate [context] proxy=+0.00 => 50.0; dxy [context] proxy=+0.00 => 50.0; central_bank_buying [context] proxy=+0.00 => 50.0; geopolitical_risk [context] proxy=+0.00 => 50.0; inflation_regime [core] proxy=+0.00 => 50.0; currency_hedge [core] proxy=+0.00 => 50.0; liquidity_regime [support] proxy=+0.00 => 50.0; macro_independence [core] proxy=+0.00 => 50.0; dominant_anchor_strength [support] proxy=+0.00 => 50.0; raw_weighted_score=50.00; penalty_adjusted_score=50.00; core_score=50.00; support_score=50.00; penalty_score=N/A; role_interpretation=raw_weighted=50.00; structured core/support/context/penalty aggregation applied for GLDM.

### DBC

Price components: {'rsi': 100.0, 'dma_200_deviation': 49.45373633729315, 'range_52w_position': 34.71576227390186, 'z_score': 39.16125549738895, 'weekly_drawdown': 52.1421640897693, 'range_5y_position': 34.71576227390186}
Price reasons: RSI=0.0; 200DMA deviation=0.3%; 52w range position=65.3; z-score=0.43; weekly return=-0.4%; 5y range position=65.3
Role components: {'crb': 50.0, 'gsci': 50.0, 'bcom': 50.0, 'oil': 50.0, 'metals': 50.0, 'agriculture': 50.0}
Role raw_weighted_score: 50.0
Role penalty_adjusted_score: 50.0
Role core_score: 50.0
Role support_score: None
Role penalty_score: None
Role applied_caps: []
Role interpretation: Role Score uses component weights; all components are treated as core for v1.5 structure.
Role reasons: crb [core] proxy=+0.00 => 50.0; gsci [core] proxy=+0.00 => 50.0; bcom [core] proxy=+0.00 => 50.0; oil [core] proxy=+0.00 => 50.0; metals [core] proxy=+0.00 => 50.0; agriculture [core] proxy=+0.00 => 50.0; raw_weighted_score=50.00; penalty_adjusted_score=50.00; core_score=50.00; support_score=N/A; penalty_score=N/A; role_interpretation=Role Score uses component weights; all components are treated as core for v1.5 structure.

### BTC

Price components: {'rsi': 0.0, 'dma_200_deviation': 47.45145140663607, 'range_52w_position': 24.901498832111656, 'z_score': 32.783575976580885, 'weekly_drawdown': 46.80900894478097, 'range_5y_position': 24.901498832111656}
Price reasons: RSI=100.0; 200DMA deviation=1.3%; 52w range position=75.1; z-score=0.69; weekly return=0.6%; 5y range position=75.1
Role components: N/A
Role raw_weighted_score: N/A
Role penalty_adjusted_score: N/A
Role core_score: N/A
Role support_score: N/A
Role penalty_score: N/A
Role applied_caps: N/A
Role interpretation: N/A
Role reasons: Role diagnosis is not applied to permanent holding assets.
