"""共通の置き場所と入出力。エンジンの他のファイルは、ここを通してだけファイルを触る。"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

JST = timezone(timedelta(hours=9))

# 事前に公開した予測。1行1件で追記する。書き換えない。
PREDICTIONS = DATA / "predictions.jsonl"
# 仮想の約定。1行1件で追記する。
TRADES = DATA / "trades.jsonl"
# 集計した成績。毎回まるごと書き直す。
SUMMARY = DATA / "summary.json"
# 資産曲線。毎回まるごと書き直す。
EQUITY = DATA / "equity.json"
# 過去データに当てはめた結果。**事前公開の記録ではない。**
BACKTEST = DATA / "backtest.json"
# 直近の相場。表示用。
MARKET = DATA / "market.json"


def now() -> datetime:
    return datetime.now(JST).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.isoformat()


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


def rewrite_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
    path.write_text(body, encoding="utf-8")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
