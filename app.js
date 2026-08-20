const sectors=["Tous","Technologie","Finance","Pharmaceutique","Immobilier","Spatial","Énergie","Politique","Économie","Général"];
let state={articles:[],selected:"Tous",query:"",watch:JSON.parse(localStorage.getItem("watch")||"[]")};

async function loadNews(){
  try{
    const r=await fetch("data/news.json?ts="+Date.now(),{cache:"no-store"});
    const d=await r.json(); state.articles=d.articles||[];
    const t=d.updatedAt?new Date(d.updatedAt).toLocaleString("fr-CA"):"";
    document.getElementById("updated").textContent=t?"Mis à jour "+t:"";
    chips(); render();
  }catch(e){
    document.getElementById("feed").innerHTML='<div class="empty">Impossible de charger les nouvelles pour le moment. Vérifie data/news.json.</div>';
  }
}

function chips(){
  document.getElementById("chips").innerHTML=sectors.map(s=>`<button class="${s===state.selected?"active":""}" onclick="state.selected='${s}';chips();render()">${s}</button>`).join("");
}
function render(){
  let arr=state.articles.filter(n=>(state.selected==="Tous"||n.sector===state.selected)&&(!state.query||(`${n.title} ${n.summary} ${n.source} ${(n.entities||[]).join(" ")}`.toLowerCase().includes(state.query.toLowerCase()))));
  document.getElementById("count").textContent=arr.length+" nouvelles";
  document.getElementById("feed").innerHTML=arr.length?arr.map(n=>`
  <article class="card" onclick="openArticle('${escapeAttr(n.id)}')" role="button">
    <div class="cardlink">
      <div class="meta">${escape(n.sector)} · ${escape(n.source)} · ${n.sourceType==="officiel"?"SOURCE OFFICIELLE":"SOURCE AGRÉGÉE"}</div>
      <h3>${escape(n.title)}</h3>
      <div class="summary">${escape(n.summary||"")}</div>
      <div class="impact">
        <span class="pill ${n.impact==="important"?"important":"neutral"}">${n.impact==="important"?"⚡ Important":"• À surveiller"}</span>
        ${n.analysis?`<span class="pill ${n.analysis.direction==="positif"?"positive":n.analysis.direction==="négatif"?"negative":"neutral"}">${n.analysis.direction==="positif"?"↗":"↘"} ${n.analysis.score}</span>`:""}
        ${(n.entities||[]).slice(0,4).map(e=>`<span class="pill">${escape(e)}</span>`).join("")}
      </div>
      ${n.analysis?`<div class="analysisline">Impact ${escape(n.analysis.magnitude)} · confiance ${escape(n.analysis.confidence)}%</div>`:""}
    </div>
  </article>`).join(""):`<div class="empty">Aucune nouvelle trouvée.</div>`;
}
function escape(s){return String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]))}
function escapeAttr(s){return escape(s).replace(/javascript:/gi,"")}
function showWatch(){
  const arr=state.articles.filter(n=>(n.entities||[]).some(e=>state.watch.includes(e)));
  document.getElementById("feed").innerHTML=arr.length?arr.map(n=>`
  <article class="card"><a class="cardlink" href="${escapeAttr(n.url)}" target="_blank" rel="noopener">
  <div class="meta">${escape(n.source)} · ${escape(n.sector)}</div><h3>${escape(n.title)}</h3><div class="summary">${escape(n.summary||"")}</div>
  <div class="impact">${(n.entities||[]).filter(e=>state.watch.includes(e)).map(e=>`<span class="pill">${escape(e)}</span>`).join("")}</div>
  </a></article>`).join(""):`<div class="empty">Ajoute des entreprises dans ton suivi depuis Réglages V2.2.</div>`;
}
document.getElementById("search").addEventListener("input",e=>{state.query=e.target.value;render()});
document.querySelectorAll(".tab").forEach(b=>b.onclick=()=>{
  document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));b.classList.add("active");
  const p=b.dataset.page;
  if(p==="home"){document.querySelector(".hero h1").innerHTML="Ce qui bouge<br><span>aujourd’hui.</span>";chips();render();}
  else if(p==="sectors"){document.querySelector(".hero h1").innerHTML="Explorez les<br><span>secteurs.</span>";chips();render();}
  else if(p==="watch"){document.querySelector(".hero h1").innerHTML="Vos<br><span>suivis.</span>";showWatch();}
  else {document.querySelector(".hero h1").innerHTML="ÉconoPulse<br><span>V2.1.</span>";document.getElementById("feed").innerHTML='<div class="card"><h3>Sources V2.1</h3><p class="summary">Banque du Canada, Federal Reserve, BCE, Statistique Canada, FMI, Maison-Blanche et GDELT.</p><p class="summary">Les sources officielles sont identifiées séparément des sources agrégées.</p></div>';}
});

function openArticle(id){
  const n=state.articles.find(x=>x.id===id);
  if(!n) return;
  const x=n.analysis||{};
  document.getElementById("modalBody").innerHTML=`
    <div class="meta">${escape(n.sector)} · ${escape(n.source)}</div>
    <h2>${escape(n.title)}</h2>
    <p>${escape(n.summary||"")}</p>
    <h4>Analyse ÉconoPulse</h4>
    <div class="analysisbox">
      <div class="score">${x.score??"—"} <small>/100</small></div>
      <div><b>Impact ${escape(x.direction||"—")}</b><br>Intensité ${escape(x.magnitude||"—")} · confiance ${escape(x.confidence||"—")}%</div>
    </div>
    <p>${escape(x.explanation||"Analyse en attente.")}</p>
    ${x.potentialWinners?.length?`<h4>Potentiellement favorisées</h4><div class="impact">${x.potentialWinners.map(e=>`<span class="pill positive">${escape(e)}</span>`).join("")}</div>`:""}
    ${x.potentialRisks?.length?`<h4>Potentiellement exposées</h4><div class="impact">${x.potentialRisks.map(e=>`<span class="pill negative">${escape(e)}</span>`).join("")}</div>`:""}
    <p class="disclaimer">${escape(x.disclaimer||"Analyse indicative.")}</p>
    <a class="brief" href="${escapeAttr(n.url)}" target="_blank" rel="noopener">Lire la source ↗</a>`;
  document.getElementById("modal").classList.remove("hidden");
}
function closeModal(){document.getElementById("modal").classList.add("hidden")}

loadNews();
