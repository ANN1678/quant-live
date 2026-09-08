"""bitbank の公開APIから価格を取る。鍵は要らない。

1時間足は日付（YYYYMMDD）で1日ぶんずつ返ってくる。日足は年（YYYY）で1年ぶん返ってくる。
返り値の ohlcv は [始値, 高値, 安値, 終値, 出来高, 時刻ms] の並びで、すべて文字列で来る。
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

import requests

from common import JST

BASE = "https://public.bitbank.cc"
PAIRS = ["btc_jpy", "eth_jpy"]
UA = {"User-Agent": "quant-live/0.1 (+https://ann1678.com/)"}


class MarketError(RuntimeError):
    pass


def _get(url: str) -> dict:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=20)
            r.raise_for_status()
            body = r.json()
        except Exception as e:
            if attempt == 2:
                raise MarketError(f"{url} を取れなかった: {e}") from e
            time.sleep(2 * (attempt + 1))
            continue
        if body.get("success") != 1:
            raise MarketError(f"{url} がエラーを返した: {body}")
        return body["data"]
    raise MarketError(url)


def candles(pair: str, span: str = "1hour", days: int = 7) -> list[dict]:
    """直近 days 日ぶんの足を、古い順で返す。"""
    out: list[dict] = []
    today = datetime.now(JST).date()
    for back in range(days - 1, -1, -1):
        d = today - timedelta(days=back)
        data = _get(f"{BASE}/{pair}/candlestick/{span}/{d.strftime('%Y%m%d')}")
        for c in data["candlestick"]:
            if c["type"] != span:
                continue
            for o, h, l, cl, v, ts in c["ohlcv"]:
                out.append({
                    "t": int(ts),
                    "o": float(o), "h": float(h), "l": float(l), "c": float(cl),
                    "v": float(v),
                })
    out.sort(key=lambda x: x["t"])
    # 同じ時刻が二重に入ることがあるので落とす
    seen, uniq = set(), []
    for c in out:
        if c["t"] in seen:
            continue
        seen.add(c["t"])
        uniq.append(c)
    return uniq


def candles_year(pair: str, year: int, span: str = "1day") -> list[dict]:
    data = _get(f"{BASE}/{pair}/candlestick/{span}/{year}")
    out = []
    for c in data["candlestick"]:
        if c["type"] != span:
            continue
        for o, h, l, cl, v, ts in c["ohlcv"]:
            out.append({"t": int(ts), "o": float(o), "h": float(h), "l": float(l),
                        "c": float(cl), "v": float(v)})
    out.sort(key=lambda x: x["t"])
    return out


def ticker(pair: str) -> dict:
    d = _get(f"{BASE}/{pair}/ticker")
    return {
        "pair": pair,
        "last": float(d["last"]),
        "buy": float(d["buy"]),
        "sell": float(d["sell"]),
        "high": float(d["high"]),
        "low": float(d["low"]),
        "open": float(d["open"]),
        "vol": float(d["vol"]),
        "t": int(d["timestamp"]),
    }
