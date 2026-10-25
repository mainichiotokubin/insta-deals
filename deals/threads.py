"""Threads用の投稿を作る（1投稿1商品）

2026-10-20 のリサーチ（research/threads_2026-10-20.md）をもとにした作り:
- 本文は1〜3行の短いつぶやき（驚き・反応・共感など）＋「詳しくはリプ欄に」＋ #PR
- 写真は商品写真（文字の入っていないもの）
- 最初の返信に、価格・レビュー・お得ポイント・こんな人に・リンクをまとめる
- 1日1件、リンクなしの「みんなに質問」投稿も作る（反応とフォロワーを増やす用）

ルール:
- 体験談（使ってみた・愛用中など）は書かない。事実（レビュー・価格・ランキング）で引きつける
- 根拠のない「定価より安い」「他より安い」は書かない
- 他の人の投稿の文章をそのまま使わない。型（構成・言い回しのパターン）だけを使う
- 商品を紹介する本文には必ず #PR を付ける
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

# 投稿時間のおすすめ（商品5投稿＋質問投稿）
TIMES = ["7:30", "12:15", "18:00", "20:30", "22:00"]
QUESTION_TIMES = ["8:30", "15:30", "21:15"]

# 商品ジャンルごとの「共感ひとこと」「感情の一言」「こんな人に向いてそう」
TOPICS = [
    (("トイレット",), "トイレットペーパー", "トイレットペーパーのストック、気づいたら最後の1個になってない？🧻",
     "トイレットペーパーをまとめ買いする人、たぶん暮らし上手。", "ストックを切らしたくない人、置き場所に余裕がある人"),
    (("スポンジ",), "キッチンスポンジ", "キッチンスポンジ、すぐヘタって買い替えてない？🧽",
     "スポンジをこまめに替える人、キッチン絶対きれい。", "毎日自炊する人、こまめに替えたい人"),
    (("柔軟剤",), "柔軟剤", "柔軟剤の詰め替え、毎回ドラッグストアから重たいの運んでない？🌸",
     "柔軟剤の香りにこだわる人、すれ違うとき分かる。", "まとめ買いでラクしたい人"),
    (("洗剤",), "洗剤", "洗剤の詰め替え、毎回ドラッグストアから重たいの運んでない？🫧",
     "洗剤をまとめ買いしてる人、買い物上手しかいない。", "まとめ買いでラクしたい人"),
    (("シャンプー", "スカルプ", "頭皮"), "シャンプー", "シャンプー、なんとなく同じの使い続けてない？🧴",
     "シャンプーにこだわる人、髪で分かる。", "頭皮や髪のケアを見直したい人"),
    (("ティッシュ", "ティシュ"), "ティッシュ", "ティッシュの箱、気づいたら空っぽになってない？🤍",
     "ティッシュをまとめ買いしてる人、家の中が平和。", "家族が多い人、ストックを切らしたくない人"),
    (("化粧水", "乳液", "ローション", "エマルジョン", "セラミド", "保湿"), "保湿ケア", "乾燥する季節、保湿どうしてる？💧",
     "保湿をサボらない人、ほんと尊敬する。", "乾燥が気になる人、保湿を見直したい人"),
    (("日焼け止め", "UV"), "日焼け止め", "日焼け止め、毎年なんとなく選んでない？☀️",
     "秋でも日焼け止め塗る人、未来の肌が強い。", "毎日使う日焼け止めを探している人"),
    (("クレンジング", "クレンズ"), "メイク落とし", "メイク落とし、なんとなく同じの使い続けてない？🫧",
     "メイク落としにこだわる人、肌きれいな人多い説。", "メイク落としを見直したい人"),
    (("オイル",), "オイルケア", "ボディや髪の乾燥、オイルでケアしてる？🌿",
     "オイルでケアしてる人、なんかいい匂いする。", "乾燥ケアをシンプルにしたい人"),
    (("パウダ", "ファンデ"), "ベースメイク", "ベースメイク、何使ってる？💄",
     "ベースメイクにお金かける人、正解だと思う。", "崩れにくいベースメイクを探している人"),
    (("ハンドクリーム",), "ハンドクリーム", "手の乾燥、気になってきてない？🤲",
     "ハンドクリーム持ち歩いてる人、優しい人しかいない。", "家事で手が荒れやすい人"),
    (("タオル",), "タオル", "タオル、ゴワゴワしてきたら替えどき🛁",
     "タオルをまとめて新しくする日、ちょっと幸せ。", "タオルをまとめて新しくしたい人"),
    (("歯磨き", "ハミガキ"), "歯みがき粉", "歯みがき粉、なんとなく同じの使ってない？🪥",
     "歯みがき粉にこだわる人、笑顔がまぶしい。", "ホワイトニングケアが気になる人"),
    (("歯ブラシ",), "歯ブラシ", "歯ブラシ、1か月で替えてる？🪥",
     "歯ブラシを毎月替える人、ちゃんとしてる。", "家族分をまとめて買いたい人"),
]
DEFAULT_TOPIC = ("日用品", "日用品って、どうせ買うならお得に買いたいよね🛒",
                 "日用品をお得に買える人、尊敬する。", "日用品をお得に買いたい人")

UNIT = re.compile(r"(\d+)\s*(ロール|個|本|枚|袋|パック|箱|回分|日分)")


def _topic(item):
    # 商品名を優先し、見つからなければ検索キーワードから選ぶ
    for text in (short_name(item["name"], 60), item.get("keyword", "")):
        for words, *rest in TOPICS:
            if any(w in text for w in words):
                return rest
    return list(DEFAULT_TOPIC)


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
    ends_today = end == today.isoformat() and item["point_rate"] > 1
    topic, pain, oneliner, suits = _topic(item)
    return {
        "short": short_name(item["name"]),
        "brand": short_name(item["name"], 14),
        "price": f"{item['price']:,}",
        "count": f"{item['review_count']:,}",
        "avg": f"{item['review_average']:.1f}",
        "emoji": _emoji(item),
        "rank": item.get("rank"),
        "rank_label": item.get("rank_label", ""),
        "point_rate": item["point_rate"],
        "unit": unit[0] if unit else "",
        "per_unit": f"{unit[1]:,}" if unit else "",
        "per_unit_num": unit[1] if unit else None,
        "avg_num": item["review_average"],
        "drop": item.get("drop_pct", 0),
        "low_span": item.get("low_span", 0),
        "lowest": item.get("lowest", False),
        "topic": topic, "pain": pain, "oneliner": oneliner, "suits": suits,
        "deadline_note": ("ポイントアップは今日の23:59まで" if ends_today
                          else "今日は楽天の「5と0のつく日」（23:59まで）" if today.day % 5 == 0 else ""),
    }


def _usable(pattern, f):
    need = set(pattern.get("needs", []))
    if "rank" in need and not (f["rank"] and f["rank"] <= 30):
        return False
    # 「安すぎない？」と言えるのは、1個あたりがはっきり安いときだけ（150円以下）
    if "per_unit" in need and not (f["per_unit_num"] and f["per_unit_num"] <= 150):
        return False
    # 「★◯◯は強すぎ」と言えるのは、評価が本当に高いときだけ（4.6以上）
    if "high_rating" in need and f["avg_num"] < 4.6:
        return False
    # 値下がりの型は、自分で記録した価格で本当に下がっているときだけ
    if "drop" in need and not (f["lowest"] and f["drop"] >= 3):
        return False
    if "points" in need and f["point_rate"] < 5:
        return False
    return True


def _reply(item, f):
    """最初の返信：詳しい情報とリンク"""
    lines = [f"{f['emoji']} {f['short']}", "", f"💴 {f['price']}円（税込）"]
    for b in badges(item):
        lines.append(("👑 " if "ランキング" in b else "📉 " if ("値下がり" in b or "最安値" in b) else "💰 ") + b)
    if f["per_unit"]:
        lines.append(f"🧮 1{f['unit']}あたり約{f['per_unit']}円")
    lines.append(f"⭐️ {f['avg']}（レビュー{f['count']}件）")
    if f["deadline_note"]:
        lines.append(f"⏰ {f['deadline_note']}")
    lines += ["", "こんな人に向いてそう👇", f"・{f['suits']}", "",
              "▼商品はこちら（楽天市場）", item["url"], "", "※価格・ポイントは投稿時点の情報です", "#PR"]
    return "\n".join(lines)


def build_posts(items, today=None, seed=None):
    """商品ごとに1投稿。同じ日に同じ型が重ならないように選ぶ"""
    today = today or date.today()
    rnd = random.Random(seed if seed is not None else today.toordinal())
    patterns = json.loads(PATTERNS.read_text(encoding="utf-8"))["patterns"]
    weights = _pattern_weights()
    used, posts = set(), []
    seen = used_texts()
    for i, item in enumerate(items, 1):
        f = _facts(item, today)
        cands = [p for p in patterns if _usable(p, f) and p["id"] not in used] or \
                [p for p in patterns if _usable(p, f)]
        pat = rnd.choices(cands, weights=[p.get("weight", 1.0) * weights.get(p["id"], 1.0) for p in cands])[0]
        used.add(pat["id"])
        hooks = [h.format(**f) for h in pat["hooks"]]
        fresh = [h for h in hooks if h.split("\n")[0] not in seen]
        if not fresh:  # この型の言い回しはどれも使用済み → 使っていない型を探す
            for alt in sorted(cands, key=lambda p: -p.get("weight", 1)):
                fresh = [h.format(**f) for h in alt["hooks"] if h.format(**f).split("\n")[0] not in seen]
                if fresh:
                    pat = alt
                    break
        hook = rnd.choice(fresh or hooks)
        seen.add(hook.split("\n")[0])
        main = [hook]
        aside_ok = "ポイント" in f["deadline_note"] or i <= 2  # 毎回だとくどいので、日のお知らせは1日2件まで
        if f["deadline_note"] and aside_ok:  # 本文では短く添える
            main.append("（ポイントは今日の23:59まで⏰）" if "ポイント" in f["deadline_note"] else "（今日は5と0のつく日⏰）")
        main += ["", "詳しくはリプ欄に👇", "#PR"]
        posts.append({"no": i, "pattern": pat["id"], "pattern_name": pat["name"],
                      "text": "\n".join(main)[:MAX_LEN], "reply": _reply(item, f)[:MAX_LEN],
                      "image": f"t{i}.jpg", "item_code": item["code"]})
    return posts


def used_texts():
    """これまでに投稿した（または承認済みで予定している）Threadsの文章。同じ文章の繰り返しはスパム判定の原因になる"""
    from . import store
    used = set()
    for d in store.list_drafts():
        if d.get("status") not in ("approved", "published"):
            continue
        used |= set(d.get("threads_questions") or [])
        used |= {p["text"].split("\n")[0] for p in d.get("threads", [])}
    return used


def question_posts(today=None, n=None):
    """リンクなしの「みんなに質問」投稿（商品の宣伝ではないので #PR は不要）。
    同じ質問は二度と使わない。使える質問がなくなったら出さない（繰り返すよりまし）"""
    from .config import settings
    n = settings().get("threads_plan", {}).get("questions", 1) if n is None else n
    qs = json.loads(PATTERNS.read_text(encoding="utf-8")).get("engagement_questions", [])
    used = used_texts()
    return [q for q in qs if q not in used][:n]


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
