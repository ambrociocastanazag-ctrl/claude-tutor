/* Los «ojos» en la página de cualquier panel (asistente, tutor de Excel, tutor de Dia): la lista de ventanas con
   miniaturas y la vista previa con permiso. ojos_panel.inyectar_ui() mete este archivo en la página.
   Usa los colores del panel (--bg, --line, --acc...) y crea sus propios elementos (clases oj-*).

   Ojos.elegir(cb)          lista de ventanas → cb({hwnd, titulo, app})
   Ojos.mirar(hwnd, cb)     captura → vista previa (Cancelar / Recortar / Adjuntar) → cb(adjunto)
   Ojos.elegirYMirar(cb)    las dos seguidas
   Ojos.tarjetaArchivo(info, enviar) la tarjeta «¿Dejo que el tutor lea «archivo»?» (Sí / No; archivos.py), o la lectura
                            sola si el archivo es libre; el archivo viaja como adjunto, igual que la captura de abajo
   Ojos.tarjetaVolver(info, enviar)  la tarjeta «¿Vuelvo a mirar «ventana»?» (Sí / No / Recortar) del tutor; la dibuja
                            Preguntas.tarjeta cuando una "pregunta" trae "volver" (ojos_panel.tarjeta_volver). enviar(texto)
                            es la función del panel que manda un mensaje; la captura viaja en ese mensaje (ver instalarEnvio)
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
    '.oj-vol{margin-top:10px;border:1px solid var(--line);border-radius:12px;background:var(--surface);padding:12px 13px;font-family:var(--sans);color:var(--ink)}' +
    '.oj-vol-q{display:flex;gap:8px;align-items:flex-start;font-size:14px;font-weight:650;line-height:1.45}' +
    '.oj-vol-q svg{flex-shrink:0;margin-top:2px;color:var(--acc)}' +
    '.oj-vol-n{margin:4px 0 10px 23px;font-size:12px;line-height:1.5;color:var(--ink3)}' +
    '.oj-vol .oj-botones{margin-left:23px;flex-wrap:wrap}' +
    '.oj-vol .oj-btn[disabled]{opacity:.5;cursor:default}' +
    '.oj-vol-r{margin:8px 0 0 23px;font-size:12.5px;line-height:1.5;color:var(--ink2)}' +
    '.oj-vol-r img{display:block;max-width:160px;max-height:100px;margin-top:6px;border:1px solid var(--line);border-radius:6px}' +
    '.oj-vol-e{margin:8px 0 0 23px;padding:8px 11px;border-radius:9px;background:var(--warn-soft);border:1px solid var(--warn-line);font-size:13px;line-height:1.5}' +
    '.oj-cargando{display:flex;align-items:center;justify-content:center;gap:10px;padding:40px 0;color:var(--ink3);font-size:13px}';
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  var P = {x: 'M6 6l12 12M18 6L6 18', refresh: 'M19.5 12a7.5 7.5 0 1 1-2.2-5.3M19.5 4v4.5H15', crop: 'M7 3v14h14M3 7h14v14',
           lock: 'M7 11V8a5 5 0 0 1 10 0v3M5 11h14v9H5z', camera: 'M4 8h3l2-3h6l2 3h3v11H4zM12 17a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z', clip: 'M20 11.5l-7.8 7.8a5 5 0 0 1-7.1-7.1l8.2-8.2a3.4 3.4 0 0 1 4.8 4.8l-8.1 8.1a1.7 1.7 0 0 1-2.4-2.4l7.4-7.4',
           file: 'M14 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7zM14 3v4h4M9 13h6M9 17h4'};
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
  // opts (todo opcional): captura() → promesa con lo mismo que api.ojos_capturar (la tarjeta «Recortar» pide una captura de una
  // ventana ya aprobada); recortar: true abre con el recorte activo; alCancelar(): se cerró la vista previa sin adjuntar.
  function mirar(hwnd, cb, alFallar, opts){
    opts = opts || {};
    var h = abrir('<div class="oj-cab"><b>Esto es lo que verá</b><button class="oj-ib oj-cerrar" type="button" aria-label="Cancelar">' + ic('x', 11) + '</button></div>' +
      '<div class="oj-cuerpo"><div class="oj-cargando">Capturando la ventana…</div></div>');
    (opts.captura ? opts.captura() : api().ojos_capturar(hwnd)).then(function(r){
      if (!hoja || hoja !== h) return;
      if (!r.ok){
        h.querySelector('.oj-cuerpo').innerHTML = '<div class="oj-aviso">' + esc(r.error) + '</div>';
        h.insertAdjacentHTML('beforeend', '<div class="oj-pie"><div class="oj-botones"><button class="oj-btn oj-cerrar" type="button">Cerrar</button>' +
          '<button class="oj-btn oj-prim oj-reintentar" type="button">Volver a intentar</button></div></div>');
        Array.prototype.forEach.call(h.querySelectorAll('.oj-cerrar'), function(b){ b.onclick = function(){ cerrar(); if (alFallar) alFallar(r); if (opts.alCancelar) opts.alCancelar(); }; });
        h.querySelector('.oj-reintentar').onclick = function(){ mirar(hwnd, cb, alFallar, opts); };
        return;
      }
      alCerrar = function(){ api().ojos_descartar(); if (opts.alCancelar) opts.alCancelar(); };          // cancelar = la captura se tira, no sale nada
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
      if (opts.recortar) h.querySelector('.oj-recortar').click();
      else h.querySelector('.oj-adjuntar').focus();
    });
  }

  // ---- «¿Vuelvo a mirar «ventana»?»: Sí / No / Recortar ----
  // La captura sale en el MISMO mensaje que la respuesta de la tarjeta: se guarda aquí y api.preguntar (la de todos los
  // paneles: asistente, curso, Excel y Dia) la añade a sus adjuntos. Así el panel no cambia y la respuesta sigue sola.
  var extra = null;
  function instalarEnvio(){
    var a = api(); if (!a || a._ojosEnvio || typeof a.preguntar !== 'function') return;
    var orig = a.preguntar;
    a.preguntar = function(q, adj){
      var e = extra; extra = null;
      if (e && Date.now() - e.t < 15000) adj = (adj || []).concat([e.adj]);
      return orig.call(a, q, adj);
    };
    a._ojosEnvio = true;
  }
  function tarjetaVolver(info, enviar){
    instalarEnvio();
    var t = info.titulo || 'la ventana';
    var raiz = document.createElement('div'); raiz.className = 'oj-vol';
    raiz.innerHTML = '<div class="oj-vol-q">' + ic('camera', 16) + '<span>¿Vuelvo a mirar «' + esc(t) + '»?</span></div>' +
      '<div class="oj-vol-n">Solo esa ventana, nunca la pantalla entera. «Sí» la captura ahora, sin vista previa; «Recortar» te deja elegir la zona antes de mandarla.</div>' +
      '<div class="oj-botones"><button class="oj-btn oj-prim oj-v-si" type="button" style="flex:none">Sí</button>' +
      '<button class="oj-btn oj-v-no" type="button">No</button>' +
      '<button class="oj-btn oj-v-rec" type="button">' + ic('crop', 14) + 'Recortar</button></div>';
    var bs = raiz.querySelectorAll('.oj-btn'), hecho = false;
    function bloquear(on){ Array.prototype.forEach.call(bs, function(b){ b.disabled = on; }); }
    function fin(txt, vista){
      hecho = true; bloquear(true);
      var r = document.createElement('div'); r.className = 'oj-vol-r'; r.textContent = txt;
      if (vista){ var im = document.createElement('img'); im.alt = 'Captura enviada'; im.src = vista; r.appendChild(im); }
      raiz.appendChild(r);
    }
    function fallo(r){
      var e = raiz.querySelector('.oj-vol-e'); if (e) e.remove();
      e = document.createElement('div'); e.className = 'oj-vol-e'; e.textContent = r.error || 'No pude capturarla.';
      if (r.cerrada || /cámara|📷/.test(r.error || '')){
        var b = document.createElement('button'); b.type = 'button'; b.className = 'oj-btn'; b.style.marginTop = '8px'; b.innerHTML = ic('camera', 14) + 'Enseñar otra ventana';
        b.onclick = function(){ Ojos.elegirYMirar(function(a){ fin('Te mandé «' + (a.titulo || a.nombre) + '».', a.vista); mandar(a, 'Te adjunto otra ventana (' + (a.titulo || a.nombre) + '). Contesta lo que te pregunté con ella.'); }); };
        e.appendChild(document.createElement('br')); e.appendChild(b);
        if (r.cerrada) bloquear(true);
      }
      raiz.appendChild(e); if (!r.cerrada) bloquear(false);
    }
    function mandar(a, texto){ extra = {adj: {nombre: a.nombre, tipo: a.tipo, media_type: a.media_type, datos: a.datos, ojos_id: a.ojos_id}, t: Date.now()}; enviar(texto); }
    raiz.querySelector('.oj-v-si').onclick = function(){
      if (hecho) return; bloquear(true);
      api().ojos_volver(info.token, 'si').then(function(a){
        if (!a || !a.ok) return fallo(a || {});
        fin('Te mandé una captura nueva de «' + t + '».', a.vista);
        mandar(a, 'Sí, vuelve a mirar «' + t + '» (te adjunto la captura nueva). Contesta lo que te pregunté con ella.');
      }, function(){ fallo({error: 'No pude capturarla.'}); });
    };
    raiz.querySelector('.oj-v-no').onclick = function(){
      if (hecho) return; fin('No la volví a mirar.');
      enviar('No, no vuelvas a mirar «' + t + '». Respóndeme sin la imagen (o dime que no puedes verla).');
    };
    raiz.querySelector('.oj-v-rec').onclick = function(){
      if (hecho) return; bloquear(true);
      mirar(info.hwnd, function(a){
        fin('Te mandé solo el recorte de «' + t + '».', a.vista);
        mandar(a, 'Te adjunto solo un recorte nuevo de «' + t + '». Contesta lo que te pregunté con él.');
      }, function(r){ fallo(r); }, {
        captura: function(){ return api().ojos_volver(info.token, 'recortar'); }, recortar: true,
        alCancelar: function(){ if (!hecho) bloquear(false); }
      });
    };
    if (info.existe === false) fallo({cerrada: true, error: '«' + t + '» ya no está abierta. Si quieres, enséñame otra con la cámara (📷).'});
    return raiz;
  }

  // ---- «¿Dejo que el tutor lea «archivo»?»: Sí / No (archivos.py). Permiso por ARCHIVO, nunca por carpeta. ----
  // Si es libre (de la carpeta del curso o ya aprobado en esta sesión), se lee y se manda solo, sin preguntar.
  function tarjetaArchivo(info, enviar){
    instalarEnvio();
    var n = info.nombre || 'el archivo', hecho = false;
    var raiz = document.createElement('div'); raiz.className = 'oj-vol';
    function fin(txt){
      hecho = true; Array.prototype.forEach.call(raiz.querySelectorAll('.oj-btn'), function(b){ b.disabled = true; });
      var r = document.createElement('div'); r.className = 'oj-vol-r'; r.textContent = txt; raiz.appendChild(r);
    }
    function leerYMandar(texto){
      api().archivo_leer(info.token).then(function(a){
        if (!a || !a.ok){ fin(a && a.error || 'No pude leerlo.'); enviar('No pude pasarte «' + n + '»: ' + (a && a.error || 'error al leerlo') + '. Sigue sin él.'); return; }
        fin(info.auto ? 'Le pasé «' + n + '» (ya tenía permiso).' : 'Le pasé «' + n + '».');
        extra = {adj: {nombre: a.nombre, tipo: a.tipo, media_type: a.media_type, datos: a.datos}, t: Date.now()};
        enviar(texto);
      }, function(){ fin('No pude leerlo.'); });
    }
    if (info.error){
      raiz.innerHTML = '<div class="oj-vol-q">' + ic('file', 16) + '<span>' + esc(info.error) + '</span></div>';
      return raiz;
    }
    if (info.auto){
      raiz.innerHTML = '<div class="oj-vol-q">' + ic('file', 16) + '<span>Leyendo «' + esc(n) + '»…</span></div>';
      setTimeout(function(){ leerYMandar('Aquí tienes «' + n + '» (' + info.ruta + '). Contesta lo que te pregunté con él.'); }, 50);
      return raiz;
    }
    raiz.innerHTML = '<div class="oj-vol-q">' + ic('file', 16) + '<span>¿Dejo que el tutor lea «' + esc(n) + '»?</span></div>' +
      '<div class="oj-vol-n">' + esc(info.ruta) + (info.secreto ? '<br><b>Ojo:</b> parece un archivo de claves o contraseñas.' : '') +
      '<br>Solo este archivo, no su carpeta. Lo lee sin cambiarlo.</div>' +
      '<div class="oj-botones"><button class="oj-btn oj-prim oj-a-si" type="button" style="flex:none">Sí</button>' +
      '<button class="oj-btn oj-a-no" type="button">No</button></div>';
    raiz.querySelector('.oj-a-si').onclick = function(){
      if (hecho) return; hecho = true;
      leerYMandar('Sí, lee «' + n + '» (te lo adjunto). Contesta lo que te pregunté con él.');
    };
    raiz.querySelector('.oj-a-no').onclick = function(){
      if (hecho) return; fin('No le pasé «' + n + '».');
      enviar('No, no leas «' + n + '». Respóndeme sin él.');
    };
    return raiz;
  }

  window.Ojos = {
    elegir: elegir,
    mirar: mirar,
    tarjetaVolver: tarjetaVolver,
    tarjetaArchivo: tarjetaArchivo,
    elegirYMirar: function(cb){ elegir(function(v){ mirar(v.hwnd, cb); }); },
    cerrar: function(){ cerrar(); }
  };
})();

/* «Buscando en la web…»: los tutores de Excel, Dia y curso lo mandan mientras investigan (capacidades.ConWeb).
   Cambia la línea «Leyendo tu …» de la burbuja de espera; el asistente tiene su propia versión en panel.html. */
(function(){
  if (window.avisoTrabajo) return;
  window.avisoTrabajo = function(t){
    var q = document.querySelector('.pensando .que');
    if (q) q.textContent = t;
  };
})();
