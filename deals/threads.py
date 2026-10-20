"""Threads用の投稿文を作る（1投稿1商品で深掘り、リンクは最初の返信に貼る）

ルール:
- 体験談（使ってみた・愛用中など）は書かない。レビュー件数・評価・価格などの事実で引きつける
- 他の人の投稿の文章をそのまま使わない。型（構成・言い回しのパターン）だけを使う
- 本文の最後に必ず #PR を付ける（広告であることの表示）
"""
import json
import random
import re
from datetime import date

from .caption import _emoji, short_name
from .config import DATA, ROOT
from .rakuten import badges

PATTERNS = ROOT / "threads_patterns.json"
LOG = DATA / "threads_log.json"
MAX_LEN = 500  # Threads の文字数上限

# 商品ジャンルごとの「共感ひとこと」と「こんな人に向いてそう」
TOPICS = [
    (("トイレット",), "トイレットペーパー", "トイレットペーパーのストック、気づいたら最後の1個になってない？🧻", "ストックを切らしたくない人、置き場所に余裕がある人"),
    (("スポンジ",), "キッチンスポンジ", "キッチンスポンジ、すぐヘタって買い替えてない？🧽", "毎日自炊する人、こまめに替えたい人"),
    (("柔軟剤",), "柔軟剤", "柔軟剤の詰め替え、毎回ドラッグストアから重たいの運んでない？🌸", "まとめ買いでラクしたい人"),
    (("洗剤",), "洗剤", "洗剤の詰め替え、毎回ドラッグストアから重たいの運んでない？🫧", "まとめ買いでラクしたい人"),
    (("シャンプー",), "シャンプー", "シャンプー、なんとなく同じの使い続けてない？🧴", "頭皮や髪のケアを見直したい人"),
    (("化粧水", "乳液", "セラミド", "保湿"), "保湿ケア", "乾燥する季節、保湿どうしてる？💧", "大容量でケチらず使いたい人、乾燥が気になる人"),
    (("日焼け止め", "UV"), "日焼け止め", "日焼け止め、毎年なんとなく選んでない？☀️", "毎日使う日焼け止めを探している人"),
    (("クレンジング",), "メイク落とし", "メイク落とし、なんとなく同じの使い続けてない？🫧", "メイク落としを見直したい人"),
    (("オイル",), "オイルケア", "ボディや髪の乾燥、オイルでケアしてる？🌿", "乾燥ケアをシンプルにしたい人"),
    (("パウダ", "ファンデ"), "ベースメイク", "ベースメイク、何使ってる？💄", "崩れにくいベースメイクを探している人"),
    (("ハンドクリーム",), "ハンドクリーム", "手の乾燥、気になってきてない？🤲", "家事で手が荒れやすい人"),
    (("タオル",), "タオル", "タオル、ゴワゴワしてきたら替えどき🛁", "タオルをまとめて新しくしたい人"),
    (("歯ブラシ",), "歯ブラシ", "歯ブラシ、1か月で替えてる？🪥", "家族分をまとめて買いたい人"),
]
DEFAULT_TOPIC = ("日用品", "日用品って、どうせ買うならお得に買いたいよね🛒", "日用品をお得に買いたい人")

UNIT = re.compile(r"(\d+)\s*(ロール|個|本|枚|袋|パック|箱|回分|日分)")


def _topic(item):
    # 商品名を優先し、見つからなければ検索キーワードから選ぶ
    for text in (short_name(item["name"], 60), item.get("keyword", "")):
        for words, topic, pain, suits in TOPICS:
            if any(w in text for w in words):
                return topic, pain, suits
    return DEFAULT_TOPIC


def _per_unit(item):
    """商品名から入り数を読み取って、1個あたりの価格を出す（多い方の数字を使う）"""
    found = [(int(n), u) for n, u in UNIT.findall(item["name"]) if int(n) >= 2]
    if not found:
        return None
    n, unit = max(found)
    return unit, max(1, round(item["price"] / n))


def _facts(item, today):
    unit = _per_unit(item)
    end = (item.get("point_end") or "")[:10]
    return {
        "short": short_name(item["name"]),
        "price": f"{item['price']:,}",
        "count": f"{item['review_count']:,}",
        "avg": f"{item['review_average']:.1f}",
        "emoji": _emoji(item),
        "rank": item.get("rank"),
        "rank_label": item.get("rank_label", ""),
        "point_rate": item["point_rate"],
        "unit": unit[0] if unit else "",
        "per_unit": f"{unit[1]:,}" if unit else "",
        "deadline": (end == today.isoformat() and item["point_rate"] > 1) or today.day % 5 == 0,
        "deadline_note": ("ポイントアップは今日の23:59まで" if end == today.isoformat() and item["point_rate"] > 1
                          else "今日は楽天の「5と0のつく日」（23:59まで）" if today.day % 5 == 0 else ""),
    }


def _usable(pattern, f):
    need = set(pattern.get("needs", []))
    if "rank" in need and not (f["rank"] and f["rank"] <= 30):
        return False
    if "per_unit" in need and not f["per_unit"]:
        return False
    if "points" in need and f["point_rate"] < 5:
        return False
    if "deadline" in need and not f["deadline"]:
        return False
    return True


def _body(item, f, topic, suits):
    lines = [f"{f['emoji']} {f['short']}", "", f"💴 {f['price']}円（税込）"]
    for b in badges(item):
        lines.append(("👑 " if "ランキング" in b else "📉 " if ("値下がり" in b or "最安値" in b) else "💰 ") + b)
    if f["per_unit"]:
        lines.append(f"🧮 1{f['unit']}あたり約{f['per_unit']}円")
    lines.append(f"⭐️ {f['avg']}（レビュー{f['count']}件）")
    if f["deadline_note"]:
        lines.append(f"⏰ {f['deadline_note']}")
    lines += ["", f"こんな人に向いてそう👇", f"・{suits}"]
    return lines


def build_posts(items, today=None, seed=None):
    """商品ごとに1投稿。同じ日に同じ型が重ならないように選ぶ"""
    today = today or date.today()
    rnd = random.Random(seed if seed is not None else today.toordinal())
    patterns = json.loads(PATTERNS.read_text(encoding="utf-8"))["patterns"]
    weights = _pattern_weights()
    used, posts = set(), []
    for i, item in enumerate(items, 1):
        f = _facts(item, today)
        topic, pain, suits = _topic(item)
        f.update(pain=pain, topic=topic)
        cands = [p for p in patterns if _usable(p, f) and p["id"] not in used] or \
                [p for p in patterns if _usable(p, f)]
        pat = rnd.choices(cands, weights=[weights.get(p["id"], 1.0) for p in cands])[0]
        used.add(pat["id"])
        hook = rnd.choice(pat["hooks"]).format(**f)
        text = "\n".join([hook, ""] + _body(item, f, topic, suits) + ["", "リンクはリプ欄に置いておきます👇", "", "#PR"])
        if len(text) > MAX_LEN:
            text = text[:MAX_LEN - 6] + "…\n#PR"
        reply = f"▼商品はこちら（楽天市場）\n{item['url']}\n\n他のお得も毎日まとめてます📦\nプロフィールのリンクからどうぞ"
        posts.append({"no": i, "pattern": pat["id"], "pattern_name": pat["name"], "text": text,
                      "reply": reply, "image": f"{i:02d}.jpg", "item_code": item["code"]})
    return posts


def _pattern_weights():
    """自分の投稿の閲覧数が記録されていれば、伸びた型を多めに使う"""
    if not LOG.exists():
        return {}
    log = json.loads(LOG.read_text(encoding="utf-8"))
    views = {}
    for row in log:
        if row.get("views") is not None:
            views.setdefault(row["pattern"], []).append(row["views"])
    if not views:
        return {}
    avg_all = sum(sum(v) for v in views.values()) / sum(len(v) for v in views.values())
    # 平均より伸びた型ほど重く（0.5〜2倍の範囲）
    return {p: min(2.0, max(0.5, (sum(v) / len(v)) / avg_all)) for p, v in views.items()}


def log_posts(draft_id, posts):
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else []
    log = [r for r in log if r["draft_id"] != draft_id]
    for p in posts:
        log.append({"draft_id": draft_id, "no": p["no"], "pattern": p["pattern"],
                    "item_code": p["item_code"], "views": None})
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


# 投稿時間のおすすめ（1日5投稿を分散）
TIMES = ["7:30", "12:15", "18:00", "20:30", "22:00"]
