"""
月次フルカタログ監査 (scripts/audit_catalog.py)

毎週のupdate_products.pyは「新商品の検出」だけを行う軽量処理。これに対し本スクリプトは
既存492件(2026-10時点)全商品を対象に、週次処理では拾えない類の不整合を点検する:

  - 商品が別IDで二重登録されていないか(ブリュワリー+商品名の近似一致)
  - 商品のURL/IDがサイト側のハンドル変更で実在しなくなっていないか
    (放置すると次回の週次実行が「新商品」と誤認して重複追加する)
  - 商品のURL/IDは実在するが、Shopify側がそのハンドルを全く別の商品に再利用していないか
    (2026-10-02の月次監査で実例を確認: 廃盤商品のハンドルが別の新商品に再利用されていた。
    ブリュワリー名が一致しない場合は同一商品と断定せず補完もスキップする)
  - 説明文中にホップ品種名が埋もれていて構造化欄(hops)に未反映のもの。辞書ベースの抽出(hop_text.py。ライブページの
    本文全体も見る)で拾えたものは hops に自動で追記し(auto_fixed.hops_from_description)、拾えなかったが
    説明文に「ホップ」の語がある最近の商品は needs_review.recent_products_hop_words_without_names に出す
  - hops[]に使われているが scripts/hops_tab.js のアロマチャートに未収録の品種名
  - Shopify以外の収集元(ブルワリー公式サイト: Vertere / West Coast Brewing など)で、サイトに載っているのに
    未登録の銘柄(週次の収集が見る範囲=最新の一覧を外れて取りこぼしたもの)。update_sources.jsonに足した
    新しい収集先も自動で対象になる(検査が未実装のtypeは sources_without_completeness_check に列挙して見逃さない)

このうち「安全・機械的に判定できるもの」(表記ゆれ再正規化、IDが現在も有効なハンドルに
一致する商品の欠落フィールド補完)はこのスクリプトが自動適用する。
それ以外(二重登録候補・ハンドル不整合候補・説明文からのホップ抽出候補・未知の品種名)は
**自動適用せず** data/audit_review.json に記録するだけに留める。理由:
いずれも「本当に同一商品か」「実在する品種名か」の判断にWeb検索や人間的判断が必要で、
誤った自動適用はデータ破損(異なる商品のデータ混同)や実在しない品種の捏造になり得るため。

data/audit_review.json は月次ワークフローでコミットされるので、レビュー待ちの項目が
チャットの流れで埋もれて消えることはない(経緯と決定記録.mdの鉄則と同じ考え方)。
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import update_products as up  # noqa: E402

ROOT = Path(__file__).parent.parent
DATA_PATH = ROOT / "data" / "products.json"
REVIEW_PATH = ROOT / "data" / "audit_review.json"

# 過去に出典を探しても見つからず、ユーザーも「分からない」と確認済みの品種名。
# 月次レビューに毎回「新規発見」のように出てこないよう除外する(2026-09-22確認)。
KNOWN_UNRESOLVED_HOPS = {"Brema", "Torpedo Hop", "X7"}
# Vertere(2026-10-16取り込み)で出てきた、品種としてチャート化しないホップ名。
# Kohia Nelson=Freestyle Hopsの植物原料入りブレンド(NelsonとRakauにNZパッションフルーツ、品種ではない)、
# Nelson Terpene/Maui Nelson Kief/Tropical Fusion=出典が見つからず製品の実体が不明
# (Maui Nelson Kiefは元々"Maui Nelson Hop Kief"表記。"Hop Kief"→"Kief"の正規化で綴りが変わった)、
# HBC 342/USDA 008/Pelre=実験品種・誤記の可能性があり香りの出典が乏しい
KNOWN_UNRESOLVED_HOPS |= {"Kohia Nelson", "Nelson Terpene", "Maui Nelson Kief", "Tropical Fusion",
                          "HBC 342", "Usda 008", "Pelre"}


# 「同一商品か」の判定ロジックは週次スクリプトと共通なので、update_products.pyの定義を使う
# (2箇所に同じロジックを書き写さない)。
handle_from_url = up.handle_from_url
word_tokens = up.word_tokens
brewery_loosely_matches = up.brewery_loosely_matches
BREWERY_STOPWORDS = up.BREWERY_STOPWORDS
STYLE_STOPWORDS = up.STYLE_STOPWORDS


def core_name_key(p: dict) -> str:
    """ブリュワリー名の重複プレフィックスと括弧書きを除いた、ゆるい比較用キー。"""
    name = re.sub(r"\(.*?\)", "", p.get("name", ""))
    brewery = p.get("brewery", "")
    if brewery and name.strip().lower().startswith(brewery.strip().lower()):
        name = name[len(brewery):]
    return re.sub(r"[^a-z0-9ぁ-んァ-ヶ一-龠]", "", name.lower())


RECENT_DAYS = 60  # 「最近追加された商品」とみなす日数(説明文からのホップの拾い漏れ確認の対象)
HOP_EMPTY_LINE_RE = re.compile(r"^(?:ホップ|hops?)\s*[:：]\s*-?\s*$", re.I)
# 品種名の列挙らしい形: 「…、(名前)ホップ」(読点の直後に1〜20字を挟んでホップ語)、または「ホップ：(名前)」
HOP_LIST_LIKE_RE = re.compile(r"[、,・]\s*[^、,・。]{1,20}(?:ホップ|hops?\b)|(?:ホップ|hops?)\s*[:：]\s*[^\s\-]", re.I)


def recently_added(p: dict) -> bool:
    try:
        return (date.today() - date.fromisoformat(p.get("added", ""))).days <= RECENT_DAYS
    except ValueError:
        return False


def hop_word_snippets(text: str, limit: int = 2) -> list[str]:
    """ホップを指す語(ホップ/hops/dry hop等)がある文。品種名を拾えなかった商品を人間/Claudeが読んで、
    辞書(hop_text.py)に無い日本語表記があれば追記するための手がかり。比較文は除く(抽出器と同じ扱い)。"""
    out = []
    for seg in up.hop_text.SPLIT_RE.split(text or ""):
        seg = seg.strip()
        if not up.hop_text.HOP_MARKER_RE.search(seg) or up.hop_text.CONTRAST_RE.search(seg):
            continue
        if seg.startswith("原材料") or HOP_EMPTY_LINE_RE.match(seg):
            continue  # 「原材料：麦芽、ホップ」「ホップ：-」は品種の手がかりにならない定型行
        if not HOP_LIST_LIKE_RE.search(seg):
            continue  # 「A、B、Cホップ」「ホップ：A, B」のような列挙の形でなければ、品種名を落としている可能性は低い
        out.append(seg[:200])
        if len(out) >= limit:
            break
    return out


def find_duplicate_candidates(products: list[dict], shopify_keys: set[str]) -> list[dict]:
    """ブリュワリー名プレフィックスを除いた商品名の完全一致 **かつ** ブリュワリー一致を候補とする。
    ブリュワリー条件が無いと「West Coast IPA」等の汎用スタイル名を共有するだけの無関係な
    別ブリュワリー商品まで大量に誤検出する(2026-10-02の監査スクリプト初版で146件の誤検出を確認)。
    ブリュワリーも一致した上で商品名が同一というのは、同じ銘柄が別バッチ/別ID/別容量で
    重複登録されている可能性が高いという意味であり、それでも「同一商品の確定」では無いため
    自動マージはせず人間/Claudeによる確認に回す。"""
    candidates = []
    by_key: dict[tuple[str, str], list[dict]] = {}
    for p in products:
        # 二重登録が起きるのは、商品ごとに別ハンドルで再掲載されるShopify系ソースだけ。
        # 公式サイト系(Vertere/WCB)は記事・ページが一意で、同名の別バッチ(Artist collaboration等)は別レシピなので対象外
        if p.get("source") not in shopify_keys:
            continue
        name_key = core_name_key(p)
        if len(name_key) < 8:
            continue
        brewery_key = re.sub(r"[^a-z0-9]", "", (p.get("brewery") or "").lower())
        if not brewery_key:
            continue
        by_key.setdefault((brewery_key, name_key), []).append(p)
    for (brewery_key, name_key), group in by_key.items():
        if len(group) < 2:
            continue
        for i, p in enumerate(group):
            for q in group[i + 1:]:
                if p["id"] != q["id"]:
                    candidates.append({"a": p["id"], "a_name": p["name"], "b": q["id"], "b_name": q["name"]})
    return candidates


def find_relocation_candidates(p: dict, catalog: list[dict], known_ids: set[str]) -> list[dict]:
    """ハンドルが消えた/別商品に再利用された商品について、同じ銘柄が新しいハンドルで
    再登録されていないかをライブカタログのタイトルから探す(提案のみ・自動適用しない)。
    2026-10-02の監査で、再利用された6件中3件(Chromatic / Emerald Bay / King Crispy)が
    別ハンドルで現存していたのを手作業の名前検索で発見したため、その手順を自動化した。
    ブリュワリー名・スタイル語を除いた固有語がすべてタイトルに含まれるものだけを候補とする。
    容量違い(355/473ml)で複数ヒットしうるので、ABV・容量の一致確認は人間/Claudeが行うこと。"""
    core = word_tokens(p.get("name"), STYLE_STOPWORDS | BREWERY_STOPWORDS) - word_tokens(p.get("brewery"))
    if not core:
        return []
    hits = []
    for raw in catalog:
        if raw["handle"] == handle_from_url(p.get("url", "")) or raw["handle"] in known_ids:
            continue
        # antennaはタイトル先頭に、southboundはvendor欄にブリュワリー名が入る
        brewery_text = f"{raw.get('title', '')} {raw.get('vendor', '')}"
        if core <= word_tokens(raw.get("title")) and brewery_loosely_matches(p.get("brewery"), brewery_text):
            hits.append({"handle": raw["handle"], "title": raw.get("title"),
                         "available": any(v.get("available") for v in raw.get("variants", []))})
    return hits


def unregistered_wp_posts(source: dict, known_ids: set) -> tuple[list[dict], str]:
    """WordPress REST系(Vertere)。全記事IDを一覧し、products.jsonに未登録のものを返す
    (全記事が収集対象なので、未登録はすべて取りこぼし)。
    週次の収集は最新30件しか見ないため、日付の古い記事が後から公開された場合や、週次が
    30件以上連続で失敗した場合の取りこぼしをここで拾う(IDの一覧だけなので数リクエストで済む)。"""
    missing, page, total = [], 1, 0
    while True:
        url = (f"{source['base_url']}/wp-json/wp/v2/{source['post_type']}?per_page=100&page={page}"
               f"&_fields=id,link,title,date")
        raw, headers = up.fetch_url_with_headers(url)
        up.time.sleep(up.REQUEST_DELAY)
        if not raw:
            break
        batch = json.loads(raw)
        total += len(batch)
        for post in batch:
            if f"{source['source_key']}-{post['id']}" not in known_ids:
                missing.append({"source": source["source_key"], "id": post["id"], "link": post["link"],
                                "title": post["title"]["rendered"], "date": post["date"][:10]})
        total_pages = int(headers.get("X-WP-TotalPages", "1") or 1) if headers else 1
        if page >= total_pages or not batch:
            break
        page += 1
    if not total:
        raise RuntimeError(f"{source['source_key']}: REST list returned no posts; cannot verify completeness")
    return missing, ""


WCB_AUDIT_ARCHIVE_PAGES = 6  # 先頭72銘柄(約半年分)。アーカイブ全体(約45ページ・500銘柄超)を毎月読む必要はない


def unregistered_wcb_items(source: dict, known_ids: set) -> tuple[list[dict], str]:
    """West Coast Brewing(wcb_list)。サイトの一覧は新しい順で、/ourbeers/ は先頭12件(=アーカイブの1ページ目と同じ)。
    週次は先頭12件だけ見て、載ったものを取り込み続ける方針なので、過去分(アーカイブの奥)が未登録なのは仕様。
    取りこぼしとして拾うのは「登録済みの最も古い銘柄より新しい位置にあるのに未登録のもの」だけ
    (週次が何週も止まった/1週間に12件超の新作が出て一覧から押し出された、がこれに当たる)。
    窓(先頭72銘柄)内に登録済みが1件も無い場合は、週次が長期間止まっているとみなして窓内の全件を出す。"""
    key = source["source_key"]
    items = up.wcb_list_items(source, archive=True, max_archive_pages=WCB_AUDIT_ARCHIVE_PAGES)
    if not items:
        raise RuntimeError(f"{key}: list/archive returned no beers; cannot verify completeness")
    registered_at = [i for i, it in enumerate(items) if f"{key}-{it['slug']}" in known_ids]
    limit = max(registered_at) if registered_at else len(items)
    missing = [{"source": key, "id": it["slug"], "link": it["url"], "title": it["name"], "date": ""}
               for i, it in enumerate(items) if i < limit and f"{key}-{it['slug']}" not in known_ids]
    return missing, (f"checked the newest {len(items)} beers on the site; older archive beers are outside "
                     f"the weekly crawl's scope (not imported)")


# source.type -> 「サイトに載っているのに未登録の銘柄」の検査。新しい収集先(COLLECTORS)を足したら、
# ここにも検査関数を足す(未登録のtypeは find_unregistered_items が sources_without_completeness_check に列挙する)
UNREGISTERED_CHECKS = {"wp_brewlog": unregistered_wp_posts, "wcb_list": unregistered_wcb_items}


def find_unregistered_items(known_ids: set) -> tuple[list[dict], list[str], dict[str, str]]:
    """Shopify以外の全収集元について、サイトにあって未登録の銘柄を返す。
    戻り値: (取りこぼし銘柄, 検査関数が未実装のソースキー, ソースごとの補足メモ)。
    検査が未実装のソースは「問題なし」ではなく「未検査」として必ず報告に出す(静かに見逃さない)。"""
    missing, unchecked, notes = [], [], {}
    for source in up.load_sources():
        source_type = source.get("type", "shopify")
        if source_type == "shopify":
            continue  # Shopify系はライブカタログと全件照合する(main側)
        check = UNREGISTERED_CHECKS.get(source_type)
        if check is None:
            unchecked.append(source["source_key"])
            continue
        found, note = check(source, known_ids)
        missing.extend(found)
        if note:
            notes[source["source_key"]] = note
    return missing, unchecked, notes


def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    products = data["products"]
    known_hops = up.known_hop_names()

    # ライブ照合の対象 = update_sources.json のShopify系ソース全部(新しいShopifyソースを足せば自動で入る)
    print(f"[{date.today()}] fetching live catalogs for full audit...")
    shopify_sources = [s for s in up.load_sources() if s.get("type", "shopify") == "shopify"]
    catalog_by_source, by_handle, base_urls = {}, {}, {}
    for s in shopify_sources:
        key = s["source_key"]
        catalog = up.fetch_catalog(s["base_url"])
        if not catalog:
            # 空のまま進めると、そのソースの全商品を「ハンドル失効」と誤判定してレビューを汚染する
            raise RuntimeError(f"{key}: live catalog is empty ({s['base_url']}); audit aborted")
        catalog_by_source[key] = catalog
        by_handle[key] = {p["handle"]: p for p in catalog}
        base_urls[key] = s["base_url"]
    print("  " + " / ".join(f"{k}: {len(c)}" for k, c in catalog_by_source.items()))
    shopify_keys = set(catalog_by_source)
    known_ids = {p["id"] for p in products}

    renormalized = []
    backfilled = []
    stale_handle_candidates = []
    handle_reassigned_candidates = []
    hops_from_description = []
    recent_hop_words_unparsed = []
    unknown_hop_names: dict[str, list[str]] = {}

    for p in products:
        old_hops = p.get("hops", [])
        if old_hops:
            new_hops = [h for h in (up.normalize_hop(h) for h in old_hops) if h]
            if new_hops != old_hops:
                renormalized.append({"id": p["id"], "before": old_hops, "after": new_hops})
                p["hops"] = new_hops

        handle = handle_from_url(p.get("url", "")) or p["id"]
        source = p.get("source")
        raw = by_handle[source].get(handle) if source in by_handle else None

        if raw is not None:
            # update_products.main() と同じ振り分け(antenna専用パーサ、それ以外のShopifyはsouthbound形式)
            reparsed = (up.parse_antenna_product(raw, source, base_urls[source])
                        if source == "antenna" else
                        up.parse_southbound_product(raw, base_urls[source], source))

            # ハンドルが実在しても、同一商品とは限らない。Shopifyは商品削除後に同じ
            # ハンドル(連番URL)を全く別の商品へ再利用することがある(2026-10-02の監査で
            # 実例を確認: 旧Pivo Hoppy Pilsのハンドルが現在はNitro Merlinを指していた)。
            # ブリュワリーも商品名も共通点が無い場合は同一商品と断定せず、補完を適用しない。
            if not up.same_product(p, reparsed):
                handle_reassigned_candidates.append({
                    "id": p["id"], "stored_name": p["name"], "stored_brewery": p.get("brewery"),
                    "handle": handle, "live_name": reparsed.get("name"), "live_brewery": reparsed.get("brewery"),
                    "relocation_candidates": find_relocation_candidates(p, catalog_by_source.get(source, []), known_ids),
                })
                continue

            changes = {}
            if not p.get("hops") and reparsed.get("hops"):
                changes["hops"] = reparsed["hops"]
            if (not p.get("abv") or p.get("abv") == "-") and reparsed.get("abv") not in (None, "", "-"):
                changes["abv"] = reparsed["abv"]
            if not p.get("url") and reparsed.get("url"):
                changes["url"] = reparsed["url"]
            if (not p.get("description") or len(p.get("description", "")) < 10) and len(reparsed.get("description", "")) >= 10:
                changes["description"] = reparsed["description"]
            if changes:
                backfilled.append({"id": p["id"], "changes": changes})
                p.update(changes)
        elif source in shopify_keys:
            # Shopify由来のレコードだけがライブのproducts.jsonと突き合わせられる。
            # 公式サイト系ソース(Vertere/WCB)は「ハンドルが見つからない=失効」の判定が成り立たない
            gaps = [k for k in ("hops", "abv", "url") if not p.get(k) or p.get(k) == "-"]
            if gaps:
                stale_handle_candidates.append({
                    "id": p["id"], "name": p["name"], "brewery": p.get("brewery"),
                    "source": source, "gaps": gaps,
                    "relocation_candidates": find_relocation_candidates(p, catalog_by_source.get(source, []), known_ids),
                })

        if not p.get("hops"):
            # スペック欄が空でも説明文に品種名があれば補う(2026-10-28のユーザー指示)。保存済みの説明文に加え、
            # Shopify系はライブページの本文全体も見る(保存用descriptionはスペック欄より後・英語段落を落としている)
            texts = [p.get("description", "") or ""]
            if raw is not None:
                texts.append(up.body_full_text(raw.get("body_html", "")))
            filled = []
            for text in texts:
                for h in up.hops_from_description(text, known_hops):
                    if h not in filled:
                        filled.append(h)
            if filled:
                p["hops"] = filled
                hops_from_description.append({"id": p["id"], "name": p["name"], "hops": filled})
            elif recently_added(p):
                snippets = [s for text in texts for s in hop_word_snippets(text)][:3]
                if snippets:
                    recent_hop_words_unparsed.append({"id": p["id"], "name": p["name"], "added": p.get("added"),
                                                      "snippets": snippets})

        for h in p.get("hops", []):
            if h not in known_hops and h not in KNOWN_UNRESOLVED_HOPS:
                unknown_hop_names.setdefault(h, []).append(p["id"])

    duplicate_candidates = find_duplicate_candidates(products, shopify_keys)
    unregistered_items, unchecked_sources, unregistered_notes = find_unregistered_items(known_ids)

    data["last_updated"] = str(date.today())
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    review = {
        "date": str(date.today()),
        "auto_fixed": {
            "renormalized_hops": renormalized,
            "backfilled_from_live_source": backfilled,
            "hops_from_description": hops_from_description,
        },
        "needs_review": {
            "duplicate_candidates": duplicate_candidates,
            "stale_handle_candidates": stale_handle_candidates,
            "handle_reassigned_candidates": handle_reassigned_candidates,
            "recent_products_hop_words_without_names": recent_hop_words_unparsed,
            "unknown_hop_names": dict(sorted(unknown_hop_names.items())),
            "unregistered_items": unregistered_items,
            "sources_without_completeness_check": unchecked_sources,
        },
        "info": {"unregistered_notes": unregistered_notes},
    }
    with open(REVIEW_PATH, "w", encoding="utf-8") as f:
        json.dump(review, f, ensure_ascii=False, indent=2)

    print(f"\nauto-fixed: {len(renormalized)} renormalized, {len(backfilled)} backfilled from live source, "
          f"{len(hops_from_description)} hop list(s) filled from the description")
    print(f"needs review (see data/audit_review.json):")
    print(f"  - {len(duplicate_candidates)} possible duplicate record(s)")
    print(f"  - {len(stale_handle_candidates)} stale-handle candidate(s) (id/url no longer resolves live)")
    print(f"  - {len(handle_reassigned_candidates)} handle-reassigned candidate(s) (handle now resolves to a different brewery)")
    print(f"  - {len(recent_hop_words_unparsed)} recent product(s) mention hops in the description but no variety was extracted")
    print(f"  - {len(unknown_hop_names)} hop name(s) not yet in hops_tab.js's aroma chart")
    print(f"  - {len(unregistered_items)} beer(s) listed on a brewery site but missing from products.json")
    if unchecked_sources:
        print(f"  - {len(unchecked_sources)} source(s) have no completeness check yet: {', '.join(unchecked_sources)}")
    for key, note in unregistered_notes.items():
        print(f"  (info) {key}: {note}")


if __name__ == "__main__":
    main()
