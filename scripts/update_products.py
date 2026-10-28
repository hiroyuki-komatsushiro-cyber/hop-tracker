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

2026-10: 「ハンドルが既知=既知商品」という判定をやめ、ブリュワリー・商品名も一致するか
(same_product)を確認するようにした。Shopifyは廃盤商品のハンドルを別商品へ再利用することがあり、
従来の判定だとその上に載った新商品を永久に取りこぼしていたため。

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

sys.path.insert(0, str(Path(__file__).parent))
import hop_text  # noqa: E402  説明文からのホップ抽出(辞書と判定ルールはhop_text.py)

ROOT = Path(__file__).parent.parent
DATA_PATH = ROOT / "data" / "products.json"
SOURCES_PATH = Path(__file__).parent / "update_sources.json"
HOPS_TAB_JS_PATH = Path(__file__).parent / "hops_tab.js"
USER_AGENT = "Mozilla/5.0 (compatible; HopTrackerBot/1.0; +https://github.com/)"

CLAUDE_MODEL = "claude-sonnet-4-6"
REQUEST_DELAY = 1.2  # seconds between requests - be polite to small retail sites, do not lower this

# Antenna Americaの商品でビール/サイダー/ミード以外(グッズ・チーズ・食品・RTD・ハードセルツァー等)を除外。
# Antenna側ではvendorがスタイル名(ビールの場合)またはカテゴリ名(それ以外)になっている。
# ハードセルツァーはvendor="Hard Seltzer"だがタグが付いていない個体もあるため、vendorとtagsの両方で判定する
# (2026-10-06: Belching Beaverのセルツァー4件が除外されずに追加された実例)。
ANTENNA_EXCLUDE_VENDORS = {"Merchandise", "Cheese", "Food&sauce", "Food", "Liquor", "Mix", "Pickles",
                           "Hard Seltzer", "Hard Sparkling Tea"}
ANTENNA_EXCLUDE_TAGS = {"RTD", "Non Alcohol", "Food", "Food & Sauces", "Hard Seltzer"}
_EXCLUDE_TAGS_LOWER = {t.lower() for t in ANTENNA_EXCLUDE_TAGS}
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
    "Cryo HBC 586": "Krush Cryo",
    "CRYO Mosaic": "Mosaic Cryo",  # Antenna America表記の語順違い(2026-10-02確認、Revision The Bird 473ml)
    "Mosic": "Mosaic",  # Antenna America側の表記ミスを確認済み
    "Melon": "Huell Melon",  # Antenna America表記は略記(2026-09-29確認、Firestone Walker Mind Haze系列)
    "Organic Helios": "Helios",  # "Organic"は栽培方法の修飾語で品種名自体はHelios(Hopsteiner)
    "Organic Adeena": "Adeena",  # 同上、品種名自体はAdeena(Latitude 46/旧ADHA)
    "Hallertau Mittelfrüh": "Hallertauer Mittelfruher",
    "Mittelfruh": "Hallertauer Mittelfruher",
    "Mandarina": "Mandarina Bavaria",  # Antenna America表記は略記(2026-10-06確認、Firestone Walker Easy Jack)
    # --- Vertere(2026-10-16)の表記。産地の修飾語・表記ミス・加工品の綴りゆれ ---
    "Styrian Bobek": "Bobek",  # スロベニア(シュタイヤー地方)産のBobek
    "Styrian Aurora": "Aurora",  # 同上、Aurora
    "US Tettnanger": "Tettnanger",  # 米国産のTettnanger(品種名は同じ)
    "NZ Cascade": "Cascade",  # NZ産Cascade(2016年からNZ Hopsが「Taiheke」名で販売。品種としてはCascade)
    "Idaho7": "Idaho 7",
    "Motueka Hop Kief": "Motueka Kief",
    "Motueka hop Kief": "Motueka Kief",
    "SImcoe Quantum": "Simcoe Quantum",  # 大文字小文字の打ち間違い
    "HQG3": "HQG 3",
    "HQG-3": "HQG 3",
    # ホップではない注記(仕込みメモ等)は空文字に対応させて除外する(split_hopsが空を捨てる)
    "--": "",
    "Reuse Hop": "",
    "(Crosby)": "",
    "XX": "",
    # 副原料・スパイスがホップ欄に混ざっている記事(Vertereの古い記事)。ホップではないので除外
    "Grapefruits peel": "",
    "Maple syrup": "",
    "Juniper berries": "",
    "Rosemary": "",
    "Lemongrass": "",
    "Lemon Peel": "",
    # West Coast Brewingの「w/」行に載る副原料(バーボンバレル熟成ビール等)。ホップではないので除外
    "Roasted Coconut": "",
    "Rum": "",
    "Vanilla Beans": "",
    # WCB「Westie Bois」の「w/」行は"Nectar"だが、同じ個別ページの本文に「Nectaronも採用」と明記(2026-10-16確認)
    "Nectar": "Nectaron",
    # 本来の綴りはStrisselspalt(アルザスのホップ)。アロマチャートの項目名は既存のStrisselspalterに合わせる
    "Strisselspalt": "Strisselspalter",
    # Vertereの古い記事の綴りミス(大文字小文字の違いだけのものは下のcanonical化で自動的に直る)
    "Centenial": "Centennial",
    "Centtenial": "Centennial",
    "simocoe": "Simcoe",
    "Eldorado": "El Dorado",
    "El Dorad0": "El Dorado",
    "EKG": "East Kent Golding",
    "Kentgoldings": "East Kent Golding",
    "Kent Golding": "East Kent Golding",
    "UK Golding": "East Kent Golding",
    "Styrian Golding": "Savinjski Golding",  # スロベニア(シュタイヤー地方)産Golding
    "Commet": "Comet",
    "Gracier": "Glacier",
    "Calista": "Callista",
    "Colombus": "Columbus",
    "Ctra": "Citra",
    "H.Saphir": "Saphir",
    "Pas Jade": "Pacific Jade",
    "Mt Hood": "Mt. Hood",
    "HBC342": "HBC 342",
    # 「Lupomax」(BarthHaasの濃縮ルプリンペレット)の略記・語順違い。LP=Lupomax
    "Lupo Citra": "Citra Lupomax",
    "LP Citra": "Citra Lupomax",
    "Citra LP": "Citra Lupomax",
    "Lupomax Citra": "Citra Lupomax",
    "LP Cascade": "Cascade Lupomax",
    "Cascade LP": "Cascade Lupomax",
    "Lupomax Mosaic": "Mosaic Lupomax",
    "Citra Incognite": "Citra Incognito",
}

# 区切り文字が抜けて1語になっている記載(Vertereの入力ミス)を、複数のホップに展開する
HOP_TOKEN_EXPANSIONS = {
    "CitraNelson Sauvin": ["Citra", "Nelson Sauvin"],
    "BelmaEl Dorado": ["Belma", "El Dorado"],
    "Simcoe Cascade": ["Simcoe", "Cascade"],
    "Citra LP Citra": ["Citra Lupomax", "Citra"],
}

_HOP_TABLES = {}


def _hop_tables():
    """表記の大文字小文字を無視して照合するための表(初回に作成)。
    fix: HOP_NAME_FIXESのキーを小文字化 / chart: アロマチャート収録名(小文字 -> 正式表記)"""
    if not _HOP_TABLES:
        _HOP_TABLES["fix"] = {k.lower(): v for k, v in HOP_NAME_FIXES.items()}
        _HOP_TABLES["chart"] = {n.lower(): n for n in known_hop_names()}
    return _HOP_TABLES["fix"], _HOP_TABLES["chart"]


def normalize_brewery(name: str) -> str:
    key = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    return BREWERY_ALIASES.get(key, name)


def normalize_hop(name: str) -> str:
    # 商標記号を除き、カーリーアポストロフィ(’)をASCII(')に揃える(Antenna表記の"Falconer’s Flight"対策。
    # アロマチャート側の名前はVeterans' Blend等と同じASCIIなので、揃えないと紐付かない)
    name = name.replace("®", "").replace("™", "").replace("’", "'").strip()
    # NZ Hopsの濃縮品「Hop Kief」はチャート側では「<品種> Kief」の表記("Riwaka Hop Kief"→"Riwaka Kief")
    name = re.sub(r"\s+Hop\s+Kief$", " Kief", name, flags=re.I)
    if name in HOP_NAME_FIXES:
        return HOP_NAME_FIXES[name]
    fix, chart = _hop_tables()
    low = name.lower()
    if low in fix:  # 別名表は大文字小文字を無視して引く(例: "lemon peel", "SImcoe")
        return fix[low]
    return chart.get(low, name)  # チャート収録名と大文字小文字だけ違うもの(例: "cascade", "EL Dorado")は正式表記に揃える


def split_hops(raw: str) -> list[str]:
    """ホップ欄の区切り文字は「, 」の他に「、」「and」「&」「・(bullet)」があり得る。"""
    if raw.strip() in ("", "-"):
        return []
    raw = raw.replace("&amp;", "&")
    out = []
    for part in re.split(r",|、|\s+and\s+|&|•", raw):
        part = part.strip()
        if not part:
            continue
        if part in HOP_TOKEN_EXPANSIONS:
            out.extend(n for n in (normalize_hop(x) for x in HOP_TOKEN_EXPANSIONS[part]) if n)
            continue
        n = normalize_hop(part)
        if n:
            out.append(n)
    return out


def handle_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1] if url else ""


# 「同一商品か」の判定。週次の新商品検出(このファイル)と月次監査(audit_catalog.py)の両方が
# 使うので、ロジックはここ1箇所にだけ置く。
BREWERY_STOPWORDS = {"brewing", "brewery", "company", "co", "the"}
STYLE_STOPWORDS = {
    "ipa", "dipa", "ale", "pils", "pilsner", "lager", "hazy", "juicy", "west", "coast",
    "imperial", "double", "pale", "stout", "porter", "sour", "wheat", "amber", "blonde",
}


def word_tokens(name, extra_stopwords=frozenset()) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (name or "").lower())
    return {w for w in words if w not in extra_stopwords}


def brewery_loosely_matches(a, b) -> bool:
    """「Brewing」「Company」等の有無やLA/Los Angelesのような略記差で誤判定しないよう、
    主要単語の共通集合があるかだけを見る(完全一致は厳しすぎることが実例で判明: 2026-10-02)。"""
    ta, tb = word_tokens(a, BREWERY_STOPWORDS), word_tokens(b, BREWERY_STOPWORDS)
    if not ta or not tb:
        return True
    return bool(ta & tb)


def same_product(stored: dict, live: dict) -> bool:
    """保存済みレコードと、ライブのフィード由来のレコードが同一商品か。
    Shopifyは廃盤商品のハンドル(連番URL)を全く別の商品へ再利用することがある(2026-10-02/06に実例:
    旧Pivo Hoppy Pilsのハンドルが別商品を指す、Ambitious Alesの旧商品のハンドルにPorch Rack
    Mexican Lagerが載る等)ため、ハンドルの一致だけでは同一商品と判定できない。
    ブリュワリーが緩く一致し、かつ(ブリュワリー名・スタイル語を除いた)商品名に共通語があれば
    同一とみなす。名前が空など判定材料が無い場合は同一扱い(誤って重複追加するより安全側)。"""
    if not brewery_loosely_matches(stored.get("brewery"), live.get("brewery")):
        return False
    brewery_words = word_tokens(stored.get("brewery")) | word_tokens(live.get("brewery"))
    stop = STYLE_STOPWORDS | brewery_words
    sn = word_tokens(stored.get("name"), stop)
    ln = word_tokens(live.get("name"), stop)
    return not sn or not ln or bool(sn & ln)


def strip_tags(t: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t).strip()


def fetch_url_with_headers(url: str, timeout: int = 20):
    """Fetch a URL; returns (text, response headers). On failure returns ("", {})."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="ignore"), resp.headers
    except (HTTPError, URLError) as e:
        print(f"  [warn] failed to fetch {url}: {e}", file=sys.stderr)
        return "", {}


def fetch_url(url: str, timeout: int = 20) -> str:
    """Fetch a URL's content as text."""
    return fetch_url_with_headers(url, timeout)[0]


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


# ---------------------------------------------------------------------------
# Vertere(バテレ、奥多摩のブルワリー公式サイト)。WordPressの「brewlog」記事が1銘柄=1記事で、
# 個別ページにStyle / Alc / Malt / Hop / Yeastが載る(ブルワリー自身の公開情報)。
# 一覧はWP REST API(認証不要の公開API)、詳細は個別ページのHTMLから取る。
# 2026-10-16追加。小規模な醸造所のサイトなので、アクセスは「新規記事の個別ページ」だけに絞る。
# ---------------------------------------------------------------------------
VERTERE_LABEL_RE = re.compile(r"^(style|alc|abv|ibu|malt|hops?|yeast|品目)\s*[:：]\s*(.*)$", re.I | re.S)


def parse_vertere_page(page: str, post: dict, source_key: str, brewery: str):
    """brewlog個別ページ(HTML) -> レコード。必須要素(タイトル)が無ければNone。"""
    m = re.search(r'<div class="splitLeft[^"]*">(.*?)</div>', page, re.S)
    if not m:
        return None
    block = m.group(1)
    h1 = re.search(r'<h1 class="brewlogTitle">(.*?)</h1>', block, re.S)
    if not h1:
        return None
    title = strip_tags(h1.group(1))
    # 「Jasius / ジャシアス」→「Jasius」。日本語名が無く末尾が「 /」だけの題(例: 仮面ライダー Collaboration Beer /)も除く
    name = re.split(r"\s+/(?:\s+|$)", title, maxsplit=1)[0].strip() or title

    style, abv, hops_raw, desc_parts = "", "-", "", []
    for para in re.findall(r"<p[^>]*>(.*?)</p>", block, re.S):
        text = strip_tags(para).replace("　", " ").strip()
        if not text or text.lower() == "back":
            continue
        lm = VERTERE_LABEL_RE.match(text)
        if lm:
            label, val = lm.group(1).lower(), lm.group(2).strip()
            if label == "style":
                style = val
            elif label in ("alc", "abv"):
                am = re.search(r"(\d+(?:\.\d+)?)\s*%", val)
                if am:
                    abv = f"{float(am.group(1)):g}%"
            elif label.startswith("hop"):
                hops_raw = val
            continue  # malt / yeast / ibu / 品目は保存しない
        desc_parts.append(text)

    # 説明文は日本語の段落を採用(英訳が併記されている記事は英語段落を除く)
    jp = [t for t in desc_parts if sum(1 for ch in t if ord(ch) > 127) > len(t) * 0.2]
    description = " ".join(jp or desc_parts).strip()

    # 古い記事の入力ゆれを除く: Hop行にYeast欄が続いている / "Hop:"が重複 / 括弧内は副原料などの注記
    hops_raw = re.split(r"\byeast\s*:", hops_raw, flags=re.I)[0]
    hops_raw = re.sub(r"\bhops?\s*:\s*", "", hops_raw, flags=re.I)
    hops_raw = re.sub(r"[（(][^）)]*[）)]", "", hops_raw)
    hops = list(dict.fromkeys(split_hops(hops_raw)))  # 仕込み工程ごとの重複記載を除く(順序は保持)

    # 画像: アイキャッチのsrcsetに300px版があればそれを使う(小さな醸造所のサーバーへの転送量を抑える)
    image = ""
    fig = re.search(r'<figure class="eyeCatch">\s*(<img[^>]*>)', page, re.S)
    if fig:
        tag = fig.group(1)
        src = re.search(r'\ssrc="([^"]+)"', tag)
        srcset = re.search(r'\ssrcset="([^"]+)"', tag)
        small = re.search(r"(\S+)\s+300w", srcset.group(1)) if srcset else None
        image = small.group(1) if small else (src.group(1) if src else "")

    return {
        "id": f"{source_key}-{post['id']}",
        "name": name,
        "brewery": brewery,
        "style": style,
        "abv": abv,
        "hops": hops,
        "url": post["link"],
        "image": image,
        "description": description,
        "source": source_key,
    }


def collect_wp_brewlog(source: dict, known_ids: set, backfill: bool) -> list[dict]:
    """WP REST APIで記事一覧(新しい順)を取り、未登録の記事だけ個別ページを取得して解析する。
    通常実行は最新30件だけ見る。全件(初回の取り込み用)は環境変数 BACKFILL_SOURCES=vertere で指定する。
    戻り値のレコードには'added'を付与済み(通常=今日、全件取り込み=記事の公開日で、
    取り込み直後に全件へNEWバッジが付くのを避ける)。"""
    base_url, key = source["base_url"], source["source_key"]
    per_page = 100 if backfill else 30
    posts, page = [], 1
    while True:
        url = (f"{base_url}/wp-json/wp/v2/{source['post_type']}?per_page={per_page}&page={page}"
               f"&_fields=id,slug,link,title,date")
        raw, headers = fetch_url_with_headers(url)
        time.sleep(REQUEST_DELAY)
        if not raw:
            break
        try:
            batch = json.loads(raw)
        except json.JSONDecodeError:
            print(f"  [warn] could not parse JSON from {url}", file=sys.stderr)
            break
        posts.extend(batch)
        total_pages = int(headers.get("X-WP-TotalPages", "1") or 1) if headers else 1
        if not backfill or page >= total_pages or not batch:
            break
        page += 1
    print(f"  {len(posts)} post(s) read from the REST list.")
    if not posts:
        # 0件は「新着なし」ではなく通信障害・API変更。黙って成功扱いにせず、このソースの失敗として報告させる
        raise RuntimeError(f"REST list returned no posts ({base_url}); site down or API changed")

    new_posts =sorted((p for p in posts if f"{key}-{p['id']}" not in known_ids), key=lambda p: p["date"])
    records = []
    for post in new_posts:
        page_html = fetch_url(post["link"])
        time.sleep(REQUEST_DELAY)
        record = parse_vertere_page(page_html, post, key, source["brewery"]) if page_html else None
        if not record:
            print(f"  [warn] could not parse {post['link']} - skipped (will retry next run)", file=sys.stderr)
            continue
        record["added"] = post["date"][:10] if backfill else str(date.today())
        records.append(record)
    return records


# ---------------------------------------------------------------------------
# West Coast Brewing(静岡のブルワリー公式サイト、WordPress)。2026-10-16追加。
# /ourbeers/ の一覧(=最新12銘柄)に、各ビールの名前・「スタイル / ABV」・「w/ホップ...」行・画像が載る。
# ホップは「w/」以降の記載が対象(ブルワリー自身の公開情報)。「w/」には副原料(Roasted Coconut, Rum等)が
# 混ざることがあるので、ホップ名の正規化(HOP_NAME_FIXES)で除く。説明文は個別ページ(/beer/<slug>/)の日本語本文。
# アーカイブ(/beer/ 、ページ送り /beer/page/N/)も同じ部品(bli_a)で構成される。
# ---------------------------------------------------------------------------
WCB_ITEM_RE = re.compile(r'<a href="([^"]+)" class="bli_a">(.*?)</a>', re.S)


def parse_wcb_list(page: str) -> list[dict]:
    """一覧/アーカイブのHTML -> アイテム(url, slug, name, style, abv, hops_raw, image)のリスト。"""
    items = []
    for m in WCB_ITEM_RE.finditer(page):
        url, body = m.group(1), m.group(2)
        ttl = re.search(r'<h3 class="bli_ttl">(.*?)</h3>', body, re.S)
        if not ttl:
            continue
        type_m = re.search(r'<p class="bli_type">(.*?)</p>', body, re.S)
        type_text = strip_tags(type_m.group(1)).strip() if type_m else ""
        sm = re.match(r"^(.*?)\s*/\s*(\d+(?:\.\d+)?)\s*%", type_text)
        style, abv = (sm.group(1).strip(), f"{float(sm.group(2)):g}%") if sm else (type_text, "-")
        w_m = re.search(r'<p class="bli_w">(.*?)</p>', body, re.S)
        hops_raw = re.sub(r"^\s*w\s*/\s*", "", strip_tags(w_m.group(1)), flags=re.I) if w_m else ""
        img = re.search(r'<img[^>]*\sdata-src="([^"]+)"', body) or re.search(r'<img[^>]*\ssrc="([^"]+)"', body)
        items.append({
            "url": url,
            "slug": handle_from_url(url),
            "name": strip_tags(ttl.group(1)).strip(),
            "style": style,
            "abv": abv,
            "hops_raw": hops_raw,
            "image": img.group(1) if img else "",
        })
    return items


def parse_wcb_description(page: str) -> str:
    """個別ページの日本語本文(beerPost_txt_ja)。"""
    m = re.search(r'<div class="beerPost_txt_ja">(.*?)</div>', page, re.S)
    if not m:
        return ""
    paras = [strip_tags(p).strip() for p in re.findall(r"<p[^>]*>(.*?)</p>", m.group(1), re.S)]
    return " ".join(p for p in paras if p)


def wcb_list_items(source: dict, archive: bool = False, max_archive_pages: int = 60) -> list[dict]:
    """/ourbeers/ の一覧のアイテムを返す。archive=Trueならアーカイブ(/beer/page/N/)も全ページ読む。"""
    pages = [source["base_url"] + source["list_path"]]
    items, seen = [], set()
    n = 0
    while True:
        if n < len(pages):
            url = pages[n]
        elif archive and n - len(pages) < max_archive_pages:
            k = n - len(pages) + 1
            url = source["base_url"] + source["archive_path"] + (f"page/{k}/" if k > 1 else "")
        else:
            break
        n += 1
        page = fetch_url(url)
        time.sleep(REQUEST_DELAY)
        found = [it for it in parse_wcb_list(page)] if page else []
        if not found and n > len(pages):
            break  # アーカイブの末尾(空ページ/404)
        for it in found:
            if it["url"] not in seen:
                seen.add(it["url"])
                items.append(it)
    return items


def collect_wcb_list(source: dict, known_ids: set, backfill: bool) -> list[dict]:
    """一覧から未登録のビールを見つけ、その個別ページだけ取得して説明文を補う。
    通常は /ourbeers/ の1ページのみ。アーカイブ(過去分)の取り込みは BACKFILL_SOURCES=westcoast で指定する
    (全ページ=約530銘柄。環境変数 BACKFILL_PAGES=N で読むアーカイブのページ数を絞れる。1ページ=12銘柄で、
    月次監査が見つけた取りこぼしの補充には BACKFILL_PAGES=6 が使える)。"""
    key = source["source_key"]
    max_pages = int(os.environ.get("BACKFILL_PAGES") or 60)
    items = wcb_list_items(source, archive=backfill, max_archive_pages=max_pages)
    print(f"  {len(items)} beer(s) read from the list page(s).")
    if not items:
        raise RuntimeError(f"no beers found on {source['base_url']}{source['list_path']}; "
                           f"site down or page layout changed")
    records = []
    for it in reversed(items):  # 古い順に追記(一覧は新しい順)
        rid = f"{key}-{it['slug']}"
        if rid in known_ids:
            continue
        detail = fetch_url(it["url"])
        time.sleep(REQUEST_DELAY)
        description = parse_wcb_description(detail) if detail else ""
        if not description:
            print(f"  [warn] no description found for {it['url']} (record added without it)", file=sys.stderr)
        records.append({
            "id": rid,
            "name": it["name"],
            "brewery": source["brewery"],
            "style": it["style"],
            "abv": it["abv"],
            "hops": list(dict.fromkeys(split_hops(it["hops_raw"]))),
            "url": it["url"],
            "image": it["image"],
            "description": description,
            "source": key,
            "added": str(date.today()),
        })
    return records


# source.type -> 収集関数。「新しい収集先の追加」= update_sources.jsonに1件足す(構造が新しいサイトは
# ここに収集関数を足す)。週次ワークフローは update_sources.json の全ソースを順に処理するので、
# 登録すれば自動的に定期巡回の対象になる(type未登録のソースは警告して飛ばす)。
COLLECTORS = {"wp_brewlog": collect_wp_brewlog, "wcb_list": collect_wcb_list}


def backfill_requested(source_key: str) -> bool:
    """全件(過去分)取り込みの指定。環境変数 BACKFILL_SOURCES にソースキーのカンマ区切り(または all)。
    旧名 VERTERE_BACKFILL=1 も受け付ける。"""
    wanted = {s.strip() for s in os.environ.get("BACKFILL_SOURCES", "").split(",") if s.strip()}
    if os.environ.get("VERTERE_BACKFILL") == "1":
        wanted.add("vertere")
    return "all" in wanted or source_key in wanted


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


def body_full_text(body_html: str) -> str:
    """Shopifyの商品説明(body_html)の全文。ブロック要素の終わりを改行にしてタグを除く。
    保存用のdescriptionはAntennaなら最初の<ul>(スペック欄)より前、Southboundなら日本語段落だけに絞っているため、
    ホップ品種名がそれ以外の部分(セット商品の個別説明、英語の説明文)に書かれていることがある。抽出にはこちらを使う。"""
    return strip_tags(re.sub(r"</(p|li|h\d|div)>", "\n", body_html or "", flags=re.I))


def hops_from_description(text: str, chart_names=None) -> list[str]:
    """説明文に品種名が書かれているホップ(アロマチャートの表記・出現順)。無ければ空リスト。
    2026-10-28、ユーザー指示「ホップ成分に記載がなくても、説明に記載があれば成分として追記する」で導入。
    誤抽出を避けるルールと検証結果は hop_text.py の冒頭と README_MIGRATION.md を参照。"""
    return hop_text.extract_hops_from_text(text, chart_names if chart_names is not None else known_hop_names(),
                                           normalize_hop)


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
    # ハンドル(商品URL末尾、無ければid) -> その名前を持つ既存レコード。
    # Shopifyは廃盤商品のハンドルを別商品へ再利用するため、「ハンドルが既知」というだけで
    # 既知商品と判定すると、再利用ハンドル上の新商品を永久に取りこぼす
    # (2026-10-06: Ambitious Alesの在庫ありのPorch Rack Mexican Lagerが未登録だった実例)。
    records_by_handle: dict[str, list[dict]] = {}
    for rec in data["products"]:
        for key in {handle_from_url(rec.get("url", "")) or rec["id"], rec["id"]}:
            records_by_handle.setdefault(key, []).append(rec)
    known_hops = known_hop_names()

    added = []
    recycled_handles: list[str] = []
    unknown_hops_seen: set[str] = set()
    hops_from_description_log: list[dict] = []  # スペック欄が空で、説明文から補ったホップ(確認用に要約へ残す)

    print(f"[{date.today()}] Scanning {len(sources)} source site(s) listed in update_sources.json...")
    source_errors: dict[str, str] = {}
    for source in sources:
        try:
            base_url = source["base_url"]
            source_key = source["source_key"]
            source_type = source.get("type", "shopify")

            if source_type != "shopify":
                collector = COLLECTORS.get(source_type)
                if collector is None:
                    # 収集関数の追加漏れ。黙って飛ばすと「登録したのに巡回されない」ままになるので失敗として報告させる
                    raise RuntimeError(f"unknown source type {source_type!r}: add a collector to COLLECTORS "
                                       f"in update_products.py")
                backfill = backfill_requested(source_key)
                print(f"[{source['name']}] collecting ({source_type}){' - FULL backfill' if backfill else ''}...")
                for record in collector(source, known_ids, backfill):
                    if not record.get("hops"):
                        desc_hops = hops_from_description(record.get("description", ""), known_hops)
                        if desc_hops:
                            record["hops"] = desc_hops
                            hops_from_description_log.append({"id": record["id"], "name": record["name"], "hops": desc_hops})
                    for h in record["hops"]:
                        if h not in known_hops:
                            unknown_hops_seen.add(h)
                    data["products"].append(record)
                    added.append(record)
                    known_ids.add(record["id"])
                continue

            print(f"[{source['name']}] fetching full catalog feed...")
            catalog = fetch_catalog(base_url)
            print(f"  {len(catalog)} total products in feed.")
            if not catalog:
                # 0件は「在庫なし」ではなく通信障害・フィード形式の変更。このソースの失敗として報告させる
                raise RuntimeError(f"products.json feed returned no products ({base_url}); "
                                   f"site down, blocked, or feed format changed")

            for p in catalog:
                handle = p["handle"]
                if not in_stock(p):
                    continue

                if source_key == "antenna":
                    if p.get("vendor") in ANTENNA_EXCLUDE_VENDORS:
                        continue
                    if {t.lower() for t in p.get("tags", [])} & _EXCLUDE_TAGS_LOWER:
                        continue
                    if not p.get("product_type"):
                        continue
                    record = parse_antenna_product(p, source_key, base_url)
                else:
                    if p.get("product_type") not in SOUTHBOUND_INCLUDE_TYPES:
                        continue
                    record = parse_southbound_product(p, base_url, source_key)

                existing = records_by_handle.get(handle, [])
                if any(same_product(r, record) for r in existing):
                    continue
                if existing:
                    # 同じハンドルを別商品の旧レコードが使っている(=ハンドル再利用)。旧レコードには
                    # 一切触れず、新商品は衝突しない別IDで追加する(urlが本来のハンドルを保持するので、
                    # 次回以降は上の判定で既知として扱われ、重複追加されない)。
                    n = 1
                    while f"{handle}-recycled{n}" in known_ids:
                        n += 1
                    record["id"] = f"{handle}-recycled{n}"
                    recycled_handles.append(handle)

                if not record.get("hops"):
                    # スペック欄が空でも説明文に品種名があれば補う(辞書ベースの決定的な抽出。ルールはhop_text.py)
                    desc_hops = hops_from_description(body_full_text(p.get("body_html", "")), known_hops)
                    if desc_hops:
                        record["hops"] = desc_hops
                        hops_from_description_log.append({"id": record["id"], "name": record["name"], "hops": desc_hops})

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
                known_ids.add(record["id"])
                records_by_handle.setdefault(handle, []).append(record)
        except Exception as e:  # 1サイトの不具合(通信エラー・サイト構造の変更)で他の収集元の更新を止めない
            key = source.get("source_key") or source.get("name", "?")
            source_errors[key] = f"{type(e).__name__}: {e}"
            print(f"[ERROR] {key}: collection failed ({type(e).__name__}: {e}) - "
                  f"the other sources are still processed", file=sys.stderr)

    # HOP_NAME_FIXESは随時追記されるため、追記時点より前に収集した既存商品が
    # 古い表記のまま残らないよう、毎回全商品に再正規化をかける(安全・決定的な処理のみ)。
    renormalized = 0
    for p in data["products"]:
        old_hops = p.get("hops", [])
        if not old_hops:
            continue
        new_hops = [h for h in (normalize_hop(h) for h in old_hops) if h]
        if new_hops != old_hops:
            p["hops"] = new_hops
            renormalized += 1

    data["last_updated"] = str(date.today())
    save_data(data)

    print(f"\nDone. {len(added)} new products added. Total products: {len(data['products'])}.")
    if renormalized:
        print(f"Re-normalized hop names on {renormalized} existing product(s) "
              f"(HOP_NAME_FIXES updated since they were first collected).")
    if recycled_handles:
        print(f"[note] {len(recycled_handles)} new product(s) sit on a handle previously used by a "
              f"different product (Shopify recycled it); added under '<handle>-recycledN' ids: "
              f"{', '.join(recycled_handles)}")
    if added:
        print("\nNew products this run:")
        for p in added:
            print(f"  - {p['name']} ({p['brewery']}) [{p['source']}] - hops: {', '.join(p['hops']) or 'unknown'}")
    if hops_from_description_log:
        print("\nHops filled from the product description (the spec field was empty):")
        for e in hops_from_description_log:
            print(f"  - {e['name']}: {', '.join(e['hops'])}")
    no_hops_new = [{"id": r["id"], "name": r["name"], "source": r["source"]} for r in added if not r.get("hops")]
    if no_hops_new:
        print(f"\n{len(no_hops_new)} new product(s) have no hop information (neither spec nor description).")
    if unknown_hops_seen:
        print("\n[review needed] hop varieties not yet in scripts/hops_tab.js's aroma chart"
              " (add sensory-profile vectors manually, do not fabricate):")
        for h in sorted(unknown_hops_seen):
            print(f"  - {h}")

    # 収集元ごとの結果。「全ソースを巡回できたか」をこのファイルだけで確認できるようにする
    sources_summary = {
        s.get("source_key") or s.get("name", "?"): {
            "status": "error" if (s.get("source_key") or s.get("name", "?")) in source_errors else "ok",
            "added": sum(1 for r in added if r.get("source") == s.get("source_key")),
        }
        for s in sources
    }
    if source_errors:
        print(f"\n[ERROR] {len(source_errors)} source(s) could not be collected: "
              f"{', '.join(f'{k} ({v})' for k, v in source_errors.items())}", file=sys.stderr)

    # Write a summary file for the workflow / notification step
    summary_path = ROOT / "data" / "last_run_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "date": str(date.today()),
                "new_products": added,
                "recycled_handles": recycled_handles,
                "hops_needing_aroma_review": sorted(unknown_hops_seen),
                "hops_from_description": hops_from_description_log,
                "new_products_without_hops": no_hops_new,
                "sources": sources_summary,
                "source_errors": source_errors,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


if __name__ == "__main__":
    main()
