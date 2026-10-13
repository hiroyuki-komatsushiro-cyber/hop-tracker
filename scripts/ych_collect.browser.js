/*
 * Yakima Chief Hops の品種/製品ページから「典型値」を収集するブラウザ側スクリプト。
 * 使い方は scripts/ych_merge.py の冒頭コメントを参照。
 *
 * 実行方法: アプリ内ブラウザ(実ブラウザ)で https://www.yakimachief.com の任意のページを開き、
 * このファイルの内容をjavascript実行 → window.__ymany(['/variety/cascade', ...], 1500) を呼ぶ。
 * 結果は window.__ych に溜まるので、最後に下の dump() の出力を raw.json として保存する。
 *
 * 守ること:
 *  - 1ページ/1.5秒以上の間隔、全体で1回きり(同社サイトはPython等のHTTPクライアントを429で拒否する。
 *    その制限を回避する目的のなりすまし等は行わない)。429/403が返ったら即停止(下の実装も停止する)
 *  - 取得するのは数値の範囲(α酸・β酸・総オイル・精油組成)とリンク先だけ。文章・画像・官能評価の値は取らない
 */
window.__ych = window.__ych || {};

window.__yparse = (html, path) => {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const lab = [...doc.querySelectorAll('[aria-label]')].map(e => e.getAttribute('aria-label'));
  const rng = (prefix) => {
    const a = lab.find(x => x.toUpperCase().startsWith(prefix));
    if (!a) return null;
    const m = a.match(/:\s*(-?[\d.]+)\s*-\s*(-?[\d.]+)/);
    return m ? [parseFloat(m[1]), parseFloat(m[2])] : null;
  };
  const comp = (prefix) => {
    const a = lab.find(x => x.toUpperCase().startsWith(prefix + ':'));
    if (!a) return null;
    let m = a.match(/:\s*(-?[\d.]+)\s*-\s*(-?[\d.]+)\s*%/);
    if (m) return [parseFloat(m[1]), parseFloat(m[2])];
    m = a.match(/:\s*(-?[\d.]+)\s*%/);
    return m ? [parseFloat(m[1]), parseFloat(m[1])] : null;
  };
  const oilLabel = lab.find(x => /^TOTAL OIL/i.test(x) && /on scale/.test(x));
  const ou = oilLabel ? (/ml\/100g/i.test(oilLabel) ? 'ml' : /v\/w/i.test(oilLabel) ? 'vw' : '?') : null;
  // コフムロンは<main>内のテキストだけから探す(<body>全体だとscript内のUI既定文言"(20-24% COHUMULONE)"を拾う)
  const coM = (doc.querySelector('main') || doc.body).textContent.match(/\((\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?\s*%\s*COHUMULONE\)/i);
  const co = coM ? [parseFloat(coM[1]), parseFloat(coM[2] !== undefined ? coM[2] : coM[1])] : null;
  const tabs = [...doc.querySelectorAll('[role="tab"]')].map(t => ({t: t.textContent.trim(), s: t.getAttribute('aria-selected') === 'true'}));
  return {
    p: path,
    form: (tabs.find(t => t.s) || {}).t || null,
    a: rng('ALPHA ACIDS'), co, b: rng('BETA ACIDS'), o: rng('TOTAL OIL'), ou,
    oil: ['B-PINENE', 'MYRCENE', 'LINALOOL', 'CARYOPHYLLENE', 'FARNESENE', 'HUMULENE', 'GERANIOL', 'OTHER'].map(comp),
    sens: !!doc.querySelector('canvas[aria-label="SENSORY ANALYSIS"]'),
  };
};

// 同一オリジンのページを順に取得(429/403/例外で即停止)。delayMsは最低1500を推奨
window.__ymany = async (items, delayMs) => {
  const out = [];
  for (const path of items) {
    if (window.__ych[path]) { out.push(['cached', path]); continue; }
    let r;
    try { r = await fetch(path, {credentials: 'same-origin'}); } catch (e) { out.push(['err', path, String(e)]); break; }
    if (r.status !== 200) { out.push(['http', path, r.status]); if (r.status === 429 || r.status === 403) break; continue; }
    window.__ych[path] = window.__yparse(await r.text(), path);
    out.push(['ok', path]);
    await new Promise(res => setTimeout(res, delayMs || 1500));
  }
  return out;
};

// ych_merge.py に渡す raw.json 形式で出力
window.__ydump = () => JSON.stringify(Object.fromEntries(Object.entries(window.__ych).map(
  ([p, r]) => [p, [r.a, r.co, r.b, r.o, r.ou, r.oil, r.sens ? 1 : 0, r.form]])));
