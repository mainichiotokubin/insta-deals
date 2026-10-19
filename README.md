# insta-deals — 楽天お得情報 Instagram 自動投稿

毎朝、楽天市場から「レビュー評価が高く、ポイントアップ中」の日用品・コスメを選び、
カルーセル画像7枚とキャプションを自動で作ります。確認画面で **承認したものだけ** が
12:00 / 20:00 に Instagram へ投稿されます。商品リンクはプロフィールのリンクページ
（GitHub Pages）にまとめられ、そこから楽天アフィリエイト報酬が発生します。

```
毎朝7:00  楽天API → 商品選定 → 画像・キャプション作成 → Mac に通知
  ↓ あなたが http://127.0.0.1:8765 で確認・修正・承認
12:00/20:00  画像とリンクページを GitHub Pages に公開 → Instagram API で投稿
```

## 初期設定（最初に1回だけ）

### 1. 楽天
1. [楽天アフィリエイト](https://affiliate.rakuten.co.jp/) に登録し、アフィリエイトIDを控える
2. [楽天ウェブサービス](https://webservice.rakuten.co.jp/) で「アプリID発行」
   → **アプリケーションID** と **アクセスキー** を控える
   （アプリURLには手順3の GitHub Pages の URL を入れる）

### 2. Instagram
1. お得情報用のアカウントを新しく作り、設定 →「プロアカウントに切り替える」→ **クリエイター** を選ぶ
2. [Meta for Developers](https://developers.facebook.com/) でアプリを作成（ユースケース：Instagram API を管理）
3. 「Instagram ログインによる API 設定」で自分のアカウントを追加し、
   権限 `instagram_business_basic` と `instagram_business_content_publish` で
   **アクセストークンを生成** → トークンと Instagram ユーザーID を控える
   （自分のアカウントだけで使うならアプリ審査は不要です）

### 3. GitHub Pages（画像とリンクページの公開先）
1. GitHub で **公開** リポジトリ `insta-deals` を作る
2. このフォルダで:
   ```bash
   git add . && git commit -m "初期設定"
   git remote add origin https://github.com/<あなたのユーザー名>/insta-deals.git
   git push -u origin main
   ```
3. リポジトリの Settings → Pages → Branch: `main` / フォルダ: `/docs` を選んで保存
4. `https://<ユーザー名>.github.io/insta-deals` を Instagram プロフィールのリンクに設定

※ `.env`（キー類）と `data/`（下書き）は `.gitignore` 済みなので公開されません。

### 4. キーを設定
```bash
cp .env.example .env
```
`.env` を開いて、上で控えた値をすべて入れる。
`settings.json` の `instagram_handle` を自分のアカウント名（@なし）に変える。

### 5. 動作確認 → 定期実行の登録
```bash
.venv/bin/python cli.py check          # キーが正しく設定できているか確認
.venv/bin/python cli.py draft          # 本番データで下書きを1件作る
.venv/bin/python cli.py review         # http://127.0.0.1:8765 で確認・「今すぐ投稿」で1件テスト
.venv/bin/python install_schedule.py   # 問題なければ毎日の自動実行を登録
```

## 手動投稿モード（Instagram API 連携前）
`.env` に `IG_ACCESS_TOKEN` がない間は、確認画面が手動投稿モードになります。
1. 確認画面で「iPhoneに送る」→ 画像が写真アプリのアルバム「毎日お得便」に、キャプションがメモアプリに入り、リンクページも更新される
2. iPhoneのインスタでアルバムから7枚を選び、メモのキャプションを貼って投稿
3. 確認画面で「投稿した」を押す

## 毎日の使い方
- 朝、Mac に「下書きができました」通知 → http://127.0.0.1:8765 を開く
- 画像とキャプションを確認（No.1〜5 のリンクで価格が合っているか確認）→ **承認する**
- 12:00・20:00 に承認済みの下書きが1件ずつ投稿される（Mac がスリープ中だと動きません）

## 設定 (`settings.json`)
| 項目 | 意味 |
|---|---|
| `search_keywords` | 楽天で探すキーワード。ジャンルを変えるならここ |
| `min_review_count` / `min_review_average` | 品質フィルタ（レビュー件数・評価） |
| `max_price` | 価格の上限 |
| `only_point_up` | ポイントアップ中の商品だけにする |
| `repost_after_days` | 同じ商品を再投稿するまでの日数 |
| `publish_times` | 投稿時刻（変えたら `install_schedule.py` を再実行） |

## 守っていること
- **ステマ規制（景品表示法）**：画像すべてに「PR」表示、キャプション冒頭に `#PR` と
  アフィリエイト利用の明記、リンクページにも PR 表示
- 価格・ポイントは変わるため、「投稿時点の情報」と明記
- Instagram の公式 API だけを使う（いいね・フォローの自動化はしない＝凍結リスクを避ける）
- Instagram のトークン（60日で期限切れ）は投稿時に自動更新

## コマンド
```bash
.venv/bin/python cli.py draft --demo             # 楽天APIなしで見た目だけ試す
.venv/bin/python cli.py publish --id 20261017-070000  # 指定の下書きを投稿
.venv/bin/python cli.py refresh-token            # トークンを手動更新
.venv/bin/python install_schedule.py --uninstall # 定期実行を解除
```
ログ: `data/logs/`
