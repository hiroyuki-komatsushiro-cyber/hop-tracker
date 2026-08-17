import json
from pathlib import Path

DATA_PATH       = Path(__file__).parent.parent / "data" / "products.json"
OUTPUT_PATH     = Path(__file__).parent.parent / "docs" / "index.html"
SCRIPTS_DIR     = Path(__file__).parent
HOPS_TAB_JS     = (SCRIPTS_DIR / "hops_tab.js").read_text(encoding="utf-8")
PRODUCTS_TAB_JS = (SCRIPTS_DIR / "products_tab.js").read_text(encoding="utf-8")

CSS = """
*{box-sizing:border-box;margin:0;padding:0;}
html,body{height:100%;overflow:hidden;}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;background:#f7f6f2;color:#2c2c2a;display:flex;flex-direction:column;}
.tab-nav{display:flex;background:#2c2c2a;flex-shrink:0;z-index:200;}
.tab-nav button{flex:1;padding:13px 4px;font-size:13px;font-weight:600;border:none;background:transparent;color:#888;cursor:pointer;border-bottom:3px solid transparent;}
.tab-nav button.active{color:#fff;border-bottom-color:#639922;}
.panels{flex:1;overflow:hidden;position:relative;}
.tab-panel{position:absolute;inset:0;overflow-y:auto;display:none;padding:12px;}
.tab-panel.active{display:block;}
@media(min-width:700px){.tab-panel{max-width:720px;left:50%;transform:translateX(-50%);right:auto;width:720px;}}
h2{font-size:16px;font-weight:700;margin-bottom:8px;}
.note{font-size:11px;color:#888780;margin-top:12px;line-height:1.6;padding-bottom:20px;}

/* TAB1 RADAR */
.progress{font-size:12px;color:#5f5e5a;margin-bottom:6px;}
.pbar{height:5px;background:#e0ddd4;border-radius:3px;overflow:hidden;margin-top:3px;}
.pbar-fill{height:100%;background:#639922;}
.srch-row{display:flex;gap:6px;margin-bottom:6px;}
.srch-row input{flex:1;padding:8px 10px;font-size:14px;border:1px solid #ccc;border-radius:8px;}
.srch-row button{padding:8px 12px;font-size:13px;border:1px solid #ccc;border-radius:8px;background:#fff;cursor:pointer;white-space:nowrap;}
#alpha-tabs{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px;}
.alpha-tab{padding:5px 8px;font-size:12px;font-weight:600;border:1px solid #ddd;border-radius:6px;background:#fff;cursor:pointer;color:#555;min-width:28px;text-align:center;}
.alpha-tab.active{background:#2c2c2a;color:#fff;border-color:#2c2c2a;}
#hop-buttons{display:grid;grid-template-columns:repeat(2,1fr);gap:5px;max-height:180px;overflow-y:auto;padding:5px;border:1px solid #e0ddd4;border-radius:8px;background:#fff;margin-bottom:10px;}
@media(min-width:420px){#hop-buttons{grid-template-columns:repeat(3,1fr);}}
@media(min-width:700px){#hop-buttons{grid-template-columns:repeat(4,1fr);}}
#hop-buttons button{font-size:11px;line-height:1.3;padding:7px 4px;border:1px solid #ccc;border-radius:7px;background:#fff;cursor:pointer;text-align:center;min-height:36px;display:flex;align-items:center;justify-content:center;word-break:break-word;}
#hop-buttons button.active{font-weight:700;}
.chart-wrap{position:relative;width:100%;height:290px;background:#fff;border-radius:8px;padding:6px;}
@media(min-width:700px){.chart-wrap{height:380px;}}
#legend{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;font-size:11px;color:#5f5e5a;}
#legend span{display:flex;align-items:center;gap:3px;}
.sw{width:9px;height:9px;border-radius:2px;display:inline-block;flex-shrink:0;}
.hop-desc-box{background:#f7f6f2;border:1px solid #e0ddd4;border-radius:8px;padding:8px;margin-top:8px;display:none;display:flex;flex-direction:column;gap:6px;}
.hop-desc-item{background:#fff;border-radius:6px;padding:8px 10px;border-left:3px solid #639922;}
.hop-desc-name{font-size:12px;font-weight:700;color:#2c2c2a;margin-bottom:2px;}
.hop-desc-text{font-size:11px;color:#5f5e5a;line-height:1.6;}
.back-to-products-btn{width:100%;padding:9px;font-size:13px;font-weight:600;background:#f0f0ee;color:#2c2c2a;border:1px solid #ddd;border-radius:8px;cursor:pointer;margin-bottom:8px;display:flex;align-items:center;justify-content:center;gap:4px;}
.back-to-products-btn:active{background:#e5e3de;}

/* TAB2 PRODUCTS */
.t2-header{display:flex;gap:6px;margin-bottom:6px;align-items:center;}
.t2-header input[type=search]{flex:1;padding:8px 10px;font-size:14px;border:1px solid #ccc;border-radius:8px;}
.t2-header select{padding:8px 6px;font-size:13px;border:1px solid #ccc;border-radius:8px;background:#fff;max-width:110px;}
#prod-count{font-size:11px;color:#888;margin-bottom:6px;}
.updated-line{font-size:11px;color:#aaa;margin-bottom:6px;}
#prod-list{display:flex;flex-direction:column;gap:0;border-radius:10px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.07);}

/* 商品行 */
.prod-row{display:flex;align-items:center;gap:8px;padding:10px 12px;background:#fff;border-bottom:1px solid #f0ede6;cursor:pointer;-webkit-tap-highlight-color:transparent;}
.prod-row-img{width:52px;height:52px;border-radius:8px;object-fit:cover;flex-shrink:0;background:#f5f3ee;}
.prod-row-img-placeholder{width:52px;height:52px;border-radius:8px;background:#f0ede6;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:20px;}
.m-img{width:100%;max-width:200px;height:200px;object-fit:cover;border-radius:12px;margin:0 auto 16px;display:block;}
.m-img-wrap{text-align:center;}
.prod-row:last-child{border-bottom:none;}
.prod-row:active{background:#f0ede6;}

/* 左: 商品名・メーカー・バッジ */
.prod-row-left{flex:1;min-width:0;}
.prod-row-name{font-size:13px;font-weight:600;line-height:1.3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.prod-row-brewery{font-size:11px;color:#639922;font-weight:500;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.prod-row-sub{font-size:10px;color:#aaa;margin-top:3px;display:flex;gap:5px;align-items:center;}
.sbadge{display:inline-block;font-size:10px;padding:1px 6px;border-radius:6px;background:#e3eef8;color:#1a4a7a;white-space:nowrap;}
.new-badge{display:inline-block;font-size:10px;padding:1px 6px;border-radius:6px;background:#E24B4A;color:#fff;white-space:nowrap;}
.abv-text{color:#bbb;}

/* 右: ホップ名 + 矢印 */
.prod-row-right{display:flex;flex-direction:column;align-items:flex-end;gap:4px;flex-shrink:0;max-width:38%;min-width:80px;}
.prod-hop-list{font-size:10px;color:#639922;font-weight:500;text-align:right;line-height:1.5;word-break:break-word;}
.prod-hop-none{font-size:11px;color:#ddd;text-align:right;}
.prod-row-arrow{color:#ddd;font-size:16px;line-height:1;align-self:center;}

/* MODAL */
.modal-overlay{display:none;position:fixed;inset:0;z-index:500;background:rgba(0,0,0,.5);align-items:flex-end;justify-content:center;}
.modal-overlay.open{display:flex;}
.modal-box{background:#fff;border-radius:20px 20px 0 0;width:100%;max-width:600px;max-height:88vh;overflow-y:auto;padding:16px 16px 40px;animation:su .2s ease;}
@keyframes su{from{transform:translateY(50px);opacity:0;}to{transform:translateY(0);opacity:1;}}
.modal-handle{width:36px;height:4px;background:#ddd;border-radius:2px;margin:0 auto 14px;}
.m-title{font-size:16px;font-weight:700;line-height:1.3;margin-bottom:3px;}
.m-brewery{font-size:13px;color:#639922;font-weight:600;margin-bottom:14px;}
.m-sec{margin-bottom:14px;}
.m-lbl{font-size:10px;font-weight:700;color:#aaa;text-transform:uppercase;letter-spacing:.07em;margin-bottom:5px;}
.m-val{font-size:14px;}
.m-hops{display:flex;flex-wrap:wrap;gap:6px;}
.m-hop{font-size:13px;padding:5px 12px;border-radius:20px;background:#e8f3d6;color:#3a6010;border:1px solid #c5dc9a;cursor:pointer;}
.m-hop:active{background:#d1eaa8;}
.m-nohop{font-size:13px;color:#bbb;}
.m-desc{font-size:13px;color:#4a4a48;line-height:1.65;}
.m-actions{display:flex;gap:8px;margin-top:18px;flex-direction:column;}
.m-btn-chart{padding:13px;font-size:14px;font-weight:700;background:#639922;color:#fff;border:none;border-radius:10px;cursor:pointer;}
.m-btn-chart:active{background:#4e7a1a;}
.m-btn-link{padding:13px;font-size:14px;font-weight:600;background:#f0f0ee;color:#2c2c2a;border:none;border-radius:10px;cursor:pointer;text-decoration:none;display:block;text-align:center;}
.m-btn-close{padding:13px;font-size:14px;background:#fff;color:#555;border:1px solid #ddd;border-radius:10px;cursor:pointer;margin-top:4px;width:100%;display:flex;align-items:center;justify-content:center;gap:6px;}
.shop-badge{display:inline-block;font-size:10px;padding:1px 6px;border-radius:6px;background:#f3e8ff;color:#6b21a8;white-space:nowrap;margin-left:4px;}
"""

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ホップ アロマ比較 / 製品ホップ成分表</title>
<style>{css}</style>
</head>
<body>

<div class="tab-nav">
  <button class="active" onclick="switchTab('t1',this)">&#x1F37A; ホップ アロマ比較</button>
  <button onclick="switchTab('t2',this)">&#x1F4CB; 製品ホップ成分表</button>
</div>

<div class="panels">

<div id="t1" class="tab-panel active">
  <h2>ホップ アロマ特性 比較チャート（全133品種）</h2>
  <div class="progress">収録品種: 133/133 <div class="pbar"><div class="pbar-fill" style="width:100%"></div></div></div>
  <div class="srch-row">
    <input type="text" id="srch" placeholder="品種名で検索...">
    <button id="clrBtn" type="button">クリア</button>
  </div>
  <div id="alpha-tabs"></div>
  <div id="hop-buttons"></div>
  <div class="chart-wrap"><canvas id="hopChart"></canvas></div>
  <div id="legend"></div>
  <div class="hop-desc-box" id="hop-desc-box" style="display:none;"></div>
  <p class="note">※ 頭文字タブで絞り込み、★は選択中の品種一覧。複数選択でレーダーチャートに重ねて比較できます。各アロマ軸は0〜5の強度の目安(BeerMaverick等のテイスティングノートに基づく)。</p>
</div>

<div id="t2" class="tab-panel">
  <h2>製品別ホップ成分表 — Antenna America</h2>
  <div class="updated-line">最終更新: {last_updated}</div>
  <div class="t2-header">
    <input type="search" id="psrch" placeholder="製品名・ブリュワリーで検索...">
    <select id="sfil">
      <option value="">全スタイル</option>
      <option value="IPA">IPA / Hazy</option>
      <option value="DIPA">DIPA</option>
      <option value="Pale Ale">Pale Ale</option>
      <option value="Sour">Sour / Saison</option>
      <option value="Stout">Stout / Porter</option>
      <option value="Lager">Lager</option>
      <option value="Other">その他</option>
    </select>
    <select id="shopfil">
      <option value="">全ショップ</option>
      <option value="antenna">Antenna America</option>
      <option value="southbound">Southbound</option>
    </select>
    <select id="bfil">
      <option value="">全ブルワリー</option>
    </select>
  </div>
  <div id="prod-count"></div>
  <div id="prod-list"></div>
  <p class="note">※ 商品をタップすると成分表が表示されます。一度登録した商品はサイトから消えても削除しません。直近7日以内の新商品にはNEWバッジが付きます。</p>
</div>

</div>

<div class="modal-overlay" id="modal" onclick="closeModal(event)">
  <div class="modal-box" id="mbox">
    <div class="modal-handle"></div>
    <div class="m-img-wrap" id="m-img-wrap"></div>
    <div class="m-title" id="m-title"></div>
    <div class="m-brewery" id="m-brewery"></div>
    <div class="m-sec"><div class="m-lbl">スタイル</div><div class="m-val" id="m-style"></div></div>
    <div class="m-sec"><div class="m-lbl">アルコール度数</div><div class="m-val" id="m-abv"></div></div>
    <div class="m-sec" id="m-desc-sec"><div class="m-lbl">商品説明</div><div class="m-desc" id="m-desc"></div></div>
    <div class="m-sec"><div class="m-lbl">使用ホップ</div><div id="m-hops"></div></div>
    <div class="m-actions" id="m-actions"></div>
    <button class="m-btn-close" onclick="document.getElementById('modal').classList.remove('open')">&#8592; 商品一覧に戻る</button>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
function switchTab(id,btn){{
  document.querySelectorAll('.tab-panel').forEach(function(p){{p.classList.remove('active');}});
  document.querySelectorAll('.tab-nav button').forEach(function(b){{b.classList.remove('active');}});
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
  if(id==='t1' && typeof chart !== 'undefined') chart.resize();
}}
</script>
<script>{hops_tab_js}</script>
<script>var products = {products_json};</script>
<script>{products_tab_js}</script>
</body>
</html>
"""

def main():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    html = HTML_TEMPLATE.format(
        css             = CSS,
        last_updated    = data.get("last_updated", "-"),
        hops_tab_js     = HOPS_TAB_JS,
        products_json   = json.dumps(data["products"], ensure_ascii=False),
        products_tab_js = PRODUCTS_TAB_JS,
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Built {OUTPUT_PATH} with {len(data['products'])} products.")

if __name__ == "__main__":
    main()
