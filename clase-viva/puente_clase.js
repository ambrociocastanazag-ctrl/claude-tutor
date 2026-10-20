/* El puente de la clase viva: va DENTRO de la página de la guía (lo inyecta clase_viva.py al cargar) y es lo único
   que el tutor sabe de ella. No cambia la guía: solo la lee, la desplaza y le deja un hueco al tutor.

   PuenteClase.mapa(forzar)    → {modulo, titulo, num, mapa: [{ref, tipo, texto, ...}], firma, vista, ultimo}
                                  mapa: cada pieza del módulo que se ve (títulos, párrafos, interactivos, fórmulas, pasos,
                                  controles con su valor…) con un ref estable («m03-12»). firma cambia si cambia el mapa.
   PuenteClase.encuadrar(refs)  si lo primero de refs no está a la vista, desplaza la clase hasta ahí (al centro)
   PuenteClase.rect(ref)        → {x, y, w, h, dpr} en px CSS de la ventana, {otro: "m05"} si es de otro módulo, o null
   PuenteClase.reservar(px)     deja px a la derecha para el tutor abierto (0 = toda la pantalla)
   PuenteClase.pregunta(spec) / quitarPregunta() / tema() / ejes(ref)   la pregunta flotante, el tema y los ejes de una gráfica (más abajo)
   PuenteClase.hacer / devolver   las manos del tutor: cursor, onda y la ficha «Devolver» (más abajo; usa window.Profe)
   Avisa a Python (window.pywebview.api): puente_listo(), modulo_cambio(id), desplazado(), atajo_pregunta() (Ctrl+Espacio),
   devuelto() (la ficha «Devolver»), pregunta_respondida(texto, acerto). */
(function(){
  if (window.PuenteClase) return;
  var PIEZAS = [                       // [selector, tipo]: el primero que encaja gana (por eso lo más concreto va antes)
    ['.js-plotly-plot', 'gráfica'], ['[data-widget="deduccion"]', 'deducción'], ['[data-widget="quiz"]', 'quiz'], ['[data-widget]', 'interactivo'],
    ['.paso-d', 'paso de la deducción'], ['.formula-caja', 'fórmula'], ['.error-tipico', 'error típico'],
    ['.turno', 'tu turno'], ['.matlab-caja', 'en MATLAB'], ['details > summary', 'desplegable'], ['figure', 'figura'],
    ['table', 'tabla'], ['.pasos > li', 'paso del ejemplo'], ['h1, h2, h3, h4', 'título'], ['.nota', 'nota'],
    ['.lectura, .mensaje-banco', 'lectura'], ['input, select, textarea, button', 'control'], ['p, li', 'texto']
  ];
  var SELECTOR = PIEZAS.map(function(p){ return p[0]; }).join(', ');
  var MAX_PIEZAS = 220, ultimo = null, contador = {};

  function api(){ return window.pywebview && window.pywebview.api; }
  function modulo(){ return document.querySelector('.modulo:not([hidden])'); }
  function limpio(t, n){ t = String(t || '').replace(/\s+/g, ' ').trim(); return t.length > n ? t.slice(0, n - 1) + '…' : t; }
  function visible(el){
    var r = el.getClientRects();                                    // nada: display:none, o dentro de un <details> cerrado
    if (!r.length || !(r[0].width > 0 && r[0].height > 0) && !el.matches('input')) return false;   // sin dibujar todavía
    var s = getComputedStyle(el); return s.visibility !== 'hidden';
  }
  function tipoDe(el){ for (var i = 0; i < PIEZAS.length; i++) if (el.matches(PIEZAS[i][0])) return PIEZAS[i][1]; return 'pieza'; }
  function refDe(el, mod){
    if (!el.dataset.cvRef){ contador[mod.id] = (contador[mod.id] || 0) + 1; el.dataset.cvRef = mod.id + '-' + contador[mod.id]; }
    return el.dataset.cvRef;
  }
  // El texto de una pieza sin repetir el de sus piezas de dentro (un interactivo no copia los textos de sus lecturas).
  function texto(el, tipo, n){
    if (tipo === 'fórmula'){ var f = el.querySelector('[data-tex]'); if (f) return '$$' + f.dataset.tex + '$$'; }
    if (tipo === 'interactivo' || tipo === 'deducción' || tipo === 'quiz'){
      var t = el.querySelector('.banco-titulo, h3, h4, summary');
      return limpio((t ? t.innerText : '') || el.dataset.titulo || '', 110);
    }
    if (tipo === 'control') return etiqueta(el);
    if (tipo === 'gráfica') return ejes(el);
    var c = el.cloneNode(true);
    // lo que no se ve no se cuenta (pasos de la deducción aún cerrados, la respuesta de un desplegable cerrado)
    [].forEach.call(c.querySelectorAll('[hidden], script, style, details:not([open]) > :not(summary), button, input, select, textarea, .modebar-container'), function(x){ x.remove(); });
    [].forEach.call(c.querySelectorAll('p, li, div, h1, h2, h3, h4, h5, summary, br, td, th, tr'), function(x){ x.append(' '); });   // que no se peguen las palabras
    [].forEach.call(c.querySelectorAll('mjx-container'), function(m){        // las fórmulas en línea, como LaTeX
      var tex = m.closest('[data-tex]'); m.replaceWith(tex ? '$' + tex.dataset.tex + '$' : ' (fórmula) ');
    });
    [].forEach.call(c.querySelectorAll('[data-widget]'), function(x){ x.remove(); });   // cada interactivo es su propia pieza
    return limpio(c.textContent, n);
  }
  // Una gráfica de Plotly: sus ejes y el tamaño de su área de datos, para que el tutor dibuje encima con sus unidades.
  function ejes(gd){
    var L = gd._fullLayout; if (!L || !L._size || !L.xaxis || !L.yaxis) return 'gráfica';
    function eje(a, n){
      var t = (a.title && (a.title.text || a.title)) || n, r = a.range || [];
      return n + ' «' + limpio(String(t).replace(/<[^>]+>/g, ''), 30) + '» de ' + (+r[0]).toFixed(2).replace(/\.?0+$/, '') + ' a ' + (+r[1]).toFixed(2).replace(/\.?0+$/, '');
    }
    var curvas = (gd.data || []).map(function(t){ return t.name; }).filter(function(n){ return n && t2(n); });
    function t2(n){ return typeof n === 'string' && n.length < 40; }
    return eje(L.xaxis, 'x') + ' · ' + eje(L.yaxis, 'y') + ' · área de datos ' + Math.round(L._size.w) + '×' + Math.round(L._size.h) + ' px'
      + (curvas.length ? ' · curvas: ' + curvas.slice(0, 6).join(', ') : '');
  }
  function etiqueta(el){
    var l = el.getAttribute('aria-label') || el.title || '';
    if (!l && el.id) { var lab = document.querySelector('label[for="' + el.id + '"]'); if (lab) l = lab.textContent; }
    if (!l && el.closest('label')) l = el.closest('label').textContent;
    if (!l) l = el.placeholder || (el.tagName === 'BUTTON' ? el.textContent : '') || el.name || '';
    return limpio(l, 60);
  }
  function datosControl(el, p){
    p.control = el.tagName === 'INPUT' ? (el.type || 'texto') : el.tagName.toLowerCase();
    if (el.tagName === 'BUTTON') return;
    if (el.type === 'checkbox' || el.type === 'radio') p.valor = el.checked ? 'marcado' : 'sin marcar';
    else p.valor = limpio(el.value, 60);
    if (el.type === 'range'){ p.min = el.min; p.max = el.max; }
  }
  function donde(el){
    var r = el.getBoundingClientRect(), h = innerHeight;
    return r.bottom < 0 ? 'arriba' : r.top > h ? 'abajo' : 'a la vista';
  }

  function mapa(){
    var mod = modulo(); if (!mod) return {modulo: null, mapa: []};
    var lista = [], vistos = new Set();
    [].forEach.call(mod.querySelectorAll(SELECTOR), function(el){
      if (lista.length >= MAX_PIEZAS || !visible(el)) return;
      if (el.closest('.modebar, .modebar-container')) return;          // los botones de zoom de Plotly no son de la clase
      var tipo = tipoDe(el);
      if (tipo === 'título' && el.closest('[data-widget]')) return;      // el título de un interactivo ya va en el interactivo
      // dentro de un interactivo solo cuentan sus controles y lecturas; un párrafo dentro de otra pieza no se repite
      var padre = el.parentElement && el.parentElement.closest('[data-cv-pieza]');
      if (tipo === 'texto' && padre && padre !== mod) return;
      if (tipo === 'texto' && el.closest('.formula-caja, .error-tipico .nota, table, figure')) return;
      var tx = texto(el, tipo, /^(título|desplegable|lectura|control)$/.test(tipo) ? 140 : 320);
      if (!tx && tipo !== 'interactivo' && tipo !== 'control') return;
      el.setAttribute('data-cv-pieza', '');
      var p = {ref: refDe(el, mod), tipo: tipo, texto: tx};
      if (el.closest('.cv-del-tutor')) p.tutor = true;                   // la puso (o la cambió) el tutor
      if (el.dataset.widget) { p.widget = el.dataset.widget; if (el.dataset.id) p.datos = el.dataset.id; }
      if (tipo === 'control') datosControl(el, p);
      var dentro = el.parentElement && el.parentElement.closest('[data-widget]');
      if (dentro && dentro.dataset.cvRef) p.en = dentro.dataset.cvRef;
      if (vistos.has(p.ref)) return; vistos.add(p.ref);
      p.donde = donde(el);
      lista.push(p);
    });
    var firma = lista.map(function(p){ return p.ref + p.tipo + p.texto + (p.valor || ''); }).join('|');
    var h = 0; for (var i = 0; i < firma.length; i++) h = (h * 31 + firma.charCodeAt(i)) | 0;
    var alto = document.documentElement.scrollHeight - innerHeight;
    return {modulo: mod.id, num: mod.dataset.num, titulo: mod.dataset.titulo || '', mapa: lista, firma: String(h),
            vista: alto > 0 ? Math.round(100 * scrollY / alto) + ' % hacia abajo' : 'todo el módulo cabe en la pantalla',
            ultimo: ultimo};
  }

  function buscar(ref){ return document.querySelector('[data-cv-ref="' + String(ref).replace(/"/g, '') + '"]'); }
  function rect(ref){
    var el = buscar(ref); if (!el) return null;
    var mod = el.closest('.modulo');
    if (mod && mod.hidden) return {otro: mod.id};
    if (!visible(el)) return {oculto: true};
    var r = el.getBoundingClientRect(), L = el._fullLayout;
    if (L && L._size && el.classList.contains('js-plotly-plot'))       // una gráfica: solo su área de datos (donde van las curvas)
      return {x: r.left + L._size.l, y: r.top + L._size.t, w: L._size.w, h: L._size.h, dpr: devicePixelRatio, vw: innerWidth, vh: innerHeight};
    return {x: r.left, y: r.top, w: r.width, h: r.height, dpr: devicePixelRatio, vw: innerWidth, vh: innerHeight};
  }
  function encuadrar(refs){
    var els = (refs || []).map(buscar).filter(function(el){ return el && visible(el) && !el.closest('.modulo[hidden]'); });
    if (!els.length) return false;
    var r = els[0].getBoundingClientRect();
    if (r.top >= 0 && r.bottom <= innerHeight) return false;        // ya se ve
    els[0].scrollIntoView({block: r.height > innerHeight * 0.8 ? 'start' : 'center', behavior: 'instant'});
    return true;
  }
  var reservado = 0;                                 // px que tapa el tutor abierto a la derecha (las figuras no van ahí)
  function reservar(px){
    reservado = Math.max(0, +px || 0); if (typeof pedir === 'function') pedir();
    var st = document.getElementById('cv-reserva');
    if (!st){ st = document.createElement('style'); st.id = 'cv-reserva'; document.head.appendChild(st); }
    // El tutor de la guía (el de claude.ai) no se usa aquí: lo reemplaza el de la clase viva.
    st.textContent = '#abrir-tutor, #tutor{display:none !important}' + (px > 0 ? ' .app{margin-right:' + Math.round(px) + 'px !important}' : '');
    requestAnimationFrame(function(){ window.dispatchEvent(new Event('resize')); });   // Plotly se remide al nuevo ancho
    return true;
  }

  // Lo último que tocó (para que el tutor sepa de qué habla): el control y su valor.
  function anotar(e){
    if (moviendo) return;                                // lo mueve el tutor, no él
    var el = e.target.closest && e.target.closest('input, select, textarea, button, summary, [data-widget]');
    if (!el || !modulo() || !modulo().contains(el)) return;
    var mod = modulo(), w = el.closest('[data-widget]');
    var p = {ref: refDe(el, mod), que: etiqueta(el) || limpio(el.textContent, 40)};
    if (el.matches('input, select, textarea')) { var d = {}; datosControl(el, d); if (d.valor != null) p.valor = d.valor; }
    if (w && w !== el) p.en = refDe(w, mod) + ' (' + (w.dataset.widget || '') + ')';
    ultimo = p;
  }
  document.addEventListener('change', anotar, true);
  document.addEventListener('input', anotar, true);
  document.addEventListener('click', anotar, true);

  // Al terminar de desplazarse (o al cambiar el tamaño), las marcas del tutor se vuelven a poner en su sitio.
  var tDesp = null;
  function desplazado(){ clearTimeout(tDesp); tDesp = setTimeout(function(){ var a = api(); if (a && a.desplazado) a.desplazado(); }, 220); }
  window.addEventListener('scroll', desplazado, true);
  window.addEventListener('resize', desplazado);
  // Al cambiar de módulo, las marcas del anterior ya no sirven.
  var actual = null;
  new MutationObserver(function(){
    var m = modulo(); if (!m || m.id === actual) return;
    actual = m.id; quitarPregunta(); ficha = null; quitarManos();   // lo del módulo anterior ya no sirve
    var a = api(); if (a && a.modulo_cambio) a.modulo_cambio(m.id);
  }).observe(document.body, {attributes: true, subtree: true, attributeFilter: ['hidden']});
  // Ctrl+Espacio: la caja del tutor para preguntar sin dejar la clase.
  document.addEventListener('keydown', function(e){
    if (e.ctrlKey && (e.code === 'Space' || e.key === ' ')){ e.preventDefault(); var a = api(); if (a && a.atajo_pregunta) a.atajo_pregunta(); }
  }, true);

  /* ---- La capa de dibujo del tutor (window.Profe): una capa SVG propia, fija sobre la ventana de la clase ----
     Va en px de la ventana (como getBoundingClientRect), se redibuja al desplazar, redimensionar o cambiar de tema.
     No captura clics, salvo lo que se puede tocar (la ficha «Devolver» y las opciones de la pregunta).
     PuenteClase.tema()            → 'claro' | 'oscuro'
     PuenteClase.ejes(ref)         → {q: [q0, q1], p: [p0, p1]} de una gráfica de Plotly, o null
     PuenteClase.pregunta(spec)    spec = {pregunta, opciones: [..], correcta?, explicacion?, ref?, puntos?: [{q, p, letra}]} → true
     PuenteClase.quitarPregunta()  */
  var NS = 'http://www.w3.org/2000/svg', capa = null, raf = 0;
  var manos = null, tManos = null, activoEl = null, ficha = null, preg = null, tPreg = null;
  function Pf(){ return window.Profe || null; }
  function tema(){
    var d = document.documentElement.getAttribute('data-theme');
    if (d === 'dark') return 'oscuro'; if (d === 'light') return 'claro';
    return window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'oscuro' : 'claro';
  }
  function rangos(ref){
    var el = buscar(ref), L = el && el._fullLayout;
    if (!L || !L.xaxis || !L.yaxis || !L.xaxis.range || !L.yaxis.range) return null;
    return {q: [+L.xaxis.range[0], +L.xaxis.range[1]], p: [+L.yaxis.range[0], +L.yaxis.range[1]]};
  }
  function asegurarCapa(){
    if (capa && capa.isConnected) return capa;
    capa = document.createElementNS(NS, 'svg'); capa.id = 'cv-capa';
    capa.style.cssText = 'position:fixed;left:0;top:0;pointer-events:none;overflow:visible;z-index:2147483000';
    capa.addEventListener('click', function(e){
      var d = e.target.getAttribute && e.target.getAttribute('data-cv'); if (!d) return;
      e.stopPropagation(); e.preventDefault();
      if (d === 'dev') devolverFicha(); else if (d === 'cerrar') { ficha = null; pedir(); }
      else if (d.indexOf('op:') === 0) elegir(+d.slice(3));
    });
    document.body.appendChild(capa); return capa;
  }
  function pedir(){ if (!raf) raf = requestAnimationFrame(function(){ raf = 0; try { dibujar(); } catch (e) { if (window.console) console.error('capa', e); } }); }
  function lim01(x){ return Math.max(0, Math.min(1, x)); }
  function corto(el){
    var l = etiqueta(el), m = /\(([^)]{1,4})\)/.exec(l);
    if (m) return m[1];
    return limpio(l.split(/[\s:·—-]/)[0], 8) || 'valor';
  }
  function entra(r, V){ return r.width > 0 && r.bottom > 0 && r.top < V.h && r.right > 0 && r.left < V.w; }
  function ajusta(txt, px, ancho){          // una línea que cabe en ancho (con «…»)
    var u = window.Profe.util; txt = String(txt || '');
    while (txt.length > 1 && u.medir(txt, px, 600) > ancho) txt = txt.slice(0, -2) + '…';
    return txt;
  }

  // lo que hace el tutor en el momento: el cursor con su riel y paradas, o la onda al pulsar
  function dibujarManos(t, V, now){
    if (!manos || !manos.el.isConnected) return {g: '', anim: false};
    var r = manos.el.getBoundingClientRect(); if (!entra(r, V)) return {g: '', anim: true};
    var P = Pf(), g = '';
    if (manos.tipo === 'boton'){
      g += P.pulsado({boton: {x: r.left, y: r.top, w: r.width, h: r.height, r: 8}, variante: 'onda', t: lim01((now - manos.t0) / 900), tema: t}).g;
    } else {
      var el = manos.el, mn = el.min === '' ? NaN : +el.min, mx = el.max === '' ? NaN : +el.max, val = parseFloat(el.value);
      var todos = manos.paradas.concat([val]);
      if (!isFinite(mn)) mn = Math.min.apply(null, todos) - 1; if (!isFinite(mx)) mx = Math.max.apply(null, todos) + 1;
      var tope = el.type === 'range' ? 8 : 4, Y = r.top + r.height / 2;
      g += P.deslizador({riel: {x1: r.left + tope, x2: r.right - tope, y: Y}, min: mn, max: mx, valor: val, paradas: manos.paradas, parada: manos.k,
        moviendo: manos.moviendo, etiqueta: corto(el), variante: 'rotulo', tema: t}).g;
      var xs = r.left + tope + (r.width - 2 * tope) * ((val - mn) / ((mx - mn) || 1));      // y la flecha del tutor en el pulgar
      g += P.util.cursor(xs + 8, Y - 2, P.paleta('azul', t), 1, false);
    }
    if (manos.texto){
      var X = manos.tipo === 'boton' ? r.left + r.width / 2 : r.left + (r.width) * ((parseFloat(manos.el.value) - (+manos.el.min || 0)) / ((+manos.el.max || 100) - (+manos.el.min || 0)) || 0);
      var der = X < V.w * 0.6, ay = manos.tipo === 'boton' ? r.top + r.height / 2 : r.top + r.height / 2 - 34;
      var ax = manos.tipo === 'boton' ? (der ? r.right + 4 : r.left - 4) : X + (der ? 58 : -58);
      g += P.globo({ancla: {x: Math.max(24, Math.min(V.w - 24, ax)), y: ay}, texto: manos.texto, lado: der ? 'derecha' : 'izquierda', variante: 'pico', distancia: 14, ancho: 230, tema: t, t: lim01((now - manos.t0) / 350)}).g;
    }
    return {g: g, anim: true};
  }

  // la ficha gris «Devolver» (una junto a la pieza, o una sola en la esquina si tocó varias)
  function piezasMovidas(){ var l = []; originales.forEach(function(v, el){ if (el.isConnected) l.push(el); }); return l; }
  function dibujarFicha(t, V, now){
    var els = piezasMovidas(); if (!ficha || !els.length || moviendo) return {g: '', hits: '', anim: false};
    var P = Pf(), tt = lim01((now - ficha.t0) / 350), d, hits = '';
    if (els.length === 1){
      var r = els[0].getBoundingClientRect(); if (!entra(r, V)) return {g: '', hits: '', anim: false};
      d = P.devolver({x: Math.min(r.right + 8, V.w - 8), y: Math.min(V.h - 24, r.top + r.height / 2 + 46), ancla: 'd', tema: t, t: tt});
      hits = '<rect data-cv="dev" x="' + d.x + '" y="' + d.y + '" width="' + d.w + '" height="' + d.h + '" fill="transparent" style="pointer-events:all;cursor:pointer"/>';
    } else {
      d = P.devolver({variante: 'esquina', x: V.w - 16, y: V.h - 28, ancla: 'd', tema: t, t: tt});
      var cx = d.x + d.w - 40;
      hits = '<rect data-cv="dev" x="' + d.x + '" y="' + d.y + '" width="' + (cx - d.x) + '" height="' + d.h + '" fill="transparent" style="pointer-events:all;cursor:pointer"/>' +
             '<rect data-cv="cerrar" x="' + cx + '" y="' + d.y + '" width="' + (d.x + d.w - cx) + '" height="' + d.h + '" fill="transparent" style="pointer-events:all;cursor:pointer"/>';
    }
    return {g: d.g, hits: hits, anim: tt < 1};
  }

  // la pregunta flotante: chips junto a la pieza, o sobre la gráfica (variante 'grafica') con sus puntos
  function dibujarPregunta(t, V, now){
    if (!preg) return {g: '', hits: '', anim: false};
    var P = Pf(), s = preg.spec, ops = s.opciones || [], est = preg.est, tt = lim01((now - preg.t0) / 350), U = P.util;
    var rc = s.ref ? rect(s.ref) : null; if (rc && (rc.otro || rc.oculto || rc.w == null)) rc = null;
    var rg = rc && s.puntos && s.puntos.length && s.ref ? rangos(s.ref) : null;
    var base = {pregunta: s.pregunta, opciones: ops, correcta: s.correcta, estado: est, elegida: preg.elegida, tema: t, t: tt}, hits = '', g = '';
    var fallo = 'Casi. Prueba otra.';
    function msgs(ancho){ return {acierto: ajusta('¡Eso!' + (s.explicacion ? ' ' + s.explicacion : ''), 13, ancho), fallo: fallo}; }
    if (rg){
      var E = P.ejes({x0: rc.x, x1: rc.x + rc.w, y0: rc.y + rc.h, y1: rc.y, q: rg.q, p: rg.p});
      var pts = s.puntos.map(function(p, i){ var xy = E.px(p.q, p.p); return {x: xy[0], y: xy[1], letra: p.letra || String.fromCharCode(65 + i)}; });
      var m = P.pregunta(Object.assign({}, base, {variante: 'grafica', puntos: [], estado: 'pregunta', ancho: 190, caja: {x: 0, y: 0}}));
      var fuera = rc.x + rc.w + 16 + m.w <= V.w - 8, cx = fuera ? rc.x + rc.w + 16 : Math.max(8, rc.x + rc.w - m.w - 8), cy = fuera ? Math.max(8, rc.y) : Math.max(8, rc.y + 8);
      var r = P.pregunta(Object.assign({}, base, {variante: 'grafica', puntos: pts, ancho: 190, caja: {x: cx, y: cy}, mensajes: msgs(m.w - 24)}));
      g = r.g;
      pts.forEach(function(p, i){
        if (est !== 'acierto') hits += '<circle data-cv="op:' + i + '" cx="' + p.x + '" cy="' + p.y + '" r="15" fill="transparent" style="pointer-events:all;cursor:pointer"/>';
      });
    } else {
      var ancho = 280, pad = 12, m2 = P.pregunta(Object.assign({}, base, {estado: 'pregunta', ancla: {x: 0, y: 0}, lado: 'derecha', ancho: ancho}));
      var w = m2.caja.w, h = m2.caja.h + 26, A, lado, C;
      if (rc){
        var cyc = Math.max(20, Math.min(V.h - 20, rc.y + rc.h / 2)), cxc = Math.max(20, Math.min(V.w - 20, rc.x + rc.w / 2));
        var ancha = rc.w > V.w * 0.5, abajo = rc.y + rc.h + 24 + h <= V.h - 8, arriba = rc.y - 24 - h >= 8;
        if (ancha && arriba){ lado = 'arriba'; A = {x: cxc, y: rc.y}; C = {x: Math.max(8, Math.min(V.w - w - 8, cxc - w / 2)), y: rc.y - 24 - h}; }   // encima: debajo suelen ir los cálculos
        else if (ancha && abajo){ lado = 'abajo'; A = {x: cxc, y: rc.y + rc.h}; C = {x: Math.max(8, Math.min(V.w - w - 8, cxc - w / 2)), y: rc.y + rc.h + 24}; }
        else if (rc.x + rc.w + 22 + w <= V.w - 8){ lado = 'derecha'; A = {x: rc.x + rc.w, y: cyc}; C = {x: rc.x + rc.w + 22, y: Math.max(8, Math.min(V.h - h - 8, cyc - h / 2))}; }
        else if (rc.x - 22 - w >= 8){ lado = 'izquierda'; A = {x: rc.x, y: cyc}; C = {x: rc.x - 22 - w, y: Math.max(8, Math.min(V.h - h - 8, cyc - h / 2))}; }
        else if (abajo){ lado = 'abajo'; A = {x: cxc, y: rc.y + rc.h}; C = {x: Math.max(8, Math.min(V.w - w - 8, cxc - w / 2)), y: rc.y + rc.h + 24}; }
        else { lado = 'arriba'; A = {x: cxc, y: rc.y}; C = {x: Math.max(8, Math.min(V.w - w - 8, cxc - w / 2)), y: Math.max(8, rc.y - 24 - h)}; }
      } else { lado = 'izquierda'; A = {x: V.w - 24, y: 90}; C = {x: V.w - 24 - 22 - w, y: 70}; }
      var r2 = P.pregunta(Object.assign({}, base, {ancla: A, lado: lado, caja: C, ancho: ancho, mensajes: msgs(w - 2 * pad)}));
      g = r2.g;
      // las fichas, donde Profe las pone (se calcula igual que él para poder tocarlas)
      var fq = 14, fo = 13.5, ql = U.envolver(s.pregunta, fq, 600, ancho - 2 * pad), cw = ancho - 2 * pad, x = 0, y = 0, rowH = 30, gap = 6;
      var oy = C.y + 10 + ql.length * 20 + 8;
      ops.forEach(function(op, i){
        var ext = est !== 'pregunta' && i === preg.elegida && (est === 'acierto' || est === 'fallo') ? 18 : 0;
        var bw = U.medir(op, fo, 600) + 24 + ext;
        if (x > 0 && x + bw > cw){ x = 0; y += rowH + gap; }
        if (est !== 'acierto') hits += '<rect data-cv="op:' + i + '" x="' + (C.x + pad + x) + '" y="' + (oy + y) + '" width="' + bw + '" height="' + rowH + '" rx="15" fill="transparent" style="pointer-events:all;cursor:pointer"/>';
        x += bw + gap;
      });
    }
    return {g: g, hits: hits, anim: tt < 1};
  }

  function dibujar(){
    var P = Pf(); asegurarCapa();
    var V = {w: document.documentElement.clientWidth - reservado, h: innerHeight};      // sin el hueco del tutor abierto
    capa.setAttribute('width', V.w + reservado); capa.setAttribute('height', V.h);
    if (!P){ capa.innerHTML = ''; return; }
    var t = tema(), now = performance.now(), a = dibujarManos(t, V, now), f = dibujarFicha(t, V, now), q = dibujarPregunta(t, V, now);
    var b = dibujarComportamientos(t, V);
    capa.innerHTML = b.g + a.g + f.g + q.g + f.hits + q.hits;
    if (a.anim || f.anim || q.anim) pedir();
  }
  window.addEventListener('scroll', pedir, true);
  window.addEventListener('resize', pedir);
  new MutationObserver(pedir).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
  if (window.matchMedia){ var mq = matchMedia('(prefers-color-scheme: dark)'); if (mq.addEventListener) mq.addEventListener('change', pedir); }

  function pregunta(spec){
    if (!spec || !spec.pregunta || !(spec.opciones || []).length) return false;
    clearTimeout(tPreg); if (spec.ref) encuadrar([spec.ref]);
    preg = {spec: spec, est: 'pregunta', elegida: null, t0: performance.now()}; pedir(); return true;
  }
  function quitarPregunta(){ clearTimeout(tPreg); var habia = !!preg; preg = null; pedir(); return habia; }
  function elegir(i){
    if (!preg || preg.est === 'acierto' || preg.cerrando) return;
    var s = preg.spec, texto = (s.opciones || [])[i];
    if (texto == null && s.puntos && s.puntos[i]) texto = s.puntos[i].letra;
    var c = s.correcta, acerto = typeof c === 'number' ? i === c : null;
    preg.elegida = i; preg.t0 = performance.now() - 350;
    clearTimeout(tPreg);
    if (acerto === null){ preg.cerrando = true; tPreg = setTimeout(quitarPregunta, 700); }
    else { preg.est = acerto ? 'acierto' : 'fallo'; if (acerto) tPreg = setTimeout(quitarPregunta, 2500); }
    pedir();
    var a = api(); if (a && a.pregunta_respondida) a.pregunta_respondida(String(texto == null ? '' : texto), acerto);
  }

  /* ---- Las manos de explicación: mover deslizadores y pulsar botones de los interactivos ----
     acciones: [{tipo: "mover", ref, a, texto, ms, pausa} | {tipo: "mover", ref, pasos: [{a, texto, pausa}]} | {tipo: "pulsar", ref, texto}]
     PuenteClase.validar(acciones) → [{ok, hecho | error}] sin tocar nada; PuenteClase.hacer(acciones) → Promise (en orden);
     PuenteClase.devolver() deja los deslizadores como estaban antes del tutor. Nunca toca deducciones, quizzes ni su «Tu turno».
     Mientras mueve, dibuja el cursor «Tutor» con las paradas en el riel (o la onda al pulsar); al terminar deja la ficha «Devolver».
     Si ella toca el control mientras el tutor lo mueve, el tutor suelta. */
  var originales = new Map(), moviendo = false, trabajando = 0, vuelta = 0;
  function esperar(ms){ return new Promise(function(ok){ setTimeout(ok, ms); }); }
  function prohibido(el){ return el.closest('[data-widget="deduccion"], [data-widget="quiz"], .turno, .mod-pie'); }
  function revisar(a){
    var el = a && buscar(a.ref);
    if (!el) return {ok: false, error: '«' + (a && a.ref) + '» no está en la clase'};
    if (el.closest('.modulo[hidden]')) return {ok: false, error: '«' + a.ref + '» es de otro módulo'};
    if (prohibido(el)) return {ok: false, error: '«' + a.ref + '» es de una deducción, un quiz o su Tu turno: eso lo hace él'};
    var nombre = etiqueta(el) || a.ref;
    if (a.tipo === 'pulsar'){
      if (el.tagName !== 'BUTTON' || !el.closest('[data-widget]')) return {ok: false, error: '«' + a.ref + '» no es un botón de un interactivo'};
      return {ok: true, hecho: 'pulsé «' + nombre + '»'};
    }
    if (!el.matches('input[type="range"], input[type="number"]')) return {ok: false, error: '«' + a.ref + '» no es un deslizador'};
    var pasos = a.pasos || [{a: a.a}], malos = pasos.filter(function(p){ return !isFinite(parseFloat(p.a)); });
    if (!pasos.length || malos.length) return {ok: false, error: 'al mover «' + nombre + '» le falta el valor ("a")'};
    return {ok: true, hecho: 'moví «' + nombre + '» a ' + pasos.map(function(p){ return ajustar(el, p.a); }).join(' → ')};
  }
  function ajustar(el, v){
    var min = el.min === '' ? -Infinity : +el.min, max = el.max === '' ? Infinity : +el.max, paso = parseFloat(el.step) || 0;
    v = Math.max(min, Math.min(max, parseFloat(v)));
    if (paso > 0 && isFinite(min)) v = min + Math.round((v - min) / paso) * paso;
    return +v.toFixed(6);
  }
  function poner(el, v){ el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); }
  function deslizar(el, a, ms, mia){
    var desde = parseFloat(el.value), hasta = ajustar(el, a);
    if (!originales.has(el)) originales.set(el, el.value);
    if (el.type !== 'range' || !(ms > 0) || desde === hasta){ poner(el, hasta); el.dispatchEvent(new Event('change', {bubbles: true})); return Promise.resolve(); }
    return new Promise(function(ok){
      var t0 = performance.now();
      (function cuadro(t){
        var k = Math.min(1, (t - t0) / ms), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
        if (mia != null && mia !== vuelta) return ok();          // lo cortaron
        poner(el, k < 1 ? ajustar(el, desde + (hasta - desde) * e) : hasta);
        if (k < 1) requestAnimationFrame(cuadro); else { el.dispatchEvent(new Event('change', {bubbles: true})); ok(); }
      })(t0);
    });
  }
  function quitarManos(){ clearTimeout(tManos); manos = null; activoEl = null; pedir(); }
  // Ella toca lo que el tutor mueve (o una pieza que movió): el tutor suelta y la ficha «Devolver» ya no tiene sentido para esa pieza.
  function ellaToca(e){
    if (!e.isTrusted) return;
    var el = e.target.closest && e.target.closest('input, select, textarea');
    if (!el) return;
    if (moviendo && activoEl && (el === activoEl || activoEl.contains(el))){ ++vuelta; moviendo = false; quitarManos(); }
    if (originales.has(el)){ originales.delete(el); if (!originales.size) ficha = null; pedir(); }
  }
  document.addEventListener('pointerdown', ellaToca, true);
  document.addEventListener('input', ellaToca, true);

  async function hacer(acciones){
    var mia = ++vuelta; moviendo = true; trabajando++; ficha = null; clearTimeout(tManos);           // «Devolver» u otra respuesta cortan este recorrido
    try {
      for (var i = 0; i < (acciones || []).length && mia === vuelta; i++){
        var a = acciones[i]; if (!revisar(a).ok) continue;
        var el = buscar(a.ref); activoEl = el;
        if (a.tipo === 'pulsar'){
          manos = {tipo: 'boton', el: el, texto: a.texto, t0: performance.now()}; pedir();
          await esperar(420); if (mia !== vuelta) break;
          el.click(); await esperar(+a.pausa || 1500); continue;
        }
        var pasos = a.pasos || [{a: a.a, texto: a.texto, pausa: a.pausa}];
        var paradas = pasos.map(function(p){ return ajustar(el, p.a); });
        for (var k = 0; k < pasos.length && mia === vuelta; k++){
          manos = {tipo: 'mover', el: el, texto: pasos[k].texto || '', paradas: paradas, k: k, moviendo: true, t0: performance.now()}; pedir();
          await deslizar(el, pasos[k].a, +a.ms || 900, mia);
          if (manos && mia === vuelta) manos.moviendo = false;
          await esperar(+pasos[k].pausa || (pasos.length > 1 || acciones.length > 1 ? 1600 : 300));
        }
      }
    } finally {
      trabajando--; if (!trabajando) moviendo = false;
      if (mia === vuelta){
        tManos = setTimeout(quitarManos, 1800);                              // el cursor se queda un momento y se va
        if (originales.size) ficha = {t0: performance.now()};                // y queda la ficha para devolverlo
      }
      pedir();
    }
    return true;
  }
  async function devolver(){
    var mia = ++vuelta; moviendo = true; trabajando++; ficha = null; quitarManos();
    try { for (var [el, v] of originales) if (el.isConnected) await deslizar(el, v, 350, mia); }
    finally { originales.clear(); trabajando--; if (!trabajando) moviendo = false; pedir(); }
    return true;
  }
  function devolverFicha(){                  // el clic en la ficha gris
    ficha = null; pedir();
    devolver().then(function(){ var a = api(); if (a && a.devuelto) a.devuelto(); });
  }

  /* ---- Los cambios del tutor (con su permiso): piezas nuevas, textos cambiados y piezas ocultas ----
     PuenteClase.aplicarCambios(id, ops) → {ok, errores: [..], anclas: [..]}   pone las piezas (la guía no cambia: van marcadas)
     PuenteClase.quitarCambios(id)                                             las quita y devuelve los textos de antes
     Cada op apunta a una pieza por su "ref" ("despues", "antes" o "ref") o, al volver a abrir la clase, por su "ancla"
     (el camino dentro del módulo, que no cambia entre sesiones: los refs sí, según lo que esté abierto). Ops: nota, formula,
     ejemplo, ejercicio, interactivo, texto, ocultar. Contrato en clase-viva/README.md («Cambios del tutor»). */
  var deshacer = {}, nCambio = 0;
  (function(){
    var st = document.createElement('style');
    st.textContent = '.cv-del-tutor{position:relative;box-shadow:inset 3px 0 0 var(--cv-tinta,#5b6fd6);padding-left:.85rem !important}' +
      '.cv-sello{display:inline-block;margin:0 0 .35rem;padding:.05rem .45rem;border-radius:999px;font:600 .72rem/1.5 system-ui,sans-serif;' +
      'background:var(--cv-tenue,#e8ecfb);color:var(--cv-tinta,#3d4fb8)}' +
      '.cv-preg{display:flex;flex-wrap:wrap;align-items:center;gap:.5rem;margin:.4rem 0}.cv-preg input{width:9rem;padding:.25rem .45rem}' +
      '.cv-res.bien{color:var(--bien,#2e8b57);font-weight:600}.cv-res.mal{color:var(--falta,#c0392b);font-weight:600}';
    document.head.appendChild(st);
  })();
  function pintarSellos(){                         // el color del sello y del borde, de la paleta plana del tema
    var P = Pf(), t = tema(); if (!P) return;
    var c = P.paleta('azul', t), r = document.documentElement.style;
    r.setProperty('--cv-tinta', c.tinta); r.setProperty('--cv-tenue', c.tenue);
  }
  function md(t){                                  // texto del tutor → HTML seguro (el LaTeX \( \) lo dibuja MathJax)
    return String(t == null ? '' : t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>');
  }
  function hijos(el){ return [].filter.call(el.children, function(h){ return !h.classList.contains('cv-del-tutor') && h.id !== 'cv-capa'; }); }
  function rutaDe(el){
    var mod = el.closest('.modulo'); if (!mod) return null;
    var ruta = [];
    for (var x = el; x && x !== mod; x = x.parentElement) ruta.unshift(hijos(x.parentElement).indexOf(x));
    return ruta.indexOf(-1) >= 0 ? null : {modulo: mod.id, ruta: ruta};
  }
  function desdeRuta(a){
    var x = a && document.getElementById(a.modulo);
    for (var i = 0; x && a.ruta && i < a.ruta.length; i++) x = hijos(x)[a.ruta[i]];
    return x || null;
  }
  function objetivo(op){
    if (op.ancla) return desdeRuta(op.ancla);
    var r = op.despues || op.antes || op.ref;
    return r ? buscar(r) : null;
  }
  function sello(){ return '<span class="cv-sello">✦ del tutor</span><br>'; }
  function pieza(op, id){
    var div = document.createElement(op.op === 'nota' ? (op.estilo === 'error' ? 'aside' : 'p') : 'div');
    div.className = 'cv-del-tutor'; div.dataset.cvCambio = id;
    if (op.op === 'nota'){
      div.className += op.estilo === 'error' ? ' error-tipico' : ' nota';
      div.innerHTML = sello() + (op.estilo === 'recuerda' ? '<b>Recuerda:</b> ' : '') + md(op.texto);
    } else if (op.op === 'formula'){
      div.className += ' formula-caja'; div.innerHTML = sello() + '\\[ ' + String(op.latex || '').replace(/</g, '&lt;') + ' \\]';
    } else if (op.op === 'ejemplo'){
      div.innerHTML = sello() + (op.titulo ? '<h3>' + md(op.titulo) + '</h3>' : '') + '<ol class="pasos">' +
        (op.pasos || []).map(function(p){ return '<li>' + md(p) + '</li>'; }).join('') + '</ol>';
    } else if (op.op === 'ejercicio'){
      div.className += ' turno';
      div.innerHTML = sello() + '<h3>Tu turno · del tutor</h3><p>' + md(op.enunciado) + '</p>' +
        (op.preguntas || []).map(function(q, i){ return '<div class="cv-preg" data-i="' + i + '"><label>' + md(q.texto || 'Respuesta') +
          ' <input type="text" autocomplete="off"></label><button class="boton" type="button">Comprobar</button><span class="cv-res"></span></div>'; }).join('') +
        (op.pista ? '<details><summary>Pista</summary><div><p>' + md(op.pista) + '</p></div></details>' : '') +
        (op.solucion ? '<details><summary>Solución completa</summary><div><p>' + md(op.solucion) + '</p></div></details>' : '');
      [].forEach.call(div.querySelectorAll('.cv-preg'), function(f){
        var q = op.preguntas[+f.dataset.i], inp = f.querySelector('input'), res = f.querySelector('.cv-res');
        var comprobar = function(){
          var v = typeof numeroDe === 'function' ? numeroDe(inp.value) : parseFloat(String(inp.value).replace(',', '.'));
          var r = +q.respuesta, tol = q.tolerancia != null ? +q.tolerancia : Math.max(0.01, Math.abs(r) * 0.005);
          var ok = isFinite(v) && Math.abs(v - r) <= tol;
          res.className = 'cv-res ' + (ok ? 'bien' : 'mal'); res.textContent = ok ? '✓ ¡Bien!' : '✗ Todavía no: revisa y vuelve a intentar';
          var a = api(); if (a && a.ejercicio_resuelto) a.ejercicio_resuelto(id, +f.dataset.i, ok, inp.value);
        };
        f.querySelector('button').onclick = comprobar;
        inp.addEventListener('keydown', function(e){ if (e.key === 'Enter') comprobar(); });
      });
    } else if (op.op === 'interactivo'){
      var did = 'cv-' + id + '-' + (++nCambio);
      div.dataset.widget = op.widget; div.dataset.id = did;
      for (var k in op.attrs || {}) if (/^[a-z][a-z0-9-]*$/.test(k)) div.dataset[k.replace(/-([a-z])/g, function(_, c){ return c.toUpperCase(); })] = op.attrs[k];
      if (typeof FUNC === 'object') FUNC[did] = Object.assign({id: did}, op.datos || {});
      div.className = 'cv-del-tutor';
    }
    return div;
  }
  function aplicarCambios(id, ops){
    var errores = [], anclas = [], puestos = [], tras = new Map();     // tras: lo último que puse después de cada pieza (respeta el orden)
    deshacer[id] = deshacer[id] || [];
    pintarSellos();
    (ops || []).forEach(function(op, i){
      if (op.op === 'regla'){
        var R = ponerRegla(id, op, errores, 'cambio ' + (i + 1));
        if (R){ (REGLAS[id] = REGLAS[id] || []).push(R); anclas.push({refs: R.anclas}); } else anclas.push(null);
        return;
      }
      var el = objetivo(op);
      if (!el){ errores.push('cambio ' + (i + 1) + ': no encuentro «' + (op.despues || op.antes || op.ref || '?') + '»'); anclas.push(null); return; }
      if (op.op !== 'texto' && op.op !== 'ocultar' && !op.ancla){          // nunca dentro de un interactivo o de una deducción: después de él
        var caja = el.parentElement && el.parentElement.closest('[data-widget], .paso-d, .turno');
        if (caja && !caja.classList.contains('cv-del-tutor')) el = caja.closest('[data-widget]') || caja;
      }
      if ((op.op === 'texto' || op.op === 'ocultar') && el.closest('[data-widget]') && !el.matches('[data-widget]')){
        errores.push('cambio ' + (i + 1) + ': no cambio piezas de dentro de un interactivo'); anclas.push(null); return;
      }
      var ancla = op.ancla || rutaDe(el); anclas.push(ancla);
      if (op.op === 'texto'){
        deshacer[id].push({el: el, html: el.innerHTML}); el.innerHTML = md(op.texto); el.classList.add('cv-del-tutor'); el.dataset.cvCambio = id; puestos.push(el);
      } else if (op.op === 'ocultar'){
        deshacer[id].push({el: el, display: el.style.display}); el.style.display = 'none';
      } else {
        var p = op.op === 'codigo' ? ponerCaja(id, op, el, errores, 'cambio ' + (i + 1)) : pieza(op, id);
        if (op.antes) el.before(p); else { (tras.get(el) || el).after(p); tras.set(el, p); }
        puestos.push(p);
        if (op.op === 'codigo') anclas[anclas.length - 1] = Object.assign({}, ancla, {refs: CAJAS[id][CAJAS[id].length - 1].anclas});
        if (op.op === 'interactivo'){
          try { if (typeof iniciarWidget === 'function') iniciarWidget(p); else throw new Error('esta guía no tiene iniciarWidget'); }
          catch (e){ errores.push('cambio ' + (i + 1) + ': ' + (e.message || e)); }
          if (/No se pudo dibujar/.test(p.textContent)) errores.push('cambio ' + (i + 1) + ': ' + p.textContent.trim().slice(0, 160));
        }
      }
    });
    puestos.forEach(function(p){ if (typeof tipografiar === 'function') tipografiar(p); else if (window.MathJax && MathJax.typesetPromise) MathJax.typesetPromise([p]); });
    return {ok: !errores.length, errores: errores, anclas: anclas};
  }
  function quitarCambios(id){
    quitarComportamientos(id);
    [].forEach.call(document.querySelectorAll('[data-cv-cambio="' + String(id).replace(/"/g, '') + '"]'), function(el){
      if (el.classList.contains('cv-del-tutor') && !(deshacer[id] || []).some(function(d){ return d.el === el; })) el.remove();
    });
    (deshacer[id] || []).slice().reverse().forEach(function(d){
      if ('html' in d){ d.el.innerHTML = d.html; d.el.classList.remove('cv-del-tutor'); delete d.el.dataset.cvCambio; }
      if ('display' in d) d.el.style.display = d.display;
    });
    delete deshacer[id];
    window.dispatchEvent(new Event('resize'));
    return true;
  }

  /* ---- Comportamientos del tutor (fase 3): reglas sin código y código aislado ----
     Van como ops de los cambios (aplicarCambios), con su permiso y su Deshacer:
       regla   {cuando: {ref, evento: 'cambia'|'pulsa', valor: {'<'|'>'|'<='|'>='|'='|'distinto': n} | {entre: [a, b]}},
                entonces: [acción], sino: [acción]}      sin «valor», cada cambio dispara «entonces»
       codigo  {despues, titulo, alto, js, lee: {nombre: ref}, toca: {nombre: ref}}   un mini-interactivo en una caja cerrada
     Acciones: {nota: texto, en: ref, color} · {resaltar: ref, color} · {mostrar: ref} · {ocultar: ref} · {mover: ref, a: n} ·
       {pulsar: ref} · {texto: ref, valor: texto} (solo piezas del tutor). En los textos, {valor} y {= 100 - 2*x} (x = el valor).
     El código corre en un <iframe sandbox="allow-scripts"> sin el mismo origen y con CSP sin red: no ve la página, ni sus
     datos, ni internet; habla con la clase solo por postMessage y solo con las piezas que declaró en «lee» y «toca». */
  var REGLAS = {}, CAJAS = {};                       // id del cambio → [reglas] / [cajas de código]
  function refDeEl(el){ var mod = el.closest('.modulo'); return mod ? refDe(el, mod) : null; }
  function resolverRef(op, ref, usados){
    var a = op.ancla && op.ancla.refs && op.ancla.refs[ref], el = a ? desdeRuta(a) : buscar(ref);
    if (el && usados) usados[ref] = a || rutaDe(el);
    return el;
  }
  function valorDe(el){
    if (!el) return NaN;
    if (el.type === 'checkbox' || el.type === 'radio') return el.checked ? 1 : 0;
    var v = typeof numeroDe === 'function' ? numeroDe(el.value) : parseFloat(String(el.value).replace(',', '.'));
    return isFinite(v) ? v : NaN;
  }
  function cumple(c, v){
    if (!c) return true;
    if (!isFinite(v)) return false;
    var e = 1e-9;
    if ('entre' in c) return v >= +c.entre[0] - e && v <= +c.entre[1] + e;
    if ('<' in c) return v < +c['<']; if ('>' in c) return v > +c['>'];
    if ('<=' in c) return v <= +c['<='] + e; if ('>=' in c) return v >= +c['>='] - e;
    if ('=' in c) return Math.abs(v - c['=']) <= e + Math.abs(+c['=']) * 1e-9;
    if ('distinto' in c) return Math.abs(v - c.distinto) > e;
    return true;
  }
  function plantilla(t, v){
    return String(t == null ? '' : t).replace(/\{=\s*([^}]+)\}/g, function(_, ex){
      try { var f = typeof compilar === 'function' ? compilar(ex, 'x') : null, r = f ? f(v) : NaN; return isFinite(r) ? String(+r.toFixed(2)).replace('.', ',') : '?'; }
      catch (e){ return '?'; }
    }).replace(/\{valor\}/g, isFinite(v) ? String(+(+v).toFixed(2)).replace('.', ',') : '?');
  }
  // Lo que pinta un comportamiento en la capa: sus notas (globos) y sus resaltes (lazo a mano). est = {notas: [], resaltes: []}
  function figurasDe(est, t, V){
    var P = Pf(), g = ''; if (!P) return g;
    est.resaltes.forEach(function(r){
      if (!r.el.isConnected) return; var b = r.el.getBoundingClientRect(); if (!entra(b, V)) return;
      g += P.mano.rodear({x: b.left, y: b.top, w: b.width, h: b.height, forma: 'auto', semilla: 5, color: r.color || 'naranja', tema: t, t: 1}).g;
    });
    est.notas.forEach(function(n){
      if (!n.el.isConnected) return; var b = n.el.getBoundingClientRect(); if (!entra(b, V)) return;
      var ancha = b.width > V.w * 0.45, der = b.right + 260 < V.w;
      var A = ancha ? {x: b.left + b.width / 2, y: b.top} : {x: der ? b.right : b.left, y: b.top + b.height / 2};
      g += P.globo({ancla: A, texto: n.texto, lado: ancha ? 'arriba' : der ? 'derecha' : 'izquierda', variante: 'pico', distancia: ancha ? 48 : 12, ancho: 240, color: n.color || 'azul', tema: t, t: 1}).g;   // encima: deja sitio a la ficha del cursor
    });
    return g;
  }
  function dibujarComportamientos(t, V){
    var g = '';
    for (var id in REGLAS) REGLAS[id].forEach(function(R){ g += figurasDe(R.est, t, V); });
    for (var c in CAJAS) CAJAS[c].forEach(function(C){ g += figurasDe(C.est, t, V); });
    return {g: g};
  }
  // Una acción, ya resuelta a elementos. dueño: la regla o la caja (lleva su est y lo que hay que deshacer).
  function accion(a, v, d){
    if (a.tipo === 'nota'){ d.est.notas = d.est.notas.filter(function(n){ return n.el !== a.el; }); d.est.notas.push({el: a.el, texto: plantilla(a.texto, v), color: a.color}); }
    else if (a.tipo === 'resaltar'){ if (!d.est.resaltes.some(function(r){ return r.el === a.el; })) d.est.resaltes.push({el: a.el, color: a.color}); }
    else if (a.tipo === 'mostrar' || a.tipo === 'ocultar'){
      if (!d.vis.has(a.el)) d.vis.set(a.el, a.el.style.display);
      a.el.style.display = a.tipo === 'ocultar' ? 'none' : (d.vis.get(a.el) === 'none' ? '' : d.vis.get(a.el));
      window.dispatchEvent(new Event('resize'));
    }
    else if (a.tipo === 'mover' || a.tipo === 'pulsar'){
      var r = refDeEl(a.el); if (r) hacer([a.tipo === 'mover' ? {tipo: 'mover', ref: r, a: plantilla(a.a, v)} : {tipo: 'pulsar', ref: r}]);
    }
    else if (a.tipo === 'texto' && a.el.classList.contains('cv-del-tutor')){
      a.el.innerHTML = md(plantilla(a.valor, v)); if (typeof tipografiar === 'function') tipografiar(a.el);
    }
    pedir();
  }
  var ACCIONES = ['nota', 'resaltar', 'mostrar', 'ocultar', 'mover', 'pulsar', 'texto'];
  function resolverAcciones(op, lista, usados, errores, donde){
    return (lista || []).map(function(a){
      var tipo = ACCIONES.filter(function(k){ return k in a; })[0];
      if (!tipo){ errores.push(donde + ': una acción no es de ' + ACCIONES.join(', ')); return null; }
      var ref = tipo === 'nota' ? (a.en || a.ref) : a[tipo], el = ref ? resolverRef(op, String(ref), usados) : null;
      if (tipo === 'nota' && !el) el = resolverRef(op, String(op.cuando && op.cuando.ref), usados);
      if (!el){ errores.push(donde + ': no encuentro «' + ref + '»'); return null; }
      if ((tipo === 'mover' || tipo === 'pulsar') && prohibido(el)){ errores.push(donde + ': no toco deducciones, quizzes ni su Tu turno'); return null; }
      return {tipo: tipo, el: el, texto: a.nota, color: a.color, a: a.a, valor: a.valor};
    }).filter(Boolean);
  }
  function ponerRegla(id, op, errores, donde){
    var usados = {}, c = op.cuando || {}, el = c.ref ? resolverRef(op, String(c.ref), usados) : null;
    if (!el){ errores.push(donde + ': no encuentro la pieza de «cuando»'); return null; }
    var R = {el: el, cond: c.valor || null, evento: c.evento === 'pulsa' ? 'click' : 'input', estado: null, est: {notas: [], resaltes: []}, vis: new Map(), oye: []};
    R.si = resolverAcciones(op, op.entonces, usados, errores, donde);
    R.no = resolverAcciones(op, op.sino, usados, errores, donde);
    var t = null;
    var evaluar = function(){
      var v = valorDe(el), ok = cumple(R.cond, v);
      if (R.evento === 'click' || !R.cond){ R.si.forEach(function(a){ accion(a, v, R); }); return; }
      if (ok && R.estado !== true){ R.si.forEach(function(a){ accion(a, v, R); }); }
      else if (ok){ R.si.forEach(function(a){ if (a.tipo === 'nota' || a.tipo === 'texto') accion(a, v, R); }); }     // el texto sigue al valor
      else if (!ok && R.estado !== false){
        if (R.no.length) R.no.forEach(function(a){ accion(a, v, R); });
        else { R.est.notas = []; R.est.resaltes = []; pedir(); }                  // sin «sino»: lo que puso se va
      }
      R.estado = ok;
    };
    var oir = function(){ clearTimeout(t); t = setTimeout(evaluar, 60); };
    if (R.evento === 'click'){ el.addEventListener('click', evaluar); R.oye.push(['click', evaluar]); }
    else { el.addEventListener('input', oir); el.addEventListener('change', oir); R.oye.push(['input', oir], ['change', oir]); evaluar(); }
    R.anclas = usados;
    return R;
  }
  function quitarComportamientos(id){
    (REGLAS[id] || []).concat(CAJAS[id] || []).forEach(function(R){
      (R.oye || []).forEach(function(o){ R.el.removeEventListener(o[0], o[1]); });
      if (R.vis) R.vis.forEach(function(d, el){ el.style.display = d; });
      if (R.quitar) R.quitar();
    });
    delete REGLAS[id]; delete CAJAS[id]; pedir();
  }

  // La caja cerrada del código del tutor. Lo de dentro solo tiene «clase»: valor, al, mover, nota, resaltar, mostrar, ocultar,
  // pulsar, reportar, tema, paleta (y Profe, para dibujar con las figuras de siempre).
  var PUENTE_CAJA = "(function(){var al={},val={};var clase={tema:'claro'," +
    "valor:function(n){return val[n];},al:function(n,f){(al[n]=al[n]||[]).push(f);if(n in val)try{f(val[n]);}catch(e){fallo(e);}}," +
    "mover:function(n,a){manda('mover',n,{a:a});},nota:function(n,t,c){manda('nota',n,{texto:String(t),color:c});},resaltar:function(n,c){manda('resaltar',n,{color:c});}," +
    "mostrar:function(n){manda('mostrar',n);},ocultar:function(n){manda('ocultar',n);},pulsar:function(n){manda('pulsar',n);}," +
    "reportar:function(t){manda('reportar',null,{texto:String(t).slice(0,200)});},quitarNotas:function(){manda('quitarNotas',null);}," +
    "paleta:function(c){if(!window.Profe)return null;var p=Profe.paleta(c||'azul',clase.tema);p.toString=function(){return p.tinta;};return p;}};" +
    "function manda(q,n,x){parent.postMessage(Object.assign({cvCaja:1,que:q,nombre:n},x||{}),'*');}" +
    "function fallo(e){manda('error',null,{texto:String(e&&e.message||e).slice(0,300)});}" +
    "window.onerror=function(m){fallo(m);};window.addEventListener('unhandledrejection',function(e){fallo(e.reason);});" +
    "window.addEventListener('message',function(e){var d=e.data||{};if(e.source!==parent||!d.cvClase)return;" +
    "if(d.tema){clase.tema=d.tema;document.documentElement.className='tema-'+d.tema;}" +
    "if(d.valores)for(var n in d.valores){var antes=val[n];val[n]=d.valores[n];if(antes!==val[n])(al[n]||[]).forEach(function(f){try{f(val[n]);}catch(e){fallo(e);}});}});" +
    "window.clase=clase;})();";
  function srcdoc(op, t){
    var P = Pf(), pa = P ? P.paleta('azul', t) : {papel: '#fff', texto: '#222', borde: '#ccc'};
    var css = 'html,body{margin:0;background:' + pa.papel + ';color:' + pa.texto + ';font:14px/1.4 system-ui,sans-serif}' +
      'html.tema-oscuro{color-scheme:dark}svg,canvas{display:block;max-width:100%}button{font:inherit}' +
      'svg text:not([fill]){fill:currentColor}';                  // el texto de un SVG sin color, en el del tema (no negro)
    return '<!doctype html><html class="tema-' + t + '"><head><meta charset="utf-8">' +
      '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; img-src data: blob:; font-src data:">' +
      '<style>' + css + '</style></head><body><div id="raiz"></div>' +
      '<script>' + (window.CV_PROFE_FUENTE || '').replace(/<\/script/gi, '<\\/script') + '<\/script><script>' + PUENTE_CAJA + '<\/script>' +
      '<script>try{(function(clase, raiz){' + String(op.js).replace(/<\/script/gi, '<\\/script') + '\n})(window.clase, document.getElementById("raiz"));}catch(e){parent.postMessage({cvCaja:1,que:"error",texto:String(e&&e.message||e)},"*");}<\/script></body></html>';
  }
  function ponerCaja(id, op, el, errores, donde){
    var usados = {}, lee = {}, toca = {};
    for (var n in op.lee || {}){ var x = resolverRef(op, String(op.lee[n]), usados); if (x) lee[n] = x; else errores.push(donde + ': no encuentro «' + op.lee[n] + '» (lee)'); }
    for (var m in op.toca || {}){ var y = resolverRef(op, String(op.toca[m]), usados); if (y && !prohibido(y)) toca[m] = y; else errores.push(donde + ': no puede tocar «' + op.toca[m] + '»'); }
    var div = document.createElement('div'); div.className = 'cv-del-tutor cv-caja'; div.dataset.cvCambio = id;
    div.innerHTML = sello() + (op.titulo ? '<h3>' + md(op.titulo) + '</h3>' : '') + '<iframe sandbox="allow-scripts" title="' + md(op.titulo || 'Interactivo del tutor') +
      '" style="width:100%;border:0;border-radius:10px;height:' + Math.max(80, Math.min(900, +op.alto || 320)) + 'px"></iframe><p class="cv-caja-error" hidden></p>';
    var fr = div.querySelector('iframe'), C = {el: div, est: {notas: [], resaltes: []}, vis: new Map(), oye: [], informes: []};
    fr.srcdoc = srcdoc(op, tema());
    var enviar = function(){
      if (!fr.contentWindow) return; var vs = {};
      for (var k in lee) vs[k] = valorDe(lee[k]);
      fr.contentWindow.postMessage({cvClase: 1, tema: tema(), valores: vs}, '*');
    };
    var oir = function(){ enviar(); };
    for (var k in lee){ lee[k].addEventListener('input', oir); lee[k].addEventListener('change', oir); }
    fr.addEventListener('load', enviar);
    var alMensaje = function(e){
      if (e.source !== fr.contentWindow) return;              // solo su propia caja
      var d = e.data || {}; if (!d.cvCaja) return;
      var a = api();
      if (d.que === 'error'){ var p = div.querySelector('.cv-caja-error'); p.hidden = false; p.textContent = '⚠ ' + d.texto; if (a && a.codigo_error) a.codigo_error(id, String(d.texto)); return; }
      if (d.que === 'reportar'){ C.informes.push(d.texto); if (a && a.codigo_informe) a.codigo_informe(id, String(d.texto)); return; }
      if (d.que === 'quitarNotas'){ C.est.notas = []; C.est.resaltes = []; pedir(); return; }
      var objetivo = (d.que === 'nota' ? (toca[d.nombre] || lee[d.nombre]) : toca[d.nombre]);
      if (!objetivo){ var pe = div.querySelector('.cv-caja-error'); pe.hidden = false; pe.textContent = '⚠ el código no puede tocar «' + d.nombre + '»'; return; }
      accion({tipo: d.que, el: objetivo, texto: d.texto, color: d.color, a: d.a}, valorDe(objetivo), C);
    };
    window.addEventListener('message', alMensaje);
    var mo = new MutationObserver(enviar); mo.observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
    C.quitar = function(){
      window.removeEventListener('message', alMensaje); mo.disconnect();
      for (var k in lee){ lee[k].removeEventListener('input', oir); lee[k].removeEventListener('change', oir); }
    };
    C.anclas = usados;
    (CAJAS[id] = CAJAS[id] || []).push(C);
    return div;
  }

  window.PuenteClase = {mapa: mapa, rect: rect, encuadrar: encuadrar, reservar: reservar,
                        validar: function(l){ return (l || []).map(revisar); }, hacer: hacer, devolver: devolver,
                        hayQueDevolver: function(){ return originales.size > 0; },
                        trabajando: function(){ return trabajando > 0; },
                        pregunta: pregunta, quitarPregunta: quitarPregunta, tema: tema, ejes: rangos,
                        aplicarCambios: aplicarCambios, quitarCambios: quitarCambios,
                        comportamientos: function(){ var o = {}; for (var k in REGLAS) o[k] = REGLAS[k].map(function(R){ return {estado: R.estado, notas: R.est.notas.map(function(n){ return n.texto; }), resaltes: R.est.resaltes.length}; });
                          for (var c in CAJAS) o[c] = CAJAS[c].map(function(C){ return {notas: C.est.notas.map(function(n){ return n.texto; }), informes: C.informes}; }); return o; }};
  reservar(0);
  actual = (modulo() || {}).id || null;
  function listo(){ var a = api(); if (a && a.puente_listo) a.puente_listo(); }
  if (api()) listo(); else window.addEventListener('pywebviewready', listo);
})();
