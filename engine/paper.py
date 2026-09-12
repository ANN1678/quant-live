"""仮想の売買。約定したことにする前提を、1か所に集める。

規則の版は long-carry-v3 と呼ぶ。
- **「上」のときだけ建てる。**「下」は建てない。理由は2つ。現物ではショートできず信用取引が要り、
  JST 0:00 の建玉に 1日 0.04% の建玉管理料がかかること。4年の当てはめで「下」の売買はどの形でも負け続けたこと。
- 1銘柄1玉。資金の 10% を建てる。72時間後に見直す
- 72時間後、予測が同じ「上」なら**閉じずに持ち越す。**閉じて同じ値で建て直すと往復のコストだけ捨てる
  （v1 はそうしていて、90日で 29件中 16件がそれだった）。持ち越しても 72時間ごとに1件として記録する。
  コストは建てた区間と閉じた区間にだけ載る
- **建て値・手仕舞い値は足の終値で決める。**建てるのは合図にした足の終値、手仕舞うのは期限の足の終値。
  それに片道 0.05% のすべりを足す。**この値は run した時刻に左右されない。**誰でも bitbank の公開APIで検算できる。
- **実際に板にあった値も残す。**entry_actual / exit_actual に気配を、late_minutes に期限からの遅れを入れる。
  規則の値と実際に取れた値の差が、そのまま「実行のずれ」として出る。消すのではなく、測って出す

  ⚠ **v2 で気配に変えたのは、v1 が遅れていたからで、足が悪かったからではない。**
     v1 は毎時37分に走っていて、足が閉じてから 40〜70分後の記録だった。だから足の終値はもう板に無く、
     実勢と 0.1〜0.3% ずれた。**直すべきは規則ではなく遅刻のほうだった。**
     気配にした結果、2026-09-11 に GitHub が4時間半おくれ、手仕舞い2件の符号が両方とも裏返った
     （btc −0.198% は本来 +1.690%、eth −5.103% は本来 +0.391%）。
     記録が「いつ走ったか」に左右される形は、証拠として使えない。だから足に戻し、遅刻は A（毎時きちんと動かす）で潰す。
     合図は Xserver の cron が毎時5分に出す。足が閉じた直後なので、規則の値と実勢の差は数分ぶんしか出ない
- 手数料は銘柄ごとの成行。bitbank の API（/v1/spot/pairs、2026-09-09 取得）の値をそのまま置く

⚠ この数字を甘くすると、サイト全体が嘘になる。緩めるときは /method/ の表も同時に直す。
⚠ 規則を変えたら RULE の名前を変える。trades.jsonl の各行に rule が入るので、違う規則の件数は混ざらない。
"""
from __future__ import annotations

from common import jst_midnights

RULE = "long-carry-v3"

# 成行（テイカー）手数料。片道。bitbank API の taker_fee_rate_quote（2026-09-09）。
TAKER = {"btc_jpy": 0.0010, "eth_jpy": 0.0012}
TAKER_DEFAULT = 0.0012
# 板を叩いたときのずれ。片道。気配で約定したことにする上で、板の厚みぶんをさらに引く。
SLIPPAGE = 0.0005
# 信用取引の建玉管理料。JST 0:00 の建玉に 1日。ショートにだけかかる（ロングは現物）。
MARGIN_DAILY = 0.0004
# 1回の建玉に使う資金の割合（建玉の額。レバレッジは使わない）。
POSITION = 0.10
# 出発点の資金（円）。
START_CAPITAL = 1_000_000
# 建てる方向。
TRADE_DIRECTIONS = ("up",)

# 互換のために残す（report の assumptions が読む）。eth_jpy の値。
FEE = TAKER_DEFAULT
ROUND_TRIP_COST = (FEE + SLIPPAGE) * 2


def side_cost(pair: str) -> float:
    """片道のコスト（手数料＋すべり）。"""
    return TAKER.get(pair, TAKER_DEFAULT) + SLIPPAGE


def round_trip_cost(pair: str) -> float:
    return side_cost(pair) * 2


def settle(pair: str, direction: str, entry: float, exit_: float, open_t: int, close_t: int,
           opens: bool = True, closes: bool = True) -> dict:
    """1区間（建ててから手仕舞う、または持ち越すまで）を計算する。手数料とずれと建玉管理料を引いた後の値を返す。

    opens  : この区間で建てた（建てるコストを載せる）
    closes : この区間で手仕舞った（手仕舞うコストを載せる）。持ち越しなら False
    """
    raw = (exit_ - entry) / entry
    if direction == "down":
        raw = -raw
    fee = (side_cost(pair) if opens else 0.0) + (side_cost(pair) if closes else 0.0)
    margin = MARGIN_DAILY * jst_midnights(open_t, close_t) if direction == "down" else 0.0
    net = raw - fee - margin
    return {
        "gross_pct": round(raw * 100, 4),
        "fee_pct": round(fee * 100, 4),
        "margin_pct": round(margin * 100, 4),
        "cost_pct": round((fee + margin) * 100, 4),
        "net_pct": round(net * 100, 4),
    }


def assumptions() -> dict:
    return {
        "rule": RULE,
        "trade_directions": list(TRADE_DIRECTIONS),
        "fee_pct": round(FEE * 100, 4),
        "fee_pct_by_pair": {p: round(v * 100, 4) for p, v in TAKER.items()},
        "slippage_pct": round(SLIPPAGE * 100, 4),
        "round_trip_cost_pct": round(ROUND_TRIP_COST * 100, 4),
        "round_trip_cost_pct_by_pair": {p: round(round_trip_cost(p) * 100, 4) for p in TAKER},
        "margin_daily_pct": round(MARGIN_DAILY * 100, 4),
        "position_pct": round(POSITION * 100, 2),
        "fill": "足の終値。建ては合図にした足、手仕舞いは期限の足。run した時刻に左右されない",
        "fill_actual": "実際に板にあった気配も entry_actual / exit_actual に残す。期限からの遅れは late_minutes",
        "carry": "72時間後に予測が同じ向きなら閉じずに持ち越す。区間ごとに1件で記録し、コストは建てた区間と閉じた区間にだけ載る",
    }
