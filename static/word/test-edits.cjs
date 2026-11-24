const {test}=require("node:test");
const assert=require("node:assert/strict");
const {validate}=require("./edits.js");
const text="Paragraf pierwszy. Paragraf drugi.";
test("replace and append",()=>{
  assert.equal(validate(text,"document","",[{type:"replace",find:"pierwszy",text:"trzeci"},{type:"append",text:"Wstawka."}]),
    "Paragraf trzeci. Paragraf drugi.\nWstawka.");
});
test("reject ambiguous / stale / unknown operations",()=>{
  assert.throws(()=>validate(text,"document","",[{type:"delete",find:"Paragraf"}]));
  assert.throws(()=>validate(text,"document","",[{type:"delete",find:"nie istnieje"}]));
  assert.throws(()=>validate(text,"document","",[{type:"eval",find:"Paragraf pierwszy"}]));
});
test("selection can only edit selected fragment",()=>{
  assert.throws(()=>validate(text,"selection","Paragraf pierwszy",[{type:"delete",find:"drugi"}]));
});
test("formatting has narrow allowlist",()=>{
  assert.equal(validate(text,"document","",[{type:"format",find:"pierwszy",format:{bold:true,fontColor:"#2350CF"}}]),text);
  assert.throws(()=>validate(text,"document","",[{type:"format",find:"pierwszy",format:{onload:"bad"}}]));
});

test("rich text and tables",()=>{
  assert.equal(validate(text,"document","",[{type:"replace_html",find:"pierwszy",html:"<p><b>Ważne</b></p>"}]),text);
  assert.equal(validate(text,"document","",[{type:"insert_table_after",find:"pierwszy",table:[["A","B"],["1","2"]]}]),text);
  assert.throws(()=>validate(text,"document","",[{type:"replace_html",find:"pierwszy",html:"<img src='x'>"}]));
});

test("create document from blank page",()=>{
  assert.equal(validate("","document","",[{type:"append_html",html:"<p>Projekt aktu</p>"}]),"");
});
