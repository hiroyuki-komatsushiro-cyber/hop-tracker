"""
月次フルカタログ監査 (scripts/audit_catalog.py)

毎週のupdate_products.pyは「新商品の検出」だけを行う軽量処理。これに対し本スクリプトは
既存492件(2026-10時点)全商品を対象に、週次処理では拾えない類の不整合を点検する:

  - 商品が別IDで二重登録されていないか(ブリュワリー+商品名の近似一致)
  - 商品のURL/IDがサイト側のハンドル変更で実在しなくなっていないか
    (放置すると次回の週次実行が「新商品」と誤認して重複追加する)
  - 説明文中にホップ品種名が埋もれていて構造化欄(hops)に未反映のもの
  - hops[]に使われているが scripts/hops_tab.js のアロマチャートに未収録の品種名

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


def handle_from_url(url: str) -> str:
    if not url:
        return ""
    return url.rstrip("/").split("/")[-1]


def core_name_key(p: dict) -> str:
    """ブリュワリー名の重複プレフィックスと括弧書きを除いた、ゆるい比較用キー。"""
    name = re.sub(r"\(.*?\)", "", p.get("name", ""))
    brewery = p.get("brewery", "")
    if brewery and name.strip().lower().startswith(brewery.strip().lower()):
        name = name[len(brewery):]
    return re.sub(r"[^a-z0-9ぁ-んァ-ヶ一-龠]", "", name.lower())


def find_duplicate_candidates(products: list[dict]) -> list[dict]:
    """ブリュワリー名プレフィックスを除いた商品名の完全一致 **かつ** ブリュワリー一致を候補とする。
    ブリュワリー条件が無いと「West Coast IPA」等の汎用スタイル名を共有するだけの無関係な
    別ブリュワリー商品まで大量に誤検出する(2026-10-02の監査スクリプト初版で146件の誤検出を確認)。
    ブリュワリーも一致した上で商品名が同一というのは、同じ銘柄が別バッチ/別ID/別容量で
    重複登録されている可能性が高いという意味であり、それでも「同一商品の確定」では無いため
    自動マージはせず人間/Claudeによる確認に回す。"""
    candidates = []
    by_key: dict[tuple[str, str], list[dict]] = {}
    for p in products:
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


def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    products = data["products"]
    known_hops = up.known_hop_names()

    print(f"[{date.today()}] fetching live catalogs for full audit...")
    antenna_catalog = up.fetch_catalog("https://www.antenna-america.com")
    southbound_catalog = up.fetch_catalog("https://southbound.jp")
    print(f"  antenna: {len(antenna_catalog)} / southbound: {len(southbound_catalog)}")
    antenna_by_handle = {p["handle"]: p for p in antenna_catalog}
    southbound_by_handle = {p["handle"]: p for p in southbound_catalog}

    renormalized = []
    backfilled = []
    stale_handle_candidates = []
    hop_in_description_candidates = []
    unknown_hop_names: dict[str, list[str]] = {}

    for p in products:
        old_hops = p.get("hops", [])
        if old_hops:
            new_hops = [up.normalize_hop(h) for h in old_hops]
            if new_hops != old_hops:
                renormalized.append({"id": p["id"], "before": old_hops, "after": new_hops})
                p["hops"] = new_hops

        handle = handle_from_url(p.get("url", "")) or p["id"]
        source = p.get("source")
        raw = (antenna_by_handle.get(handle) if source == "antenna"
               else southbound_by_handle.get(handle) if source == "southbound" else None)

        if raw is not None:
            reparsed = (up.parse_antenna_product(raw, source, "https://www.antenna-america.com")
                        if source == "antenna" else
                        up.parse_southbound_product(raw, "https://southbound.jp", source))
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
        else:
            gaps = [k for k in ("hops", "abv", "url") if not p.get(k) or p.get(k) == "-"]
            if gaps:
                stale_handle_candidates.append({
                    "id": p["id"], "name": p["name"], "brewery": p.get("brewery"),
                    "source": source, "gaps": gaps,
                })

        if not p.get("hops"):
            desc = p.get("description", "") or ""
            found = [h for h in known_hops if h.lower() in desc.lower()]
            if found:
                hop_in_description_candidates.append({"id": p["id"], "name": p["name"], "found": found})

        for h in p.get("hops", []):
            if h not in known_hops and h not in KNOWN_UNRESOLVED_HOPS:
                unknown_hop_names.setdefault(h, []).append(p["id"])

    duplicate_candidates = find_duplicate_candidates(products)

    data["last_updated"] = str(date.today())
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    review = {
        "date": str(date.today()),
        "auto_fixed": {
            "renormalized_hops": renormalized,
            "backfilled_from_live_source": backfilled,
        },
        "needs_review": {
            "duplicate_candidates": duplicate_candidates,
            "stale_handle_candidates": stale_handle_candidates,
            "hop_in_description_candidates": hop_in_description_candidates,
            "unknown_hop_names": dict(sorted(unknown_hop_names.items())),
        },
    }
    with open(REVIEW_PATH, "w", encoding="utf-8") as f:
        json.dump(review, f, ensure_ascii=False, indent=2)

    print(f"\nauto-fixed: {len(renormalized)} renormalized, {len(backfilled)} backfilled from live source")
    print(f"needs review (see data/audit_review.json):")
    print(f"  - {len(duplicate_candidates)} possible duplicate record(s)")
    print(f"  - {len(stale_handle_candidates)} stale-handle candidate(s) (id/url no longer resolves live)")
    print(f"  - {len(hop_in_description_candidates)} hop-in-description candidate(s)")
    print(f"  - {len(unknown_hop_names)} hop name(s) not yet in hops_tab.js's aroma chart")


if __name__ == "__main__":
    main()
