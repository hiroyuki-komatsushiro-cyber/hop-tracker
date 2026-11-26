"""
京都醸造(Kyoto Brewing Co.)の収集(scope / parse_kyoto_product / parse_kyoto_page / enrich_kyoto_record / kyoto_style_en)の回帰テスト。
scripts/fixtures/ の実物の抜粋(products.jsonの代表7商品と、商品ページ2枚)を使う。ルールを変えたら必ず実行すること:
    python scripts/test_kyoto.py
(失敗があれば終了コード1。週次/月次のワークフローには組み込んでいない)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import update_products as up  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


feed = {p["handle"]: p for p in json.loads((FIX / "kyoto_feed_sample.json").read_text(encoding="utf-8"))}
src = next(s for s in up.load_sources() if s["source_key"] == "kyoto")
known = up.known_hop_names()

# ---- 設定: 売り切れも対象、公開日でadded、商品ページを読む ----
check("include_sold_out kyoto", up.include_sold_out("kyoto"), True)
check("include_sold_out antenna", up.include_sold_out("antenna"), False)
check("added_from", src.get("added_from"), "published_at")
check("page_parser", src.get("page_parser"), "kyoto")

# ---- 収集対象: Beerの単品だけ(セット・グッズ・定期便・ギフトは対象外) ----
for handle, want in (("denko-sekka", True), ("comet-wcipa", True), ("hyotto-four", True), ("kbc-holiday-set", False),
                     ("kbc-socks", False), ("fukuwauchi-set", False), ("summer-gift-set-2026", False)):
    check(f"scope {handle}", up.shopify_scope(feed[handle], "kyoto")[0], want)

# ---- feedの解析: 古い商品は本文のスペック(スタイル/ABV)と味わいの特徴、新しい商品は紹介文だけ ----
old = up.parse_shopify_product(feed["denko-sekka"], src)
check("old id", old["id"], "kyoto-denko-sekka")
check("old name", old["name"], "電光石火 (Lightning Fast)")
check("old brewery", old["brewery"], "Kyoto Brewing")
check("old style (JP spec -> EN)", old["style"], "West Coast IPA")
check("old abv", old["abv"], "7%")
check("old description starts with the blurb", old["description"].startswith("往年のスター級ホップをふんだんに使用した、クラシックなウェストコーストIPA"), True)
check("old description includes the taste notes", "キャラメルモルト" in old["description"], True)
check("old url", old["url"], "https://kyotobrewing.com/products/denko-sekka")
check("old image has a width", old["image"].endswith("?width=400"), True)
check("old hops come from the full text (feed has no hop row)", up.hops_from_description(up.body_full_text(feed["denko-sekka"]["body_html"]), known)[:3],
      ["Centennial", "Cascade", "Chinook"])

new = up.parse_shopify_product(feed["comet-wcipa"], src)
check("new style empty before the page", new["style"], "")
check("new abv unknown before the page", new["abv"], "-")
check("new description = the blurb", new["description"], "コメットホップの柑橘香にライ麦のスパイシーなニュアンスをまとったドライでスパイシーな西海岸IPA")

# ---- 商品ページの解析と補完 ----
page = (FIX / "kyoto_page_comet.html").read_text(encoding="utf-8")
info = up.parse_kyoto_page(page)
check("page style", info["style"], "West Coast IPA")
check("page abv", info["abv"], "6.5%")
check("page hops row", info["hops_raw"], "Comet, Simcoe, Dynaboost simcoe, Citra T-45")
check("page feel", info["feel"].startswith("ライ麦由来のスパイシーなニュアンス"), True)
check("page notes mention Comet", "Comet" in info["notes"], True)
up.enrich_kyoto_record(new, info, known)
check("enriched hops (Dynaboost reordered, T-45 dropped)", new["hops"], ["Comet", "Simcoe", "Simcoe Dynaboost", "Citra"])
check("enriched style", new["style"], "West Coast IPA")
check("enriched abv", new["abv"], "6.5%")
check("enriched description keeps the blurb and adds the taste notes", new["description"].count("コメットホップの柑橘香"), 1)

hz = up.parse_shopify_product(feed["hyotto-four"], src)
up.enrich_kyoto_record(hz, up.parse_kyoto_page((FIX / "kyoto_page_hyotto4.html").read_text(encoding="utf-8")), known)
check("hyotto style (JP page value -> EN)", hz["style"], "Hazy IPA")
check("hyotto hops (Nelson Sauv T-45 -> Nelson Sauvin, Prysma Galaxy -> Galaxy Prysma, trailing period)",
      hz["hops"], ["Chinook", "Cashmere", "Kohia Nelson", "Krush", "Nelson Sauvin", "Galaxy Prysma"])
check("hyotto hops are all in the aroma chart", [h for h in hz["hops"] if h not in known], [])

# ---- ページが読めない/形式が違うとき(古い商品のページ等)は空で返し、例外を出さない ----
check("empty page", up.parse_kyoto_page(""), {"style": "", "abv": "", "hops_raw": "", "feel": "", "notes": ""})
check("old-layout page", up.parse_kyoto_page("<html><body><h1>x</h1></body></html>")["hops_raw"], "")
rec = up.parse_shopify_product(feed["denko-sekka"], src)
up.enrich_kyoto_record(rec, up.parse_kyoto_page("<html></html>"), known)
check("enrich with an empty page keeps the feed's style/abv", (rec["style"], rec["abv"]), ("West Coast IPA", "7%"))

# ---- 日本語スタイル → 英語(style_classが分類できる表記) ----
for jp, en in (("ヘイジーIPA", "Hazy IPA"), ("ウェストコーストIPA", "West Coast IPA"), ("ウエストコーストIPA", "West Coast IPA"), ("西海岸IPA", "West Coast IPA"),
               ("サワーIPA", "Sour IPA"), ("ベルジャンIPA", "Belgian IPA"), ("ホワイトIPA", "White IPA"), ("ダブルIPA", "Double IPA"),
               ("セッションIPA", "Session IPA"), ("コールドIPA", "Cold IPA"), ("IPA", "IPA"), ("ペールエール", "Pale Ale"),
               ("アメリカンペールエール", "American Pale Ale"), ("ジャーマンピルスナー", "Pilsner"), ("ホッピーラガー", "Hoppy Lager"),
               ("メキシカンラガー", "Mexican Lager"), ("ラガー", "Lager"), ("セゾン", "Saison"), ("フラワーセゾン", "Saison"),
               ("サワーエール", "Sour Ale"), ("ベルジャンウィット", "Witbier"), ("ヴァイツェン", "Hefeweizen"), ("ケルシュ", "Kolsch"),
               ("インペリアルスタウト", "Imperial Stout"), ("スタウト", "Stout"), ("スモークバニラポーター", "Porter"),
               ("West Coast IPA", "West Coast IPA"), ("", ""), ("ミステリー酵母ビール", "ミステリー酵母ビール")):  # 当てはまらない日本語は原文のまま
    check(f"style {jp!r}", up.kyoto_style_en(jp), en)

for jp, en in (("レッドIPA", "Red IPA"), ("ボック", "Bock"), ("クリスマスエール", "Christmas Ale"), ("ヘーフェヴァイツェン", "Hefeweizen"),
               ("フェストビア", "Festbier"), ("セレブレーションエール", "Celebration Ale"), ("アニバーサリーエール", "Anniversary Ale")):
    check(f"style {jp!r}", up.kyoto_style_en(jp), en)

# ---- 度数: 「6.5%」「6.5％」(全角)「9.0」(記号なし)のどれも読む(全角と記号なしを読めずに34件が空になった実例) ----
for text, want in (("6.5%", "6.5%"), ("6.5％", "6.5%"), ("9.0", "9%"), ("７．５％", "7.5%"), (" 5.5% ", "5.5%"), ("", ""), ("なし", ""), ("0", ""), ("120", "")):
    check(f"kyoto_abv {text!r}", up.kyoto_abv(text), want)

# ---- ホップ欄の綴りゆれ(京都醸造の過去分) ----
for raw, want in (("Hallertau mittfruh", ["Hallertauer Mittelfruher"]), ("Hallertau Mittlefruh, Audacia", ["Hallertauer Mittelfruher", "Audacia"]),
                  ("Styrian Goldings, Aurum, McKenzie", ["Savinjski Golding", "Aurum", "McKenzie"]), ("Mckenzie", ["McKenzie"]),
                  ("Nelson Sauvin Hop Keif", ["Nelson Sauvin Kief"]), ("Madarina Bravaria", ["Mandarina Bavaria"]),
                  ("Krush HyperBoost, Strata HyperBoost", ["Krush HyperBoost", "Strata HyperBoost"]), ("Willamette", ["Willamette"])):
    check(f"hops {raw!r}", up.wcb_hops(raw), want)

# ---- 追加後の分類(画面の絞り込み)まで通ること ----
import style_class as sc  # noqa: E402
for en, sub in (("Hazy IPA", "ipa_hazy"), ("West Coast IPA", "ipa_wc"), ("Hoppy Lager", "lager_hoppy"), ("Sour Ale", "sour_fruit"),
                ("Hefeweizen", "wheat"), ("Witbier", "bel_wit"), ("Festbier", "lager_dark_amber"), ("Belgian Strong Ale", "bel_strong")):
    check(f"classify {en}", sc.classify_style(en, "")[1], sub)

if failures:
    print(f"FAILED {len(failures)}")
    for f in failures:
        print("  " + f)
    sys.exit(1)
print("OK: all Kyoto Brewing cases passed")
