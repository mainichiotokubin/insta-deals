"""Threads API（投稿・返信・閲覧数の取得・トークン更新）"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from .config import env, set_env

API = "https://graph.threads.net/v1.0"


class ThreadsError(Exception):
    pass


def _call(method, path, params=None):
    params = dict(params or {})
    params["access_token"] = env("THREADS_ACCESS_TOKEN")
    url = f"{API}/{path}"
    data = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ThreadsError(f"{e.code} {e.read().decode('utf-8', 'replace')}") from None


def me():
    return _call("GET", "me", {"fields": "id,username"})


def _publish(container_id):
    # 作成直後は処理中のことがあるので、公開できる状態になるまで待つ
    for _ in range(10):
        status = _call("GET", container_id, {"fields": "status,error_message"})
        if status.get("status") == "FINISHED":
            break
        if status.get("status") == "ERROR":
            raise ThreadsError(status.get("error_message", "コンテナの作成に失敗"))
        time.sleep(10)
    return _call("POST", "me/threads_publish", {"creation_id": container_id})["id"]


def post(text, image_url=None, reply_to=None):
    params = {"media_type": "IMAGE" if image_url else "TEXT", "text": text}
    if image_url:
        params["image_url"] = image_url
    if reply_to:
        params["reply_to_id"] = reply_to
    container = _call("POST", "me/threads", params)["id"]
    time.sleep(5)
    return _publish(container)


def views(media_id):
    """投稿の閲覧数・いいね・返信数"""
    data = _call("GET", f"{media_id}/insights", {"metric": "views,likes,replies"})
    out = {}
    for m in data.get("data", []):
        out[m["name"]] = (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value"))
    return out


def save_token(token):
    """トークンが毎日お得便のものか確かめてから保存する"""
    set_env("THREADS_ACCESS_TOKEN", token)
    info = me()
    set_env("THREADS_USER_ID", info["id"])
    set_env("THREADS_TOKEN_REFRESHED_AT", datetime.now().isoformat(timespec="seconds"))
    return info


def refresh_token_if_needed():
    """長期トークン（60日）を30日ごとに更新する"""
    last = env("THREADS_TOKEN_REFRESHED_AT", required=False)
    if last and datetime.fromisoformat(last) > datetime.now() - timedelta(days=30):
        return False
    url = "https://graph.threads.net/refresh_access_token?" + urllib.parse.urlencode({
        "grant_type": "th_refresh_token", "access_token": env("THREADS_ACCESS_TOKEN")})
    try:
        with urllib.request.urlopen(url, timeout=30) as res:
            token = json.loads(res.read().decode("utf-8"))["access_token"]
    except urllib.error.HTTPError as e:
        print(f"  Threadsトークンの更新に失敗（今のトークンで続けます）: {e.code}")
        return False
    set_env("THREADS_ACCESS_TOKEN", token)
    set_env("THREADS_TOKEN_REFRESHED_AT", datetime.now().isoformat(timespec="seconds"))
    return True
