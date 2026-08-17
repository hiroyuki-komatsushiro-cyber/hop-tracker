// ===== RADAR / HOPS TAB =====

var pal = ["#D85A30","#378ADD","#639922","#993556","#0F6E56","#BA7517","#7F77DD","#D4537E",
           "#888780","#1D9E75","#85B7EB","#F0997B","#5DCAA5","#ED93B1","#EF9F27"];
var rlabels = ["トロピカル","シトラス","ベリー/ストーンフルーツ","フローラル","パイン/樹脂","ハーブ/スパイス・土"];

// ホップ説明文（選択時にチャート下に表示）
var hopDesc = {
  "Ahtanum":                  "グレープフルーツ・フローラルが主体。カスケードに似た柑橘感を持ちながら、より松脂のニュアンスが強い。",
  "Ales for ALS":             "ALS研究支援のためのチャリティーブレンド。トロピカル・シトラス・ベリーが複合的に香る。",
  "Amarillo":                 "オレンジ・グレープフルーツのシトラスと甘いフローラルが特徴。現代IPAの定番品種。",
  "Apollo":                   "グレープフルーツ・ライム・オレンジのシトラスに、力強いパイン・樹脂感。高α酸ホップ。",
  "Aramis":                   "フランス産のノーブルホップ。アニス・スパイス・ハーブが中心のクラシックなアロマ。",
  "Aurora":                   "スロベニア産。フローラルとスパイスが穏やかに香る繊細なノーブル系。",
  "Aurora Cryo":              "元品種の香りキャラクターを凝縮した濃縮加工品(Cryo/Incognito/DynaBoost等)。基本的なアロマ傾向は元品種(Aurora)と同じ。",
  "Azacca":                   "マンゴー・パイナップル・柑橘が爆発するジャマイカ語で「農業の神」を意味する品種。",
  "Bobek":                    "スロベニア産。フローラル・スパイス・わずかなパインが香るノーブル系の代表格。",
  "Bravo":                    "オレンジ・バニラ・フローラルの上品なアロマ。ビタリング・アロマ両用の万能品種。",
  "Brewer's Gold":            "イギリス・カナダ産の古典品種。ブラックカラントのベリー感と土っぽいアロマ。",
  "Callista":                 "パッションフルーツ・アプリコット・グレープフルーツに、ブラックベリー・ストロベリー・ブラックカラントのベリー感が重なるドイツ・Hüll研究所開発品種(2016年)。オレンジやキャラメルのニュアンスも。",
  "Calypso":                  "洋梨・リンゴ・桃などの白系フルーツ/ストーンフルーツが主体。控えめなトロピカル感とライムのシトラス感を伴い、後味に紅茶のようなアーシーな渋みが特徴。",
  "Cascade":                  "グレープフルーツ・フローラル・スパイスのバランスが絶妙。アメリカクラフトビール革命の立役者。",
  "Cashmere":                 "レモン・ライム・ピーチ・ハーブが柔らかく融合。飲みやすさと香りの両立が魅力。",
  "Celeia":                   "スロベニア産ノーブル系。ラベンダー・フローラル・スパイスが上品に広がる。",
  "Centennial":               "グレープフルーツ・フローラルにパインが加わる。「スーパーカスケード」とも呼ばれる万能品種。",
  "Challenger":               "イギリス産。シダー・グリーンティー・フルーツが穏やかに広がるバランス型。",
  "Chelan":                   "柑橘・フローラル・フルーティが穏やかに香る。マイルドで飲みやすいスタイルに最適。",
  "Chinook":                  "パイン・グレープフルーツ・スモーキーなスパイスが力強く主張する西海岸IPAの定番。",
  "Citra":                    "グレープフルーツ・ライム・パッションフルーツ・ライチが炸裂。現代ヘイジーIPAの代名詞。",
  "Citra Incognito":          "元品種の香りキャラクターを凝縮した濃縮加工品(Cryo/Incognito/DynaBoost等)。基本的なアロマ傾向は元品種(Citra)と同じ。",
  "Cluster":                  "フローラル・ベリー（ブラックカラント）・アーシーが穏やかに香るアメリカ最古の品種の一つ。",
  "Cluster Fugget":           "クラスターとフグルの特性を持つブレンド系。フローラル・アーシーが中心。",
  "Columbia":                 "パイナップル・レモン・柑橘の明るいアロマ。ノーブル系の穏やかさも兼ね備える。",
  "Columbus":                 "ブラックペッパー・カレー・リコリスのスパイシーなアロマ。ビタリングホップとしても定番。",
  "Columbus Cryo":            "元品種の香りキャラクターを凝縮した濃縮加工品(Cryo/Incognito/DynaBoost等)。基本的なアロマ傾向は元品種(Columbus)と同じ。",
  "Comet":                    "グレープフルーツ・ワイルドグラッシーなアロマ。古典品種として近年再注目されている。",
  "Contessa":                 "洋梨・緑茶・レモングラスの繊細なノーブル系アロマ。フローラルとハーブが主体で、樹脂・トロピカル感はほぼ無い上品な香り。",
  "Cryo Pop Original Blend":  "クライオホップ技術によるブレンド。トロピカル・シトラスが凝縮されたジューシーな香り。",
  "Crystal":                  "フローラル・スパイス（シナモン・ナツメグ）・フルーティが穏やかに香るドイツ系。",
  "Crystal Lupulin":          "元品種の香りキャラクターを凝縮した濃縮加工品(Cryo/Incognito/DynaBoost等)。基本的なアロマ傾向は元品種(Crystal)と同じ。",
  "CTZ":                      "ブラックペッパー・カレー・アーシーのスパイシーかつ力強いアロマ。Columbus/Tomahawk/Zeusの総称。",
  "Dolcita":                  "ピーチ・パイナップル・オレンジのスウィートなトロピカル系。甘く上品な香りが魅力。",
  "East Kent Golding":        "ラベンダー・ハチミツ・タイム・オレンジの繊細なフローラル。イギリス伝統品種の象徴。",
  "Ekuanot":                  "レモン・ライム・オレンジ・トロピカルフルーツ・ベリー・パパイヤが複合的に香る多面体品種。",
  "El Dorado":                "パイナップル・マンゴー・ウォーターメロン・キャンディのジューシーなトロピカル感。",
  "Elani":                    "パイナップル・グアバ・ホワイトピーチ・タンジェリン・ライム。南洋風のエキゾチックな香り。",
  "Ella":                     "オーストラリア産(旧名Stella)。低添加ではフローラル・スターアニスの上品な香り、高添加ではグレープフルーツ・パッションフルーツ・ライチのトロピカル/シトラス感が際立つ。",
  "Endeavour":                "ブラックカラント・ログベリーのベリー感と、グレープフルーツのシトラスが印象的。",
  "Enigma":                   "オーストラリア産。ラズベリー・レッドカラント・白ワイン様のベリー/ストーンフルーツが主体で、メロン・パッションフルーツのトロピカルとカモミールのフローラルも併せ持つ複雑な香り。",
  "Erebus":                   "Hopsteiner社の新品種(2024年)。ブルーベリー・アプリコット・レッドベリーの甘い果実味にフローラルローズが重なる。生葉では控えめだがドライホップで一気に香りが開く。",
  "Ernest":                   "アプリコット・シトラス・スパイスが中心。ストーンフルーツの甘みが特徴的。",
  "Falconer's Flight 7Cs":    "7つのC系ホップのブレンド。トロピカル・フローラル・柑橘・パインが複合的に香る。",
  "Falconer's Flight Blend":  "C系ホップのブレンド。レモン・グレープフルーツ・トロピカルのバランスが良い。",
  "First Gold":               "タンジェリン・オレンジマーマレード・アプリコット・レッドベリーのフルーティな英国品種。",
  "Fuggle":                   "ウッド・グラス・ミントの穏やかでアーシーなアロマ。英国ポーターの伝統的なホップ。",
  "Galaxy":                   "パッションフルーツ・シトラス・ピーチのトロピカル感が際立つオーストラリア産人気品種。",
  "Galena":                   "フルーティ（ペアー・パイナップル・ブラックカラント）・グレープフルーツ・ウッディな複合アロマ。",
  "Glacier":                  "プラム・ブラックベリー・ウッドのストーンフルーツ感が穏やかに広がる。",
  "Hallertau Blanc":          "パイナップル・パッションフルーツ・エルダーフラワー・グーズベリーのエレガントなドイツ品種。",
  "Hallertauer Mittelfruher": "スパイシー・フローラル・ハーブのクラシックなノーブル感。ドイツラガーの魂。",
  "Hallertauer Tradition":    "フローラル・アーシー・グラッシーのクラシックドイツ品種。ミッテルフリューの後継。",
  "HBC 1134":                 "John I. Haas / Yakima Chief Ranchesのラガー向け実験品種。ローズ・パイン・レモン・グレープフルーツにハーブが重なる、ノーブルホップにアメリカ的柑橘を加えた複合香。",
  "HBC 472":                  "トロピカル・シトラス・フローラルが複合的に香る実験的品種。",
  "HBC 630":                  "ベリー（チェリー・ラズベリー）・トロピカル・シトラスのフルーティな実験品種。",
  "HBC 638":                  "マンゴー・パイナップル・チェリー・ストロベリーのトロピカルかつベリー感が特徴の実験品種。",
  "HBC 682":                  "ハーブ・アーシー・フローラル・ミャルドシトラスを持つ実験品種。",
  "Helga":                    "フローラル・スパイス・ハーブのノーブル系。オーストラリア版ハラタウ。",
  "Herkules":                 "柑橘（メロン・レモン）・パイン・スパイシーのバランス型ドイツ品種。高α酸でもアロマが豊か。",
  "Hersbrucker Spat":         "フローラル・ハーブ・スパイス・ヘイのクラシックなバイエルン産ノーブルホップ。",
  "Horizon":                  "フローラル・スパイスのノーブル系。センテニアルの兄弟品種として安定した品質を誇る。",
  "Huell Melon":              "メロン・ストロベリーのベリー感が突出するドイツ産の異色品種。甘いフルーティさが魅力。",
  "Idaho 7":                  "アプリコット・パパイヤ・パイナップル・オレンジ・グレープフルーツ・パインの複合アロマ。",
  "Idaho Gem":                "ストーンフルーツ・トロピカル・ベリーのアロマ。アイダホ7の親戚的存在。",
  "Jarrylo":                  "スパイス・バナナ・柑橘・フローラル。サイソン・ウィートビールとの相性が抜群。",
  "Kazbek":                   "チェコ産のザーツ代替品種。柑橘・フローラル・ハーブのバランスが良い。",
  "Kohatu":                   "NZ産。トロピカル（パイン・グレープフルーツ）とパインの爽快感が特徴。",
  "Krush":                    "Hop Breeding Companyが17年の開発を経て2024年にリリースしたばかりの新品種(HBC 586)。オレンジ・マンゴー・グアバ・モモ・ミックスベリーの濃厚なトロピカル/ストーンフルーツに軽い樹脂感を伴う。",
  "Krush Cryo":               "元品種の香りキャラクターを凝縮した濃縮加工品(Cryo/Incognito/DynaBoost等)。基本的なアロマ傾向は元品種(Krush)と同じ。",
  "Lemondrop":                "CascadeとUSDA由来品種の交配種。レモンを中心としたシトラス感が際立ち、フローラル・ミント・緑茶様のハーブ感を伴う。",
  "Liberty":                  "フローラル・ハーブ・ウッディの穏やかなアロマ。ハラタウ・ミッテルフリューのアメリカ版。",
  "Loral":                    "フローラル（ローズ）・エキゾチックフルーツ・スパイスの上品なアロマ。貴族的な品種。",
  "Lorien":                   "Indie Hopsが2021年にリリースした低アルファ品種。レモン・ライムの柑橘とメロンのフルーティさに、甘い干し草・野花のフローラルさ、仕上げにシナモンのスパイス感。",
  "Magnum":                   "フローラル・スパイス・柑橘の繊細なアロマ。ビタリングホップとしても世界標準。",
  "Mandarina Bavaria":        "タンジェリン・オレンジのシトラス感が突出するドイツ品種。フルーツIPAに最適。",
  "Millennium":               "ハーブ・フローラル・ストーンフルーツ・パインの複合アロマ。マグナムの後継品種。",
  "Mosaic":                   "マンゴー・パイナップル・ブルーベリー・タンジェリン・パインの多面体アロマ。ヘイジーIPAの王者。",
  "Mosaic Cryo":              "元品種の香りキャラクターを凝縮した濃縮加工品(Cryo/Incognito/DynaBoost等)。基本的なアロマ傾向は元品種(Mosaic)と同じ。",
  "Mosaic Dynaboost":         "元品種の香りキャラクターを凝縮した濃縮加工品(Cryo/Incognito/DynaBoost等)。基本的なアロマ傾向は元品種(Mosaic)と同じ。",
  "Mosaic Incognito":         "元品種の香りキャラクターを凝縮した濃縮加工品(Cryo/Incognito/DynaBoost等)。基本的なアロマ傾向は元品種(Mosaic)と同じ。",
  "Motueka":                  "ライム・レモン・トロピカルのシャープなシトラス感が特徴のNZ品種。",
  "Motueka (MacHops)":        "ライム・レモン・トロピカルのシャープなシトラス感。マックホップス社供給のモツエカ。",
  "Motueka (NZ Hops)":        "ライム・レモン・トロピカルのシャープなシトラス感。NZホップス社供給のモツエカ。",
  "Moutere":                  "マンゴー・シトラス・ストーンフルーツのトロピカル感。Nelson Sauvinの弟分的NZ品種。",
  "Mt. Hood":                 "フローラル・ハーブ・スパイスの穏やかなアロマ。ドイツ・ハラタウ系のアメリカ版。",
  "Mt. Rainier":              "フローラル・フルーティ・スパイスのバランス型。ハラタウとイギリス系の交配種。",
  "Nectaron":                 "パッションフルーツ・グアバ・ピーチ・マンゴーのトロピカル爆弾。NZ産の最新スーパー品種。",
  "Nelson Sauvin":            "白ワイン・グーズベリー・パッションフルーツの独特なワインライクアロマ。NZを代表する品種。",
  "Nelson Sauvin (MacHops)":  "白ワイン・グーズベリー・パッションフルーツ。マックホップス社供給のネルソン・ソーヴィン。",
  "Nelson Sauvin (NZ Hops)":  "白ワイン・グーズベリー・パッションフルーツ。NZホップス社供給のネルソン・ソーヴィン。",
  "Newport":                  "ハーブ・パイン・樹脂のアロマ。高α酸ビタリングホップとして安定した品質。",
  "Northdown":                "パイン・ウッド・フルーティのバランス型イギリス品種。チャレンジャーの後継。",
  "Northern Brewer":          "パイン・ハーブ・ミントのクリーンなアロマ。ラガーからエールまで幅広く使用。",
  "Nugget":                   "ハーブ・フローラル・パイン・スパイスのクラシックなアメリカホップ。ビタリング中心だが香りも良好。",
  "Olympic":                  "ハーブ・パイン・柑橘の穏やかなアロマ。北西部産の安定したビタリング品種。",
  "Opal":                     "フローラル・スパイス・ストーンフルーツ・パインのバランス型ドイツ品種。",
  "Pacific Crest Blend":      "ハーブ・アーシー・パイン・柑橘のブレンド。太平洋岸トレイルをイメージした複合アロマ。",
  "Pacific Gem":              "ブラックカラント・ウッド・パインのNZ産品種。ビタリング向けだが独特なアロマも持つ。",
  "Pacific Jade":             "柑橘・スパイス・パインのクリーンなNZ品種。ビタリングとアロマの両用で活躍。",
  "Pacifica (MacHops)":       "柑橘（オレンジ・タンジェリン）・フローラルのNZ品種。マックホップス社供給。",
  "Pacifica (NZ Hops)":       "柑橘（オレンジ・タンジェリン）・フローラルのNZ品種。NZホップス社供給。",
  "Palisade":                 "パイナップル・アプリコット・ハーブのアロマ。まろやかで親しみやすい香り。",
  "Peacharine":               "ニュージーランドFreestyle Hops社の新品種。完熟ピーチ・ネクタリンが主体のストーンフルーツ香が突出し、ライム様の柑橘の芯とほのかなフローラルを伴う。",
  "Pekko":                    "ミント・フローラル・シトラスの清涼感あふれる品種。軽快なスタイルに最適。",
  "Perle":                    "フローラル・ミント・スパイスのクリーンなドイツ品種。ピルスナーに伝統的に使用。",
  "Phoenix":                  "フローラル・スパイス・パインのバランス型イギリス品種。チャレンジャーに近い性質。",
  "Pilgrim":                  "スパイシー・フルーティ・フローラルの多面体イギリス品種。モダンな英国IPAに活用。",
  "Pilot":                    "スパイス・ハーブ・パインのアーシーなアロマ。イギリス産ビタリング向け品種。",
  "Pink Boots Blend":         "女性醸造家支援のチャリティーブレンド。トロピカル・シトラス・ベリーの明るいアロマ。",
  "Polaris":                  "ミント・パイン・柑橘の爽快なアロマ。超高α酸（約20%）のドイツ産品種。",
  "Premiant":                 "フローラル・スパイス・ハーブのチェコ産ノーブル系。ピルスナーに最適。",
  "Pride of Ringwood":        "アーシー・パイン・樹脂のオーストラリア伝統品種。フォスターズ等の定番ビールに使用。",
  "Progress":                 "ハーブ・フルーティ・フローラルの穏やかなイギリス品種。フグルの後継として開発。",
  "Rakau":                    "アプリコット・マンゴー・プラム・シトラスのストーンフルーツ感が豊かなNZ品種。",
  "Rakau (MacHops)":          "アプリコット・マンゴー・プラムのストーンフルーツ感。マックホップス社供給のラカウ。",
  "Rakau (NZ Hops)":          "アプリコット・マンゴー・プラムのストーンフルーツ感。NZホップス社供給のラカウ。",
  "Riwaka":                   "シトラス（ライム・レモン）が突出するNZ品種。鮮烈な柑橘感がヘイジーIPAを彩る。",
  "Saaz":                     "スパイシー・フローラル・アーシーのクラシックノーブル感。チェコピルスナーの象徴。",
  "Sabro":                    "タンジェリン・ライム・トロピカル・ミント・クリームシクル。多面体の個性的なアロマ。",
  "Santiam":                  "フローラル・ハーブ・スパイスのノーブル感。ドイツ品種のアメリカ版的存在。",
  "Saphir":                   "タンジェリン・フローラル・スパイスの繊細なドイツ品種。ハラタウ系の上品さ。",
  "Savinjski Golding":        "スロベニア産ゴールディング。柑橘・フローラル・スパイスの上品なアロマ。",
  "Simcoe":                   "パッションフルーツ・柑橘・パイン・アーシーの力強いアロマ。WCIPAのマストホップ。",
  "Simcoe Cryo":              "元品種の香りキャラクターを凝縮した濃縮加工品(Cryo/Incognito/DynaBoost等)。基本的なアロマ傾向は元品種(Simcoe)と同じ。",
  "Sladek":                   "ハーブ・スパイス・フローラルのチェコ産ノーブル系。ザーツの現代版。",
  "Sorachi Ace":              "レモン・ディル・コリアンダーのユニークな日本産品種。個性的な柑橘×ハーブ感。",
  "Southern Cross (NZ Hops)": "柑橘（ライム・レモン）・スパイス・パインのNZ品種。南十字星の名が示す南半球産。",
  "Sovereign":                "フローラル・ストーンフルーツ・ハーブのイギリス品種。ファーストゴールドに近い性質。",
  "Spalter":                  "フローラル・スパイス・ハーブのクラシックドイツ・ノーブル品種。バイエルン伝統の味。",
  "Spalter Select":           "フローラル・スパイスのノーブル感。シュパルターの改良品種で香りがより明確。",
  "Sterling":                 "フローラル・スパイス・柑橘のノーブル系アメリカ品種。ザーツとアメリカ品種の交配。",
  "Strata":                   "パッションフルーツ・ストロベリー・グレープフルーツのトロピカル×ベリー感が特徴。",
  "Strisselspalter":          "スパイス・フローラル・アーシーのフランス・アルザス産伝統品種。",
  "Summer":                   "トロピカル・ストーンフルーツ・柑橘のオーストラリア産品種。夏向けのフルーティさ。",
  "Summit":                   "オニオン・柑橘・スパイスの個性的なアロマ。愛好家を選ぶ超高α酸品種。",
  "Super Pride":              "アーシー・パイン・樹脂の高α酸オーストラリア品種。Pride of Ringwoodの後継。",
  "Superdelic (NZ Hops)":     "トロピカル・シトラス・ベリーのエレクトリックなNZ品種。",
  "Sussex Hop":               "フローラル・スパイス・柑橘のイングランド・サセックス産品種。",
  "Sylva":                    "フローラル・スパイス・ハーブのドイツ品種。繊細で上品なアロマ。",
  "Tahoma":                   "シトラス・スパイス・フルーティのバランス型。シムコー・シェランの交配から生まれた品種。",
  "Talus":                    "グレープフルーツ・フローラル・ストーンフルーツ・パインの多面体品種。次世代スター候補。",
  "Tangier":                  "タンジェリン・ネーブルオレンジ・オレンジクリームシクルのシトラス爆弾。2021年発見の新鋭。",
  "Target":                   "スパイシー・ハーブ・パインの力強いイギリス品種。ビタリング中心だが複雑なアロマも持つ。",
  "Tettnanger":               "フローラル・スパイス・ハーブの繊細なドイツ産ノーブルホップ。テットナングの宝。",
  "Topaz":                    "トロピカル（ライチ）・柑橘・パインのオーストラリア産高α酸品種。",
  "Triskel":                  "フローラル・シトラス・スパイスのフランス・アルザス産品種。ストリッセルシュパルターの後継。",
  "Triumph":                  "柑橘・フルーティ・フローラルのバランス型。センテニアルの兄弟品種として開発。",
  "Vanguard":                 "フローラル・ハーブ・スパイスのノーブル系。ハラタウの北アメリカ版的存在。",
  "Veterans' Blend":          "退役軍人支援のチャリティーブレンド。トロピカル・シトラス・ベリーの明るいアロマ。",
  "Vic Secret":               "オーストラリア産。パイナップル・パッションフルーツの明るいトロピカルとパイン(松)の樹脂感が主体。Galaxyに似るがより控えめで、ハーブ・アーシーなニュアンスも。",
  "Vista":                    "トロピカル・シトラス・フローラルのバランス型。比較的新しいアメリカ品種。",
  "Wai Iti (NZ Hops)":        "レモン・ライム・ピーチのシトラス×ストーンフルーツ感。ニュージーランドの小さな宝。",
  "Waimea":                   "ライム・レモン・タンジェリンのシャープなシトラス感とパインが共存するNZ品種。",
  "Wakatu (MacHops)":         "柑橘・フローラル・スパイスのNZ品種。マックホップス社供給のワカトゥ。",
  "Wakatu (NZ Hops)":         "柑橘・フローラル・スパイスのNZ品種。NZホップス社供給のワカトゥ。",
  "Warrior":                  "ハーブ・パイン・柑橘の穏やかなアロマ。高α酸ビタリング品種として安定した人気。",
  "Willamette":               "フローラル・ハーブ・スパイスの穏やかなアロマ。フグルのアメリカ版として長く愛用。",
  "Yakima Gold":              "柑橘・スパイス・ハーブの穏やかなアロマ。ヤキマバレー産のクラシック品種。",
  "Zamba":                    "BSG Hop Solutionsの独自ブレンド品種(単一の在来種ではなく複数品種を組み合わせた製品)。パイナップル・マンゴーの濃厚なトロピカルに、ストーンフルーツ、オレンジ・タンジェリンのシトラス感。",
  "Zappa":                    "マンゴー・パッションフルーツ・スパイシーなトロピカル感。ロックの帝王の名を冠した個性派。",
  "Zythos Blend":             "タンジェリン・柑橘・フローラルのブレンド。複数品種の良いとこ取りのブレンドホップ。"
};

var hops = [
{name:"Ahtanum",v:[1,5,0,3,4,3]},{name:"Ales for ALS",v:[3,3,3,1,2,2]},
{name:"Amarillo",v:[4,5,1,3,1,2]},{name:"Apollo",v:[0,4,0,0,3,4]},
{name:"Aramis",v:[0,2,0,2,0,5]},{name:"Aurora",v:[1,3,0,3,1,3]},
{name:"Aurora Cryo",v:[1,3,0,3,1,3]},{name:"Azacca",v:[5,4,0,1,2,2]},
{name:"Bobek",v:[0,3,0,4,3,3]},{name:"Bravo",v:[2,4,2,4,1,2]},
{name:"Brewer's Gold",v:[0,0,4,0,0,2]},{name:"Callista",v:[4,3,5,0,0,2]},
{name:"Calypso",v:[2,2,4,0,0,2]},{name:"Cascade",v:[1,4,2,3,2,3]},
{name:"Cashmere",v:[3,4,2,1,0,2]},{name:"Celeia",v:[0,2,0,4,1,4]},
{name:"Centennial",v:[1,4,2,3,2,1]},{name:"Challenger",v:[1,1,1,2,1,4]},
{name:"Chelan",v:[1,2,1,2,1,1]},{name:"Chinook",v:[1,3,1,1,4,3]},
{name:"Citra",v:[4,5,3,1,1,1]},{name:"Citra Incognito",v:[4,5,3,1,1,1]},
{name:"Cluster",v:[0,1,3,3,0,3]},{name:"Cluster Fugget",v:[1,2,1,1,1,3]},
{name:"Columbia",v:[3,4,0,1,0,1]},{name:"Columbus",v:[0,2,0,1,1,5]},
{name:"Columbus Cryo",v:[0,2,0,1,1,5]},{name:"Comet",v:[1,3,1,1,1,2]},
{name:"Contessa",v:[0,2,1,3,0,3]},{name:"Cryo Pop Original Blend",v:[4,4,3,1,1,0]},
{name:"Crystal",v:[1,2,1,3,1,3]},{name:"Crystal Lupulin",v:[1,2,1,3,1,3]},
{name:"CTZ",v:[0,2,0,1,1,4]},{name:"Dolcita",v:[4,3,3,1,0,1]},
{name:"East Kent Golding",v:[0,3,0,4,0,3]},{name:"Ekuanot",v:[4,4,2,1,0,2]},
{name:"El Dorado",v:[5,2,3,1,1,1]},{name:"Elani",v:[4,4,1,1,1,1]},
{name:"Ella",v:[3,3,2,4,0,3]},{name:"Endeavour",v:[0,4,4,1,0,3]},
{name:"Enigma",v:[3,2,4,2,1,2]},{name:"Erebus",v:[2,2,5,3,0,1]},
{name:"Ernest",v:[1,3,4,1,0,2]},{name:"Falconer's Flight 7Cs",v:[3,4,2,2,2,2]},
{name:"Falconer's Flight Blend",v:[4,4,1,3,2,1]},{name:"First Gold",v:[1,4,2,3,0,3]},
{name:"Fuggle",v:[0,1,1,1,0,4]},{name:"Galaxy",v:[4,4,2,0,1,1]},
{name:"Galena",v:[2,4,3,0,1,3]},{name:"Glacier",v:[1,2,3,1,0,3]},
{name:"Hallertau Blanc",v:[4,4,2,3,0,1]},{name:"Hallertauer Mittelfruher",v:[0,2,0,3,0,4]},
{name:"Hallertauer Tradition",v:[0,2,1,3,0,4]},{name:"HBC 1134",v:[0,3,2,3,3,4]},
{name:"HBC 472",v:[3,3,2,3,1,3]},{name:"HBC 630",v:[3,3,4,2,0,1]},
{name:"HBC 638",v:[4,4,3,2,0,1]},{name:"HBC 682",v:[0,2,1,2,0,3]},
{name:"Helga",v:[0,1,0,3,0,4]},{name:"Herkules",v:[1,3,1,1,3,3]},
{name:"Hersbrucker Spat",v:[0,2,1,3,0,4]},{name:"Horizon",v:[0,2,0,3,1,3]},
{name:"Huell Melon",v:[3,1,4,1,0,1]},{name:"Idaho 7",v:[4,4,2,1,3,2]},
{name:"Idaho Gem",v:[3,3,4,2,0,2]},{name:"Jarrylo",v:[2,4,2,1,0,2]},
{name:"Kazbek",v:[1,4,2,2,0,3]},{name:"Kohatu",v:[4,2,2,1,2,1]},
{name:"Krush",v:[5,2,4,0,2,2]},{name:"Krush Cryo",v:[5,2,4,0,2,2]},
{name:"Lemondrop",v:[1,4,1,3,0,3]},{name:"Liberty",v:[0,2,0,3,0,3]},
{name:"Loral",v:[1,3,2,4,0,2]},{name:"Lorien",v:[2,3,0,3,0,3]},
{name:"Magnum",v:[0,2,0,2,1,3]},{name:"Mandarina Bavaria",v:[2,5,1,2,0,1]},
{name:"Millennium",v:[0,1,2,2,3,2]},{name:"Mosaic",v:[4,3,4,2,2,2]},
{name:"Mosaic Cryo",v:[4,3,4,2,2,2]},{name:"Mosaic Dynaboost",v:[4,3,4,2,2,2]},
{name:"Mosaic Incognito",v:[4,3,4,2,2,2]},{name:"Motueka",v:[2,5,1,2,0,2]},
{name:"Motueka (MacHops)",v:[2,5,1,2,0,2]},{name:"Motueka (NZ Hops)",v:[2,5,1,2,0,2]},
{name:"Moutere",v:[4,3,2,1,1,1]},{name:"Mt. Hood",v:[0,1,0,3,1,3]},
{name:"Mt. Rainier",v:[1,2,1,2,2,2]},{name:"Nectaron",v:[5,4,3,0,0,0]},
{name:"Nelson Sauvin",v:[3,2,4,2,0,1]},{name:"Nelson Sauvin (MacHops)",v:[3,2,4,2,0,1]},
{name:"Nelson Sauvin (NZ Hops)",v:[3,2,4,2,0,1]},{name:"Newport",v:[0,2,0,0,2,3]},
{name:"Northdown",v:[0,1,2,2,2,3]},{name:"Northern Brewer",v:[0,1,0,1,2,4]},
{name:"Nugget",v:[1,2,1,1,2,4]},{name:"Olympic",v:[0,2,0,0,2,3]},
{name:"Opal",v:[1,2,2,3,2,3]},{name:"Pacific Crest Blend",v:[0,1,0,2,2,4]},
{name:"Pacific Gem",v:[0,2,3,0,2,3]},{name:"Pacific Jade",v:[0,3,0,0,2,4]},
{name:"Pacifica (MacHops)",v:[1,4,0,3,0,2]},{name:"Pacifica (NZ Hops)",v:[1,4,0,3,0,2]},
{name:"Palisade",v:[1,2,3,2,0,2]},{name:"Peacharine",v:[2,3,5,2,0,1]},
{name:"Pekko",v:[1,3,0,3,0,3]},{name:"Perle",v:[0,1,0,2,1,3]},
{name:"Phoenix",v:[1,1,0,2,2,3]},{name:"Pilgrim",v:[0,1,2,2,2,3]},
{name:"Pilot",v:[0,1,1,1,2,3]},{name:"Pink Boots Blend",v:[3,4,3,2,1,1]},
{name:"Polaris",v:[2,2,0,1,3,4]},{name:"Premiant",v:[0,1,0,2,0,3]},
{name:"Pride of Ringwood",v:[0,0,0,0,2,4]},{name:"Progress",v:[0,1,2,2,0,3]},
{name:"Rakau",v:[2,2,3,1,2,1]},{name:"Rakau (MacHops)",v:[2,2,3,1,2,1]},
{name:"Rakau (NZ Hops)",v:[2,2,3,1,2,1]},{name:"Riwaka",v:[3,5,1,1,0,1]},
{name:"Saaz",v:[0,1,0,3,0,4]},{name:"Sabro",v:[4,4,3,1,2,2]},
{name:"Santiam",v:[0,2,0,3,0,3]},{name:"Saphir",v:[1,3,1,3,0,2]},
{name:"Savinjski Golding",v:[0,2,0,3,1,3]},{name:"Simcoe",v:[3,3,2,1,4,2]},
{name:"Simcoe Cryo",v:[3,3,2,1,4,2]},{name:"Sladek",v:[0,1,0,2,0,3]},
{name:"Sorachi Ace",v:[0,4,0,0,0,4]},{name:"Southern Cross (NZ Hops)",v:[2,4,1,1,2,2]},
{name:"Sovereign",v:[0,1,2,3,0,3]},{name:"Spalter",v:[0,1,0,3,0,3]},
{name:"Spalter Select",v:[0,1,0,3,0,3]},{name:"Sterling",v:[0,2,0,3,0,3]},
{name:"Strata",v:[4,3,3,0,1,3]},{name:"Strisselspalter",v:[0,1,0,3,0,4]},
{name:"Summer",v:[2,3,3,1,0,2]},{name:"Summit",v:[0,3,0,0,1,4]},
{name:"Super Pride",v:[0,1,1,0,2,3]},{name:"Superdelic (NZ Hops)",v:[3,3,4,1,0,2]},
{name:"Sussex Hop",v:[0,2,0,2,0,3]},{name:"Sylva",v:[0,1,0,3,1,3]},
{name:"Tahoma",v:[0,3,0,1,2,2]},{name:"Talus",v:[2,4,3,3,3,2]},
{name:"Tangier",v:[0,5,0,2,0,1]},{name:"Target",v:[0,1,1,1,2,4]},
{name:"Tettnanger",v:[0,1,0,3,0,3]},{name:"Topaz",v:[2,3,1,0,2,2]},
{name:"Triskel",v:[1,3,1,3,0,2]},{name:"Triumph",v:[1,3,2,2,2,1]},
{name:"Vanguard",v:[0,1,0,2,1,4]},{name:"Veterans' Blend",v:[4,3,3,1,1,1]},
{name:"Vic Secret",v:[4,1,0,0,4,2]},{name:"Vista",v:[2,3,2,2,2,2]},
{name:"Wai Iti (NZ Hops)",v:[2,3,3,2,0,1]},{name:"Waimea",v:[2,4,1,1,3,2]},
{name:"Wakatu (MacHops)",v:[1,3,0,3,0,2]},{name:"Wakatu (NZ Hops)",v:[1,3,0,3,0,2]},
{name:"Warrior",v:[0,2,0,1,3,2]},{name:"Willamette",v:[0,1,0,3,1,3]},
{name:"Yakima Gold",v:[0,2,0,1,0,2]},{name:"Zamba",v:[5,3,2,0,0,0]},
{name:"Zappa",v:[5,4,1,0,2,2]},{name:"Zythos Blend",v:[2,4,1,2,2,1]}
];
hops.forEach(function(h,i){ h.color = pal[i % pal.length]; });

var currentLetter = 'C'; // Citraがデフォルト選択されているためCから開始
var sel = ['Citra'];

function getLetters(){
  var set = {};
  hops.forEach(function(h){ set[h.name[0].toUpperCase()] = true; });
  return Object.keys(set).sort();
}

function renderAlphaTabs(){
  var letters = getLetters();
  var nav = document.getElementById('alpha-tabs');
  nav.innerHTML = '';
  var all = document.createElement('button');
  all.textContent = '\u2605';
  all.className = 'alpha-tab' + (currentLetter === '\u2605' ? ' active' : '');
  all.title = '選択中の品種';
  all.addEventListener('click', function(){ currentLetter='\u2605'; renderAlphaTabs(); renderBtns(''); });
  nav.appendChild(all);
  letters.forEach(function(l){
    var b = document.createElement('button');
    b.textContent = l;
    b.className = 'alpha-tab' + (currentLetter === l ? ' active' : '');
    b.addEventListener('click', function(){ currentLetter=l; renderAlphaTabs(); renderBtns(''); });
    nav.appendChild(b);
  });
}

function renderBtns(filter){
  var btnCont = document.getElementById('hop-buttons');
  btnCont.innerHTML = '';
  var visible = hops.filter(function(h){
    if(filter) return h.name.toLowerCase().indexOf(filter.toLowerCase()) >= 0;
    if(currentLetter === '\u2605') return sel.indexOf(h.name) >= 0;
    return h.name[0].toUpperCase() === currentLetter;
  });
  visible.forEach(function(h){
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = h.name;
    b.dataset.name = h.name;
    b.addEventListener('click', function(){
      if(sel.indexOf(h.name) >= 0){
        sel = sel.filter(function(n){ return n !== h.name; });
      } else {
        sel.push(h.name);
      }
      refreshBtns();
      updateChart();
      showHopDesc();
    });
    btnCont.appendChild(b);
  });
  refreshBtns();
}

function showHopDesc(){
  var box = document.getElementById('hop-desc-box');
  if(!box) return;
  if(sel.length === 0){
    box.innerHTML = '';
    box.style.display = 'none';
    return;
  }
  // 選択中の全ホップの説明を表示
  var html = '';
  sel.forEach(function(name){
    var h = hops.find(function(x){ return x.name === name; });
    var desc = hopDesc[name] || '';
    if(!desc) return;
    html += '<div class="hop-desc-item" style="border-left:3px solid '+h.color+'">'
          + '<div class="hop-desc-name">'+name+'</div>'
          + '<div class="hop-desc-text">'+desc+'</div>'
          + '</div>';
  });
  if(html){
    box.innerHTML = html;
    box.style.display = 'block';
  } else {
    box.style.display = 'none';
  }
}

function refreshBtns(){
  document.querySelectorAll('#hop-buttons button').forEach(function(b){
    var on = sel.indexOf(b.dataset.name) >= 0;
    var h = hops.find(function(x){ return x.name === b.dataset.name; });
    b.classList.toggle('active', on);
    b.style.background = on ? h.color+'22' : '#fff';
    b.style.borderColor = on ? h.color : '#ccc';
  });
}

function buildDS(){
  return sel.map(function(name){
    var h = hops.find(function(x){ return x.name === name; });
    return{
      label: h.name,
      data: h.v.map(function(x){ return x/5*100; }),
      rawData: h.v,
      borderColor: h.color,
      backgroundColor: h.color+'33',
      borderWidth: 2,
      pointBackgroundColor: h.color,
      pointRadius: 3
    };
  });
}

var ctx = document.getElementById('hopChart');
var chart = new Chart(ctx, {
  type: 'radar',
  data: { labels: rlabels, datasets: buildDS() },
  options: {
    responsive: true, maintainAspectRatio: false,
    scales: { r: { min:0, max:100, ticks:{display:false}, pointLabels:{font:{size:11}} } },
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: function(c){ return c.dataset.label+': '+c.dataset.rawData[c.dataIndex]+'/5'; } } }
    }
  }
});

function updateChart(){
  chart.data.datasets = buildDS();
  chart.update();
  document.getElementById('legend').innerHTML = sel.map(function(name){
    var h = hops.find(function(x){ return x.name === name; });
    return '<span><span class="sw" style="background:'+h.color+'"></span>'+h.name+'</span>';
  }).join('');
}

document.getElementById('srch').addEventListener('input', function(e){
  renderBtns(e.target.value);
});
document.getElementById('clrBtn').addEventListener('click', function(){
  sel = [];
  updateChart();
  refreshBtns();
  var box = document.getElementById('hop-desc-box');
  if(box) box.style.display = 'none';
});

renderAlphaTabs();
renderBtns('');
updateChart();
showHopDesc();
