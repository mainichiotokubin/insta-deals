"""楽天市場から「お得な」商品候補を集める（キーワード検索＋ランキング）"""
import json
import re
import time
import urllib.parse
import urllib.request

from .config import env, settings

ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
RANKING = "https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601"


def _get(params, endpoint=ENDPOINT):
    params = {
        "applicationId": env("RAKUTEN_APP_ID"),
        "affiliateId": env("RAKUTEN_AFFILIATE_ID"),
        "format": "json",
        "formatVersion": 2,
        **params,
    }
    url = endpoint + "?" + urllib.parse.urlencode(params)
    # 楽天のアプリ設定「許可されたウェブサイト」と一致させるため Referer/Origin を付ける
    site = env("PUBLIC_BASE_URL").rstrip("/")
    origin = "/".join(site.split("/")[:3])
    req = urllib.request.Request(url, headers={
        "accessKey": env("RAKUTEN_ACCESS_KEY"),
        "Referer": site + "/",
        "Origin": origin,
        "User-Agent": "insta-deals/1.0",
    })
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode("utf-8"))


def _image_url(item):
    urls = item.get("mediumImageUrls") or []
    if not urls:
        return None
    url = urls[0]["imageUrl"] if isinstance(urls[0], dict) else urls[0]
    # 128x128 のサムネを大きいサイズで取り直す
    return re.sub(r"\?_ex=\d+x\d+", "", url) + "?_ex=600x600"


def _clean_name(name):
    # 【】や★などの装飾を落として短くする
    name = re.sub(r"[【\[].*?[】\]]", " ", name)
    name = re.sub(r"[＼\\].*?[／]", " ", name)  # ＼10/19限定 P10倍／ のような期間限定の告知
    name = re.sub(r"\d{1,2}/\d{1,2}\s*(限定|まで|は|から)\S*", " ", name)
    name = re.sub(r"(ポイント|P)\s*\d+\s*倍", " ", name)  # バッジと重複するので消す
    name = re.sub(r"[★☆◆◇■□●○♪！!]+", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def _normalize(it, s, group):
    """APIの商品データを共通の形にする。条件に合わなければ None"""
    name = it.get("itemName", "")
    if any(w in name for w in s.get("exclude_words", [])):
        return None
    if it.get("hasPriceRange") or not int(it.get("availability", 1)):
        return None  # 「選べる」で価格が幅のある商品は、表示価格がずれるので除外
    if int(it.get("itemPrice", 0)) > s["max_price"]:
        return None
    if int(it.get("reviewCount", 0)) < s["min_review_count"]:
        return None
    if float(it.get("reviewAverage", 0)) < s["min_review_average"]:
        return None
    img = _image_url(it)
    if not img:
        return None
    return {
        "code": it["itemCode"],
        "name": _clean_name(name),
        "price": int(it["itemPrice"]),
        "point_rate": int(it.get("pointRate") or 1),
        "review_average": float(it.get("reviewAverage", 0)),
        "review_count": int(it.get("reviewCount", 0)),
        "shop": it.get("shopName", ""),
        "image": img,
        "url": it.get("affiliateUrl") or it["itemUrl"],
        "keyword": group,
        "rank": None,
    }


def _keyword_items(s):
    out = []
    for kw in s["search_keywords"]:
        params = {"keyword": kw, "sort": "-reviewCount", "hits": 30, "availability": 1,
                  "imageFlag": 1, "maxPrice": s["max_price"]}
        if s.get("only_point_up"):
            params["pointRateFlag"] = 1
        try:
            data = _get(params)
        except Exception as e:  # 1キーワード失敗しても続ける
            print(f"  [楽天] '{kw}' の取得に失敗: {e}")
            continue
        for it in data.get("Items", []):
            item = _normalize(it.get("Item", it), s, kw)
            if item:
                out.append(item)
        time.sleep(1.1)  # 楽天APIは1秒1リクエストまで
    return out


def _ranking_items(s):
    out = []
    for label, genre in s.get("ranking_genres", {}).items():
        for page in range(1, s.get("ranking_pages", 2) + 1):
            try:
                data = _get({"genreId": genre, "page": page}, RANKING)
            except Exception as e:
                print(f"  [楽天] ランキング '{label}' p{page} の取得に失敗: {e}")
                break
            for it in data.get("Items", []):
                it = it.get("Item", it)
                item = _normalize(it, s, f"ランキング:{label}")
                if item:
                    item["rank"] = int(it["rank"])
                    item["rank_label"] = label
                    out.append(item)
            time.sleep(1.1)
    return out


def search_candidates(exclude_codes=()):
    """キーワード検索とランキングの候補を合わせる。両方に出た商品はランキング順位を引き継ぐ"""
    from . import prices
    s = settings()
    found = {}
    for item in _keyword_items(s) + _ranking_items(s):
        prev = found.get(item["code"])
        if prev:
            if item["rank"] and not prev["rank"]:
                prev.update(rank=item["rank"], rank_label=item["rank_label"])
            prev["point_rate"] = max(prev["point_rate"], item["point_rate"])
            continue
        found[item["code"]] = item
    items = list(found.values())
    prices.annotate(items)  # 今日の価格を記録する前に、過去と比べる
    prices.record(items)
    return [it for it in items if it["code"] not in exclude_codes]


def score(item):
    """お得度：ポイント・売れ筋・レビュー・値下がりをバランスよく足し合わせる（最大およそ200点）"""
    points = min(item["point_rate"], 20) * 3                                # 0〜60
    rank = 40 * max(0.0, 1 - (item["rank"] - 1) / 60) if item.get("rank") else 0  # 1位=40
    review = max(0.0, item["review_average"] - 4.0) * 25 + min(item["review_count"], 5000) / 250  # 0〜45
    drop = min(item.get("drop_pct", 0), 30) * 2 + (15 if item.get("lowest") else 0)  # 0〜75
    return points + rank + review + drop


def badges(item):
    """画像とキャプションに出す「お得ポイント」（強い順に最大2つ）"""
    out = []
    if item.get("lowest"):
        out.append("30日最安値")
    elif item.get("drop_pct", 0) >= 5:
        out.append(f"{item['drop_pct']}%値下がり")
    if item.get("rank") and item["rank"] <= 30:
        out.append(f"ランキング{item['rank']}位")
    if item["point_rate"] > 1:
        out.append(f"ポイント{item['point_rate']}倍")
    return out[:2]
