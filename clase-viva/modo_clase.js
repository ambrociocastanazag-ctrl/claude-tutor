/* El panel del tutor en modo «clase viva» (lo inyecta clase_viva.py; panel.html no cambia). Tres formas de la ventana:
     abierto   el chat entero, a la derecha de la clase (la clase le deja el hueco);
     pastilla  una lengüeta de 34 × 64 px en el borde derecho (Profe.pastilla 'marca'): con un clic (o con Ctrl+Espacio
               en la clase) se abre la caja. Un latido y quieta cuando llega una respuesta estando plegada;
     pregunta  solo la caja para escribir, flotando sobre la clase, con la lengüeta «abierta» a su derecha. NO se ven las
               respuestas del tutor ni su tarjeta de preguntas: las explica en la clase. Bajo la caja queda una línea
               «✦ Te lo expliqué en la clase · Abrir el chat».
   La caja tiene el borde azul al escribir y, mientras el tutor piensa, el garabato de Profe.cajita en lugar del botón de enviar.
   Python pone la ventana del tamaño de cada forma: api.clase_modo(modo) y api.clase_alto(px) (lo que mide la página).
   window.modoClase(modo) lo llama Python (atajo, ✕ de la barra); la página lo llama con los botones.
   Usa window.Profe (tutor-pantalla/profe.js) para dibujar; si no está, la pastilla y el garabato no se dibujan. */
(function(){
  if (window.modoClase) return;
  var $ = function(id){ return document.getElementById(id); };
  function api(){ return window.pywebview && window.pywebview.api; }
  var modo = 'abierto', tCerrar = null, firmaPlegada = '', hayNuevo = false;

  var css = '' +
    'html.cv .tabs .tab{display:none}' +
    'html.cv .tabs{align-items:center;padding:6px 8px;gap:6px}' +
    '.cv-titulo{flex:1;min-width:0;display:flex;align-items:center;gap:7px;font-weight:700;font-size:13.5px;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' +
    '.cv-titulo .cv-chispa{color:var(--acc);display:grid}' +
    '.cv-titulo small{font-weight:500;color:var(--ink3);font-size:12px;overflow:hidden;text-overflow:ellipsis}' +
    '.cv-btn{height:28px;padding:0 9px;border:1px solid var(--line);border-radius:7px;background:var(--surface);color:var(--ink2);font-size:12.5px;font-weight:650;display:flex;align-items:center;gap:5px;flex:none}' +
    '.cv-btn:hover{color:var(--ink);border-color:var(--acc-mid)}' +
    'html.cv .bv-cerrar{display:none}' +
    'html.cv #chipRevisar{display:none !important}' +
    /* pastilla (34 × 64 px): todo el dibujo de Profe.pastilla 'marca' */
    '#cvPastilla{display:none;position:fixed;inset:0;border:0;border-radius:0;padding:0;cursor:pointer;overflow:hidden}' +
    '#cvPastilla svg{display:block;width:34px;height:64px;transform-origin:100% 50%}' +
    '#cvPastilla svg.latido{animation:cvLatido .9s ease-out 1}' +
    '@keyframes cvLatido{0%{transform:scale(1)}28%{transform:scale(1.12)}58%{transform:scale(.97)}100%{transform:scale(1)}}' +
    'html.cv-pastilla .app{display:none} html.cv-pastilla #cvPastilla{display:block}' +
    /* la lengüeta «abierta» de la forma pregunta, a la derecha de la caja */
    '#cvTab{display:none;position:fixed;right:0;top:50%;margin-top:-32px;width:34px;height:64px;border:0;padding:0;background:transparent;cursor:pointer;overflow:hidden}' +
    '#cvTab svg{display:block;width:34px;height:64px}' +
    'html.cv-pregunta #cvTab{display:block} html.cv-pregunta body{padding-right:34px}' +
    /* pregunta: solo la caja (las respuestas del tutor van en la clase) */
    'html.cv-pregunta .app{border:1px solid var(--acc-mid)}' +
    'html.cv-pregunta .cab-tutor, html.cv-pregunta .chips, html.cv-pregunta .chat{display:none}' +
    'html.cv-pregunta .pie{border-top:0;padding:10px 10px 10px}' +
    'html.cv-pregunta .cv-solo-abierto, html.cv-abierto .cv-solo-pregunta{display:none}' +
    '.cv-ayuda{font-size:12px;color:var(--ink3);padding:0 4px 2px}' +
    '#cvLinea{display:none;font-size:12.5px;color:var(--ink2);padding:2px 4px 0;align-items:center;gap:6px;flex-wrap:wrap}' +
    '#cvLinea button{border:0;background:transparent;padding:0;color:var(--acc-text);font-weight:650;text-decoration:underline;font-size:12.5px}' +
    'html.cv-pregunta #cvLinea.hay{display:flex} html.cv-pregunta #cvLinea.hay ~ .cv-ayuda{display:none}' +
    /* la cajita: borde azul al escribir y garabato mientras el tutor piensa */
    '.caja.cv-escribe{border-color:var(--cv-tinta,var(--acc)) !important;box-shadow:0 0 0 1px var(--cv-tinta,var(--acc))}' +
    '.enviar .cv-gar{display:none}' +
    '.enviar.cv-pensando{background:transparent !important;opacity:1 !important}' +
    '.enviar.cv-pensando > :not(.cv-gar){display:none !important} .enviar.cv-pensando .cv-gar{display:block}' +
    '.cv-movi{align-items:center} .cv-movi span{flex:1;min-width:0;overflow-wrap:anywhere} .cv-movi .cv-btn{height:24px;padding:0 8px}';
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
  document.documentElement.classList.add('cv', 'cv-abierto');

  var IC = {
    chispa: '<svg class="ic" viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 3.5l1.9 5.1 5.1 1.9-5.1 1.9L12 17.5l-1.9-5.1L5 10.5l5.1-1.9z"/></svg>',
    abrir: '<svg class="ic" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6M20 4l-7 7M10 20H4v-6M4 20l7-7"/></svg>',
    plegar: '<svg class="ic" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>'
  };

  // ---- el tema y las figuras de Profe ----
  function temaPanel(){
    var c = document.documentElement.classList;
    if (c.contains('tema-oscuro')) return 'oscuro'; if (c.contains('tema-claro')) return 'claro';
    return window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'oscuro' : 'claro';
  }
  // La pastilla ocupa toda la ventana (34 × 64): el dibujo va pegado al borde derecho, centrado.
  function figuraPastilla(estado, latido){
    var Pf = window.Profe; if (!Pf) return '';
    var t = temaPanel(), d = Pf.pastilla({x: 34, y: 32, estado: estado, variante: 'marca', escala: 0.95, tema: t});
    return '<svg xmlns="http://www.w3.org/2000/svg" width="34" height="64" viewBox="0 0 34 64"' + (latido ? ' class="latido"' : '') + '>' + d.g + '</svg>';
  }
  function pintarPastilla(latido){
    var p = $('cvPastilla'), Pf = window.Profe; if (!p) return;
    if (Pf) p.style.background = Pf.paleta('azul', temaPanel()).fondo;
    p.innerHTML = figuraPastilla(hayNuevo ? 'nuevo' : 'reposo', latido);
  }
  function pintarTab(){
    var b = $('cvTab'); if (b) b.innerHTML = figuraPastilla('abierta', false);
  }
  function pintarTodo(){
    var Pf = window.Profe;
    if (Pf) document.documentElement.style.setProperty('--cv-tinta', Pf.paleta('azul', temaPanel()).tinta);
    pintarPastilla(false); pintarTab();
  }

  function armar(){
    if ($('cvPastilla')) return;
    if ($('tab-tutor')) $('tab-tutor').click();                // aquí no hay Lección: la clase es la lección
    // la barra de arriba: «Tutor · módulo», y los botones de cada forma (la barra de la ventana pone el «—»)
    var tabs = document.querySelector('.tabs');
    var tit = document.createElement('div'); tit.className = 'cv-titulo';
    tit.innerHTML = '<span class="cv-chispa">' + IC.chispa + '</span><span>Tutor</span><small id="cvModulo"></small>';
    tabs.insertBefore(tit, tabs.firstChild);
    var bAbrir = boton('cv-solo-pregunta', IC.abrir + 'Abrir el chat', 'Ver toda la conversación', function(){ poner('abierto'); });
    var bPlegar = boton('cv-solo-abierto', IC.plegar + 'Plegar', 'Deja toda la pantalla para la clase (Ctrl+Espacio en la clase para preguntar)', function(){ poner('pastilla'); });
    tit.after(bAbrir); bAbrir.after(bPlegar);                  // antes del «—» de la barra de la ventana
    // la pastilla (todo su dibujo es de Profe) y la lengüeta «abierta» de la forma pregunta
    var p = document.createElement('button'); p.id = 'cvPastilla'; p.type = 'button'; p.title = 'Pregúntale al tutor (Ctrl+Espacio en la clase)';
    p.onclick = function(){ poner('pregunta', true); };
    document.body.appendChild(p);
    var tb = document.createElement('button'); tb.id = 'cvTab'; tb.type = 'button'; tb.title = 'Plegar (Esc)';
    tb.onclick = function(){ poner('pastilla'); };
    document.body.appendChild(tb);
    // bajo la caja en modo pregunta: la línea de «te lo expliqué en la clase» y, si no, la ayuda corta
    var li = document.createElement('div'); li.id = 'cvLinea'; li.className = 'cv-solo-pregunta';
    li.innerHTML = '<span>✦ Te lo expliqué en la clase ·</span><button type="button">Abrir el chat</button>';
    li.querySelector('button').onclick = function(){ poner('abierto'); };
    $('caja').after(li);
    var ay = document.createElement('div'); ay.className = 'cv-ayuda cv-solo-pregunta'; ay.textContent = 'Enter para enviar · Esc para plegar';
    li.after(ay);
    // el garabato del botón de enviar
    var g = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); g.setAttribute('class', 'cv-gar'); g.setAttribute('width', '32'); g.setAttribute('height', '22');
    g.setAttribute('viewBox', '254 11 36 22'); $('enviar').appendChild(g);
    // la bienvenida del panel habla de hojas: aquí, de la clase
    var primero = $('chat').querySelector('.tutor-m .bloques');
    if (primero) primero.innerHTML = '<p>Pregúntame lo que quieras de la clase. Te contesto aquí y te lo señalo o te lo dibujo encima de la clase. '
      + 'Si pliegas el chat, la pastilla de la derecha se abre con un clic (o con <b>Ctrl+Espacio</b> en la clase).</p>';
    pintarTodo();
  }
  function boton(clase, html, titulo, fn){
    var b = document.createElement('button'); b.type = 'button'; b.className = 'cv-btn ' + clase; b.innerHTML = html; b.title = titulo; b.onclick = fn; return b;
  }

  // ---- el garabato mientras el tutor piensa (el panel deshabilita #enviar mientras espera) ----
  var rafGar = 0;
  function garabato(){
    var b = $('enviar'), Pf = window.Profe; rafGar = 0;
    if (!b || !Pf || !b.disabled) return;
    var s = b.querySelector('.cv-gar');
    if (s){
      var g = Pf.cajita({x: 300, y: 22, ancho: 300, estado: 'pensando', texto: '', fase: (performance.now() % 1600) / 1600, tema: temaPanel()}).g;
      var m = g.match(/<path[^>]*\/>\s*$/);                    // el garabato es lo último que dibuja la cajita
      s.innerHTML = m ? m[0] : '';
    }
    rafGar = requestAnimationFrame(garabato);
  }
  function revisarPensando(){
    var b = $('enviar'); if (!b) return;
    var on = !!b.disabled && !!window.Profe;
    b.classList.toggle('cv-pensando', on);
    if (on && !rafGar) rafGar = requestAnimationFrame(garabato);
    if (!on && rafGar){ cancelAnimationFrame(rafGar); rafGar = 0; }
    actualizarLinea(); medir();
  }
  // el borde azul de la caja: mientras escribe (con el cursor dentro o con texto)
  function revisarEscribe(){
    var e = $('entrada'); if (!e || !$('caja')) return;
    $('caja').classList.toggle('cv-escribe', document.activeElement === e || !!e.value.trim());
  }

  // ---- «te lo expliqué en la clase»: ¿llegó una respuesta después de la última pregunta? ----
  function respuestaLlegada(){
    var hijos = [].slice.call($('chat').children), ultimaYo = -1;
    hijos.forEach(function(h, i){ if (h.classList.contains('yo') && h.dataset.cvVieja !== '1') ultimaYo = i; });
    if (ultimaYo < 0) return false;
    return hijos.some(function(h, i){ return i > ultimaYo && h.classList.contains('tutor-m') && !h.querySelector('.pensando') && h.dataset.cvVieja !== '1'; });
  }
  function actualizarLinea(){
    var l = $('cvLinea'); if (l) l.classList.toggle('hay', modo === 'pregunta' && !$('enviar').disabled && respuestaLlegada());   // ya terminó de contestar
  }
  function firmaChat(){ var c = $('chat'), u = c.lastElementChild; return c.children.length + ':' + (u ? u.textContent.length : 0); }
  new MutationObserver(function(){
    // plegada: una respuesta terminada (ya no está «Pensando…») enciende la pastilla con un latido
    if (modo === 'pastilla' && !hayNuevo && firmaChat() !== firmaPlegada && !$('chat').querySelector('.pensando')){ hayNuevo = true; pintarPastilla(true); }
    actualizarLinea(); medir();
  }).observe($('chat'), {childList: true, subtree: true, characterData: true});

  // El alto que necesita el modo pregunta (barra + la caja y su línea); Python lo limita.
  var tMedir = null;
  function medir(){
    if (modo !== 'pregunta') return;
    clearTimeout(tMedir);
    tMedir = setTimeout(function(){
      var h = document.querySelector('.tabs').offsetHeight + document.querySelector('.pie').offsetHeight + 4;
      var a = api(); if (a && a.clase_alto) a.clase_alto(Math.ceil(h + 2));
    }, 60);
  }
  if (window.ResizeObserver) new ResizeObserver(medir).observe(document.querySelector('.pie'));

  function poner(nuevo, enfocar){
    var a = api();
    if (nuevo === 'pregunta' && modo !== 'pregunta')        // al abrir la caja, lo de antes se queda en el chat entero
      [].forEach.call($('chat').children, function(h){ h.dataset.cvVieja = '1'; });
    if (nuevo === 'pastilla' && modo !== 'pastilla') firmaPlegada = firmaChat();
    modo = nuevo;
    var raiz = document.documentElement;
    ['abierto', 'pastilla', 'pregunta'].forEach(function(m){ raiz.classList.toggle('cv-' + m, m === modo); });
    if (modo === 'abierto') [].forEach.call($('chat').children, function(h){ delete h.dataset.cvVieja; });
    if (hayNuevo){ hayNuevo = false; pintarPastilla(false); }                       // abrirla (o volver a plegar) la deja en reposo
    actualizarLinea();
    var hecho = a && a.clase_modo ? a.clase_modo(modo) : Promise.resolve();
    Promise.resolve(hecho).then(function(){
      if (modo === 'pregunta') medir();
      if (modo === 'abierto') $('chat').scrollTop = $('chat').scrollHeight;
      if (enfocar && modo !== 'pastilla') setTimeout(function(){ $('entrada').focus(); }, 40);
    });
  }
  window.modoClase = function(m, enfocar){ poner(m, enfocar !== false); };
  // Lo que movió el tutor en la clase, con «↺ Devolver», al pie de su última respuesta (en la clase queda la ficha gris).
  window.cvMovi = function(t){
    var ult = [].filter.call($('chat').children, function(h){ return h.classList.contains('tutor-m'); }).pop();
    var donde = ult && ult.querySelector('.bloques'); if (!donde) return;
    var d = document.createElement('div'); d.className = 'marcas cv-movi';
    d.innerHTML = '<i></i><span></span><button type="button" class="cv-btn">↺ Devolver</button>';
    d.querySelector('span').textContent = t;
    d.querySelector('button').onclick = function(){
      var a = api(); if (!a || !a.clase_devolver) return;
      this.disabled = true; this.textContent = 'Devuelto';
      a.clase_devolver();
    };
    donde.appendChild(d); medir();
  };
  // Los cambios del tutor que ya estaban en la clase (de otras sesiones), cada uno con su «Deshacer».
  window.cvCambios = function(lista){
    if (!lista || !lista.length || document.querySelector('.cv-capa-aviso')) return;
    var d = document.createElement('div'); d.className = 'nota cv-capa-aviso';
    d.innerHTML = '<b>En esta clase hay ' + lista.length + ' cambio' + (lista.length > 1 ? 's' : '') + ' del tutor</b> (se guardan aparte; la guía no cambia):';
    lista.forEach(function(c){
      var f = document.createElement('div'); f.className = 'marcas cv-movi';
      f.innerHTML = '<i></i><span></span><button type="button" class="cv-btn">↺ Deshacer</button>';
      f.querySelector('span').textContent = c.resumen + (c.fecha ? ' · ' + c.fecha : '');
      f.querySelector('button').onclick = function(){
        var a = api(); if (!a || !a.deshacer) return;
        var b = this; b.disabled = true; b.textContent = 'Deshaciendo…';
        a.deshacer(c.id, false).then(function(){ b.textContent = 'Deshecho'; });
      };
      d.appendChild(f);
    });
    $('chat').appendChild(d);
  };
  window.moduloClase = function(t){ var s = $('cvModulo'); if (s) s.textContent = t ? '· ' + t : ''; };

  // Plegar solo: en modo pregunta, si sale el ratón y no hay nada escrito ni respuesta a la vista.
  document.addEventListener('mouseleave', function(){
    if (modo !== 'pregunta') return;
    clearTimeout(tCerrar);
    tCerrar = setTimeout(function(){
      var vacio = !$('entrada').value.trim() && !$('cvLinea').classList.contains('hay') && !document.querySelector('#adjuntos:not([hidden])');
      if (modo === 'pregunta' && vacio && document.activeElement !== $('entrada')) poner('pastilla');
    }, 900);
  });
  document.addEventListener('mouseenter', function(){ clearTimeout(tCerrar); });
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape' && modo === 'pregunta'){ e.preventDefault(); poner('pastilla'); } });

  function iniciar(){
    armar();
    $('entrada').addEventListener('input', revisarEscribe); $('entrada').addEventListener('focus', revisarEscribe); $('entrada').addEventListener('blur', revisarEscribe);
    new MutationObserver(revisarPensando).observe($('enviar'), {attributes: true, attributeFilter: ['disabled']});
    var ultimoTema = temaPanel();                                                   // si cambia el tema, se redibuja todo
    new MutationObserver(function(){ if (temaPanel() !== ultimoTema){ ultimoTema = temaPanel(); pintarTodo(); } }).observe(document.documentElement, {attributes: true, attributeFilter: ['class']});
    revisarEscribe(); revisarPensando();
    var a = api();
    if (a && a.clase_inicio) a.clase_inicio().then(function(r){ r = r || {}; if (r.modulo) window.moduloClase(r.modulo); poner(r.modo || 'abierto', false); });
  }
  // después del arranque de panel.html (que pone la bienvenida y la barra)
  function luego(){ setTimeout(iniciar, 30); }
  if (api()) luego(); else window.addEventListener('pywebviewready', luego);
})();
