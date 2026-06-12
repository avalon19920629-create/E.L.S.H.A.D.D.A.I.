# El Shaddai 健全度診断システム v2.0

El Shaddai は、三体戦略における監査対象資産を **Permanent Holdings / Value Opportunity Only** と **Role-Audited Assets** に分け、説明可能性を優先して診断する監査システムです。v2.0 では既存の資産別監査に L.U.M.U.S.-8 統合監査層を追加し、役割健全性と助言専用の運用判断を日本語で提示します。売買予測やブラックボックスの機械学習、自動売買は行いません。

v2.0 は「実運用完成版」ではなく、透明性・説明可能性・監査可能性・将来拡張性を優先した器です。

## 対象アセットの分類

### Permanent Holdings / Value Opportunity Only

- VT
- BTC

VT と BTC は永年保有資産として扱います。El Shaddai はこれらについて、Role 診断を意図的に適用せず、スポット買い好機（Value Opportunity）のみを判定します。

### Role-Audited Assets

- BNDX
- TLT
- TIP
- XLRE
- GLDM
- DBC

Role-Audited Assets については、Price × Role によって、価格魅力度と本来の役割を果たしているかを保守的に監査します。

## スコア計算ロジック

### Price Score

全アセットに適用します。高いほど、悲観・割安・追加投資妙味が高い状態です。

v1.5 の Price Score は、RSI、200DMA 乖離率、52週レンジ位置、Z-score、週足下落率、過去5年レンジ位置に基づく **価格履歴ベースのテクニカル初期スコア** です。VT 向けの CAPE、Fear & Greed、VIX、Market Cap / GDP、BTC 向けの MVRV、Puell Multiple、Reserve Risk などは未統合です。そのため、Price Score は本来目指す「バリュー/センチメント診断」の初期版として扱ってください。

| 指標 | 重み | 方向性 |
| --- | ---: | --- |
| RSI | 20% | RSI 30 以下を魅力的、70 以上を非魅力的に近づける |
| 200DMA 乖離率 | 20% | 200 日移動平均を大きく下回るほど高得点 |
| 52 週レンジ位置 | 20% | レンジ下限に近いほど高得点 |
| Z-score | 15% | 直近 252 日平均との差がマイナス方向に大きいほど高得点 |
| 週足下落率 | 10% | 直近 1 週間の下落が大きいほど高得点 |
| 過去 5 年レンジ位置 | 15% | 長期レンジ下限に近いほど高得点 |

欠損した指標は除外し、利用可能な指標だけで重みを再正規化します。価格履歴がまったくない場合は中立の 50 点を返します。

### Role Score

BNDX、TLT、TIP、XLRE、GLDM、DBC に適用します。入力値は監査可能な -2〜+2 のプロキシ値です。スコア変換は `50 + proxy * 25` で、0〜100 にクリップします。

Role proxy は、各アセットの役割に対して **符号調整済みの値** として入力します。+2 はその資産の Role にとって非常に好ましい状態、0 は中立、-2 は Role を大きく毀損する状態です。実質金利や DXY など、原系列の上昇が常に良いとは限らないため、外部入力時には必ず Role に対する方向性へ変換してください。

初期版は中立の built-in proxy を採用します。必要に応じて `--role-inputs-json` で外部 JSON を渡してください。Role proxy が全て中立の場合、HTML ダッシュボードは「まだ実運用 Role 監査ではない」旨の警告を表示します。

### 総合スコア

- VT/BTC: `value_opportunity_score = price_score`
- その他: `el_shaddai_score = min(price_score, role_score)`

保守的に、価格魅力度と役割健全性の弱い方に合わせます。



## Role Score aggregation（v1.7）

El Shaddai v1.7 の Role Score は、単純平均ではなく、資産ごとの Role structure に基づく監査スコアです。各 component は `core` / `support` / `context` / `risk_penalty` に分類され、Markdown レポートの `Role Component Weights` に weight と group が一覧出力されます。

TLT structure:

- Core: `recession_pressure`, `yield_curve`, `real_rate`
- Support: `us_10y_yield`, `us_30y_yield`
- Risk Penalty: `debt_sustainability`, `interest_burden`, `foreign_demand`

GLDM structure:

- Core: `macro_independence`, `currency_hedge`, `safe_haven_pressure`, `inflation_regime`
- Support: `liquidity_regime`, `dominant_anchor_strength`
- Neutral/context placeholder: `central_bank_buying`, `geopolitical_risk`, `real_rate`, `dxy`

Risk Penalty は平均で薄めません。TLT では `risk_penalty` component が複数 severe（score <= 25）になった場合、Role Score に cap を適用します。Score Details には `raw_weighted_score`, `penalty_adjusted_score`, `core_score`, `support_score`, `penalty_score`, `applied_caps`, `role_interpretation` が出力されます。

## BNDX A.T.L.A.S. adapter（v1.8）

El Shaddai v1.8 では、BNDX Role Score に A.T.L.A.S.（Advanced Tracker for Liquidity And Sovereign-health）adapter を接続できます。A.T.L.A.S. は BNDX を危機時の「城壁」ではなく、長い Winter を耐えるための「Winter Blanket」として監査します。目的は「債券が魅力的か」ではなく、「グローバル sovereign-credit structure が文明を冬の間支え続けられるか」を判定することです。

A.T.L.A.S. の Four Pillars:

- `sovereign_trust`: 政府債務・ソブリン信用への信頼。
- `currency_order`: 為替ヘッジと準備通貨秩序の安定性。
- `liquidity_flow`: 債券市場と信用循環の流動性。
- `diversification_integrity`: BNDX が TLT とは別の国際分散価値を保っているか。

BNDX Role structure:

- Core: `sovereign_trust`, `currency_order`, `liquidity_flow`, `diversification_integrity`
- Support: `fx_hedge_value`, `global_bond_trend`, `sovereign_stability`
- Risk Penalty: `hedge_cost_pressure`, `global_credit_stress`, `sovereign_stress`

Structural geometry は単純平均ではありません。Four Pillars のうち severe（score <= 25）になった柱の位置で cap を適用します。

- Single pillar failure: `Atlas Strained`（cap なし）
- Diagonal failure（A+C / B+D）: `Atlas Kneeling`、Role Score 上限 50
- Adjacent failure（A+B / B+C / C+D / D+A）: `Atlas Cannot Hold`、Role Score 上限 35
- Three pillars failed: `Atlas Fallen`、Role Score 上限 20
- Four pillars failed: `Atlas Fallen`、Role Score 上限 0

実行例:

```bash
python -m el_shaddai.cli \
  --use-atlas-bndx-role \
  --output-dir artifacts/el_shaddai
```

Manual CSV route:

```bash
python -m el_shaddai.cli \
  --atlas-inputs-csv data/sample_atlas_inputs.csv \
  --output-dir artifacts/el_shaddai
```

CSV は `date` と BNDX proxy columns（-2〜+2）を持つ直接 proxy 形式、または `date,ticker,close` の long price 形式、または `date,BNDX,TLT,HYG,UUP,BND,BWX` の wide price 形式に対応します。live data / yfinance 取得失敗、ネットワーク遮断、データ不足時でも CLI は停止せず、warning を出したうえで BNDX の中立 proxy にフォールバックします。

## TLT L.O.D.E. adapter（v1.1）

v1.1 以降では、TLT Role Score に L.O.D.E.（Leading Observatory of Debt & Economic-health）adapter を接続できます。TLT の Role は「景気後退時のクッション」「長期米国債エクスポージャー」「株式リスクへのヘッジ」であるため、adapter は原系列をそのまま使わず、TLT の Role に対して方向調整済みの -2〜+2 proxy に変換します。

取得する FRED 系列:

| FRED ID | 内容 | 用途 |
| --- | --- | --- |
| T10Y2Y | 10年-2年金利差 | yield_curve / recession_pressure |
| DFII10 | 10年実質金利 | real_rate / rate-pressure proxy |
| GFDEGDQ188S | Federal Debt / GDP | debt_sustainability |
| A091RC1Q027SBEA | Federal interest payments | interest_burden の分子 |
| W006RC1Q027SBEA | Federal tax receipts | interest_burden の分母 |
| FDHBFIN | Foreign holdings of Treasury debt | foreign_demand の分子 |
| GFDEBTN | Total public debt | foreign_demand の分母 |

生成される TLT component:

- `recession_pressure`
- `us_10y_yield`
- `us_30y_yield`
- `yield_curve`
- `real_rate`
- `debt_sustainability`
- `interest_burden`
- `foreign_demand`

変換方針の概要:

- `yield_curve`: 10Y-2Y が深い逆イールドほど、景気後退保険としての TLT 需要が高まりやすいためプラス寄り。
- `real_rate`: 実質金利が高い局面は TLT 価格には逆風だが、将来の利下げ余地でもあるため、過去レンジ内の位置から中立〜プラス/マイナスへ変換。
- `debt_sustainability`: Debt/GDP が過去レンジ上限に近いほどマイナス。
- `interest_burden`: 利払い費/税収が過去レンジ上限に近いほどマイナス。
- `foreign_demand`: 外国保有比率が高い/安定しているほどプラス、低下傾向ならマイナス。

v1.1 以降の FRED 取得リストには名目 10年・30年金利が含まれていないため、`us_10y_yield` と `us_30y_yield` は DFII10 と yield curve から作る透明な近似 proxy です。将来版では名目 10年・30年金利系列を追加して置き換える想定です。



## TIP I.N.F.E.R.N.O. adapter（v1.7）

El Shaddai v1.7 では、TIP Role Score に I.N.F.E.R.N.O.（Inflation Navigation Framework for Evaluating Real-rate Neutralization Operations）adapter を接続できます。TIP の Role は「魔法防御（Magic Resistance）」、すなわち購買力防衛です。インフレ、通貨価値の希薄化、スタグフレーションから資産を守る Summer（インフレ気団）の防衛資産として監査します。

使用系列・入力候補:

| component | 主な系列・入力 | 解釈 |
| --- | --- | --- |
| inflation_threat | CPI / Core CPI / PCE / Core PCE | インフレ圧力が高いほど TIP Role にプラス |
| inflation_expectation_gap | 5Y/10Y Breakeven Inflation | CPI/PCE が breakeven を上回るほど、市場の過小評価としてプラス |
| purchasing_power_protection | TIP/TLT relative strength | TIP が購買力防衛資産として機能しているほどプラス |
| stagflation_pressure | inflation + unemployment/growth proxy | インフレ高 + 成長低下ほどプラス |
| inflation_regime_strength | DBC trend / commodity trend | Summer 気団が強いほどプラス |
| real_rate_shock | DFII10 / real yield change | 実質金利急騰は TIP 価格にマイナス |
| deflation_pressure | low inflation / low breakeven | Winter 気団が強いほどマイナス |
| macro_submission | dollar trend + real-rate change | 中央銀行・ドル・金利への服従が強いほどマイナス |

TIP Role structure:

- Core: `inflation_threat`, `inflation_expectation_gap`, `purchasing_power_protection`
- Support: `stagflation_pressure`, `inflation_regime_strength`
- Risk Penalty: `real_rate_shock`, `deflation_pressure`, `macro_submission`

Penalty caps:

- severe `real_rate_shock`: Role Score 上限 55
- severe `real_rate_shock` + severe `deflation_pressure`: Role Score 上限 45
- 3 penalty 全て severe: Role Score 上限 35

実行例:

```bash
python -m el_shaddai.cli \
  --use-inferno-tip-role \
  --output-dir artifacts/el_shaddai
```

FRED 取得失敗、ネットワーク遮断、データ不足時でも CLI は停止せず、warning を出したうえで TIP の中立 proxy にフォールバックします。

## GLDM A.U.R.A. adapter（v1.7）

El Shaddai v1.7 では、GLDM Role Score に Project A.U.R.A. adapter を接続できます。A.U.R.A. adapter は、GLD と SPY/TLT/DBC/UUP/BTC-USD のローリング相関を使い、金が現在どのレジームで動いているかを推定します。目的は金価格の予測ではなく、GLDM が「無国籍価値保存」「通貨不信ヘッジ」「実物資産防衛」として機能しているかを説明可能に監査することです。

使用ティッカー:

| ticker | anchor | 意味 |
| --- | --- | --- |
| GLD | Gold proxy | GLDM の金価格 proxy |
| SPY | Risk | 株式リスク |
| TLT | Rates | 金利・長期債 |
| DBC | Inflation | 商品・インフレ |
| UUP | Currency | 米ドル |
| BTC-USD | Liquidity | 流動性・法定通貨外資産 |

A.U.R.A. は以下の Gold Regime Index（GRI）を維持します。

```python
gri_score = corr(GLD, DBC) - corr(GLD, TLT) - corr(GLD, UUP) + corr(GLD, BTC-USD)
```

GRI は `+1.0` 超を liquidity/inflation regime、`-1.0` 未満を traditional macro/rates-dollar regime、それ以外を transition/mixed regime として解釈し、レポートに出力します。

生成される主な GLDM proxy:

- `inflation_regime`: GLD/DBC 相関が強く正ならプラス。
- `currency_hedge`: GLD/UUP 相関が低い/負ならプラス。
- `liquidity_regime`: GLD/BTC-USD 相関が強く正ならプラス。ただし極端に BTC と同一化している場合は warning。
- `macro_independence`: GLD が SPY/TLT/UUP に過度に従属していないほどプラス。
- `safe_haven_pressure`: GLD/SPY 相関が低い/負ならプラス。
- `dominant_anchor_strength`: dominant anchor の種類と絶対相関から、GLDM Role に対して方向調整。

A.U.R.A. adapter は v1.7 で実データから生成できる proxy だけを上書きし、中央銀行買付や地政学リスクなど未接続の proxy は中立のまま保持します。


## External data dependency handling（v1.7）

El Shaddai v1.7 は、外部データについて以下の 3 モードを明確に分けます。

1. **built-in neutral fallback mode**
   - 追加依存なしで実行できます。
   - Role proxy は built-in neutral values を使い、CLI は必ず成果物を生成します。
2. **manual CSV input mode**
   - `--atlas-inputs-csv data/sample_atlas_inputs.csv` で BNDX/A.T.L.A.S. proxy を CSV から生成します。
   - `--lode-inputs-csv data/sample_lode_inputs.csv` で TLT/L.O.D.E. proxy を CSV から生成します。
   - `--aura-prices-csv data/sample_aura_prices.csv` で GLDM/A.U.R.A. proxy を CSV から生成します。
   - `--oracle-inputs-csv data/sample_oracle_inputs.csv` で VT/BTC O.R.A.C.L.E. opportunity を CSV から生成します。
   - `--inferno-inputs-csv data/sample_inferno_inputs.csv` で TIP/I.N.F.E.R.N.O. proxy を CSV から生成します。
   - ネットワークや yfinance が使えない環境でも、実 proxy 生成ルートを監査できます。
3. **live data mode**
   - `--use-atlas-bndx-role` は yfinance install とネットワーク接続が必要です。
   - `--use-lode-tlt-role` は FRED endpoint へのネットワーク接続が必要です。
   - `--use-inferno-tip-role` は FRED endpoint へのネットワーク接続が必要です。
   - `--use-aura-gldm-role` は yfinance install とネットワーク接続が必要です。
   - `--use-arcadia-xlre-role` は yfinance install とネットワーク接続が必要です。
   - `--use-oracle` の live route は yfinance install とネットワーク接続が必要です。

Optional dependencies:

- `yfinance`
- `pandas`
- `requests`

インストール例:

```bash
pip install -e ".[data]"
```

データソース診断:

```bash
python -m el_shaddai.cli --diagnose-data-sources
```

診断では、yfinance import 可否、FRED endpoint 到達可否、A.T.L.A.S. 取得可否、L.O.D.E. 取得可否、I.N.F.E.R.N.O. 取得可否、A.U.R.A. 取得可否、A.R.C.A.D.I.A. 取得可否、O.R.A.C.L.E. 取得可否、fallback になる理由を表示します。

## 使用データソース

デフォルトの v1.8 はネットワーク依存を避け、テスト可能性と透明性を優先します。ただし `--use-atlas-bndx-role` を指定した場合は yfinance から A.T.L.A.S. 価格データを取得して BNDX Role proxy を生成し、`--use-lode-tlt-role` を指定した場合は FRED から L.O.D.E. 系列を取得して TLT Role proxy を生成し、`--use-inferno-tip-role` を指定した場合は FRED から I.N.F.E.R.N.O. 系列を取得して TIP Role proxy を生成し、`--use-aura-gldm-role` を指定した場合は yfinance から A.U.R.A. 価格データを取得して GLDM Role proxy を生成し、`--use-arcadia-xlre-role` を指定した場合は yfinance から A.R.C.A.D.I.A. 価格データを取得して XLRE Role proxy を生成し、`--use-oracle` を指定した場合は VT/BTC の O.R.A.C.L.E. opportunity 生成を試みます。

- 価格データ: デフォルトは決定論的な built-in sample price history
- 任意の外部価格データ: `--prices-csv` で `date,asset,close` 列を持つ CSV を指定
- Role データ: デフォルトは中立の built-in role proxy inputs
- 任意の外部 Role データ: `--role-inputs-json` で asset ごとの proxy JSON を指定
- サンプル入力: `data/sample_prices.csv`, `data/sample_role_inputs.json`, `data/sample_lode_inputs.csv`, `data/sample_inferno_inputs.csv`, `data/sample_aura_prices.csv`, `data/sample_arcadia_prices.csv`, `data/sample_oracle_inputs.csv`

## 実行方法

```bash
python -m el_shaddai.cli --output-dir artifacts/el_shaddai
```

任意入力の例:

```bash
python -m el_shaddai.cli \
  --prices-csv data/sample_prices.csv \
  --role-inputs-json data/sample_role_inputs.json \
  --output-dir artifacts/el_shaddai
```

L.O.D.E. adapter を使って TLT Role Score を FRED 実データから生成する例:

```bash
python -m el_shaddai.cli \
  --use-lode-tlt-role \
  --output-dir artifacts/el_shaddai
```

`--use-lode-tlt-role` は TLT の `role_inputs` を L.O.D.E. 由来の direction-adjusted proxy で上書きします。FRED 取得に失敗した場合でも CLI は停止せず、warning を出したうえで既存の中立 proxy にフォールバックします。

I.N.F.E.R.N.O. adapter を使って TIP Role Score を FRED inflation data から生成する例:

```bash
python -m el_shaddai.cli \
  --use-inferno-tip-role \
  --output-dir artifacts/el_shaddai
```

`--use-inferno-tip-role` は TIP の `role_inputs` を I.N.F.E.R.N.O. 由来の direction-adjusted proxy で上書きします。FRED 取得失敗、データ不足時でも CLI は停止せず、warning を出したうえで既存の中立 proxy にフォールバックします。

FRED live fetch が 403 Forbidden になる環境では、manual CSV route を優先して使えます。`--inferno-inputs-csv` が指定された場合は live FRED よりも CSV が優先され、Markdown report には `Source: manual I.N.F.E.R.N.O. CSV: ...` と `Used I.N.F.E.R.N.O. data: True` が出力されます。CSV は `date,cpi,core_cpi,pce,core_pce,breakeven_5y,breakeven_10y,dfii10,unrate,broad_dollar,tip_close,tlt_close,dbc_close` を基本列とし、`cpi`/`pce` 系列は YoY inflation rate として解釈されます。

```bash
python -m el_shaddai.cli \
  --inferno-inputs-csv data/sample_inferno_inputs.csv \
  --output-dir artifacts/el_shaddai
```


A.U.R.A. adapter を使って GLDM Role Score を market data から生成する例:

```bash
python -m el_shaddai.cli \
  --use-aura-gldm-role \
  --output-dir artifacts/el_shaddai
```

`--use-aura-gldm-role` は GLDM の `role_inputs` を A.U.R.A. 由来の direction-adjusted proxy で上書きします。yfinance 取得失敗、データ不足、相関計算不能時でも CLI は停止せず、warning を出したうえで既存の中立 proxy にフォールバックします。

manual CSV input mode の例:

```bash
python -m el_shaddai.cli \
  --lode-inputs-csv data/sample_lode_inputs.csv \
  --inferno-inputs-csv data/sample_inferno_inputs.csv \
  --aura-prices-csv data/sample_aura_prices.csv \
  --output-dir artifacts/el_shaddai
```


## 出力

CLI は以下を生成します。

- `el_shaddai_scores.csv`
- `el_shaddai_report.md`
- `el_shaddai_dashboard.html`

HTML には、Executive Summary、Permanent Holdings / Value Opportunity Only、全アセット一覧表、Price × Role マトリクス、元気玉候補ランキングを含みます。

## 未実装項目

- 実データ API からの自動取得
- DXY、米国金利、CPI、PCE、Breakeven Inflation、CRB/GSCI/BCOM などの公式系列との自動連携（TLT の L.O.D.E. adapter、TIP の I.N.F.E.R.N.O. adapter、GLDM の A.U.R.A. adapter、XLRE の A.R.C.A.D.I.A. adapter、VT/BTC の O.R.A.C.L.E. adapter を除く）
- PNG 画像の直接出力（v1.7 は依存関係を増やさないため HTML/SVG 出力）
- 中央銀行買付や地政学リスクなど、定性的プロキシの自動生成
- VT 専用のバリュー/センチメント指標
  - CAPE
  - Fear & Greed
  - VIX
  - Market Cap / GDP など
- BTC 専用のオンチェーン/サイクル指標
  - MVRV
  - Puell Multiple
  - Reserve Risk
  - 前サイクル高値との距離 など
- Role proxy / opportunity proxy の実データ変換ロジック（v1.7 では TLT/L.O.D.E.、TIP/I.N.F.E.R.N.O.、GLDM/A.U.R.A.、XLRE/A.R.C.A.D.I.A.、VT・BTC/O.R.A.C.L.E. が初期接続済み）
- 日次履歴保存
- スコア推移グラフ

## 改善候補

- FRED、Treasury、ETF price API などからの取得アダプタ追加
- Role proxy の更新手順と監査ログの整備
- 各スコアの閾値を実運用レビューで調整
- HTML ダッシュボードへの経時変化チャート追加
- CSV 入力検証とサンプル入力ファイルの追加
- HTML ダッシュボードの Executive Summary 化
- Role proxy が全て中立の場合の警告表示
- `role_inputs.json` のサンプルファイル追加
- `prices.csv` のサンプルファイル追加
- Price Score の資産別カスタマイズ

## A.R.C.A.D.I.A. adapter（v1.7 / XLRE）

A.R.C.A.D.I.A.（Asset Real-estate Cycle Analysis & Demand Intelligence Architecture）は、XLRE 専用の Role Adapter です。XLRE を単なる中立 proxy として扱うのではなく、三体戦略における XLRE の本来の役割を監査できるようにします。

XLRE は「米国不動産市場全体」や広範 REIT 市場全体そのものではありません。XLRE は S&P 500 内の不動産セクター ETF であり、A.R.C.A.D.I.A. は、大型上場不動産企業群が **地代収益・デジタルインフラ地主・利回り気団** として機能しているかを監査します。

XLRE の Role 定義:

- デジタル社会の地主
- 地代収益によるインカムの安定
- 不動産オペレーション由来のキャッシュフロー
- Autumn / 利回り気団の資産
- VT と TIP の中間層、つまり成長とインフレ耐性の橋渡し

XLRE はインフレ耐性候補ですが、TIP ほど純粋なインフレ防衛資産ではありません。また実態は株式 ETF であるため、SPY/VT との連動が強まりすぎると「不動産の顔をした株式セクター」に堕し、Role が毀損します。

A.R.C.A.D.I.A. が利用する候補ティッカー:

| ticker | 用途 |
| --- | --- |
| XLRE | 監査対象 / S&P 500 real-estate sector ETF |
| SPY | 株式市場への服従 anchor |
| VNQ | 広範 REIT relative comparison |
| HYG | credit stress / oxygen sensor |
| UUP | dollar headwind sensor |
| DBC | commodity inflation / pass-through proxy |
| TLT | rate-shock proxy |
| ^TNX | US 10-year Treasury yield |

生成される XLRE component:

- Core: `rental_cashflow`, `digital_infrastructure_demand`, `dividend_sustainability`, `yield_spread_advantage`
- Support: `reit_relative_strength`, `inflation_pass_through`, `occupancy_environment`
- Risk Penalty: `real_rate_shock`, `credit_stress`, `dollar_headwind`, `equity_submission`

Role proxy は必ず方向調整済みの -2〜+2 です。+2 は XLRE の Role に非常に好ましい状態、0 は中立、-2 は XLRE の Role を大きく毀損する状態です。

A.R.C.A.D.I.A. は以下の cap を適用します。

- `real_rate_shock` severe: Role Score cap 55
- `real_rate_shock` severe + `credit_stress` severe: Role Score cap 45
- `real_rate_shock` severe + `credit_stress` severe + `equity_submission` severe: Role Score cap 35
- `dollar_headwind` severe + `credit_stress` severe: Role Score cap 50

### A.R.C.A.D.I.A. live fetch route

`--use-arcadia-xlre-role` は yfinance から XLRE/SPY/VNQ/HYG/UUP/DBC/TLT/^TNX の価格・金利 proxy を取得し、XLRE の `role_inputs` を A.R.C.A.D.I.A. 由来の direction-adjusted proxy で上書きします。

```bash
python -m el_shaddai.cli \
  --use-arcadia-xlre-role \
  --output-dir artifacts/el_shaddai
```

### A.R.C.A.D.I.A. manual CSV route

`--arcadia-prices-csv` が指定された場合は、live fetch より manual CSV route が優先されます。推奨 wide format は以下です。

```text
date,xlre_close,spy_close,vnq_close,hyg_close,uup_close,dbc_close,tlt_close,tnx
```

`data/sample_arcadia_prices.csv` はこの形式のサンプルです。long format の `date,ticker,close` も受け付けます。long format で 10 年金利を入れる場合、ticker は `^TNX` または `TNX` を使えます。

CLI 例:

```bash
python -m el_shaddai.cli \
  --arcadia-prices-csv data/sample_arcadia_prices.csv \
  --output-dir artifacts/el_shaddai
```

Markdown report には `## XLRE Role inputs generated by A.R.C.A.D.I.A.` が追加され、Source、Data date、Used A.R.C.A.D.I.A. data、Real-estate regime interpretation、Warnings、Applied caps、Raw metrics、Proxy table、Reasons が出力されます。HTML dashboard には `XLRE Role generated by A.R.C.A.D.I.A.` と regime interpretation が表示されます。

### A.R.C.A.D.I.A. fallback 仕様

live fetch 失敗、yfinance 未導入、データ不足、相関計算不能時でも CLI は停止しません。XLRE Role proxy は中立 fallback になり、warning が stdout と report に出力されます。`^TNX` が取得できない場合、A.R.C.A.D.I.A. は TLT trend を rate proxy として使い、金利 proxy の透明性を reasons/raw metrics に残します。

## O.R.A.C.L.E. adapter（v1.7 / VT・BTC）

O.R.A.C.L.E.（Opportunity Radar for Accumulation & Cycle-Level Entries）は、VT と BTC 専用のスポット買い判定機構です。他の Role Adapter が「そんな装備で大丈夫か？」を監査するのに対し、O.R.A.C.L.E. は永年保有アセットに対して **「今、スポット買いする好機か？」** だけを判定します。

VT と BTC は引き続き Role 監査対象ではありません。

- VT: 第一ユニットの永年保有資産
- BTC: 第二ユニットの永年保有資産
- `role_score = N/A`
- 定期積立ルールは不変
- `--use-oracle` 使用時のみ、VT/BTC の最終判断に `opportunity_score` と `oracle_signal` を使います

O.R.A.C.L.E. は以下の 4 層を 0〜100 点で評価します。高いほどスポット買い好機です。

| layer | 初期 weight | 意味 |
| --- | ---: | --- |
| `value_score` | 35% | 割安度 |
| `sentiment_score` | 25% | 市場の悲観度 |
| `drawdown_momentum_score` | 25% | 価格が十分に冷えているか |
| `cycle_score` | 15% | 長期サイクル上、買い場に近いか |

VT/BTCごとに個別 weight を設定できる構造にしてあります。O.R.A.C.L.E. の signal は以下です。

| score | oracle_signal |
| ---: | --- |
| 80-100 | 神は云っている、ここで買う定めなのだと…… |
| 60-79 | 近い。備えよ |
| 40-59 | まだその時ではない |
| 20-39 | 高値圏。待て |
| 0-19 | 慢心の極み |

### 使用可能な指標

VT O.R.A.C.L.E. は、世界株式をスポット買いする好機かを判定します。

- Value: `cape`, `market_cap_gdp`, `earnings_yield`, `equity_risk_premium`
- Sentiment: `fear_greed`, `vix`, `put_call`
- Drawdown / Momentum: `rsi`, `dma_200_deviation`, `range_52w_position`, `drawdown_from_ath` および既存 Price Score 由来の価格部品
- Cycle: v1.7 では中立 fallback。将来 `market_cycle_position`, `recession_probability`, `yield_curve`, `ISM/PMI` などを接続予定

BTC O.R.A.C.L.E. は、BTCをスポット買いする好機かを判定します。

- Value: `mvrv_z`, `puell_multiple`, `reserve_risk`, `rhodl_ratio`, `yardstick`
- Sentiment: `crypto_fear_greed`, `funding_rate`
- Drawdown / Momentum: `rsi`, `dma_200_deviation`, `dma_200w_deviation`, `range_52w_position`, `drawdown_from_ath` および既存 Price Score 由来の価格部品
- Cycle: `days_since_halving`, `distance_from_previous_cycle_high`, `bitcoin_dominance`

BTC では特に「前回サイクル高値付近」を cycle-level entry zone として扱います。ただし、ATH付近・Fear&Greed高・MVRV高などの慢心条件では `Euphoria Risk` 相当の低スコアになります。

### O.R.A.C.L.E. manual CSV route

v1.7 では manual CSV route を主経路とします。`--oracle-inputs-csv` が指定された場合は manual CSV が優先されます。サンプルは `data/sample_oracle_inputs.csv` です。

推奨列:

```text
date,asset,cape,market_cap_gdp,earnings_yield,equity_risk_premium,fear_greed,vix,put_call,rsi,dma_200_deviation,dma_200w_deviation,range_52w_position,drawdown_from_ath,mvrv_z,puell_multiple,reserve_risk,rhodl_ratio,yardstick,crypto_fear_greed,funding_rate,days_since_halving,distance_from_previous_cycle_high,bitcoin_dominance
```

VTに関係ないBTC指標、BTCに関係ないVT指標は空欄で構いません。

CLI例:

```bash
python -m el_shaddai.cli \
  --use-oracle \
  --oracle-inputs-csv data/sample_oracle_inputs.csv \
  --output-dir artifacts/el_shaddai
```

`--use-oracle` のみを指定した場合、可能なら yfinance から VT、BTC-USD、^VIX を取得し、価格由来・VIX由来の限定的な O.R.A.C.L.E. 判定を試みます。オンチェーン指標や CAPE などは取得元が不安定になりやすいため、v1.7 では manual CSV を推奨します。

### O.R.A.C.L.E. 出力

Markdown report には以下が追加されます。

- `## VT Opportunity generated by O.R.A.C.L.E.`
- `## BTC Opportunity generated by O.R.A.C.L.E.`

各セクションには Source、Data date、Used O.R.A.C.L.E. data、`opportunity_score`、`oracle_signal`、4層スコア、components、reasons、warnings が出ます。HTML dashboard にも VT/BTC の O.R.A.C.L.E. summary が表示されます。CSV には `opportunity_score`, `oracle_signal`, `oracle_reason` 列が追加され、VT/BTC以外は空欄になります。

### O.R.A.C.L.E. fallback 仕様

O.R.A.C.L.E. 入力がない場合、または VT/BTC の入力が不足している場合でも CLI は停止しません。VT/BTC は既存の `price_score` ベース判定へ fallback し、warning を stdout と Markdown report に出力します。これにより、El Shaddai の Role 監査思想を崩さず、VT/BTC だけを永年保有アセット専用の神託エンジンとして扱えます。

## G.A.I.A. DBC Commodity Role Adapter

**G.A.I.A.** means **Global Asset Intelligence for Inflationary Abundance**. It audits whether DBC, or a DBC-like commodity exposure, is fulfilling its intended L.U.M.U.S.-8 role as the Summer / inflation air-mass attack asset.

G.A.I.A. deliberately separates the audit anchor from the instrument that may be held in real operations:

```text
Audit target: DBC / Commodity Regime
Actual holding target: eMAXIS commodity products or similar SBI-available commodity funds
```

DBC remains the El Shaddai audit anchor because A.U.R.A. already uses DBC as the primary commodity-regime anchor, DBC bundles energy, metals, and agriculture into a convenient commodity proxy, and G.A.I.A. audits the **commodity role** rather than the price behavior of one local product.

### DBC role definition

DBC is treated as:

- 属性攻撃
- インフレ局面における爆発力
- 資源ショック対策
- 文明の燃料
- Summer / インフレ気団の攻撃資産

In normal weather DBC may remain quiet. When inflation or resource shocks arrive, it should burn as civilization's fuel and compensate for stagnation elsewhere in the portfolio. G.A.I.A. therefore asks: **is DBC correctly burning as civilization's fuel, or is it merely moving as noise?**

### Tickers and proxies

Live mode uses `yfinance` when available. Candidate tickers are:

```text
DBC, USO, UNG, GLD, CPER, DBA, SPY, UUP, TIP, GLDM, TLT, BNDX
```

The generated DBC role proxies are direction-adjusted to `-2..+2`, where `+2` is highly favorable for DBC's role, `0` is neutral, and `-2` means the commodity role is materially impaired.

Core proxies: `commodity_trend`, `inflation_firepower`, `resource_shock_response`, `summer_regime_strength`.
Support proxies: `energy_leadership`, `metals_leadership`, `agriculture_leadership`, `tip_gldm_alignment`.
Risk-penalty proxies: `deflation_drag`, `dollar_headwind`, `growth_collapse`, `commodity_noise`.

### Manual CSV route

Manual data takes priority over live fetch. The sample wide-format CSV is `data/sample_gaia_prices.csv` and uses these columns:

```text
date,dbc_close,uso_close,ung_close,gld_close,cper_close,dba_close,spy_close,uup_close,tip_close,gldm_close,tlt_close,bndx_close
```

Long format is also accepted with:

```text
date,ticker,close
```

### CLI examples

```bash
python -m el_shaddai.cli \
  --gaia-prices-csv data/sample_gaia_prices.csv \
  --output-dir artifacts/el_shaddai
```

Live route:

```bash
python -m el_shaddai.cli \
  --use-gaia-dbc-role \
  --output-dir artifacts/el_shaddai
```

### Fallback behavior

If live fetch fails, `yfinance` is not installed, required data is insufficient, or correlations cannot be computed, the CLI does **not** stop. G.A.I.A. emits a warning to stdout/report output and returns neutral DBC role proxies so the broader El Shaddai audit can complete.

### Regime interpretation

G.A.I.A. reports one of these interpretations:

- **Gaia Ignited** — Commodity fire is active; Summer regime is dominant.
- **Gaia Smoldering** — Commodity role evidence exists but is not yet dominant.
- **Gaia Dormant** — Commodity role is neutral or inactive.
- **Gaia Choked** — Dollar/deflation/growth collapse suppresses commodity role.
- **Gaia Extinguished** — Commodity regime is structurally impaired.

## El Shaddai 統合監査層 v2.0

v2.0 の統合監査層は、L.U.M.U.S.-8 の8資産監査結果を `AssetAuditInput` に正規化し、役割健全度順位、負傷アセット、役割グループ診断、聖域健全度、総合診断、助言専用の運用判断をまとめます。低スコアを自動売却へ変換せず、Market Amedas は弱い市場文脈としてのみ利用します。補正候補には継続判定（ヒステリシス）を適用し、自動売買は実装しません。

日本語のサンプル統合監査報告書は次のコマンドで生成できます。

```bash
python -m el_shaddai.integrated_audit --demo
```

報告書は標準出力に表示され、`artifacts/demo/el_shaddai_integrated_audit_report.md` にも保存されます。Python からは `run_integrated_audit(asset_audits, portfolio, market_amedas=None)` を呼び出すと、構造化された辞書と `report_text` を取得できます。

統合監査では、内部の役割証拠、市場文脈反映後の健全度、負傷判定を分離します。Market Amedas の弱い局面補正や低信頼だけでは負傷を生成せず、市場文脈だけが補正判断レベル2以上を示した場合は `1. 監視強化` に制限します。

2026年6月6日向けの Market Amedas デモシナリオでは、主要気団比率・気団の強弱・主要な上昇流／下降流・BTC逆行注意を含む報告書を生成できます。

```bash
python -m el_shaddai.integrated_audit --demo --scenario market_amedas_20260606
```

生成される報告書は `artifacts/demo/el_shaddai_integrated_audit_market_amedas_20260606.md` に保存されます。報告書の保存・表示前には端末UI由来の `:codex-terminal-citation[...]` メタ文字列を除去します。

`market_amedas_20260606` は、利回り気団 50.2%、成長気団 44.7%、防衛気団 4.4%、インフレ気団 0.7% の観測比率と、符号付きの上昇流・下降流実測値を使用します。観測値は表示用に保持し、市場文脈補正は従来どおり資産健全度側に限定して、負傷判定には使用しません。

## Google Colab向け最小production実行

`run_el_shaddai_production.py` は、demo modeに依存せず、ライブ価格データと既存adapterを使ってL.U.M.U.S.-8の単発・助言専用監査を実行するproduction入口です。`--output-dir` にGoogle Driveのmount先を渡すと、資産別レポート、統合監査レポート、HTML、CSV、実行manifestをそのディレクトリへ保存します。価格履歴が欠損した場合は、production実行ではbuilt-in sampleへフォールバックせず終了します。

```bash
python -m pip install -r requirements.txt
python run_el_shaddai_production.py \
  --config configs/production_lumus8.yaml \
  --output-dir /content/drive/MyDrive/el_shaddai/production_reports
```

設定例は `configs/production_lumus8.yaml`、Google Driveのmountを含むColab手順、生成物、警告確認、障害時の扱いは [`PRODUCTION_RUNBOOK.md`](PRODUCTION_RUNBOOK.md) を参照してください。この入口は自動売買・注文執行・常時監視を行いません。

## Parallax Engine v0.1

Parallax Engine は、Market Amedas の市場天候 JSON と El Shaddai の L.U.M.U.S.-8 監査 JSON を照合し、資産状態が市場文脈に支持されるか、説明可能な弱さか、乖離または役割不全候補かをルールベースで分類します。入力側のスコア、気団比率、負傷分類は変更せず、自動売買や配分変更も行いません。

```bash
python run_parallax.py \
  --market-amedas market_amedas_snapshot.json \
  --el-shaddai el_shaddai_lumus8_audit.json \
  --output-dir reports/parallax
```

出力は `parallax_context_report.json` と `parallax_context_report.md` です。どちらかの入力ファイルが欠損していても処理は停止せず、利用可能な範囲で `insufficient_context` レポートを生成します。

## Colab production FRED setup (L.O.D.E. / I.N.F.E.R.N.O.)

L.O.D.E.（TLT）と I.N.F.E.R.N.O.（TIP）の live FRED 取得は、`FRED_API_KEY` 環境変数が設定されている場合、production config の `fred.provider` よりも `fredapi` を優先します。Colab では El Shaddai 実行前に次を実行してください。

```python
%pip install -q fredapi

import os
from google.colab import userdata

os.environ["FRED_API_KEY"] = userdata.get("FRED_API_KEY")
print("FRED_API_KEY is set:", bool(os.environ.get("FRED_API_KEY")))
```

手入力する場合は次のように設定できます。

```python
from getpass import getpass
import os

os.environ["FRED_API_KEY"] = getpass("FRED_API_KEY: ")
```

API キーを設定しない場合は、設定済みの既存 provider（既定値は keyless `pandas_datareader`）を使用します。live FRED 取得に失敗しても監査全体は停止せず、last-successful cache、続いて neutral TLT/TIP Role proxy の順に fallback します。neutral fallback が使用されると L.O.D.E. / I.N.F.E.R.N.O. adapter は degraded / failed として記録され、Parallax Engine の confidence が低下する可能性があります。出力は引き続き助言専用で、自動売買・自動売却には接続しません。
