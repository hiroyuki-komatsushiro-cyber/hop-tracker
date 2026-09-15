"""
新商品自動検出・追記スクリプト (Antenna America + Southbound)

毎週実行され、以下を行う:
1. 各サイトが公開しているShopify標準の products.json フィード(全ページ)を取得
2. 在庫あり(variants[].available)かつビール/サイダー/ミードに該当する商品を判定
3. data/products.json に存在しないIDのみ、body_htmlから構造化データを直接抽出して追記
4. products.json に追記(既存データは一切削除しない)
5. 変更があればコミット用に差分をログ出力

2026-09: コレクションページのHTMLを正規表現でスクレイピングする旧方式(2026-08導入)を
全面刷新。旧方式は一覧ページに埋め込まれた無関係な文字列(画像ファイル名の一部やJSデータ内の
文字列)を商品ハンドルと誤認識し、実在しないURLを大量に「新商品候補」として検出する不具合が
あった(2026-09-15の実行ログで確認: UUID文字列や既存商品名の断片を誤ってハンドル扱い)。

products.jsonフィードは商品ページと全く同じ構造化スペック(body_html内の<li>ABV:...</li>等)を
含んでおり、かつ在庫状況(variants[].available)も直接返すため、この誤検出が原理的に起こらない。
個々の商品ページを再取得する必要も無くなった(一覧取得の時点で全項目が揃っている)。

これに伴いANTHROPIC_API_KEYは必須ではなくなった。設定されていれば、構造化スペック欄が
「ホップ:-」になっている商品について、説明文中にホップ品種名が埋もれていないかの追加チェックに
のみ使う(未設定でも収集・追記の本体機能は問題なく動作する)。
"""

import html
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    import anthropic
except ImportError:
    anthropic = None

ROOT = Path(__file__).parent.parent
DATA_PATH = ROOT / "data" / "products.json"
SOURCES_PATH = Path(__file__).parent / "update_sources.json"
HOPS_TAB_JS_PATH = Path(__file__).parent / "hops_tab.js"
USER_AGENT = "Mozilla/5.0 (compatible; HopTrackerBot/1.0; +https://github.com/)"

CLAUDE_MODEL = "claude-sonnet-4-6"
REQUEST_DELAY = 1.2  # seconds between requests - be polite to small retail sites, do not lower this

# Antenna Americaの商品でビール/サイダー/ミード以外(グッズ・チーズ・食品・酒類以外)を除外
ANTENNA_EXCLUDE_VENDORS = {"Merchandise", "Cheese", "Food&sauce", "Food", "Liquor", "Mix", "Pickles"}
ANTENNA_EXCLUDE_TAGS = {"RTD", "Non Alcohol", "Food", "Food & Sauces"}
# Southboundはproduct_typeがそのままカテゴリ(Beer/Cider/Mead/Accessories/Apparel/Set)
SOUTHBOUND_INCLUDE_TYPES = {"Beer", "Cider", "Mead"}

# 既知のブリュワリー名の表記ゆれ正規化(README_MIGRATION.md「更新ルール」より)。
# キーは小文字・空白除去したゆれ表記、値はデータセットで使う正式表記。
# 新しいゆれを見つけたらここに追記する。
BREWERY_ALIASES = {
    "laaleworks": "LA Ale Works",
    "l.a.aleworks": "LA Ale Works",
    "harlandbrewing": "Harland",
    "harlandbrewingco": "Harland",
    "harlandbrewingcompany": "Harland",
    "revision": "Revision Brewing",
    "revisionbrewingcompany": "Revision Brewing",
    "revisionbrewery": "Revision Brewing",
    "boneyard": "Boneyard Beer",
    "hiwire": "Hi-Wire Brewing",
    "paperback": "Paperback Brewing",
    "stone": "Stone Brewing",
}

# ホップ名の表記ゆれ・タイプミス・商標記号・略記の正規化(過去のデータ補完作業で判明したもの)。
# 新しいゆれを見つけたらここに追記する。
HOP_NAME_FIXES = {
    "East Kent Goldings": "East Kent Golding",
    "Golding": "East Kent Golding",
    "Tettnang": "Tettnanger",
    "NUGGET": "Nugget",
    "WILLAMETTE": "Willamette",
    "Nelson": "Nelson Sauvin",
    "Southern Cross": "Southern Cross (NZ Hops)",
    "Wakatu": "Wakatu (NZ Hops)",
    "Pacifica": "Pacifica (NZ Hops)",
    "Cristal": "Crystal",
    "Czech Saaz": "Saaz",
    "Equanot": "Ekuanot",
    "Hallertau": "Hallertauer Mittelfruher",
    "Hallertau Mittelfruh": "Hallertauer Mittelfruher",
    "Crush": "Krush",  # 実在するホップ品種名では無く、Krush(HBC 586)の誤記とほぼ断定できる
    "HBC 586": "Krush",
    "Mosic": "Mosaic",  # Antenna America側の表記ミスを確認済み
}


def normalize_brewery(name: str) -> str:
    key = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    return BREWERY_ALIASES.get(key, name)


def normalize_hop(name: str) -> str:
    name = name.replace("®", "").replace("™", "").strip()
    return HOP_NAME_FIXES.get(name, name)


def split_hops(raw: str) -> list[str]:
    """ホップ欄の区切り文字は「, 」の他に「、」「and」「&」「・(bullet)」があり得る。"""
    if raw.strip() in ("", "-"):
        return []
    raw = raw.replace("&amp;", "&")
    parts = re.split(r",|、|\s+and\s+|&|•", raw)
    return [normalize_hop(p.strip()) for p in parts if p.strip() and normalize_hop(p.strip())]


def strip_tags(t: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t).strip()


def fetch_url(url: str, timeout: int = 20) -> str:
    """Fetch a URL's content as text."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="ignore")
    except (HTTPError, URLError) as e:
        print(f"  [warn] failed to fetch {url}: {e}", file=sys.stderr)
        return ""


def fetch_catalog(base_url: str) -> list[dict]:
    """サイトの公開Shopify products.json フィードを全ページ取得する(在庫問わず全件)。"""
    products: list[dict] = []
    page = 1
    while True:
        url = f"{base_url}/products.json?limit=250&page={page}"
        raw = fetch_url(url)
        time.sleep(REQUEST_DELAY)
        if not raw:
            break
        try:
            batch = json.loads(raw).get("products", [])
        except json.JSONDecodeError:
            print(f"  [warn] could not parse JSON from {url}", file=sys.stderr)
            break
        if not batch:
            break
        products.extend(batch)
        if len(batch) < 250:
            break
        page += 1
    return products


def in_stock(p: dict) -> bool:
    return any(v.get("available") for v in p.get("variants", []))


def antenna_spec_fields(body_html: str) -> dict:
    """<li>ラベル：値</li> 形式のスペック欄(ABV/ホップ/ブリュワリー/スタイル等)を辞書化する。"""
    fields = {}
    for li in re.findall(r"<li>(.*?)</li>", body_html, re.S):
        line = strip_tags(li)
        m = re.match(r"^([^：:]+)[：:]\s*(.*)$", line)
        if m:
            fields[m.group(1).strip()] = m.group(2).strip()
    return fields


def parse_antenna_product(p: dict, source_key: str, base_url: str) -> dict:
    body = p.get("body_html", "")
    fields = antenna_spec_fields(body)

    brewery = normalize_brewery(fields.get("ブリュワリー") or p.get("product_type") or "")
    style = fields.get("スタイル") or p.get("vendor") or ""
    abv = fields.get("ABV") or "-"
    hops = split_hops(fields.get("ホップ") or "")

    # 商品名: タイトルから "/日本語名" と "(NNNml)" とブリュワリー名の重複プレフィックスを除去
    title = p["title"]
    name = title.split(" / ")[0].strip()
    name = re.sub(r"\s*\(\d+\s*ml\).*$", "", name).strip()
    if brewery and name.startswith(brewery):
        name = name[len(brewery):].strip()
    elif p.get("product_type") and name.startswith(p["product_type"]):
        name = name[len(p["product_type"]):].strip()

    # 説明文: <ul>スペック欄より前のマーケティング文(既に日本語)をそのまま使う
    desc_html = re.split(r"<ul>", body)[0]
    desc_html = re.sub(r"<h2[^>]*>.*?</h2>", "", desc_html, flags=re.S)
    description = strip_tags(desc_html).replace("\n", "").strip()

    image = ""
    if p.get("images"):
        src = re.sub(r"\?.*$", "", p["images"][0]["src"])
        image = src + "?width=400"

    return {
        "id": p["handle"],
        "name": name,
        "brewery": brewery,
        "style": style,
        "abv": abv,
        "hops": hops,
        "url": f"{base_url}/products/{p['handle']}",
        "image": image,
        "description": description,
        "source": source_key,
    }


def parse_southbound_product(p: dict, base_url: str, source_key: str) -> dict:
    body = p.get("body_html", "")
    paras = [strip_tags(x) for x in re.findall(r"<p>(.*?)</p>", body, re.S)]

    style, style_jp = "", ""
    abv = "-"
    hops: list[str] = []
    jp_desc_parts = []
    for i, para in enumerate(paras):
        if i == 0:
            lines = [l.strip() for l in para.split("\n") if l.strip()]
            style = lines[-1] if lines else ""
            style_jp = lines[0] if lines else ""
            continue
        m_abv = re.search(r"ABV:\s*([\d.]+%)", para)
        if m_abv:
            abv = m_abv.group(1)
        m_hops = re.search(r"Hops:\s*([^\n]+)", para)
        if m_hops:
            hops = split_hops(m_hops.group(1))
        if m_abv or m_hops or re.match(r"^(麦芽|副原料|Malt|Adjuncts|賞味期限|Best By)", para):
            continue
        non_ascii = sum(1 for ch in para if ord(ch) > 127)
        if non_ascii > len(para) * 0.2:
            jp_desc_parts.append(para)

    brewery = normalize_brewery(p.get("vendor") or "")
    # マーケティング文が無い商品(発売直後など)は、既に具体的なスタイル名(JP)を代替として使う
    description = " ".join(jp_desc_parts).strip() or style_jp

    image = ""
    if p.get("images"):
        src = re.sub(r"\?.*$", "", p["images"][0]["src"])
        image = src + "?width=400"

    return {
        "id": p["handle"],
        "name": p["title"].strip(),
        "brewery": brewery,
        "style": style,
        "abv": abv,
        "hops": hops,
        "url": f"{base_url}/products/{p['handle']}",
        "image": image,
        "description": description,
        "source": source_key,
    }


def recheck_description_for_hops(client, product: dict) -> list[str]:
    """[オプション機能] 構造化スペック欄が「-」でも、説明文中にホップ品種名が明記されている
    場合がある。ANTHROPIC_API_KEYが設定されている場合のみ実行し、失敗しても本体の収集処理には
    一切影響しない(例外はここで握りつぶす)。"""
    prompt = f"""次のクラフトビール商品の説明文に、使用ホップ品種が明記されていないか確認してください。
商品名: {product['name']} / ブリュワリー: {product['brewery']} / スタイル: {product['style']}
説明文: {product['description']}

説明文中に具体的なホップ品種名(カタカナ・英語いずれも可)が書かれていれば、英語の標準的な品種名の
JSON配列として返してください(例: ["Citra", "Mosaic"])。無ければ空配列 [] を返してください。
一般的な推測でホップ名を補完することは絶対にしないでください。出力はJSON配列のみとし、
説明やマークダウンの```は付けないでください。"""
    try:
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text").strip()
        text = re.sub(r"^```json\s*|\s*```$", "", text)
        hops = json.loads(text)
        if isinstance(hops, list):
            return [normalize_hop(h) for h in hops if isinstance(h, str) and h.strip()]
    except Exception as e:
        print(f"  [info] description hop recheck skipped for {product['id']}: {e}", file=sys.stderr)
    return []


def load_existing_data() -> dict:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict) -> None:
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_sources() -> list[dict]:
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["sources"]


def known_hop_names() -> set[str]:
    """Parse scripts/hops_tab.js's `hops` array for variety names already in the aroma chart."""
    text = HOPS_TAB_JS_PATH.read_text(encoding="utf-8")
    return set(re.findall(r'\{name:"([^"]+)"', text))


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = None
    if api_key and anthropic:
        try:
            client = anthropic.Anthropic(api_key=api_key)
        except Exception as e:
            print(f"[info] ANTHROPIC_API_KEY is set but client init failed - "
                  f"continuing without the optional description recheck: {e}", file=sys.stderr)
    else:
        print("[info] ANTHROPIC_API_KEY not set - running without the optional "
              "description-based hop recheck (core collection is unaffected).", file=sys.stderr)

    sources = load_sources()
    data = load_existing_data()
    known_ids = {p["id"] for p in data["products"]}
    known_hops = known_hop_names()

    added = []
    unknown_hops_seen: set[str] = set()

    print(f"[{date.today()}] Scanning {len(sources)} source site(s) via their products.json feed...")
    for source in sources:
        base_url = source["base_url"]
        source_key = source["source_key"]
        print(f"[{source['name']}] fetching full catalog feed...")
        catalog = fetch_catalog(base_url)
        print(f"  {len(catalog)} total products in feed.")

        for p in catalog:
            handle = p["handle"]
            if handle in known_ids:
                continue
            if not in_stock(p):
                continue

            if source_key == "antenna":
                if p.get("vendor") in ANTENNA_EXCLUDE_VENDORS:
                    continue
                if set(p.get("tags", [])) & ANTENNA_EXCLUDE_TAGS:
                    continue
                if not p.get("product_type"):
                    continue
                record = parse_antenna_product(p, source_key, base_url)
            else:
                if p.get("product_type") not in SOUTHBOUND_INCLUDE_TYPES:
                    continue
                record = parse_southbound_product(p, base_url, source_key)

            if not record.get("hops") and client:
                extra_hops = recheck_description_for_hops(client, record)
                if extra_hops:
                    record["hops"] = extra_hops

            for h in record["hops"]:
                if h not in known_hops:
                    unknown_hops_seen.add(h)

            record["added"] = str(date.today())
            data["products"].append(record)
            added.append(record)
            known_ids.add(handle)

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
