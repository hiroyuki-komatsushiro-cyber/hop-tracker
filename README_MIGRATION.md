# ホップ アロマ比較 / 製品ホップ成分表 - 移行ガイド

## 含まれるファイル一覧

```
hop-automation/
├── data/
│   └── products.json          # 全商品データ（1486件、2026-11-16時点。画像・説明文・ホップ・ABV）
├── docs/
│   └── index.html             # 公開用Webページ（GitHub Pages用）
├── scripts/
│   ├── build_html.py          # products.json → index.html を生成するビルドスクリプト（収集元の表示はupdate_sources.jsonから生成）
│   ├── hops_tab.js            # ホップアロマチャート（233品種・説明文付き）
│   ├── products_tab.js        # 製品成分表タブ（スタイル/度数/並び順の絞り込み・モーダル・戻る機能）
│   ├── style_class.py         # スタイルの細分類(36種)と度数帯。画面の絞り込み用（test_style_class.pyでテスト）
│   ├── hop_text.py            # 説明文からのホップ抽出（test_hop_text.pyでテスト）
│   ├── update_products.py     # 全収集元の自動巡回スクリプト（新商品の追加+登録済み商品の更新。収集先ごとの収集関数はCOLLECTORS/REFRESHERS。test_refresh.pyでテスト）
│   ├── coverage_check.py      # 登録漏れ・更新漏れの総チェック（読み取り専用。python scripts/coverage_check.py）
│   ├── test_wcb.py            # West Coast Brewingの「w/」行(ホップ欄)の解析のテスト（wcb_hops）
│   ├── update_sources.json    # 巡回対象サイトの一覧（ここに1件足すと週次で自動巡回される）
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
2. Actions タブ → `Weekly Hop Product Update (all sources)`（毎週火曜9:00 JST。実際の開始はGitHub混雑で2〜4時間遅れることがある）/ `Monthly Full Catalog Audit`（毎月1日9:00 JST）→ Run workflow で動作確認

## 手動でHTMLを再ビルドする方法

```bash
pip install anthropic --break-system-packages
cd hop-automation
python3 scripts/build_html.py
# docs/index.html が更新される
```

## 巡回対象サイト

**巡回対象は `scripts/update_sources.json` の `sources` に載っている全サイト**で、週次ワークフロー(`weekly-update.yml`)が
全てを順に巡回する。収集先を足すときはこのファイルに1件足すだけで、週次の定期巡回・月次監査・画面の絞り込み/バッジ/注記に
自動で反映される(手順は下の「新しい収集先の追加チェックリスト」)。1つの収集先が失敗しても他の収集先の更新は止まらず、
失敗は `data/last_run_summary.json` の `source_errors` に記録され、ワークフローは最後に失敗扱いになる(GitHubの通知メールで気づける)。
`last_run_summary.json` の `sources` に、収集元ごとの結果(ok/error・追加件数)が毎回残る。

Shopify系(Antenna America / Southbound)は、各サイトが公開しているShopify標準の `products.json` フィード
(`{base_url}/products.json?limit=250&page=N`)を全ページ巡回する(2026-09〜。コレクションページのHTMLスクレイピングは
誤検出が多く廃止済み)。ブルワリー公式サイト系(Vertere / West Coast Brewing)は `type` ごとの収集関数(`COLLECTORS`)で取る。

- **Antenna America**: https://www.antenna-america.com
- **Southbound**: https://southbound.jp
- **Vertere（バテレ、奥多摩のブルワリー公式サイト）**: https://verterebrew.com/brewery-beer/ （2026-10-16追加）。
  WordPressの「brewlog」記事が1銘柄=1記事(約300件)で、個別ページにStyle / Alc / Malt / **Hop** / Yeastが載る
  (ブルワリー自身の公開情報なのでホップが高い確率で取れる)。一覧はWP REST API(`/wp-json/wp/v2/brewlog`)、
  詳細は個別ページのHTMLを解析する(`update_products.py`の`collect_wp_brewlog`/`parse_vertere_page`)。
  通常の週次実行は最新30件を見て、**未登録の記事の個別ページだけ**取得する(小規模な醸造所のサイトなので負荷を最小に)。
  初回の全件取り込みは環境変数 `BACKFILL_SOURCES=vertere`(旧名 `VERTERE_BACKFILL=1` も有効。このとき`added`は記事の公開日にして、
  取り込み直後に全件へNEWバッジが付くのを避ける)。
  idは `vertere-<記事ID>`、`source`は `vertere`。**在庫の概念が無い**ため、サイトに載っている銘柄は過去の醸造分も含めて全て対象
  (他の2サイトのように「販売中のみ」ではない)。月次監査(`audit_catalog.py`)はShopify由来のレコードだけをライブ照合し、
  Vertereは「サイトにあって未登録の記事」を全記事のID一覧と照合する
- **West Coast Brewing（静岡のブルワリー公式サイト）**: https://www.westcoastbrewing.jp/ourbeers/ （2026-10-16追加）。
  `/ourbeers/` の一覧(新しい順に最新12銘柄。`/beer/` アーカイブの1ページ目と同じ内容)から、名前・「スタイル / ABV」・画像・
  **「w/ …」の行(=ホップ。ユーザー指定)** を取り、未登録の銘柄だけ個別ページ(`/beer/<slug>/`)の日本語説明文を取得する
  (`collect_wcb_list`/`parse_wcb_list`)。idは `westcoast-<slug>`、`source`は `westcoast`。
  **「w/」の行の解析は `wcb_hops`(`test_wcb.py`でテスト)**。過去分の行には、副原料(果実・香辛料・乳糖・ナッツ・コーヒー等)、
  「Dry Hopped with …」の文(それより前は副原料の列挙)、供給元・ロットの修飾(Freestyle/EG/Crosby/YCH、PM19・YM23・KM09・25QL・X51X、
  Pikimai=NZの農場名、Diesel、Bliss、Lupulin)、加工品の表記ゆれ(CRYO/Hyper Boost/語順違いのQuantum)、全角記号(＆・ｗ/・「・」)が混ざる。
  ホップ名の判定は**アロマチャートの名前が先**で、チャートに無く副原料の語(`WCB_ADJUNCT_RE`)に当たるものだけを捨てる(Lemon Drop等の実在ホップを捨てないため)。
  どちらでもない名前はそのまま残り、週次の`hops_needing_aroma_review`に出る(新しい副原料が出たら`HOP_NAME_FIXES`の空文字か`WCB_ADJUNCT_RE`に足す)。
  「w/」行が空の銘柄(Seabreeze等)は、説明文に品種名があれば補い(「説明文からのホップ抽出」)、無ければホップ空のまま(推測で埋めない)。
  **WCB固有の落とし穴(2026-11-16に調べて確定)**: ①`Kohia Nelson`はFreestyle Hops社の「ボタニカル・ブレンド」(ホップ+乾燥パッションフルーツ、配合は年で変わる)で、
  Nelson Sauvinとは別物なのでチャートに別項目で追加した。②`Anchovy`は副原料ではなく実在のホップ(Segal Ranch育成の実験品種24B-05)。
  ③`Clean Fusion`はホップではなく製法(発酵後に酵母を除いてドライホップ)。④`Denali`は現在のSultana(Hopsteiner 06277の旧商品名)、`TRI2304CR`はCryo Pop(Yakima Chiefの試験ブレンド名)。
  ⑤`Nelson Sauvin Bliss`はFreestyleが早摘み・遅摘みのNelson Sauvinを組み合わせた製品、`Pikimai`は農場名なので、いずれも元の品種に寄せる。
  出典が見つからず、書かれたとおりに保存している名前(The Bruce / Tropical Fusion / Maui Nelson Kief / NZ04 / HBC 1019 / ADHA 1631 / Jackson Pink / Special X / Super Sauvin / ID158 / 7270 / USDA074 / Mi Copper)は
  `audit_catalog.KNOWN_UNRESOLVED_HOPS`に入れて月次監査に毎回出ないようにしてある(出典が見つかったら外してチャートへ)。
  **一覧の「w/」行と個別ページ本文で食い違う例**: Campfire Storiesは「w/」行がCascade/Centennial/Columbusだが、
  本文(10バッチ目)はChinookを挙げている。ユーザー指定どおり「w/」行を採用している。
  **範囲は全銘柄**: 週次は`/ourbeers/`(最新12銘柄)から新作を取り込み続ける。**過去分(アーカイブ45ページ・540銘柄)は2026-11-16に全件取り込み済み**
  (`BACKFILL_SOURCES=westcoast`。個別ページを1.2秒間隔で約500回取得するので約15分。`added`はWP REST API(`/wp-json/wp/v2/beer`)のCMS公開日にしてNEWバッジの洪水を避けた。
  CMSの日付なので、投稿を使い回した銘柄は実際の醸造より古い日付のことがある。日付が取れない銘柄があれば取得を始める前に失敗する)。
  `robots.txt`は`/wp/wp-admin/`以外を許可。小規模サイトなので1ページ/1.2秒以上の間隔を守る(`REQUEST_DELAY`)。
  月次監査・総チェックは、WP REST APIの全銘柄(6リクエスト)と照合するので、未登録は全て取りこぼしとして出る

## 新しい収集先の追加チェックリスト

「今後追加する収集先も同様に定期巡回する」ための手順。**登録した時点で週次の自動巡回の対象になる**(別途ワークフローを足す必要は無い)。

1. **利用可否の確認**: `robots.txt`と利用規約を読み、巡回が禁止されていないことを確認する(WAFの429等を回避するなりすましはしない)。
   小規模サイトは1ページ/1.2秒以上の間隔(`REQUEST_DELAY`)を守り、一覧+新規の個別ページだけに絞る
2. **データの所在を確認**: Shopifyなら `{base_url}/products.json` があるか。無ければ、一覧/個別ページのHTMLかWP REST API(`/wp-json/wp/v2/...`)のどれで
   名前・スタイル・ABV・ホップ・画像・説明が取れるかを実ページで確かめる。**ホップを書いている場所はサイトごとに違う**
   (例: WCBは「w/」の行、Vertereは個別ページのHop欄、Antennaはスペック欄)ので、ユーザーに場所を確認する
3. **`scripts/update_sources.json` に1件足す**: `name` / `base_url` / `source_key`(idの接頭辞、重複不可) / `kind`(`retailer`=販売中の商品 /
   `brewery`=公式サイト掲載銘柄、見出しと注記の文言が変わる) / `ui`(`filter`=絞り込み名、`badge`/`badge_bg`/`badge_fg`=バッジ、`link`=詳細リンクの文言) / `notes`。
   Shopifyなら`type`省略(ただしAntenna以外のShopifyは`parse_southbound_product`で解析し、除外条件は`update_products.py`の`main()`に足す)。
   それ以外は`type`を決めて次へ。公式サイト系は`brewery`も必須
4. **構造が新しいサイトだけ**: `update_products.py` に収集関数 `collect_xxx(source, known_ids, backfill) -> list[dict]` を書き、`COLLECTORS` に登録する
   (レコードは `id`=`<source_key>-…` / `name` / `brewery` / `style` / `abv` / `hops` / `url` / `image` / `description` / `source` / `added`)。
   **0件は「新着なし」でなく障害**なので例外を投げる(1ソースの失敗は他へ波及せず `source_errors` に記録される)。
   typeが未登録のままだとその回は失敗として報告される(黙って飛ばされない)。
   登録済み銘柄の更新点検をしたい収集先は、`refresh_xxx(source, stored) -> [ライブのレコード]` を書いて `REFRESHERS` にも登録する(任意。無ければ更新点検を飛ばすだけ)
5. **月次監査の対応**: `audit_catalog.py` の `UNREGISTERED_CHECKS` に「サイトにあって未登録の銘柄」の検査関数を足す
   (足し忘れても、月次の`audit_review.json`に`sources_without_completeness_check`として出るので見逃さない)。Shopify系は自動で全件ライブ照合される
6. **ホップ名の整備**: ドライランで出る「[review needed] hop varieties not yet in the aroma chart」を処理する。表記ゆれ・副原料・商標は
   `HOP_NAME_FIXES`、本物の新品種・加工品(Cryo/Kief等)は`hops_tab.js`のチャートへ(根拠のある情報源があるものだけ。捏造しない)。
   チャートの構造確認(`hops`と`hopDesc`の整列・アルファベット順・ベクトル6要素)を忘れずに。
   スペック欄が空の商品は説明文から自動で補われる(新しい収集先の日本語表記が辞書に無ければ`hop_text.py`に足し、`test_hop_text.py`にも例を追加)
7. **初回取り込み**: 通常実行は「一覧に載っている最新分」だけ。過去分を入れるかはユーザーに確認し、入れるなら `BACKFILL_SOURCES=<source_key>`
   (公式サイトの全件取り込み時は`added`を公開日にしてNEWバッジの洪水を避ける)
8. **画面と本番の確認**: `python scripts/build_html.py` → 絞り込み・バッジ・リンク・見出し/注記・モーダルをブラウザで確認 → コミット/push →
   Actionsの`Weekly Hop Product Update (all sources)`を手動実行し、`data/last_run_summary.json`の`sources`に新しい収集先が`ok`で載ることを確認
9. **記録**: このREADMEの「巡回対象サイト」に1項目足し、運用メモリ/月次タスクの説明にも追記する

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
| source | 収集元(`update_sources.json`の`source_key`): antenna / southbound / vertere / westcoast |
| added | 追加日（YYYY-MM-DD） |

## 更新ルール（Claude引き継ぎ用）

- 既存商品（同一id）は絶対に削除しない
- 新商品は必ず image / description（日本語）/ hops / abv を揃えてから追記。ページ自体がホップ品種を開示していない商品（スタウト・サワー・ラガー・サイダー等に多い）は空配列のままでよい——推測で埋めない。**ただし構造化欄(スペックのホップ欄)が空でも、説明文に品種名が書かれていれば hops に追記する**(2026-10-28のユーザー指示。下の「説明文からのホップ抽出」)。「ホップ」とだけ書かれていて品種名が無い場合は空のまま
- 画像URLはproducts.jsonフィードの`images[0].src`から取得（?width=400を付与）
- ホップはアロマチャートに未収録のものがあれば hops_tab.js の hops配列と hopDesc オブジェクトにも追加。ただしアロマの0〜5スコアは感覚評価が必要なため自動生成せず、実在確認(BeerMaverick/Hopsteiner/Yakima Chief等の一次情報源)を取った上で追加すること。`data/audit_review.json`の`needs_review.unknown_hop_names`に溜まったものがレビュー対象
- ブルワリー名・ホップ名の表記ゆれは`update_products.py`の`BREWERY_ALIASES`/`HOP_NAME_FIXES`に追記していく方式。新しいゆれを見つけたら必ずそこに追記する(2箇所以上に同じ正規化ロジックを書き写さない)
- 週次の新商品検出は「ハンドルが既知か」ではなく「ハンドルが既知 **かつ** 同一商品か(`same_product`、ブリュワリー・商品名の一致)」で判定する。Shopifyは廃盤商品のハンドル(連番URL)を別商品へ再利用するため、ハンドルだけで判定すると再利用ハンドル上の新商品を永久に取りこぼす(2026-10-06にAmbitious AlesのPorch Rack Mexican Lagerで実害を確認)。再利用ハンドル上の新商品は `<handle>-recycledN` というidで追加され(旧レコードには触らない)、urlが本来のハンドルを保持する。idがハンドルと一致しない商品が存在するのは正常
- Antenna Americaの非ビール商品(ハードセルツァー等)は`ANTENNA_EXCLUDE_VENDORS`/`ANTENNA_EXCLUDE_TAGS`で除外する。vendor欄がスタイル名(ビール)またはカテゴリ名(それ以外)になっているため、新しい非ビールカテゴリが混入したらここに追記する(2026-10-06にHard Seltzer 4件が混入して発覚)。逆に、除外ルールがビールを落としていないかは総チェックのA2(`coverage_check.py`)で目視する(2026-11-16に`Mix`=ミックスパックの誤除外を発見)
- 出力ファイル名は `docs/index.html` 固定（GitHub Pages公開用）

## 製品別ホップ成分表の絞り込み（スタイル36分類・度数帯、2026-11-10導入）

商品が950件を超え、旧版の7分類(IPA/DIPA/Pale Ale/Sour/Stout/Lager/その他)では粗すぎたため、スタイルを細分化し、度数別の絞り込みを足した。

- **スタイルの細分類**: `scripts/style_class.py`。収集元ごとの自由記述`style`(384種類の表記ゆれ)を、7つの大分類・36の細分類に振り分ける
  (例: IPA系=ヘイジー/ウエストコースト/ダブル・トリプル/セッション/コールド・ブリュット/ブラック・レッド・ベルジャン/サワー/特殊/指定なし、
  ラガー系=ピルスナー/メキシカン/ダーク・アンバー/ホッピーラガー・IPL/スモーク・ライス・和風/ヘレス等、サワー・ワイルド系、スタウト・ポーター・ストロング系、
  小麦・ベルギー・セゾン系、サイダー・ミード・セット・その他)。1商品=1つの細分類(排他)で、`RULES`の上から最初に一致したものを採用する(順序が意味を持つ。
  例: "Sour IPA"をサワー系に取られないよう`ipa_sour`をサワー汎用より先に置く)。セット商品はstyle欄が中の1本の値になっているので商品名で見分ける。
  どれにも当てはまらないものは「その他のビール」に落ちる(2026-11-10時点で4件=0.4%)
- **度数帯**: 〜4.9% / 5.0〜5.9% / 6.0〜6.9% / 7.0〜7.9% / 8.0〜9.9% / 10%〜 / 度数不明(「-」)。`abv`欄の数値から作る
- **作り方**: `build_html.py`がビルド時に各商品へ派生値(大分類`sg`/細分類`ss`/度数`av`/度数帯`ab`)を付けて画面に埋め込む。
  `products.json`には書かない(ルールを直せば全商品に反映される。分類ルールは`style_class.py`の1か所だけ)
- **画面**(`products_tab.js`): 検索(製品名・ブリュワリー・ホップ名・スタイル)/スタイル(大分類ごとの選択肢+「〜すべて」)/度数のチップ/並び順
  (標準・新着・度数の高い順/低い順・名前順。度数不明は常に最後)/ショップ/ブルワリー(折りたたみ)/条件をクリア。
  選択肢の数字は「ほかの条件を満たす商品数」(例: ヘイジーIPAを選ぶと、度数チップの数字がヘイジーIPAの中での件数になる)。
  モーダルのホップ名をタップすると、そのホップの商品だけを表示する
- **ルールの足し方**: 新しいスタイル表記が「その他のビール」に落ちたら(ビルド時のログ`[note] ... fell back to 'その他のビール'`、
  月次監査の`needs_review.recent_products_unclassified_style`)、`style_class.py`の`RULES`に足し、`test_style_class.py`に例を追加して
  `python scripts/test_style_class.py`を通す。新しい細分類を作るときは`GROUPS`にも足す(足さないと画面に出ない)

## 説明文からのホップ抽出（scripts/hop_text.py、2026-10-28導入）

スペックのホップ欄が空でも、説明文に品種名が書かれていることがある(例: 「シトラとアマリロホップを使用した、力強いNew England IPA」)。
ユーザー指示「ホップ成分に記載がなくても、説明に記載があれば成分として追記する」に従い、これを `hops` に反映する。

- **使う場所**: 週次(`update_products.py`)は、新商品のスペック欄が空なら説明文から補う(Shopifyは`body_html`の全文、
  Vertere/WCBは説明文)。補った商品は `data/last_run_summary.json` の `hops_from_description`、
  何も無かった新商品は `new_products_without_hops` に残る。月次(`audit_catalog.py`)は既存商品のうちホップが空のものを同じ方法で補う
- **なぜ`body_html`の全文か**: 保存用の`description`は、Antennaは最初の`<ul>`(スペック欄)より前、Southboundは日本語の段落だけに絞っている。
  セット商品の個別説明や英語の説明文(例: Jester Kingの"dry hop of El Dorado, Motueka…")はそこに入らない
- **辞書ベース・誤抽出ゼロ優先**: 品種名はアロマチャートの名前と、日本語(カタカナ)表記の辞書(`JP_DISTINCT`/`JP_CONTEXT`)だけ。
  - カタカナ名は前後にカタカナが続く場合は除外(シトラス=citrus、フローラル=floral、シエラネバダ、クリスタルモルトの誤検出防止)
  - 一般名詞・地名・人名と同形の名前(Cascade/Summit/Target/Summer/クラッシュ/コロンバス等)は、「ホップ」「hops」「dry hop」等が
    同じ文にあるときだけ採用。英語表記はさらに大文字小文字の一致と「hopに隣接/確実な名前が同じ文にある/名前が2つ以上並ぶ」を要求
  - ブルワリー名(Cascade Brewing)・地名(カスケード山脈)・他銘柄との比較文(「…とは対照的に」)・「ホッピー」(風味)・
    「クライオ系のホップ」(品種名なし)は拾わない。加工品は「シトラ・クライオ」→`Citra Cryo`(チャートに在る組み合わせだけ)
  - セット商品は、含まれる銘柄の説明に出てくるホップの和集合(例: Belching Beaverの飲み比べセット)
- **検証(2026-10-28、商品896件)**: ホップ空だった323件を人手で全て読んだ正解と比べ、品種名ありの37件は全て拾え(取りこぼしは
  加工品の細かい形2語のみ)、品種名なしの286件は誤抽出ゼロ。スペック欄のある573件に対しても、抽出器が出した「欄に無い名前」25件は
  全て説明文/ライブページ側の正しい記載だった(比較文の誤抽出は比較語ルールで除外)。回帰テスト: `python scripts/test_hop_text.py`
- **カタカナ表記への対応**: 辞書(`JP_DISTINCT`/`JP_CONTEXT`/`JP_NEEDS_SUFFIX`)に載っている表記は拾える
  (例: Citra←シトラ、Mosaic←モザイク、Simcoe←シムコー、Nelson Sauvin←ネルソン/ネルソンソーヴィン、Moutere←モウテレ)。
  2026-10-28時点でチャートの基本品種162のうち142に日本語表記があり、残り20は英字の名前(HBC 630、CTZ等)やブレンド名。
  「シトラス」「フローラル」のようにカタカナが続く語は品種として拾わず、「オーロラ」「リバティ」等の日常語と同形の名前は
  「…ホップ」と直後に書かれているときだけ採用する(`JP_NEEDS_SUFFIX`。「オーロラのようにホップアロマが輝く」を品種と誤認した実例がある)
- **辞書にない新しい日本語表記は拾えない**(取りこぼし=ホップ空のまま)。月次監査が`recent_products_hop_words_without_names`に
  「ホップの語が列挙の形である最近の商品」を出すので、月次のClaudeタスクが読み、新しい表記を `hop_text.py` に足してテストを追加する
- **注意**: 「スペック欄の記載」と「説明文の記載」が食い違う商品がある(例: WCB Campfire Storiesは「w/」行がCentennial、本文はChinook)。
  欄に記載がある商品の、説明文にだけある品種は、欄を書き換えず食い違いを報告に残す。
  例外として、ページ側が**追加で**品種を挙げていて保存済みの品種と矛盾しない場合は追記する(2026-10-28に8商品。例: Deschutes Fresh Haze IPAに
  Callista/Bravoを追記)。**ページ側でホップが一新された商品**(Sierra Nevada Rad/Peachy/Cosmic Little Thing、Atomic Torpedo、Rye Torpedo IPA、
  Revision DIPA/IPA。新しいバッチ/ヴィンテージ)は、2026-11-16から週次の更新点検が自動で追従する(次章「登録済み商品の更新」)
- **セット商品のスペック**: Antennaのセット商品は「ホップ：」の行が銘柄ごとに並ぶ。`antenna_spec_fields`は以前は最後の行で上書きしていた
  (Allagash 4本セットでLagerのホップしか入らなかった)ので、全行の和集合にした(2026-10-28)
- **誤記の解消(2026-10-28)**: Southboundの日本語訳が「ブレマ」「X ７」と起こしていたため、Jester King Enigmatic Taxaのホップ欄が
  "Brema / X7" になっていたが、同商品の英語原文は"Belma / X17"。Brema→Belma(`HOP_NAME_FIXES`、チャートに在る)、X7→X17(出典が乏しくチャート化しない)に直した

## 登録漏れ・更新漏れの対策と総チェック（2026-11-16導入）

ユーザー依頼「登録漏れ、更新漏れがないか総チェック」で、4収集元の全件をライブのサイトと突き合わせた(`scripts/coverage_check.py`)。
見つかった構造的な穴を週次の本体(`update_products.py`)で塞いだ。

- **売り切れでも直近に公開された商品は登録する**(`RECENT_SOLDOUT_DAYS`、既定14日)。週次は火曜朝に在庫を1回見るだけなので、
  公開後その週のうちに売り切れた限定品・予約枠は「在庫あり」の判定だけだと永久に見えない(Topa Topa/The Bruery等の予約枠8件が公開4日で完売、
  Heavy Riffの1件は登録されないまま26日経っていた)。公開から古い売り切れ品(過去の廃盤・完売)は従来どおり登録しない。
  該当したidは `last_run_summary.json` の `new_products_sold_out`。取りこぼしを一括補充するときは `HOP_RECENT_SOLDOUT_DAYS=45` のように広げて1回だけ実行する
- **vendor="Mix"の除外を外した**。実体はビールのミックスパックで、大文字の`MIX`(14件)や`set-`のセットは元から収集対象だったのに、
  綴りが違うだけの`Mix`だけ除外されていた(49th State Brewing Mix Packが在庫ありで未登録)。Southboundの`Set`型(Eclipse瓶セット・Tシャツ付きセット)は
  中身が個別に登録済みの銘柄かグッズなので、従来どおり収集しない
- **登録済み商品の更新**(`refresh_changes`)。以前の週次は追加だけで、登録後にサイト側で変わった事実は二度と読み直されなかった。
  次の項目だけを、サイト自身の記載を根拠に自動で直す(ルールは`update_products.py`の該当コメントが正):
  - **abv**: サイトに%の数値があり保存値と違う。サイトが空なら保存値を消さない
  - **style**: サイトのスタイル欄が短い名詞句(70字未満・「。」「！」なし・英字あり)で、`style_class`の細分類が保存値と変わるとき。
    言い換えだけ(同じ細分類)・分類できない欄・販売注記が入った欄(「Southbound限定の商品！…」)は採らない
  - **hops**(`refresh_hops`): サイトの記載=スペック欄、無ければ説明文から読めた品種。保存値が空なら埋める。保存値にサイトの記載に無い品種があるときは、
    スペック欄が根拠なら「スペック欄にも説明文にも無い保存値」がある場合だけ、説明文が根拠なら保存値と完全に食い違う場合だけ置き換え、それ以外は追記のみ
    (説明文には書かれているがスペック欄から漏れている品種=ユーザー指示で補ったものは消さない)。追加する名前がアロマチャートに無ければ適用せず確認へ
  - **name**: 触らない(ブリュワリー名の有無・【再入荷】等の飾りはノイズ)。例外は再発売(細分類と度数が同時に変わる=別レシピ。Ambitious Ales Soccer Pants)
  - 説明文・画像は触らない(言い換え・写真の差し替えは事実の更新ではない。2026-11-16時点でAntennaの95件・Southboundの18件が言い換えで違う)
  - **歯止め**: 1回で更新するのは最大`MAX_REFRESH_PER_RUN`(60)件。超えるのは「サイト構造が変わって解析が全体にずれた」ときなので、超えた分は適用せず
    `last_run_summary.json`の`refresh_review`へ。**適用した変更は全て`refreshed`に旧→新で残る**
  - 収集元ごとの根拠: Shopifyは取得済みのカタログ(追加リクエストなし)、VertereはWP記事の`modified`が直近`WP_MODIFIED_DAYS`(14)日以内のものだけ個別ページを読み直す
    (`refresh_wp_brewlog`)、WCBは`/ourbeers/`の一覧(最新12銘柄、`refresh_wcb_list`。説明文が無いのでホップは追記のみ)
  - 初回(2026-11-16)の適用: 32件(スタイル24・ホップ8・度数2、Revision DIPA/IPA、Sierra Nevadaの5品、Vertere Achillea等)。
    旧→新は当日のコミットメッセージと`last_run_summary.json`にある
- **商品名の整形**: 先頭の販促タグ(`【再入荷】`等)は英字の銘柄名が続くときだけ除く(タグがあるとブリュワリー名の接頭辞除去も効かなかった)。セット名はそのまま
- **売り切れ商品も読むため**、解析できない1商品でソース全体が止まらないよう、商品ごとにtry/exceptし`parse_errors`に記録する
- **総チェック**: `python scripts/coverage_check.py [--json 出力先]`(読み取り専用)。A=登録漏れ(A1在庫あり未登録/A2除外条件で外れた在庫あり商品の目視用/A3売り切れ最近公開の未登録/A4公式サイト系の未登録)、
  B=更新漏れ(B1・B2=次回の週次が直す差、B3=ハンドル失効と別ハンドルでの再掲載、B4=チャートに無いホップ、B5=公開ページとの一致)。
  更新の判定は週次と同じ`refresh_changes`を呼ぶので食い違わない。修正後の状態では A1/A3/A4/B1/B2/B4 が全て0、B3は廃盤(再掲載の疑い0件)になる
- **HBC 522 / Alora**: B4で見つかったチャート未収録のホップ。HBC 522は米国植物特許PP29894(Hop Breeding Company、Columbus×986-2、香り「シトラス、フローラル」、α酸9.9〜11.7%)、
  AloraはHopsteiner社のデータシート(香り「ピーチ、ゆず、甘いメロン、アプリコット」、α酸7.0〜10.0%)を根拠に、`hops_tab.js`へ追加した
  (0〜5スコアは出典の香りの語からの感覚評価。Peacharine等の既存品種に合わせた)
- **West Coast Brewingの過去分を全件取り込み**(2026-11-16、ユーザー依頼「取り込んで」。540銘柄のうち未登録だった517件。商品は969→1486件):
  実行は `BACKFILL_SOURCES=westcoast python -u scripts/update_products.py`(約15分)。結果: 説明文・画像は全件あり、ABV不明3件、ホップ空136件
  (副原料だけの行・「w/」行なし。説明文から補えた10件を除く)、`added`はCMS公開日(2015-10〜2021-11)なのでNEWバッジは1件も付かない。既存レコードへの影響0。
  解析ルールは前述の`wcb_hops`。この過程で**チャートに20項目を追加**(233品種): 実在確認済みの本体=Anchovy(Segal Ranchの実験品種)・Kohia Nelson(Freestyle Hopsのブレンド)・
  Wai-iti・Ramosa(Segal Ranch、2026年に命名)・Cryo Pop(Yakima Chiefのブレンド)、加工品=El Dorado Cryo/Incognito/Quantum、Talus Cryo、Sabro Cryo、Idaho 7 Cryo、
  Comet/Nelson Sauvin/Motueka/Riwaka/Cashmere CGX、Nelson Sauvin/Waimea/Wai-iti/Rakau Kief(元品種のベクトルと共通の説明文を機械的に写した)。
  Yakima Chiefの成分パネル(`ych_map.json`)は、これらの新項目を未登録のまま(同社サイトはPythonから取れないので、必要ならアプリ内ブラウザ経由。「成分データ」の節)。
  `hop_text.py`の`EN_COMMON`にAnchovyを追加(食べ物のアンチョビと同形のため、説明文からは「hop」が近くにあるときだけ採用)。
  スタイル分類にGrodziskie(ポーランドの燻製小麦ビール)を追加。残る「その他のビール」7件はFruited Ale/Fruit/Blueberry Ale/Milkshake/Winter Ale/Low ABV Brews(0.5%)
- **画面の確認(1486件)**: 検索の再描画は約20〜40ミリ秒、DOMは約1.9万ノード、ページは1.9MB。ブラウザのコンソールエラーなし
- **手元から取れなくなったとき(2026-11-25)**: この端末のIPからAntenna/Southboundの`products.json`がCloudflareのボット確認
  (HTTP 403 `cf-mitigated: challenge`。直前に429)で取れなくなった(Vertere・WCBは取れる)。GitHub Actionsの週次実行(11/17・11/24)は成功していた。
  **突破しない**(User-Agent偽装・ブラウザ自動化・Cookie流用はしない。Anny CMSと同じ方針)。総チェックはこの2つを「点検できなかった収集元」として出し(「問題なし」にしない)、
  代わりにCIの結果(`gh run list`・`data/last_run_summary.json`・`gh workflow run weekly-update.yml`)で見る。
  見立て: 11/16に全カタログ(各約12リクエスト)を手元から何度も取った(総チェック3回・調査・試走)ことが引き金の可能性が高い。
  **全カタログを手元から短時間に繰り返し取らない**(調べ物は一度取ってキャッシュして使う)

## 月次監査（scripts/audit_catalog.py）

週次の`update_products.py`は「新商品の検出」と、登録済み商品のスタイル・ABV・ホップの更新(前章)だけを行う軽量処理であり、以下は拾えない。これを毎月1日に
`monthly-audit.yml`が自動実行して点検する(2026-10-02導入、きっかけは同日に発見した実例: Shopify側のURL変更で
5商品のIDが無効化し、次週の週次実行が「新商品」と誤認して重複追加する一歩手前だった事象):

- 商品の二重登録（ブリュワリー名+商品名の一致で検出）
- 商品ページのURL/IDがサイト側のハンドル変更で無効化していないか
- 説明文中にホップ品種名が埋もれていて構造化欄(hops)に未反映のもの(`hop_text.py`の辞書ベース抽出。ライブページの本文全体も見る)。
  拾えたものは**hopsに自動で追記**し(`auto_fixed.hops_from_description`)、拾えなかったが説明文に「ホップ」の語が
  列挙の形である最近60日の商品は `needs_review.recent_products_hop_words_without_names`(辞書に無い日本語表記の発見用)に出す
- hops[]に使われているが hops_tab.js のアロマチャートに未収録の品種名
- ブルワリー公式サイト系(Vertere / West Coast Brewing)で、週次の収集が見る範囲(Vertere=最新30件、WCB=最新12件)を外れた取りこぼし
  (`needs_review.unregistered_items`。Vertere・WCBとも、REST APIの全記事/全銘柄のID(WCBは540件=6リクエスト)と照合する。
  見つかったら `BACKFILL_SOURCES=<source_key> python scripts/update_products.py` で取り込む。WCBは
  `BACKFILL_SOURCES=westcoast BACKFILL_ONLY=<unregistered_itemsのid(slug),...>` とidまで指定する(`added`はREST公開日になる)。
  `BACKFILL_ONLY`が無いと、一覧の対象ページ内の未登録を全て取り込んでしまう)。
  **検査が未実装の収集先は `sources_without_completeness_check` に列挙される**(「問題なし」と区別して必ず報告に出す)。
  Shopify系はライブカタログと全件照合する対象を`update_sources.json`から自動で決める

このうち「表記ゆれの再正規化」「IDが今も有効なハンドルに一致する商品の欠落フィールド補完」「説明文からの
ホップ抽出(辞書ベース。検証済み)」は機械的に安全なため自動適用される(月次のClaudeタスクが`auto_fixed`の中身を確認する)。
それ以外（二重登録候補・ハンドル不整合候補・辞書で拾えなかった説明文・未知の品種名）は**自動適用せず** `data/audit_review.json` に記録するだけに留める
——いずれも「本当に同一商品か」「実在する品種名か」の判断にWeb検索や人間的判断が必要なため、
誤った自動適用はデータ破損や品種の捏造になり得る。月1回、Claudeが`data/audit_review.json`を読んで
Web検索で裏取りし、安全と確認できたものだけ反映する運用（スケジュール済みタスクとして設定済み）。

## 成分データ（Yakima Chief公開の典型値、2026-10-13導入）

アロマチャートの品種ごとに「成分」欄(α酸・β酸・コフムロン・総オイル・精油組成8成分の典型値の範囲)と、
Yakima Chief Hops社のページへのリンク(同社の官能評価=13分類のレーダーチャートがある)を表示する。

- データ: `data/ych_specs.json`(品種名 -> 値)、対応表: `data/ych_map.json`(品種名 -> 同社ページのパス)。
  同社が扱わない品種(Helios・Delta・Vic Secret・Lemondrop等)や他社製の濃縮加工品(Incognito・Lupocore・CGX・Abstrax・Kief等)は載らない(表示も非表示)
- 取り込み: `scripts/ych_collect.browser.js`(アプリ内ブラウザで実行) → `scripts/ych_merge.py`。
  同社サイトはPython等のHTTPクライアントを429で拒否する。**その制限を回避するなりすましはしないこと**。
  robots.txtは全面許可だが、収集は1ページ/1.5秒以上・1回きり(静的な典型値なので定期収集は不要)
- 権利: 同社の利用規約は「データ編集物を含むサイトの内容は同社の知的財産」としている。そのため公開サイト上では
  数値の範囲のみを出典明記で表示し、官能評価(13分類・ロット別のパネル値)は**転載せずリンクで誘導**する。
  転載の拡大(官能評価の値の掲載等)をする場合は、先に同社へ許諾を取ること
- 新品種をアロマチャートに追加したら、同社に掲載があるか(`https://www.yakimachief.com/variety/<slug>`)を確認し、
  あれば `ych_map.json` に追記して上記の手順で取り込む。掲載が無ければ何もしない

- **2026-10-02時点の状態**: GitHub Pagesで公開中、週次(`weekly-update.yml`)・月次(`monthly-audit.yml`)とも
  実運用で動作確認済み。商品492件・ホップ175品種。`ANTHROPIC_API_KEY`は登録されているが値が無効(401)の
  ままだが、収集本体には影響しない(説明文からの追加ホップ抽出機能のみ使われない)
