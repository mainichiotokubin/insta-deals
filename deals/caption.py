"""投稿キャプションを作る"""

from .rakuten import badges

NUMS = "①②③④⑤⑥⑦⑧⑨⑩"


def build_caption(items, date_label, s):
    lines = [
        "#PR 楽天アフィリエイトを利用しています",
        "",
        f"【{date_label}】今日の楽天お得まとめ",
        "売れ筋ランキング・ポイントアップ・値下がり中の高評価アイテムを集めました！",
        "",
    ]
    for i, it in enumerate(items):
        pt = "".join(f"／{b}" for b in badges(it))
        lines.append(f"{NUMS[i]} {it['name'][:40]}")
        lines.append(f"　¥{it['price']:,}{pt}／★{it['review_average']:.1f}（{it['review_count']:,}件）")
    lines += [
        "",
        "商品リンクはプロフィールのリンクから番号で探してね",
        "あとで見返せるように「保存」がおすすめです",
        "",
        "※価格・ポイント倍率・在庫は投稿時点の情報です。購入前に必ず商品ページでご確認ください。",
        "",
        " ".join(s["hashtags"]),
    ]
    return "\n".join(lines)
