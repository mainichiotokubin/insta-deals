"""下書き・投稿履歴の保存"""
import json
from datetime import datetime, timedelta

from .config import DATA, DRAFTS


def _read(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def save_draft(draft):
    draft["updated"] = datetime.now().isoformat(timespec="seconds")
    _write(DRAFTS / draft["id"] / "draft.json", draft)


def load_draft(draft_id):
    return _read(DRAFTS / draft_id / "draft.json", None)


def list_drafts(status=None):
    out = []
    if DRAFTS.exists():
        for p in sorted(DRAFTS.glob("*/draft.json")):
            d = _read(p, None)
            if d and (status is None or d["status"] == status):
                out.append(d)
    return out


def recent_item_codes(days):
    """最近投稿した（or 下書き中の）商品は除外して、同じ商品ばかりにならないようにする"""
    history = _read(DATA / "history.json", {})
    border = (datetime.now() - timedelta(days=days)).isoformat()
    codes = {c for c, at in history.items() if at >= border}
    for d in list_drafts():
        if d["status"] in ("pending", "approved"):
            codes |= {it["code"] for it in d["items"]}
    return codes


def mark_posted(items):
    path = DATA / "history.json"
    history = _read(path, {})
    now = datetime.now().isoformat(timespec="seconds")
    for it in items:
        history[it["code"]] = now
    _write(path, history)
