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

1. https://console.anthropic.com でAPIキーを発行
2. GitHubリポジトリの Settings → Secrets → Actions に `ANTHROPIC_API_KEY` を登録
3. Actions タブ → `Weekly Antenna America Hop Product Update` → Run workflow で動作確認

## 手動でHTMLを再ビルドする方法

```bash
pip install anthropic --break-system-packages
cd hop-automation
python3 scripts/build_html.py
# docs/index.html が更新される
```

## 巡回対象サイト

- **Antenna America**: https://www.antenna-america.com/en/collections/new-arrivals
- **Southbound**: 全スタイルページ（ipa / hazy-ipa / pale-ale / saison / sour / stout / lager / wheat / amber / belgian / porter）

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
- 画像URLはog:imageから取得（?width=400を付与）
- ホップはアロマチャートに未収録のものがあれば hops_tab.js の hops配列と hopDesc オブジェクトにも追加。ただしアロマの0〜5スコアは感覚評価が必要なため自動生成せず、`data/last_run_summary.json`の`hops_needing_aroma_review`に溜まったものを人間(またはAIとユーザーの対話)でレビューしてから追加すること
- ブルワリー名は名寄せ済み（LA Ale Works / Harland / Revision Brewing で統一）。`update_products.py`の`BREWERY_ALIASES`に既知のゆれを追記していく方式
- ビルド後は可能なら `node --check` で構文チェック（ローカル環境にNode.jsが無い場合はPythonで`docs/index.html`内の`var products = [...]`をjson.loadsしてパース確認するだけでも良い）
- 出力ファイル名は `docs/index.html` 固定（GitHub Pages公開用。旧仕様の`hop_aroma_chart_YYYYMMDD.html`は使用しない）
- **2026-08-17時点の状態**: このリポジトリはまだGitHubに一度もpushされておらず、`.github/workflows/weekly-update.yml`の自動実行は稼働していない（ローカルフォルダのみ）。現在の195商品は過去のセッションで手動/対話的に集めたデータ。`update_products.py`は当時Antenna Americaのみ・image/description未取得の実装だったため、Southbound巡回＋image/description取得＋source記録に対応させ、`weekly-update.yml`にHTML自動再生成ステップを追加済み（実運用にはGitHubリポジトリ作成・ANTHROPIC_API_KEYのSecrets登録が必要、README.mdのセットアップ手順を参照）
