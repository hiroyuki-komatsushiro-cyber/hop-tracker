"""
Yakima Chief Hops公開データの取り込み (scripts/ych_merge.py)

ホップ品種ごとの成分(α酸・β酸・総オイル・精油組成の典型値範囲)と、同社ページへのリンクを
data/ych_specs.json にまとめる。アロマチャートの「成分」欄(hops_tab.js)がこれを使う。

データの取得は、同社サイトが非ブラウザのHTTPクライアントを429で拒否するため、アプリ内ブラウザ
(実ブラウザ)で scripts/ych_collect.browser.js を実行して行う。robots.txtは全面許可
(User-Agent: * / Allow: /)で、1ページ/1.5秒以上の間隔・1回きりの収集にとどめること。
同社の利用規約は「データ編集物を含むサイトの内容はYCHの知的財産」としているため、公開サイト上は
典型値の範囲のみを出典明記で表示し、官能評価(13分類)は転載せずリンクで誘導する方針。

使い方:
  1. data/ych_map.json に「品種名 -> YCHページのパス」を追記(新品種を追加したとき)
  2. アプリ内ブラウザで https://www.yakimachief.com を開き、ych_collect.browser.js の手順で
     対象パスを収集して raw.json を作る
  3. python scripts/ych_merge.py raw.json   (既存エントリは上書き更新、他は保持)
  4. python scripts/build_html.py

raw.json の形式: {"/variety/cascade": [a, co, b, o, ou, oil, sens, form], ...}
  a/co/b/o = [下限,上限] または null、ou = 'ml'|'vw'|null、oil = 8成分の[下限,上限]配列(順序は固定)、
  sens = 官能評価チャートの有無、form = 品種ページで選択中の製品形態タブ名
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
MAP_PATH = ROOT / "data" / "ych_map.json"
SPECS_PATH = ROOT / "data" / "ych_specs.json"

FORM_JA = {
    "Whole Leaf Hops": "ホールリーフ",
    "T-90 Hop Pellets": "T-90ペレット",
    "Cryo Hops® Pellets": "Cryo Hops®ペレット",
    "American Noble Hops™ Pellets": "American Noble Hops™ペレット",
}


def form_label(path: str, form):
    if path.startswith("/product/"):
        if "cryo" in path:
            return "Cryo Hops®ペレット"
        if "hyperboost" in path:
            return "HyperBoost®"
        if "dynaboost" in path:
            return "DynaBoost®"
        if "t-90" in path:
            return "T-90ペレット"
        return None
    return FORM_JA.get(form, form)


def main(raw_path: str) -> None:
    mapping = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    raw = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    if SPECS_PATH.exists():
        cur = json.loads(SPECS_PATH.read_text(encoding="utf-8"))
    else:
        cur = {"specs": {}}
    specs = cur.get("specs", {})

    n_new = n_upd = 0
    for name, path in mapping.items():
        r = raw.get(path)
        if not r:
            continue
        a, co, b, o, ou, oil, sens, form = r
        entry = {"p": path}
        f = form_label(path, form)
        if f:
            entry["f"] = f
        # コフムロンは採用条件を絞る: 「典型値」欄(β酸があるページ)のものだけ、かつ20-24%は除く。
        # 欄が無いページでも、同社サイトのUI既定文言「(20-24% COHUMULONE)」を拾ってしまうため、
        # 実測値か既定文言か区別できない「20-24」は載せない(誤情報より欠落を選ぶ)
        if not b or co == [20, 24]:
            co = None
        for key, val in (("a", a), ("co", co), ("b", b), ("o", o)):
            if val:
                entry[key] = val
        if o and ou:
            entry["ou"] = ou
        # 精油組成: 「0-0%」は同社データ上の未設定値とみなして除外する(例: HyperBoost等の「その他」)
        if oil:
            oil = [None if (x == [0, 0]) else x for x in oil]
        if oil and any(oil):
            entry["oil"] = oil
        if sens:
            entry["s"] = 1
        if name in specs:
            n_upd += 1
        else:
            n_new += 1
        specs[name] = entry

    jst = timezone(timedelta(hours=9))
    cur["source"] = "Yakima Chief Hops (https://www.yakimachief.com) 公開の典型値"
    cur["note"] = ("α酸・β酸・総オイル・精油組成は同社が公開する典型値(複数年の収穫データに基づく範囲)。"
                   "p=同社ページのパス、f=製品形態、s=官能評価チャートあり。oilは"
                   "β-ピネン,ミルセン,リナロール,カリオフィレン,ファルネセン,フムレン,ゲラニオール,その他の順")
    cur["collected"] = str(datetime.now(jst).date())
    ordered = dict(sorted(specs.items(), key=lambda kv: kv[0].lower()))
    lines = [
        "{",
        f' "source": {json.dumps(cur["source"], ensure_ascii=False)},',
        f' "note": {json.dumps(cur["note"], ensure_ascii=False)},',
        f' "collected": {json.dumps(cur["collected"])},',
        ' "specs": {',
    ]
    items = list(ordered.items())
    for i, (name, entry) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        lines.append(f'  {json.dumps(name, ensure_ascii=False)}: '
                     f'{json.dumps(entry, ensure_ascii=False, separators=(",", ":"))}{comma}')
    lines += [" }", "}"]
    SPECS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"merged: {n_new} new, {n_upd} updated, total {len(ordered)} varieties -> {SPECS_PATH}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/ych_merge.py raw.json")
    main(sys.argv[1])
