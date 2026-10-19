"""楽天の大型イベント（お買い物マラソン・スーパーSALE）が開催中かを調べる

イベントページは、終わっていると「◯◯は終了しました」と表示されるので、それで判定する。
取得に失敗したときは「開催中ではない」扱いにする（間違ってハッシュタグを付けないため）。
"""
import re
import urllib.request

from .config import settings

ENDED = ("終了しました", "開催予定", "予告")


def active_events():
    """開催中のイベントの [(名前, ハッシュタグ)]"""
    out = []
    for ev in settings().get("event_hashtags", []):
        try:
            req = urllib.request.Request(ev["url"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as res:
                text = res.read().decode("utf-8", "ignore")
        except Exception:
            continue
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))
        if ev["name"] in text and not any(w in text for w in ENDED):
            out.append((ev["name"], ev["tag"]))
    return out
