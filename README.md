# Antenna America ホップ製品 自動更新システム

毎週火曜日に Antenna America の在庫ありページを確認し、新商品が追加されていれば
Claude API でホップ・スタイル・ABV を自動抽出して `data/products.json` に追記、
`docs/index.html`（ホップアロマ比較 + 製品成分表の2タブページ）を再生成します。

既存の商品データは削除されず、常に追記のみ行われます。

---

## ⚠️ 最初に必ず確認すること

このスクリプトは Antenna America のサーバーに自動アクセスします。実行前に
`https://www.antenna-america.com/robots.txt` を必ず確認し、対象パス
（`/collections/all` および `/products/*`）が自動クローラーに対して
許可されているか確認してください。

- 許可されていない場合: このスクリプトをそのまま使うことはできません。
  Antenna America に問い合わせて公式フィード（RSS/API等）の提供がないか確認するか、
  許可された範囲内に対象を絞ってください。
- 許可されている場合: 念のためアクセス頻度を週1回に抑え、サーバー負荷をかけない
  よう本スクリプトの `time.sleep(1)` 等のマナー設定を変更しないでください。

---

## 必要なもの

1. **GitHubアカウント**（無料）
2. **Anthropic APIキー**（Claude API用）
   - https://console.anthropic.com/ でアカウント作成し、API Keysページで発行
   - 従量課金です。商品数件〜数十件の解析なら月額は数十円〜数百円程度の見込みです
3. このリポジトリ一式

---

## セットアップ手順

### 1. GitHubにリポジトリを作成

1. GitHubで新しいリポジトリを作成（例: `hop-tracker`）
2. このフォルダの中身（`.github/`, `scripts/`, `data/`, `requirements.txt`, `README.md`）
   をすべてアップロード（GitHub Desktop、`git push`、またはWeb UIのドラッグ&ドロップでOK）

### 2. Anthropic APIキーをGitHub Secretsに登録

1. リポジトリの `Settings` → `Secrets and variables` → `Actions` を開く
2. `New repository secret` をクリック
3. Name: `ANTHROPIC_API_KEY`
4. Secret: 発行したAPIキーを貼り付けて保存

### 3. GitHub Pagesを有効化（Webページとして公開する場合）

1. リポジトリの `Settings` → `Pages` を開く
2. Source を `Deploy from a branch` に設定
3. Branch を `main` / フォルダを `/docs` に設定して保存
4. 数分後、`https://<ユーザー名>.github.io/<リポジトリ名>/` でページが公開されます

### 4. 動作確認（手動実行）

1. リポジトリの `Actions` タブを開く
2. 左メニューの `Weekly Antenna America Hop Product Update` を選択
3. 右側の `Run workflow` ボタンを押して手動実行
4. 数分後、緑のチェックマークが出れば成功
5. `data/products.json` に新商品が追記されているか確認

これ以降は、設定済みの cron（毎週火曜 9:00 JST）に従って自動実行されます。

---

## ファイル構成

```
hop-automation/
├── .github/workflows/weekly-update.yml  # 自動実行スケジュール定義
├── scripts/
│   ├── update_products.py     # メイン処理: 新商品検出 + Claude APIで解析
│   ├── build_html.py          # products.json → docs/index.html を生成
│   └── hops_aroma_data.js     # 133品種のアロマデータ(固定・変更不要)
├── data/
│   ├── products.json          # 製品データ本体(自動追記される)
│   └── last_run_summary.json  # 直近の実行結果サマリー(自動生成)
├── docs/
│   └── index.html             # 公開用Webページ(自動生成、GitHub Pages用)
└── requirements.txt
```

---

## カスタマイズ

- **実行曜日・時刻を変える**: `.github/workflows/weekly-update.yml` の
  `cron: '0 0 * * 2'` を編集（UTC基準。現在は火曜9:00 JST = 火曜0:00 UTC）
- **通知を追加したい**: ワークフローの最後に Slack Webhook や
  メール送信ステップを追加できます（`data/last_run_summary.json` の内容を使用）
- **HTML自動再生成を組み込みたい**: `weekly-update.yml` の
  `Run update script` の後に `python scripts/build_html.py` の実行ステップと
  `docs/index.html` のコミットを追加してください

---

## 制限事項・注意点

- Claude APIの解析結果は完璧ではありません。月1回程度、`data/products.json` を
  目視確認し、明らかな誤りがあれば手動で修正することをおすすめします。
- サイトのHTML構造が変わると `extract_product_links` の抽出が失敗する可能性が
  あります。その場合はワークフローのログを確認し、`scripts/update_products.py`
  の正規表現を調整してください。
- これはAntenna Americaの非公式な自動取得です。サイト側の利用規約・robots.txt
  の方針が変わった場合は速やかに運用を停止してください。
