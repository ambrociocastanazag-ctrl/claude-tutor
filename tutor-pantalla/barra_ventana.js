/* La barra de la ventana de los paneles (asistente, Excel, Dia, curso): la ventana va sin el marco de Windows (sin el
   logo de Python) y aquí se ponen sus botones, como en la Tarjeta SVG: minimizar y cerrar ✕. La barra de arriba de cada
   página sirve para arrastrar la ventana (clase pywebview-drag-region); sus botones siguen siendo botones.
   Dónde: en el asistente, la fila de arriba (.cab .fila); en los paneles de lección, la fila de pestañas (.tabs).
   Python: OjosApi.ventana_minimizar() y ventana_cerrar(). Sin ellos (panel con marco), no hace nada. */
(function(){
  if (window.BarraVentana) return;
  var ARRASTRE = 'pywebview-drag-region';
  function api(){ return window.pywebview && window.pywebview.api; }
  function icono(d){ return '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + d + '</svg>'; }
  var I = {minimizar: icono('<path d="M6 12h12"/>'), cerrar: icono('<path d="M6 6l12 12"/><path d="M18 6L6 18"/>')};

  var css = '.bv-botones{display:flex;align-items:center;gap:2px;flex:none;margin-left:auto}' +
    '.bv-btn{width:30px;height:28px;border:0;border-radius:7px;background:transparent;color:var(--ink2,var(--muted,#666));display:grid;place-items:center;cursor:pointer;padding:0}' +
    '.bv-btn:hover{background:var(--line,rgba(0,0,0,.08));color:var(--ink,#222)}' +
    '.bv-btn.bv-cerrar:hover{background:var(--bad,#c02828);color:#fff}' +
    '.tabs .bv-botones{align-self:center;margin:0 0 4px 4px}' +
    '.' + ARRASTRE + '{cursor:default}';

  function barra(){                                   // dónde van los botones en esta página
    return document.querySelector('body > .tabs, .tabs[role="tablist"]') || document.querySelector('header.cab .fila');   // la lección también tiene .cab .fila por dentro
  }
  function poner(){
    var a = api();
    if (!a || !a.ventana_cerrar || document.querySelector('.bv-botones')) return;
    var b = barra(); if (!b) return;
    a.ventana_sin_marco().then(function(sin){
      if (!sin || document.querySelector('.bv-botones')) return;      // con el marco de Windows no hacen falta
      var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
      var caja = document.createElement('div'); caja.className = 'bv-botones';
      [['minimizar', 'Minimizar', function(){ a.ventana_minimizar(); }],
       ['cerrar', 'Cerrar', function(){ a.ventana_cerrar(); }]].forEach(function(x){
        var btn = document.createElement('button'); btn.type = 'button'; btn.className = 'bv-btn bv-' + x[0];
        btn.title = x[1]; btn.setAttribute('aria-label', x[1]); btn.innerHTML = I[x[0]]; btn.onclick = x[2];
        caja.appendChild(btn);
      });
      b.appendChild(caja);
      // arrastrar desde la barra y desde su texto, pero nunca desde un botón, una pestaña o un campo
      b.classList.add(ARRASTRE);
      [].forEach.call(b.querySelectorAll('.marca, .marca *'), function(e){ e.classList.add(ARRASTRE); });
      b.addEventListener('mousedown', function(e){
        if (e.target.closest('button, a, input, select, textarea, [role="tab"]')) e.stopPropagation();   // pywebview escucha en <body>
      });
      b.addEventListener('dblclick', function(e){ if (!e.target.closest('button')) e.preventDefault(); });
    });
  }
  window.BarraVentana = {poner: poner};
  if (api()) poner(); else window.addEventListener('pywebviewready', poner);
})();
