"""検証台が engine/backtest.py と同じ足で同じ数字を出すかを確かめる。

⚠ v1 の engine（commit e0f11e2 以前）でだけ動く。v2 では strategy.SLOW も backtest.run_pair の引数も無い。
   確かめた結果（2026-09-08）: BTC 29件 +0.2188% sd 3.8900／ETH 29件 +0.3343% sd 6.3847 で小数4桁まで一致。"""
import sys, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "engine"))
import numpy as np, pandas as pd
import market, backtest, strategy, paper
from harness import simulate, ema_cross_v1, trade_stats, LEGACY_COSTS

for pair in ["btc_jpy", "eth_jpy"]:
    candles = market.candles(pair, "1hour", days=90)
    ref = backtest.run_pair(pair, days=90)  # 内部でまた取りに行くが同じ範囲
    df = pd.DataFrame(candles); df.index = pd.to_datetime(df["t"], unit="ms", utc=True); df = df[["o","h","l","c","v"]]
    sig = ema_cross_v1(df); sig[:strategy.SLOW + 2] = 0  # backtest.py は i=SLOW+2 から
    # backtest.py は i in range(SLOW+2, len-H) で判定するので、同じ範囲に限る
    sim = simulate(df, sig, H=72, fill="close", costs=LEGACY_COSTS, position=0.10)
    st = trade_stats(sim["trades"])
    print(f"{pair}: backtest.py trades={ref['trades']} mean={ref['avg_net_pct']} sd={ref['sd_pct']} cap={ref['capital_end']} dd={ref['max_drawdown_pct']}")
    print(f"{pair}: harness     trades={st['n']} mean={st['mean']:.4f} sd={st['sd']:.4f} cap={sim['capital_end']:.0f} dd={sim['max_drawdown_pct']:.3f}")
    # 予測の判定数と的中率も
    from harness import prediction_stats
    p = prediction_stats(df, sig, 72)
    print(f"{pair}: backtest.py judged={ref['judged']} hit={ref['hit_rate']} / harness judged={p['judged']} hit={p['hit_rate']:.2f}")
