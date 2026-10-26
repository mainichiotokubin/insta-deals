"""投稿キャプションを作る（絵文字多め・話しかけるような、やわらかい文章）"""
import re
from datetime import date

from .rakuten import badges

NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

# 毎日同じ書き出しにならないように、日付で順番に切り替える
OPENINGS = [
    "おはようございます☀️\n今日も楽天でお得なもの、見つけてきました🛒✨",
    "今日のお得まとめ、届きました〜📦💌\n気になるものはあるかな？👀",
    "日用品とコスメ、どうせ買うならお得に🫶\n今日のおすすめはこちら👇",
    "ストック切れそうなもの、ありませんか？🧺\n今日のお得をまとめました✨",
    "ポイントもしっかりもらって、賢くお買い物💰\n今日の厳選アイテムです🛍️",
    "今日も1日おつかれさまです🍵\nお得な楽天アイテムをどうぞ💐",
    "買い忘れチェックにどうぞ📝\n今日のお得まとめです🛒",
]

CLOSINGS = [
    "気になるものがあったら、コメントで教えてね💬",
    "「これ使ってる！」って方もぜひコメントで教えてください💭",
    "役に立ったら、いいね❤️で教えてもらえるとうれしいです",
]

# 商品のジャンル（検索キーワード）ごとの絵文字
EMOJI = [
    ("洗剤", "🫧"), ("柔軟剤", "🌸"), ("トイレット", "🧻"), ("ティッシュ", "🤍"), ("ティシュ", "🤍"), ("ローション", "💧"), ("エマルジョン", "💧"), ("シャンプー", "🧴"),
    ("化粧水", "💧"), ("日焼け止め", "☀️"), ("UV", "☀️"), ("クレンジング", "🫧"), ("クレンズ", "🫧"), ("ハンドクリーム", "🤲"),
    ("歯ブラシ", "🪥"), ("歯磨き", "🪥"), ("マスカラ", "👁️"), ("ゲル", "✨"), ("美白", "✨"), ("ごみ箱", "🗑️"), ("ゴミ箱", "🗑️"), ("芳香剤", "🌿"), ("美容液", "✨"), ("エッセンス", "✨"), ("コンディショナー", "🧴"), ("トリートメント", "🧴"), ("シートマスク", "🧖‍♀️"), ("パック", "🧖‍♀️"), ("アイシャドウ", "💄"), ("ディスペンサー", "🧴"), ("洗顔", "🫧"), ("スポンジ", "🧽"), ("タオル", "🛁"), ("オイル", "🌿"), ("乳液", "💧"),
    ("パウダ", "💄"), ("ファンデ", "💄"), ("リップ", "💋"), ("ランキング:コスメ", "💄"), ("ランキング:日用品", "🏠"),
]

BADGE_EMOJI = {"最安値": "📉", "値下がり": "📉", "ランキング": "👑", "ポイント": "💰"}


def _emoji(item):
    # 商品名を優先し、見つからなければ検索キーワードから選ぶ
    for text in (short_name(item["name"]), item.get("keyword", "")):
        for word, e in EMOJI:
            if word in text:
                return e
    return "🛍️"


def short_name(name, limit=26):
    """楽天の長い商品名（キーワードの羅列）を、読みやすい長さに縮める"""
    name = re.split(r"\s*[|｜/／]\s*", name)[0]
    # お店の宣伝文句は落とす
    name = re.sub(r"(最安値に挑戦\S*|送料無料|楽天\S*位\S*|公式|正規品|即納|あす楽)", " ", name)
    out = ""
    for word in name.split():
        if len(out) + len(word) + 1 > limit:
            break
        out = f"{out} {word}".strip()
    return out or name[:limit]


def _badge_line(item):
    parts = []
    for b in badges(item):
        mark = next((e for k, e in BADGE_EMOJI.items() if k in b), "✨")
        parts.append(f"{mark}{b}")
    return "｜".join(parts)


COSME_WORDS = ("化粧水", "乳液", "ローション", "クレンジング", "クレンズ", "日焼け止め", "UV", "リップ", "パウダ",
               "ファンデ", "美容液", "クリーム", "アイシャドウ", "マスカラ", "コスメ", "ヘアオイル", "オイル", "美白", "美容", "シートマスク", "パック", "スキンケア")


def _hashtags(items, s, events):
    """インスタのハッシュタグは5個まで。1行目の #PR を含めて5個になるように選ぶ"""
    limit = s.get("hashtag_limit", 5) - 1  # 1行目の #PR の分
    cosme = sum(1 for it in items if any(w in it["name"] + it.get("keyword", "") for w in COSME_WORDS))
    genre = "#コスメ" if cosme > len(items) / 2 else "#日用品"
    tags = [tag for _, tag in events] + [genre] + [t for t in s["hashtags"] if t != "#PR"]
    out = []
    for t in tags:
        if t not in out:
            out.append(t)
    return out[:limit]


def build_caption(items, date_label, s, events=None):
    """events: 開催中の楽天イベント [(名前, ハッシュタグ)]。None のときはその場で調べる"""
    from .timing import early_reasons
    if events is None:
        from .events import active_events
        events = active_events()
    n = date.today().toordinal()
    lines = [
        "#PR 楽天アフィリエイトを利用しています",
        "",
        f"🗓️ {date_label} の楽天お得まとめ",
        "",
        OPENINGS[n % len(OPENINGS)],
        "",
    ]
    # 今日ならではのお知らせ（イベント・5と0のつく日など）
    news = [f"🎉 楽天「{name}」開催中！" for name, _ in events]
    reasons = early_reasons(items)
    news += ["⏰ " + r for r in reasons if "No." not in r]
    nos = [r.split("の")[0].replace("No.", "") for r in reasons if r.startswith("No.")]
    if nos:  # ポイントアップが今日で終わる商品
        news.append(f"⏰ No.{'・'.join(nos)}のポイントアップは今日の23:59まで！")
    if news:
        lines += news + [""]

    for i, it in enumerate(items):
        lines.append(f"{NUMS[i]} {short_name(it['name'])} {_emoji(it)}")
        price = f"💴 {it['price']:,}円"
        badge = _badge_line(it)
        lines.append(f"　{price}" + (f"｜{badge}" if badge else ""))
        lines.append(f"　⭐️{it['review_average']:.1f}（レビュー{it['review_count']:,}件）")
        lines.append("")

    lines += [
        "🔗 商品リンクはプロフィールのリンクから、番号で探してね",
        "📌 あとで見返せるように「保存」がおすすめです",
        CLOSINGS[n % len(CLOSINGS)],
        "",
        "※価格・ポイント倍率・在庫は投稿時点の情報です。購入前に商品ページで確認してね🙏",
        "",
        " ".join(_hashtags(items, s, events)),
    ]
    return "\n".join(lines)
