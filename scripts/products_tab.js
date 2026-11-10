// ===== PRODUCTS TAB =====

function isRecent(d){ return d && (new Date()-new Date(d))/864e5 <= 7; }

// 収集元ごとの表示(バッジ・リンク文言)は SHOPS(update_sources.jsonのuiから生成、build_html.pyが埋め込む)。
// バッジが無い収集元(antenna)は表示しない。sourceが空の旧データはantenna扱い
function shopBadge(p){
  var s = SHOPS[p.source];
  return (s && s.badge) ? '<span class="shop-badge ' + p.source + '">' + s.badge + '</span>' : '';
}
function shopLink(p){
  var s = SHOPS[p.source || 'antenna'];
  return (s && s.link) || '🛒 商品ページへ';
}

function escHtml(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ---- スタイル分類・度数帯 ----
// 分類表 TREE と、商品ごとの派生値 sg(大分類)/ss(細分類)/av(度数の数値)/ab(度数帯)は、
// scripts/style_class.py が build_html.py のビルド時に作って埋め込む(ルールは1か所だけ)
var SUB_LABEL = {}, GROUP_LABEL = {}, ABV_LABEL = {};
TREE.groups.forEach(function(g){
  GROUP_LABEL[g[0]] = g[1];
  g[2].forEach(function(s){ SUB_LABEL[s[0]] = s[1]; });
});
TREE.abv.forEach(function(a){ ABV_LABEL[a[0]] = a[1]; });
products.forEach(function(p, i){ p._i = i; });   // 登録順(「標準」の並び、同じ値のときの順序)

var abvSel = '';   // 選択中の度数帯キー('' = すべて)

function buildStyleSelect(){
  var sel = document.getElementById('sfil');
  sel.innerHTML = '<option value="">全スタイル</option>';
  TREE.groups.forEach(function(g){
    var og = document.createElement('optgroup');
    og.label = g[1];
    var all = document.createElement('option');
    all.value = 'g:' + g[0];
    og.appendChild(all);
    g[2].forEach(function(s){
      var o = document.createElement('option');
      o.value = 's:' + s[0];
      og.appendChild(o);
    });
    sel.appendChild(og);
  });
}

function buildAbvChips(){
  var box = document.getElementById('abv-chips');
  box.innerHTML = '';
  TREE.abv.forEach(function(a){
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip';
    b.setAttribute('data-ab', a[0]);
    b.addEventListener('click', function(){
      abvSel = (abvSel === a[0]) ? '' : a[0];   // もう一度押すと解除
      renderProds();
    });
    box.appendChild(b);
  });
}

// ブルワリーフィルタを動的生成
function buildBreweryFilter(){
  var sel = document.getElementById('bfil');
  if(!sel) return;
  var breweries = [...new Set(products.map(function(p){ return p.brewery; }))].sort();
  breweries.forEach(function(b){
    var o = document.createElement('option');
    o.value = b;
    o.textContent = b;
    sel.appendChild(o);
  });
}

// ---- 絞り込み ----
function readFilters(){
  return {
    q: document.getElementById('psrch').value.toLowerCase().trim(),
    style: document.getElementById('sfil').value,
    abv: abvSel,
    shop: document.getElementById('shopfil').value,
    brewery: document.getElementById('bfil').value
  };
}

// skip: その項目だけ無視して判定する(各選択肢の件数を「他の条件を満たす商品数」として出すため)
function passes(p, f, skip){
  if(skip !== 'q' && f.q){
    // 製品名・ブリュワリー・ホップ名・スタイル(元の表記)で検索
    var hay = (p.name + ' ' + p.brewery + ' ' + (p.hops || []).join(' ') + ' ' + (p.style || '')).toLowerCase();
    if(hay.indexOf(f.q) < 0) return false;
  }
  if(skip !== 'style' && f.style){
    var k = f.style.slice(2);
    if(f.style.charAt(0) === 'g' ? p.sg !== k : p.ss !== k) return false;
  }
  if(skip !== 'abv' && f.abv && p.ab !== f.abv) return false;
  if(skip !== 'shop' && f.shop && (p.source || 'antenna') !== f.shop) return false;
  if(skip !== 'brewery' && f.brewery && p.brewery !== f.brewery) return false;
  return true;
}

// ---- 並び順 ----
function abvCmp(x, y, dir){
  if(x.av == null && y.av == null) return x._i - y._i;
  if(x.av == null) return 1;          // 度数不明は、どちらの向きでも最後
  if(y.av == null) return -1;
  return (x.av - y.av) * dir || (x._i - y._i);
}
function sortList(list, mode){
  var a = list.slice();
  if(mode === 'new') a.sort(function(x, y){ return (y.added || '').localeCompare(x.added || '') || (y._i - x._i); });
  else if(mode === 'abv_desc') a.sort(function(x, y){ return abvCmp(x, y, -1); });
  else if(mode === 'abv_asc') a.sort(function(x, y){ return abvCmp(x, y, 1); });
  else if(mode === 'name') a.sort(function(x, y){ return x.name.toLowerCase().localeCompare(y.name.toLowerCase()) || (x._i - y._i); });
  return a;   // 'std' = 登録順のまま
}

// ---- 選択肢の件数(ほかの条件を満たす商品数)を更新 ----
function updateFacets(f){
  var cs = {}, ca = {}, cp = {}, nStyle = 0;
  products.forEach(function(p){
    if(passes(p, f, 'style')){
      nStyle++;
      cs['g:' + p.sg] = (cs['g:' + p.sg] || 0) + 1;
      cs['s:' + p.ss] = (cs['s:' + p.ss] || 0) + 1;
    }
    if(passes(p, f, 'abv')) ca[p.ab] = (ca[p.ab] || 0) + 1;
    if(passes(p, f, 'shop')){ var k = p.source || 'antenna'; cp[k] = (cp[k] || 0) + 1; }
  });
  [].forEach.call(document.getElementById('sfil').options, function(o){
    if(o.value === '') o.textContent = '全スタイル (' + nStyle + ')';
    else if(o.value.charAt(0) === 'g') o.textContent = GROUP_LABEL[o.value.slice(2)] + ' すべて (' + (cs[o.value] || 0) + ')';
    else o.textContent = '　' + SUB_LABEL[o.value.slice(2)] + ' (' + (cs[o.value] || 0) + ')';
  });
  [].forEach.call(document.querySelectorAll('#abv-chips .chip'), function(b){
    var key = b.getAttribute('data-ab');
    b.textContent = ABV_LABEL[key] + ' ' + (ca[key] || 0);
    b.classList.toggle('active', abvSel === key);
  });
  [].forEach.call(document.getElementById('shopfil').options, function(o){
    if(!o.hasAttribute('data-base')) o.setAttribute('data-base', o.textContent);
    if(o.value !== '') o.textContent = o.getAttribute('data-base') + ' (' + (cp[o.value] || 0) + ')';
  });
}

function anyFilter(f){ return !!(f.q || f.style || f.abv || f.shop || f.brewery); }

// 検索・スタイル・度数・ショップ・ブルワリーを全て解除(並び順は変えない)。keepSearch=trueなら検索語は残す
function resetFilters(keepSearch){
  if(!keepSearch) document.getElementById('psrch').value = '';
  document.getElementById('sfil').value = '';
  document.getElementById('shopfil').value = '';
  document.getElementById('bfil').value = '';
  abvSel = '';
}

var cameFromProduct = false;

function renderProds(){
  var f = readFilters();
  var list = document.getElementById('prod-list');
  list.innerHTML = '';
  var matched = sortList(products.filter(function(p){ return passes(p, f, ''); }),
                         document.getElementById('sortsel').value);
  document.getElementById('prod-count').textContent = matched.length + '件表示（全' + products.length + '件）';
  document.getElementById('fclear').style.display = anyFilter(f) ? 'inline-block' : 'none';
  document.getElementById('fmore-sum').textContent = 'ブルワリーで絞り込む' + (f.brewery ? '：' + f.brewery : '');
  updateFacets(f);

  matched.forEach(function(p){
    var row = document.createElement('div');
    row.className = 'prod-row';
    row.addEventListener('click', function(){ openModal(p); });

    var newB = isRecent(p.added) ? '<span class="new-badge">NEW</span>' : '';
    var shopB = shopBadge(p);
    var hopStr = p.hops && p.hops.length > 0 ? p.hops.join(' / ') : '';

    var imgHtml = '';
    if(p.image){
      imgHtml = '<img class="prod-row-img" src="' + escHtml(p.image) + '" alt="' + escHtml(p.name) + '" loading="lazy" onerror="this.style.display=\'none\';this.nextSibling.style.display=\'flex\'">'
              + '<div class="prod-row-img-placeholder" style="display:none">🍺</div>';
    } else {
      imgHtml = '<div class="prod-row-img-placeholder">🍺</div>';
    }

    row.innerHTML =
      imgHtml
      + '<div class="prod-row-left">'
        + '<div class="prod-row-name">' + escHtml(p.name) + (newB ? '&nbsp;' + newB : '') + shopB + '</div>'
        + '<div class="prod-row-brewery">' + escHtml(p.brewery) + '</div>'
        + '<div class="prod-row-sub">'
          + '<span class="sbadge">' + escHtml(p.style) + '</span>'
          + ((p.abv && p.abv !== '-') ? '<span class="abv-text">' + escHtml(p.abv) + '</span>' : '')
        + '</div>'
      + '</div>'
      + '<div class="prod-row-right">'
        + (hopStr ? '<div class="prod-hop-list">' + escHtml(hopStr) + '</div>' : '<div class="prod-hop-none">−</div>')
        + '<div class="prod-row-arrow">›</div>'
      + '</div>';

    list.appendChild(row);
  });
}

function openModal(p){
  var mImgWrap = document.getElementById('m-img-wrap');
  if(p.image){
    mImgWrap.innerHTML = '<img class="m-img" src="' + escHtml(p.image) + '" alt="' + escHtml(p.name) + '" onerror="this.parentNode.innerHTML=\'\'">';
    mImgWrap.style.display = '';
  } else {
    mImgWrap.innerHTML = '';
    mImgWrap.style.display = 'none';
  }

  document.getElementById('m-title').textContent = p.name;
  document.getElementById('m-brewery').textContent = p.brewery;
  document.getElementById('m-style').innerHTML = escHtml(p.style || '−')
    + '<div class="m-subcat">分類: ' + escHtml(GROUP_LABEL[p.sg] || '') + ' › ' + escHtml(SUB_LABEL[p.ss] || '') + '</div>';
  document.getElementById('m-abv').textContent = (p.abv && p.abv !== '-') ? p.abv : '不明';

  var mdesc = document.getElementById('m-desc-sec');
  if(p.description){
    document.getElementById('m-desc').textContent = p.description;
    mdesc.style.display = '';
  } else {
    mdesc.style.display = 'none';
  }

  var mh = document.getElementById('m-hops');
  mh.innerHTML = '';
  if(p.hops && p.hops.length > 0){
    var tags = document.createElement('div');
    tags.className = 'm-hops';
    p.hops.forEach(function(h){
      var sp = document.createElement('span');
      sp.className = 'm-hop';
      sp.textContent = h;
      sp.addEventListener('click', function(){ hopFilter(h); });
      tags.appendChild(sp);
    });
    mh.appendChild(tags);
  } else {
    mh.innerHTML = '<div class="m-nohop">ホップ情報は非公開です</div>';
  }

  var acts = document.getElementById('m-actions');
  acts.innerHTML = '';

  var ch = (p.hops||[]).filter(function(h){ return hops.find(function(x){ return x.name === h; }); });
  if(ch.length > 0){
    var cb = document.createElement('button');
    cb.className = 'm-btn-chart';
    cb.textContent = '📊 アロマチャートで比較';
    cb.addEventListener('click', function(){
      document.getElementById('modal').classList.remove('open');
      cameFromProduct = true;
      sel = ch;
      updateChart();
      renderBtns('');
      showHopDesc();
      var radarBtn = document.querySelector('.tab-nav button');
      switchTab('t1', radarBtn);
      showBackToProducts();
    });
    acts.appendChild(cb);
  }

  if(p.url && p.url.indexOf('/collections/') === -1){
    var lb = document.createElement('a');
    lb.className = 'm-btn-link';
    lb.href = p.url;
    lb.target = '_blank';
    lb.rel = 'noopener noreferrer';
    lb.textContent = shopLink(p);
    acts.appendChild(lb);
  }

  document.getElementById('modal').classList.add('open');
}

function showBackToProducts(){
  var existing = document.getElementById('back-to-products-btn');
  if(existing) return;
  var btn = document.createElement('button');
  btn.id = 'back-to-products-btn';
  btn.className = 'back-to-products-btn';
  btn.innerHTML = '← 商品一覧に戻る';
  btn.addEventListener('click', function(){
    cameFromProduct = false;
    btn.remove();
    var prodBtn = document.querySelectorAll('.tab-nav button')[1];
    switchTab('t2', prodBtn);
  });
  var t1 = document.getElementById('t1');
  var chartWrap = t1.querySelector('.chart-wrap');
  t1.insertBefore(btn, chartWrap);
}

// モーダルのホップ名をタップ → そのホップを使う商品だけを表示(検索語=ホップ名。ほかの条件は解除)
function hopFilter(h){
  document.getElementById('modal').classList.remove('open');
  resetFilters(false);
  document.getElementById('psrch').value = h;
  renderProds();
}

function closeModal(e){
  if(e.target === document.getElementById('modal')){
    document.getElementById('modal').classList.remove('open');
  }
}

document.getElementById('psrch').addEventListener('input', renderProds);
document.getElementById('sfil').addEventListener('change', renderProds);
document.getElementById('shopfil').addEventListener('change', renderProds);
document.getElementById('bfil').addEventListener('change', renderProds);
document.getElementById('sortsel').addEventListener('change', renderProds);
document.getElementById('fclear').addEventListener('click', function(){ resetFilters(false); renderProds(); });

buildBreweryFilter();
buildStyleSelect();
buildAbvChips();
renderProds();
