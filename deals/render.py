"""投稿用のカルーセル画像（1080x1350 / 4:5）を作る"""
import io
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
FONT_DIR = "/System/Library/Fonts/"
BG = (255, 247, 240)
ACCENT = (235, 70, 60)
DARK = (40, 35, 35)
SUB = (120, 110, 105)
GOLD = (245, 170, 30)
GREEN = (31, 157, 85)


def font(weight, size):
    return ImageFont.truetype(f"{FONT_DIR}ヒラギノ角ゴシック W{weight}.ttc", size)


def _wrap(draw, text, fnt, width, max_lines):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=fnt) > width:
            lines.append(cur)
            cur = ch
            if len(lines) == max_lines:
                break
        else:
            cur += ch
    else:
        lines.append(cur)
        return lines
    lines[-1] = lines[-1][:-1] + "…"
    return lines


def _load_image(src):
    if src.startswith("http"):
        req = urllib.request.Request(src, headers={"User-Agent": "insta-deals/1.0"})
        with urllib.request.urlopen(req, timeout=20) as res:
            return Image.open(io.BytesIO(res.read())).convert("RGB")
    return Image.open(src).convert("RGB")


def _rounded_card(img, box, radius=40, fill=(255, 255, 255)):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=radius, fill=fill)


def _paste_fit(canvas, photo, box):
    x0, y0, x1, y1 = box
    photo = photo.copy()
    photo.thumbnail((x1 - x0, y1 - y0), Image.LANCZOS)
    px = x0 + (x1 - x0 - photo.width) // 2
    py = y0 + (y1 - y0 - photo.height) // 2
    canvas.paste(photo, (px, py))


def _pr_label(d):
    # ステマ規制対応：全スライドに広告表示
    d.rounded_rectangle((48, 44, 168, 100), radius=14, fill=DARK)
    d.text((108, 72), "PR", font=font(7, 34), fill="white", anchor="mm")


def _center(d, y, text, fnt, fill):
    d.text((W // 2, y), text, font=fnt, fill=fill, anchor="mm")


def cover(items, photos, date_label, account):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    _pr_label(d)
    _center(d, 200, date_label, font(6, 44), SUB)
    _center(d, 300, "今日の楽天", font(8, 110), DARK)
    _center(d, 430, "お得まとめ", font(8, 130), ACCENT)
    d.rounded_rectangle((300, 520, 780, 590), radius=35, fill=GOLD)
    _center(d, 555, f"厳選{len(items)}アイテム", font(7, 40), "white")

    # 商品サムネを2x2で並べる
    cell, gap = 400, 30
    left = (W - cell * 2 - gap) // 2
    for i, photo in enumerate(photos[:4]):
        x = left + (i % 2) * (cell + gap)
        y = 640 + (i // 2) * (290 + gap)
        box = (x, y, x + cell, y + 290)
        _rounded_card(img, box, radius=30)
        _paste_fit(img, photo, (box[0] + 20, box[1] + 20, box[2] - 20, box[3] - 20))
    _center(d, H - 70, f"保存して買い物リストに  @{account}", font(5, 34), SUB)
    return img


def item_slide(no, item, photo):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    _pr_label(d)
    # 番号
    d.ellipse((W - 170, 36, W - 50, 156), fill=ACCENT)
    d.text((W - 110, 96), str(no), font=font(8, 64), fill="white", anchor="mm")

    _rounded_card(img, (90, 180, W - 90, 800))
    _paste_fit(img, photo, (130, 210, W - 130, 770))

    # お得ポイントのバッジ（最安値・値下がりは緑、ランキングは赤、ポイントは金）
    from .rakuten import badges
    x = 90
    for text in badges(item):
        color = GREEN if ("最安値" in text or "値下がり" in text) else ACCENT if "ランキング" in text else GOLD
        w = int(d.textlength(text, font=font(8, 40))) + 70
        d.rounded_rectangle((x, 760, x + w, 840), radius=40, fill=color)
        d.text((x + w // 2, 800), text, font=font(8, 40), fill="white", anchor="mm")
        x += w + 16

    y = 865
    for line in _wrap(d, item["name"], font(6, 44), W - 180, 2):
        d.text((90, y), line, font=font(6, 44), fill=DARK)
        y += 60
    price = f"{item['price']:,}"
    d.text((90, 1020), "¥", font=font(8, 70), fill=ACCENT)
    d.text((150, 995), price, font=font(8, 110), fill=ACCENT)
    tax_x = 160 + d.textlength(price, font=font(8, 110))
    d.text((tax_x, 1055), "税込", font=font(5, 36), fill=SUB)

    stars = f"★{item['review_average']:.1f}  （レビュー{item['review_count']:,}件）"
    d.text((90, 1140), stars, font=font(6, 40), fill=GOLD)
    d.rounded_rectangle((90, 1205, 640, 1265), radius=30, fill=DARK)
    d.text((365, 1235), f"商品リンクはプロフから No.{no}", font=font(6, 30), fill="white", anchor="mm")
    d.text((90, 1290), "※価格・ポイントは投稿時点のものです", font=font(4, 26), fill=SUB)
    return img


def ending(account):
    img = Image.new("RGB", (W, H), ACCENT)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((48, 44, 168, 100), radius=14, fill="white")
    d.text((108, 72), "PR", font=font(7, 34), fill=ACCENT, anchor="mm")
    _center(d, 420, "商品リンクは", font(8, 90), "white")
    _center(d, 540, "プロフィールから", font(8, 90), "white")
    _center(d, 680, "番号（No.）で探してね", font(6, 50), "white")
    d.rounded_rectangle((190, 860, 890, 980), radius=60, fill="white")
    _center(d, 920, f"@{account}", font(7, 50), ACCENT)
    _center(d, 1060, "フォローで毎日お得情報が届きます", font(5, 40), "white")
    return img


def render_post(items, out_dir: Path, date_label, account):
    out_dir.mkdir(parents=True, exist_ok=True)
    photos = [_load_image(it["image"]) for it in items]
    slides = [cover(items, photos, date_label, account)]
    slides += [item_slide(i + 1, it, p) for i, (it, p) in enumerate(zip(items, photos))]
    slides.append(ending(account))
    names = []
    for i, s in enumerate(slides):
        name = f"{i:02d}.jpg"
        s.save(out_dir / name, "JPEG", quality=90)
        names.append(name)
    # Threads用：文字の入っていない商品写真（白い正方形に収める）
    for i, p in enumerate(photos, 1):
        sq = Image.new("RGB", (1080, 1080), "white")
        _paste_fit(sq, p.resize((p.width * 2, p.height * 2), Image.LANCZOS) if p.width < 540 else p, (60, 60, 1020, 1020))
        sq.save(out_dir / f"t{i}.jpg", "JPEG", quality=92)
    return names
