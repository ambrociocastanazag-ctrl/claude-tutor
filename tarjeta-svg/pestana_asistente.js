/* Pestaña «Asistente» de la Tarjeta SVG: un chat compacto (cabe en 420 px) que pregunta a asistente_tarjeta.py y dibuja
   en pequeño cada figura de la respuesta, con «Copiar» y «Llevar a su pestaña».

   Llama a:    window.pywebview.api.asistente_preguntar(texto, contexto) → la respuesta completa (texto) o {texto, contenidos}
               window.pywebview.api.asistente_reiniciar()   ·   api.copiar_svg(svg, nombre)
   Recibe:     window.Tarjeta.trozo(t)  (trozos de la respuesta mientras Claude escribe; si la cáscara no lo define, lo define este archivo)
   Necesita:   Figuras.grafica(spec, {tema, tam}) y Figuras.geometria(guion, {tema, tam}) (tutor-pantalla/motor_figuras.js) → {svg}
               y MathJax (tutor-pantalla/vendor/tex-svg.js) para las ecuaciones. Si faltan, la figura sale como texto.
   De la cáscara: Tarjeta.registrar / ir / aviso / cambio / tema, y (opcional) Tarjeta.contexto() → {pestana, contenido}
               con lo que hay en la pestaña desde la que llegó (para «retócalo»). Sin eso, el contexto es la última figura del chat.
   Clases CSS: prefijo ta-. Todo lo visual está en los tokens --ta-* de .ta-raiz (el diseño de Claude Design los cambia). */
(function () {
  'use strict';

  var CSS = '\
.ta-raiz{--ta-fondo:#ffffff;--ta-panel:#f4f5f8;--ta-tinta:#1b1d24;--ta-suave:#5d6272;--ta-linea:#d9dce4;--ta-acento:#2f6fed;--ta-acento-t:#fff;--ta-error:#c0392b;--ta-user:#e6eeff;\
  display:flex;flex-direction:column;height:100%;min-height:0;background:var(--ta-fondo);color:var(--ta-tinta);font:13.5px/1.45 "Segoe UI",system-ui,sans-serif}\
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .ta-raiz{--ta-fondo:#171a21;--ta-panel:#222733;--ta-tinta:#e8eaf0;--ta-suave:#9aa1b3;--ta-linea:#343b4a;--ta-acento:#6b9bff;--ta-acento-t:#0e1424;--ta-error:#ff7a6b;--ta-user:#26345a}}\
:root[data-theme="dark"] .ta-raiz{--ta-fondo:#171a21;--ta-panel:#222733;--ta-tinta:#e8eaf0;--ta-suave:#9aa1b3;--ta-linea:#343b4a;--ta-acento:#6b9bff;--ta-acento-t:#0e1424;--ta-error:#ff7a6b;--ta-user:#26345a}\
.ta-raiz *{box-sizing:border-box}\
.ta-msgs{flex:1;min-height:0;overflow-y:auto;padding:10px 10px 4px;display:flex;flex-direction:column;gap:10px}\
.ta-vacio{margin:auto 6px;color:var(--ta-suave);text-align:center;font-size:12.5px}\
.ta-vacio b{display:block;color:var(--ta-tinta);font-size:14px;margin-bottom:4px}\
.ta-vacio button{margin:8px 3px 0}\
.ta-m{max-width:100%;min-width:0;overflow-wrap:anywhere}\
.ta-m.ta-yo{align-self:flex-end;max-width:88%;background:var(--ta-user);border-radius:12px 12px 3px 12px;padding:6px 10px;white-space:pre-wrap}\
.ta-m.ta-ia{align-self:stretch}\
.ta-m.ta-error{color:var(--ta-error)}\
.ta-txt{margin:0 0 2px}\
.ta-txt code{background:var(--ta-panel);border-radius:4px;padding:0 4px;font:12px Consolas,monospace}\
.ta-pensando{color:var(--ta-suave);font-style:italic}\
.ta-pensando::after{content:"";display:inline-block;width:1.2em;text-align:left;animation:ta-puntos 1.2s steps(4) infinite}\
@keyframes ta-puntos{0%{content:""}25%{content:"."}50%{content:".."}75%{content:"..."}}\
.ta-fig{margin:6px 0 2px;border:1px solid var(--ta-linea);border-radius:10px;background:var(--ta-panel);overflow:hidden;min-width:0}\
.ta-lienzo{padding:8px;display:flex;justify-content:center;background:var(--ta-fondo);overflow:auto;max-height:260px}\
.ta-lienzo svg{display:block;max-width:100%;height:auto;max-height:240px}\
.ta-lienzo.ta-tex svg{max-width:100%}\
.ta-lienzo pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:12px Consolas,monospace;color:var(--ta-suave)}\
.ta-fig-pie{display:flex;align-items:center;gap:6px;padding:5px 7px;border-top:1px solid var(--ta-linea);flex-wrap:wrap}\
.ta-fig-tipo{font-size:11.5px;color:var(--ta-suave);margin-right:auto;min-width:0;overflow-wrap:anywhere}\
.ta-errs{padding:4px 8px;border-top:1px solid var(--ta-linea);color:var(--ta-error);font-size:11.5px;overflow-wrap:anywhere}\
.ta-btn{font:inherit;font-size:12.5px;border:1px solid var(--ta-linea);background:var(--ta-fondo);color:var(--ta-tinta);border-radius:7px;padding:3px 9px;cursor:pointer}\
.ta-btn:hover{border-color:var(--ta-acento)}\
.ta-btn.ta-prim{background:var(--ta-acento);border-color:var(--ta-acento);color:var(--ta-acento-t)}\
.ta-btn:focus-visible,.ta-caja textarea:focus-visible{outline:2px solid var(--ta-acento);outline-offset:1px}\
.ta-barra{display:flex;gap:6px;padding:8px 10px 10px;border-top:1px solid var(--ta-linea);align-items:flex-end}\
.ta-caja{flex:1;min-width:0;display:flex}\
.ta-caja textarea{flex:1;min-width:0;resize:none;font:inherit;color:var(--ta-tinta);background:var(--ta-panel);border:1px solid var(--ta-linea);border-radius:9px;padding:6px 9px;max-height:96px}\
.ta-enviar{height:32px;width:36px;padding:0}\
.ta-nuevo{height:32px;width:32px;padding:0}';

  var estado = { mensajes: [] };          // [{rol: 'yo'|'ia'|'error', texto, contenidos: [...]}]
  var raiz, lista, caja, btnEnviar, actual = null, esperando = false;
  var figuras = [];                       // [{contenido, lienzo, svg}] las del chat, en orden (la última manda en figura())

  /* ---------- texto ---------- */
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

  /* Lo que se copia o arrastra a Miro se dibuja SIEMPRE con Tarjeta.temaFigura ('claro'), aunque la ventana esté en oscuro.
     currentColor (MathJax) no existe fuera de la página: tinta fija. */
  function svgParaCopiar(f) {
    var d = dibujar(f.contenido, (window.Tarjeta && Tarjeta.temaFigura) || 'claro');
    return d.svg ? d.svg.replace(/currentColor/g, '#1b1d24') : null;
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

  function nuevaFigura(c) {
    var caja_ = document.createElement('div'); caja_.className = 'ta-fig';
    var f = { contenido: c, svg: null, lienzo: document.createElement('div'), errs: document.createElement('div') };
    f.errs.className = 'ta-errs';
    var pie = document.createElement('div'); pie.className = 'ta-fig-pie';
    var tipo = document.createElement('span'); tipo.className = 'ta-fig-tipo'; tipo.textContent = NOMBRE[c.tipo] || c.tipo;
    var copiar = boton('Copiar', 'Copiar el SVG', function () {
      var s = svgParaCopiar(f);
      if (!s) return aviso('No hay figura que copiar');
      var api = window.pywebview && pywebview.api;
      if (!api || !api.copiar_svg) return aviso('No puedo copiar desde aquí');
      Promise.resolve(api.copiar_svg(s, nombreDe(c))).then(function () { aviso('Copiado'); }, function () { aviso('No se pudo copiar'); });
    });
    pie.appendChild(tipo); pie.appendChild(copiar);
    if (PESTANA[c.tipo]) pie.appendChild(boton('Llevar a su pestaña', 'Abrirla en la pestaña ' + NOMBRE[c.tipo] + ' para retocarla', function () {
      if (window.Tarjeta && Tarjeta.ir) Tarjeta.ir(PESTANA[c.tipo], c);
    }, true));
    caja_.appendChild(f.lienzo); caja_.appendChild(f.errs); caja_.appendChild(pie);
    pintarFigura(f); figuras.push(f);
    f.caja = caja_;
    return caja_;
  }

  function boton(txt, titulo, fn, prim) {
    var b = document.createElement('button'); b.type = 'button'; b.className = 'ta-btn' + (prim ? ' ta-prim' : '');
    b.textContent = txt; b.title = titulo || ''; b.onclick = fn; return b;
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

  function rellenarIA(el, texto, contenidos) {
    el.innerHTML = '';
    if (texto) { var p = document.createElement('p'); p.className = 'ta-txt'; p.innerHTML = ligero(texto); el.appendChild(p); }
    contenidos.forEach(function (c) { el.appendChild(nuevaFigura(c)); });
  }

  function bajar() { lista.scrollTop = lista.scrollHeight; }

  function vacio() {
    var v = document.createElement('div'); v.className = 'ta-vacio';
    v.innerHTML = '<b>Pídeme una figura</b>Una gráfica, un triángulo con su altura, una ecuación…';
    ['grafica sen y cos de 0 a 2π', 'triángulo rectángulo con su altura', 'la fórmula general'].forEach(function (t) {
      v.appendChild(boton(t, 'Probar este pedido', function () { caja.value = t; enviar(); }));
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
    actual.el.innerHTML = '';
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
      var nuevo = boton('↺', 'Empezar de nuevo', reiniciar); nuevo.classList.add('ta-nuevo'); nuevo.setAttribute('aria-label', 'Empezar de nuevo');
      var cj = document.createElement('div'); cj.className = 'ta-caja';
      caja = document.createElement('textarea'); caja.rows = 1; caja.placeholder = 'Pide una figura…'; caja.setAttribute('aria-label', 'Pide una figura');
      caja.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar(); } });
      caja.addEventListener('input', ajustarCaja);
      cj.appendChild(caja);
      btnEnviar = boton('➤', 'Enviar (Enter)', enviar, true); btnEnviar.classList.add('ta-enviar'); btnEnviar.setAttribute('aria-label', 'Enviar');
      barra.appendChild(nuevo); barra.appendChild(cj); barra.appendChild(btnEnviar);
      raiz.appendChild(lista); raiz.appendChild(barra); cont.appendChild(raiz);
      repintarTodo();
      // las figuras se redibujan al cambiar el tema (claro ↔ oscuro)
      try {
        new MutationObserver(function () { figuras.forEach(pintarFigura); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
        matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () { figuras.forEach(pintarFigura); });
      } catch (e) { /* sin observador: se redibujan al volver a abrir */ }
    },

    figura: function () {
      var f = ultimaFigura();
      if (!f || !f.svg) return null;
      return { svg: svgParaCopiar(f), nombre: nombreDe(f.contenido) };
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
