"""楽天市場商品検索APIから「お得な」商品候補を集める"""
import json
import re
import time
import urllib.parse
import urllib.request

from .config import env, settings

ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"


def _get(params):
    params = {
        "applicationId": env("RAKUTEN_APP_ID"),
        "affiliateId": env("RAKUTEN_AFFILIATE_ID"),
        "format": "json",
        "formatVersion": 2,
        **params,
    }
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "accessKey": env("RAKUTEN_ACCESS_KEY"),
        # 一部環境で Referer なしだと HTTP_REFERRER_MISSING になる報告があるため付ける
        "Referer": env("PUBLIC_BASE_URL", required=False) or "https://example.com",
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
    name = re.sub(r"[★☆◆◇■□●○♪！!]+", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def search_candidates(exclude_codes=()):
    s = settings()
    found = {}
    for kw in s["search_keywords"]:
        params = {
            "keyword": kw,
            "sort": "-reviewCount",
            "hits": 30,
            "availability": 1,
            "imageFlag": 1,
            "maxPrice": s["max_price"],
        }
        if s.get("only_point_up"):
            params["pointRateFlag"] = 1
        try:
            data = _get(params)
        except Exception as e:  # 1キーワード失敗しても続ける
            print(f"  [楽天] '{kw}' の取得に失敗: {e}")
            continue
        for it in data.get("Items", []):
            it = it.get("Item", it)  # formatVersion=1 でも動くように
            code = it["itemCode"]
            if code in exclude_codes or code in found:
                continue
            if it.get("reviewCount", 0) < s["min_review_count"]:
                continue
            if float(it.get("reviewAverage", 0)) < s["min_review_average"]:
                continue
            img = _image_url(it)
            if not img:
                continue
            found[code] = {
                "code": code,
                "name": _clean_name(it["itemName"]),
                "price": int(it["itemPrice"]),
                "point_rate": int(it.get("pointRate") or 1),
                "review_average": float(it.get("reviewAverage", 0)),
                "review_count": int(it.get("reviewCount", 0)),
                "shop": it.get("shopName", ""),
                "image": img,
                "url": it.get("affiliateUrl") or it["itemUrl"],
                "keyword": kw,
            }
        time.sleep(1.1)  # 楽天APIは1秒1リクエストまで
    return list(found.values())


def score(item):
    """ポイント倍率とレビューの多さを重視した「お得度」"""
    return item["point_rate"] * 10 + item["review_average"] * 5 + min(item["review_count"], 5000) / 500
