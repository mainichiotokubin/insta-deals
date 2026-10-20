"""下書きを確認・承認するためのローカル画面"""
import html
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import DRAFTS
from . import store

LABEL = {"pending": "確認待ち", "approved": "承認済み（次の投稿時刻に投稿）", "publishing": "投稿中…",
         "exporting": "iPhoneに送信中…", "exported": "iPhoneに送信済み・投稿待ち",
         "published": "投稿済み", "rejected": "見送り", "failed": "失敗"}

HOWTO = """<div class="card howto"><strong>使い方（手動投稿モード）</strong><ol>
<li>画像とキャプションを確認して、必要ならキャプションを直す</li>
<li>「iPhoneに送る」を押す（写真アプリのアルバム「{name}」とメモアプリに入り、リンクページも更新されます）</li>
<li>iPhoneのインスタで「＋」→ アルバム「{name}」から7枚を順番に選ぶ → メモのキャプションを貼って投稿</li>
<li>投稿できたら「投稿した」を押す</li></ol></div>"""


def _auto_mode():
    from .config import env
    return bool(env("IG_ACCESS_TOKEN", required=False))

CSS = """
:root{--bg:#f6f3f0;--card:#fff;--text:#282323;--sub:#786e69;--accent:#eb463c;--ok:#1f9d55;--line:#e8e0da}
@media (prefers-color-scheme:dark){:root{--bg:#1c1a19;--card:#2a2725;--text:#f2ecea;--sub:#a99f9a;--line:#3a3532}}
body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,"Hiragino Sans",sans-serif}
header{padding:16px;border-bottom:1px solid var(--line)} h1{margin:0;font-size:20px}
main{max-width:1100px;margin:0 auto;padding:16px}
.card{background:var(--card);border-radius:14px;padding:16px;margin-bottom:20px}
.head{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
.badge{font-size:12px;padding:4px 10px;border-radius:99px;background:var(--line)}
.badge.approved,.badge.exported{background:var(--ok);color:#fff}.badge.failed{background:var(--accent);color:#fff}
.strip{display:flex;gap:8px;overflow-x:auto;padding:12px 0}
.strip img{height:300px;border-radius:8px;flex:none}
textarea{width:100%;box-sizing:border-box;height:220px;font:13px/1.5 inherit;background:var(--bg);color:var(--text);border:1px solid var(--line);border-radius:8px;padding:8px}
.btns{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
button{border:0;border-radius:8px;padding:10px 16px;font-size:14px;cursor:pointer;background:var(--line);color:var(--text)}
button.ok{background:var(--ok);color:#fff} button.go{background:var(--accent);color:#fff}
.tip{margin:10px 0 0;padding:8px 12px;border-radius:8px;background:var(--line);font-size:14px}
.tip.early{background:#fff1d6;color:#7a4a00} .tip ul{margin:4px 0 0;padding-left:20px}
.threads{margin-top:12px} .threads summary{cursor:pointer;font-weight:600}
.tp{border-top:1px solid var(--line);padding:10px 0} .tph{font-size:13px;color:var(--sub)}
.tp pre{white-space:pre-wrap;font-family:inherit;font-size:14px;line-height:1.6;background:var(--bg);padding:10px;border-radius:8px}
.tp pre.reply{font-size:12px;word-break:break-all}
.howto ol{margin:8px 0 0;padding-left:20px;font-size:14px;line-height:1.7}
.err{color:var(--accent);font-size:13px;white-space:pre-wrap} .empty{color:var(--sub)}
a{color:inherit}
"""


def _timing_banner(d):
    from . import timing
    reasons = d.get("early_reasons") or []
    if d["status"] not in ("pending", "approved", "exported"):
        return ""
    if not reasons:
        return f'<p class="tip">おすすめ投稿時間：<b>{timing.NORMAL}</b></p>'
    items = "".join(f"<li>{html.escape(r)}</li>" for r in reasons)
    return f'<div class="tip early">⏰ 今日は早めの投稿がおすすめ：<b>{timing.EARLY}</b><ul>{items}</ul></div>'


def _threads_block(d):
    from .threads import TIMES
    posts = d.get("threads") or []
    if not posts:
        return ""
    rows = []
    for p in posts:
        t = TIMES[(p["no"] - 1) % len(TIMES)]
        rows.append(
            f'<div class="tp"><div class="tph">投稿{p["no"]}（型：{html.escape(p["pattern_name"])}／おすすめ {t}／'
            f'画像 {p["image"]}）</div><pre>{html.escape(p["text"])}</pre>'
            '<button type="button" onclick="copyPre(this,0)">本文をコピー</button> '
            f'<pre class="reply">{html.escape(p["reply"])}</pre>'
            '<button type="button" onclick="copyPre(this,1)">返信をコピー</button></div>')
    return f'<details class="threads"><summary>🧵 Threads用の投稿（{len(posts)}件）</summary>{"".join(rows)}</details>'


def _card(d):
    imgs = "".join(f'<img src="/img/{d["id"]}/{n}" alt="">' for n in d["images"])
    links = " ／ ".join(f'<a href="{html.escape(it["url"])}" target="_blank">No.{i}</a>'
                        for i, it in enumerate(d["items"], 1))
    editable = d["status"] in ("pending", "approved", "failed", "rejected", "exported")
    copy = '<button type="button" onclick="copyCap(this)">キャプションをコピー</button>'
    btns = ""
    if editable and _auto_mode():
        btns = ('<div class="btns">'
                '<button class="ok" name="action" value="approve">承認する</button>'
                '<button class="go" name="action" value="publish_now">今すぐ投稿</button>'
                f'{copy}<button name="action" value="reject">見送る</button></div>')
    elif d["status"] == "exported":
        btns = ('<div class="btns"><button class="go" name="action" value="posted">投稿した</button>'
                f'{copy}<button name="action" value="export">もう一度iPhoneに送る</button>'
                '<button name="action" value="reject">見送る</button></div>')
    elif editable:
        btns = ('<div class="btns"><button class="ok" name="action" value="export">iPhoneに送る</button>'
                f'{copy}<button name="action" value="reject">見送る</button></div>')
    demo = "（デモ・投稿不可）" if d.get("demo") else ""
    err = f'<p class="err">{html.escape(d["error"])}</p>' if d.get("error") and d["status"] in ("failed", "exported") else ""
    return f"""<form class="card" method="post" action="/action">
<input type="hidden" name="id" value="{d['id']}">
<div class="head"><strong>{html.escape(d['date_label'])} {d['id']}{demo}</strong>
<span class="badge {d['status']}">{LABEL.get(d['status'], d['status'])}</span></div>
{_timing_banner(d)}<div class="strip">{imgs}</div>
<div style="font-size:13px">商品ページ確認: {links}</div>{err}
{_threads_block(d)}
<p style="margin:12px 0 4px;font-size:13px">インスタのキャプション</p>
<textarea name="caption" {'readonly' if not editable else ''}>{html.escape(d['caption'])}</textarea>
{btns}</form>"""


def _page():
    drafts = store.list_drafts()
    active = [d for d in drafts if d["status"] in ("pending", "approved", "failed", "publishing", "exporting", "exported")]
    done = [d for d in drafts if d["status"] == "published"][-3:]
    body = "".join(_card(d) for d in reversed(active)) or '<p class="empty">確認待ちの下書きはありません</p>'
    if not _auto_mode():
        from .config import settings
        body = HOWTO.format(name=html.escape(settings()["account_name"])) + body
    busy = any(d["status"] in ("exporting", "publishing") for d in drafts)
    if done:
        body += "<h2>最近の投稿</h2>" + "".join(_card(d) for d in reversed(done))
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>お得投稿 確認</title>
{'<meta http-equiv="refresh" content="3">' if busy else ''}
<style>{CSS}</style></head><body><header><h1>お得投稿 確認画面</h1></header><main>{body}</main>
<script>
function copyPre(btn, i){{
  var t = btn.parentElement.querySelectorAll("pre")[i].textContent;
  navigator.clipboard.writeText(t).then(function(){{ btn.textContent = "コピーしました"; }});
}}
function copyCap(btn){{
  var t = btn.closest("form").querySelector("textarea").value;
  navigator.clipboard.writeText(t).then(function(){{ btn.textContent = "コピーしました"; }});
}}
</script></body></html>"""


def _publish_bg(draft_id):
    from cli import publish_draft
    d = store.load_draft(draft_id)
    try:
        publish_draft(d)
    except Exception as e:
        d.update(status="failed", error=str(e))
        store.save_draft(d)


def _export_bg(draft_id):
    from . import export, site
    d = store.load_draft(draft_id)
    done, errors = export.export_for_phone(d)
    if not done:
        d.update(status="failed", error=" / ".join(errors))
        store.save_draft(d)
        return
    # 先に「送信済み」にしてから、リンクページに載せて公開する
    d.update(status="exported", sent_to=done)
    store.save_draft(d)
    try:
        site.push_page(f"ready {d['id']}")
    except Exception as e:
        errors.append(f"リンクページ更新: {e}")
    d["error"] = ("一部できませんでした: " + " / ".join(errors)) if errors else ""
    store.save_draft(d)


def _posted(draft_id):
    from datetime import datetime
    from . import site
    d = store.load_draft(draft_id)
    d.update(status="published", published_at=datetime.now().isoformat(timespec="seconds"), error="")
    store.save_draft(d)
    store.mark_posted(d["items"])
    try:
        site.push_page(f"posted {d['id']}")
    except Exception:
        pass


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            return self._send(200, _page().encode("utf-8"))
        if self.path.startswith("/img/"):
            parts = self.path.split("/")
            if len(parts) == 4 and ".." not in parts[2] + parts[3]:
                f = DRAFTS / parts[2] / parts[3]
                if f.exists():
                    return self._send(200, f.read_bytes(), "image/jpeg")
        self._send(404, b"not found")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
        d = store.load_draft(form.get("id", [""])[0])
        action = form.get("action", [""])[0]
        if d:
            if "caption" in form:
                d["caption"] = form["caption"][0].replace("\r\n", "\n")
            if action == "approve":
                d["status"] = "approved"
            elif action == "reject":
                d["status"] = "rejected"
            elif action == "publish_now" and not d.get("demo"):
                d["status"] = "publishing"
            elif action == "publish_now":
                d.update(status="failed", error="デモの下書きは投稿できません")
            elif action == "export" and d.get("demo"):
                d.update(status="failed", error="デモの下書きは送れません")
            elif action == "export":
                d["status"] = "exporting"
            store.save_draft(d)
            if d["status"] == "publishing":
                threading.Thread(target=_publish_bg, args=(d["id"],), daemon=True).start()
            elif d["status"] == "exporting":
                threading.Thread(target=_export_bg, args=(d["id"],), daemon=True).start()
            elif action == "posted":
                threading.Thread(target=_posted, args=(d["id"],), daemon=True).start()
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, *args):
        pass


def serve(port):
    print(f"確認画面: http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
