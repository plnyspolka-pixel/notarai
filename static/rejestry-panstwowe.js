(() => {
  "use strict";
  const r=id=>document.getElementById(id);
  if (!r("rp-katalog-btn")) return;
  const opisy={publiczne_api:"Publiczny interfejs",portal:"Portal urzędowy",wniosek:"Wniosek urzędowy",wymaga_dostepu:"Wymaga indywidualnego dostępu",wymaga_potwierdzenia:"Najpierw potwierdzenie uprawnienia",istniejacy_modul:"Istniejący moduł – sprawdź konfigurację"};
  async function odpowiedz(url,opcje){
    const resp=await api(url,opcje);
    if(!resp.ok) throw new Error("Operacja nie powiodła się ("+resp.status+").");
    return resp.json();
  }
  r("rp-katalog-btn").addEventListener("click",async()=>{
    const lista=r("rp-lista"), btn=r("rp-katalog-btn");
    btn.disabled=true;
    try{
      const wynik=await odpowiedz("/api/rejestry-panstwowe/katalog");
      lista.replaceChildren();
      for(const x of wynik.rejestry){
        const p=document.createElement("p"), a=document.createElement("a");
        a.href=x.url; a.target="_blank"; a.rel="noopener noreferrer"; a.textContent=x.nazwa;
        p.append(a,document.createTextNode(" — "+(opisy[x.sciezka]||x.sciezka)));
        lista.append(p);
      }
    }catch(e){lista.textContent=e.message;}finally{btn.disabled=false;}
  });
  r("rp-form").addEventListener("submit",async event=>{
    event.preventDefault();
    const wynik=r("rp-wynik"),btn=r("rp-szukaj");
    btn.disabled=true;wynik.textContent="Pobieranie…";
    try{
      const d=await odpowiedz("/api/rejestry-panstwowe/publiczne/"+r("rp-usluga").value,{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({identyfikator:r("rp-id").value.trim(),data:r("rp-data").value,rejestr:r("rp-rejestr").value,potwierdzam:true})
      });
      wynik.textContent=JSON.stringify(d,null,2);
    }catch(e){wynik.textContent=e.message;}finally{btn.disabled=false;}
  });
})();
