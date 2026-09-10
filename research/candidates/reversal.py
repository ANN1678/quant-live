"""候補 reversal: 極端な売られすぎの戻りを買う（ロングのみ）。

規則
  直近 W=240 本（10日）の1時間足の終値から Wilder の RSI(24) を計算し、RSI < 20 なら「上」。それ以外は見送り。
  ショートは出さない（train では買われすぎ側は反転せず続伸するため）。
  H=72 時間後に成行で手仕舞う。fill='next_open'（決めた次の足の始値で成行）。hold_through は効かない（72時間後に RSI<20 が続くことがほぼ無い）。

本番での計算（純 Python）
  closes = 直近 240 本の終値（古い→新しい）。d[i] = closes[i]-closes[i-1] (i=1..239)。
  up = max(d,0), dn = max(-d,0)。au = mean(up[1..24]), ad = mean(dn[1..24])。
  i=25..239 について au = (au*23 + up[i])/24, ad = (ad*23 + dn[i])/24。
  RSI = 100 - 100/(1 + au/ad)（ad==0 なら 100）。RSI < 20 なら up。
  240 本だけ要る。計算量は 240 回の加算。
"""
import numpy as np

RSI_N = 24
RSI_THR = 20.0
WINDOW = 240

CONFIG = dict(H=72, fill="next_open", hold_through=False, position=0.10, costs="DEFAULT_COSTS")


def rsi_from_window(closes, n=RSI_N):
    """closes: 長さ >= n+2 の並び（古い→新しい）。純 Python でも同じ式で書ける。"""
    m = len(closes)
    if m < n + 2:
        return None
    au = 0.0; ad = 0.0
    for i in range(1, n + 1):
        d = closes[i] - closes[i - 1]
        if d > 0: au += d
        else: ad -= d
    au /= n; ad /= n
    for i in range(n + 1, m):
        d = closes[i] - closes[i - 1]
        up = d if d > 0 else 0.0
        dn = -d if d < 0 else 0.0
        au = (au * (n - 1) + up) / n
        ad = (ad * (n - 1) + dn) / n
    if ad == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + au / ad)


def strategy(df):
    c = df["c"].to_numpy().tolist()
    n = len(c)
    sig = np.zeros(n, dtype=int)
    for i in range(RSI_N + 1, n):
        lo = max(0, i + 1 - WINDOW)
        r = rsi_from_window(c[lo:i + 1])
        if r is not None and r < RSI_THR:
            sig[i] = 1
    return sig
