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

2026-11-16(ユーザー依頼「登録漏れ、更新漏れがないか総チェック」の結果):
- 売り切れでも直近(RECENT_SOLDOUT_DAYS日)に公開された未登録商品は登録する。週次の合間に売り切れた商品は
  在庫ありの判定だけだと永久に見えなかった(Topa Topa/The Bruery等、公開後4日で完売した予約枠9件が実例)
- 登録済み商品の「更新」を加えた(refresh_changes。方針はそこのコメント)。以前は追加だけで、登録後にサイト側で
  変わったスタイル・ABV・ホップは二度と読み直されなかった
"""

import html
import json
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    import anthropic
except ImportError:
    anthropic = None

sys.path.insert(0, str(Path(__file__).parent))
import hop_text  # noqa: E402  説明文からのホップ抽出(辞書と判定ルールはhop_text.py)
import style_class as sc  # noqa: E402  スタイルの細分類・ABVの数値化(更新の判定にも同じ分類を使う)

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
#  ※"Mix"は2026-11-16に外した。vendor="Mix"の実体はビールのミックスパック(49th State Brewing Mix Pack、
#    Trademark ミリーちゃん Mix Pack等)で、大文字の"MIX"(14件)や"set-"のセット商品は元から収集対象なのに、
#    綴りが違うだけの"Mix"だけ除外されていた(総チェックで在庫あり1件の登録漏れを発見)。
ANTENNA_EXCLUDE_VENDORS = {"Merchandise", "Cheese", "Food&sauce", "Food", "Liquor", "Pickles",
                           "Hard Seltzer", "Hard Sparkling Tea"}
ANTENNA_EXCLUDE_TAGS = {"RTD", "Non Alcohol", "Food", "Food & Sauces", "Hard Seltzer"}
_EXCLUDE_TAGS_LOWER = {t.lower() for t in ANTENNA_EXCLUDE_TAGS}
# Southboundはproduct_typeがそのままカテゴリ(Beer/Cider/Mead/Accessories/Apparel/Set)。
# "Set"(現在2件: Eclipse 2024の瓶セットとTシャツ付きセット)は、中身が個別に登録済みの銘柄かグッズなので収集しない(2026-11-16確認)
SOUTHBOUND_INCLUDE_TYPES = {"Beer", "Cider", "Mead"}

# 売り切れでも、公開から何日以内の未登録商品なら登録するか。週次は火曜朝の1回だけ在庫を見るため、
# 公開後その週のうちに売り切れた商品(限定・予約枠)は在庫ありの判定だけだと一度も見えない。
# 通常は週次1回分+余裕で14日。取りこぼしの一括補充は環境変数 HOP_RECENT_SOLDOUT_DAYS=45 のように広げて1回だけ実行する
RECENT_SOLDOUT_DAYS = int(os.environ.get("HOP_RECENT_SOLDOUT_DAYS") or 14)
# Vertereの登録済み記事を、WP側のmodified(更新日時)が何日以内なら再取得して読み直すか(HOP_WP_MODIFIED_DAYSで広げられる)
WP_MODIFIED_DAYS = int(os.environ.get("HOP_WP_MODIFIED_DAYS") or 14)
# 1回の実行で更新してよい登録済み商品の数。これを超えるのは「サイトの構造が変わって解析結果が全体にずれた」ときなので、
# 超えた分は適用せず確認(refresh_review)へ回す。大規模な一括補充は HOP_MAX_REFRESH=100 のように広げて1回だけ実行する
MAX_REFRESH_PER_RUN = int(os.environ.get("HOP_MAX_REFRESH") or 60)

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
    "Idaho7 CGX": "Idaho 7 CGX",  # Vertere Lunaria(2026-11-16)。チャートには"Idaho 7 CGX"がある
    "Nectaron2026": "Nectaron",  # Vertere Window to WCB 2026 Hazy DIPA(2026-11-25)。「Nectaron 2026」(収穫年)のスペース抜け
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
    "Orange": "",  # WCB「#fruitstories 2」(Fruited Ale)の「w/」行。果実でホップではない(2026-11-02)
    # WCB「Guava & Chill」の「w/ Guava, Apricot, Coconut」も果実・副原料でホップではない(2026-11-16)
    "Guava": "",
    "Apricot": "",
    "Coconut": "",
    # WCB「Westie Bois」の「w/」行は"Nectar"だが、同じ個別ページの本文に「Nectaronも採用」と明記(2026-10-16確認)
    "Nectar": "Nectaron",
    # 本来の綴りはStrisselspalt(アルザスのホップ)。アロマチャートの項目名は既存のStrisselspalterに合わせる
    "Strisselspalt": "Strisselspalter",
    # New Belgium Fat Tire等の"Goldings"(複数形)。既存の"Golding"→East Kent Goldingと同じ扱い(2026-11-10)
    "Goldings": "East Kent Golding",
    # Jester King Enigmatic Taxa: 日本語訳の「ブレマ」を"Brema"と起こしていたが、同じ商品の英語原文は"Belma"(2026-10-28確認)
    "Brema": "Belma",
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
    # Antenna America表記のゆれ(2026-11-16、総チェックで発見)。品種名はアロマチャートの表記に揃える
    "German Tettnang": "Tettnanger",  # Cellarmaker 10 Forty(独産Tettnang)
    "German Mittelfruh": "Hallertauer Mittelfruher",
    "German Hallertau Mittelfruh": "Hallertauer Mittelfruher",  # Hayabusa Lager(2026-11-24の週次で未知名として出た)
    "Hersbrucker": "Hersbrucker Spat",  # Oktoberfest 2026。Hersbruckerは独Hersbruck産の晩生種(Spat)のこと
    # ホップの品種名ではない記載(注記・抽出物)。「Mosaic, Simcoe, Saaz, Cascade & Varying」(The Coachman)の"Varying"は
    # 「品種は時期により変わる」の意味、"Citrulicious Hop Oil"はホップオイル(抽出物)で、品種は別に記載がある
    "Varying": "",
    "Citrulicious Hop Oil": "",
    # West Coast Brewingの過去分(2026-11-16、全540銘柄の「w/」行を調べて整理)。綴りミス・別名・改名・ホップではない記載
    "Lemon Drop": "Lemondrop",
    "Citara": "Citra",  # 「Citara, Rakau & Wakatu」。Citraの綴りミス
    "Cacade": "Cascade",
    "Garaxy": "Galaxy",
    "Saltana": "Sultana",
    "Hallerteau Mittlefruh": "Hallertauer Mittelfruher",
    "Bruce": "The Bruce",  # Freestyle Hops社のブレンドホップ「The Bruce」(Southboundの説明文: ネルソン・ソーヴィン、モツエカ、ラカウ)
    "Juniper Cashmere": "Cashmere",  # 「Cardamon and Juniper, Cashmere」のカンマ抜け(副原料のJuniperとホップのCashmere)
    "Denali": "Sultana",  # Hopsteiner 06277の旧商品名Denali(現在の品種名はSultana。HopsConnectの品種表)
    "TRI2304CR": "Cryo Pop",  # Yakima Chiefの試験ブレンド名。2021年にCryo Pop Original Blendとして発売
    "Nelson Kief": "Nelson Sauvin Kief",  # 同じ行群の「Nelson Sauvin Hop Kief」の略記
    "Nelson Sauv": "Nelson Sauvin",  # 京都醸造の「Nelson Sauv T-45」(T-45はペレットの種類。2026-11-26)
    "Modern Times Idea Machine": "",  # 別のビール(ブレンド用)の名前で、ホップではない
}

# 区切り文字が抜けて1語になっている記載(Vertereの入力ミス)を、複数のホップに展開する
HOP_TOKEN_EXPANSIONS = {
    "CitraNelson Sauvin": ["Citra", "Nelson Sauvin"],
    "BelmaEl Dorado": ["Belma", "El Dorado"],
    "Simcoe Cascade": ["Simcoe", "Cascade"],
    "Citra LP Citra": ["Citra Lupomax", "Citra"],
    # El Segundo Hop Tankerのスペック欄「Citra, Nelson Simcoe」。同じ商品の説明文は「Nelson Sauvin, Citra, Simcoe, Chinook」(2026-11-16確認)
    "Nelson Simcoe": ["Nelson Sauvin", "Simcoe"],
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
        if not part or re.fullmatch(r"[-–—ー.・\s]+", part):  # 空や「-」だけの断片はホップ名ではない
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


def fetch_url_retry(url: str, tries: int = 3, delay: float = 3.0) -> str:
    """個別ページのように「取れなくても収集全体は止めない」ページ用。読み取りタイムアウト(fetch_urlが拾わない例外)も含め、
    失敗したら間隔を空けて再試行し、それでも取れなければ空文字を返す。カタログのように「欠けたら困る」取得には使わない
    (黙って欠けると、サイトの障害が「在庫なし」に見えてしまうため)。"""
    for i in range(tries):
        try:
            text = fetch_url(url)
        except OSError as e:
            print(f"  [warn] {url}: {type(e).__name__}: {e}", file=sys.stderr)
            text = ""
        if text:
            return text
        if i + 1 < tries:
            time.sleep(delay)
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


_SOURCE_CFG: dict = {}


def source_cfg(source_key: str) -> dict:
    """update_sources.json のソース定義(source_keyで引く)。scope/parser/added_from等の設定を読むのに使う。"""
    if not _SOURCE_CFG:
        _SOURCE_CFG.update({s.get("source_key"): s for s in load_sources()})
    return _SOURCE_CFG.get(source_key) or {}


def include_sold_out(source_key: str) -> bool:
    """売り切れでも収集対象にするソースか(ブルワリー自身のオンラインショップ=ラインナップが目的)。update_sources.jsonのscope.include_sold_out"""
    return bool((source_cfg(source_key).get("scope") or {}).get("include_sold_out"))


def shopify_scope(p: dict, source_key: str) -> tuple[bool, str]:
    """Shopify系ソースの商品が収集対象か。(対象か, 対象外の理由)を返す。在庫の有無は in_stock() で別に見る。
    週次の収集(main)と、登録漏れの点検(coverage_check.py)で同じ判定を使うため、ここ1か所にだけ書く。
    update_sources.json に scope があるソース(京都醸造等)は、その設定(include_types/exclude_tags/exclude_title_regex)で判定する。"""
    cfg = source_cfg(source_key).get("scope")
    if cfg:
        types = cfg.get("include_types")
        if types and p.get("product_type") not in types:
            return False, f"product_type={p.get('product_type')}"
        excluded = {t.lower() for t in cfg.get("exclude_tags", [])} & {t.lower() for t in p.get("tags", [])}
        if excluded:
            return False, f"tag={sorted(excluded)[0]}"
        rx = cfg.get("exclude_title_regex")
        if rx and re.search(rx, p.get("title", ""), re.I):
            return False, "title looks like a set/pack"
        return True, ""
    if source_key == "antenna":
        if p.get("vendor") in ANTENNA_EXCLUDE_VENDORS:
            return False, f"vendor={p.get('vendor')}"
        excluded_tags = {t.lower() for t in p.get("tags", [])} & _EXCLUDE_TAGS_LOWER
        if excluded_tags:
            return False, f"tag={sorted(excluded_tags)[0]}"
        if not p.get("product_type"):
            return False, "product_type empty"
        return True, ""
    if p.get("product_type") not in SOUTHBOUND_INCLUDE_TYPES:
        return False, f"product_type={p.get('product_type')}"
    return True, ""


def recently_published(p: dict, days=None) -> bool:
    """商品の公開日(published_at)が直近days日以内か(省略時はRECENT_SOLDOUT_DAYS)。
    売り切れでも直近に公開された未登録商品を登録するための判定。"""
    days = RECENT_SOLDOUT_DAYS if days is None else days
    if days <= 0:
        return False
    try:
        pub = date.fromisoformat((p.get("published_at") or "")[:10])
    except ValueError:
        return False
    return (date.today() - pub).days <= days


# ---------------------------------------------------------------------------
# 登録済み商品の更新(2026-11-16導入)。
# 以前の週次は「未登録の新商品を足す」だけで、登録後にサイト側で変わった事実(スタイル・ABV・ホップ)は
# 二度と読み直されなかった。総チェックで、保存値がサイトの現在の記載と食い違う商品が多数見つかった
# (Sierra Nevada Rad Little Thingのホップ、Ambitious Ales Soccer Pantsの度数とスタイル、
# 古い記録の「Sour」表記のままのウィットビア等)。自動で直すのは、サイト自身の記載が根拠になる
# 機械的な変更だけにする:
#   abv   : サイトに%の数値があり、保存値と違う -> サイトの値(度数の訂正・再発売)。サイトが空なら保存値を消さない
#   style : サイトのスタイル欄が短い名詞句で、細分類(style_class)が保存値と変わる -> サイトの値。
#           言い換えだけ(同じ細分類)は触らない。説明文や販売注記が入っている欄・分類できない欄は採らない
#   hops  : refresh_hops の注釈を参照(スペック欄 > 説明文の順に根拠を取り、サイトに裏付けの無い保存値だけを置き換える)
#   name  : 触らない(ブリュワリー名の有無・「【再入荷】」等の飾りの差はノイズ)。例外は再発売
#           (細分類と度数が同時に変わる=別レシピ)で、商品名も新しい記載に合わせる
# 説明文・画像は触らない(言い換えや写真の差し替えは事実の更新ではない)。
# 適用した変更はすべて data/last_run_summary.json の refreshed に旧->新で残る(人の確認が要るものは refresh_review)。
# ---------------------------------------------------------------------------
STYLE_TEXT_MAX_LEN = 70


def hop_core(h: str) -> str:
    """供給元の括弧書きと加工品の接尾を除いた、比較用のホップ名(Citra CryoとCitraを同じ品種として比べる)"""
    h = re.sub(r"\s*\(.*?\)$", "", h)
    return re.sub(r"\s+(Cryo|CGX|Lupomax|Incognito|Spectrum|Quantum|Prysma|HyperBoost|Lupocore|Abstrax|Dynaboost|Kief)$", "", h)


def clean_style_text(s: str) -> bool:
    """ページのスタイル欄が「スタイル名」として採れる短い名詞句か。
    Southboundには、この欄に「Southbound限定の商品！お一人様1本まで。…」の販売注記が入る商品がある。"""
    s = (s or "").strip()
    return 0 < len(s) < STYLE_TEXT_MAX_LEN and not re.search(r"[。！!？?]", s) and bool(re.search(r"[A-Za-z]", s))


def refresh_hops(stored_hops: list, live_spec_hops: list, live_desc_hops, known_hops):
    """保存済みのホップを、サイトの現在の記載に合わせる案を返す: (新しいホップ または None, 人の確認が要る理由 または None)。
    - サイトの記載 = スペック欄があればそれ、無ければ説明文から読めた品種(live_desc_hops。取れない収集元はNone)
    - 保存値が空なら、サイトの記載で埋める
    - 保存値にサイトの記載に無い品種があるとき: スペック欄が根拠なら「スペック欄にも説明文にも無い保存値」がある場合だけ、
      説明文が根拠なら保存値と完全に食い違う(共通の品種が無い)場合だけ、サイトの記載に置き換える。それ以外は追記のみ。
      Sierra Nevada Rad Little ThingやRevision DIPAのように、保存値にサイトのどこにも無い品種が残っている商品は置き換わり、
      説明文には書かれているがスペック欄から漏れている品種(ユーザー指示「説明に記載があれば成分として追記する」で補ったもの)は消えない。
      説明文が取れない収集元(live_desc_hops=None)は、根拠を確かめられないので置き換えず追記のみ
    - 追加する名前がアロマチャートに無い品種は適用せず、理由を返す(注記や綴り違いを品種として入れない。新品種はチャートに足してから)"""
    if live_spec_hops:
        live, basis = list(live_spec_hops), "spec"
    elif live_desc_hops:
        live, basis = list(live_desc_hops), "description"
    else:
        return None, None
    sk, lk = {hop_core(h) for h in stored_hops}, {hop_core(h) for h in live}
    gone = [h for h in stored_hops if hop_core(h) not in lk]  # 保存値にあって、サイトの記載に無い品種
    added = list(dict.fromkeys(h for h in live if hop_core(h) not in sk))
    if not gone and not added:
        return None, None
    if not stored_hops:
        replace = True
    elif basis == "spec":
        dk = {hop_core(h) for h in (live_desc_hops or [])}
        replace = live_desc_hops is not None and any(hop_core(h) not in dk for h in gone)
    else:
        replace = not (sk & lk)
    new = list(live) if replace else list(stored_hops) + added
    unknown_added = [h for h in added if h not in known_hops]
    if unknown_added and new != list(stored_hops):
        return None, f"サイトの記載に未知の名前 {unknown_added}(保存={stored_hops}、サイト={live})"
    return new, None


def refresh_changes(stored: dict, live: dict, live_desc_hops=None, known_hops=frozenset()):
    """保存済みレコードを、サイトの現在のレコードに合わせて安全に直せる項目を返す: (changes, review)。
    changes={項目: (旧, 新)}、review=[人の確認が要る理由]。方針は上のコメントを参照。"""
    changes, review = {}, []
    sa, la = sc.parse_abv(stored.get("abv")), sc.parse_abv(live.get("abv"))
    abv_changed = la is not None and (sa is None or abs(sa - la) > 0.05)
    if abv_changed:
        changes["abv"] = (stored.get("abv"), live["abv"])

    style_changed = False
    l_style = (live.get("style") or "").strip()
    if l_style and l_style.lower() != (stored.get("style") or "").strip().lower() and clean_style_text(l_style):
        name = stored.get("name", "")
        l_sub = sc.classify_style(l_style, name)[1]
        if l_sub != sc.classify_style(stored.get("style", ""), name)[1] and l_sub != sc.FALLBACK:
            changes["style"] = (stored.get("style"), l_style)
            style_changed = True

    if style_changed and abv_changed and sa is not None and live.get("name") and live["name"] != stored.get("name"):
        changes["name"] = (stored.get("name"), live["name"])  # 再発売(別レシピ)。商品名も新しい記載に合わせる

    stored_hops = list(stored.get("hops") or [])
    new_hops, why = refresh_hops(stored_hops, list(live.get("hops") or []), live_desc_hops, known_hops)
    if new_hops is not None and new_hops != stored_hops:
        changes["hops"] = (stored_hops, new_hops)
    if why:
        review.append(why)
    return changes, review


def apply_refresh(rec: dict, changes: dict) -> None:
    for field, (_old, new) in changes.items():
        rec[field] = new


def antenna_spec_fields(body_html: str) -> dict:
    """<li>ラベル：値</li> 形式のスペック欄(ABV/ホップ/ブリュワリー/スタイル等)を辞書化する。"""
    fields = {}
    for li in re.findall(r"<li>(.*?)</li>", body_html, re.S):
        line = strip_tags(li)
        m = re.match(r"^([^：:]+)[：:]\s*(.*)$", line)
        if m:
            label, value = m.group(1).strip(), m.group(2).strip()
            if label == "ホップ":
                # 複数のビールを含むセット商品は「ホップ：」の行が銘柄ごとに並ぶ。上書きすると最後の銘柄のホップだけになる
                # (2026-10-28: Allagash 4本セットでLagerのホップしか入っていなかった)ので、全行を連結して和集合にする。
                # 「ホップ：-」(非公開の印)は実際の記載を消さず、記載の前後どちらにあっても連結しない
                # (2026-11-10: 先頭が「-」のセットで"-"がホップ名として混入した)
                prev = fields.get(label, "")
                if value in ("", "-"):
                    fields.setdefault(label, value)
                elif prev in ("", "-"):
                    fields[label] = value
                else:
                    fields[label] = prev + ", " + value
            else:
                fields[label] = value
    return fields


def parse_antenna_product(p: dict, source_key: str, base_url: str) -> dict:
    body = p.get("body_html", "")
    fields = antenna_spec_fields(body)

    brewery = normalize_brewery(fields.get("ブリュワリー") or p.get("product_type") or "")
    style = fields.get("スタイル") or p.get("vendor") or ""
    abv = fields.get("ABV") or "-"
    hops = list(dict.fromkeys(split_hops(fields.get("ホップ") or "")))  # セットで同じ品種が複数行に出ても1回にする

    # 商品名: タイトルから "/日本語名" と "(NNNml)" とブリュワリー名の重複プレフィックスを除去
    title = p["title"]
    name = title.split(" / ")[0].strip()
    # 先頭の販促タグ(【再入荷】【完売】【ACBE2026でも大注目！】、＼新宿店オープン記念…／、《…》等)は商品名ではない。
    # 英字の銘柄名だけが続くときに除く(セットは「飲み比べ○本セット」のように日本語が続くので対象外=登録済みのセット名と同じ形のまま)。
    # タグがあるとブリュワリー名の接頭辞除去も効かなくなる(2026-11-24、Monkishの「＼新宿店オープン記念…／Monkish Shinjuku…」で発生)
    tagged = re.match(r"^(?:(?:【[^】]*】|＼[^／]*／|《[^》]*》)\s*)+(?=[A-Za-z0-9])(.*)$", name)
    if tagged and not re.search(r"[぀-ヿ一-龯]", tagged.group(1)):
        name = tagged.group(1)
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
# 京都醸造(Kyoto Brewing Co.、https://kyotobrewing.com)。Shopify製のブルワリー自身のオンラインショップ。2026-11-26追加。
# products.json の本文(body_html)には、ほとんどの商品で一行の紹介文(<h4>)しか無い。ホップ・度数・スタイルは商品ページ(HTML)の
# 「スペック」タブ(metafields由来。ホップ:/スタイル:/度数:/IBU:の行)にだけあるので、未登録の商品の商品ページを1ページずつ読む
# (1.2秒間隔。初回は約135銘柄で数分、以後は新商品の分だけ)。古い商品は本文にも<div class="spec">のスペックがある。
# ブルワリーのラインナップが目的なので売り切れも対象(scope.include_sold_out)。セット・グッズ・定期便は対象外(scope)。
# ---------------------------------------------------------------------------
KYOTO_STYLE_RULES = [
    (r"サワー\s*IPA", "Sour IPA"), (r"ホワイト\s*IPA", "White IPA"), (r"ベルジャン\s*IPA|ベルギー\s*IPA", "Belgian IPA"),
    (r"コールド\s*IPA", "Cold IPA"), (r"ブラック\s*IPA", "Black IPA"), (r"ライ\s*IPA", "Rye IPA"),
    (r"(ダブル|インペリアル|トリプル)\s*IPA", "Double IPA"), (r"セッション\s*IPA", "Session IPA"),
    (r"(ヘイジー|ニューイングランド|NE)\s*IPA", "Hazy IPA"), (r"(ウェスト|ウエスト)コースト\s*IPA|西海岸\s*IPA", "West Coast IPA"),
    (r"IPA", "IPA"),
    (r"ヘイジー.*ペール", "Hazy Pale Ale"), (r"アメリカン.*ペール", "American Pale Ale"), (r"ペール", "Pale Ale"),
    (r"(ウェスト|ウエスト)コースト.*(ピルス|ラガー)|ホッピー.*(ラガー|ピルス)", "Hoppy Lager"),
    (r"メキシカン.*ラガー", "Mexican Lager"), (r"ヘレス", "Helles"), (r"ピルスナー|ピルス", "Pilsner"),
    (r"フェスト|メルツェン|メルツェン|ウィンナ|ウィーン", "Festbier"), (r"ダーク.*ラガー|シュヴァルツ", "Dark Lager"), (r"ラガー", "Lager"),
    (r"ヴァイツェン|ヴァイス|ヘフェ|白ビール|ヴァイツェン", "Hefeweizen"), (r"ケルシュ", "Kolsch"),
    (r"ヴィット|ウィット|ベルジャン.*ホワイト", "Witbier"), (r"トリペル|トリプル(?!.*IPA)", "Belgian Tripel"), (r"クアッド|クワッド", "Belgian Quad"),
    (r"ストロング|ダブベル|デュベル", "Belgian Strong Ale"), (r"ベルジャン.*ブロンド|ブロンド", "Blonde Ale"),
    (r"ベルジャン.*(シングル|ペール)|ベルジャン", "Belgian Ale"),
    (r"セゾン", "Saison"), (r"ゴーゼ", "Gose"), (r"ベルリナー", "Berliner Weisse"), (r"サワー", "Sour Ale"),
    (r"インペリアル.*スタウト", "Imperial Stout"), (r"スタウト", "Stout"), (r"ポーター", "Porter"),
    (r"ブラウン", "Brown Ale"), (r"ESB|エクストラ.*ビター|ビター", "ESB"), (r"アンバー", "Amber Ale"), (r"レッド", "Red Ale"),
    (r"ゴールデン", "Golden Ale"), (r"バーレイ|バーレー", "Barley Wine"),
]


def kyoto_style_en(text: str) -> str:
    """京都醸造の「スタイル」(日本語またはEnglish)をstyle_classが分類できる英語表記にする。英語はそのまま、
    日本語はKYOTO_STYLE_RULESで引き、当てはまらなければ原文のまま返す(後から辞書に足せるよう、勝手に捨てない)。"""
    text = (text or "").strip()
    if not text or text.isascii():
        return text
    for pattern, english in KYOTO_STYLE_RULES:
        if re.search(pattern, text, re.I):
            return english
    return text


def _kyoto_lines(html_fragment: str) -> list[str]:
    """HTML断片 -> 空行を除いた表示テキストの行リスト(script/style/svgは除く)。"""
    t = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", html_fragment or "", flags=re.S | re.I)
    t = re.sub(r"<svg\b.*?</svg>", "", t, flags=re.S | re.I)
    t = re.sub(r"</(p|li|div|h\d|dt|dd|tr|button|span)>", "\n", t, flags=re.I)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    return [ln.strip() for ln in html.unescape(re.sub(r"<[^>]+>", "", t)).splitlines() if ln.strip()]


def parse_kyoto_product(p: dict, base_url: str, source_key: str, brewery: str = "Kyoto Brewing") -> dict:
    """products.json の1商品 -> レコード(商品ページを読む前の状態)。紹介文(<h4>)と、古い商品にある本文のスペック(<div class="spec">)だけを使う。
    新しい商品のホップ・度数・スタイルは商品ページ側にだけあるので、未登録のときに parse_kyoto_page / enrich_kyoto_record で補う。"""
    body = re.sub(r"<style\b.*?</style>", "", p.get("body_html", "") or "", flags=re.S | re.I)
    h4 = re.search(r"<h4[^>]*>(.*?)</h4>", body, re.S)
    blurb = strip_tags(h4.group(1)).strip() if h4 else ""
    spec = {}
    sm = re.search(r'<div class="spec">(.*?)</div>', body, re.S)
    if sm:
        for dt, dd in re.findall(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", sm.group(1), re.S):
            spec[strip_tags(dt).strip()] = strip_tags(dd).strip()
    feel = re.search(r"<dt>【味わいの特徴】</dt>\s*<dd>(.*?)</dd>", body, re.S)
    description = " ".join(x for x in (blurb, strip_tags(feel.group(1)).strip() if feel else "") if x)
    abv = "-"
    am = re.search(r"(\d+(?:\.\d+)?)\s*%", spec.get("ABV", "") or spec.get("度数", ""))
    if am:
        abv = f"{float(am.group(1)):g}%"
    image = ""
    if p.get("images"):
        image = re.sub(r"\?.*$", "", p["images"][0]["src"]) + "?width=400"
    return {
        "id": f"{source_key}-{p['handle']}",
        "name": p["title"].strip(),
        "brewery": brewery,
        "style": kyoto_style_en(spec.get("スタイル", "")),
        "abv": abv,
        "hops": [],
        "url": f"{base_url}/products/{p['handle']}",
        "image": image,
        "description": description,
        "source": source_key,
    }


def parse_kyoto_page(page: str) -> dict:
    """商品ページのHTML -> {style, abv, hops_raw, feel, notes}。無い項目は空文字。
    - 上部の特徴ブロック(beer-features-wrapper): スタイル / 度数 / IBU
    - 「スペック」タブ(panel-specs): ラベル行(末尾が「:」)と次の行の値。ホップ:の行がホップ欄(例: "Comet, Simcoe, Dynaboost simcoe, Citra T-45")
    - 「説明」タブ(panel-description)の「味わいの特徴:」と、「ノート」タブ(panel-other)の「ブルワーの声:」(ホップ名が書かれていることが多い)"""
    t = page or ""
    feats = {}
    for label, value in re.findall(r"<div class='body-2'>(.*?)</div>\s*<span class='heading-s medium'>(.*?)</span>", t, re.S):
        feats[strip_tags(label).strip()] = strip_tags(value).strip()

    def panel(pid):
        m = re.search(rf"id='{pid}'[^>]*>(.*)", t, re.S)
        if not m:
            return []
        rest = m.group(1)
        nxt = re.search(r"id='panel-", rest)
        return _kyoto_lines(rest[: nxt.start()] if nxt else rest[:12000])

    def labeled(lines):
        """['ラベル:', '値', 'ラベル:', '値', ...] -> {ラベル: 値(複数行は連結)}。「上に戻る」(フッターの始まり)で終わる"""
        out, cur = {}, None
        for ln in lines:
            if ln == "上に戻る":
                break
            if re.fullmatch(r"[^:：]{1,20}[:：]", ln):
                cur = ln[:-1]
                out.setdefault(cur, "")
            elif cur:
                out[cur] = (out[cur] + " " + ln).strip()
        return out

    specs = labeled(panel("panel-specs"))
    desc = labeled(panel("panel-description"))
    other = labeled(panel("panel-other"))
    abv_text = specs.get("度数") or feats.get("度数") or specs.get("ABV") or ""
    am = re.search(r"(\d+(?:\.\d+)?)\s*%", abv_text)
    return {
        "style": specs.get("スタイル") or feats.get("スタイル") or "",
        "abv": f"{float(am.group(1)):g}%" if am else "",
        "hops_raw": specs.get("ホップ", ""),
        "feel": desc.get("味わいの特徴", ""),
        "notes": other.get("ブルワーの声", ""),
    }


def enrich_kyoto_record(record: dict, info: dict, known: set) -> None:
    """parse_kyoto_page の結果で、未登録の京都醸造レコードを埋める。ホップは「ホップ:」の行が根拠(wcb_hopsと同じ整形)、
    行が空なら説明・ノートに書かれた品種名から補う(ユーザー指示「説明に記載があれば成分として追記する」)。"""
    if info.get("style"):
        record["style"] = kyoto_style_en(info["style"])
    if info.get("abv"):
        record["abv"] = info["abv"]
    if info.get("feel") and info["feel"] not in record["description"]:
        record["description"] = " ".join(x for x in (record["description"], info["feel"]) if x)
    hops = wcb_hops(info.get("hops_raw", ""))
    if not hops:
        hops = hops_from_description(" ".join(x for x in (record["description"], info.get("notes", "")) if x), known)
    record["hops"] = hops


def parse_shopify_product(p: dict, source: dict) -> dict:
    """Shopify系ソースの1商品 -> レコード。解析器は source.parser(無ければsource_key): antenna / kyoto / それ以外はsouthbound形式。
    週次の収集・月次監査・総チェックで同じ振り分けを使うため、ここ1か所にだけ書く。"""
    key, base_url = source["source_key"], source["base_url"]
    parser = source.get("parser") or key
    if parser == "antenna":
        return parse_antenna_product(p, key, base_url)
    if parser == "kyoto":
        return parse_kyoto_product(p, base_url, key, source.get("brewery", "Kyoto Brewing"))
    return parse_southbound_product(p, base_url, key)

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


# --- 「w/」行の解析(2026-11-16、過去分540銘柄の全行を調べて整理) ---
# 最近の銘柄は「w/ Citra, Mosaic & Mosaic CRYO」のような素直な列挙だが、過去分には次が混ざる:
#  - 副原料(果実・香辛料・乳糖・ナッツ・コーヒー等)と、「Dry Hopped with ...」の文(それより前は副原料の列挙)
#  - 供給元・ロットの修飾: Freestyle/EG/Crosby/YCH(供給元)、YM23・PM19・KM09・25QL・X51X(ロット符号)、
#    Pikimai(NZの農場名。Riwaka/Rakauの産地)、Diesel(Haze Allianceの「Riwaka, Riwaka Diesel」=2社のRiwaka)、
#    Bliss(Freestyleが早摘み・遅摘みのNelson Sauvinを組み合わせた製品)、Lupulin(ルプリン加工品)
#  - 加工品の表記ゆれ(CRYO/Hyper Boost、語順違いのQuantum Nectaron、Quantum(El Dorado))と、全角記号(＆・ｗ/・「・」)
# ホップ名の判定はアロマチャートの名前が先で、チャートに無く副原料の語に当たるものだけを捨てる(Lemon Drop等の実在ホップを捨てないため)。
# どちらでもない名前はそのまま残り、週次の要約の hops_needing_aroma_review に出る。
WCB_TRANSLATE = str.maketrans({"＆": "&", "ｗ": "w", "Ｗ": "W", "／": "/", "，": ",", "・": ","})
WCB_LEADIN_RE = re.compile(r"(?:(?:dry|late|cold|whirlpool|kettle)[ -]?hopp?ed|dry[ -]?hopping|dry[ -]?hop|hopped)\s*(?:with|using|w/|:)?\s*", re.I)
WCB_PREFIX_RE = re.compile(r"^(?:Freestyle|EG|Crosby|YCH\d*|GR|Selected\s+\d{4}\s+Indie)\s+", re.I)
WCB_LOT_SUFFIX_RE = re.compile(r"\s+(?:[A-Z]{2}\d{2}|[A-Z]{3}\d{3}|X\d{2}X|T-?\d{2}|(?:19|20)\d{2})$")  # T-45/T90=ペレットの種類(京都醸造のホップ欄)
WCB_DESCRIPTOR_SUFFIX_RE = re.compile(r"\s+(?:Bliss(?:\s+Process)?|Diesel|Pikimai|(?:Liquid\s+)?Lupulin)$", re.I)
WCB_FORM_WORDS = "Quantum|Cryo|CGX|Kief|Lupomax|Incognito|Spectrum|Prysma|HyperBoost|Lupocore|Abstrax|Dynaboost"
WCB_FORM_FIRST_RE = re.compile(rf"^({WCB_FORM_WORDS})\s+(.+)$", re.I)
WCB_FORM_PAREN_RE = re.compile(rf"^({WCB_FORM_WORDS})\s*\((.+)\)$", re.I)
WCB_CODE_BEFORE_SUFFIX_RE = re.compile(r"\b(?:HBC|ADHA|USDA|ID|NZ|X|YCH|TRI)$", re.I)  # "HBC 1019"の数字をロット/年として削らない
WCB_ADJUNCT_RE = re.compile(
    r"\b(?:\w*berr(?:y|ies)|cherr(?:y|ies)|vanilla|coconut|cacao|cocoa|coffee|chocolate|mango|peach(?:es)?|plums?|pineapple|"
    r"guava|passion\s*fruit|\w*fruit|citrus|lemon|lime|oranges?|yuzu|grapefruit|tangerine|banana|ginger|cinnamon|nutmeg|"
    r"cloves?|anise|cardamo[nm]|honey|sugar|lactose|salt|\w*nuts?|pecans?|macadamia|almonds?|hazelnuts?|pistachio|wheat|"
    r"oats?|grapes?|skins?|pur[ée]es?|juice|zest|peel|spice|pepper|reapers?|habanero|chipotle|matcha|lavender|"
    r"elderflower|rhubarb|cucumber|watermelon|melon|figs?|raisins?|apricot|a[cç]a[ií]|agave|maple|caramel|biscuits?|"
    r"marshmallows?|candy|praline|flavou?ring|juniper|cedar|sudachi|dekopon|ao-?mikan|zakuro|kuromitsu|kinako|"
    r"pi[ñn]a|durazno|maracuy[aá]|\w*currants?|prickly\s*pear|sichuan|phantasm|clean\s*fusion|powder|tart|sweet|roasted|"
    r"toasted|raw|malted|flaked|dried|beans?|nibs?|merlot|koshu|muscat|delaware|potat\w*)\b", re.I)


def _wcb_split_tokens(seg: str) -> list[str]:
    """括弧の中の区切りは分けずに、ホップ名の列挙を1語ずつに分ける。"""
    out, depth = [], 0
    for ch in seg:
        depth += (ch == "(") - (ch == ")" and depth > 0)
        out.append("\x00" if depth and ch in ",&" else ch)
    protected = "".join(out)
    return [p.replace("\x00", ",").strip() for p in re.split(r",|、|\s+and\s+|&|•", protected) if p.strip()]


def wcb_clean_token(tok: str) -> str:
    """「w/」行の1語 -> 正規化したホップ名(ホップでない注記は空文字)。供給元・ロットの修飾は外し、加工品の表記を揃える。"""
    t = re.sub(r"\s+", " ", tok).strip(" .　")
    t = re.sub(r"^w\s*/\s*", "", t, flags=re.I)
    m = WCB_FORM_PAREN_RE.match(t)
    if m:  # 「Quantum(El Dorado)」= El Dorado Quantum
        t = f"{m.group(2).strip()} {m.group(1)}"
    t = re.sub(r"\s*\([^)]*\)?", "", t).strip()  # Nelson Sauvin(25QL) / Pink Boots Blend(構成ホップ) の括弧書き
    prev = None
    while prev != t:  # 修飾が重なる語(EG Crosby Comet、Freestyle Nelson Sauvin PM24)は外側から順に
        prev = t
        t = WCB_PREFIX_RE.sub("", t)
        t = WCB_DESCRIPTOR_SUFFIX_RE.sub("", t)
        m = WCB_LOT_SUFFIX_RE.search(t)
        if m and not WCB_CODE_BEFORE_SUFFIX_RE.search(t[:m.start()]):
            t = t[:m.start()]
    t = re.sub(r"\bIdaho7\b", "Idaho 7", t)
    t = re.sub(r"\bHBC\s*(\d+)\b", r"HBC \1", t)
    t = re.sub(r"Hyper\s+Boost", "HyperBoost", t, flags=re.I)
    m = WCB_FORM_FIRST_RE.match(t)
    if m and normalize_hop(m.group(2)) in _hop_tables()[1].values():
        # 「Quantum Nectaron」→「Nectaron Quantum」、「Dynaboost simcoe」→「Simcoe Dynaboost」(元の品種がチャートに在るときだけ。品種名の大文字小文字も揃える)
        t = f"{normalize_hop(m.group(2))} {m.group(1)}"
    # 末尾の加工品の語(CRYO/cryo等)の大文字小文字をチャートの表記(Cryo/CGX/Kief...)に揃える(チャートに無い組み合わせでも綴りが割れないように)
    t = re.sub(rf"\s+({WCB_FORM_WORDS})$", lambda mm: " " + next(w for w in WCB_FORM_WORDS.split("|") if w.lower() == mm.group(1).lower()),
               t.strip(), flags=re.I)
    return normalize_hop(t.strip())


def wcb_hops(raw: str) -> list[str]:
    """West Coast Brewingの「w/」行 -> ホップ名のリスト(出現順、重複なし)。解析ルールは上のコメントを参照。"""
    text = re.sub(r"\s+", " ", (raw or "").translate(WCB_TRANSLATE).replace("\xa0", " ")).strip()
    text = re.sub(r"^w\s*/\s*", "", text, flags=re.I)
    segments = []
    for sent in (s for s in re.split(r"\.\s+|;|\n", text) if s.strip()):
        leadins = list(WCB_LEADIN_RE.finditer(sent))
        segments.append((bool(leadins), sent[leadins[-1].end():] if leadins else sent))
    if any(has_leadin for has_leadin, _ in segments):
        segments = [s for s in segments if s[0]]  # 「Dry Hopped with」の文があれば、ホップはそれ以降だけ(前は副原料の列挙)
    chart = set(_hop_tables()[1].values())
    hops: list[str] = []
    for _, seg in segments:
        for tok in _wcb_split_tokens(seg):
            name = wcb_clean_token(tok)
            if not name or (name not in chart and WCB_ADJUNCT_RE.search(name)) or name in hops:
                continue
            hops.append(name)
    return hops


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


def wcb_rest_dates(source: dict) -> dict:
    """WP REST APIの全銘柄の公開日 {slug: 'YYYY-MM-DD'}(per_page=100で数リクエスト。2026-11-16時点で540銘柄=6リクエスト)。
    過去分の取り込みで added に使う(今日にすると全件にNEWバッジが付く)。サイト側の公開日(CMSの日付)なので、
    使い回した投稿は実際の醸造より古い日付のことがある。完全性の点検(coverage_check.py)にも使える(全銘柄のslugが取れる)。"""
    base_url, post_type = source["base_url"], source.get("post_type", "beer")
    dates, page = {}, 1
    while True:
        raw, headers = fetch_url_with_headers(
            f"{base_url}/wp-json/wp/v2/{post_type}?per_page=100&page={page}&_fields=slug,date&orderby=date&order=desc")
        time.sleep(REQUEST_DELAY)
        if not raw:
            break
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError:
            break
        for r in rows:
            dates[r["slug"]] = (r.get("date") or "")[:10]
        total_pages = int(headers.get("X-WP-TotalPages", "1") or 1) if headers else 1
        if page >= total_pages or not rows:
            break
        page += 1
    return dates


def wcb_all_slugs(source: dict) -> dict:
    """全銘柄の {slug: 公開日(読めなければ空文字)}。完全性の点検(月次監査・総チェック)用。
    WP REST API(6リクエスト・日付付き)を先に試し、読めなければアーカイブのHTML全ページ(45リクエスト・日付なし)で代替する。
    GitHubのIPからはRESTだけが403で止められる(2026-11-25に総チェックのCI実行で確認。手元のPCからは読める)ため、
    REST頼みにすると月次監査がGitHub上で止まる。"""
    dates = wcb_rest_dates(source)
    if dates:
        return dates
    print("  [note] WP REST API not readable; falling back to the archive pages (slower, no dates)", file=sys.stderr)
    items = wcb_list_items(source, archive=True, max_archive_pages=60)
    return {it["slug"]: "" for it in items}


def parse_wcb_published(page: str) -> str:
    """個別ページ(JSON-LD)の公開日 'YYYY-MM-DD'。無ければ空文字。RESTが読めないときの代替(UTC表記なので日本時間と1日ずれうる)。"""
    m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', page or "")
    return m.group(1) if m else ""


def collect_wcb_list(source: dict, known_ids: set, backfill: bool) -> list[dict]:
    """一覧から未登録のビールを見つけ、その個別ページだけ取得して説明文を補う。
    通常は /ourbeers/ の1ページのみ。アーカイブ(過去分)の取り込みは BACKFILL_SOURCES=westcoast で指定する
    (全ページ=約540銘柄。環境変数 BACKFILL_PAGES=N で読むアーカイブのページ数を絞れる。1ページ=12銘柄。
    個別ページを1.2秒間隔で取るので、全件は約15分かかる)。過去分の added はWP REST APIの公開日にする(NEWバッジの洪水を避ける。
    RESTが読めなければ個別ページのJSON-LDの公開日を使い、どちらも無い銘柄があれば失敗させる)。
    月次監査が見つけた取りこぼしの補充は BACKFILL_ONLY=<id,id,...>(audit_review.json の unregistered_items の
    id)も必ず付ける。BACKFILL_PAGES=6 だけだと、その6ページにある「登録済みの最も古い銘柄より古い」過去分まで
    取り込んでしまう(2026-11-02に4件の補充のつもりで58件入った)。"""
    key = source["source_key"]
    max_pages = int(os.environ.get("BACKFILL_PAGES") or 60)
    only = {s.strip() for s in os.environ.get("BACKFILL_ONLY", "").split(",") if s.strip()}
    items = wcb_list_items(source, archive=backfill, max_archive_pages=max_pages)
    print(f"  {len(items)} beer(s) read from the list page(s).")
    if not items:
        raise RuntimeError(f"no beers found on {source['base_url']}{source['list_path']}; "
                           f"site down or page layout changed")
    todo = [it for it in reversed(items)  # 古い順に追記(一覧は新しい順)
            if f"{key}-{it['slug']}" not in known_ids and (not only or it["slug"] in only or f"{key}-{it['slug']}" in only)]
    dates = wcb_rest_dates(source) if backfill and todo else {}
    records = []
    for n, it in enumerate(todo, 1):
        detail = fetch_url_retry(it["url"])
        time.sleep(REQUEST_DELAY)
        description = parse_wcb_description(detail) if detail else ""
        if not description:
            print(f"  [warn] no description found for {it['url']} (record added without it)", file=sys.stderr)
        # 過去分の added はCMSの公開日(REST API。読めなければ個別ページのJSON-LD=追加のリクエスト無し)。
        # どちらも無いときに「今日」で登録するとNEWバッジが付くので、そのときは取り込みを失敗させる
        published = dates.get(it["slug"]) or parse_wcb_published(detail)
        if backfill and not published:
            raise RuntimeError(f"no publication date for {it['slug']} (REST API and page both lack it); "
                               f"refusing to backfill with today's date (it would flood the list with NEW badges)")
        records.append({
            "id": f"{key}-{it['slug']}",
            "name": it["name"],
            "brewery": source["brewery"],
            "style": it["style"],
            "abv": it["abv"],
            "hops": wcb_hops(it["hops_raw"]),
            "url": it["url"],
            "image": it["image"],
            "description": description,
            "source": key,
            "added": published if backfill else str(date.today()),
        })
        if backfill and n % 25 == 0:
            print(f"  ... {n}/{len(todo)} beers fetched", flush=True)
    return records


# source.type -> 収集関数。「新しい収集先の追加」= update_sources.jsonに1件足す(構造が新しいサイトは
# ここに収集関数を足す)。週次ワークフローは update_sources.json の全ソースを順に処理するので、
# 登録すれば自動的に定期巡回の対象になる(type未登録のソースは警告して飛ばす)。
COLLECTORS = {"wp_brewlog": collect_wp_brewlog, "wcb_list": collect_wcb_list}


# 登録済み銘柄の更新(refresh_changes)用に、公式サイト系ソースの「ライブの現在の値」を返す関数。
# refresh_xxx(source, stored: そのソースの登録済みレコード) -> [ライブのレコード(idは登録済みと同じ)]。
# 無いtypeは更新点検を飛ばすだけ(収集には影響しない)。Shopify系は取得済みのカタログをそのまま使う。
def refresh_wp_brewlog(source: dict, stored: list[dict]) -> list[dict]:
    """Vertere: WP側のmodified(更新日時)が直近WP_MODIFIED_DAYS日以内の登録済み記事だけ、個別ページを読み直す。
    記事の公開後にブルワリーが直すこと(ホップの訂正等)があり、実例はAchillea(2026-10-27更新、Centennial→Cascade)。
    一覧を更新が新しい順に取るので、窓の外に出た時点で打ち切れる(小さな醸造所のサーバーへのアクセスを最小にする)。"""
    base_url, key = source["base_url"], source["source_key"]
    stored_ids = {r["id"] for r in stored}
    url = (f"{base_url}/wp-json/wp/v2/{source['post_type']}?per_page=30&orderby=modified&order=desc"
           f"&_fields=id,slug,link,title,date,modified")
    raw = fetch_url(url)
    time.sleep(REQUEST_DELAY)
    try:
        posts = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        posts = []
    if not posts:
        raise RuntimeError(f"REST list (by modified) returned no posts ({base_url}); site down or API changed")
    cutoff = date.today() - timedelta(days=WP_MODIFIED_DAYS)
    live = []
    for post in posts:
        try:
            modified = date.fromisoformat((post.get("modified") or "")[:10])
        except ValueError:
            continue
        if modified < cutoff:
            break
        if f"{key}-{post['id']}" not in stored_ids:
            continue
        page_html = fetch_url(post["link"])
        time.sleep(REQUEST_DELAY)
        record = parse_vertere_page(page_html, post, key, source["brewery"]) if page_html else None
        if record:
            live.append(record)
    return live


def refresh_wcb_list(source: dict, stored: list[dict]) -> list[dict]:
    """West Coast Brewing: /ourbeers/ の一覧(最新12銘柄)に載る登録済み銘柄の、スタイル・ABV・ホップの現在の値。
    一覧ページ1枚だけを読む(説明文は個別ページにあるので返さない=ホップの置き換えは行わず追記のみになる)。"""
    key = source["source_key"]
    stored_ids = {r["id"] for r in stored}
    live = []
    for it in wcb_list_items(source, archive=False):
        rid = f"{key}-{it['slug']}"
        if rid in stored_ids:
            live.append({"id": rid, "name": it["name"], "style": it["style"], "abv": it["abv"],
                         "hops": wcb_hops(it["hops_raw"]), "description": ""})
    return live


REFRESHERS = {"wp_brewlog": refresh_wp_brewlog, "wcb_list": refresh_wcb_list}


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
    body_html = re.sub(r"<style\b.*?</style>", "", body_html or "", flags=re.S | re.I)  # 京都醸造の説明にはCSSが入っている
    return strip_tags(re.sub(r"</(p|li|h\d|div|dt|dd)>", "\n", body_html, flags=re.I))


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

    # HOP_NAME_FIXESは随時追記されるため、追記時点より前に収集した既存商品が古い表記のまま残らないよう、
    # 毎回全商品に再正規化をかける(安全・決定的な処理のみ)。更新点検(refresh_changes)がサイトの値と比べる前に行い、
    # 表記ゆれだけの差を「サイトで変わった」と誤認しないようにする。
    renormalized = 0
    for p in data["products"]:
        old_hops = p.get("hops", [])
        if not old_hops:
            continue
        new_hops = [h for h in (normalize_hop(h) for h in old_hops) if h]
        if new_hops != old_hops:
            p["hops"] = new_hops
            renormalized += 1

    added = []
    recycled_handles: list[str] = []
    unknown_hops_seen: set[str] = set()
    hops_from_description_log: list[dict] = []  # スペック欄が空で、説明文から補ったホップ(確認用に要約へ残す)
    new_sold_out: list[str] = []  # 売り切れだが直近に公開されたため登録した商品のid
    refreshed_log: list[dict] = []  # 登録済み商品に適用した更新(旧->新)
    refresh_review_log: list[dict] = []  # 更新したいが人の確認が要るもの
    refresh_errors: dict[str, str] = {}
    parse_errors: list[dict] = []
    page_fetch_failed: list[str] = []  # 商品ページが取れず、登録を見送った商品のハンドル(次回に再試行される)
    ids_before = set(known_ids)  # 今回の追加分を更新点検の対象にしないため
    by_id = {r["id"]: r for r in data["products"]}

    def refresh_record(rec: dict, live: dict, live_desc_hops) -> None:
        changes, review = refresh_changes(rec, live, live_desc_hops, known_hops)
        if changes and len(refreshed_log) >= MAX_REFRESH_PER_RUN:
            review = review + [f"1回の更新上限({MAX_REFRESH_PER_RUN}件)を超えたため適用せず(サイト構造の変更を疑う): "
                               + ", ".join(f"{k}: {old} -> {new}" for k, (old, new) in changes.items())]
            changes = {}
        if changes:
            apply_refresh(rec, changes)
            refreshed_log.append({"id": rec["id"], "name": rec["name"], "source": rec.get("source"),
                                  "changes": {k: [old, new] for k, (old, new) in changes.items()}})
        if review:
            refresh_review_log.append({"id": rec["id"], "name": rec["name"], "source": rec.get("source"), "reasons": review})
            unknown_hops_seen.update(h for h in live.get("hops", []) if h not in known_hops)

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

                refresher = REFRESHERS.get(source_type)
                if refresher:
                    # 登録済み銘柄の更新点検。失敗しても収集(上で完了済み)は成功扱いのまま、warningとして要約に残す
                    try:
                        stored_here = [r for r in data["products"] if r.get("source") == source_key and r["id"] in ids_before]
                        for live in refresher(source, stored_here):
                            rec = by_id.get(live["id"])
                            if rec is not None:
                                live_desc = (hops_from_description(live["description"], known_hops)
                                             if live.get("description") else None)
                                refresh_record(rec, live, live_desc)
                    except Exception as e:
                        refresh_errors[source_key] = f"{type(e).__name__}: {e}"
                        print(f"[warn] {source_key}: refresh of registered items failed ({type(e).__name__}: {e}) - "
                              f"new-item collection above is unaffected", file=sys.stderr)
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
                if not shopify_scope(p, source_key)[0]:
                    continue

                try:
                    record = parse_shopify_product(p, source)
                except Exception as e:  # 売り切れ商品も読むようになったので、解析できない1商品でソース全体を止めない
                    parse_errors.append({"source": source_key, "handle": handle, "error": f"{type(e).__name__}: {e}"})
                    continue

                existing = records_by_handle.get(handle, [])
                matched = [r for r in existing if same_product(r, record)]
                if matched:
                    # 登録済み。在庫の有無を問わず、サイトの現在の記載とスタイル・ABV・ホップを突き合わせる
                    live_desc = hops_from_description(body_full_text(p.get("body_html", "")), known_hops)
                    for rec in matched:
                        refresh_record(rec, record, live_desc)
                    continue

                instock = in_stock(p)
                if not instock and not recently_published(p) and not include_sold_out(source_key):
                    continue  # 売り切れで、直近の公開でもない(=過去の廃盤・完売品)は登録しない(ブルワリー自身のショップは売り切れも対象)
                if existing:
                    # 同じハンドルを別商品の旧レコードが使っている(=ハンドル再利用)。旧レコードには
                    # 一切触れず、新商品は衝突しない別IDで追加する(urlが本来のハンドルを保持するので、
                    # 次回以降は上の判定で既知として扱われ、重複追加されない)。
                    n = 1
                    while f"{handle}-recycled{n}" in known_ids:
                        n += 1
                    record["id"] = f"{handle}-recycled{n}"
                    recycled_handles.append(handle)

                if source.get("page_parser") == "kyoto":
                    # ホップ・度数・スタイルは商品ページの「スペック」タブにある。取れなければ登録を見送り次回に再試行する
                    # (feedの紹介文だけの中途半端な記録を作らない)
                    page = fetch_url_retry(f"{base_url}/products/{handle}")
                    time.sleep(REQUEST_DELAY)
                    if not page:
                        page_fetch_failed.append(handle)
                        continue
                    enrich_kyoto_record(record, parse_kyoto_page(page), known_hops)

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

                # ブルワリー自身のショップ(added_from=published_at)は、公開日で登録する(初回の一括登録でNEWバッジが全件に付くのを避ける)
                record["added"] = ((p.get("published_at") or "")[:10]
                                   if source.get("added_from") == "published_at" and p.get("published_at") else str(date.today()))
                data["products"].append(record)
                added.append(record)
                known_ids.add(record["id"])
                records_by_handle.setdefault(handle, []).append(record)
                if not instock and not include_sold_out(source_key):
                    new_sold_out.append(record["id"])
        except Exception as e:  # 1サイトの不具合(通信エラー・サイト構造の変更)で他の収集元の更新を止めない
            key = source.get("source_key") or source.get("name", "?")
            source_errors[key] = f"{type(e).__name__}: {e}"
            print(f"[ERROR] {key}: collection failed ({type(e).__name__}: {e}) - "
                  f"the other sources are still processed", file=sys.stderr)

    data["last_updated"] = str(date.today())
    save_data(data)

    print(f"\nDone. {len(added)} new products added. Total products: {len(data['products'])}.")
    if renormalized:
        print(f"Re-normalized hop names on {renormalized} existing product(s) "
              f"(HOP_NAME_FIXES updated since they were first collected).")
    if new_sold_out:
        print(f"[note] {len(new_sold_out)} of the new product(s) were sold out but published within the last "
              f"{RECENT_SOLDOUT_DAYS} days (registered so that limited releases that sell out between weekly runs "
              f"are not missed): {', '.join(new_sold_out)}")
    if refreshed_log:
        print(f"\nRefreshed {len(refreshed_log)} registered product(s) to match the site's current listing:")
        for e in refreshed_log:
            for field, (old, new) in e["changes"].items():
                print(f"  - {e['name']} [{e['id']}] {field}: {old} -> {new}")
    if refresh_review_log:
        print(f"\n[review needed] {len(refresh_review_log)} registered product(s) differ from the site but were NOT changed automatically:")
        for e in refresh_review_log:
            print(f"  - {e['name']} [{e['id']}]: {'; '.join(e['reasons'])}")
    if parse_errors:
        print(f"\n[warn] {len(parse_errors)} product(s) could not be parsed and were skipped: "
              f"{', '.join(e['handle'] for e in parse_errors)}", file=sys.stderr)
    if page_fetch_failed:
        print(f"\n[warn] {len(page_fetch_failed)} product page(s) could not be read, so the product was not registered "
              f"(it will be retried next run): {', '.join(page_fetch_failed[:10])}", file=sys.stderr)
    if recycled_handles:
        print(f"[note] {len(recycled_handles)} new product(s) sit on a handle previously used by a "
              f"different product (Shopify recycled it); added under '<handle>-recycledN' ids: "
              f"{', '.join(recycled_handles)}")
    if added:
        print("\nNew products this run:")
        for p in added:
            print(f"  - {p['name']} ({p['brewery']}) [{p['source']}] {p['style']} / {p['abv']} - hops: {', '.join(p['hops']) or 'unknown'}")
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
            "refreshed": sum(1 for e in refreshed_log if e.get("source") == s.get("source_key")),
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
                "new_products_sold_out": new_sold_out,
                "refreshed": refreshed_log,
                "refresh_review": refresh_review_log,
                "refresh_errors": refresh_errors,
                "parse_errors": parse_errors,
                "page_fetch_failed": page_fetch_failed,
                "sources": sources_summary,
                "source_errors": source_errors,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


if __name__ == "__main__":
    main()
