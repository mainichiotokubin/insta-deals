"""価格の記録（毎日の下書き作成時に、見かけた商品の価格を保存する）と値下がり判定"""
import json
from datetime import date, timedelta

from .config import DATA

PATH = DATA / "prices.json"
WINDOW_DAYS = 30
MIN_POINTS = 3   # 過去にこの回数以上記録がある商品だけ判定する
MIN_SPAN = 5     # 最初の記録から何日以上たっていれば判定するか


def _load():
    return json.loads(PATH.read_text(encoding="utf-8")) if PATH.exists() else {}


def record(items):
    """{商品コード: {日付: 価格}} を更新する。同じ日は最後の価格で上書き"""
    data = _load()
    today = date.today().isoformat()
    border = (date.today() - timedelta(days=90)).isoformat()
    for it in items:
        hist = data.setdefault(it["code"], {})
        hist[today] = it["price"]
        for d in [d for d in hist if d < border]:  # 90日より古い記録は捨てる
            del hist[d]
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def annotate(items):
    """各商品に drop_pct（過去30日の最高値からの値下がり率）と lowest（30日最安値）を付ける"""
    data = _load()
    today = date.today()
    border = (today - timedelta(days=WINDOW_DAYS)).isoformat()
    for it in items:
        past = {d: p for d, p in data.get(it["code"], {}).items() if border <= d < today.isoformat()}
        it["drop_pct"], it["lowest"] = 0, False
        if len(past) < MIN_POINTS:
            continue
        if (today - date.fromisoformat(min(past))).days < MIN_SPAN:
            continue
        high, low = max(past.values()), min(past.values())
        it["drop_pct"] = max(0, round((high - it["price"]) / high * 100))
        it["lowest"] = it["price"] < low
    return items
