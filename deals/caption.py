"""投稿キャプションを作る"""

NUMS = "①②③④⑤⑥⑦⑧⑨⑩"


def build_caption(items, date_label, s):
    lines = [
        "#PR 楽天アフィリエイトを利用しています",
        "",
        f"【{date_label}】今日の楽天お得まとめ",
        "レビュー評価が高く、ポイントアップ中のアイテムを集めました！",
        "",
    ]
    for i, it in enumerate(items):
        pt = f"／ポイント{it['point_rate']}倍" if it["point_rate"] > 1 else ""
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
