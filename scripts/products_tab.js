// ===== PRODUCTS TAB =====

function isRecent(d){ return d && (new Date()-new Date(d))/864e5 <= 7; }
function sgroup(s){
  if(/dipa|double|imperial|triple|quad/i.test(s)) return 'DIPA';
  if(/hazy|ne-style|northeast/i.test(s)) return 'IPA';
  if(/ipa|india/i.test(s)) return 'IPA';
  if(/pale ale|belgian pale/i.test(s)) return 'Pale Ale';
  if(/saison|farmhouse/i.test(s)) return 'Sour';
  if(/sour|lambic|gose|berliner/i.test(s)) return 'Sour';
  if(/lager|pilsner/i.test(s)) return 'Lager';
  if(/stout|porter/i.test(s)) return 'Stout';
  return 'Other';
}

function escHtml(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
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

var cameFromProduct = false;

function renderProds(){
  var s = document.getElementById('psrch').value.toLowerCase();
  var sf = document.getElementById('sfil').value;
  var shopf = document.getElementById('shopfil').value;
  var bf = document.getElementById('bfil').value;
  var list = document.getElementById('prod-list');
  list.innerHTML = '';
  var f = products.filter(function(p){
    var ms = p.name.toLowerCase().indexOf(s) >= 0 || p.brewery.toLowerCase().indexOf(s) >= 0;
    var mst = !sf || sgroup(p.style) === sf;
    var mshop = !shopf ||
      (shopf === 'southbound' && p.source === 'southbound') ||
      (shopf === 'antenna' && p.source !== 'southbound');
    var mbrew = !bf || p.brewery === bf;
    return ms && mst && mshop && mbrew;
  });
  document.getElementById('prod-count').textContent = f.length + '件表示（全' + products.length + '件）';

  f.forEach(function(p){
    var row = document.createElement('div');
    row.className = 'prod-row';
    row.addEventListener('click', function(){ openModal(p); });

    var newB = isRecent(p.added) ? '<span class="new-badge">NEW</span>' : '';
    var shopB = p.source === 'southbound'
      ? '<span class="shop-badge">Southbound</span>'
      : '';
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
        + '<div class="prod-row-arrow">\u203a</div>'
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
  document.getElementById('m-style').textContent = p.style || '\u2212';
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
    lb.textContent = p.source === 'southbound'
      ? '🛒 Southboundの商品ページへ'
      : '🛒 Antenna Americaの商品ページへ';
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
  btn.innerHTML = '\u2190 商品一覧に戻る';
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

function hopFilter(h){
  document.getElementById('modal').classList.remove('open');
  document.getElementById('psrch').value = h;
  document.getElementById('sfil').value = '';
  document.getElementById('shopfil').value = '';
  document.getElementById('bfil').value = '';
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

buildBreweryFilter();
renderProds();
