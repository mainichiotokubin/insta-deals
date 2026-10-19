"""プロフィールに貼るリンクページ（GitHub Pages）を作って公開する"""
import html
import shutil
import subprocess
import time
import urllib.request

from .config import DRAFTS, ROOT, SITE, env, settings
from .store import list_drafts

PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{account}｜商品リンク</title>
<style>
body{{margin:0;background:#fff7f0;color:#282323;font-family:-apple-system,"Hiragino Sans",sans-serif}}
header{{background:#eb463c;color:#fff;padding:20px 16px;text-align:center}}
header h1{{margin:0;font-size:20px}} header p{{margin:6px 0 0;font-size:12px;opacity:.9}}
main{{max-width:560px;margin:0 auto;padding:16px}}
section{{background:#fff;border-radius:16px;padding:14px;margin-bottom:16px}}
h2{{font-size:16px;margin:0 0 10px}}
a.item{{display:flex;gap:12px;align-items:center;padding:10px 0;border-top:1px solid #f0e6df;color:inherit;text-decoration:none}}
a.item img{{width:72px;height:72px;object-fit:contain;flex:none}}
.no{{background:#eb463c;color:#fff;border-radius:50%;width:28px;height:28px;display:grid;place-items:center;font-weight:700;flex:none}}
.name{{font-size:14px;line-height:1.4}} .price{{color:#eb463c;font-weight:700;margin-top:2px}}
.note{{font-size:11px;color:#786e69;text-align:center;padding:8px 16px 32px}}
</style></head><body>
<header><h1>{account}</h1><p>【PR】当ページは楽天アフィリエイトを利用しています</p></header>
<main>{sections}</main>
<p class="note">価格・ポイント倍率・在庫は投稿時点の情報です。購入前に必ず商品ページでご確認ください。</p>
</body></html>
"""


def build_page(extra_draft=None):
    s = settings()
    drafts = [d for d in list_drafts("published")]
    if extra_draft:
        drafts.append(extra_draft)
    drafts.sort(key=lambda d: d["id"], reverse=True)
    sections = []
    for d in drafts[:20]:  # 新しい20投稿まで載せる
        rows = []
        for i, it in enumerate(d["items"], 1):
            rows.append(
                f'<a class="item" href="{html.escape(it["url"])}" target="_blank" rel="nofollow sponsored">'
                f'<span class="no">{i}</span><img src="{html.escape(it["image"])}" alt="" loading="lazy">'
                f'<div><div class="name">{html.escape(it["name"][:60])}</div>'
                f'<div class="price">¥{it["price"]:,}</div></div></a>'
            )
        sections.append(f"<section><h2>{html.escape(d['date_label'])}のお得まとめ</h2>{''.join(rows)}</section>")
    SITE.mkdir(exist_ok=True)
    (SITE / ".nojekyll").touch()
    (SITE / "index.html").write_text(
        PAGE.format(account=html.escape(s["account_name"]), sections="".join(sections)), encoding="utf-8")


def publish_images(draft):
    """画像を docs/posts/<id>/ にコピーし、git push して公開URLを返す"""
    dest = SITE / "posts" / draft["id"]
    dest.mkdir(parents=True, exist_ok=True)
    for name in draft["images"]:
        shutil.copy(DRAFTS / draft["id"] / name, dest / name)
    build_page(extra_draft=draft)

    def git(*args):
        subprocess.run(["git", *args], cwd=ROOT, check=True)

    git("add", "docs")
    git("commit", "-m", f"post {draft['id']}")
    git("push")

    base = env("PUBLIC_BASE_URL").rstrip("/")
    urls = [f"{base}/posts/{draft['id']}/{n}" for n in draft["images"]]
    # GitHub Pages に反映されるまで待つ（最大10分）
    for _ in range(40):
        try:
            with urllib.request.urlopen(urls[-1], timeout=15) as res:
                if res.status == 200:
                    return urls
        except Exception:
            pass
        time.sleep(15)
    raise RuntimeError("GitHub Pages に画像が反映されませんでした")
