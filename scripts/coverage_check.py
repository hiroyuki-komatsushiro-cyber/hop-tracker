"""
登録漏れ・更新漏れの総チェック (scripts/coverage_check.py)

実行: python scripts/coverage_check.py [--json 出力先.json]
何も書き換えない(読み取り専用)。各収集元のライブのサイトと data/products.json、公開ページを突き合わせて報告する。
2026-11-16、ユーザー依頼「登録漏れ、更新漏れがないか総チェック」で作成。

A. 登録漏れ
  A1 [Shopify] 収集対象(在庫あり・除外条件に当たらない)なのに未登録の商品 → 次回の週次で入る(今すぐ入れるなら update_products.py)
  A2 [Shopify] 除外条件(vendor/タグ/product_type)で外れている在庫ありの商品 → ビールを誤って除外していないかの目視確認用
  A3 [Shopify] 売り切れだが最近公開された収集対象の商品 → 週次の合間に売り切れた限定品。週次は直近update_products.RECENT_SOLDOUT_DAYS日
     (既定14日)の公開分を売り切れでも登録する。それより古く、一度も登録されなかった分がここに出る
  A4 [公式サイト系] サイトに載っているのに未登録の銘柄(Vertere=全記事、WCB=WP REST APIの全銘柄。2026-11-16に過去分を全件取り込んだので0が正常)
B. 更新漏れ(判定は週次と同じ update_products.refresh_changes。ここに出る=次回の週次が自動で直す、またはreviewは人の確認が要る)
  B1 [Shopify] 登録済み商品のうち、サイトの現在の記載とスタイル・度数・ホップが食い違うもの(商品名・説明文・画像の差は仕様上更新しない)
  B2 [公式サイト系] 登録後にサイト側で更新された銘柄(Vertere=WP記事のmodifiedから再取得して比較、WCB=先頭72銘柄)
  B3 [Shopify] 現在のサイトに見つからない登録済み商品(ハンドル失効=廃盤または移転)。別ハンドルで再掲載されていないかも照合する
  B4 アロマチャートに無いホップ名
  B5 公開ページ(docs/index.html と GitHub Pages)が products.json と一致しているか
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import audit_catalog as ac  # noqa: E402
import update_products as up  # noqa: E402

ROOT = Path(__file__).parent.parent
DATA_PATH = ROOT / "data" / "products.json"
DOCS_PATH = ROOT / "docs" / "index.html"
LIVE_SITE = "https://hiroyuki-komatsushiro-cyber.github.io/hop-tracker/"
RECENT_DAYS = 45                  # A3: 「最近公開された」とみなす日数
VERTERE_IMPORT_DATE = "2026-10-16"  # Vertereの全件取り込み日。これ以降にサイト側で更新された記事を「登録後の更新」とみなす
DETAIL_LIMIT = 12                 # 各項目の詳細表示の上限


def parse_date(s: str):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        return None


def pending(stored: dict, live: dict, live_desc_hops, known: set):
    """週次の更新点検(update_products.refresh_changes)が、この登録済み商品に対して行うことを返す。変更も確認事項も無ければNone。
    判定を週次と同じ関数に任せるので、ここと週次で食い違わない(判定を2か所に書かない)"""
    changes, review = up.refresh_changes(stored, live, live_desc_hops, known)
    if not changes and not review:
        return None
    return {"id": stored["id"], "name": stored["name"][:50],
            "changes": {k: [o, n] for k, (o, n) in changes.items()}, "review": review}


def check_shopify(source: dict, products: list, report: dict, last_updated: date, known: set):
    key, base_url = source["source_key"], source["base_url"]
    catalog = up.fetch_catalog(base_url)
    if not catalog:
        # 2026-11-25: この端末のIPがCloudflareのボット確認(HTTP 403 challenge / 429)で止まり、Antenna/Southboundが取れなかった。
        # 突破しない(UA偽装・ブラウザ自動化・Cookie流用はしない)。GitHub Actionsの週次実行(data/last_run_summary.json)で代替する
        raise RuntimeError(f"{key}: live catalog is empty (HTTP 403/429 = bot protection, or the site is down). "
                           f"Do not bypass it; use the scheduled CI run's data/last_run_summary.json (gh run list) instead")
    stored = [p for p in products if p["source"] == key]
    by_handle = {}
    for rec in stored:
        for k in {up.handle_from_url(rec.get("url", "")) or rec["id"], rec["id"]}:
            by_handle.setdefault(k, []).append(rec)
    live_handles = {p["handle"] for p in catalog}

    r = {"live_total": len(catalog), "registered": len(stored), "A1": [], "A2": Counter(), "A2_titles": {}, "A3": [],
         "B1": [], "B3": [], "parse_errors": []}
    # フィードの中身(登録対象かを問わない全体): 売り切れ商品がどれだけ長くフィードに残っているか。
    # 「在庫が無くなるとWEB表示が消える」商品でも、フィード(裏)には残っているかの確認用(2026-11-26、ユーザーの指摘)
    today = date.today()
    sold = [p for p in catalog if not up.in_stock(p)]
    ages = Counter()
    for p in sold:
        d = parse_date(p.get("published_at", ""))
        n = (today - d).days if d else 99999
        ages["30日以内" if n <= 30 else "31〜90日" if n <= 90 else "91〜365日" if n <= 365 else "1年超"] += 1
    r["feed"] = {"in_stock": len(catalog) - len(sold), "sold_out": len(sold), "sold_out_by_age": dict(ages)}
    cutoff = date.today() - timedelta(days=RECENT_DAYS)
    for p in catalog:
        handle = p["handle"]
        instock = up.in_stock(p)
        ok, reason = up.shopify_scope(p, key)
        if not ok:
            if instock:
                r["A2"][reason] += 1
                r["A2_titles"].setdefault(reason, []).append(p["title"][:60])
            continue
        try:
            rec = up.parse_shopify_product(p, source)
        except Exception as e:  # 解析できない商品があると、週次はそのソース全体が失敗する。ここで見つけておく
            r["parse_errors"].append({"handle": handle, "error": f"{type(e).__name__}: {e}"})
            continue
        matches = [x for x in by_handle.get(handle, []) if up.same_product(x, rec)]
        pub = parse_date(p.get("published_at", ""))
        if not matches:
            item = {"handle": handle, "title": p["title"][:70], "published": str(pub) if pub else None,
                    "vendor": p.get("vendor"), "type": p.get("product_type"), "in_stock": instock}
            if instock or up.include_sold_out(key):  # ブルワリー自身のショップ(京都醸造)は売り切れも登録対象
                item["after_last_run"] = bool(pub and pub >= last_updated)  # 同じ日の公開は、週次の後か前か分からないので「次の週次が入れる」側に倒す
                r["A1"].append(item)
            elif pub and pub >= cutoff:
                r["A3"].append(item)
        else:
            row = pending(matches[0], rec, up.hops_from_description(up.body_full_text(p.get("body_html", "")), known), known)
            if row:
                r["B1"].append(row)
    registered_handles = {up.handle_from_url(x.get("url", "")) or x["id"] for x in stored} | {x["id"] for x in stored}
    known_ids = {x["id"] for x in products}
    for rec in stored:
        h = up.handle_from_url(rec.get("url", "")) or rec["id"]
        if h not in live_handles and rec["id"] not in live_handles:
            # 別ハンドルで同じ銘柄が再掲載されていれば、廃盤ではなく移転(週次が新商品として二重登録する一歩手前)
            moved = [x for x in ac.find_relocation_candidates(rec, catalog, known_ids) if x["handle"] not in registered_handles]
            r["B3"].append({"id": rec["id"], "name": rec["name"][:50], "relocated_to": [x["handle"] for x in moved[:3]]})
    report[key] = r


def check_vertere(source: dict, products: list, report: dict, known: set):
    key, base = source["source_key"], source["base_url"]
    stored = {p["id"]: p for p in products if p["source"] == key}
    posts, page = [], 1
    while True:
        url = (f"{base}/wp-json/wp/v2/{source['post_type']}?per_page=100&page={page}"
               f"&_fields=id,link,title,date,modified")
        raw, headers = up.fetch_url_with_headers(url)
        time.sleep(up.REQUEST_DELAY)
        if not raw:
            break
        batch = json.loads(raw)
        posts.extend(batch)
        total_pages = int(headers.get("X-WP-TotalPages", "1") or 1) if headers else 1
        if page >= total_pages or not batch:
            break
        page += 1
    if not posts:
        raise RuntimeError(f"{key}: REST list returned no posts")
    r = {"live_total": len(posts), "registered": len(stored), "A4": [], "B2": [], "refetched": 0}
    for post in posts:
        pid = f"{key}-{post['id']}"
        rec = stored.get(pid)
        if rec is None:
            r["A4"].append({"id": pid, "title": post["title"]["rendered"][:60], "date": post["date"][:10]})
            continue
        registered_at = max(rec.get("added", ""), VERTERE_IMPORT_DATE)
        if post["modified"][:10] > registered_at:
            r["refetched"] += 1
            page_html = up.fetch_url(post["link"])
            time.sleep(up.REQUEST_DELAY)
            live = up.parse_vertere_page(page_html, {"id": post["id"], "link": post["link"]}, key, source["brewery"]) if page_html else None
            if live is None:
                r["B2"].append({"id": pid, "name": rec["name"][:40], "changes": {}, "review": ["could not parse the live page"],
                                "modified": post["modified"][:10]})
                continue
            row = pending(rec, live, up.hops_from_description(live.get("description", ""), known), known)
            if row:
                row["modified"] = post["modified"][:10]
                r["B2"].append(row)
    report[key] = r


def check_wcb(source: dict, products: list, report: dict, known: set):
    key = source["source_key"]
    stored = {p["id"]: p for p in products if p["source"] == key}
    # A4(登録漏れ)は、全銘柄(WP REST API=6リクエスト。GitHubのIPからは403なのでアーカイブのHTML全ページで代替)と照合する
    dates = up.wcb_all_slugs(source)
    if not dates:
        raise RuntimeError(f"{key}: no beers listed by the REST API or the archive pages")
    items = up.wcb_list_items(source, archive=True, max_archive_pages=ac.WCB_AUDIT_ARCHIVE_PAGES)
    if not items:
        raise RuntimeError(f"{key}: list/archive returned no beers")
    r = {"live_total": len(dates), "live_window": len(items), "registered": len(stored), "A4": [], "B2": []}
    for slug, published in sorted(dates.items(), key=lambda kv: kv[1], reverse=True):
        if f"{key}-{slug}" not in stored:
            r["A4"].append({"id": f"{key}-{slug}", "title": f"{slug} ({published})" if published else slug, "date": published})
    for it in items:  # B2(更新漏れ)は先頭の窓(約半年分)の値を比べる
        rec = stored.get(f"{key}-{it['slug']}")
        if rec is None:
            continue
        live = {"abv": it["abv"], "style": it["style"], "name": it["name"], "hops": up.wcb_hops(it["hops_raw"])}
        row = pending(rec, live, None, known)  # 一覧には説明文が無いので、ホップは追記だけが対象(週次のrefresh_wcb_listと同じ)
        if row:
            r["B2"].append(row)
    report[key] = r


def check_chart(products: list, report: dict):
    known = up.known_hop_names()
    unk = {}
    for p in products:
        for h in p.get("hops", []):
            if h not in known and h not in ac.KNOWN_UNRESOLVED_HOPS:
                unk.setdefault(h, []).append(p["id"])
    report["B4"] = {h: ids[:5] for h, ids in sorted(unk.items())}


def embedded_products(html: str):
    m = re.search(r"var products = (\[.*?\]);</script>", html, re.S)
    return json.loads(m.group(1)) if m else None


def check_pages(data: dict, report: dict):
    r = {"data_last_updated": data.get("last_updated"), "data_count": len(data["products"])}
    for label, loader in (("docs_file", lambda: DOCS_PATH.read_text(encoding="utf-8")),
                          ("github_pages", lambda: urllib.request.urlopen(
                              urllib.request.Request(LIVE_SITE, headers={"User-Agent": "Mozilla/5.0 (coverage check)"}),
                              timeout=30).read().decode("utf-8"))):
        try:
            html = loader()
            emb = embedded_products(html)
            if emb is None:
                r[label] = {"error": "could not find the embedded product data"}
                continue
            ids_data = [p["id"] for p in data["products"]]
            ids_emb = [p["id"] for p in emb]
            hops_diff = sum(1 for a, b in zip(data["products"], emb) if a["id"] == b["id"] and a.get("hops") != b.get("hops"))
            m = re.search(r"最終更新:\s*([\d-]+)", html)
            r[label] = {"count": len(emb), "ids_equal": ids_emb == ids_data, "hops_differ": hops_diff,
                        "last_updated_text": m.group(1) if m else None}
        except Exception as e:
            r[label] = {"error": f"{type(e).__name__}: {e}"}
    report["B5"] = r


def fmt_pending(x: dict) -> str:
    parts = [f"{k}: {o} -> {n}" for k, (o, n) in x["changes"].items()] + [f"要確認: {why}" for why in x["review"]]
    return f"{x['id']} {x['name']}: " + " / ".join(parts)


def show(title: str, rows: list, fmt):
    print(f"\n{title}: {len(rows)}")
    for row in rows[:DETAIL_LIMIT]:
        print("   " + fmt(row))
    if len(rows) > DETAIL_LIMIT:
        print(f"   ... and {len(rows) - DETAIL_LIMIT} more")


def attention_items(report: dict, last_updated: date) -> list[str]:
    """人が見るべきもの(--strict のとき、1つでもあれば終了コード1=GitHubの失敗通知メール)。
    直前の週次より後に公開された未登録(A1・A4)は、次の週次が入れるだけなので数えない(週次の直後に走らせれば普通は0)。"""
    out = []
    last = str(last_updated)
    for key, r in report.items():
        if not isinstance(r, dict):
            continue
        if "A1" in r:  # Shopify系
            real = [x for x in r["A1"] if not x.get("after_last_run")]
            if real:
                out.append(f"{key}: A1 登録漏れ(公開が前回更新より前) {len(real)}件 例: {real[0]['title'][:40]}")
            if r["A3"]:
                out.append(f"{key}: A3 売り切れで最近公開された未登録 {len(r['A3'])}件")
            if r["B1"]:
                out.append(f"{key}: B1 サイトの記載と食い違う登録済み {len(r['B1'])}件 例: {r['B1'][0]['id']}")
            moved = [x for x in r["B3"] if x["relocated_to"]]
            if moved:
                out.append(f"{key}: B3 別ハンドルで再掲載(二重登録の疑い) {len(moved)}件 例: {moved[0]['id']}")
            if r["parse_errors"]:
                out.append(f"{key}: 解析できない商品 {len(r['parse_errors'])}件")
        elif "A4" in r:  # 公式サイト系
            real = [x for x in r["A4"] if not (x.get("date") and x["date"] >= last)]
            if real:
                out.append(f"{key}: A4 サイトにあるのに未登録 {len(real)}件 例: {real[0]['id']}")
            if r["B2"]:
                out.append(f"{key}: B2 登録後にサイトで変わった銘柄 {len(r['B2'])}件 例: {r['B2'][0]['id']}")
    if report.get("B4"):
        out.append(f"B4 アロマチャートに無いホップ名 {sorted(report['B4'])[:5]}")
    for label, b in (report.get("B5") or {}).items():
        if isinstance(b, dict) and label in ("docs_file", "github_pages"):
            if "error" in b or not b.get("ids_equal") or b.get("hops_differ"):
                out.append(f"B5 公開ページ({label})がproducts.jsonと一致しない: {b}")
    for key, why in (report.get("errors") or {}).items():
        out.append(f"点検できなかった収集元 {key}: {why[:120]}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="結果をJSONで書き出す先")
    ap.add_argument("--strict", action="store_true", help="人が見るべきものが1つでもあれば終了コード1(GitHub上の定期実行用)")
    args = ap.parse_args()
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    products = data["products"]
    last_updated = parse_date(data.get("last_updated", "")) or date.today()
    report = {"date": str(date.today()), "last_updated": str(last_updated)}
    errors = {}
    known = up.known_hop_names()
    for source in up.load_sources():
        key, stype = source["source_key"], source.get("type", "shopify")
        print(f"[{key}] checking ({stype}) ...")
        try:
            if stype == "shopify":
                check_shopify(source, products, report, last_updated, known)
            elif stype == "wp_brewlog":
                check_vertere(source, products, report, known)
            elif stype == "wcb_list":
                check_wcb(source, products, report, known)
            else:
                errors[key] = f"no coverage check for type {stype!r}"
        except Exception as e:
            errors[key] = f"{type(e).__name__}: {e}"
    check_chart(products, report)
    check_pages(data, report)
    report["errors"] = errors

    print("\n" + "=" * 70 + f"\n登録漏れ・更新漏れの総チェック {date.today()}  (products.json最終更新: {last_updated}, {len(products)}件)")
    for key, r in report.items():
        if not isinstance(r, dict) or "live_total" not in r and "live_window" not in r:
            continue
        if "A1" in r:  # Shopify
            feed = r["feed"]
            print(f"\n----- {key}: ライブ{r['live_total']}件 / 登録{r['registered']}件 -----")
            print(f"   フィードの中身: 在庫あり{feed['in_stock']}件 / 売り切れ{feed['sold_out']}件(公開からの日数別 {feed['sold_out_by_age']})"
                  f" … 売り切れ商品もフィード(裏)には残っている")
            show("A1 収集対象なのに未登録", r["A1"],
                 lambda x: f"{'[公開が前回更新の後]' if x['after_last_run'] else '[前回更新より前に公開]'} {x['published']} {x['title']} ({x['vendor']})")
            print(f"\nA2 除外条件で外れている在庫あり商品: {sum(r['A2'].values())}件  内訳: {dict(r['A2'])}")
            for reason, titles in r["A2_titles"].items():
                print(f"   [{reason}] " + " / ".join(titles[:4]) + (" ..." if len(titles) > 4 else ""))
            show(f"A3 売り切れだが最近{RECENT_DAYS}日に公開された未登録商品", r["A3"],
                 lambda x: f"{x['published']} {x['title']} ({x['vendor']})")
            show("B1 サイトの現在の記載と食い違う登録済み商品(次回の週次が直す/要確認)", r["B1"], fmt_pending)
            moved = [x for x in r["B3"] if x["relocated_to"]]
            show("B3 現在のサイトに見つからない登録済み商品(ハンドル失効=廃盤または移転)", r["B3"],
                 lambda x: f"{x['id']} {x['name']}" + (f"  -> 別ハンドルで再掲載? {x['relocated_to']}" if x["relocated_to"] else ""))
            print(f"   (うち別ハンドルで再掲載されている=二重登録の疑い: {len(moved)}件)")
            if r["parse_errors"]:
                show("!! 解析できなかった商品(週次の失敗原因になる)", r["parse_errors"], lambda x: f"{x['handle']}: {x['error']}")
        else:  # 公式サイト系
            total = r.get("live_total") or r.get("live_window")
            window = f"(うち値の比較は先頭{r['live_window']}件の窓)" if "live_total" in r and "live_window" in r else \
                ("(先頭の窓)" if "live_window" in r else "")
            print(f"\n----- {key}: サイト{total}件{window} / 登録{r['registered']}件 -----")
            show("A4 サイトにあるのに未登録", r["A4"], lambda x: f"{x['id']} {x['title']}")
            show("B2 登録後にサイト側で変わった銘柄(次回の週次が直す/要確認)", r["B2"], fmt_pending)
            if "refetched" in r:
                print(f"   (サイト側で更新された記事を再取得して比較: {r['refetched']}件)")
    print(f"\nB4 アロマチャートに無いホップ名: {len(report['B4'])}  {report['B4']}")
    print(f"B5 公開ページ: {json.dumps(report['B5'], ensure_ascii=False)}")
    if errors:
        print(f"\n!! 点検できなかった収集元: {errors}")
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"\n(詳細JSON: {args.json})")
    problems = attention_items(report, last_updated)
    print("\nRESULT: " + ("OK(人が見るべきものは無し)" if not problems else f"ATTENTION {len(problems)}件"))
    for line in problems:
        print("  - " + line)
    if args.strict and problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
