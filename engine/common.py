"""共通の置き場所と入出力。エンジンの他のファイルは、ここを通してだけファイルを触る。

QUANT_LIVE_DATA を環境変数で渡すと data/ の置き場所を変えられる（手元で試すとき用。本番では使わない）。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("QUANT_LIVE_DATA") or (ROOT / "data"))

JST = timezone(timedelta(hours=9))

# 事前に公開した予測。1行1件で追記する。書き換えない。
PREDICTIONS = DATA / "predictions.jsonl"
# 予測の判定。1行1件で追記する。
RESULTS = DATA / "results.jsonl"
# 仮想の約定。1行1件で追記する。持ち越した区間も1件。
TRADES = DATA / "trades.jsonl"
# 関門の検査の結果。検査は決めた件数に達したときの1回だけで、その結果を追記する。
GATE = DATA / "gate.jsonl"
# いま持っている玉。毎回まるごと書き直す。
POSITIONS = DATA / "positions.json"
# 集計した成績。毎回まるごと書き直す。
SUMMARY = DATA / "summary.json"
# 資産曲線。毎回まるごと書き直す。
EQUITY = DATA / "equity.json"
# 過去データに当てはめた結果。**事前公開の記録ではない。**
BACKTEST = DATA / "backtest.json"
# 直近の相場。表示用。
MARKET = DATA / "market.json"

HOUR_MS = 3_600_000
DAY_MS = 24 * HOUR_MS


def now() -> datetime:
    return datetime.now(JST).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def at(ms: int) -> str:
    """ミリ秒の時刻を JST の ISO 文字列にする。"""
    return iso(datetime.fromtimestamp(ms / 1000, JST))


def jst_midnights(open_ms: int, close_ms: int) -> int:
    """open から close までに JST の 0:00 を何回またぐか。信用取引の建玉管理料はこの回数ぶんかかる。"""
    return int((close_ms + 9 * HOUR_MS) // DAY_MS - (open_ms + 9 * HOUR_MS) // DAY_MS)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, obj) -> None:
    """隣に書いてから置き換える。途中で止まっても壊れたファイルが残らない。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
