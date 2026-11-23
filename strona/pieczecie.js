/* Tarcze zgodności: błysk gra tylko na ekranie, przechył 3D za kursorem.
   Nic się nie rusza przy ograniczeniu ruchu; przechyłu nie ma na ekranach dotykowych. */
(function () {
  var panel = document.querySelector('.nx-law');
  if (!panel || !window.matchMedia || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (wpisy) {
      wpisy.forEach(function (w) { panel.classList.toggle('is-widoczny', w.isIntersecting); });
    }).observe(panel);
  }
  if (!matchMedia('(hover: hover)').matches) return;
  panel.querySelectorAll('li').forEach(function (li) {
    var svg = li.querySelector('.nx-tarcza');
    if (!svg) return;
    li.addEventListener('pointermove', function (e) {
      var r = svg.getBoundingClientRect();
      li.classList.add('is-tilt');
      svg.style.setProperty('--ry', (((e.clientX - r.left) / r.width - 0.5) * 18).toFixed(2) + 'deg');
      svg.style.setProperty('--rx', (-((e.clientY - r.top) / r.height - 0.5) * 14).toFixed(2) + 'deg');
    });
    li.addEventListener('pointerleave', function () {
      li.classList.remove('is-tilt');
      svg.style.setProperty('--ry', '0deg');
      svg.style.setProperty('--rx', '0deg');
    });
  });
})();
