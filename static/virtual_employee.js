"use strict";
const $ = id => document.getElementById(id);
const states = {
  queued: "W kolejce", waiting_for_approval: "Wymaga akceptacji",
  running: "Wykonywane", completed: "Zakończone",
  waiting_for_human: "Wymaga operatora", needs_reconciliation: "Do uzgodnienia",
  failed: "Błąd", cancelled: "Anulowane", denied: "Odmowa"
};
const token = () => { try { return localStorage.getItem("notarai_token") || ""; } catch { return ""; } };
function alertText(text) { $("alert").textContent = text; }
async function call(path, method="GET", body=null) {
  const t = token();
  if (!t) throw new Error("Zaloguj się najpierw w głównym panelu NotarAI.");
  const response = await fetch("/api/virtual-employee"+path, {
    method, credentials:"same-origin", cache:"no-store",
    headers: {"Authorization":"Bearer "+t, ...(body ? {"Content-Type":"application/json"} : {})},
    ...(body ? {body: JSON.stringify(body)} : {})
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Operacja niedostępna ("+response.status+")");
  return data;
}
async function refresh() {
  try {
    const [jobs, worker] = await Promise.all([call("/jobs"), call("/worker/status")]);
    $("workerState").textContent = worker.disabled ? "Wstrzymany" : "Aktywny";
    $("stopWorker").disabled = worker.disabled;
    $("startWorker").disabled = !worker.disabled;
    const body = $("rows");
    body.replaceChildren();
    const items = Array.isArray(jobs.jobs) ? jobs.jobs : [];
    if (!items.length) {
      const tr=document.createElement("tr"), td=document.createElement("td");
      td.colSpan=6; td.textContent="Nie ma jeszcze żadnych zadań"; tr.append(td);body.append(tr);
    }
    for (const item of items) {
      const tr=document.createElement("tr");
      const cell=(value)=>{ const td=document.createElement("td");td.textContent=String(value ?? "—");tr.append(td);return td; };
      cell(item.job_id);cell(item.app_id);cell(item.action);
      const st=cell("");const mark=document.createElement("span");
      mark.className="badge";mark.textContent=states[item.status]||item.status;st.append(mark);
      cell(item.created_at ? new Date(item.created_at*1000).toLocaleString("pl-PL") : "—");
      const actions=cell("");
      const add=(label,task)=>{const b=document.createElement("button");b.type="button";b.textContent=label;b.className="secondary";b.addEventListener("click",async()=>{try{await task();await refresh();}catch(e){alertText(e.message)}});actions.append(b);};
      if(item.status==="waiting_for_approval")add("Zatwierdź",async()=>{
        const preview=await call("/jobs/"+encodeURIComponent(item.job_id)+"/approval-preview");
        const decision=window.confirm(
          "Potwierdź dokładną treść zmiany w programie kancelaryjnym:\\n\\n"+
          "Program: "+preview.app_id+"\\nPole: "+preview.field+
          "\\nWartość: "+preview.value+"\\n\\nZatwierdzić wykonanie przez robota?"
        );
        if(!decision)return;
        await call("/jobs/"+encodeURIComponent(item.job_id)+"/approve","POST");
      });
      if(["queued","running","waiting_for_approval"].includes(item.status))add("Anuluj",()=>call("/jobs/"+encodeURIComponent(item.job_id)+"/cancel","POST"));
      if(item.status==="completed")add("Wynik",async()=>{
        const response=await call("/jobs/"+encodeURIComponent(item.job_id)+"/result");
        $("resultText").textContent=JSON.stringify(response.result,null,2);
        $("resultDialog").showModal();
      });
      body.append(tr);
    }
    alertText("Dane odświeżone. Zmiany dotyczą tylko zalogowanej kancelarii.");
  } catch(e) { alertText(e.message);$("stopWorker").disabled=true;$("startWorker").disabled=true; }
}
$("refresh").addEventListener("click",refresh);
$("newJob").elements.action.addEventListener("change",()=>{
  $("draftLabel").hidden=$("newJob").elements.action.value!=="fill_draft_field";
});
$("newJob").addEventListener("submit",async event=>{
  event.preventDefault();
  const form=$("newJob"), data=new FormData(form);
  const action=String(data.get("action"));
  const body={app_id:String(data.get("app_id")),action,field:String(data.get("field"))};
  if(action==="fill_draft_field")body.value=String(data.get("value"));
  try{await call("/jobs","POST",body);form.reset();$("draftLabel").hidden=true;await refresh();}
  catch(e){alertText(e.message);}
});
for(const [name,disabled] of [["stopWorker",true],["startWorker",false]]){
  $(name).addEventListener("click",async()=>{try{await call("/worker/status","PUT",{disabled});await refresh()}catch(e){alertText(e.message)}});
}
refresh();
