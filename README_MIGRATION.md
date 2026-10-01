# ホップ アロマ比較 / 製品ホップ成分表 - 移行ガイド

## 含まれるファイル一覧

```
hop-automation/
├── data/
│   └── products.json          # 全195商品データ（画像・説明文・ホップ・ABV）
├── docs/
│   └── index.html             # 公開用Webページ（GitHub Pages用）
├── scripts/
│   ├── build_html.py          # products.json → index.html を生成するビルドスクリプト
│   ├── hops_tab.js            # ホップアロマチャート（134品種・説明文付き）
│   ├── products_tab.js        # 製品成分表タブ（フィルタ・モーダル・戻る機能）
│   ├── update_products.py     # Antenna America自動巡回スクリプト
│   ├── update_sources.json    # 巡回対象サイト設定
│   └── hops_aroma_data.js     # ホップアロマデータ（旧バージョン・参考用）
├── .github/workflows/
│   └── weekly-update.yml      # 毎週火曜9時(JST)自動実行ワークフロー
├── requirements.txt           # Python依存パッケージ
└── README.md                  # 元のセットアップガイド

```

## GitHub Pagesでの公開手順

1. GitHubで新しいリポジトリを作成（例: `hop-tracker`）
2. このフォルダの中身を全てアップロード
3. Settings → Pages → Branch: main / Folder: /docs → Save
4. 数分後に `https://<ユーザー名>.github.io/hop-tracker/` で公開される

## 自動更新のセットアップ

1. （任意）https://console.anthropic.com でAPIキーを発行し、GitHubリポジトリの Settings → Secrets → Actions に `ANTHROPIC_API_KEY` を登録。未設定でも収集本体は問題なく動作する(説明文からの追加ホップ抽出機能のみ使われない)
2. Actions タブ → `Weekly Antenna America Hop Product Update`（毎週火曜9:00 JST）/ `Monthly Full Catalog Audit`（毎月1日9:00 JST）→ Run workflow で動作確認

## 手動でHTMLを再ビルドする方法

```bash
pip install anthropic --break-system-packages
cd hop-automation
python3 scripts/build_html.py
# docs/index.html が更新される
```

## 巡回対象サイト

各サイトが公開しているShopify標準の `products.json` フィード(`{base_url}/products.json?limit=250&page=N`)を
全ページ巡回する(2026-09〜。コレクションページのHTMLスクレイピングは誤検出が多く廃止済み、詳細は`scripts/update_sources.json`)。

- **Antenna America**: https://www.antenna-america.com
- **Southbound**: https://southbound.jp

## データの仕様（products.json）

| フィールド | 内容 |
|---|---|
| id | 商品固有ID（削除禁止・追記専用） |
| name | 商品名 |
| brewery | ブリュワリー名 |
| style | ビアスタイル |
| abv | アルコール度数 |
| hops | 使用ホップ一覧（アロマチャートと連動） |
| url | 商品ページURL |
| image | 缶画像URL（?width=400付き） |
| description | 日本語説明文 |
| source | antenna / southbound |
| added | 追加日（YYYY-MM-DD） |

## 更新ルール（Claude引き継ぎ用）

- 既存商品（同一id）は絶対に削除しない
- 新商品は必ず image / description（日本語）/ hops / abv を揃えてから追記。ページ自体がホップ品種を開示していない商品（スタウト・サワー・ラガー・サイダー等に多い）は空配列のままでよい——推測で埋めない
- 画像URLはproducts.jsonフィードの`images[0].src`から取得（?width=400を付与）
- ホップはアロマチャートに未収録のものがあれば hops_tab.js の hops配列と hopDesc オブジェクトにも追加。ただしアロマの0〜5スコアは感覚評価が必要なため自動生成せず、実在確認(BeerMaverick/Hopsteiner/Yakima Chief等の一次情報源)を取った上で追加すること。`data/audit_review.json`の`needs_review.unknown_hop_names`に溜まったものがレビュー対象
- ブルワリー名・ホップ名の表記ゆれは`update_products.py`の`BREWERY_ALIASES`/`HOP_NAME_FIXES`に追記していく方式。新しいゆれを見つけたら必ずそこに追記する(2箇所以上に同じ正規化ロジックを書き写さない)
- 出力ファイル名は `docs/index.html` 固定（GitHub Pages公開用）

## 月次監査（scripts/audit_catalog.py）

週次の`update_products.py`は「新商品の検出」専用の軽量処理であり、以下は拾えない。これを毎月1日に
`monthly-audit.yml`が自動実行して点検する(2026-10-02導入、きっかけは同日に発見した実例: Shopify側のURL変更で
5商品のIDが無効化し、次週の週次実行が「新商品」と誤認して重複追加する一歩手前だった事象):

- 商品の二重登録（ブリュワリー名+商品名の一致で検出）
- 商品ページのURL/IDがサイト側のハンドル変更で無効化していないか
- 説明文中にホップ品種名が埋もれていて構造化欄(hops)に未反映のもの
- hops[]に使われているが hops_tab.js のアロマチャートに未収録の品種名

このうち「表記ゆれの再正規化」と「IDが今も有効なハンドルに一致する商品の欠落フィールド補完」は
機械的に安全なため自動適用される。それ以外（二重登録候補・ハンドル不整合候補・説明文からの
ホップ抽出候補・未知の品種名）は**自動適用せず** `data/audit_review.json` に記録するだけに留める
——いずれも「本当に同一商品か」「実在する品種名か」の判断にWeb検索や人間的判断が必要なため、
誤った自動適用はデータ破損や品種の捏造になり得る。月1回、Claudeが`data/audit_review.json`を読んで
Web検索で裏取りし、安全と確認できたものだけ反映する運用（スケジュール済みタスクとして設定済み）。

- **2026-10-02時点の状態**: GitHub Pagesで公開中、週次(`weekly-update.yml`)・月次(`monthly-audit.yml`)とも
  実運用で動作確認済み。商品492件・ホップ175品種。`ANTHROPIC_API_KEY`は登録されているが値が無効(401)の
  ままだが、収集本体には影響しない(説明文からの追加ホップ抽出機能のみ使われない)
