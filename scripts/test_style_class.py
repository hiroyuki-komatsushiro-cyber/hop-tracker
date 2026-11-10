"""
スタイル細分類・度数帯(style_class.py)の回帰テスト。実際の商品のstyle表記を例にしている。

style_class.py のルールを変えたら必ず実行すること:
    python scripts/test_style_class.py
(失敗があれば終了コード1。週次/月次のワークフローには組み込んでいない)
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import style_class as sc  # noqa: E402

# (style, name, 期待する細分類)
CASES = [
    # --- IPA系
    ("Hazy IPA", "", "ipa_hazy"), ("DDH Hazy IPA", "", "ipa_hazy"), ("New England IPA", "", "ipa_hazy"), ("NEIPA", "", "ipa_hazy"),
    ("Double Mashed Hazy IPA", "", "ipa_hazy"), ("Tropical IPA", "", "ipa_hazy"), ("Murky IPA", "", "ipa_hazy"),
    ("West Coast IPA", "", "ipa_wc"), ("WC IPA", "", "ipa_wc"), ("San Diego-Style IPA", "", "ipa_wc"), ("NW IPA", "", "ipa_wc"),
    ("DDH WC IPA", "", "ipa_wc"), ("West Coast-Style India Pale Ale", "", "ipa_wc"),
    ("IPA", "", "ipa_plain"), ("American IPA", "", "ipa_plain"), ("India Pale Ale", "", "ipa_plain"), ("Single Hop IPA", "", "ipa_plain"),
    ("NZIPA", "", "ipa_plain"), ("Extra IPA", "", "ipa_plain"),
    ("DIPA", "", "ipa_double"), ("Hazy DIPA", "", "ipa_double"), ("Double IPA", "", "ipa_double"), ("TIPA", "", "ipa_double"),
    ("Hazy Triple IPA", "", "ipa_double"), ("Imperial Red IPA", "", "ipa_double"), ("NE-Style Hazy Double IPA", "", "ipa_double"),
    ("Fruited IIPA", "", "ipa_double"), ("DIPA / Imperial", "", "ipa_double"),
    ("Session IPA", "", "ipa_session"), ("Session Hazy", "", "ipa_session"), ("CBD & TERPENE-Infused West Coast Session IPA", "", "ipa_session"),
    ("Cold IPA", "", "ipa_cold_brut"), ("Brut IPA", "", "ipa_cold_brut"),
    ("Red IPA", "", "ipa_color"), ("Black IPA", "", "ipa_color"), ("Belgian IPA", "", "ipa_color"), ("Cascadian Dark Ale", "", "ipa_color"),
    ("Sour IPA", "", "ipa_sour"), ("Sour DIPA", "", "ipa_sour"), ("Mixed Culture IPA", "", "ipa_sour"), ("Brux IPA", "", "ipa_sour"),
    ("Oats IPA", "", "ipa_special"), ("Terpene IPA", "", "ipa_special"), ("Strawberry Milkshake IPA", "", "ipa_special"),
    ("Fresh Hop IPA", "", "ipa_special"), ("Fruited IPA", "", "ipa_special"), ("Spruce Tip IPA", "", "ipa_special"),
    # --- エール系
    ("Pale Ale", "", "pale_american"), ("American Pale Ale", "", "pale_american"), ("West Coast Pale Ale", "", "pale_american"),
    ("Single Hop Pale Ale", "", "pale_american"),
    ("Hazy Pale Ale", "", "pale_hazy_nz"), ("Hazy Pale", "", "pale_hazy_nz"), ("NZ Pale Ale", "", "pale_hazy_nz"),
    ("TDH New Zealand Pale Ale", "", "pale_hazy_nz"),
    ("Blonde Ale", "", "ale_blonde"), ("Golden Ale", "", "ale_blonde"), ("Hazy Blonde", "", "ale_blonde"), ("Honey Ale", "", "ale_blonde"),
    ("Rye Bolnde", "", "ale_blonde"),
    ("Amber Ale", "", "ale_amber"), ("Irish Red Ale", "", "ale_amber"), ("Red Ale", "", "ale_amber"),
    ("Mild Ale", "", "ale_brown_english"), ("American Brown Ale", "", "ale_brown_english"), ("English Pale Ale", "", "ale_brown_english"),
    ("Bitter", "", "ale_brown_english"),
    # --- ラガー系
    ("Pilsner", "", "lager_pils"), ("West Coast Pilsner", "", "lager_pils"), ("Italian style Pilsner", "", "lager_pils"),
    ("Lager / Pilsner", "", "lager_pils"), ("Dry Hopped Pilsner", "", "lager_pils"),
    ("Session IPL", "", "lager_hoppy"), ("TIPL", "", "lager_hoppy"), ("West Coast-style Hoppy Lager", "", "lager_hoppy"),
    ("Lager", "", "lager_light"), ("American Lager", "", "lager_light"), ("Helles", "", "lager_light"), ("Pale Lager", "", "lager_light"),
    ("Unfiltered Lager", "", "lager_light"),  # "red lager"に部分一致していた回帰
    ("Mexican Lager", "", "lager_mexican"), ("Baja-style Lager", "", "lager_mexican"),
    ("Vienna Lager", "", "lager_dark_amber"), ("Red Lager", "", "lager_dark_amber"), ("Italian Red Lager", "", "lager_dark_amber"),
    ("Dark Lager", "", "lager_dark_amber"), ("Festbier", "", "lager_dark_amber"), ("Bock", "", "lager_dark_amber"),
    ("Smoked Lager", "", "lager_special"), ("Rice Lager", "", "lager_special"), ("Japanese Lager", "", "lager_special"),
    ("Hojicha Lager", "", "lager_special"), ("Pseudo Lager (スードラガー)", "", "lager_special"), ("Vienna Pseudo Lager", "", "lager_special"),
    # --- 小麦・ベルギー・セゾン系
    ("Hefeweizen", "", "wheat"), ("Hoppy Wheat", "", "wheat"), ("Fruited Wheat", "", "wheat"), ("Wheat Lager", "", "wheat"),
    ("Belgian Wit", "", "bel_wit"), ("White Ale", "", "bel_wit"), ("Belgian style Wheat", "", "bel_wit"),
    ("Belgian Pale Ale", "", "bel_ale"), ("Belgian Blonde", "", "bel_ale"), ("Belgian-Style Golden Ale", "", "bel_ale"),
    ("Belgian Tripel", "", "bel_strong"), ("Belgian Quad", "", "bel_strong"), ("Belgian Golden Strong Ale", "", "bel_strong"),
    ("Bourbon Barrel Aged Belgian-Style Quadrupel", "", "bel_strong"),
    ("Saison", "", "sai_farm"), ("Hoppy Farmhouse Ale with New Zealand Hops", "", "sai_farm"), ("Grisette", "", "sai_farm"),
    ("Table Saison", "", "sai_farm"), ("Saiosn", "", "sai_farm"), ("Farmhouse Ale Refermented on Raspberries", "", "sai_farm"),
    # --- サワー・ワイルド系
    ("Sour", "", "sour_fruit"), ("Fruited Sour", "", "sour_fruit"), ("Sour Saison", "", "sour_fruit"),
    ("Mango Sour w/Pineapple&Chili", "", "sour_fruit"), ("Sour Blonde", "", "sour_fruit"),
    ("Peach Gose", "", "sour_gose"), ("Triple Fruited Gose", "", "sour_gose"), ("Lichtenhainer", "", "sour_gose"),
    ("Traditional Lambic", "", "sour_wild"), ("Wild Ale Fermented in Oak", "", "sour_wild"),
    ("Bière de Coupage (Blended Farmhouse Ale)", "", "sour_wild"), ("Brett Table Saison", "", "sour_wild"),
    ("Barrel Aged Sour Ale", "", "sour_wild"),
    # --- スタウト・ポーター・ストロング系
    ("Stout", "", "dark_stout"), ("Milk Stout", "", "dark_stout"), ("Pastry Stout", "", "dark_stout"), ("Stout / Porter", "", "dark_stout"),
    ("Porter", "", "dark_porter"), ("Robust Porter w/ Coffee", "", "dark_porter"), ("Mexican Hot Chocolate Porter", "", "dark_porter"),
    ("Imperial Stout", "", "dark_imperial"), ("Bourbon Barrel-Aged Imperial Stout", "", "dark_imperial"), ("BA Imperial Stout", "", "dark_imperial"),
    ("Russian Imperial Stout", "", "dark_imperial"), ("Imperial Porter", "", "dark_imperial"), ("Barrel Aged Stout", "", "dark_imperial"),
    ("Mint Chocolate Chip Ice Cream Stout Aged in Wheated Bourbon Barrels", "", "dark_imperial"),
    ("Barley Wine", "", "dark_strong"), ("Strong Wheat Wine With Honey (Bourbon Barrel-Aged)", "", "dark_strong"),
    ("Peated Scotch Ale", "", "dark_strong"), ("Blend of Stout, Quadrupel, and Barleywine", "", "dark_strong"),
    # --- サイダー・ミード・セット・その他
    ("Cider", "", "cider"), ("Dry Hard Cider", "", "cider"), ("Hard Cider with Ginger", "", "cider"), ("Perry Craft Cider", "", "cider"),
    ("Mead", "", "mead"), ("Session Mead with Mango", "", "mead"), ("Fruited Mead with Lactose and Vanilla", "", "mead"),
    ("0", "Plum Mead", "mead"),  # style欄が「0」でも商品名で救う
    ("MIX", "", "set_mix"), ("Variety Pack", "", "set_mix"),
    ("Double IPA", "Delicious Family 4本セット", "set_mix"),  # セットはstyle欄が中の1本の値
    ("Hazy IPA", "Embolden Shogunシリーズ4本セット 【うち新作1本】", "set_mix"),
    ("アメリカンクラフトビール通販 Antenna America", "《オクトーバーフェスト！》 Pils （3本）・Oktoberfest 2026 （3本）", "set_mix"),
    ("Hazy IPA", "Sunset Hazy IPA", "ipa_hazy"),  # "set"が単語でない名前はセットにしない
    ("Blueberry Ale", "", "other_beer"), ("Fruited Ale", "", "other_beer"),
]

ABV_CASES = [("6.5%", 6.5), ("12%", 12.0), ("7%", 7.0), ("-", None), ("", None), ("0", None), (None, None), ("4.4%", 4.4)]
BAND_CASES = [(4.9, "abv_lt5"), (3.4, "abv_lt5"), (5.0, "abv_5"), (5.99, "abv_5"), (6.0, "abv_6"), (7.5, "abv_7"), (8.0, "abv_8"),
              (9.9, "abv_8"), (10.0, "abv_10"), (17.0, "abv_10"), (None, "abv_unknown")]


def main():
    failures = []
    for style, name, expected in CASES:
        got = sc.classify_style(style, name)[1]
        if got != expected:
            failures.append(f"style={style!r} name={name!r}: expected {expected} got {got}")
    for raw, expected in ABV_CASES:
        if sc.parse_abv(raw) != expected:
            failures.append(f"parse_abv({raw!r}) expected {expected} got {sc.parse_abv(raw)}")
    for v, expected in BAND_CASES:
        if sc.abv_band(v) != expected:
            failures.append(f"abv_band({v}) expected {expected} got {sc.abv_band(v)}")

    # 表の整合性: ルールの行き先が分類表に在る、キーの重複が無い、フォールバックが在る
    subs = [s for _, _, ss in sc.GROUPS for s, _ in ss]
    if len(subs) != len(set(subs)):
        failures.append("duplicate sub-style keys")
    if len({g for g, _, _ in sc.GROUPS}) != len(sc.GROUPS):
        failures.append("duplicate group keys")
    for key, _ in sc.RULES:
        if key not in sc.SUB_TO_GROUP:
            failures.append(f"rule target missing from GROUPS: {key}")
    if sc.FALLBACK not in sc.SUB_TO_GROUP:
        failures.append("FALLBACK missing from GROUPS")
    unused = [s for s in subs if s != sc.FALLBACK and s not in {k for k, _ in sc.RULES}]
    if unused:
        failures.append(f"sub-styles without a rule: {unused}")

    # 実データでの「その他のビール」の割合(新しい表記が増えたら気づくための目安。失敗にはしない)
    data = Path(__file__).parent.parent / "data" / "products.json"
    note = ""
    if data.exists():
        ps = json.loads(data.read_text(encoding="utf-8"))["products"]
        c = Counter(sc.classify_style(p.get("style", ""), p.get("name", ""))[1] for p in ps)
        share = c[sc.FALLBACK] / max(len(ps), 1)
        note = f" | real data: {len(ps)} products, other_beer {c[sc.FALLBACK]} ({share:.1%})"
        if share > 0.05:
            failures.append(f"other_beer share too high ({share:.1%}): new style spellings need rules")

    total = len(CASES) + len(ABV_CASES) + len(BAND_CASES)
    if failures:
        print(f"FAILED {len(failures)}")
        for f in failures:
            print("  " + f)
        sys.exit(1)
    print(f"OK: {total} cases passed{note}")


if __name__ == "__main__":
    main()
