/* Pestaña «Asistente» de la Tarjeta SVG: un chat compacto (cabe en 420 px) que pregunta a asistente_tarjeta.py y dibuja
   en pequeño cada figura de la respuesta, con «Copiar» y «Llevar a su pestaña».

   Llama a:    window.pywebview.api.asistente_preguntar(texto, contexto) → la respuesta completa (texto) o {texto, contenidos}
               window.pywebview.api.asistente_reiniciar()   ·   api.copiar_svg(svg, nombre)
   Recibe:     window.Tarjeta.trozo(t)  (trozos de la respuesta mientras Claude escribe; si la cáscara no lo define, lo define este archivo)
   Necesita:   Figuras.grafica(spec, {tema, tam}) y Figuras.geometria(guion, {tema, tam}) (tutor-pantalla/motor_figuras.js) → {svg}
               y MathJax (tutor-pantalla/vendor/tex-svg.js) para las ecuaciones. Si faltan, la figura sale como texto.
   De la cáscara: Tarjeta.registrar / ir / aviso / cambio / tema, y (opcional) Tarjeta.contexto() → {pestana, contenido}
               con lo que hay en la pestaña desde la que llegó (para «retócalo»). Sin eso, el contexto es la última figura del chat.
   Clases CSS: prefijo ta-. Los colores salen de los tokens de la cáscara (diseño de Claude Design: --sup, --borde, --acento…). */
(function () {
  'use strict';

  var CSS = '\
.ta-raiz{display:flex;flex-direction:column;height:100%;min-height:0;color:var(--tinta)}\
.ta-raiz *{box-sizing:border-box}\
.ta-msgs{flex:1;min-height:0;overflow-y:auto;padding:10px 8px 6px;display:flex;flex-direction:column;gap:12px;user-select:text}\
.ta-msgs>*{flex:none}\
.ta-vacio{margin:auto 6px;color:var(--tenue);text-align:center;font-size:13px}\
.ta-vacio b{display:block;color:var(--tinta);font-size:14px;margin-bottom:4px}\
.ta-chip{margin:8px 3px 0;height:28px;padding:0 11px;border:1px solid var(--borde);border-radius:999px;background:var(--sup);font:600 12px var(--f);color:var(--tinta)}\
.ta-chip:hover{border-color:var(--acento);background:var(--sup-2)}\
.ta-m{max-width:100%;min-width:0;overflow-wrap:anywhere}\
.ta-m.ta-yo{align-self:flex-end;max-width:86%;padding:7px 11px;border-radius:12px 12px 4px 12px;background:var(--acento-suave);font-size:13.5px;white-space:pre-wrap}\
.ta-m.ta-ia{align-self:stretch}\
.ta-m.ta-error{align-self:stretch;color:var(--error);font-size:13px}\
.ta-quien{display:flex;align-items:center;gap:6px;font-weight:700;font-size:12.5px}\
.ta-avatar{width:20px;height:20px;border-radius:6px;background:var(--acento);color:var(--sobre-acento);display:grid;place-items:center}\
.ta-txt{margin:4px 0 0;font-size:13.5px;text-wrap:pretty}\
.ta-txt code{background:var(--hundido);border-radius:4px;padding:0 4px;font:12px var(--mono)}\
.ta-pensando{margin-top:4px;color:var(--tenue);font-style:italic;font-size:13px}\
.ta-pensando::after{content:"";display:inline-block;width:1.2em;text-align:left;animation:ta-puntos 1.2s steps(4) infinite}\
@keyframes ta-puntos{0%{content:""}25%{content:"."}50%{content:".."}75%{content:"..."}}\
.ta-fig{margin-top:8px;border:1px solid var(--borde);border-radius:10px;overflow:hidden;background:var(--sup);display:flex;flex-direction:column;min-width:0}\
.ta-lienzo{height:218px;flex:none;padding:10px;display:flex;align-items:center;justify-content:center;overflow:hidden;background:repeating-conic-gradient(var(--cuadro) 0 25%,transparent 0 50%) 0 0/14px 14px}\
.ta-lienzo svg{display:block;max-width:100%;max-height:100%}\
.ta-lienzo.ta-tex svg{max-width:100%}\
.ta-lienzo pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:12px var(--mono);color:var(--tenue);align-self:flex-start;max-height:100%;overflow:auto}\
.ta-fig-pie{display:flex;align-items:center;gap:5px;padding:6px;border-top:1px solid var(--borde)}\
.ta-esp{flex:1}\
.ta-errs{padding:5px 8px;border-top:1px solid var(--borde);color:var(--error);font-size:11.5px;overflow-wrap:anywhere}\
.ta-btn{height:30px;display:inline-flex;align-items:center;justify-content:center;gap:5px;padding:0 10px;border-radius:8px;border:1px solid var(--borde);background:var(--sup);font:700 12.5px var(--f);color:var(--tinta);white-space:nowrap}\
.ta-btn:hover{background:var(--sup-2)}\
.ta-btn.ta-prim{background:var(--acento);border-color:var(--acento);color:var(--sobre-acento)}\
.ta-btn.ta-prim:hover{background:var(--acento-2);border-color:var(--acento-2)}\
.ta-btn.ta-hecho{background:var(--ok);border-color:var(--ok);color:var(--sobre-acento)}\
.ta-btn.ta-hecho-2{color:var(--ok);border-color:var(--ok)}\
.ta-barra{display:flex;gap:6px;align-items:center;margin:0 8px 8px;padding:4px 4px 4px 10px;border:1px solid var(--acento);border-radius:10px;background:var(--sup)}\
.ta-caja{flex:1;min-width:0;display:flex}\
.ta-caja textarea{flex:1;min-width:0;resize:none;border:0;background:none;outline:none;font:500 13.5px/20px var(--f);color:var(--tinta);padding:5px 0;max-height:96px}\
.ta-caja textarea::placeholder{color:var(--tenue)}\
.ta-enviar,.ta-nuevo{flex:none;width:30px;height:30px;border-radius:7px;border:0;background:var(--hundido);color:var(--tenue);display:grid;place-items:center;padding:0;font:600 15px/1 var(--f)}\
.ta-enviar:hover:not(:disabled){background:var(--acento);color:var(--sobre-acento)}\
.ta-enviar:disabled{opacity:.5;cursor:default}\
.ta-nuevo{background:none}\
.ta-nuevo:hover{background:var(--sup-2);color:var(--tinta)}';

  var estado = { mensajes: [] };          // [{rol: 'yo'|'ia'|'error', texto, contenidos: [...]}]
  var raiz, lista, caja, btnEnviar, actual = null, esperando = false;
  var figuras = [];                       // [{contenido, lienzo, svg}] las del chat, en orden (la última manda en figura())

  /* ---------- texto ---------- */
  function ic(n, t) { return window.Tarjeta && Tarjeta.icono ? Tarjeta.icono(n, t) : ''; }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  function tex(latex, display) {
    var MJ = window.MathJax;
    if (!MJ || !MJ.tex2svg) return null;
    try {
      var n = MJ.tex2svg(latex, { display: !!display });
      var s = n.querySelector('svg');
      return s ? s.outerHTML : null;
    } catch (e) { return null; }
  }

  function ligero(texto) {                 // **negrita**, `código`, $fórmula pequeña$ y saltos de línea
    var h = esc(texto).replace(/`([^`\n]+)`/g, '<code>$1</code>').replace(/\*\*([^*\n]+)\*\*/g, '<b>$1</b>');
    h = h.replace(/\$([^$\n]+)\$/g, function (m, f) {
      var s = tex(f.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&'), false);
      return s ? '<span class="ta-tex-en">' + s + '</span>' : m;
    });
    return h.replace(/\n/g, '<br>');
  }

  /* Mientras Claude escribe: los bloques y las ecuaciones $$..$$ (completos o a medias) no se enseñan como texto. */
  function sinBloques(t) {
    t = t.replace(/```[\s\S]*?```/g, '').replace(/```[\s\S]*$/, '').replace(/\$\$[\s\S]*?\$\$/g, '').replace(/\$\$[\s\S]*$/, '');
    return t.replace(/\n{3,}/g, '\n\n').trim();
  }

  /* El mismo reparto que asistente_tarjeta.separar() de Python (por si la respuesta llega como texto crudo). */
  function separar(texto) {
    texto = texto || '';
    var cont = [], cortes = [], m, re = /```[ \t]*([A-Za-z]+)[ \t]*([^\n]*)\n([\s\S]*?)```/g;
    while ((m = re.exec(texto))) cortes.push({ a: m.index, b: re.lastIndex, tipo: 'bloque', m: m });
    var re2 = /\$\$([\s\S]+?)\$\$/g;
    while ((m = re2.exec(texto))) {
      var dentro = cortes.some(function (c) { return c.tipo === 'bloque' && m.index >= c.a && m.index < c.b; });
      if (!dentro) cortes.push({ a: m.index, b: re2.lastIndex, tipo: 'tex', m: m });
    }
    cortes.sort(function (x, y) { return x.a - y.a; });
    var out = '', pos = 0;
    cortes.forEach(function (c) {
      out += texto.slice(pos, c.a); pos = c.b;
      if (c.tipo === 'tex') { cont.push({ tipo: 'latex', latex: c.m[1].trim() }); return; }
      var lang = c.m[1].toLowerCase(), resto = c.m[2].trim(), cuerpo = c.m[3].replace(/^\n+|\n+$/g, '');
      if (lang === 'grafica') {
        try { var spec = JSON.parse(cuerpo.charAt(0) === '{' ? cuerpo : resto + cuerpo); if (spec && typeof spec === 'object') cont.push({ tipo: 'grafica', spec: spec }); } catch (e) { /* JSON roto: no se cuenta */ }
      } else if (lang === 'geometria') {
        var g = cuerpo.split('\n').map(function (l) { return l.replace(/\s+$/, ''); }).filter(function (l) { return l.trim(); }).join('\n');
        if (g) cont.push({ tipo: 'geometria', guion: g });
      } else if (lang === 'svg') {
        if (cuerpo.indexOf('<svg') >= 0) { var o = { tipo: 'svg', svg: cuerpo.trim() }; if (resto) o.pie = resto; cont.push(o); }
      } else out += c.m[0];
    });
    out += texto.slice(pos);
    return { texto: out.replace(/\n{3,}/g, '\n\n').trim(), contenidos: cont };
  }

  /* ---------- figuras ---------- */
  var NOMBRE = { grafica: 'Gráfica', geometria: 'Geometría', latex: 'Ecuación', svg: 'Figura SVG' };
  var PESTANA = { grafica: 'grafica', geometria: 'geometria', latex: 'escribir' };       // el SVG libre no tiene pestaña

  function limpiarSvg(s) {
    return String(s).replace(/<script[\s\S]*?<\/script>/gi, '').replace(/\son\w+\s*=\s*("[^"]*"|'[^']*')/gi, '')
      .replace(/(xlink:)?href\s*=\s*("(?!#)[^"]*"|'(?!#)[^']*')/gi, '');
  }

  function tema() { return (window.Tarjeta && Tarjeta.tema) || (matchMedia('(prefers-color-scheme: dark)').matches ? 'oscuro' : 'claro'); }

  /* → {svg, errores, texto} (texto: lo que se enseña si no hay motor o falla) */
  function dibujar(c, temaFig) {
    var o = { svg: null, errores: [], texto: null }, th = temaFig || tema();
    try {
      if (c.tipo === 'grafica') {
        if (!window.Figuras || !Figuras.grafica) o.texto = JSON.stringify(c.spec, null, 1);
        else o.svg = Figuras.grafica(c.spec, { tema: th, tam: 'S' }).svg;
      } else if (c.tipo === 'geometria') {
        if (!window.Figuras || !Figuras.geometria) o.texto = c.guion;
        else { var r = Figuras.geometria(c.guion, { tema: th, tam: 'S' }); o.svg = r.svg; o.errores = r.errores || []; }
      } else if (c.tipo === 'latex') {
        o.svg = tex(c.latex, true);
        if (!o.svg) o.texto = '$$' + c.latex + '$$';
      } else if (c.tipo === 'svg') {
        var s = window.Figuras && Figuras.svgLibre ? Figuras.svgLibre(c.svg, { tema: th }) : c.svg;
        o.svg = limpiarSvg(s && s.svg ? s.svg : s);
      }
    } catch (e) { o.texto = 'No pude dibujarla: ' + (e && e.message || e); }
    return o;
  }

  /* Lo que se copia o se arrastra se dibuja SIEMPRE con Tarjeta.temaFigura ('claro'), aunque la ventana esté en oscuro.
     currentColor (MathJax) no existe fuera de la página: tinta fija. */
  function svgParaCopiar(f, t) {                    // t: el tema de la ventana, solo para enseñarla en la tarjeta plegada
    var th = t || (window.Tarjeta && Tarjeta.temaFigura) || 'claro';
    var d = dibujar(f.contenido, th);
    return d.svg ? d.svg.replace(/currentColor/g, th === 'oscuro' ? '#e8eaed' : '#1b1d24') : null;
  }

  function nombreDe(c) {
    var t = c.tipo === 'grafica' ? (c.spec && c.spec.titulo) : c.tipo === 'svg' ? c.pie : '';
    return (t || NOMBRE[c.tipo] || 'figura').replace(/[^\wáéíóúüñÁÉÍÓÚÑ ().-]+/g, '').trim().slice(0, 40) || 'figura';
  }

  function pintarFigura(f) {
    var d = dibujar(f.contenido);
    f.svg = d.svg;
    f.lienzo.className = 'ta-lienzo' + (f.contenido.tipo === 'latex' ? ' ta-tex' : '');
    f.lienzo.innerHTML = d.svg ? d.svg : '<pre>' + esc(d.texto || '') + '</pre>';
    f.errs.hidden = !d.errores.length;
    f.errs.innerHTML = d.errores.map(function (e) { return 'Línea ' + esc(e.linea) + ': ' + esc(e.mensaje); }).join('<br>');
  }

  var DESTINO = { grafica: 'Gráfica', geometria: 'Geometría', latex: 'Escribir' };

  // un botón que, al copiar, se pone verde un momento
  function copiaDe(f, c, tipo, b) {
    var s = svgParaCopiar(f);
    if (!s) return aviso('No hay figura que copiar');
    var T = window.Tarjeta, api = window.pywebview && pywebview.api;
    var listo = function (ok) {
      if (!ok) return;
      var l = b.querySelector('.lbl'), antes = b.dataset.lbl || l.textContent; b.dataset.lbl = antes;
      l.textContent = tipo === 'svg' ? 'SVG copiado' : 'Copiado'; b.classList.add(tipo === 'svg' ? 'ta-hecho' : 'ta-hecho-2');
      var i = b.querySelector('.ta-ic'); if (i) i.innerHTML = ic('hecho', 15);
      clearTimeout(b._t); b._t = setTimeout(function () { l.textContent = antes; b.classList.remove('ta-hecho', 'ta-hecho-2'); if (i) i.innerHTML = ic('copiar', 15); }, 1800);
    };
    if (T && T.copiar) return T.copiar(tipo, s, nombreDe(c)).then(listo);
    if (tipo !== 'svg' || !api || !api.copiar_svg) return aviso('No puedo copiar desde aquí');
    Promise.resolve(api.copiar_svg(s, nombreDe(c))).then(function () { listo(true); }, function () { aviso('No se pudo copiar'); });
  }

  function nuevaFigura(c) {
    var caja_ = document.createElement('div'); caja_.className = 'ta-fig';
    var f = { contenido: c, svg: null, lienzo: document.createElement('div'), errs: document.createElement('div') };
    f.errs.className = 'ta-errs';
    var pie = document.createElement('div'); pie.className = 'ta-fig-pie';
    var svg = boton('<span class="ta-ic">' + ic('copiar', 15) + '</span><span class="lbl">Copiar SVG</span>', 'Copiar el SVG', function (e) { copiaDe(f, c, 'svg', e.currentTarget); }, true, true);
    var png = boton('<span class="lbl">PNG</span>', 'Copiar como imagen PNG', function (e) { copiaDe(f, c, 'png', e.currentTarget); }, false, true);
    var esp = document.createElement('span'); esp.className = 'ta-esp';
    pie.appendChild(svg); pie.appendChild(png); pie.appendChild(esp);
    if (PESTANA[c.tipo]) pie.appendChild(boton(ic('llevar', 15) + DESTINO[c.tipo], 'Abrirla en la pestaña ' + DESTINO[c.tipo] + ' para retocarla', function () {
      if (window.Tarjeta && Tarjeta.ir) Tarjeta.ir(PESTANA[c.tipo], c);
    }, false, true));
    caja_.appendChild(f.lienzo); caja_.appendChild(f.errs); caja_.appendChild(pie);
    pintarFigura(f); figuras.push(f);
    f.caja = caja_;
    return caja_;
  }

  function boton(txt, titulo, fn, prim, html) {
    var b = document.createElement('button'); b.type = 'button'; b.className = 'ta-btn' + (prim ? ' ta-prim' : '');
    if (html) b.innerHTML = txt; else b.textContent = txt;
    b.title = titulo || ''; b.onclick = fn; return b;
  }
  function aviso(t) { if (window.Tarjeta && Tarjeta.aviso) Tarjeta.aviso(t); }

  /* ---------- mensajes ---------- */
  function quitarVacio() { var v = lista.querySelector('.ta-vacio'); if (v) v.remove(); }

  function pintarMensaje(m) {
    quitarVacio();
    var el = document.createElement('div');
    el.className = 'ta-m ta-' + m.rol;
    if (m.rol === 'yo' || m.rol === 'error') el.textContent = m.texto;
    else rellenarIA(el, m.texto, m.contenidos || []);
    lista.appendChild(el); bajar();
    return el;
  }

  function quien() {
    var q = document.createElement('div'); q.className = 'ta-quien';
    q.innerHTML = '<span class="ta-avatar">' + ic('asistente', 13) + '</span>Asistente'; return q;
  }
  function rellenarIA(el, texto, contenidos) {
    el.innerHTML = ''; el.appendChild(quien());
    if (texto) { var p = document.createElement('p'); p.className = 'ta-txt'; p.innerHTML = ligero(texto); el.appendChild(p); }
    contenidos.forEach(function (c) { el.appendChild(nuevaFigura(c)); });
  }

  function bajar() { lista.scrollTop = lista.scrollHeight; }

  function vacio() {
    var v = document.createElement('div'); v.className = 'ta-vacio';
    v.innerHTML = '<b>Pídeme una figura</b>Una gráfica, un triángulo con su altura, una ecuación…';
    ['grafica sen y cos de 0 a 2π', 'triángulo rectángulo con su altura', 'la fórmula general'].forEach(function (t) {
      var b = boton(t, 'Probar este pedido', function () { caja.value = t; enviar(); }); b.className = 'ta-chip'; v.appendChild(b);
    });
    lista.appendChild(v);
  }

  /* ---------- enviar / recibir ---------- */
  function ultimaFigura() { return figuras.length ? figuras[figuras.length - 1] : null; }

  function contexto() {
    var c = null;
    try { c = window.Tarjeta && Tarjeta.contexto ? Tarjeta.contexto() : null; } catch (e) { c = null; }
    if (c && c.contenido && c.pestana !== 'asistente') return c;
    var u = ultimaFigura();
    return u ? { pestana: 'asistente (última figura del chat)', contenido: u.contenido } : (c || null);
  }

  window.Tarjeta = window.Tarjeta || {};
  Tarjeta.trozo = function (t) { recibirTrozo(t); };

  function recibirTrozo(t) {
    if (!actual) return;
    actual.crudo += t;
    var visible = sinBloques(actual.crudo);
    var hayBloque = /```|\$\$/.test(actual.crudo);
    actual.el.innerHTML = ''; actual.el.appendChild(quien());
    if (visible) { var p = document.createElement('p'); p.className = 'ta-txt'; p.textContent = visible; actual.el.appendChild(p); }
    if (hayBloque) { var d = document.createElement('div'); d.className = 'ta-pensando'; d.textContent = 'Dibujando la figura'; actual.el.appendChild(d); }
    else if (!visible) { var q = document.createElement('div'); q.className = 'ta-pensando'; q.textContent = 'Pensando'; actual.el.appendChild(q); }
    bajar();
  }

  function enviar() {
    var texto = caja.value.trim();
    if (!texto || esperando) return;
    var api = window.pywebview && pywebview.api;
    caja.value = ''; ajustarCaja();
    var ctx = contexto();
    estado.mensajes.push({ rol: 'yo', texto: texto });
    pintarMensaje({ rol: 'yo', texto: texto });
    if (!api || !api.asistente_preguntar) {
      estado.mensajes.push({ rol: 'error', texto: 'El asistente no está disponible en esta ventana.' });
      return void pintarMensaje({ rol: 'error', texto: 'El asistente no está disponible en esta ventana.' });
    }
    esperando = true; btnEnviar.disabled = true;
    var el = pintarMensaje({ rol: 'ia', texto: '', contenidos: [] });
    actual = { el: el, crudo: '' };
    recibirTrozo('');
    Promise.resolve(api.asistente_preguntar(texto, ctx)).then(function (r) {
      var crudo = typeof r === 'string' ? r : (r && (r.crudo || r.texto)) || actual.crudo;
      var res = (r && typeof r === 'object' && r.contenidos) ? { texto: r.texto || '', contenidos: r.contenidos } : separar(crudo);
      figurasDe(el);
      rellenarIA(el, res.texto, res.contenidos);
      estado.mensajes.push({ rol: 'ia', texto: res.texto, contenidos: res.contenidos });
      if (estado.mensajes.length > 24) estado.mensajes = estado.mensajes.slice(-24);
      if (res.contenidos.length && window.Tarjeta && Tarjeta.cambio) Tarjeta.cambio();
    }, function (e) {
      el.remove();
      var msg = 'No pude contestar: ' + ((e && e.message) || e || 'error');
      estado.mensajes.push({ rol: 'error', texto: msg }); pintarMensaje({ rol: 'error', texto: msg });
    }).then(function () { actual = null; esperando = false; btnEnviar.disabled = false; bajar(); caja.focus(); });
  }

  function figurasDe(el) {                 // quita del registro las figuras de un mensaje que se vuelve a pintar
    figuras = figuras.filter(function (f) { return !el.contains(f.caja); });
  }

  function reiniciar() {
    var api = window.pywebview && pywebview.api;
    if (api && api.asistente_reiniciar) try { api.asistente_reiniciar(); } catch (e) { /* sigue */ }
    estado.mensajes = []; figuras = []; lista.innerHTML = ''; vacio();
    if (window.Tarjeta && Tarjeta.cambio) Tarjeta.cambio();
  }

  function ajustarCaja() { caja.style.height = 'auto'; caja.style.height = Math.min(96, caja.scrollHeight + 2) + 'px'; }

  function repintarTodo() {
    var antes = estado.mensajes.slice();
    lista.innerHTML = ''; figuras = [];
    if (!antes.length) return vacio();
    antes.forEach(function (m) { pintarMensaje(m); });
  }

  /* ---------- la pestaña ---------- */
  Tarjeta.registrar('asistente', {
    titulo: 'Asistente',
    icono: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/><path d="M19 15l.7 1.8L21.5 17.5l-1.8.7L19 20l-.7-1.8-1.8-.7 1.8-.7z"/></svg>',

    montar: function (cont) {
      if (!document.getElementById('ta-css')) {
        var st = document.createElement('style'); st.id = 'ta-css'; st.textContent = CSS; document.head.appendChild(st);
      }
      raiz = document.createElement('div'); raiz.className = 'ta-raiz';
      lista = document.createElement('div'); lista.className = 'ta-msgs'; lista.setAttribute('aria-live', 'polite');
      var barra = document.createElement('div'); barra.className = 'ta-barra';
      var nuevo = boton('↺', 'Empezar de nuevo', reiniciar); nuevo.className = 'ta-nuevo'; nuevo.setAttribute('aria-label', 'Empezar de nuevo');
      var cj = document.createElement('div'); cj.className = 'ta-caja';
      caja = document.createElement('textarea'); caja.rows = 1; caja.placeholder = 'Pídele una figura…'; caja.setAttribute('aria-label', 'Pide una figura');
      caja.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar(); } });
      caja.addEventListener('input', ajustarCaja);
      cj.appendChild(caja);
      btnEnviar = boton(ic('enviar', 16), 'Enviar (Enter)', enviar, false, true); btnEnviar.className = 'ta-enviar'; btnEnviar.setAttribute('aria-label', 'Enviar');
      barra.appendChild(cj); barra.appendChild(nuevo); barra.appendChild(btnEnviar);
      raiz.appendChild(lista); raiz.appendChild(barra); cont.appendChild(raiz);
      repintarTodo();
      // las figuras se redibujan al cambiar el tema (claro ↔ oscuro)
      try {
        new MutationObserver(function () { figuras.forEach(pintarFigura); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
        matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () { figuras.forEach(pintarFigura); });
      } catch (e) { /* sin observador: se redibujan al volver a abrir */ }
    },

    figura: function (t) {                        // t ('claro'|'oscuro'): para enseñarla en la ventana; sin él, la que se copia
      var f = ultimaFigura();
      if (!f || !f.svg) return null;
      return { svg: svgParaCopiar(f, t), nombre: nombreDe(f.contenido) };
    },

    cargar: function (contenido) {                // algo que llega de fuera: se enseña como figura del chat
      if (!contenido || !contenido.tipo || !lista) return;
      var m = { rol: 'ia', texto: '', contenidos: [contenido] };
      estado.mensajes.push(m); pintarMensaje(m);
    },

    estado: function () { return { mensajes: estado.mensajes.slice(-24) }; },

    restaurar: function (e) {
      if (!e || !Array.isArray(e.mensajes)) return;
      estado.mensajes = e.mensajes.filter(function (m) { return m && typeof m.texto === 'string'; });
      if (lista) repintarTodo();
    }
  });
})();
