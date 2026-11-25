"""
登録済み商品の更新(update_products.refresh_changes / refresh_hops)と、売り切れ新商品の登録判定の回帰テスト。
実際に起きた/起きかけた例を使っている。ルールを変えたら必ず実行すること:
    python scripts/test_refresh.py
(失敗があれば終了コード1。週次/月次のワークフローには組み込んでいない)
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import update_products as up  # noqa: E402

KNOWN = up.known_hop_names()
failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def hops(stored, spec, desc, expect, expect_review=False, desc_known=True):
    new, why = up.refresh_hops(stored, spec, desc if desc_known else None, KNOWN)
    if new == stored:  # 保存値と同じ案は「変更なし」(refresh_changesもそう扱う)
        new = None
    check(f"hops stored={stored} spec={spec} desc={desc}", new, expect)
    check(f"  review flag stored={stored} spec={spec}", bool(why), expect_review)


# ---- ホップ: スペック欄が根拠 ----
# Sierra Nevada Rad Little Thing: サイトのスペック欄と説明文が一致して一新されている -> 置き換え
hops(["Citra", "Mosaic", "Galaxy"], ["Bravo", "Chinook", "Citra", "Crystal", "Magnum"],
     ["Bravo", "Chinook", "Citra", "Crystal", "Magnum"], ["Bravo", "Chinook", "Citra", "Crystal", "Magnum"])
# Revision DIPA: 保存値のCitraがスペック欄にも説明文にも無い -> 置き換え
hops(["Citra", "Simcoe", "Mosaic"], ["Simcoe", "Mosaic"], ["Simcoe", "Mosaic"], ["Simcoe", "Mosaic"])
# Faction Pale: スペック欄に無いApolloが説明文に書かれている(ユーザー指示で補った品種) -> 触らない
hops(["Mosaic", "Columbus", "Apollo"], ["Mosaic", "Columbus"], ["Mosaic", "Apollo", "Columbus"], None)
# スペック欄が保存値の一部だけで、残りの保存値がサイトのどこにも無い -> サイトの記載に置き換える(Revision DIPAと同じ型)
hops(["Citra", "Mosaic", "Simcoe"], ["Citra", "Mosaic"], [], ["Citra", "Mosaic"])
# 同じ型でも、残りの保存値を説明文が裏付けているなら残す(WCB Campfire Storiesのような、欄と本文で品種が違うもの)
hops(["Cascade", "Centennial", "Chinook"], ["Cascade", "Centennial"], ["Cascade", "Chinook"], None)
# サイトのスペック欄に品種が増えただけ -> 追記
hops(["Cashmere", "Amarillo"], ["Callista", "Bravo", "Amarillo", "Cashmere"], [],
     ["Cashmere", "Amarillo", "Callista", "Bravo"])
# 保存値が空 -> サイトの記載で埋める
hops([], ["Citra", "Mosaic"], [], ["Citra", "Mosaic"])
# サイトの欄が空 -> 保存値を消さない
hops(["Citra", "Mosaic"], [], [], None)
# 加工品の違い(Citra CryoとCitra)は同じ品種として扱う -> 触らない
hops(["Citra"], ["Citra Cryo"], [], None)
# サイトの欄に未知の名前(チャートに無い) -> 適用せず確認へ
hops(["Mosaic", "Simcoe"], ["Mosaic", "Simcoe", "Zzyzx Hop"], [], None, expect_review=True)
# 説明文が取れない収集元(WCBの一覧): 置き換えはせず追記のみ
hops(["Cascade", "Chinook"], ["Cascade", "Centennial"], None, ["Cascade", "Chinook", "Centennial"], desc_known=False)

# ---- ホップ: 説明文が根拠(スペック欄が空) ----
# Cosmic Little Thing: スペック欄は「-」、説明文はComet/Strata/Helios。保存値(古い記載)と共通の品種が無い -> 置き換え
hops(["Citra", "Mosaic", "Simcoe", "Galaxy"], [], ["Comet", "Strata", "Helios"], ["Comet", "Strata", "Helios"])
# 共通の品種がある(説明文が一部だけ書いている)ときは消さず追記のみ
hops(["Citra", "Mosaic", "Simcoe"], [], ["Citra", "Comet"], ["Citra", "Mosaic", "Simcoe", "Comet"])
# 説明文由来で既に入っている -> 触らない
hops(["Comet", "Strata", "Helios"], [], ["Comet", "Strata", "Helios"], None)

# ---- スペック欄の記載ゆれが正規化後に一致する(表記ゆれだけで更新しない) ----
check("normalize German Tettnang", up.split_hops("German Tettnang, German Mittelfruh"), ["Tettnanger", "Hallertauer Mittelfruher"])
check("normalize Varying dropped", up.split_hops("Mosaic, Simcoe, Saaz, Cascade & Varying"), ["Mosaic", "Simcoe", "Saaz", "Cascade"])
check("normalize Citrulicious dropped", up.split_hops("Citra, Nelson Sauvin,Citrulicious Hop Oil"), ["Citra", "Nelson Sauvin"])
check("normalize Hersbrucker", up.split_hops("Cascade, Hersbrucker"), ["Cascade", "Hersbrucker Spat"])
check("expand Nelson Simcoe", up.split_hops("Citra, Nelson Simcoe"), ["Citra", "Nelson Sauvin", "Simcoe"])
check("normalize Alora known", "Alora" in KNOWN and "HBC 522" in KNOWN, True)


# ---- refresh_changes 全体 ----
def rc(stored, live, desc=None):
    return up.refresh_changes(stored, live, desc, KNOWN)


base = {"name": "Hop Reach IPA", "style": "IPA", "abv": "6.2%", "hops": ["Cascade"]}
# ABV: 数値が変わった -> 更新。同じ数値・サイトが空 -> 触らない
ch, _ = rc(base, {**base, "abv": "6.8%"})
check("abv changed", ch.get("abv"), ("6.2%", "6.8%"))
ch, _ = rc(base, {**base, "abv": "6.2%"})
check("abv same", "abv" in ch, False)
ch, _ = rc(base, {**base, "abv": "-"})
check("abv blank on site keeps stored", "abv" in ch, False)
ch, _ = rc({**base, "abv": "-"}, {**base, "abv": "5.5%"})
check("abv fill from blank", ch.get("abv"), ("-", "5.5%"))

# スタイル: 細分類が変わる -> 更新 / 言い換えだけ -> 触らない / 販売注記・文章 -> 採らない / 分類できない -> 採らない
ch, _ = rc({**base, "style": "IPA"}, {**base, "style": "West Coast IPA"})
check("style IPA->WC IPA", ch.get("style"), ("IPA", "West Coast IPA"))
ch, _ = rc({**base, "style": "Hazy DIPA"}, {**base, "style": "Double IPA"})
check("style paraphrase (same class) untouched", "style" in ch, False)
ch, _ = rc({**base, "style": "Hazy IPA"}, {**base, "style": "Northeast-Style IPA"})
check("style NE paraphrase untouched", "style" in ch, False)
ch, _ = rc({**base, "style": "Saison"}, {**base, "style": "Southbound限定の商品！お一人様1本まで。Only available at Southbound! Limit one bottle per person."})
check("style sales note rejected", "style" in ch, False)
ch, _ = rc({**base, "style": "IPA"}, {**base, "style": "Limit one bottle per person"})
check("style unclassifiable rejected", "style" in ch, False)
ch, _ = rc({**base, "style": "Sour"}, {**base, "style": "Belgian Witbier (Oak-Barrel-Aged)"})
check("style Sour->Witbier", ch.get("style"), ("Sour", "Belgian Witbier (Oak-Barrel-Aged)"))
ch, _ = rc({**base, "style": "DIPA"}, {**base, "style": "DDH QIPA"})
check("QIPA stays double-class (no change)", "style" in ch, False)

# 名前: 通常は触らない(ブリュワリー名の有無)。再発売(細分類と度数が同時に変わる)だけ追従
ch, _ = rc({**base, "name": "Coronado Weekend Vibes IPA"}, {**base, "name": "Weekend Vibes IPA"})
check("name decoration untouched", "name" in ch, False)
soccer = {"name": "Ambitious Ales Soccer Pants WC IPA", "style": "West Coast IPA", "abv": "6.5%", "hops": []}
ch, _ = rc(soccer, {"name": "Soccer Pants DDH Hazy DIPA", "style": "DDH Hazy DIPA", "abv": "8%", "hops": []})
check("relaunch updates style+abv+name", sorted(ch), ["abv", "name", "style"])
check("relaunch name", ch["name"], ("Ambitious Ales Soccer Pants WC IPA", "Soccer Pants DDH Hazy DIPA"))

# 説明文・画像は更新対象外
ch, _ = rc({**base, "description": "旧", "image": "a.jpg"}, {**base, "description": "新", "image": "b.jpg"})
check("description/image untouched", ch, {})

# ---- 売り切れ新商品の登録判定 ----
today = date.today()
iso = lambda d: d.isoformat() + "T12:00:00+09:00"  # noqa: E731
check("published 3 days ago", up.recently_published({"published_at": iso(today - timedelta(days=3))}, 14), True)
check("published 20 days ago", up.recently_published({"published_at": iso(today - timedelta(days=20))}, 14), False)
check("published_at missing", up.recently_published({}, 14), False)
check("window 0 disables", up.recently_published({"published_at": iso(today)}, 0), False)

# ---- 収集対象の判定(Mixパックの扱い) ----
check("Mix pack now in scope", up.shopify_scope({"vendor": "Mix", "tags": ["Beer"], "product_type": "49th State Brewing"}, "antenna")[0], True)
check("Merchandise out of scope", up.shopify_scope({"vendor": "Merchandise", "tags": [], "product_type": "x"}, "antenna")[0], False)
check("Southbound Set out of scope", up.shopify_scope({"product_type": "Set"}, "southbound")[0], False)

# ---- 商品名: 先頭の販促タグを除く(英字の銘柄名が続くときだけ) ----
def antenna_name(title, product_type=""):
    p = {"handle": "x", "title": title, "body_html": "<ul><li>ブリュワリー：%s</li></ul>" % product_type, "product_type": product_type,
         "vendor": "IPA", "images": []}
    return up.parse_antenna_product(p, "antenna", "https://example.com")["name"]


check("promo tag stripped", antenna_name("【再入荷】Pizza Port Swami's IPA (355ml) / スワミズIPA", "Pizza Port"), "Swami's IPA")
check("multi tag stripped", antenna_name("【ACBE2026でも大注目！】Embolden Beer Co Shogun - The Warrior Rice Lager (473ml) / x", "Embolden Beer Co"),
      "Shogun - The Warrior Rice Lager")
check("japanese set name keeps tag", antenna_name("【Pilsロゴグラス付き】Sierra Nevada 飲み比べ11本セット", ""), "【Pilsロゴグラス付き】Sierra Nevada 飲み比べ11本セット")
check("banner stripped from a single beer", antenna_name("＼新宿店オープン記念1本購入でラベル1枚プレゼント／Monkish Shinjuku DDH Hazy IPA (473ml) / 新宿", "Monkish"), "Shinjuku DDH Hazy IPA")
check("banner kept on a Japanese set name", antenna_name("＼新宿西口店オープン記念ビール入り／Monkish 満喫8本セット【11/26出荷】", "Monkish"), "＼新宿西口店オープン記念ビール入り／Monkish 満喫8本セット【11/26出荷】")
check("normalize German Hallertau Mittelfruh", up.split_hops("German Hallertau Mittelfruh"), ["Hallertauer Mittelfruher"])

if failures:
    print(f"FAILED {len(failures)}")
    for f in failures:
        print("  " + f)
    sys.exit(1)
print("OK: all refresh / registration-rule cases passed")
