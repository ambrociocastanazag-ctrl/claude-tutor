/* Los «ojos» en la página de cualquier panel (asistente, tutor de Excel, tutor de Dia): la lista de ventanas con
   miniaturas y la vista previa con permiso. ojos_panel.inyectar_ui() mete este archivo en la página.
   Usa los colores del panel (--bg, --line, --acc...) y crea sus propios elementos (clases oj-*).

   Ojos.elegir(cb)          lista de ventanas → cb({hwnd, titulo, app})
   Ojos.mirar(hwnd, cb)     captura → vista previa (Cancelar / Recortar / Adjuntar) → cb(adjunto)
   Ojos.elegirYMirar(cb)    las dos seguidas
   El adjunto tiene el formato de los adjuntos del panel ({nombre, tipo, media_type, datos, vista, tam}) más ojos_id.
   Nada sale de la PC aquí: «Adjuntar» solo lo pone en el mensaje; sale cuando la persona lo envía. */
(function(){
  if (window.Ojos) return;
  var css = '' +
    '.oj-velo{position:fixed;inset:0;z-index:1000;background:light-dark(oklch(0.3 0.02 265 / 0.35),oklch(0 0 0 / 0.6))}' +
    '.oj-hoja{position:fixed;inset:10px;z-index:1001;display:flex;flex-direction:column;border-radius:14px;background:var(--bg);border:1px solid var(--line);box-shadow:0 10px 40px var(--shadow-c,rgba(0,0,0,.2));overflow:hidden;font-family:var(--sans);color:var(--ink)}' +
    '.oj-cab{flex-shrink:0;display:flex;align-items:center;gap:8px;padding:10px 8px 10px 14px;border-bottom:1px solid var(--line2)}' +
    '.oj-cab b{flex:1;font-size:15px}' +
    '.oj-ib{flex-shrink:0;width:32px;height:32px;padding:0;border:none;border-radius:8px;background:transparent;color:var(--ink2);display:grid;place-items:center;cursor:pointer}' +
    '.oj-ib:hover{background:var(--line2)}' +
    '.oj-cuerpo{flex:1;min-height:0;overflow-y:auto;padding:12px;scrollbar-width:thin}' +
    '.oj-pie{flex-shrink:0;display:flex;flex-direction:column;gap:8px;padding:10px 12px 12px;border-top:1px solid var(--line2)}' +
    '.oj-grupo{margin:2px 0 8px;font-size:11px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--ink3)}' +
    '.oj-rejilla{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-bottom:14px}' +
    '.oj-tarjeta{display:flex;flex-direction:column;padding:0;border:1px solid var(--line);border-radius:10px;background:var(--surface);overflow:hidden;text-align:left;cursor:pointer;font:inherit;color:inherit}' +
    '.oj-tarjeta:hover{border-color:var(--acc-mid)} .oj-tarjeta.oj-curso{border-color:var(--acc)} .oj-tarjeta.oj-actual{box-shadow:0 0 0 1px var(--acc)}' +
    '.oj-mini{aspect-ratio:16/10;background:var(--sunk);display:grid;place-items:center;color:var(--ink3);font-size:12px;overflow:hidden}' +
    '.oj-mini img{display:block;width:100%;height:100%;object-fit:cover;object-position:top left}' +
    '.oj-nm{padding:6px 9px 1px;font-size:12.5px;font-weight:650;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' +
    '.oj-ap{padding:0 9px 7px;font-family:var(--mono);font-size:11px;color:var(--ink3)}' +
    '.oj-lienzo{position:relative;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--sunk);user-select:none}' +
    '.oj-lienzo img{display:block;width:100%} .oj-lienzo.oj-recortando{cursor:crosshair}' +
    '.oj-sel{position:absolute;border:2px solid var(--acc);box-shadow:0 0 0 9999px oklch(0 0 0 / .35);pointer-events:none}' +
    '.oj-permiso{display:flex;gap:8px;align-items:flex-start;font-size:12.5px;line-height:1.5;color:var(--ink2)}' +
    '.oj-permiso svg{flex-shrink:0;color:var(--ok);margin-top:2px}' +
    '.oj-botones{display:flex;gap:6px}' +
    '.oj-btn{height:38px;padding:0 12px;display:flex;align-items:center;gap:6px;border:1px solid var(--line);border-radius:9px;background:var(--surface);font:inherit;font-size:13.5px;font-weight:650;color:var(--ink);cursor:pointer;white-space:nowrap}' +
    '.oj-btn.oj-prim{flex:1;justify-content:center;border:none;background:var(--acc);color:var(--on-acc);font-size:14px}' +
    '.oj-btn.oj-activo{background:var(--acc-soft);color:var(--acc-text);border-color:transparent}' +
    '.oj-aviso{padding:8px 11px;border-radius:9px;background:var(--warn-soft);border:1px solid var(--warn-line);font-size:13px;line-height:1.5;margin-bottom:10px}' +
    '.oj-cargando{display:flex;align-items:center;justify-content:center;gap:10px;padding:40px 0;color:var(--ink3);font-size:13px}';
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  var P = {x: 'M6 6l12 12M18 6L6 18', refresh: 'M19.5 12a7.5 7.5 0 1 1-2.2-5.3M19.5 4v4.5H15', crop: 'M7 3v14h14M3 7h14v14',
           lock: 'M7 11V8a5 5 0 0 1 10 0v3M5 11h14v9H5z', clip: 'M20 11.5l-7.8 7.8a5 5 0 0 1-7.1-7.1l8.2-8.2a3.4 3.4 0 0 1 4.8 4.8l-8.1 8.1a1.7 1.7 0 0 1-2.4-2.4l7.4-7.4'};
  function ic(n, t){ return '<svg width="' + (t || 15) + '" height="' + (t || 15) + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="' + P[n] + '"/></svg>'; }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function api(){ return window.pywebview && window.pywebview.api; }

  var velo = null, hoja = null, alCerrar = null;
  function abrir(html){
    cerrar(true);
    velo = document.createElement('div'); velo.className = 'oj-velo';
    hoja = document.createElement('section'); hoja.className = 'oj-hoja'; hoja.setAttribute('role', 'dialog'); hoja.innerHTML = html;
    document.body.appendChild(velo); document.body.appendChild(hoja);
    velo.onclick = function(){ cerrar(); };
    Array.prototype.forEach.call(hoja.querySelectorAll('.oj-cerrar'), function(b){ b.onclick = function(){ cerrar(); }; });
    return hoja;
  }
  function cerrar(sinAviso){
    var f = alCerrar; alCerrar = null;
    if (velo) velo.remove(); if (hoja) hoja.remove(); velo = hoja = null;
    if (f && !sinAviso) f();
  }
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape' && hoja){ e.stopPropagation(); cerrar(); } }, true);

  // ---- Lista de ventanas ----
  var ultima = null;
  function elegir(cb){
    var h = abrir('<div class="oj-cab"><b>¿Qué ventana le enseño?</b>' +
      '<button class="oj-ib oj-recargar" type="button" title="Actualizar la lista" aria-label="Actualizar">' + ic('refresh') + '</button>' +
      '<button class="oj-ib oj-cerrar" type="button" aria-label="Cerrar">' + ic('x', 11) + '</button></div>' +
      '<div class="oj-cuerpo"></div>' +
      '<div class="oj-pie"><div class="oj-permiso">' + ic('lock', 14) + '<span>Las miniaturas solo se ven aquí y no se mandan a nadie. Después verás la captura antes de adjuntarla.</span></div></div>');
    function cargar(){
      var c = h.querySelector('.oj-cuerpo');
      c.innerHTML = '<div class="oj-cargando">Buscando ventanas…</div>';
      api().ojos_ventanas(ultima).then(function(vs){
        c.innerHTML = '';
        if (!vs.length){ c.innerHTML = '<div class="oj-cargando">No hay ventanas abiertas.</div>'; return; }
        var curso = vs.filter(function(v){ return v.curso; }), otras = vs.filter(function(v){ return !v.curso; });
        [[curso, 'De ' + (window.APP_PANEL || 'la app del curso')], [otras, curso.length ? 'Otras ventanas' : '']].forEach(function(g){
          if (!g[0].length) return;
          if (g[1]) c.insertAdjacentHTML('beforeend', '<div class="oj-grupo">' + esc(g[1]) + '</div>');
          var rej = document.createElement('div'); rej.className = 'oj-rejilla'; c.appendChild(rej);
          g[0].forEach(function(v){
            var b = document.createElement('button'); b.type = 'button';
            b.className = 'oj-tarjeta' + (v.curso ? ' oj-curso' : '') + (v.actual ? ' oj-actual' : '');
            b.innerHTML = '<div class="oj-mini">' + (v.minimizada ? 'Minimizada' : '…') + '</div><div class="oj-nm"></div><div class="oj-ap"></div>';
            b.querySelector('.oj-nm').textContent = v.titulo; b.querySelector('.oj-ap').textContent = v.app; b.title = v.titulo;
            b.onclick = function(){ ultima = v.hwnd; cerrar(true); cb(v); };
            rej.appendChild(b);
            if (!v.minimizada) api().ojos_miniatura(v.hwnd).then(function(src){
              b.querySelector('.oj-mini').innerHTML = src ? '<img alt="" src="' + src + '">' : 'Sin vista';
            });
          });
        });
      });
    }
    h.querySelector('.oj-recargar').onclick = cargar;
    cargar();
  }

  // ---- Vista previa: el permiso ----
  function mirar(hwnd, cb, alFallar){
    var h = abrir('<div class="oj-cab"><b>Esto es lo que verá</b><button class="oj-ib oj-cerrar" type="button" aria-label="Cancelar">' + ic('x', 11) + '</button></div>' +
      '<div class="oj-cuerpo"><div class="oj-cargando">Capturando la ventana…</div></div>');
    api().ojos_capturar(hwnd).then(function(r){
      if (!hoja || hoja !== h) return;
      if (!r.ok){
        h.querySelector('.oj-cuerpo').innerHTML = '<div class="oj-aviso">' + esc(r.error) + '</div>';
        h.insertAdjacentHTML('beforeend', '<div class="oj-pie"><div class="oj-botones"><button class="oj-btn oj-cerrar" type="button">Cerrar</button>' +
          '<button class="oj-btn oj-prim oj-reintentar" type="button">Volver a intentar</button></div></div>');
        Array.prototype.forEach.call(h.querySelectorAll('.oj-cerrar'), function(b){ b.onclick = function(){ cerrar(); if (alFallar) alFallar(r); }; });
        h.querySelector('.oj-reintentar').onclick = function(){ mirar(hwnd, cb, alFallar); };
        return;
      }
      alCerrar = function(){ api().ojos_descartar(); };          // cancelar = la captura se tira, no sale nada
      var recorte = null, arrastre = null;
      h.querySelector('.oj-cuerpo').innerHTML = '<div class="oj-lienzo"><img alt="Captura de ' + esc(r.titulo) + '" src="' + r.img + '"><div class="oj-sel" hidden></div></div>';
      h.insertAdjacentHTML('beforeend', '<div class="oj-pie"><div class="oj-permiso">' + ic('lock', 14) + '<span>Se adjunta esta imagen de «' + esc(r.titulo) + '»' +
        (r.controles ? ' y los nombres de sus ' + r.controles + ' botones y campos' : '') + '. Sale solo cuando envíes el mensaje; si cancelas, no sale nada.</span></div>' +
        '<div class="oj-botones"><button class="oj-btn oj-cerrar" type="button">Cancelar</button>' +
        '<button class="oj-btn oj-recortar" type="button" title="Arrastra sobre la imagen para adjuntar solo una parte">' + ic('crop', 14) + 'Recortar</button>' +
        '<button class="oj-btn oj-prim oj-adjuntar" type="button">' + ic('clip', 15) + 'Adjuntar</button></div></div>');
      Array.prototype.forEach.call(h.querySelectorAll('.oj-cerrar'), function(b){ b.onclick = function(){ cerrar(); }; });
      var lienzo = h.querySelector('.oj-lienzo'), sel = h.querySelector('.oj-sel');
      h.querySelector('.oj-recortar').onclick = function(){
        var on = !lienzo.classList.contains('oj-recortando');
        lienzo.classList.toggle('oj-recortando', on); this.classList.toggle('oj-activo', on);
        if (!on){ recorte = null; sel.hidden = true; }
      };
      lienzo.addEventListener('pointerdown', function(e){
        if (!lienzo.classList.contains('oj-recortando')) return;
        var b = lienzo.getBoundingClientRect(); arrastre = {x: e.clientX - b.left, y: e.clientY - b.top};
        lienzo.setPointerCapture(e.pointerId); e.preventDefault();
      });
      lienzo.addEventListener('pointermove', function(e){
        if (!arrastre) return;
        var b = lienzo.getBoundingClientRect(), x = Math.max(0, Math.min(b.width, e.clientX - b.left)), y = Math.max(0, Math.min(b.height, e.clientY - b.top));
        var a = Math.min(arrastre.x, x), t = Math.min(arrastre.y, y), w = Math.abs(x - arrastre.x), hh = Math.abs(y - arrastre.y);
        sel.hidden = false; sel.style.left = a + 'px'; sel.style.top = t + 'px'; sel.style.width = w + 'px'; sel.style.height = hh + 'px';
        var k = r.w / b.width; recorte = w > 10 && hh > 10 ? [a * k, t * k, w * k, hh * k].map(Math.round) : null;
      });
      lienzo.addEventListener('pointerup', function(){ arrastre = null; if (!recorte) sel.hidden = true; });
      h.querySelector('.oj-adjuntar').onclick = function(){
        alCerrar = null; cerrar(true);
        api().ojos_adjuntar(recorte).then(function(a){ if (a && a.ok) cb(a); });
      };
      h.querySelector('.oj-adjuntar').focus();
    });
  }

  window.Ojos = {
    elegir: elegir,
    mirar: mirar,
    elegirYMirar: function(cb){ elegir(function(v){ mirar(v.hwnd, cb); }); },
    cerrar: function(){ cerrar(); }
  };
})();
