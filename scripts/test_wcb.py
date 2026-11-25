"""
West Coast Brewingの「w/」行の解析(update_products.wcb_hops)の回帰テスト。2026-11-16に過去分540銘柄の全行を調べて整理した。
例は実際の行(一部はその行から抜粋)。ルールを変えたら必ず実行すること:
    python scripts/test_wcb.py
(失敗があれば終了コード1。週次/月次のワークフローには組み込んでいない)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import update_products as up  # noqa: E402

CASES = [
    # 素直な列挙(従来の形。結果は旧解析と同じ)
    ("Cascade, Centennial & Columbus", ["Cascade", "Centennial", "Columbus"]),
    ("Chinook", ["Chinook"]),
    ("Cascade, Simcoe & Simcoe CRYO", ["Cascade", "Simcoe", "Simcoe Cryo"]),
    ("", []),
    # 「Dry Hopped with」の文: それより前は副原料の列挙
    ("Blueberry, Blackberry, Marionberry and Milk Sugar. Dry Hopped with Strata, Mosaic & Mosaic CRYO", ["Strata", "Mosaic", "Mosaic Cryo"]),
    ("Pineapple.  Dry Hopped with  El Dorado, Idaho7 & Luminosa", ["El Dorado", "Idaho 7", "Luminosa"]),
    ("Citrus. Dry Hopped w/Cascade, Cashmere, Citra & Lemon Drop", ["Cascade", "Cashmere", "Citra", "Lemondrop"]),
    ("Clean Fusion. Dry Hopped with Cascade & Chinook", ["Cascade", "Chinook"]),  # Clean Fusionは製法でホップではない
    ("Dekopon. Dry Hopped with Citra, Centenial, Chinook, Simcoe＆Simcoe CRYO", ["Citra", "Centennial", "Chinook", "Simcoe", "Simcoe Cryo"]),
    # 副原料だけの行・副原料が混ざる行
    ("Locally sourced strawberries", []),
    ("Hazelnut, Vanilla Beans & Cacao Nibs", []),
    ("Merlot (Japanese) & Muscat Bailey A (Japanese) Grape skins", []),
    ("Raw and Malted Wheat, Lactose, Passionfruit, Japanese Plum, Blackcurrant, Elderflower , Yuzu, Cascade, Cashmere & Mosaic", ["Cascade", "Cashmere", "Mosaic"]),
    ("Guava, Apricot, Coconut", []),
    # 全角記号
    ("ｗ/ Citra CRYO", ["Citra Cryo"]),
    ("El Dorado・Nelson Sauvin・Strata・Mosaic・Mosaic CRYO", ["El Dorado", "Nelson Sauvin", "Strata", "Mosaic", "Mosaic Cryo"]),
    ("ｗ/Citra, Amarillo, Denali ＆ Enigma", ["Citra", "Amarillo", "Sultana", "Enigma"]),  # Denaliは旧商品名でSultanaに改名
    # 供給元・ロットの修飾
    ("Freestyle Nelson Sauvin PM24, Citra, Cashmere & Freestyle Rakau Hop Kief", ["Nelson Sauvin", "Citra", "Cashmere", "Rakau Kief"]),
    ("Nelson Sauvin PM19, Citra CRYO, Super Sauvin X53X, Nelson Sauvin PM16 & Nelson Sauvin YM23", ["Nelson Sauvin", "Citra Cryo", "Super Sauvin"]),
    ("Nelson Sauvin(25QL), Motueka KM09 & Idaho7 YCH702", ["Nelson Sauvin", "Motueka", "Idaho 7"]),
    ("Riwaka, Riwaka Diesel, Nelson Sauvin, Riwaka Hop Kief & Nelson Sauvin Hop Kief", ["Riwaka", "Nelson Sauvin", "Riwaka Kief", "Nelson Sauvin Kief"]),
    ("EG Comet, EG Crosby Comet, Crosby El Dorado, YCH301 Citra & YCH Simcoe", ["Comet", "El Dorado", "Citra", "Simcoe"]),
    ("Nelson Sauvin Bliss Process, Nelson Bliss & Selected 2024 Indie Strata", ["Nelson Sauvin", "Strata"]),
    ("Wakatu, Bruce & NZ Cascade", ["Wakatu (NZ Hops)", "The Bruce", "Cascade"]),
    ("Kohia Nelson, Peacharine & Southern Cross", ["Kohia Nelson", "Peacharine", "Southern Cross (NZ Hops)"]),  # Kohia NelsonはNelson Sauvinとは別のブレンド
    # 加工品・ブレンド・コード
    ("Mosaic, Rakau, Pacifica & Quantum(El Dorado)", ["Mosaic", "Rakau", "Pacifica (NZ Hops)", "El Dorado Quantum"]),
    ("El Dorado, Nelson Sauvin, Peacharine, Strata＆ Nelson Kief", ["El Dorado", "Nelson Sauvin", "Peacharine", "Strata", "Nelson Sauvin Kief"]),
    ("Kohatu, Motueka, Citra CRYO & HBC1019", ["Kohatu", "Motueka", "Citra Cryo", "HBC 1019"]),
    ("Idaho7, CRYO POP®, Citra CRYO, Idaho7 CRYO & Mosaic CRYO", ["Idaho 7", "Cryo Pop", "Citra Cryo", "Idaho 7 Cryo", "Mosaic Cryo"]),
    ("Idaho7, Idaho7 Cryo, Citra Cryo, Mosaic Cryo & TRI2304CR", ["Idaho 7", "Idaho 7 Cryo", "Citra Cryo", "Mosaic Cryo", "Cryo Pop"]),
    ("Pink Boots Blend(HBC638, El Dorado, Ahtanum & Idaho7), ID158 & Mosaic", ["Pink Boots Blend", "ID158", "Mosaic"]),
    ("Anchovy, Citra, Nelson Sauvin & Anchovy Liquid Lupulin", ["Anchovy", "Citra", "Nelson Sauvin"]),
    ("Anchovy, Mosaic, Strata & ADHA 1631", ["Anchovy", "Mosaic", "Strata", "ADHA 1631"]),
    # 綴りミス
    ("Riwaka, Cacade, Centennial & Citra CRYO", ["Riwaka", "Cascade", "Centennial", "Citra Cryo"]),
    ("Citara, Rakau & Wakatu", ["Citra", "Rakau", "Wakatu (NZ Hops)"]),
    ("Hallerteau Mittlefruh, Saphir & Centennial", ["Hallertauer Mittelfruher", "Saphir", "Centennial"]),
    ("Nelson Sauvin, Idaho7 & Saltana", ["Nelson Sauvin", "Idaho 7", "Sultana"]),
    # 括弧つきの一語(カンマを含む括弧書きは1語のまま扱う)
    ("Vanilla Toasted Coconut, Vanilla Beans & Modern Times Idea Machine", []),
]


def check_completeness_fallback(failures):
    """WP REST APIがGitHubのIPから403で止められても(2026-11-25に確認)、全銘柄の照合(月次監査・総チェック)が止まらない"""
    import audit_catalog as ac
    source = {"source_key": "westcoast", "base_url": "https://example.test", "archive_path": "/beer/"}
    saved = (up.wcb_rest_dates, up.wcb_list_items)
    try:
        up.wcb_rest_dates = lambda s: {}  # REST: 403で空
        up.wcb_list_items = lambda s, archive=False, max_archive_pages=60: [
            {"slug": "a", "url": "u/a", "name": "A"}, {"slug": "b", "url": "u/b", "name": "B"}]
        slugs = up.wcb_all_slugs(source)
        if slugs != {"a": "", "b": ""}:
            failures.append(f"wcb_all_slugs fallback: got {slugs}")
        missing, _note = ac.unregistered_wcb_items(source, {"westcoast-a"})
        if [m["id"] for m in missing] != ["b"]:
            failures.append(f"unregistered_wcb_items fallback: got {[m['id'] for m in missing]}")
        up.wcb_rest_dates = lambda s: {"a": "2021-11-02", "b": "2021-10-01"}  # RESTが読めるとき
        slugs = up.wcb_all_slugs(source)
        if slugs != {"a": "2021-11-02", "b": "2021-10-01"}:
            failures.append(f"wcb_all_slugs via REST: got {slugs}")
    finally:
        up.wcb_rest_dates, up.wcb_list_items = saved
    page = '<script type="application/ld+json">{"@graph":[{"datePublished":"2021-10-01T14:07:00+00:00"}]}</script>'
    if up.parse_wcb_published(page) != "2021-10-01":
        failures.append(f"parse_wcb_published: got {up.parse_wcb_published(page)!r}")
    if up.parse_wcb_published("<html></html>") != "":
        failures.append("parse_wcb_published should be empty without JSON-LD")


def main():
    failures = []
    for raw, want in CASES:
        got = up.wcb_hops(raw)
        if got != want:
            failures.append(f"{raw!r}\n      got  {got}\n      want {want}")
    check_completeness_fallback(failures)
    if failures:
        print(f"FAILED {len(failures)}")
        for f in failures:
            print("  " + f)
        sys.exit(1)
    print(f"OK: {len(CASES)} cases passed")


if __name__ == "__main__":
    main()
