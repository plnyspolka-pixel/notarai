/* Pure helpers shared by Office add-in and Node tests. No document content is logged. */
(function(root,factory) {
  const lib = factory();
  if(typeof module==="object"&&module.exports) module.exports=lib;
  root.NotarAIWordEdits=lib;
})(typeof globalThis!=="undefined"?globalThis:this,function() {
  "use strict";
  const types=new Set(["replace","insert_before","insert_after","delete","format","append"]);
  function validate(body,scope,selection,operations) {
    if(typeof body!=="string"||!body.length)throw Error("Nie ma tekstu dokumentu.");
    if(!Array.isArray(operations)||operations.length>30)throw Error("Nieprawidłowa lista zmian.");
    let shadow=body;
    for(const op of operations){
      if(!op||!types.has(op.type))throw Error("Nieobsługiwana operacja AI.");
      if(op.type==="append"){
        if(scope!=="document")throw Error("Wstawka poza zaznaczeniem.");
        if(!op.text||op.text.length>15000)throw Error("Nieprawidłowa wstawka.");
        shadow+="\n"+op.text;continue;
      }
      if(typeof op.find!=="string"||!op.find.trim()||op.find.length>1500||/[\r\n]/.test(op.find))
        throw Error("Niepoprawna kotwica tekstowa.");
      if(scope==="selection"&&!selection.includes(op.find))
        throw Error("Zmiana poza zaznaczeniem.");
      const at=shadow.indexOf(op.find);
      if(at<0||shadow.indexOf(op.find,at+1)!==-1)
        throw Error("Miejsce edycji nie jest jednoznaczne.");
      if(["replace","insert_before","insert_after"].includes(op.type)
         &&(typeof op.text!=="string"||!op.text.trim()||op.text.length>15000))
        throw Error("Niepoprawny tekst zmiany.");
      if(op.type==="replace")shadow=shadow.slice(0,at)+op.text+shadow.slice(at+op.find.length);
      if(op.type==="delete")shadow=shadow.slice(0,at)+shadow.slice(at+op.find.length);
      if(op.type==="insert_before")shadow=shadow.slice(0,at)+op.text+shadow.slice(at);
      if(op.type==="insert_after")shadow=shadow.slice(0,at+op.find.length)+op.text+shadow.slice(at+op.find.length);
      if(op.type==="format"){
        if(!op.format||typeof op.format!=="object")throw Error("Brak danych formatowania.");
        for(const [k,v] of Object.entries(op.format)){
          if(["bold","italic","underline"].includes(k)){if(typeof v!=="boolean")throw Error("Formatowanie bool.");}
          else if(k==="fontSize"){if(typeof v!=="number"||v<8||v>72)throw Error("Rozmiar czcionki.");}
          else if(["fontColor","highlightColor"].includes(k)){if(typeof v!=="string"||!/^#[0-9a-fA-F]{6}$/.test(v))throw Error("Kolor.");}
          else throw Error("Niedozwolone formatowanie.");
        }
      }
    }
    return shadow;
  }
  return {validate};
});