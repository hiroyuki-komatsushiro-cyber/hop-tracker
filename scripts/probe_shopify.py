"""
新しいShopify系の収集先の下見(README_MIGRATION.md「新しい収集先の追加チェックリスト」2)。
products.json を1回だけ全ページ取得し、構造の要約を表示し、生データを probe_out/ に保存する(ワークフローがartifactにする)。
何も登録しない・何も書き換えない。取得は update_products.fetch_catalog と同じ(1.2秒間隔、正直なUser-Agent)。

使い方(GitHub上で実行する。手元のPCから全カタログを繰り返し取ると、Shopifyのレート制限/ボット確認で止められる):
    gh workflow run probe-shopify.yml -f base_url=https://example.com
    gh run download <id> -D <出力先>   # 生データ(probe_out/products.json)を手元で解析する。サイトへの再アクセスは要らない
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import update_products as up  # noqa: E402

OUT_DIR = Path(__file__).parent.parent / "probe_out"
SAMPLE_TEXT = 700


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BASE_URL", "")).rstrip("/")
    if not base.startswith("https://"):
        sys.exit("usage: probe_shopify.py https://store.example.com")
    catalog = up.fetch_catalog(base)
    if not catalog:
        sys.exit(f"{base}: products.json returned no products (blocked, rate limited, or not a Shopify store). Do not bypass it.")
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "products.json").write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")

    # 任意: 商品ページのHTMLも数件だけ保存する(ABV等が商品説明ではなくページ側の別の場所に出ていないかを見る用)。
    # 環境変数 PAGES=handle1,handle2(最大5件)。1.2秒間隔
    import re as _re
    handles = [h.strip() for h in os.environ.get("PAGES", "").split(",") if h.strip()][:5]
    for h in handles:
        page = up.fetch_url(f"{base}/products/{h}")
        up.time.sleep(up.REQUEST_DELAY)
        (OUT_DIR / "pages").mkdir(exist_ok=True)
        (OUT_DIR / "pages" / f"{h}.html").write_text(page, encoding="utf-8")
        print(f"[page {h}] {len(page)} bytes; lines mentioning ABV/アルコール/ホップ/HOP:")
        for m in list(_re.finditer(r"[^<>\n]{0,60}(?:ABV|アルコール|ホップ|HOP|IBU|スタイル)[^<>\n]{0,80}", page))[:12]:
            print("    ", m.group(0).strip())
    instock = [p for p in catalog if up.in_stock(p)]
    print(f"{base}: {len(catalog)} products, {len(instock)} in stock")
    print("product_type:", Counter(p.get("product_type") for p in catalog).most_common())
    print("vendor:", Counter(p.get("vendor") for p in catalog).most_common(12))
    tags = Counter(t for p in catalog for t in p.get("tags", []))
    print("tags (top 30):", tags.most_common(30))
    pubs = sorted(p.get("published_at", "")[:10] for p in catalog)
    print("published_at range:", pubs[0], "..", pubs[-1])
    print("with images:", sum(1 for p in catalog if p.get("images")), "| empty body:", sum(1 for p in catalog if not (p.get("body_html") or "").strip()))
    print()
    # 種類ごとに数件ずつ、タイトル・タグ・在庫・説明文(先頭)を出す。ホップ・ABV・スタイルがどこにどう書かれているかを見る用
    seen = Counter()
    for p in catalog:
        ptype = p.get("product_type") or "(none)"
        if seen[ptype] >= 4:
            continue
        seen[ptype] += 1
        text = up.strip_tags(__import__("re").sub(r"</(p|li|h\d|div)>", "\n", p.get("body_html") or "", flags=__import__("re").I))
        print("-" * 70)
        print(f"[{ptype}] {p['title']}  (handle={p['handle']}, vendor={p.get('vendor')}, in_stock={up.in_stock(p)}, published={p.get('published_at', '')[:10]})")
        print("  tags:", p.get("tags"))
        print("  variants:", [(v.get("title"), v.get("price"), v.get("available")) for v in p.get("variants", [])][:4])
        print("  body:", " / ".join(t.strip() for t in text.splitlines() if t.strip())[:SAMPLE_TEXT])


if __name__ == "__main__":
    main()
