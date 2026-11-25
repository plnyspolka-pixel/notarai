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
  function podpowiedz(){
    const pole=r("rp-id"), usluga=r("rp-usluga").value;
    pole.placeholder=usluga==="uldk"?"np. Krzewina 134 lub pełny identyfikator":usluga==="krs"?"10 cyfr KRS":"10 cyfr NIP";
  }
  let wersjaZapytania=0;
  function uniewaznij(){wersjaZapytania++;r("rp-wynik").replaceChildren();}
  r("rp-usluga").addEventListener("change",()=>{podpowiedz();uniewaznij();});
  for(const id of ["rp-id","rp-data","rp-rejestr"]) r(id).addEventListener("input",uniewaznij);
  podpowiedz();
  function pokaz(d,usluga){
    const wynik=r("rp-wynik"), dane=d.dane;
    if(usluga!=="uldk"||!Array.isArray(dane?.kandydaci)){
      wynik.textContent=JSON.stringify(d,null,2);return;
    }
    wynik.replaceChildren();
    const opis=document.createElement("p");
    opis.textContent=dane.kandydaci.length?"Wybierz właściwą działkę. Następnie kliknij Szukaj, aby potwierdzić pełny identyfikator.":"Nie znaleziono działki w ULDK. Sprawdź numer i obręb.";
    wynik.append(opis);
    for(const k of dane.kandydaci){
      const przycisk=document.createElement("button");
      przycisk.type="button";
      przycisk.textContent=[k.id,k.region,k.commune,k.county,k.voivodeship].filter(Boolean).join(" — ");
      przycisk.addEventListener("click",()=>{
        r("rp-usluga").value="uldk";r("rp-id").value=k.id;podpowiedz();
        wynik.textContent="Wybrano "+k.id+". Kliknij Szukaj, aby pobrać szczegóły.";
        r("rp-szukaj").focus();
      });
      const wiersz=document.createElement("div");wiersz.append(przycisk);wynik.append(wiersz);
    }
  }
  r("rp-form").addEventListener("submit",async event=>{
    event.preventDefault();
    const wynik=r("rp-wynik"),btn=r("rp-szukaj");
    const wersja=++wersjaZapytania;
    btn.disabled=true;wynik.textContent="Pobieranie…";
    try{
      const usluga=r("rp-usluga").value;
      const d=await odpowiedz("/api/rejestry-panstwowe/publiczne/"+usluga,{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({identyfikator:r("rp-id").value.trim(),data:r("rp-data").value,rejestr:r("rp-rejestr").value,potwierdzam:true})
      });
      if(wersja===wersjaZapytania && r("rp-usluga").value===usluga) pokaz(d,usluga);
    }catch(e){if(wersja===wersjaZapytania) wynik.textContent=e.message;}finally{btn.disabled=false;}
  });
})();
