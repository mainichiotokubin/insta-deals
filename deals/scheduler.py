"""自動投稿（10分ごとに launchd から呼ばれる）

- 承認された今日の下書きを、インスタは決めた時刻に投稿する（早めの日は12:00、ふだんは20:00）
- Threads は商品投稿・質問投稿を、おすすめ時刻を過ぎたものから1回に1件ずつ投稿する
  （まとめて連投しないため。返信のリンクも続けて投稿する）
- Threads の投稿から24時間たったら閲覧数を記録する（伸びた型を多めに使うため）
"""
import json
from datetime import datetime, timedelta

from . import store
from .config import env

IG_TIMES = {"early": "12:00", "normal": "20:00"}
MAX_TRIES = 2


def _at(today, hhmm):
    h, m = map(int, hhmm.split(":"))
    return today.replace(hour=h, minute=m, second=0, microsecond=0)


def ig_time(draft):
    return IG_TIMES["early" if draft.get("early_reasons") else "normal"]


def _is_today(draft, now):
    return draft["id"].startswith(now.strftime("%Y%m%d"))


def _notify(title, msg):
    import subprocess
    subprocess.run(["osascript", "-e", f'display notification "{msg[:100]}" with title "{title}"'],
                   capture_output=True)


def _public_urls(draft):
    """画像を GitHub Pages に置いて公開URLを返す（1つの下書きにつき1回だけ）"""
    from . import site
    if not draft.get("public_urls"):
        draft["public_urls"] = site.publish_images(draft)
        store.save_draft(draft)
    return draft["public_urls"]


def _instagram(draft, now):
    from cli import publish_draft
    from .config import settings
    if not env("IG_ACCESS_TOKEN", required=False) or not settings().get("instagram_auto", True):
        return False  # 音楽を付けるためインスタは手動投稿（settings.json の instagram_auto）
    if draft["status"] != "approved" or now < _at(now, ig_time(draft)):
        return False
    try:
        _public_urls(draft)
        publish_draft(draft)
        print(f"インスタに投稿しました: {draft['id']}")
    except Exception as e:
        draft.update(status="failed", error=f"インスタ: {e}")
        store.save_draft(draft)
        _notify("インスタの自動投稿に失敗", str(e))
    return True


def _threads_queue(draft, now):
    """投稿時刻を過ぎた、まだ投稿していないThreads投稿（時刻順）"""
    from .threads import QUESTION_TIMES, TIMES
    queue = []
    for p in draft.get("threads", []):
        queue.append((TIMES[(p["no"] - 1) % len(TIMES)], "post", p))
    state = draft.setdefault("threads_q_state", [{} for _ in draft.get("threads_questions", [])])
    for k, q in enumerate(draft.get("threads_questions", [])):
        queue.append((QUESTION_TIMES[k % len(QUESTION_TIMES)], "question", {"text": q, "state": state[k]}))
    queue.sort(key=lambda x: _at(now, x[0]))
    return [(t, kind, p) for t, kind, p in queue
            if now >= _at(now, t) and not (p.get("media_id") or p.get("state", {}).get("media_id"))
            and (p.get("tries") or p.get("state", {}).get("tries") or 0) < MAX_TRIES]


def _threads(draft, now):
    from . import threads_api
    from .config import settings
    if not env("THREADS_ACCESS_TOKEN", required=False) or not settings().get("threads_auto", True):
        return False  # settings.json の threads_auto が false のあいだは投稿しない
    due = _threads_queue(draft, now)
    if not due:
        return False
    t, kind, p = due[0]
    target = p if kind == "post" else p["state"]
    target["tries"] = target.get("tries", 0) + 1
    try:
        if kind == "post":
            urls = _public_urls(draft)
            img = urls.get(p["image"])
            media = threads_api.post(p["text"], image_url=img)
            p["media_id"] = media
            p["reply_id"] = threads_api.post(p["reply"], reply_to=media)
        else:
            target["media_id"] = threads_api.post(p["text"])
        target["posted_at"] = datetime.now().isoformat(timespec="seconds")
        target.pop("error", None)
        print(f"Threadsに投稿しました: {draft['id']} {kind} {t}")
    except Exception as e:
        import urllib.error
        if isinstance(e, (urllib.error.URLError, OSError)) and not isinstance(e, urllib.error.HTTPError):
            target["tries"] -= 1  # 通信エラー（Macがオフライン等）は回数に数えず、次の回にやり直す
            target["error"] = f"通信エラーのため再試行待ち: {e}"[:300]
        else:
            target["error"] = str(e)[:300]
            _notify("Threadsの自動投稿に失敗", str(e))
    store.save_draft(draft)
    return True


def _record_views():
    """投稿から24時間以上たったThreads投稿の閲覧数を記録する"""
    from . import threads_api
    from .threads import LOG
    if not env("THREADS_ACCESS_TOKEN", required=False) or not LOG.exists():
        return
    log = json.loads(LOG.read_text(encoding="utf-8"))
    border = datetime.now() - timedelta(hours=24)
    changed = False
    for d in store.list_drafts():
        for p in d.get("threads", []):
            if not p.get("media_id") or not p.get("posted_at"):
                continue
            if datetime.fromisoformat(p["posted_at"]) > border:
                continue
            row = next((r for r in log if r["draft_id"] == d["id"] and r["no"] == p["no"]), None)
            if not row or row.get("views") is not None:
                continue
            try:
                stats = threads_api.views(p["media_id"])
            except Exception:
                continue
            row.update(views=stats.get("views"), likes=stats.get("likes"), replies=stats.get("replies"))
            changed = True
    if changed:
        LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_photos(draft):
    """承認された下書きの画像を、写真アプリのアルバム「毎日お得便」にも保存しておく（1回だけ）"""
    from . import export
    from .config import settings
    if draft.get("photos_saved"):
        return
    try:
        export.to_icloud_drive(draft, settings()["account_name"])  # 写真の同期が遅いとき用（ファイルアプリから見られる）
    except Exception as e:
        print(f"iCloud Driveへの保存に失敗: {e}")
    try:
        export.to_photos(draft, settings()["account_name"])
        draft["photos_saved"] = True
        store.save_draft(draft)
    except Exception as e:
        print(f"写真アプリへの保存に失敗: {e}")


def tick(now=None):
    from . import instagram, threads_api
    now = now or datetime.now()
    try:
        if env("IG_ACCESS_TOKEN", required=False):
            instagram.refresh_token_if_needed()
        if env("THREADS_ACCESS_TOKEN", required=False):
            threads_api.refresh_token_if_needed()
    except Exception as e:
        print(f"トークン更新でエラー: {e}")
    for d in store.list_drafts():
        if d.get("demo") or not d.get("approved_at") or not _is_today(d, now):
            continue
        _save_photos(d)
        if not d.get("marked_posted"):
            store.mark_posted(d["items"])
            d["marked_posted"] = True
            store.save_draft(d)
        if _instagram(d, now):
            d = store.load_draft(d["id"])
        _threads(d, now)
    _record_views()
