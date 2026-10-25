"""
使い方:
  python cli.py draft [--demo]   今日の投稿の下書きを作る（--demo は楽天APIなしで試す）
  python cli.py review           確認画面を開く http://127.0.0.1:8765
  python cli.py publish [--id X] 承認済みの下書きを1件投稿する
  python cli.py refresh-token    Instagramのトークンを更新する
  python cli.py check            .env のキーが正しく設定できているか確認する
"""
import argparse
import random
import subprocess
import sys
import urllib.parse
from datetime import datetime

from deals import caption, render, store
from deals.config import DATA, DRAFTS, settings

WEEK = "月火水木金土日"


def _date_label(now):
    return f"{now.month}/{now.day}({WEEK[now.weekday()]})"


def _demo_items(n):
    from PIL import Image, ImageDraw
    from deals.render import font

    out = DATA / "demo"
    out.mkdir(parents=True, exist_ok=True)
    names = ["詰め替え用 柔軟剤 特大 2.5kg ×2袋セット", "トイレットペーパー 3倍巻き 12ロール",
             "大容量 化粧水 500ml 高保湿 敏感肌", "UVカット 日焼け止めジェル SPF50+ 2本セット",
             "ハンドクリーム 6本セット 無香料 しっとり", "歯ブラシ ふつう 20本 まとめ買い"]
    items = []
    for i in range(n):
        p = out / f"demo{i}.jpg"
        img = Image.new("RGB", (600, 600), (random.randint(150, 230), random.randint(170, 230), 240))
        ImageDraw.Draw(img).text((300, 300), f"商品{i + 1}", font=font(7, 80), fill="white", anchor="mm")
        img.save(p)
        items.append({
            "code": f"demo:{i}", "name": names[i % len(names)], "price": random.randint(6, 40) * 100 - 20,
            "point_rate": random.choice([1, 2, 5, 10]), "review_average": round(random.uniform(4.2, 4.8), 1),
            "review_count": random.randint(100, 20000), "shop": "デモショップ",
            "image": str(p), "url": "https://www.rakuten.co.jp/", "keyword": "demo",
        })
    return items


def pick(candidates, n):
    """スコア順に並べて、同じキーワードから偏らないように選ぶ"""
    from deals.rakuten import score
    ranked = sorted(candidates, key=score, reverse=True)
    from deals.caption import short_name
    from datetime import datetime, timedelta
    border = (datetime.now() - timedelta(days=3)).strftime("%Y%m%d")
    brands = {short_name(it["name"]).split(" ")[0]
              for d in store.list_drafts() if d["id"][:8] >= border and d["status"] in ("approved", "published", "exported")
              for it in d["items"]}  # 直近3日に紹介したブランドは避ける
    from deals.threads import _topic
    COSME = ("化粧水", "日焼け止め", "クレンジング", "ハンドクリーム", "ランキング:コスメ", "美容液", "シートマスク",
             "ファンデーション", "リップ", "マスカラ", "ヘアオイル", "ボディクリーム", "オールインワン", "洗顔料")
    cat_limit = n - 2  # 日用品・コスメのどちらかに偏るのは最大3つまで（5商品のとき）
    chosen, used, cats, topics = [], {}, {}, set()
    for it in ranked:
        key = it["keyword"]
        brand = short_name(it["name"]).split(" ")[0]  # 商品名の最初の言葉＝だいたいブランド名
        cat = "コスメ" if key.startswith(COSME) else "日用品"
        topic = _topic(it)[0]  # 保湿ケア・メイク落とし など
        limit = 2 if key.startswith("ランキング") else 1  # 売れ筋ランキングからは2つまで
        recent_hit = any(len(b) >= 3 and b in it["name"] for b in brands)
        if (used.get(key, 0) < limit and brand not in brands and not recent_hit  # 同じブランド・シリーズは避ける
                and cats.get(cat, 0) < cat_limit
                and (topic not in topics or topic == "日用品")):  # 同じジャンルは1日1つまで
            chosen.append(it)
            used[key] = used.get(key, 0) + 1
            cats[cat] = cats.get(cat, 0) + 1
            brands.add(brand)
            topics.add(topic)
        if len(chosen) == n:
            return chosen
    for it in ranked:  # キーワードが足りなければ残りから補う
        if it not in chosen:
            chosen.append(it)
        if len(chosen) == n:
            break
    return chosen


def _force_big_drops(items, candidates, s):
    """大きく値下がりした商品（記録上の最高値から15%以上）は、その日の下書きに必ず入れる（最大2つ）"""
    from deals.rakuten import score
    th = s.get("tracking", {}).get("big_drop_pct", 15)
    big = sorted([c for c in candidates if c.get("lowest") and c.get("drop_pct", 0) >= th],
                 key=lambda c: -c["drop_pct"])[:2]
    for b in big:
        if any(b["code"] == it["code"] for it in items):
            continue
        weakest = min((it for it in items if it.get("drop_pct", 0) < th), key=score, default=None)
        if weakest is None:
            break
        items[items.index(weakest)] = b
        print(f"  大きな値下がりを入れました: {b['name'][:30]}（{b['drop_pct']}%ダウン）")
    # 値下がりの大きい商品を先頭に
    items.sort(key=lambda it: -(it.get("drop_pct", 0) if it.get("lowest") and it.get("drop_pct", 0) >= th else 0))
    return items


def cmd_track(args):
    """価格の記録だけを行う（1日2回）。大きな値下がりがあれば通知する"""
    from deals.rakuten import track
    items, big = track()
    print(f"価格を記録しました：{len(items)}商品")
    for b in big[:5]:
        print(f"  ↓{b['drop_pct']}% {b['price']:,}円 {b['name'][:40]}")
    if big:
        notify("大きな値下がりを発見", f"{big[0]['name'][:25]} が{big[0]['drop_pct']}%ダウン。次の下書きに入れます")


def cmd_draft(args):
    s = settings()
    today = datetime.now().strftime("%Y%m%d")
    if not args.demo and not getattr(args, "force", False) and any(
            d["id"].startswith(today) and d["status"] in ("pending", "approved", "published") for d in store.list_drafts()):
        print("今日の下書きはもうあるので、作りません（作り直すときは --force）")
        return
    n = s["items_per_post"]
    if args.demo:
        items = _demo_items(n)
    else:
        from deals.rakuten import search_candidates
        print("楽天から候補を取得中...")
        candidates = search_candidates(store.recent_item_codes(s["repost_after_days"]))
        print(f"  候補 {len(candidates)} 件")
        if len(candidates) < 3:
            sys.exit("候補が少なすぎます。settings.json の条件をゆるめてください")
        items = pick(candidates, n)
        items = _force_big_drops(items, candidates, s)

    now = datetime.now()
    draft_id = now.strftime("%Y%m%d-%H%M%S")
    label = _date_label(now)
    images = render.render_post(items, DRAFTS / draft_id, label, s["instagram_handle"])
    from deals import timing
    reasons = timing.early_reasons(items)
    draft = {
        "id": draft_id, "status": "pending", "demo": args.demo, "date_label": label,
        "items": items, "images": images, "caption": caption.build_caption(items, label, s),
        "early_reasons": reasons,
    }
    from deals import threads
    draft["threads"] = threads.build_posts(items)
    draft["threads_questions"] = threads.question_posts()
    threads.log_posts(draft_id, draft["threads"])
    store.save_draft(draft)
    print(f"下書きを作成しました: {draft_id}（{len(images)}枚）")
    print("確認: python cli.py review")
    if reasons:
        notify("今日は早めの投稿がおすすめ", f"{timing.EARLY}に投稿しましょう。" + reasons[0])
    else:
        notify("お得投稿の下書きができました", f"確認して{timing.NORMAL}に投稿しましょう")
    return draft


def notify(title, message):
    subprocess.run(["osascript", "-e", f'display notification "{message}" with title "{title}"'],
                   capture_output=True)


def publish_draft(draft):
    from deals import instagram, site
    if draft.get("demo"):
        raise RuntimeError("デモの下書きは投稿できません")
    instagram.refresh_token_if_needed()
    urls = draft.get("public_urls") or site.publish_images(draft)
    draft["public_urls"] = urls
    media_id = instagram.publish_carousel([urls[n] for n in draft["images"]], draft["caption"])
    draft.update(status="published", ig_media_id=media_id,
                 published_at=datetime.now().isoformat(timespec="seconds"))
    store.save_draft(draft)
    store.mark_posted(draft["items"])
    site.build_page()
    return media_id


def cmd_publish(args):
    if args.id:
        draft = store.load_draft(args.id)
    else:
        approved = store.list_drafts("approved")
        draft = approved[0] if approved else None
    if not draft:
        print("投稿待ち（承認済み）の下書きはありません")
        return
    try:
        media_id = publish_draft(draft)
        print(f"投稿しました: {draft['id']} → media {media_id}")
    except Exception as e:
        draft.update(status="failed", error=str(e))
        store.save_draft(draft)
        notify("お得投稿に失敗しました", str(e)[:100].replace('"', "'"))
        sys.exit(f"投稿に失敗しました: {e}")


def cmd_review(args):
    from deals.review import serve
    serve(args.port)


def cmd_refresh(args):
    from deals import instagram
    instagram.refresh_token_if_needed(force=True)
    print("トークンを更新しました")


def cmd_check(args):
    from deals.config import env
    ok = True
    print("[楽天]")
    try:
        from deals import rakuten
        data = rakuten._get({"keyword": "トイレットペーパー", "hits": 1})
        it = data["Items"][0]
        it = it.get("Item", it)
        print(f"  OK: {it['itemName'][:30]}…")
        print("  アフィリエイトリンク: " + ("OK" if it.get("affiliateUrl") else "なし（アフィリエイトIDを確認）"))
    except SystemExit as e:
        ok = False
        print(f"  NG: {e}")
    except Exception as e:
        ok = False
        detail = e.read().decode("utf-8", "replace") if hasattr(e, "read") else ""
        print(f"  NG: {e} {detail}")
    print("[Instagram]")
    try:
        from deals import instagram
        info = instagram.me()
        print(f"  OK: @{info.get('username')}（{info.get('account_type')}）user_id={info.get('user_id')}")
        if not env("IG_USER_ID", required=False):
            print(f"  → .env の IG_USER_ID に {info.get('user_id')} を入れてください")
    except SystemExit as e:
        ok = False
        print(f"  NG: {e}")
    except Exception as e:
        ok = False
        print(f"  NG: {e}")
    print("[公開URL]")
    print("  " + (env("PUBLIC_BASE_URL", required=False) or "NG: PUBLIC_BASE_URL が未設定"))
    print("すべてOKです" if ok else "NG の項目を確認してください")


def cmd_set_token(args):
    """クリップボードにコピーしたInstagramトークンを .env に保存する（画面には出さない）"""
    from datetime import datetime
    from deals.config import set_env
    token = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout.strip()
    if not token.startswith("IG") or len(token) < 50 or any(c.isspace() for c in token):
        sys.exit("クリップボードにトークンがありません。トークンをコピーしてからもう一度実行してください")
    set_env("IG_ACCESS_TOKEN", token)
    set_env("IG_TOKEN_REFRESHED_AT", datetime.now().isoformat(timespec="seconds"))
    subprocess.run(["pbcopy"], input="", text=True)  # クリップボードから消しておく
    print(f"保存しました（{token[:6]}…{len(token)}文字）")


def cmd_ig_login(args):
    """リンクページに表示された連携コードを貼り付けてもらい、トークンに交換して保存する"""
    from deals import instagram
    from deals.config import env
    redirect = env("PUBLIC_BASE_URL").rstrip("/") + "/"
    script = ('text returned of (display dialog "リンクページの「コードをコピー」を押してから、ここに貼り付けて「保存」を押してください"'
              ' default answer "" with hidden answer buttons {"キャンセル", "保存"} default button "保存"'
              ' with title "毎日お得便" giving up after 600)')
    code = subprocess.run(["osascript", "-e", script], capture_output=True, text=True).stdout.strip()
    if "code=" in code:
        code = urllib.parse.parse_qs(urllib.parse.urlparse(code).query).get("code", [""])[0]
    code = code.replace("#_", "").strip()
    if len(code) < 20 or any(c.isspace() for c in code):
        sys.exit(f"コードを受け取れませんでした（{len(code)}文字）。もう一度やり直してください")
    days = (instagram.exchange_code(code, redirect) or 0) // 86400
    subprocess.run(["pbcopy"], input="", text=True)
    print(f"Instagramのトークンを保存しました（有効期限 約{days}日、自動更新あり）")


def cmd_threads_token(args):
    """Macに入力欄を出して、Threadsのトークンを貼り付けてもらい保存する（画面には表示しない）"""
    from deals import threads_api
    script = ('text returned of (display dialog "Threadsのアクセストークンを貼り付けて「保存」を押してください"'
              ' default answer "" with hidden answer buttons {"キャンセル", "保存"} default button "保存"'
              ' with title "毎日お得便" giving up after 600)')
    token = subprocess.run(["osascript", "-e", script], capture_output=True, text=True).stdout.strip()
    if len(token) < 50 or any(c.isspace() for c in token):
        sys.exit(f"トークンを受け取れませんでした（{len(token)}文字）")
    info = threads_api.save_token(token)
    subprocess.run(["pbcopy"], input="", text=True)
    print(f"Threadsのトークンを保存しました：@{info.get('username')}")


def cmd_tick(args):
    from deals import scheduler
    scheduler.tick()


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draft")
    d.add_argument("--demo", action="store_true")
    d.add_argument("--force", action="store_true")
    d.set_defaults(func=cmd_draft)
    pb = sub.add_parser("publish")
    pb.add_argument("--id")
    pb.set_defaults(func=cmd_publish)
    r = sub.add_parser("review")
    r.add_argument("--port", type=int, default=8765)
    r.set_defaults(func=cmd_review)
    sub.add_parser("refresh-token").set_defaults(func=cmd_refresh)
    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("set-token").set_defaults(func=cmd_set_token)
    sub.add_parser("ig-login").set_defaults(func=cmd_ig_login)
    sub.add_parser("threads-token").set_defaults(func=cmd_threads_token)
    sub.add_parser("tick").set_defaults(func=cmd_tick)
    sub.add_parser("track").set_defaults(func=cmd_track)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
