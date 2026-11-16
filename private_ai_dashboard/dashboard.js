"use strict";
/*
 * Private AI Data Lineage prototype.
 * This file uses GENERATED SYNTHETIC DATA ONLY. No API, network, localStorage,
 * credentials, third-party analytics, cookie, user-provided HTML or live auth.
 * Never treat the demo persona dropdown as a real authorization system.
 */
const DEMO = [
  {id:"ev_090",time:"2026-11-16T13:46:16Z",asset:"doc_a01",actor:"user_104",agent:"agent_ocr",origin:"Portal klienta",destination:"Zasobnik organizacji",action:"Odebrano dokument",status:"success",proof:"observed",region:"eu-central-1",trace:"trace_101"},
  {id:"ev_091",time:"2026-11-16T13:46:17Z",asset:"doc_a01",actor:"user_104",agent:"agent_ocr",origin:"Zasobnik organizacji",destination:"Brama polityk",action:"Autoryzacja operacji",status:"success",proof:"observed",region:"eu-central-1",trace:"trace_102"},
  {id:"ev_092",time:"2026-11-16T13:46:18Z",asset:"doc_a01",actor:"user_104",agent:"agent_ocr",origin:"Brama polityk",destination:"AWS Bedrock / UE",action:"Analiza dokumentu",status:"success",proof:"observed",region:"eu-central-1",trace:"trace_103"},
  {id:"ev_093",time:"2026-11-16T13:46:20Z",asset:"doc_a01",actor:"user_104",agent:"agent_ocr",origin:"AWS Bedrock / UE",destination:"Rejestr audytu",action:"Zapis zdarzenia",status:"success",proof:"declared",region:"eu-central-1",trace:"trace_104"},
  {id:"ev_094",time:"2026-11-16T13:40:02Z",asset:"doc_b02",actor:"user_202",agent:"agent_assistant",origin:"API organizacji",destination:"Brama polityk",action:"Autoryzacja operacji",status:"success",proof:"observed",region:"eu-central-1",trace:"trace_201"},
  {id:"ev_095",time:"2026-11-16T13:40:03Z",asset:"doc_b02",actor:"user_202",agent:"agent_assistant",origin:"Brama polityk",destination:"Zablokowane",action:"Próba niedozwolonego wysłania",status:"blocked",proof:"observed",region:"—",trace:"trace_202"},
  {id:"ev_096",time:"2026-11-16T13:32:27Z",asset:"doc_c03",actor:"user_104",agent:"agent_ocr",origin:"Portal klienta",destination:"Brama polityk",action:"Autoryzacja operacji",status:"success",proof:"observed",region:"eu-central-1",trace:"trace_301"},
  {id:"ev_097",time:"2026-11-16T13:32:29Z",asset:"doc_c03",actor:"user_104",agent:"agent_ocr",origin:"Brama polityk",destination:"AWS Bedrock / UE",action:"Analiza dokumentu",status:"success",proof:"unknown",region:"eu-central-1",trace:"trace_302"},
  {id:"ev_098",time:"2026-11-16T13:24:40Z",asset:"doc_d04",actor:"user_305",agent:"agent_forms",origin:"API organizacji",destination:"Zasobnik organizacji",action:"Odebrano dokument",status:"success",proof:"observed",region:"eu-central-1",trace:"trace_401"},
  {id:"ev_099",time:"2026-11-16T13:24:42Z",asset:"doc_d04",actor:"user_305",agent:"agent_forms",origin:"Zasobnik organizacji",destination:"Brama polityk",action:"Autoryzacja operacji",status:"pending",proof:"declared",region:"eu-central-1",trace:"trace_402"},
  {id:"ev_100",time:"2026-11-16T13:16:11Z",asset:"doc_e05",actor:"user_202",agent:"agent_assistant",origin:"Brama polityk",destination:"Zablokowane",action:"Brak uprawnień agenta",status:"blocked",proof:"observed",region:"—",trace:"trace_501"},
  {id:"ev_101",time:"2026-11-16T13:09:00Z",asset:"doc_f06",actor:"user_305",agent:"agent_ocr",origin:"API organizacji",destination:"Brama polityk",action:"Ustalanie źródła",status:"error",proof:"unknown",region:"—",trace:"trace_601"}
];
const VIEW_NAMES = {overview:"Centrum dowodzenia",ledger:"Dziennik zdarzeń",incidents:"Incydenty i blokady"};
const STATUS = {success:"Zakończone",blocked:"Zablokowane",pending:"W toku",error:"Błąd"};
const PROOF = {observed:"Zarejestrowane",declared:"Deklarowane",unknown:"Brak dowodu"};
const state = {view:"overview",persona:"auditor",term:"",result:"all",proof:"all",selected:"ev_095"};
const $ = id => document.getElementById(id);
const cell = (tag,text,cls) => {const x=document.createElement(tag);if(cls)x.className=cls;x.textContent=String(text);return x};
const localTime = iso => new Intl.DateTimeFormat("pl-PL",{timeZone:"Europe/Warsaw",day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}).format(new Date(iso));

function scopedData(){
  // The role selector ONLY simulates presentation. Real server MUST authorize.
  return DEMO.filter(e=>state.persona!=="operator" || e.actor==="user_104");
}
function visibleData(){
  let rows=scopedData();
  if(state.view==="incidents")rows=rows.filter(e=>e.status==="blocked"||e.status==="error"||e.proof==="unknown");
  if(state.result!=="all")rows=rows.filter(e=>e.status===state.result);
  if(state.proof!=="all")rows=rows.filter(e=>e.proof===state.proof);
  if(state.term)rows=rows.filter(e=>[e.id,e.asset,e.actor,e.agent,e.origin,e.destination,e.action,e.region].join(" ").toLowerCase().includes(state.term.toLowerCase()));
  return rows.slice().sort((a,b)=>b.time.localeCompare(a.time));
}
function updateMetrics(){
  const rows=visibleData();
  $("metric-all").textContent=rows.length;
  $("metric-success").textContent=rows.filter(e=>e.status==="success").length;
  $("metric-denied").textContent=rows.filter(e=>e.status==="blocked").length;
  $("metric-unknown").textContent=rows.filter(e=>e.proof==="unknown").length;
  $("count-label").textContent=rows.length+" zdarzeń";
  $("footer-count").textContent=rows.length+" widocznych zdarzeń";
  $("nav-alert-count").textContent=scopedData().filter(e=>e.status==="blocked"||e.status==="error").length;
}
function renderDetails(rows){
  const item=rows.find(e=>e.id===state.selected)||rows[0];
  const section=$("detail-fields");
  section.replaceChildren();
  if(!item){
    section.appendChild(cell("p","Brak danych dla wybranych filtrów.","empty"));
    $("detail-result").textContent="Brak zdarzenia";$("flow-selected").textContent="—";return;
  }
  state.selected=item.id;
  $("detail-result").textContent=STATUS[item.status];
  const fields=[
    ["Identyfikator zdarzenia",item.id],["Dokument (pseudonim)",item.asset],
    ["Użytkownik (pseudonim)",item.actor],["Agent wykonujący operację",item.agent],
    ["Źródło",item.origin],["Cel operacji",item.destination],
    ["Wynik polityki",STATUS[item.status]],["Region wykonania",item.region],
    ["Ślad metadanych",item.trace],["Dowód",PROOF[item.proof]],
  ];
  fields.forEach(([label,value])=>{const box=cell("div","","field");box.append(cell("small",label),cell("strong",value));section.appendChild(box)});
  $("flow-source").textContent=item.origin;
  $("flow-target").textContent=item.destination;
  $("flow-region").textContent=item.region==="—"?"Brak przekazania / brak danych":item.region;
  $("flow-evidence").textContent=PROOF[item.proof];
  $("flow-selected").textContent=item.id+" · "+item.asset;
}
function renderTable(){
  const rows=visibleData();
  const tbody=$("events-body");tbody.replaceChildren();
  for(const e of rows){
    const tr=document.createElement("tr");tr.tabIndex=0;tr.setAttribute("aria-label","Pokaż ślad "+e.id);
    if(e.id===state.selected)tr.className="selected";
    const a=cell("td","");a.append(cell("strong",e.id),cell("small",localTime(e.time)));
    const b=cell("td","");b.append(cell("strong",e.asset),cell("small",e.actor+" · "+e.agent));
    const c=cell("td","");c.append(cell("strong",e.origin),cell("small","→ "+e.destination));
    const d=cell("td",e.action);
    const t=cell("td","");t.append(cell("span",STATUS[e.status],"event-tag "+e.status));
    const p=cell("td","");p.append(cell("span",PROOF[e.proof],"evidence-tag "+e.proof));
    tr.append(a,b,c,d,t,p);
    const activate=()=>{state.selected=e.id;renderTable();$("details-section").scrollIntoView({behavior:"smooth",block:"nearest"})};
    tr.addEventListener("click",activate);
    tr.addEventListener("keydown",ev=>{if(ev.key==="Enter"||ev.key===" "){ev.preventDefault();activate()}});
    tbody.appendChild(tr);
  }
  if(!rows.length){const tr=document.createElement("tr");const td=cell("td","Brak zdarzeń spełniających filtry.");td.colSpan=6;tr.appendChild(td);tbody.appendChild(tr)}
  updateMetrics();renderDetails(rows);
}
function switchView(view){
  state.view=view;
  const isOverview=view==="overview";
  $("overview-section").classList.toggle("hidden",!isOverview);
  $("metrics-section").classList.toggle("hidden",view==="ledger");
  $("details-section").classList.toggle("hidden",view==="incidents");
  $("events-title").textContent=view==="incidents"?"Incydenty i sygnały ostrzegawcze":"Dziennik aktywności";
  $("page-title").textContent=view==="incidents"?"Wykrywamy i dokumentujemy odchylenia.":view==="ledger"?"Każda operacja pozostawia ślad.":"Widzisz, co dzieje się z Twoimi danymi.";
  $("crumb").textContent=VIEW_NAMES[view];
  document.querySelectorAll("[data-view]").forEach(b=>b.setAttribute("aria-current",b.dataset.view===view?"page":"false"));
  renderTable();
}
document.querySelectorAll("[data-view]").forEach(b=>b.addEventListener("click",()=>switchView(b.dataset.view)));
$("persona-select").addEventListener("change",ev=>{state.persona=ev.target.value;renderTable()});
$("filter-state").addEventListener("change",ev=>{state.result=ev.target.value;renderTable()});
$("filter-proof").addEventListener("change",ev=>{state.proof=ev.target.value;renderTable()});
$("search").addEventListener("input",ev=>{state.term=ev.target.value.trim();renderTable()});
$("export-btn").addEventListener("click",()=>{
  const payload={
    schema:"private-ai-synthetic-report-v1",generated_by:"local-demo",synthetic:true,
    note:"Only demo metadata, no production events; NOT audit certification",
    view:state.view,persona:state.persona,events:visibleData()
  };
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:"application/json"});
  const url=URL.createObjectURL(blob);
  const anchor=document.createElement("a");anchor.href=url;anchor.download="private-ai-demo-lineage.json";
  document.body.appendChild(anchor);anchor.click();anchor.remove();URL.revokeObjectURL(url);
});
switchView("overview");
