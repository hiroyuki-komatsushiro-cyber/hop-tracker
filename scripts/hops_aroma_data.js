const pal=["#D85A30","#378ADD","#639922","#993556","#0F6E56","#BA7517","#7F77DD","#D4537E","#888780","#1D9E75","#85B7EB","#F0997B","#5DCAA5","#ED93B1","#EF9F27"];
const rlabels=["トロピカル","シトラス","ベリー/ストーンフルーツ","フローラル","パイン/樹脂","ハーブ/スパイス・土"];
const hops=[
{name:"Ahtanum",v:[1,5,0,3,4,3]},{name:"Ales for ALS",v:[3,3,3,1,2,2]},
{name:"Amarillo",v:[4,5,1,3,1,2]},{name:"Aramis",v:[0,2,0,2,0,5]},
{name:"Aurora",v:[1,3,0,3,1,3]},{name:"Azacca",v:[5,4,0,1,2,2]},
{name:"Bobek",v:[0,3,0,4,3,3]},{name:"Bravo",v:[2,4,2,4,1,2]},
{name:"Brewer's Gold",v:[0,0,4,0,0,2]},{name:"Cascade",v:[1,4,2,3,2,3]},
{name:"Cashmere",v:[3,4,2,1,0,2]},{name:"Celeia",v:[0,2,0,4,1,4]},
{name:"Centennial",v:[1,4,2,3,2,1]},{name:"Challenger",v:[1,1,1,2,1,4]},
{name:"Chelan",v:[1,2,1,2,1,1]},{name:"Chinook",v:[1,3,1,1,4,3]},
{name:"Citra",v:[4,5,3,1,1,1]},{name:"Cluster",v:[0,1,3,3,0,3]},
{name:"Cluster Fugget",v:[1,2,1,1,1,3]},{name:"Columbia",v:[3,4,0,1,0,1]},
{name:"Comet",v:[1,3,1,1,1,2]},{name:"Cryo Pop Original Blend",v:[4,4,3,1,1,0]},
{name:"Crystal",v:[1,2,1,3,1,3]},{name:"CTZ",v:[0,2,0,1,1,4]},
{name:"Dolcita",v:[4,3,3,1,0,1]},{name:"East Kent Golding",v:[0,3,0,4,0,3]},
{name:"Ekuanot",v:[4,4,2,1,0,2]},{name:"El Dorado",v:[5,2,3,1,1,1]},
{name:"Elani",v:[4,4,1,1,1,1]},{name:"Endeavour",v:[0,4,4,1,0,3]},
{name:"Ernest",v:[1,3,4,1,0,2]},{name:"Falconer's Flight 7Cs",v:[3,4,2,2,2,2]},
{name:"Falconer's Flight Blend",v:[4,4,1,3,2,1]},{name:"First Gold",v:[1,4,2,3,0,3]},
{name:"Fuggle",v:[0,1,1,1,0,4]},{name:"Galaxy",v:[4,4,2,0,1,1]},
{name:"Galena",v:[2,4,3,0,1,3]},{name:"Glacier",v:[1,2,3,1,0,3]},
{name:"Hallertau Blanc",v:[4,4,2,3,0,1]},{name:"Hallertauer Mittelfruher",v:[0,2,0,3,0,4]},
{name:"Hallertauer Tradition",v:[0,2,1,3,0,4]},{name:"HBC 472",v:[3,3,2,3,1,3]},
{name:"HBC 630",v:[3,3,4,2,0,1]},{name:"HBC 638",v:[4,4,3,2,0,1]},
{name:"HBC 682",v:[0,2,1,2,0,3]},{name:"Helga",v:[0,1,0,3,0,4]},
{name:"Herkules",v:[1,3,1,1,3,3]},{name:"Hersbrucker Spat",v:[0,2,1,3,0,4]},
{name:"Horizon",v:[0,2,0,3,1,3]},{name:"Huell Melon",v:[3,1,4,1,0,1]},
{name:"Idaho 7",v:[4,4,2,1,3,2]},{name:"Idaho Gem",v:[3,3,4,2,0,2]},
{name:"Jarrylo",v:[2,4,2,1,0,2]},{name:"Kazbek",v:[1,4,2,2,0,3]},
{name:"Kohatu",v:[4,2,2,1,2,1]},{name:"Krush",v:[4,4,3,1,1,0]},
{name:"Liberty",v:[0,2,0,3,0,3]},{name:"Loral",v:[1,3,2,4,0,2]},
{name:"Magnum",v:[0,2,0,2,1,3]},{name:"Mandarina Bavaria",v:[2,5,1,2,0,1]},
{name:"Millennium",v:[0,1,2,2,3,2]},{name:"Mosaic",v:[4,3,4,2,2,2]},
{name:"Motueka (MacHops)",v:[2,5,1,2,0,2]},{name:"Motueka (NZ Hops)",v:[2,5,1,2,0,2]},
{name:"Moutere",v:[4,3,2,1,1,1]},{name:"Mt. Hood",v:[0,1,0,3,1,3]},
{name:"Mt. Rainier",v:[1,2,1,2,2,2]},{name:"Nectaron",v:[5,4,3,0,0,0]},
{name:"Nelson Sauvin (MacHops)",v:[3,2,4,2,0,1]},{name:"Nelson Sauvin (NZ Hops)",v:[3,2,4,2,0,1]},
{name:"Newport",v:[0,2,0,0,2,3]},{name:"Northdown",v:[0,1,2,2,2,3]},
{name:"Northern Brewer",v:[0,1,0,1,2,4]},{name:"Nugget",v:[1,2,1,1,2,4]},
{name:"Olympic",v:[0,2,0,0,2,3]},{name:"Opal",v:[1,2,2,3,2,3]},
{name:"Pacific Crest Blend",v:[0,1,0,2,2,4]},{name:"Pacific Gem",v:[0,2,3,0,2,3]},
{name:"Pacific Jade",v:[0,3,0,0,2,4]},{name:"Pacifica (MacHops)",v:[1,4,0,3,0,2]},
{name:"Pacifica (NZ Hops)",v:[1,4,0,3,0,2]},{name:"Palisade",v:[1,2,3,2,0,2]},
{name:"Pekko",v:[1,3,0,3,0,3]},{name:"Perle",v:[0,1,0,2,1,3]},
{name:"Phoenix",v:[1,1,0,2,2,3]},{name:"Pilgrim",v:[0,1,2,2,2,3]},
{name:"Pilot",v:[0,1,1,1,2,3]},{name:"Pink Boots Blend",v:[3,4,3,2,1,1]},
{name:"Polaris",v:[2,2,0,1,3,4]},{name:"Premiant",v:[0,1,0,2,0,3]},
{name:"Pride of Ringwood",v:[0,0,0,0,2,4]},{name:"Progress",v:[0,1,2,2,0,3]},
{name:"Rakau (MacHops)",v:[2,2,3,1,2,1]},{name:"Rakau (NZ Hops)",v:[2,2,3,1,2,1]},
{name:"Riwaka",v:[3,5,1,1,0,1]},{name:"Saaz",v:[0,1,0,3,0,4]},
{name:"Sabro",v:[4,4,3,1,2,2]},{name:"Santiam",v:[0,2,0,3,0,3]},
{name:"Saphir",v:[1,3,1,3,0,2]},{name:"Savinjski Golding",v:[0,2,0,3,1,3]},
{name:"Simcoe",v:[3,3,2,1,4,2]},{name:"Sladek",v:[0,1,0,2,0,3]},
{name:"Sorachi Ace",v:[0,4,0,0,0,4]},{name:"Southern Cross (NZ Hops)",v:[2,4,1,1,2,2]},
{name:"Sovereign",v:[0,1,2,3,0,3]},{name:"Spalter",v:[0,1,0,3,0,3]},
{name:"Spalter Select",v:[0,1,0,3,0,3]},{name:"Sterling",v:[0,2,0,3,0,3]},
{name:"Strisselspalter",v:[0,1,0,3,0,4]},{name:"Summer",v:[2,3,3,1,0,2]},
{name:"Summit",v:[0,3,0,0,1,4]},{name:"Super Pride",v:[0,1,1,0,2,3]},
{name:"Superdelic (NZ Hops)",v:[3,3,4,1,0,2]},{name:"Sussex Hop",v:[0,2,0,2,0,3]},
{name:"Sylva",v:[0,1,0,3,1,3]},{name:"Tahoma",v:[0,3,0,1,2,2]},
{name:"Talus",v:[2,4,3,3,3,2]},{name:"Target",v:[0,1,1,1,2,4]},
{name:"Tettnanger",v:[0,1,0,3,0,3]},{name:"Topaz",v:[2,3,1,0,2,2]},
{name:"Triskel",v:[1,3,1,3,0,2]},{name:"Triumph",v:[1,3,2,2,2,1]},
{name:"Vanguard",v:[0,1,0,2,1,4]},{name:"Veterans' Blend",v:[4,3,3,1,1,1]},
{name:"Vista",v:[2,3,2,2,2,2]},{name:"Wai Iti (NZ Hops)",v:[2,3,3,2,0,1]},
{name:"Waimea (NZ Hops)",v:[2,4,1,1,3,2]},{name:"Wakatu (MacHops)",v:[1,3,0,3,0,2]},
{name:"Wakatu (NZ Hops)",v:[1,3,0,3,0,2]},{name:"Warrior",v:[0,2,0,1,3,2]},
{name:"Willamette",v:[0,1,0,3,1,3]},{name:"Yakima Gold",v:[0,2,0,1,0,2]},
{name:"Zythos Blend",v:[2,4,1,2,2,1]}
];
hops.forEach((h,i)=>{ h.color=pal[i%pal.length]; });

let sel=["Citra"];
const btnCont=document.getElementById('hop-buttons');
function renderBtns(f){
  btnCont.innerHTML='';
  hops.filter(h=>h.name.toLowerCase().includes(f.toLowerCase())).forEach(h=>{
    const b=document.createElement('button');
    b.type='button';b.textContent=h.name;b.dataset.name=h.name;
    b.addEventListener('click',()=>{
      sel=sel.includes(h.name)?sel.filter(n=>n!==h.name):[...sel,h.name];
      updateChart();
    });
    btnCont.appendChild(b);
  });
  refreshBtns();
}
document.getElementById('srch').addEventListener('input',e=>renderBtns(e.target.value));
document.getElementById('clrBtn').addEventListener('click',()=>{sel=[];updateChart();});
function buildDS(){
  return sel.map(name=>{
    const h=hops.find(x=>x.name===name);
    return{label:h.name,data:h.v.map(x=>x/5*100),rawData:h.v,
      borderColor:h.color,backgroundColor:h.color+'33',
      borderWidth:2,pointBackgroundColor:h.color,pointRadius:3};
  });
}
const ctx=document.getElementById('hopChart');
const chart=new Chart(ctx,{
  type:'radar',data:{labels:rlabels,datasets:buildDS()},
  options:{responsive:true,maintainAspectRatio:false,
    scales:{r:{min:0,max:100,ticks:{display:false},pointLabels:{font:{size:11}}}},
    plugins:{legend:{display:false},
      tooltip:{callbacks:{label:c=>c.dataset.label+': '+c.dataset.rawData[c.dataIndex]+'/5'}}}}
});
function refreshBtns(){
  document.querySelectorAll('#hop-buttons button').forEach(b=>{
    const on=sel.includes(b.dataset.name);
    const h=hops.find(x=>x.name===b.dataset.name);
    b.classList.toggle('active',on);
    b.style.background=on?h.color+'22':'#fff';
    b.style.borderColor=on?h.color:'#ccc';
  });
}
function updateChart(){
  chart.data.datasets=buildDS();chart.update();refreshBtns();
  document.getElementById('legend').innerHTML=sel.map(n=>{
    const h=hops.find(x=>x.name===n);
    return '<span><span class="sw" style="background:'+h.color+'"></span>'+h.name+'</span>';
  }).join('');
}
renderBtns('');updateChart();
