"""投稿時間のおすすめ（基本は20〜21時、期限が今日までのお得がある日は12〜13時）"""
from datetime import date

NORMAL = "20〜21時"
EARLY = "12〜13時（お昼休み）"

# 楽天の1日限りのイベント（その日の23:59まで）
EVENTS = {1: "ワンダフルデー", 18: "ご愛顧感謝デー"}


def early_reasons(items, today=None):
    """早めに投稿したほうがいい理由のリスト（空なら通常の時間でOK）"""
    today = today or date.today()
    reasons = []
    if today.day % 5 == 0:
        reasons.append(f"今日は楽天の「5と0のつく日」（{today.month}/{today.day}の23:59まで）")
    if today.day in EVENTS:
        reasons.append(f"今日は楽天の「{EVENTS[today.day]}」（23:59まで）")
    for i, it in enumerate(items, 1):
        end = (it.get("point_end") or "")[:10]
        if end == today.isoformat() and it.get("point_rate", 1) > 1:
            reasons.append(f"No.{i}のポイント{it['point_rate']}倍が今日の23:59で終了")
    return reasons


def recommendation(reasons):
    return EARLY if reasons else NORMAL
