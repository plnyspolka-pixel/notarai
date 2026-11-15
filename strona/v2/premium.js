// notarai.pl v2: dwa drobne ulepszenia. Bez tego pliku strona wygląda i działa tak samo, tylko bez ruchu.
(() => {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  // Nagłówek pierwszego ekranu wynurza się słowo po słowie.
  const h1 = document.getElementById('brand-hero-heading');
  if (h1) {
    let i = 0;
    const tnij = wezel => {
      for (const dziecko of [...wezel.childNodes]) {
        if (dziecko.nodeType === 3) {
          const czesci = document.createDocumentFragment();
          for (const czesc of dziecko.textContent.split(/(\s+)/)) {
            if (!czesc.trim()) { czesci.append(czesc); continue; }
            const s = document.createElement('span'); s.className = 'p-s';
            const w = document.createElement('span'); w.style.setProperty('--i', i++); w.textContent = czesc;
            s.append(w); czesci.append(s);
          }
          dziecko.replaceWith(czesci);
        } else if (dziecko.nodeType === 1) tnij(dziecko);
      }
    };
    h1.setAttribute('aria-label', h1.textContent.replace(/\s+/g, ' ').trim());
    tnij(h1);
    h1.classList.add('p-gra');
  }

  // Pętle (tło pierwszego ekranu, ramka pakietu startowego) grają tylko wtedy, gdy są na ekranie.
  if ('IntersectionObserver' in window) {
    const oko = new IntersectionObserver(wpisy => wpisy.forEach(w => w.target.classList.toggle('p-gra', w.isIntersecting)));
    document.querySelectorAll('.brand-hero, .p-pakiet--start').forEach(el => oko.observe(el));
  }
})();
