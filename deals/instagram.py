"""Instagram API with Instagram Login でカルーセル投稿する"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from .config import env, set_env

API = "https://graph.instagram.com/v25.0"


class InstagramError(Exception):
    pass


def _call(method, path, params=None):
    params = params or {}
    url = f"{API}/{path}"
    headers = {"Authorization": f"Bearer {env('IG_ACCESS_TOKEN')}"}
    data = None
    if method == "GET":
        if params:
            url += "?" + urllib.parse.urlencode(params)
    else:
        data = json.dumps(params).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise InstagramError(f"{e.code} {e.read().decode('utf-8', 'replace')}") from None


def _wait_ready(container_id):
    for _ in range(10):
        status = _call("GET", container_id, {"fields": "status_code"}).get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise InstagramError(f"コンテナ {container_id} が {status}")
        time.sleep(30)
    raise InstagramError(f"コンテナ {container_id} の処理がタイムアウト")


def publish_carousel(image_urls, caption):
    ig = env("IG_USER_ID")
    children = []
    for url in image_urls[:10]:
        res = _call("POST", f"{ig}/media", {"image_url": url, "is_carousel_item": True})
        children.append(res["id"])
    for c in children:
        _wait_ready(c)
    carousel = _call("POST", f"{ig}/media", {
        "media_type": "CAROUSEL",
        "children": ",".join(children),
        "caption": caption,
    })["id"]
    _wait_ready(carousel)
    return _call("POST", f"{ig}/media_publish", {"creation_id": carousel})["id"]


def exchange_code(code, redirect_uri):
    """Instagramログインの認証コード → 長期トークン（60日）に交換して .env に保存する"""
    form = urllib.parse.urlencode({
        "client_id": env("IG_APP_ID"),
        "client_secret": env("IG_APP_SECRET"),
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code": code,
    }).encode("utf-8")
    try:
        with urllib.request.urlopen("https://api.instagram.com/oauth/access_token", data=form, timeout=30) as res:
            short = json.loads(res.read().decode("utf-8"))
        url = "https://graph.instagram.com/access_token?" + urllib.parse.urlencode({
            "grant_type": "ig_exchange_token",
            "client_secret": env("IG_APP_SECRET"),
            "access_token": short["access_token"],
        })
        with urllib.request.urlopen(url, timeout=30) as res:
            long = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise InstagramError(f"{e.code} {e.read().decode('utf-8', 'replace')}") from None
    set_env("IG_ACCESS_TOKEN", long["access_token"])
    set_env("IG_TOKEN_REFRESHED_AT", datetime.now().isoformat(timespec="seconds"))
    if short.get("user_id"):
        set_env("IG_LOGIN_USER_ID", str(short["user_id"]))
    return long.get("expires_in")


def me():
    """トークンが正しいか確認し、Instagram ユーザーIDを返す"""
    return _call("GET", "me", {"fields": "user_id,username,account_type"})


def refresh_token_if_needed(force=False):
    """長期トークンは60日で切れるので、30日ごとに更新する"""
    last = env("IG_TOKEN_REFRESHED_AT", required=False)
    if not force and not last:
        # 発行から24時間たたないと更新できないので、初回は記録だけして次回以降に回す
        set_env("IG_TOKEN_REFRESHED_AT", datetime.now().isoformat(timespec="seconds"))
        return False
    if not force and datetime.fromisoformat(last) > datetime.now() - timedelta(days=30):
        return False
    url = "https://graph.instagram.com/refresh_access_token?" + urllib.parse.urlencode({
        "grant_type": "ig_refresh_token",
        "access_token": env("IG_ACCESS_TOKEN"),
    })
    try:
        with urllib.request.urlopen(url, timeout=30) as res:
            token = json.loads(res.read().decode("utf-8"))["access_token"]
    except urllib.error.HTTPError as e:
        if force:
            raise InstagramError(f"{e.code} {e.read().decode('utf-8', 'replace')}") from None
        print(f"  トークン更新に失敗（今のトークンで投稿を続けます）: {e.code}")
        return False
    set_env("IG_ACCESS_TOKEN", token)
    set_env("IG_TOKEN_REFRESHED_AT", datetime.now().isoformat(timespec="seconds"))
    return True
