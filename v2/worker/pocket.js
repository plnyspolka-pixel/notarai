"use strict";
const el=id=>document.getElementById(id);
let token="",doc=null,scope="";
function status(s){el("status").textContent=s;}
async function call(path,method="GET",data){
  const headers={"Content-Type":"application/json"};
  if(token) headers.Authorization="Bearer "+token;
  const response=await fetch("/v2/"+path,{method,headers,cache:"no-store",credentials:"omit",body:data===undefined?undefined:JSON.stringify(data)});
  if(!response.ok) throw new Error(response.status===409?"Konflikt wersji: zachowano tekst w edytorze. Skopiuj go przed ponownym otwarciem dokumentu.":"Błąd HTTP "+response.status);
  return response.json();
}
function run(fn){return async()=>{try{await fn()}catch(e){status(e.message)}}}
function clear(){doc=null;el("name").value="";el("body").value="";}
async function refresh(){
  const items=await call("documents");el("docs").replaceChildren();
  for(const item of items){const li=document.createElement("li"),b=document.createElement("button");b.textContent=item.id.slice(0,8)+" · v"+item.version;
    b.onclick=run(async()=>{const d=await call("documents/"+item.id);
      if(!/\.txt$/i.test(d.name)) throw new Error("Prototyp edytuje wyłącznie TXT.");
      const text=new TextDecoder("utf-8",{fatal:true}).decode(Uint8Array.from(atob(d.content_b64),c=>c.charCodeAt(0)));
      doc=d;el("name").value=d.name;el("body").value=text;status("Otwarto wersję "+d.version);});
    li.append(b);el("docs").append(li);}
}
el("pair").onclick=run(async()=>{const code=el("code").value;el("code").value="";const d=await call("devices/redeem","POST",{code});token=d.token;scope=d.scope;el("save").disabled=scope!=="write";clear();status("Połączono: "+scope);await refresh();});
el("refresh").onclick=run(refresh);
el("logout").onclick=()=>{token="";scope="";clear();el("docs").replaceChildren();el("save").disabled=true;status("Rozłączono");};
el("new").onclick=clear;
el("save").disabled=true;
el("save").onclick=run(async()=>{if(scope!=="write")throw new Error("Brak uprawnień");if(!/\.txt$/i.test(el("name").value))throw new Error("Wymagane rozszerzenie .txt");
  const bytes=new TextEncoder().encode(el("body").value);let binary="";for(const b of bytes)binary+=String.fromCharCode(b);
  const d=await call("documents","POST",{id:doc?.id||null,expected_version:doc?.version||0,name:el("name").value,content_b64:btoa(binary)});
  doc=d;status("Zapisano wersję "+d.version);await refresh();});
