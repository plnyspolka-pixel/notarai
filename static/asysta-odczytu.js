/* Asysta odczytu aktu — only the user approves a change. No transcript persistence. */
"use strict";
const el = id => document.getElementById(id);
let caseId = "", sha = "", content = "", revision = "", socket = null, audio = null;
let mic = null, node = null, silent = null, live = false, last = "", transcript = [];
const KEY = "notarai_token";
const token = () => { try { return localStorage.getItem(KEY) || ""; } catch { return ""; } };
let refreshPromise = null;
async function refresh() {
  if (!refreshPromise) refreshPromise = fetch("/api/logowanie/odnow", {method:"POST"})
    .then(async r => {
      if (!r.ok) return false;
      const t = (await r.json()).token;
      try { localStorage.setItem(KEY,t); } catch {}
      return !!t;
    }).catch(() => false).finally(() => { refreshPromise = null; });
  return refreshPromise;
}
async function api(path, options = {}) {
  function call() {
    const headers = new Headers(options.headers || {});
    if (token()) headers.set("Authorization","Bearer " + token());
    return fetch(path, {...options,headers,cache:"no-store"});
  }
  let response = await call();
  if (response.status === 401 && await refresh()) response = await call();
  if (!response.ok) {
    let message = "Błąd " + response.status;
    try { const d = await response.json(); message = d.detail || message; } catch {}
    throw new Error(message);
  }
  return response;
}
const post = (path,body) => api(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
const status = (message, bad=false) => {
  el("status").textContent = message; el("status").style.color = bad ? "var(--warn)":"";
};
function controls() {
  el("start").disabled = !caseId || !sha || !el("consent").checked || live;
  el("stop").disabled = !live;
  el("suggest").disabled = !caseId || !sha;
  el("approve").disabled = !caseId || !sha;
}
async function listCases(){
  try {
    const items = await (await api("/api/sprawy")).json();
    const select = el("case"); select.replaceChildren();
    const none = new Option("Wybierz sprawę z projektem",""); select.add(none);
    for (const item of items.filter(x => x.etap >= 3)) {
      select.add(new Option(item.nazwa || item.sygnatura || item.id, item.id));
    }
    status("Wybierz sprawę i wczytaj projekt.");
  } catch (e) { status(e.message,true); }
}
function drawHistory(list) {
  const box = el("history"); box.replaceChildren();
  if (!list.length) { const li=document.createElement("li");li.textContent="Brak zatwierdzonych zmian.";box.append(li);return; }
  for (const entry of list.slice().reverse()) {
    const li=document.createElement("li");
    li.append(document.createTextNode((entry.mode === "projekt" ? "Wersja robocza" : "Notatka do oryginału") + " · " + entry.created.slice(0,16).replace("T"," ")));
    if(entry.mode === "projekt") {
      const b=document.createElement("button");b.type="button";b.className="secondary";b.textContent="Pobierz Word";
      b.addEventListener("click",()=>download(entry.id));li.append(" ",b);
    }
    box.append(li);
  }
}
async function openCase() {
  stopMic();
  const chosen = el("case").value;
  if (!chosen) { status("Wybierz sprawę.",true); return; }
  try {
    const result = await (await api("/api/asysta-odczytu/sprawy/"+encodeURIComponent(chosen))).json();
    caseId = chosen; sha=result.sha; content=result.tekst; revision="";
    el("akt").value=content; el("position").textContent="Wskazanie miejsca będzie orientacyjne.";
    drawHistory(result.rewizje || []);status("Załadowano projekt. Źródłowy Word pozostaje bez zmian.");
    const recent=(result.rewizje||[]).filter(x=>x.mode==="projekt").slice(-1)[0]; if(recent)revision=recent.id;
    el("consent").checked=false;
    controls();
  } catch(e){caseId="";sha="";content="";el("akt").value="";status(e.message,true);controls();}
}
function selectedText() {
  const field=el("akt");
  if(field.selectionStart===field.selectionEnd) return "";
  return field.value.slice(field.selectionStart,field.selectionEnd);
}
el("selection").addEventListener("click",()=>{
  const fragment=selectedText();
  if(!fragment) {status("Zaznacz fragment tekstu po lewej.",true);return;}
  el("before").value=fragment;
  el("after").value=fragment;
  showDiff();
});
function showDiff() {
  const old=el("before").value, now=el("after").value;
  const box=el("difference");box.replaceChildren();
  if(!old && !now)return;
  const del=document.createElement("del");del.textContent=old;
  const ins=document.createElement("ins");ins.textContent=now;
  box.append(del,ins);
}
el("preview").addEventListener("click",showDiff);
el("mode").addEventListener("change",()=>{
  el("approval-note").textContent = el("mode").value === "oryginal"
    ? "Oryginał: tylko notatka dla notariusza, bez jakiejkolwiek zmiany w dokumencie."
    : "Projekt: zatwierdzenie tworzy wersjonowany DOCX; plik źródłowy pozostaje bez zmian.";
});
el("suggest").addEventListener("click",async()=>{
  if(!caseId || !sha)return;
  const instruction=el("instruction").value.trim();
  if(instruction.length<3){status("Wpisz polecenie.",true);return;}
  el("suggest").disabled=true;
  status("Analizuję propozycję w Amazon Bedrock (UE)...");
  try {
    const result = await (await post("/api/asysta-odczytu/proponuj",{
      sprawa:caseId,sha,polecenie:instruction,fragment:selectedText()
    })).json();
    if(!result.ready){status("AI potrzebuje doprecyzowania: "+result.reason,true);return;}
    el("before").value=result.before;el("after").value=result.after;
    el("reason").value=result.reason;showDiff();
    status("Propozycja gotowa. Porównaj oba fragmenty i świadomie zatwierdź.");
  }catch(e){status(e.message,true);}finally{controls();}
});
el("approve").addEventListener("click",async()=>{
  if(!caseId || !sha)return;
  const before=el("before").value,after=el("after").value;
  if(!before.trim()||!after.trim()||before===after){status("Popraw dwa fragmenty przed zatwierdzeniem.",true);return;}
  if(content.split(before).length!==2){status("Stary fragment musi występować dokładnie raz w aktualnej treści.",true);return;}
  const mode=el("mode").value;
  const confirmation=mode==="oryginal"
    ? "Zapisać NOTATKĘ do oryginału? System nie naniesie poprawki na akt."
    : "Zatwierdzić osobną WERSJĘ ROBOCZĄ? Źródłowy projekt.docx pozostanie bez zmian.";
  if(!window.confirm(confirmation))return;
  el("approve").disabled=true;
  try{
    const result=await (await post("/api/asysta-odczytu/zatwierdz",{
      sprawa:caseId,sha,tryb:mode,przed:before,po:after,powod:el("reason").value
    })).json();
    sha=result.sha;content=result.tekst;el("akt").value=content;
    if(mode==="projekt")revision=result.id;
    el("before").value="";el("after").value="";el("difference").replaceChildren();
    status(result.informacja);
    const list=await (await api("/api/asysta-odczytu/sprawy/"+encodeURIComponent(caseId))).json();
    drawHistory(list.rewizje||[]);
  }catch(e){status(e.message,true);}finally{controls();}
});
async function download(id) {
  try {
    const resp=await api("/api/asysta-odczytu/sprawy/"+caseId+"/rewizje/"+id+".docx");
    const url=URL.createObjectURL(await resp.blob());
    const a=document.createElement("a");a.href=url;a.download="projekt-asysta-"+id+".docx";a.click();
    setTimeout(()=>URL.revokeObjectURL(url),10000);
  }catch(e){status(e.message,true);}
}
function showPosition(text) {
  // Heuristic only. Never claims compliance or verifies any paragraph was read.
  const words=(text.toLowerCase().match(/[a-ząćęłńóśźż0-9]{4,}/gu)||[]).slice(-5);
  if(words.length<3)return;
  const current=content.toLowerCase();
  const hit=words.findLast(w=>current.indexOf(w)>=0&&current.indexOf(w)===current.lastIndexOf(w));
  if(!hit)return;
  const index=current.indexOf(hit);
  const par=current.slice(0,index).match(/§\s*\d+[a-z]?/gu);
  el("position").textContent="Orientacyjne dopasowanie wypowiedzi: "+(par?.slice(-1)[0]||"fragment aktu")+". Nie stanowi potwierdzenia odczytania.";
}
function pushTranscript(text, id) {
  if(!text.trim())return;
  const previous=transcript[transcript.length-1];
  if(previous?.id===id)return;
  transcript.push({id,text});
  if(transcript.length>50)transcript.shift();
  last=text; el("copy-last").disabled=false;
  el("final").textContent=transcript.map(t=>t.text).join("\n").slice(-15000);
  el("partial").textContent="";showPosition(text);
  // Rozpoznajemy WYŁĄCZNIE sygnał możliwej poprawki. Nie wywołujemy
  // automatycznie Bedrock, nie zapisujemy dokumentu ani niczego nie akceptujemy.
  if (/\b(zmień|zmieniamy|popraw|zamiast|niech będzie|proszę zmienić|proszę poprawić)\b/iu.test(text)) {
    el("instruction").value=text;
    status("Wykryto możliwą poprawkę w wypowiedzi. Sprawdź ją i kliknij Przygotuj propozycję AI.");
  }
}
async function stopMic() {
  const ws=socket; socket=null;
  if(ws && ws.readyState===WebSocket.OPEN) { try{ws.send(JSON.stringify({type:"stop"}));}catch{} }
  if(node){ try{node.port.postMessage("stop");node.disconnect();}catch{} node=null; }
  if(silent){try{silent.disconnect();}catch{}silent=null;}
  if(audio){try{await audio.close();}catch{}audio=null;}
  if(mic){mic.getTracks().forEach(t=>t.stop());mic=null;}
  if(ws){setTimeout(()=>{if(ws.readyState<2)ws.close();},2000);}
  live=false; el("mic-status").textContent="Mikrofon wyłączony.";controls();
}
async function startMic() {
  if(live || !caseId || !el("consent").checked)return;
  live=true;controls();el("mic-status").textContent="Łączę z AWS Frankfurt...";
  try {
    if(!navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode)throw Error("Ta przeglądarka nie obsługuje AudioWorklet.");
    mic=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true},video:false});
    audio=new AudioContext();
    await audio.audioWorklet.addModule("/static/asysta-worklet.js");
    const source=audio.createMediaStreamSource(mic);
    node=new AudioWorkletNode(audio,"notarai-pcm");
    silent=audio.createGain();silent.gain.value=0;
    source.connect(node);node.connect(silent);silent.connect(audio.destination);
    await audio.resume();
    const protocol=location.protocol==="https:"?"wss:":"ws:";
    const ws=new WebSocket(protocol+"//"+location.host+"/api/asysta-odczytu/na-zywo");
    socket=ws;ws.binaryType="arraybuffer";
    ws.onopen=()=>{ws.send(JSON.stringify({type:"auth",jwt:token(),case:caseId}));};
    ws.onmessage=ev=>{
      let m;try{m=JSON.parse(ev.data);}catch{return;}
      if(m.type==="start"){el("mic-status").textContent="Nasłuch aktywny (Polski · Frankfurt).";return;}
      if(m.type==="transcript"){if(m.final)pushTranscript(m.text,m.id);else el("partial").textContent=m.text;return;}
      if(m.type==="error"){status(m.message,true);void stopMic();return;}
      if(m.type==="end"){void stopMic();}
    };
    ws.onerror=()=>{status("Błąd połączenia rozpoznawania mowy.",true);void stopMic();};
    ws.onclose=()=>{if(socket===ws){status("Sesja rozpoznawania mowy zakończona.");void stopMic();}};
    node.port.onmessage=event=>{
      if(socket===ws&&ws.readyState===WebSocket.OPEN&&ws.bufferedAmount<128000&&event.data instanceof ArrayBuffer)ws.send(event.data);
    };
  } catch (e) {status("Mikrofon: "+e.message,true);await stopMic();}
}
el("start").addEventListener("click",()=>{void startMic();});
el("stop").addEventListener("click",()=>{void stopMic();});
el("consent").addEventListener("change",controls);
el("load").addEventListener("click",()=>{void openCase();});
el("copy-last").addEventListener("click",()=>{el("instruction").value=last;});
el("clear-text").addEventListener("click",()=>{transcript=[];last="";el("final").textContent="Brak wypowiedzi.";el("partial").textContent="";el("copy-last").disabled=true;});
window.addEventListener("pagehide",()=>{void stopMic();});
controls();void listCases();
