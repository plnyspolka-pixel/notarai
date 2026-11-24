/* NotarAI Word: read, ask Bedrock, show operations, apply with WordApi.
   Only explicit user actions read/transmit documents. Never store JWT or acts. */
(function(){
"use strict";
const el=id=>document.getElementById(id);
const state={token:"",ready:false,busy:false,history:[],proposal:null,snapshot:null};
const $=(id)=>el(id);
function status(message,isError=false){$("state").textContent=message;$("state").classList.toggle("error",isError);}
function busy(v){state.busy=v;for(const id of ["propose","apply","reset"])$(id).disabled=v;}
function message(role,text){const div=document.createElement("div");div.className="message "+role;
  const strong=document.createElement("strong");strong.textContent=role==="user"?"Polecenie":"Asystent NotarAI";
  const body=document.createElement("span");body.textContent=text;
  div.append(strong,body);$("conversation").append(div);}
function errorText(err){return err&&err.message?err.message:String(err||"Nieznany błąd");}
async function api(path,body,token){
  const r=await fetch(path,{method:"POST",credentials:"same-origin",cache:"no-store",headers:{
    "Content-Type":"application/json",...(token?{"Authorization":"Bearer "+token}:{})
  },body:JSON.stringify(body)});
  const data=await r.json().catch(()=>({}));
  if(!r.ok)throw Error(typeof data.detail==="string"?data.detail:"Błąd usługi NotarAI ("+r.status+")");
  return data;
}
function invalidate(){state.proposal=null;state.snapshot=null;$("proposal-box").hidden=true;$("operations").replaceChildren();}
async function signIn(ev){ev.preventDefault();
  const form=$("login-form"),fields=new FormData(form);
  try{status("Logowanie do kancelarii…");
    const result=await api("/api/logowanie",{email:String(fields.get("email")),haslo:String(fields.get("password"))},"");
    if(!result.token)throw Error("Logowanie wymaga dodatkowego kroku. Zaloguj się w aplikacji NotarAI.");
    state.token=result.token;form.reset();$("login-panel").hidden=true;$("editor-panel").hidden=false;
    status("Zalogowano. Dokument zostanie wysłany do AI dopiero po Twoim kliknięciu.");
  }catch(e){status(errorText(e),true);}
}
async function signOut(){
  try{await api("/api/logowanie/wyloguj",{},"");}catch(_){}
  state.token="";state.history=[];invalidate();$("conversation").replaceChildren();
  $("editor-panel").hidden=true;$("login-panel").hidden=false;status("Wylogowano.");
}
async function readSnapshot(scope){
  let result=null;
  await Word.run(async ctx=>{
    const body=ctx.document.body,selection=ctx.document.getSelection();
    body.load("text");selection.load("text");await ctx.sync();
    result={body:body.text,selection:selection.text||"",scope};
  });
  if(!result.body.trim())throw Error("Dokument jest pusty.");
  if(result.body.length>100000)throw Error("Dokument przekracza 100 tys. znaków. Zaznacz mniejszy fragment i podziel edycję na etapy.");
  if(scope==="selection"&&!result.selection.trim())throw Error("Zaznacz fragment w Wordzie.");
  return result;
}
function render(ops){
  const place=$("operations");place.replaceChildren();
  const names={replace:"Zastąp tekst",delete:"Usuń tekst",insert_before:"Wstaw przed",insert_after:"Wstaw po",append:"Dodaj na końcu",format:"Zmień formatowanie",replace_html:"Zastąp treścią formatowaną",append_html:"Dodaj blok formatowany",insert_table_after:"Wstaw tabelę"};
  ops.forEach((op,i)=>{
    const card=document.createElement("div");card.className="edit";
    const header=document.createElement("label");header.className="edit-header";
    const input=document.createElement("input");input.type="checkbox";input.checked=true;input.dataset.index=i;input.className="pick";
    const title=document.createElement("span");title.textContent=(i+1)+". "+(names[op.type]||op.type);
    header.append(input,title);card.append(header);
    if(op.find){const before=document.createElement("pre");before.className="before";before.textContent="W dokumencie:\n"+op.find;card.append(before);}
    if(op.text){const after=document.createElement("pre");after.className="after";after.textContent="Proponowana treść:\n"+op.text;card.append(after);}
    if(op.html){const h=document.createElement("pre");h.className="after";h.textContent="Formatowana treść (HTML):\n"+op.html;card.append(h);}
    if(op.table){const tbl=document.createElement("pre");tbl.className="after";tbl.textContent="Tabela:\n"+op.table.map(row=>row.join(" | ")).join("\n");card.append(tbl);}
    if(op.format){const fmt=document.createElement("pre");fmt.textContent="Formatowanie:\n"+JSON.stringify(op.format);card.append(fmt);}
    place.append(card);
  });
}
async function propose(){
  if(!state.token){status("Najpierw się zaloguj.",true);return;}
  if(!state.ready){status("Office.js nie połączył się z Wordem.",true);return;}
  if(!$("draft").checked){status("Potwierdź, że dokument jest projektem lub kopią roboczą.",true);return;}
  const instruction=$("instruction").value.trim();
  if(instruction.length<3){status("Wpisz polecenie dla AI.",true);return;}
  busy(true);invalidate();
  try{
    status("Odczytuję dokument w Wordzie…");
    const snap=await readSnapshot($("scope").value);
    status("Przesyłam tekst do Bedrock w infrastrukturze NotarAI (UE) i przygotowuję propozycje…");
    const data=await api("/api/word/propozycja",{
      scope:snap.scope,document_text:snap.body,selection_text:snap.selection,
      instruction,draft_confirmed:true,history:state.history.slice(-8)
    },state.token);
    window.NotarAIWordEdits.validate(snap.body,snap.scope,snap.selection,data.operations);
    state.snapshot=snap;state.proposal=data;
    message("user",instruction);message("assistant",data.summary||"Przygotowano propozycje.");
    state.history.push({role:"user",text:instruction},{role:"assistant",text:data.summary||""});
    if(state.history.length>12)state.history.splice(0,state.history.length-12);
    $("summary").textContent=data.summary||"Przejrzyj każdą proponowaną poprawkę.";
    render(data.operations);$("proposal-box").hidden=!data.operations.length;
    status(data.operations.length?"Przejrzyj propozycje i zatwierdź wybrane zmiany.":"AI nie zaproponował zmian.");
  }catch(e){invalidate();status(errorText(e),true);}
  finally{busy(false);}
}
async function apply(){
  if(!state.proposal||!state.snapshot)return;
  if(!$("draft").checked){status("Nie można zmienić oryginału aktu. Potwierdź kopię roboczą.",true);return;}
  const picks=[...document.querySelectorAll(".pick:checked")].map(x=>Number(x.dataset.index));
  if(!picks.length){status("Zaznacz co najmniej jedną operację.",true);return;}
  const chosen=picks.map(i=>state.proposal.operations[i]);
  const snapshot=state.snapshot;
  try{window.NotarAIWordEdits.validate(snapshot.body,snapshot.scope,snapshot.selection,chosen);}
  catch(e){status(errorText(e),true);return;}
  if(!confirm("Zastosować "+chosen.length+" poprawek do projektu Word ze śledzeniem zmian?"))return;
  busy(true);
  try{
    status("Weryfikuję bieżący dokument i włączam śledzenie zmian…");
    await Word.run(async ctx=>{
      const body=ctx.document.body;body.load("text");await ctx.sync();
      if(body.text!==snapshot.body)throw Error("Dokument zmienił się od wygenerowania propozycji. Odczytaj go ponownie.");
      // WordApi 1.4 - fail closed, no edits without revision tracking.
      ctx.document.changeTrackingMode=Word.ChangeTrackingMode.trackAll;
      await ctx.sync();
      for(const op of chosen){
        if(op.type==="append_html"){
          body.insertHtml(op.html,"End");await ctx.sync();continue;
        }
        if(op.type==="append"){
          body.insertParagraph(op.text,"End");
          await ctx.sync();
          continue;
        }
        const matches=body.search(op.find,{matchCase:true,matchWholeWord:false,ignorePunct:false,ignoreSpace:false});
        matches.load("items/text");await ctx.sync();
        if(matches.items.length!==1||matches.items[0].text!==op.find)
          throw Error("Fragment nie jest jednoznaczny w Wordzie. Przerwano; sprawdź już zastosowane zmiany.");
        const range=matches.items[0];
        if(op.type==="replace_html")range.insertHtml(op.html,"Replace");
        else if(op.type==="insert_table_after")range.insertTable(op.table.length,op.table[0].length,"After",op.table);
        else if(op.type==="replace")range.insertText(op.text,"Replace");
        else if(op.type==="delete")range.insertText("","Replace");
        else if(op.type==="insert_before")range.insertText(op.text,"Before");
        else if(op.type==="insert_after")range.insertText(op.text,"After");
        else if(op.type==="format"){
          const f=op.format;
          if("bold" in f)range.font.bold=f.bold;
          if("italic" in f)range.font.italic=f.italic;
          if("underline" in f)range.font.underline=f.underline?"Single":"None";
          if("fontSize" in f)range.font.size=f.fontSize;
          if("fontColor" in f)range.font.color=f.fontColor;
          if("highlightColor" in f)range.font.highlightColor=f.highlightColor;
        }
        await ctx.sync();
      }
    });
    invalidate();
    status("Wprowadzono poprawki ze śledzeniem zmian. Przejrzyj je w Wordzie (Recenzja), a następnie zapisz projekt.");
  }catch(e){invalidate();status(errorText(e)+" Jeżeli część zmian została zastosowana, sprawdź dokument przed ponowną próbą.",true);}
  finally{busy(false);}
}
function start(){
  $("login-form").addEventListener("submit",signIn);
  $("logout").addEventListener("click",signOut);
  $("propose").addEventListener("click",propose);
  $("apply").addEventListener("click",apply);
  $("reset").addEventListener("click",()=>{state.history=[];invalidate();$("conversation").replaceChildren();status("Nowa rozmowa.");});
  $("scope").addEventListener("change",invalidate);
  $("select-all").addEventListener("click",()=>document.querySelectorAll(".pick").forEach(x=>x.checked=true));
  $("select-none").addEventListener("click",()=>document.querySelectorAll(".pick").forEach(x=>x.checked=false));
  if(!window.Office){status("Uruchom panel z Microsoft Word.",true);return;}
  Office.onReady(info=>{
    if(info.host!==Office.HostType.Word){status("Panel wymaga programu Word.",true);return;}
    if(!Office.context.requirements.isSetSupported("WordApi","1.4")){
      $("office-state").textContent="Nieobsługiwana wersja Word";
      status("Wymagany Word z WordApi 1.4 (śledzenie zmian). Aktualizacja programu jest konieczna.",true);
      return;
    }
    state.ready=true;$("office-state").textContent="Połączono z Word · tryb projektu";status("Zaloguj się kontem kancelarii.");
  }).catch(e=>status(errorText(e),true));
}
document.addEventListener("DOMContentLoaded",start);
})();