/* Część „Ten komputer” strony notarai.pl/bezpieczenstwo/: rysowanie wyniku skanu z skan.js. */
'use strict';
document.addEventListener('DOMContentLoaded', () => {
  const S = window.Skan; if (!S) return;
  const $ = id => document.getElementById(id);
  const redukcja = window.matchMedia && window.matchMedia('(prefers-reduced-motion:reduce)').matches;
  const stan = { karty: [], samoaudyt: {} };

  function ikonaChip(w){ return {ok:'OK',uwaga:'Do poprawy',alarm:'Zagrożenie',info:'Info'}[w] || 'Info'; }

  function rysujKarta(k){
    const el = document.createElement('article');
    el.className = 'bz-karta ' + k.werdykt;
    const h = document.createElement('h3');
    const t = document.createElement('span'); t.textContent = k.tytul;
    const chip = document.createElement('span'); chip.className = 'bz-chip ' + k.werdykt; chip.textContent = ikonaChip(k.werdykt);
    h.append(t, chip); el.append(h);
    const p = document.createElement('p'); p.textContent = k.opis || ''; el.append(p);
    if (Array.isArray(k.dane) && k.dane.length){
      const dl = document.createElement('dl');
      k.dane.forEach(([n,v]) => { const dt=document.createElement('dt'); dt.textContent=n; const dd=document.createElement('dd'); dd.textContent=v; dl.append(dt,dd); });
      el.append(dl);
    }
    if (k.czyn){ const p2=document.createElement('p'); p2.style.marginTop='8px'; p2.style.color='var(--tekst)';
      p2.innerHTML='<b>Co zrobić:</b> '; p2.append(document.createTextNode(k.czyn)); el.append(p2); }
    return el;
  }

  function kolorPoziom(poz){ return poz==='ok'?'var(--ok)':poz==='uwaga'?'var(--uwaga)':'var(--alarm)'; }

  function przeliczWynik(odrazu){
    const w = S.policzWynik(stan.karty, stan.samoaudyt);
    const ring = $('bz-pierscien');
    ring.style.setProperty('--kolor', kolorPoziom(w.poziom));
    const docel = w.pkt; let od = 0;
    if (redukcja || odrazu){ ring.style.setProperty('--p', docel); $('bz-pkt').textContent = docel; }
    else {
      $('bz-pkt').textContent = 0; ring.style.setProperty('--p', 0);
      const krok = Math.max(1, Math.round(docel/28));
      const anim = setInterval(()=>{ od=Math.min(docel,od+krok); ring.style.setProperty('--p',od); $('bz-pkt').textContent=od; if(od>=docel) clearInterval(anim); }, 22);
    }
    const plak = $('bz-plakietka');
    plak.textContent = ikonaChip(w.poziom);
    plak.style.background = w.poziom==='ok'?'var(--ok-tlo)':w.poziom==='uwaga'?'var(--uwaga-tlo)':'var(--alarm-tlo)';
    plak.style.color = kolorPoziom(w.poziom);
    $('bz-naglowek').textContent = w.naglowek;
    $('bz-podpis').textContent = w.pkt>=80 ? 'Dobra podstawa. Zamknij ostatnie luki, żeby mieć spokój.' :
      w.pkt>=55 ? 'Kilka rzeczy wymaga pilnej reakcji. Plan naprawy masz niżej.' :
      'To realne ryzyko wycieku akt i danych klientów. Zacznij od punktów z planu naprawy.';
    rysujZagrozenia();
    rysujPlan();
  }

  function rysujZagrozenia(){
    const box = $('bz-zagr-lista'); box.textContent='';
    const etykieta = { alarm:'Wysokie ryzyko', uwaga:'Średnie ryzyko', ok:'Na razie czysto' };
    S.ocenZagrozenia(stan.karty, stan.samoaudyt).forEach(z => {
      const el=document.createElement('article'); el.className='bz-zagr-k '+z.poziom;
      const h=document.createElement('h3'); const t=document.createElement('span'); t.textContent=z.nazwa;
      const chip=document.createElement('span'); chip.className='bz-chip '+z.poziom; chip.textContent=etykieta[z.poziom];
      h.append(t,chip); el.append(h);
      if (z.powody.length){
        const typ=document.createElement('p'); typ.className='typ';
        const tb=document.createElement('b'); tb.textContent='Jak wygląda atak: ';
        typ.append(tb, document.createTextNode(z.typ)); el.append(typ);
        const ul=document.createElement('ul'); ul.className='pow';
        const naglP=document.createElement('li'); naglP.style.listStyle='none'; naglP.style.marginLeft='-20px'; naglP.style.color='var(--tekst3)'; naglP.textContent='Dlaczego akurat u Ciebie:';
        ul.append(naglP);
        z.powody.forEach(p=>{ const li=document.createElement('li'); li.textContent=p; ul.append(li); });
        el.append(ul);
        const meta=document.createElement('p'); meta.className='meta'; const kol=kolorPoziom(z.poziom);
        const s1=document.createElement('span'); s1.textContent='Łatwość ataku: ';
        const b1=document.createElement('b'); b1.textContent=z.latwosc; b1.style.color=kol;
        const s2=document.createElement('span'); s2.textContent='   ·   Skuteczność: ';
        const b2=document.createElement('b'); b2.textContent=z.skutecznosc; b2.style.color=kol;
        meta.append(s1,b1,s2,b2); el.append(meta);
        const kons=document.createElement('p'); kons.className='kons';
        const b=document.createElement('strong'); b.textContent='Jeśli się uda: ';
        kons.append(b, document.createTextNode(z.konsekwencja)); el.append(kons);
        if (Array.isArray(z.rozwiazanie) && z.rozwiazanie.length){
          const rozw=document.createElement('div'); rozw.className='rozw';
          const rt=document.createElement('p'); rt.className='rozw-tyt'; rt.textContent='Jak notarai to rozwiązuje:'; rozw.append(rt);
          const rul=document.createElement('ul'); z.rozwiazanie.forEach(r=>{ const li=document.createElement('li'); li.textContent=r; rul.append(li); }); rozw.append(rul);
          el.append(rozw);
        }
      } else {
        const p=document.createElement('p'); p.className='spok';
        p.textContent='Na podstawie tego, co wiemy, nie widać tu luki — o ile samoaudyt niżej jest szczery.'; el.append(p);
      }
      box.append(el);
    });
  }

  function rysujPlan(){
    const kroki = [];
    for (const k of stan.karty) if ((k.werdykt==='alarm'||k.werdykt==='uwaga') && k.czyn) kroki.push([k.tytul, k.czyn, k.werdykt]);
    for (const poz of S.SAMOAUDYT) if (stan.samoaudyt[poz.id]===false) kroki.push([poz.pytanie.replace(/\?$/,''), poz.gdyNie, 'alarm']);
    const sek = $('bz-plan'), lista = $('bz-plan-lista'); lista.textContent='';
    if (!kroki.length){ sek.hidden=true; return; }
    kroki.sort((a,b)=> (a[2]==='alarm'?0:1)-(b[2]==='alarm'?0:1));
    kroki.forEach(([tyt,op]) => { const li=document.createElement('li'); const b=document.createElement('b'); b.textContent=tyt+'. '; li.append(b, document.createTextNode(op)); lista.append(li); });
    sek.hidden=false;
  }

  function rysujSamoaudyt(){
    const box = $('bz-sa'); box.textContent='';
    S.SAMOAUDYT.forEach(poz => {
      const fs=document.createElement('fieldset'); const lg=document.createElement('legend'); lg.textContent=poz.pytanie; fs.append(lg);
      const opcje=document.createElement('div'); opcje.className='sa-opcje'; opcje.setAttribute('role','group'); opcje.setAttribute('aria-label',poz.pytanie);
      const uwaga=document.createElement('p'); uwaga.className='sa-uwaga'; uwaga.hidden=true; uwaga.textContent=poz.gdyNie;
      const jakEl=document.createElement('div'); jakEl.className='sa-jak'; jakEl.hidden=true;
      if (Array.isArray(poz.jak)){
        const h=document.createElement('p'); h.className='sa-jak-tyt'; h.textContent='Jak to zrobić samemu:'; jakEl.append(h);
        const ol=document.createElement('ol'); poz.jak.forEach(k=>{ const li=document.createElement('li'); li.textContent=k; ol.append(li); }); jakEl.append(ol);
        if (poz.ustawienia){ const a=document.createElement('a'); a.href=poz.ustawienia; a.className='sa-jak-link'; a.rel='noopener'; a.textContent='↗ '+(poz.ustawieniaTekst||'Otwórz ustawienia')+' (Windows)'; jakEl.append(a); }
      }
      const bTak=document.createElement('button'); bTak.type='button'; bTak.className='tak'; bTak.textContent='Tak'; bTak.setAttribute('aria-pressed','false');
      const bNie=document.createElement('button'); bNie.type='button'; bNie.className='nie'; bNie.textContent='Nie'; bNie.setAttribute('aria-pressed','false');
      bTak.addEventListener('click',()=>{ stan.samoaudyt[poz.id]=true; bTak.setAttribute('aria-pressed','true'); bNie.setAttribute('aria-pressed','false'); uwaga.hidden=true; jakEl.hidden=true; przeliczWynik(true); });
      bNie.addEventListener('click',()=>{ stan.samoaudyt[poz.id]=false; bNie.setAttribute('aria-pressed','true'); bTak.setAttribute('aria-pressed','false'); uwaga.hidden=false; jakEl.hidden=false; przeliczWynik(true); });
      opcje.append(bTak,bNie); fs.append(opcje,uwaga,jakEl); box.append(fs);
    });
  }

  async function uruchom(){
    $('bz-start').disabled=true; $('bz-start').textContent='Skanowanie…';
    stan.karty = [];
    const kroki=[
      ['System operacyjny', S.wykryjSystem],
      ['Przeglądarka', ()=>Promise.resolve(S.wykryjPrzegladarke())],
      ['Połączenie', ()=>Promise.resolve(S.wykryjPolaczenie())],
      ['Ślad w sieci', ()=>Promise.resolve(S.wykryjSlad())],
      ['Adres widoczny z internetu', S.wykryjIP],
    ];
    const lista=$('bz-skan-lista'); lista.textContent=''; $('bz-skan').hidden=false;
    const liEl=kroki.map(([n])=>{ const li=document.createElement('li'); const d=document.createElement('span'); d.className='bz-kropka'; const s=document.createElement('span'); s.textContent=n; li.append(d,s); lista.append(li); return li; });
    for (let i=0;i<kroki.length;i++){
      if (!redukcja) await new Promise(r=>setTimeout(r,320));
      let wynik=null; try { wynik=await kroki[i][1](); } catch(_){ wynik=null; }
      if (wynik) stan.karty.push(wynik);
      liEl[i].classList.add('gotowe');
    }
    // render wyników
    const karty=$('bz-karty'); karty.textContent='';
    stan.karty.forEach(k=> karty.append(rysujKarta(k)));
    rysujSamoaudyt();
    $('bz-wynik').hidden=false;
    przeliczWynik();
    $('bz-start').disabled=false; $('bz-start').textContent='Skanuj ponownie';
    if (!redukcja) setTimeout(()=>{ $('bz-wynik').scrollIntoView({behavior:'smooth',block:'start'}); }, 120);
  }

  $('bz-start').addEventListener('click', uruchom);

  // Pasywny rekonesans — odpala się od razu na wejściu, bez kliknięcia.
  // Pokazuje, ile widać z samego połączenia i przeglądarki.
  function prawdLokalizacja(){
    let tz=''; try { tz=Intl.DateTimeFormat().resolvedOptions().timeZone||''; } catch(_){}
    const miasto = tz.includes('/') ? tz.split('/').pop().replace(/_/g,' ') : '';
    const lang=(navigator.language||'').toLowerCase();
    const kraje={ 'pl':'Polska','de':'Niemcy','cs':'Czechy','sk':'Słowacja','uk':'Ukraina','lt':'Litwa','en-gb':'Wielka Brytania' };
    const kraj = kraje[lang] || kraje[lang.split('-')[0]] || '';
    const mm={ 'Warsaw':'Warszawa','Berlin':'Berlin','Prague':'Praga','Kiev':'Kijów','Kyiv':'Kijów','London':'Londyn','Vilnius':'Wilno' };
    const miastoPl = mm[miasto]||miasto;
    return [kraj, miastoPl].filter(Boolean).join(' · ') || tz || 'nieznana';
  }
  async function reconPasywny(){
    const dl=$('bz-recon-dl'); if(!dl) return;
    const wiersz=(n,v,kl)=>{ if(v===undefined||v===null||v==='') return; const dt=document.createElement('dt'); dt.textContent=n; const dd=document.createElement('dd'); dd.textContent=v; if(kl) dd.className=kl; dl.append(dt,dd); };
    let sys=null; try { sys=await S.wykryjSystem(); } catch(_){}
    // Wielkie fakty na górze
    if (sys){ $('bz-f-system').textContent=sys.tytul; if (sys.werdykt==='alarm'){ $('bz-f-system').style.color='var(--alarm)'; $('bz-f-system2').textContent='bez wsparcia — brak poprawek'; } }
    $('bz-f-lok').textContent = prawdLokalizacja();
    // Szczegóły niżej
    const prz=S.wykryjPrzegladarke(); wiersz('Przeglądarka', prz.tytul, prz.werdykt==='alarm'?'alarm':'');
    try { wiersz('Strefa czasowa', Intl.DateTimeFormat().resolvedOptions().timeZone); } catch(_){}
    wiersz('Język', (navigator.languages&&navigator.languages[0])||navigator.language||'');
    wiersz('Ekran', screen.width+'×'+screen.height+' px');
    if (navigator.hardwareConcurrency) wiersz('Rdzenie procesora', String(navigator.hardwareConcurrency));
    if (navigator.deviceMemory) wiersz('Pamięć (ok.)', navigator.deviceMemory+' GB');
    wiersz('Dotyk', (navigator.maxTouchPoints||0)>0?'tak':'nie');
    $('bz-recon-stopka').textContent = (sys && sys.werdykt==='alarm')
      ? 'A to wszystko z samego połączenia — bez zgody i bez kliknięcia. Już widać, że Twój system jest bez poprawek. Uruchom skan, żeby zobaczyć, na co dokładnie Cię to wystawia.'
      : 'A to wszystko z samego połączenia — bez pytania o zgodę i bez kliknięcia. Uruchom skan, żeby zobaczyć, na co to Cię wystawia.';
    // Znane luki — od razu, dla systemu po końcu wsparcia
    const z=S.znaneLuki(sys);
    if (z){
      $('bz-luki-wstep').textContent=z.wstep;
      const ul=$('bz-luki-lista'); ul.textContent='';
      const link=(id,url)=>{ const a=document.createElement('a'); a.href=url; a.target='_blank'; a.rel='noopener noreferrer'; a.textContent=id; a.style.color='#0072ad'; return a; };
      const badge=(li)=>{ const b=document.createElement('span'); b.textContent='aktywnie wykorzystywana'; b.style.cssText='font-size:.72rem;font-weight:700;color:#fff;background:var(--alarm);border-radius:999px;padding:1px 8px;margin:0 2px;white-space:nowrap;'; li.append(b); };
      $('bz-luki').hidden=false;
      // 1) Świeże, aktywnie wykorzystywane — na żywo z backendu (CISA KEV)
      let naZywo=[]; try { naZywo=await S.pobierzLukiNaZywo(sys.wsparcieDo||''); } catch(_){}
      naZywo.slice(0,8).forEach(l=>{ const li=document.createElement('li');
        li.append(link(l.id,l.url), document.createTextNode(' ')); badge(li);
        if (l.dataDodania){ const d=document.createElement('span'); d.className='sc'; d.textContent=' (od '+l.dataDodania+')'; li.append(d); }
        li.append(document.createTextNode(' — ')); const sc=document.createElement('span'); sc.className='sc'; sc.textContent=l.opis||''; li.append(sc);
        ul.append(li); });
      // 2) Klasyki — ilustracje ścieżki ataku (dostępne też offline)
      z.luki.forEach(l=>{ const li=document.createElement('li');
        const b=document.createElement('b'); b.textContent=l.nazwa+' ';
        li.append(b, document.createTextNode('('), link(l.id,l.url), document.createTextNode(') '));
        if (l.aktywna) badge(li);
        li.append(document.createTextNode(' — '+l.co+'. '));
        const sc=document.createElement('span'); sc.className='sc'; const scb=document.createElement('b'); scb.textContent='Na co pozwala: '; scb.style.color='var(--tekst)';
        sc.append(scb, document.createTextNode(l.naPozwala)); li.append(sc); ul.append(li); });
    }
    // IP z backendu — wpada do wielkiego faktu, gdy serwer odpowie
    try { const ip=await S.wykryjIP(); if (ip && Array.isArray(ip.dane)){
      const adr=ip.dane.find(d=>/IP/i.test(d[0])); if (adr) $('bz-f-ip').textContent=adr[1];
      const lok=ip.dane.find(d=>/lokaliz/i.test(d[0])); if (lok) $('bz-f-lok').textContent=lok[1];
    } } catch(_){}
  }
  reconPasywny();

  // Test hasła na żywo: siła (lokalnie, natychmiast) + wyciek (HIBP, z opóźnieniem).
  const kolorPoz = p => p==='alarm'?'var(--alarm)':p==='uwaga'?'var(--uwaga)':p==='ok'?'var(--ok)':'var(--tekst3)';
  function wierszHaslo(kolor){ const d=document.createElement('p'); d.style.margin='0 0 6px'; if(kolor) d.style.color=kolor; return d; }
  function renderHaslo(h, hibp){
    const out=$('bz-haslo-wynik'); out.textContent='';
    if(!h){ stan.karty=stan.karty.filter(k=>k.klucz!=='haslo'); przeliczWynik(true); return; }
    // 1) Twoje hasło, wygwiazdkowane — żebyś rozpoznał, że to Twoje.
    const w1=wierszHaslo(); const et=document.createElement('span'); et.textContent='Twoje hasło: ';
    const code=document.createElement('code'); code.textContent=S.maskujHaslo(h);
    code.style.cssText='background:#eef3fb;border:1px solid var(--linia);border-radius:6px;padding:2px 8px;font-size:1.05rem;letter-spacing:.06em;word-break:break-all;overflow-wrap:anywhere;max-width:100%;';
    const dlug=document.createElement('span'); dlug.style.color='var(--tekst3)'; dlug.style.fontSize='.88rem'; dlug.textContent=' — '+h.length+' znaków';
    w1.append(et,code,dlug); out.append(w1);
    // 2) Siła — lokalnie, dosadnie.
    const sila=S.ocenSile(h); const w2=wierszHaslo(kolorPoz(sila.poziom));
    const b=document.createElement('b'); b.textContent=sila.etykieta+'. '; w2.append(b, document.createTextNode(sila.opis)); out.append(w2);
    // 3) Wyciek — HIBP (undefined = sprawdzanie w toku).
    const w3=wierszHaslo('var(--tekst3)');
    if (hibp===undefined) w3.textContent='Sprawdzam w wyciekach…';
    else if (hibp===null){ w3.textContent='Nie udało się teraz sprawdzić wycieków — spróbuj za chwilę.'; w3.style.color='var(--uwaga)'; }
    else if (hibp.blad){ w3.textContent=hibp.blad; w3.style.color='var(--uwaga)'; }
    else { w3.textContent=hibp.opis; w3.style.color=kolorPoz(hibp.werdykt); }
    out.append(w3);
    // 4) Pochwała, gdy mocne i bez wycieku.
    if (sila.poziom==='ok' && hibp && !hibp.blad && hibp.ile===0){
      const w4=wierszHaslo('var(--ok)'); const bb=document.createElement('b'); bb.textContent='Dobra robota — to już mocne hasło. ';
      w4.append(bb, document.createTextNode('Używaj go tylko w jednym miejscu i włącz 2FA.')); out.append(w4);
    }
    // Wpływ na wynik: gorszy z (siła, wyciek); gdy HIBP w toku, liczymy samą siłę.
    const rank={ok:0,uwaga:1,alarm:2,info:0};
    const hw=(hibp && hibp.werdykt) ? hibp.werdykt : 'ok';
    const gorszy = rank[hw]>=rank[sila.poziom] ? hw : sila.poziom;
    stan.karty=stan.karty.filter(k=>k.klucz!=='haslo');
    stan.karty.push({ klucz:'haslo', tytul:'Hasło', werdykt: gorszy==='ok'?'ok':gorszy,
      opis: sila.opis + (hibp&&hibp.ile>0?(' Dodatkowo: '+hibp.opis):''),
      czyn: gorszy==='alarm'?'Zmień to hasło, nie używaj go nigdzie indziej, włącz menedżer haseł i 2FA.':null });
    przeliczWynik(true);
  }
  let hasloTimer=null, hasloSeq=0;
  $('bz-haslo-input').addEventListener('input', ()=>{
    const h=$('bz-haslo-input').value;
    renderHaslo(h, undefined);                 // natychmiast: echo + siła + „sprawdzam…”
    clearTimeout(hasloTimer);
    if(!h) return;
    const mojSeq=++hasloSeq;
    hasloTimer=setTimeout(async ()=>{
      let hibp=null; try { hibp=await S.sprawdzHaslo(h); } catch(_){ hibp=null; }
      if(mojSeq!==hasloSeq) return;             // hasło zmieniło się w międzyczasie
      renderHaslo(h, hibp);
    }, 650);
  });
});
