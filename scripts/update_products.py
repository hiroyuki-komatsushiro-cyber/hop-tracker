"""
新商品自動検出・追記スクリプト (Antenna America + Southbound)

毎週実行され、以下を行う:
1. update_sources.json に登録された各サイトのコレクションページ(在庫あり商品一覧)を巡回
2. 商品リンクを抽出
3. data/products.json に存在しないIDのみ、個別ページを取得
4. Claude APIでホップ・ABV・スタイル・日本語説明文を抽出、og:imageから画像URLを取得
5. products.json に追記(既存データは一切削除しない)
6. 変更があればコミット用に差分をログ出力

2026-08: Southbound巡回 + image/description抽出に対応(README_MIGRATION.mdの仕様に追従)。
それまでは Antenna America のみ・hops/style/abv/brewery/name しか取得していなかった。
"""

import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import anthropic

ROOT = Path(__file__).parent.parent
DATA_PATH = ROOT / "data" / "products.json"
SOURCES_PATH = Path(__file__).parent / "update_sources.json"
HOPS_TAB_JS_PATH = Path(__file__).parent / "hops_tab.js"
USER_AGENT = "Mozilla/5.0 (compatible; HopTrackerBot/1.0; +https://github.com/)"

CLAUDE_MODEL = "claude-sonnet-4-6"
REQUEST_DELAY = 1.2  # seconds between requests - be polite to small retail sites, do not lower this

# 既知のブリュワリー名の表記ゆれ正規化(README_MIGRATION.md「更新ルール」より)。
# キーは小文字・空白除去したゆれ表記、値はデータセットで使う正式表記。
# 新しいゆれを見つけたらここに追記する。
BREWERY_ALIASES = {
    "laaleworks": "LA Ale Works",
    "l.a.aleworks": "LA Ale Works",
    "harlandbrewing": "Harland",
    "harlandbrewingco": "Harland",
    "harlandbrewingcompany": "Harland",
    "revisionbrewingcompany": "Revision Brewing",
    "revisionbrewery": "Revision Brewing",
}


def normalize_brewery(name: str) -> str:
    key = re.sub(r"[^a-z0-9]", "", name.lower())
    return BREWERY_ALIASES.get(key, name)


def fetch_url(url: str, timeout: int = 20) -> str:
    """Fetch a URL's HTML content as text."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="ignore")
    except (HTTPError, URLError) as e:
        print(f"  [warn] failed to fetch {url}: {e}", file=sys.stderr)
        return ""


def extract_product_links(html: str) -> list[str]:
    """Pull unique /products/<handle> URLs from a collection page."""
    handles = set(re.findall(r'/products/([a-zA-Z0-9\-]+)', html))
    return sorted(handles)


def extract_og_image(html: str) -> str:
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    if not m:
        return ""
    url = m.group(1)
    if url.startswith("//"):
        url = "https:" + url
    # 統一サイズを付与(既存の慣習に合わせて幅400px)
    url = re.sub(r"\?.*$", "", url)
    return url + "?width=400"


def load_existing_data() -> dict:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict) -> None:
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_sources() -> list[dict]:
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["sources"]


def existing_ids(data: dict) -> set[str]:
    return {p["id"] for p in data["products"]}


def known_hop_names() -> set[str]:
    """Parse scripts/hops_tab.js's `hops` array for variety names already in the aroma chart."""
    text = HOPS_TAB_JS_PATH.read_text(encoding="utf-8")
    return set(re.findall(r'\{name:"([^"]+)"', text))


def analyze_product_with_claude(client: anthropic.Anthropic, handle: str, html: str) -> dict | None:
    """Ask Claude to extract structured product info + a Japanese description from a raw product page."""
    # Trim HTML to keep token usage reasonable - keep main content area only
    snippet = html[:15000]

    prompt = f"""以下はクラフトビール通販サイトの商品ページのHTMLです。
この商品について、次のJSON形式で情報を抽出してください。情報が見つからない項目は空文字または空配列にしてください。
出力はJSONのみとし、説明文やマークダウンの```は付けないでください。

{{
  "name": "商品名(日本語表記があれば優先、なければ英語名)",
  "brewery": "ブリュワリー名(英語表記のまま)",
  "style": "ビアスタイル(例: IPA, DIPA, Pale Ale, Lager)",
  "abv": "アルコール度数(例: 6.5%、不明なら-)",
  "hops": ["使用ホップ品種を英語名でリスト化。ページに明記が無ければ空配列(推測で埋めない)"],
  "description": "日本語の商品紹介文を100〜150文字程度で。ページ内の説明が英語なら日本語に翻訳・要約する。ホップの風味や特徴に触れること"
}}

HTML:
{snippet}
"""

    try:
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        text = text.strip()
        # Strip accidental code fences
        text = re.sub(r"^```json\s*|\s*```$", "", text.strip())
        parsed = json.loads(text)
        return parsed
    except Exception as e:
        print(f"  [warn] Claude parse failed for {handle}: {e}", file=sys.stderr)
        return None


def collect_new_handles(sources: list[dict], known_ids: set[str]) -> list[tuple[str, str, str]]:
    """Return list of (handle, base_url, source_key) for products not yet in data, deduped across sources."""
    seen_handles: dict[str, tuple[str, str]] = {}  # handle -> (base_url, source_key)
    for source in sources:
        base_url = source["base_url"]
        source_key = source["source_key"]
        for page_url in source["collection_pages"]:
            print(f"[{source['name']}] fetching {page_url} ...")
            html = fetch_url(page_url)
            time.sleep(REQUEST_DELAY)
            if not html:
                print(f"  [warn] could not fetch collection page. Site may block bots (robots.txt),"
                      f" or the page moved.", file=sys.stderr)
                continue
            handles = extract_product_links(html)
            print(f"  found {len(handles)} product handles.")
            for h in handles:
                if h not in seen_handles:
                    seen_handles[h] = (base_url, source_key)

    new_handles = [
        (h, base_url, source_key)
        for h, (base_url, source_key) in seen_handles.items()
        if h not in known_ids
    ]
    return new_handles


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    sources = load_sources()

    data = load_existing_data()
    known_ids = existing_ids(data)
    known_hops = known_hop_names()

    print(f"[{date.today()}] Scanning {len(sources)} source site(s) for product listings...")
    new_handles = collect_new_handles(sources, known_ids)
    print(f"\n{len(new_handles)} potentially new products to check across all sources.")

    added = []
    unknown_hops_seen = set()
    for handle, base_url, source_key in new_handles:
        url = f"{base_url}/products/{handle}"
        print(f"  Fetching {url} ...")
        html = fetch_url(url)
        time.sleep(REQUEST_DELAY)
        if not html:
            continue

        info = analyze_product_with_claude(client, handle, html)
        if not info or not info.get("name"):
            print(f"  [skip] could not extract info for {handle}")
            continue

        hops = info.get("hops", []) or []
        for h in hops:
            if h not in known_hops:
                unknown_hops_seen.add(h)

        new_product = {
            "id": handle,
            "name": info.get("name", ""),
            "brewery": normalize_brewery(info.get("brewery", "")),
            "style": info.get("style", ""),
            "abv": info.get("abv", "-"),
            "hops": hops,
            "url": url,
            "added": str(date.today()),
            "image": extract_og_image(html),
            "description": info.get("description", ""),
            "source": source_key,
        }
        data["products"].append(new_product)
        added.append(new_product)

    data["last_updated"] = str(date.today())
    save_data(data)

    print(f"\nDone. {len(added)} new products added. Total products: {len(data['products'])}.")
    if added:
        print("\nNew products this run:")
        for p in added:
            print(f"  - {p['name']} ({p['brewery']}) [{p['source']}] - hops: {', '.join(p['hops']) or 'unknown'}")
    if unknown_hops_seen:
        print("\n[review needed] hop varieties not yet in scripts/hops_tab.js's aroma chart"
              " (add sensory-profile vectors manually, do not fabricate):")
        for h in sorted(unknown_hops_seen):
            print(f"  - {h}")

    # Write a summary file for the workflow / notification step
    summary_path = ROOT / "data" / "last_run_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "date": str(date.today()),
                "new_products": added,
                "hops_needing_aroma_review": sorted(unknown_hops_seen),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


if __name__ == "__main__":
    main()
